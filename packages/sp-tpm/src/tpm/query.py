"""Import-light TPM query requests and deterministic artifact-backed evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from typing import Any

from .artifact import TPMArtifact, load_tpm_artifact
from .conditional import TPMConditionalPair, TPMNativeConditionalEvaluation
from .features import (
    TPMFeatureSpec,
    validate_spflow_feature_assignments,
)
from .spflow_backend import load_spflow_payload, require_spflow_backend
from .piecewise import (
    DEFAULT_QUERY_NUMERIC_TOLERANCE,
    resolve_query_numeric_tolerance,
)


def _is_non_boolean_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class TPMQueryRequest:
    """Persisted query inputs for conditional TPM evaluation."""

    decision_assignments: Mapping[str, object] = field(default_factory=dict)
    marginalized_features: tuple[str, ...] = field(default_factory=tuple)
    output_mode: str = "conditional_probability"
    target_name: str = ""
    numeric_tolerance: float | None = None
    target_threshold: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.decision_assignments, Mapping):
            raise TypeError("decision_assignments must be a mapping")
        normalized_assignments = {
            str(feature_name): value
            for feature_name, value in self.decision_assignments.items()
        }
        if any(not feature_name for feature_name in normalized_assignments):
            raise ValueError("decision_assignments must not contain empty feature names")
        object.__setattr__(self, "decision_assignments", normalized_assignments)

        marginalized_features = tuple(
            str(feature_name) for feature_name in self.marginalized_features
        )
        if any(not feature_name for feature_name in marginalized_features):
            raise ValueError("marginalized_features must not contain empty feature names")
        if len(set(marginalized_features)) != len(marginalized_features):
            raise ValueError("marginalized_features must not contain duplicates")
        object.__setattr__(self, "marginalized_features", marginalized_features)

        output_mode = str(self.output_mode)
        if not output_mode:
            raise ValueError("output_mode must be non-empty")
        object.__setattr__(self, "output_mode", output_mode)

        target_name = str(self.target_name)
        object.__setattr__(self, "target_name", target_name)

        if self.numeric_tolerance is not None:
            numeric_tolerance = float(self.numeric_tolerance)
            if numeric_tolerance <= 0.0:
                raise ValueError("numeric_tolerance must be positive when provided")
            object.__setattr__(self, "numeric_tolerance", numeric_tolerance)

        if self.target_threshold is not None:
            object.__setattr__(self, "target_threshold", float(self.target_threshold))


@dataclass(frozen=True, slots=True)
class _QueryContext:
    feature_by_name: Mapping[str, TPMFeatureSpec]
    supported_output_modes: tuple[str, ...]
    required_decision_features: tuple[str, ...]
    canonical_target_name: str
    event_target_name: str
    target_threshold: float
    numeric_tolerance: float


def query_tpm_artifact(
    artifact: TPMArtifact | str | Path | Mapping[str, Any],
    request: TPMQueryRequest,
) -> dict[str, object]:
    """Evaluate one conditional TPM query from a persisted artifact contract."""

    resolved_artifact = _load_artifact(artifact)
    context = _build_query_context(resolved_artifact, request)
    result = _evaluate_current_spflow_query(resolved_artifact, request, context)
    if result is None:
        raise RuntimeError(
            "production TPM queries require a valid current-SPFlow model payload"
        )

    response = {
        "artifact_id": resolved_artifact.artifact_id,
        "dataset_reference": resolved_artifact.dataset_reference,
        "target_name": context.canonical_target_name,
        "output_mode": request.output_mode,
        "target_threshold": context.target_threshold,
        "decision_assignments": dict(request.decision_assignments),
        "marginalized_features": tuple(request.marginalized_features),
        "matched_row_count": result["matched_row_count"],
        "total_row_count": result["total_row_count"],
        "source": result["source"],
        "value": float(result["value"]),
    }
    if "resolved_target_name" in result:
        response["resolved_target_name"] = str(result["resolved_target_name"])
    response[request.output_mode] = response["value"]
    return response


def evaluate_native_conditional_pair(
    artifact: TPMArtifact | str | Path | Mapping[str, Any],
    pair: TPMConditionalPair,
    *,
    declared_domain_assignments: Mapping[str, object],
) -> TPMNativeConditionalEvaluation:
    """Query raw native numerator and denominator logs for one explicit event."""

    if not isinstance(pair, TPMConditionalPair):
        raise TypeError("pair must be a TPMConditionalPair")
    resolved_artifact = _load_artifact(artifact)
    _validate_native_pair_source(resolved_artifact, pair=pair)
    require_spflow_backend()
    if not isinstance(declared_domain_assignments, Mapping):
        raise TypeError("declared_domain_assignments must be a mapping")
    supplied_names = {str(name) for name in declared_domain_assignments}
    expected_names = set(pair.retained_decisions)
    missing = sorted(expected_names - supplied_names)
    extra = sorted(supplied_names - expected_names)
    if missing or extra:
        raise ValueError(
            "native conditional assignments must exactly cover retained decisions; "
            f"missing={missing!r}, extra={extra!r}"
        )
    feature_specs = resolved_artifact.feature_specs
    feature_by_name = {spec.feature_name: spec for spec in feature_specs}
    feature_indices = {
        spec.feature_name: index for index, spec in enumerate(feature_specs)
    }
    for feature_name in pair.retained_decisions:
        feature_by_name[feature_name].validate_value(
            declared_domain_assignments[feature_name]
        )
    runtime_payload = load_spflow_payload(resolved_artifact)
    if runtime_payload is None:
        raise RuntimeError(
            "native conditional evaluation requires a current-SPFlow model sidecar"
        )
    if (
        runtime_payload.get("payload_kind") != "current-spflow-model-sidecar"
        or runtime_payload.get("backend_generation") != "current-spflow"
        or runtime_payload.get("backend_api_version")
        != resolved_artifact.backend_api_version
        or runtime_payload.get("query_strategy") != "spflow"
    ):
        raise RuntimeError(
            "native conditional evaluation requires the matching current-SPFlow payload"
        )
    model = runtime_payload.get("model")
    if model is None:
        raise RuntimeError("current-SPFlow payload does not contain a fitted model")

    import torch

    evidence = torch.full(
        (1, len(feature_specs)),
        torch.nan,
        dtype=torch.float64,
        device="cpu",
    )
    ordered_assignments: dict[str, object] = {}
    for feature_name in pair.retained_decisions:
        value = declared_domain_assignments[feature_name]
        ordered_assignments[feature_name] = value
        evidence[0, feature_indices[feature_name]] = feature_by_name[
            feature_name
        ].normalize_value(value)

    denominator_log = reduce_spflow_log_likelihood(model.log_likelihood(evidence))
    numerator_evidence = evidence.clone()
    event_spec = feature_by_name[pair.event.feature_name]
    numerator_evidence[0, feature_indices[pair.event.feature_name]] = (
        event_spec.normalize_value(pair.event.declared_value)
    )
    numerator_log = reduce_spflow_log_likelihood(
        model.log_likelihood(numerator_evidence)
    )
    conditional_log_risk = numerator_log - denominator_log
    if not math.isfinite(conditional_log_risk):
        raise ValueError("native conditional log-risk must be finite")
    try:
        probability = math.exp(conditional_log_risk)
    except OverflowError as exc:
        raise ValueError("native conditional probability must be finite") from exc
    if not math.isfinite(probability):
        raise ValueError("native conditional probability must be finite")
    return TPMNativeConditionalEvaluation(
        pair_id=pair.pair_id,
        artifact_id=resolved_artifact.artifact_id,
        assignments=ordered_assignments,
        numerator_log=numerator_log,
        denominator_log=denominator_log,
        conditional_log_risk=conditional_log_risk,
        conditional_probability=probability,
        backend_generation=resolved_artifact.backend_generation,
        backend_api_version=resolved_artifact.backend_api_version,
    )


__all__ = [
    "DEFAULT_QUERY_NUMERIC_TOLERANCE",
    "TPMQueryRequest",
    "evaluate_native_conditional_pair",
    "marginalize_spflow_model",
    "query_tpm_artifact",
    "reduce_spflow_log_likelihood",
]


def _load_artifact(artifact: TPMArtifact | str | Path | Mapping[str, Any]) -> TPMArtifact:
    if isinstance(artifact, TPMArtifact):
        return artifact
    return load_tpm_artifact(artifact)


def _validate_native_pair_source(
    artifact: TPMArtifact,
    *,
    pair: TPMConditionalPair,
) -> None:
    expected = {
        "artifact_id": artifact.artifact_id,
        "artifact_schema_version": artifact.schema_version,
        "sidecar_sha256": artifact.payload_hash,
        "backend_generation": artifact.backend_generation,
        "backend_api_version": artifact.backend_api_version,
    }
    actual = {
        "artifact_id": pair.source.artifact_id,
        "artifact_schema_version": pair.source.artifact_schema_version,
        "sidecar_sha256": pair.source.sidecar_sha256,
        "backend_generation": pair.source.backend_generation,
        "backend_api_version": pair.source.backend_api_version,
    }
    if actual != expected:
        raise ValueError(
            "conditional pair source provenance does not match the native artifact"
        )
    persisted_schema = tuple(
        spec.to_dict(schema_version="v3") for spec in artifact.feature_specs
    )
    pair_schema = tuple(pair.to_dict()["feature_schema"])
    if pair_schema != persisted_schema:
        raise ValueError(
            "conditional pair feature schema does not match the native artifact"
        )
    event_name = str(artifact.target_definition.get("event_target_name", ""))
    if pair.event.feature_name != event_name:
        raise ValueError("conditional pair event does not match the native artifact")


def _build_query_context(
    artifact: TPMArtifact,
    request: TPMQueryRequest,
) -> _QueryContext:
    feature_by_name = {feature.feature_name: feature for feature in artifact.feature_specs}
    canonical_target_name = str(artifact.target_definition.get("target_name", ""))
    event_target_name = str(
        artifact.target_definition.get("event_target_name", canonical_target_name)
    )
    resolved_request_target_name = request.target_name or canonical_target_name
    if resolved_request_target_name not in {canonical_target_name, event_target_name}:
        raise ValueError(
            f"unsupported target request {resolved_request_target_name!r}; expected one of "
            f"{(canonical_target_name, event_target_name)!r}"
        )

    supported_output_modes = tuple(
        str(mode)
        for mode in artifact.query_configuration.get("supported_output_modes", ())
    )
    if request.output_mode not in supported_output_modes:
        raise ValueError(
            f"unsupported output_mode {request.output_mode!r}; "
            f"expected one of {supported_output_modes!r}"
        )

    assignment_names = set(request.decision_assignments)
    marginalized_names = set(request.marginalized_features)
    overlap = sorted(assignment_names & marginalized_names)
    if overlap:
        raise ValueError(
            "features cannot be both assigned and marginalized: " + ", ".join(overlap)
        )

    for target_name in (canonical_target_name, event_target_name):
        if target_name in assignment_names:
            raise ValueError(
                f"target feature {target_name!r} cannot appear in decision_assignments"
            )
        if target_name in marginalized_names:
            raise ValueError(f"target feature {target_name!r} cannot be marginalized")

    required_decision_features = tuple(
        str(feature_name)
        for feature_name in artifact.query_configuration.get(
            "required_decision_features",
            (),
        )
    )
    _validate_native_assignments(
        artifact.feature_specs,
        request.decision_assignments,
        required_decision_features=tuple(
            feature_name
            for feature_name in required_decision_features
            if feature_name not in marginalized_names
        ),
    )
    for feature_name in request.decision_assignments:
        spec = feature_by_name[feature_name]
        if not spec.modifiable:
            raise ValueError(
                "decision_assignments must reference modifiable features, found "
                f"{feature_name!r}"
            )

    for feature_name in request.marginalized_features:
        if feature_name not in feature_by_name:
            raise ValueError(f"unknown marginalized feature {feature_name!r}")

    target_threshold = float(
        request.target_threshold
        if request.target_threshold is not None
        else artifact.target_definition.get("threshold_default", 0.0)
    )
    numeric_tolerance = float(
        request.numeric_tolerance
        if request.numeric_tolerance is not None
        else resolve_query_numeric_tolerance(
            artifact.approximation_metadata,
            default=DEFAULT_QUERY_NUMERIC_TOLERANCE,
        )
    )

    return _QueryContext(
        feature_by_name=feature_by_name,
        supported_output_modes=supported_output_modes,
        required_decision_features=required_decision_features,
        canonical_target_name=canonical_target_name,
        event_target_name=event_target_name,
        target_threshold=target_threshold,
        numeric_tolerance=numeric_tolerance,
    )


def _validate_native_assignments(
    feature_schema: tuple[TPMFeatureSpec, ...],
    assignments: Mapping[str, object],
    *,
    required_decision_features: tuple[str, ...],
) -> None:
    """Validate physical query inputs through persisted semantic records."""

    validate_spflow_feature_assignments(
        feature_schema,
        assignments,
        required_decision_features=required_decision_features,
    )


def reduce_spflow_log_likelihood(value: object) -> float:
    """Reduce one scalar-root SPFlow likelihood tensor to a finite float."""

    import torch

    if not isinstance(value, torch.Tensor):
        raise TypeError("SPFlow log_likelihood output must be a Torch tensor")
    if value.numel() != 1:
        raise ValueError(
            "SPFlow log_likelihood reduction requires one batch, channel, and "
            f"repetition value; found shape {tuple(value.shape)!r}"
        )
    scalar = value.detach().cpu().to(dtype=torch.float64).reshape(-1)[0]
    if not bool(torch.isfinite(scalar)):
        raise ValueError("SPFlow log_likelihood output must be finite")
    return float(scalar.item())


def marginalize_spflow_model(
    model: object,
    feature_indices: tuple[int, ...] | list[int],
) -> object:
    """Structurally remove the named feature indices from a current model."""

    normalized_indices = tuple(int(index) for index in feature_indices)
    if len(set(normalized_indices)) != len(normalized_indices):
        raise ValueError("feature_indices must not contain duplicates")
    if any(index < 0 for index in normalized_indices):
        raise ValueError("feature_indices must be non-negative")
    scalar_result = _marginalize_scalar_dag(model, normalized_indices)
    if scalar_result is not NotImplemented:
        return scalar_result
    marginalize = getattr(model, "marginalize", None)
    if not callable(marginalize):
        raise TypeError("current SPFlow model must provide marginalize()")
    return marginalize(list(normalized_indices))


def _marginalize_scalar_dag(model, feature_indices):
    """Preserve scalar Sum/Product DAG sharing during exact marginalization.

    SPFlow 1.1's module marginalize methods recursively copy each incoming path.
    Tensorized exports can share a subgraph across hundreds of parents. Keep a
    per-node transformation cache instead. Other supported vectorized layouts
    continue through their native marginalizer.
    """
    import copy
    import torch
    from spflow.modules.leaves import Normal, Bernoulli, Categorical
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum
    from spflow.modules.ops.cat import Cat
    leaves = (Normal, Bernoulli, Categorical)
    if type(model) not in (*leaves, Product, Sum):
        return NotImplemented
    for node in model.modules():
        if type(node) in (*leaves, Product, Sum):
            shape = node.out_shape
            if (shape.features, shape.channels, shape.repetitions) != (1,1,1):
                return NotImplemented
        elif type(node) not in (Cat, torch.nn.ModuleList):
            return NotImplemented
    excluded = set(feature_indices)
    memo, clone_memo = {}, {}

    def children(node):
        inputs = node.inputs
        if type(inputs) is Cat:
            return list(inputs.inputs)
        if isinstance(inputs,(list,tuple,torch.nn.ModuleList)):
            return list(inputs)
        return [inputs]

    def visit(node):
        key = id(node)
        if key in memo:
            return memo[key]
        scope = set(node.scope.query)
        if scope <= excluded:
            result = None
        elif type(node) in leaves:
            result = copy.deepcopy(node,clone_memo)
        elif type(node) is Product:
            kept = [value for child in children(node) if (value := visit(child)) is not None]
            result = kept[0] if len(kept) == 1 else Product(kept)
        elif type(node) is Sum:
            kept = [visit(child) for child in children(node)]
            if any(value is None for value in kept):
                raise ValueError('a smooth scalar Sum cannot be partly marginalized to identity')
            weights = node.weights.detach().reshape(-1).clone()
            if len(kept) != len(weights):
                raise ValueError('scalar Sum children differ from its weight arity')
            result = Sum(kept, weights=weights)
            with torch.no_grad():
                result.logits.copy_(node.logits.detach())
        else:
            raise TypeError('unsupported scalar marginalization node')
        memo[key] = result
        return result

    return visit(model)


def _evaluate_current_spflow_query(
    artifact: TPMArtifact,
    request: TPMQueryRequest,
    context: _QueryContext,
) -> dict[str, object] | None:
    import pickle

    try:
        runtime_payload = load_spflow_payload(artifact)
    except (OSError, TypeError, ValueError, EOFError, AttributeError, pickle.PickleError) as exc:
        raise RuntimeError(
            "production TPM queries require a valid current-SPFlow model payload"
        ) from exc
    if runtime_payload is None:
        return None
    model = runtime_payload.get("model")
    if model is None:
        return None
    if str(runtime_payload.get("backend_generation", "")) != "current-spflow":
        raise RuntimeError("production query requires a current-SPFlow model payload")
    if str(runtime_payload.get("backend_api_version", "")) != artifact.backend_api_version:
        raise RuntimeError(
            "production query payload API version does not match the TPM artifact"
        )

    import torch

    feature_specs = artifact.feature_specs
    feature_indices = {
        spec.feature_name: index for index, spec in enumerate(feature_specs)
    }
    evidence = torch.full(
        (1, len(feature_specs)),
        torch.nan,
        dtype=torch.float64,
        device="cpu",
    )
    for feature_name, supplied_value in request.decision_assignments.items():
        spec = context.feature_by_name[feature_name]
        evidence[0, feature_indices[feature_name]] = spec.normalize_value(supplied_value)

    denominator_output = model.log_likelihood(evidence)
    denominator_log_likelihood = reduce_spflow_log_likelihood(denominator_output)
    if request.output_mode == "conditional_probability":
        numerator_evidence = evidence.clone()
        event_spec = context.feature_by_name[context.event_target_name]
        event_value = event_spec.ordering[-1]
        numerator_evidence[0, feature_indices[context.event_target_name]] = (
            event_spec.normalize_value(event_value)
        )
        numerator_output = model.log_likelihood(numerator_evidence)
        numerator_log_likelihood = reduce_spflow_log_likelihood(numerator_output)
        probability = math.exp(
            min(0.0, numerator_log_likelihood - denominator_log_likelihood)
        )
        value = min(1.0, max(0.0, probability))
    else:
        numerator_log_likelihood = None
        value = denominator_log_likelihood

    raw_rows = runtime_payload.get("raw_rows")
    total_row_count = int(
        runtime_payload.get(
            "training_row_count",
            len(raw_rows) if isinstance(raw_rows, tuple | list) else 0,
        )
    )
    result: dict[str, object] = {
        "matched_row_count": 0,
        "total_row_count": total_row_count,
        "source": "spflow_backend",
        "value": float(value),
        "resolved_target_name": context.event_target_name,
        "denominator_log_likelihood": denominator_log_likelihood,
    }
    if numerator_log_likelihood is not None:
        result["numerator_log_likelihood"] = numerator_log_likelihood
    return result
