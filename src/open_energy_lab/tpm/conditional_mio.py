"""Lazy compilation and direct execution of conditional TPM circuit pairs."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path

from .artifact import TPMArtifact, load_tpm_artifact
from .conditional import (
    TPMConditionalCircuit,
    TPMConditionalCircuitNode,
    TPMConditionalCompilationRequest,
    TPMConditionalEncodingPolicy,
    TPMConditionalEvaluation,
    TPMConditionalEvent,
    TPMConditionalFeatureValidity,
    TPMConditionalPair,
    TPMConditionalSourceReference,
)
from .domains import (
    TPMApproximationDomain,
    TPMCompiledValidityRecord,
    TPMFeatureDomain,
    TPMNormalizationSpec,
)
from .mio import compile_spflow_model_to_mio, condition_compiled_spflow_mio
from .optional_spflow import (
    CURRENT_SPFLOW_BACKEND_GENERATION,
    REQUIRED_SPFLOW_VERSION,
    load_spflow_payload,
    require_spflow_backend,
)
from .query import marginalize_spflow_model


_DISCRETE_PROBABILITY_FLOOR = 1e-12


class TPMConditionalEvaluationError(ValueError):
    """Raised when a finite raw evaluation violates conditional probability meaning."""

    def __init__(self, message: str, *, evaluation: TPMConditionalEvaluation) -> None:
        self.evaluation = evaluation
        super().__init__(message)


def compile_conditional_mio_pair(
    request: TPMConditionalCompilationRequest,
) -> TPMConditionalPair:
    """Compile one eligible persisted current-SPFlow artifact into a pair."""

    if not isinstance(request, TPMConditionalCompilationRequest):
        raise TypeError("request must be a TPMConditionalCompilationRequest")
    artifact = load_tpm_artifact(request.source_artifact)
    _validate_eligible_artifact(artifact)
    require_spflow_backend()
    feature_specs = artifact.feature_specs
    feature_by_name = {spec.feature_name: spec for spec in feature_specs}
    if request.event_target not in feature_by_name:
        raise ValueError(
            f"conditional event target {request.event_target!r} is absent from the artifact"
        )
    expected_event = str(artifact.target_definition.get("event_target_name", ""))
    if request.event_target != expected_event:
        raise ValueError(
            f"conditional event target must match artifact event target {expected_event!r}"
        )
    event_spec = feature_by_name[request.event_target]
    event_ordering = tuple(
        event_spec.ordering or event_spec.discrete_values
    )
    if event_spec.feature_type != "binary" or len(event_ordering) != 2:
        raise ValueError("conditional event target must have an exact binary domain")
    if request.event_value not in event_ordering:
        raise ValueError(
            f"conditional event value {request.event_value!r} is not in "
            f"{event_ordering!r}"
        )
    event_index = event_ordering.index(request.event_value)

    unknown_decisions = [
        name for name in request.retained_decisions if name not in feature_by_name
    ]
    if unknown_decisions:
        raise ValueError(
            "unknown retained decision features: " + ", ".join(unknown_decisions)
        )
    approximation_domains = _validate_retained_features_and_domains(
        request=request,
        feature_by_name=feature_by_name,
    )
    runtime_payload = load_spflow_payload(artifact)
    if runtime_payload is None:
        raise RuntimeError("eligible conditional compilation requires a current-SPFlow sidecar")
    _validate_current_payload(runtime_payload, artifact=artifact)
    model = runtime_payload.get("model")
    if model is None:
        raise RuntimeError("current-SPFlow sidecar does not contain a fitted model")

    retained_names = set(request.retained_decisions) | {request.event_target}
    marginalized_indices = tuple(
        index
        for index, spec in enumerate(feature_specs)
        if spec.feature_name not in retained_names
    )
    retained_model = (
        marginalize_spflow_model(model, marginalized_indices)
        if marginalized_indices
        else model
    )
    leaf_configuration = dict(request.encoding.leaf_configuration)
    relative_breakpoints = leaf_configuration.get(
        "relative_breakpoints", leaf_configuration.get("breakpoints")
    )
    compiled = compile_spflow_model_to_mio(
        retained_model,
        fitted_artifact=artifact,
        approximation_domains=approximation_domains,
        breakpoint_count=int(leaf_configuration.get("breakpoint_count", 5)),
        breakpoints=(
            tuple(float(value) for value in relative_breakpoints)
            if relative_breakpoints is not None
            else None
        ),
        mio_epsilon=float(leaf_configuration["mio_epsilon"]),
    )
    _validate_compiled_origin(compiled, artifact=artifact)
    numerator_payload = condition_compiled_spflow_mio(
        compiled,
        decision_features=request.retained_decisions,
        event_target_name=request.event_target,
        event_value_index=event_index,
    )
    denominator_payload = condition_compiled_spflow_mio(
        compiled,
        decision_features=request.retained_decisions,
        event_target_name=request.event_target,
        event_value_index=None,
    )
    if numerator_payload["source_model"] != denominator_payload["source_model"]:
        raise ValueError("conditional numerator and denominator do not share one source model")
    resolved_encoding = _resolve_encoding_policy(
        request.encoding,
        compiled=compiled,
    )
    validity = _build_feature_validity(
        request.retained_decisions,
        feature_by_name=feature_by_name,
        compiled=compiled,
    )
    source_model = numerator_payload["source_model"]
    source_reference = TPMConditionalSourceReference(
        artifact_id=artifact.artifact_id,
        artifact_schema_version=artifact.schema_version,
        manifest_reference=_portable_manifest_reference(
            request.source_artifact, artifact=artifact
        ),
        sidecar_sha256=artifact.payload_hash,
        backend_generation=artifact.backend_generation,
        backend_api_version=artifact.backend_api_version,
        model_digest=str(source_model["model_digest"]),
    )
    numerator = _circuit_from_conditioned_payload(numerator_payload)
    denominator = _circuit_from_conditioned_payload(denominator_payload)
    marginalized_features = tuple(
        spec.feature_name
        for spec in feature_specs
        if spec.feature_name not in retained_names
    )
    return TPMConditionalPair(
        source=source_reference,
        event=TPMConditionalEvent(
            feature_name=request.event_target,
            declared_value=request.event_value,
            model_index=event_index,
        ),
        feature_schema=tuple(
            spec.to_dict(schema_version="v3") for spec in feature_specs
        ),
        retained_decisions=request.retained_decisions,
        marginalized_features=marginalized_features,
        validity=validity,
        encoding=resolved_encoding,
        numerical_policy=request.numerical_policy,
        numerator=numerator,
        denominator=denominator,
        provenance={
            "artifact_payload_sha256": artifact.payload_hash,
            "base_compiler_schema_version": compiled.get("schema_version"),
            "base_compiler_version": compiled.get("compiler_version"),
            "marginalization_policy": (
                "marginalize-all-nonevent-nondecision-features"
            ),
        },
    )


def evaluate_conditional_mio_pair(
    pair: TPMConditionalPair,
    *,
    declared_domain_assignments: Mapping[str, object] | None = None,
    model_coordinate_assignments: Mapping[str, object] | None = None,
) -> TPMConditionalEvaluation:
    """Execute the exact max or PWL semantics persisted by one pair."""

    if not isinstance(pair, TPMConditionalPair):
        raise TypeError("pair must be a TPMConditionalPair")
    supplied = (
        declared_domain_assignments is not None,
        model_coordinate_assignments is not None,
    )
    if sum(supplied) != 1:
        raise ValueError(
            "direct conditional evaluation requires exactly one complete assignment mode"
        )
    if declared_domain_assignments is not None:
        assignment_mode = "declared-domain"
        assignments = declared_domain_assignments
    else:
        assignment_mode = "model-coordinate"
        assignments = model_coordinate_assignments
    if not isinstance(assignments, Mapping):
        raise TypeError("conditional assignments must be a mapping")
    expected_names = set(pair.retained_decisions)
    actual_names = {str(name) for name in assignments}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unknown extra " + ", ".join(extra))
        raise ValueError(
            "conditional assignments must be complete: " + "; ".join(details)
        )
    ordered_assignments = {
        feature_name: assignments[feature_name]
        for feature_name in pair.retained_decisions
    }
    coordinates = _resolve_assignment_coordinates(
        pair,
        assignments=ordered_assignments,
        assignment_mode=assignment_mode,
    )
    numerator_log = _evaluate_circuit(
        pair.numerator,
        coordinates=coordinates,
        encoding=pair.encoding,
    )
    denominator_log = _evaluate_circuit(
        pair.denominator,
        coordinates=coordinates,
        encoding=pair.encoding,
    )
    conditional_log_risk = numerator_log - denominator_log
    if not math.isfinite(conditional_log_risk):
        raise ValueError("conditional log-risk must be finite")
    try:
        probability = math.exp(conditional_log_risk)
    except OverflowError as exc:
        raise ValueError("conditional probability must be finite") from exc
    if not math.isfinite(probability):
        raise ValueError("conditional probability must be finite")
    limit = float(
        pair.numerical_policy.tolerances["positive_log_risk_limit"]
    )
    classification = (
        "positive-numerical-noise"
        if 0.0 < conditional_log_risk <= limit
        else "valid"
    )
    evaluation = TPMConditionalEvaluation(
        pair_id=pair.pair_id,
        assignment_mode=assignment_mode,
        assignments=ordered_assignments,
        numerator_log=numerator_log,
        denominator_log=denominator_log,
        conditional_log_risk=conditional_log_risk,
        conditional_probability=probability,
        classification=classification,
    )
    if conditional_log_risk > limit:
        raise TPMConditionalEvaluationError(
            "compiled conditional log-risk exceeds its positive numerical limit",
            evaluation=evaluation,
        )
    return evaluation


def _validate_eligible_artifact(artifact: TPMArtifact) -> None:
    if not isinstance(artifact, TPMArtifact):
        raise TypeError("conditional compilation source must load as a TPMArtifact")
    if artifact.schema_version != "v3":
        raise ValueError(
            "conditional compilation requires a current schema-v3 artifact with "
            "declared U-Bounds semantics; legacy artifacts remain compatibility-only"
        )
    if artifact.execution_mode != "production":
        raise ValueError("conditional compilation requires a production fitted artifact")
    if artifact.backend_generation != CURRENT_SPFLOW_BACKEND_GENERATION:
        raise ValueError("conditional compilation requires the current-SPFlow backend")
    if artifact.backend_api_version != REQUIRED_SPFLOW_VERSION:
        raise ValueError(
            f"conditional compilation requires SPFlow {REQUIRED_SPFLOW_VERSION}"
        )
    if artifact.spn_payload_format != "spflow-model-sidecar" or not artifact.source_path:
        raise ValueError(
            "conditional compilation requires a persisted current-SPFlow sidecar"
        )
    for spec in artifact.feature_specs:
        domain = spec.mathematical_domain
        normalization = spec.normalization
        if domain is None or normalization is None:
            raise ValueError(
                f"feature {spec.feature_name!r} lacks declared U-Bounds semantics"
            )
        if domain.origin == "omitted":
            raise ValueError(
                f"feature {spec.feature_name!r} has omitted mathematical semantics"
            )
        if normalization.origin == "legacy-inferred":
            raise ValueError(
                f"feature {spec.feature_name!r} uses legacy-inferred normalization"
            )


def _validate_retained_features_and_domains(
    *,
    request: TPMConditionalCompilationRequest,
    feature_by_name: Mapping[str, object],
) -> tuple[TPMApproximationDomain, ...]:
    raw_domains = tuple(
        TPMApproximationDomain.from_dict(value)
        for value in request.approximation_domains
    )
    domain_by_name = {value.feature_name: value for value in raw_domains}
    continuous_names: list[str] = []
    for feature_name in request.retained_decisions:
        spec = feature_by_name[feature_name]
        domain = spec.mathematical_domain
        normalization = spec.normalization
        if domain is None or normalization is None:
            raise ValueError(
                f"retained decision {feature_name!r} lacks declared semantics"
            )
        if not spec.modifiable or domain.purpose != "decision-domain":
            raise ValueError(
                f"retained feature {feature_name!r} is not a declared decision"
            )
        if spec.feature_type == "continuous":
            continuous_names.append(feature_name)
            if (
                domain.origin != "caller-declared"
                or domain.shape != "finite"
                or domain.lower is None
                or domain.upper is None
            ):
                raise ValueError(
                    f"retained continuous decision {feature_name!r} requires a finite "
                    "caller-declared decision domain"
                )
            approximation = domain_by_name.get(feature_name)
            if approximation is None:
                raise ValueError(
                    f"missing explicit approximation domain for {feature_name!r}"
                )
            if approximation.lower < domain.lower or approximation.upper > domain.upper:
                raise ValueError(
                    f"approximation domain for {feature_name!r} lies outside its "
                    "declared decision domain"
                )
        elif spec.feature_type in {"binary", "categorical"}:
            if feature_name in domain_by_name:
                raise ValueError(
                    f"discrete decision {feature_name!r} must not have an approximation domain"
                )
            if not domain.ordering:
                raise ValueError(
                    f"discrete decision {feature_name!r} requires complete declared ordering"
                )
        else:
            raise ValueError(
                f"retained feature {feature_name!r} has unsupported type {spec.feature_type!r}"
            )
    if set(domain_by_name) != set(continuous_names):
        raise ValueError(
            "approximation domains must exactly cover retained continuous decisions"
        )
    return tuple(domain_by_name[name] for name in continuous_names)


def _validate_current_payload(
    payload: Mapping[str, object],
    *,
    artifact: TPMArtifact,
) -> None:
    expected = {
        "payload_kind": "current-spflow-model-sidecar",
        "backend_generation": CURRENT_SPFLOW_BACKEND_GENERATION,
        "backend_api_version": artifact.backend_api_version,
        "query_strategy": "spflow",
    }
    for name, expected_value in expected.items():
        if payload.get(name) != expected_value:
            raise RuntimeError(
                f"current-SPFlow sidecar {name} must be {expected_value!r}"
            )


def _validate_compiled_origin(
    compiled: Mapping[str, object],
    *,
    artifact: TPMArtifact,
) -> None:
    if compiled.get("schema_version") != "v2":
        raise ValueError("conditional pair requires compiled-v2 declared-domain output")
    fitted = compiled.get("fitted_artifact")
    if not isinstance(fitted, Mapping):
        raise ValueError("compiled output is missing fitted-artifact provenance")
    expected = {
        "artifact_id": artifact.artifact_id,
        "schema_version": artifact.schema_version,
        "payload_hash": artifact.payload_hash,
    }
    if dict(fitted) != expected:
        raise ValueError("compiled output fitted-artifact provenance is mismatched")


def _resolve_encoding_policy(
    requested: TPMConditionalEncodingPolicy,
    *,
    compiled: Mapping[str, object],
) -> TPMConditionalEncodingPolicy:
    leaf_configuration = dict(requested.leaf_configuration)
    compiled_epsilon = float(compiled.get("mio_epsilon", math.nan))
    if compiled_epsilon != float(leaf_configuration["mio_epsilon"]):
        raise ValueError("compiled leaf mio_epsilon differs from the request")
    leaf_configuration["compiled_breakpoint_policy"] = dict(
        compiled.get("breakpoint_policy", {})
    )
    leaf_configuration["discrete_probability_floor"] = float(
        leaf_configuration.get(
            "discrete_probability_floor", _DISCRETE_PROBABILITY_FLOOR
        )
    )
    sum_arities = [
        len(node.get("children", ()))
        for node in compiled.get("nodes", ())
        if isinstance(node, Mapping) and node.get("type") == "sum"
    ]
    maximum_sum_arity = max(sum_arities, default=1)
    sum_configuration = dict(requested.sum_configuration)
    sum_configuration["maximum_sum_arity"] = maximum_sum_arity
    if requested.mode == "piecewise":
        log_x = tuple(float(value) for value in sum_configuration["log_x_points"])
        exp_x = tuple(float(value) for value in sum_configuration["exp_x_points"])
        if log_x[0] > 1.0 or log_x[-1] < float(maximum_sum_arity):
            raise ValueError(
                "piecewise logarithm curve does not cover the resolved Sum arity"
            )
        if exp_x[-1] != 0.0:
            raise ValueError("piecewise exponential curve must end exactly at zero")
        if float(sum_configuration["exp_domain_floor"]) != exp_x[0]:
            raise ValueError(
                "piecewise exp_domain_floor must match the first exponential point"
            )
    return TPMConditionalEncodingPolicy(
        mode=requested.mode,
        approximation_label=requested.approximation_label,
        certification_label=requested.certification_label,
        leaf_configuration=leaf_configuration,
        sum_configuration=sum_configuration,
    )


def _build_feature_validity(
    retained_decisions: Sequence[str],
    *,
    feature_by_name: Mapping[str, object],
    compiled: Mapping[str, object],
) -> tuple[TPMConditionalFeatureValidity, ...]:
    compiled_validity = {
        record.feature_name: record
        for record in (
            TPMCompiledValidityRecord.from_dict(value)
            for value in compiled.get("compiled_validity", ())
        )
    }
    result: list[TPMConditionalFeatureValidity] = []
    for feature_name in retained_decisions:
        spec = feature_by_name[feature_name]
        approximation: Mapping[str, object] | None = None
        if spec.feature_type == "continuous":
            if feature_name not in compiled_validity:
                raise ValueError(
                    f"compiled output is missing validity for {feature_name!r}"
                )
            approximation = compiled_validity[feature_name].to_dict()
        result.append(
            TPMConditionalFeatureValidity(
                feature_name=feature_name,
                feature_index=tuple(feature_by_name).index(feature_name),
                feature_type=spec.feature_type,
                declared_domain=spec.mathematical_domain.to_dict(),
                normalization=spec.normalization.to_dict(),
                approximation_domain=approximation,
            )
        )
    return tuple(result)


def _circuit_from_conditioned_payload(
    payload: Mapping[str, object],
) -> TPMConditionalCircuit:
    nodes = payload.get("nodes")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise TypeError("conditioned circuit nodes must be a sequence")
    metadata = {
        **dict(payload.get("conditioning", {})),
        "source_model": dict(payload.get("source_model", {})),
    }
    return TPMConditionalCircuit(
        root_id=int(payload["root_id"]),
        nodes=tuple(TPMConditionalCircuitNode.from_dict(node) for node in nodes),
        metadata=metadata,
    )


def _portable_manifest_reference(
    requested_source: str,
    *,
    artifact: TPMArtifact,
) -> str:
    requested_path = Path(requested_source)
    if not requested_path.is_absolute():
        return requested_path.as_posix()
    try:
        return requested_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return Path(artifact.source_path).name


def _resolve_assignment_coordinates(
    pair: TPMConditionalPair,
    *,
    assignments: Mapping[str, object],
    assignment_mode: str,
) -> dict[str, float]:
    coordinates: dict[str, float] = {}
    for validity in pair.validity:
        feature_name = validity.feature_name
        supplied = assignments[feature_name]
        domain = TPMFeatureDomain.from_dict(validity.declared_domain)
        normalization = TPMNormalizationSpec.from_dict(validity.normalization)
        if assignment_mode == "declared-domain":
            if validity.feature_type == "continuous":
                approximation = validity.approximation_domain
                physical_interval = tuple(approximation["physical_interval"])
                physical = _finite_float(
                    supplied, field_name=f"{feature_name} physical assignment"
                )
                if not physical_interval[0] <= physical <= physical_interval[1]:
                    raise ValueError(
                        f"{feature_name} assignment is outside its closed approximation domain"
                    )
            domain.validate_value(supplied)
            coordinate = float(normalization.normalize_value(supplied))
        else:
            coordinate = _finite_float(
                supplied, field_name=f"{feature_name} model-coordinate assignment"
            )
            if validity.feature_type == "continuous":
                approximation = validity.approximation_domain
                model_interval = tuple(approximation["model_interval"])
                if not model_interval[0] <= coordinate <= model_interval[1]:
                    raise ValueError(
                        f"{feature_name} assignment is outside its closed approximation domain"
                    )
            else:
                physical = normalization.denormalize_value(coordinate)
                domain.validate_value(physical)
        coordinates[feature_name] = coordinate
    return coordinates


def _evaluate_circuit(
    circuit: TPMConditionalCircuit,
    *,
    coordinates: Mapping[str, float],
    encoding: TPMConditionalEncodingPolicy,
) -> float:
    nodes = {node.node_id: node for node in circuit.nodes}
    cache: dict[int, float] = {}
    active: set[int] = set()
    probability_floor = float(
        encoding.leaf_configuration["discrete_probability_floor"]
    )

    def evaluate(node_id: int) -> float:
        if node_id in cache:
            return cache[node_id]
        if node_id in active:
            raise ValueError("conditional circuit must be acyclic")
        active.add(node_id)
        node = nodes[node_id]
        if node.node_type == "log_one":
            value = 0.0
        elif node.node_type == "leaf_piecewise":
            if node.feature_name not in coordinates:
                raise ValueError(
                    f"conditional circuit has unresolved feature {node.feature_name!r}"
                )
            value = _strict_linear_interpolate(
                coordinates[node.feature_name],
                x_values=node.parameters["breakpoints"],
                y_values=node.parameters["log_values"],
                field_name=f"leaf {node.node_id}",
            )
        elif node.node_type in {"leaf_binary", "leaf_categorical"}:
            densities = tuple(float(value) for value in node.parameters["densities"])
            if "fixed_value" in node.parameters:
                index = int(node.parameters["fixed_value"])
            else:
                if node.feature_name not in coordinates:
                    raise ValueError(
                        f"conditional circuit has unresolved feature {node.feature_name!r}"
                    )
                raw_index = coordinates[node.feature_name]
                index = int(raw_index)
                if raw_index != float(index) or not 0 <= index < len(densities):
                    raise ValueError(
                        f"conditional discrete coordinate for {node.feature_name!r} is invalid"
                    )
            value = math.log(max(densities[index], probability_floor))
        elif node.node_type == "product":
            value = math.fsum(evaluate(child_id) for child_id in node.children)
        elif node.node_type == "sum":
            weights = tuple(float(value) for value in node.parameters["weights"])
            terms = tuple(
                evaluate(child_id) + math.log(weight)
                for child_id, weight in zip(node.children, weights, strict=True)
            )
            maximum = max(terms)
            if encoding.mode == "max":
                value = maximum
            else:
                sum_configuration = encoding.sum_configuration
                exp_values = tuple(
                    _strict_linear_interpolate(
                        term - maximum,
                        x_values=sum_configuration["exp_x_points"],
                        y_values=sum_configuration["exp_y_points"],
                        field_name=f"PWL exponential at Sum {node.node_id}",
                    )
                    for term in terms
                )
                total = math.fsum(exp_values)
                logarithm = _strict_linear_interpolate(
                    total,
                    x_values=sum_configuration["log_x_points"],
                    y_values=sum_configuration["log_y_points"],
                    field_name=f"PWL logarithm at Sum {node.node_id}",
                )
                value = maximum + logarithm
        else:  # pragma: no cover - record validation owns this invariant
            raise ValueError(f"unsupported conditional node {node.node_type!r}")
        active.remove(node_id)
        if not math.isfinite(value):
            raise ValueError(
                f"conditional circuit node {node.node_id} produced a nonfinite value"
            )
        cache[node_id] = value
        return value

    return evaluate(circuit.root_id)


def _strict_linear_interpolate(
    value: object,
    *,
    x_values: Sequence[object],
    y_values: Sequence[object],
    field_name: str,
) -> float:
    point = _finite_float(value, field_name=field_name)
    x_points = tuple(
        _finite_float(item, field_name=f"{field_name} x point") for item in x_values
    )
    y_points = tuple(
        _finite_float(item, field_name=f"{field_name} y point") for item in y_values
    )
    if len(x_points) < 2 or len(x_points) != len(y_points):
        raise ValueError(f"{field_name} interpolation points must align")
    if point < x_points[0] or point > x_points[-1]:
        raise ValueError(
            f"{field_name} value {point} is outside [{x_points[0]}, {x_points[-1]}]"
        )
    if point == x_points[-1]:
        return y_points[-1]
    for left_x, right_x, left_y, right_y in zip(
        x_points,
        x_points[1:],
        y_points,
        y_points[1:],
        strict=True,
    ):
        if left_x <= point <= right_x:
            ratio = (point - left_x) / (right_x - left_x)
            return left_y + ratio * (right_y - left_y)
    raise ValueError(f"{field_name} interpolation value is outside its domain")


def _finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


__all__ = [
    "TPMConditionalEvaluationError",
    "compile_conditional_mio_pair",
    "evaluate_conditional_mio_pair",
]
