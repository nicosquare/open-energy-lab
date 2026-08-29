"""Lazy compilation and direct execution of conditional TPM circuit pairs."""

from __future__ import annotations

import math
import keyword
from collections.abc import Mapping, Sequence
from pathlib import Path

from .artifact import TPMArtifact, load_tpm_artifact
from .conditional import (
    TPMBinaryDecisionLink,
    TPMBinaryDecisionMapping,
    TPMCategoricalDecisionLink,
    TPMCategoricalDecisionMapping,
    TPMConditionalAttachment,
    TPMConditionalAttachmentDiagnostics,
    TPMConditionalCircuit,
    TPMConditionalCircuitNode,
    TPMConditionalCompilationRequest,
    TPMConditionalEncodingPolicy,
    TPMConditionalEvaluation,
    TPMConditionalEvent,
    TPMConditionalDecisionLink,
    TPMConditionalFeatureValidity,
    TPMConditionalPair,
    TPMConditionalSourceReference,
    TPMCompilerFidelityEvidence,
    TPMContinuousDecisionMapping,
    TPMEmbeddingParityEvidence,
    TPMNativeConditionalEvaluation,
)
from .piecewise import (
    CONDITIONAL_GUARD_DOMAIN_FLOOR,
    CONDITIONAL_GUARD_TRANSITION_WIDTH,
    DEFAULT_EXP_PROBABILITY_FLOOR,
    evaluate_guarded_exponential,
    guarded_exponential_points,
    resolve_guarded_exponential_spec,
)
from .domains import (
    TPMApproximationDomain,
    TPMCompiledValidityRecord,
    TPMFeatureDomain,
    TPMNormalizationSpec,
)
from .mio import (
    compile_spflow_model_to_mio,
    condition_compiled_spflow_mio,
    encode_conditioned_spflow_circuit,
    require_pyomo_backend,
)
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


class TPMConditionalDiagnosticsError(ValueError):
    """Raised when finite attached values violate conditional probability meaning."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: TPMConditionalAttachmentDiagnostics,
    ) -> None:
        self.diagnostics = diagnostics
        super().__init__(message)


def attach_conditional_mio_pair(
    pair: TPMConditionalPair,
    model: object,
    *,
    mappings: Sequence[
        TPMContinuousDecisionMapping
        | TPMBinaryDecisionMapping
        | TPMCategoricalDecisionMapping
    ],
    namespace: str,
) -> TPMConditionalAttachment:
    """Attach one unchanged pair to supported caller-owned Pyomo decisions."""

    if not isinstance(pair, TPMConditionalPair):
        raise TypeError("pair must be a TPMConditionalPair")
    (
        pair,
        validity_by_name,
        domain_by_name,
        normalization_by_name,
        approximation_by_name,
    ) = _validate_pair_for_attachment(pair)
    backend = require_pyomo_backend()
    normalized_namespace = _validate_attachment_namespace(
        model, namespace=namespace
    )
    if isinstance(mappings, Mapping) or isinstance(mappings, (str, bytes)):
        raise TypeError("mappings must be an ordered sequence of typed mappings")
    try:
        ordered_mappings = tuple(mappings)
    except TypeError as exc:
        raise TypeError(
            "mappings must be an ordered sequence of typed mappings"
        ) from exc
    feature_names: list[str] = []
    mapping_types = (
        TPMContinuousDecisionMapping,
        TPMBinaryDecisionMapping,
        TPMCategoricalDecisionMapping,
    )
    mapping_by_name: dict[
        str,
        TPMContinuousDecisionMapping
        | TPMBinaryDecisionMapping
        | TPMCategoricalDecisionMapping,
    ] = {}
    for mapping in ordered_mappings:
        if not isinstance(mapping, mapping_types):
            raise TypeError("attachment requires typed decision mapping records")
        feature_name = mapping.feature_name
        if feature_name in mapping_by_name:
            raise ValueError(f"duplicate decision mapping for {feature_name!r}")
        feature_names.append(feature_name)
        mapping_by_name[feature_name] = mapping
    expected = tuple(pair.retained_decisions)
    missing = [name for name in expected if name not in mapping_by_name]
    extra = [name for name in feature_names if name not in set(expected)]
    if missing or extra:
        raise ValueError(
            "decision mappings must exactly cover retained decisions; "
            f"missing={missing!r}, unknown extra={extra!r}"
        )
    continuous_variables: dict[str, tuple[object, ...]] = {}
    discrete_ordering: dict[str, tuple[object, ...]] = {}
    for feature_name in expected:
        validity = validity_by_name[feature_name]
        mapping = mapping_by_name[feature_name]
        if validity.feature_type == "continuous":
            if not isinstance(mapping, TPMContinuousDecisionMapping):
                raise TypeError(
                    f"retained continuous feature {feature_name!r} requires a "
                    "TPMContinuousDecisionMapping"
                )
            if validity.approximation_domain is None:
                raise ValueError(
                    f"continuous feature {feature_name!r} lacks approximation validity"
                )
            continuous_variables[feature_name] = _inspect_structural_affine_expression(
                backend,
                model,
                mapping.physical_expression,
                feature_name=feature_name,
            )
            continue
        domain = domain_by_name[feature_name]
        ordering = tuple(domain.ordering)
        if validity.feature_type == "binary":
            if not isinstance(mapping, TPMBinaryDecisionMapping):
                raise TypeError(
                    f"retained binary feature {feature_name!r} requires a "
                    "TPMBinaryDecisionMapping"
                )
            if len(ordering) != 2:
                raise ValueError(
                    f"binary feature {feature_name!r} lacks exact declared ordering"
                )
            _validate_scalar_binary_variable(
                model,
                mapping.caller_variable,
                feature_name=feature_name,
            )
            discrete_ordering[feature_name] = ordering
            continue
        if validity.feature_type == "categorical":
            if not isinstance(mapping, TPMCategoricalDecisionMapping):
                raise TypeError(
                    f"retained categorical feature {feature_name!r} requires a "
                    "TPMCategoricalDecisionMapping"
                )
            labels = tuple(value for value, _ in mapping.ordered_indicators)
            if labels != ordering:
                raise ValueError(
                    f"categorical mapping for {feature_name!r} must exactly follow "
                    f"declared ordering {ordering!r}"
                )
            for _, indicator in mapping.ordered_indicators:
                _validate_scalar_binary_variable(
                    model, indicator, feature_name=feature_name
                )
            discrete_ordering[feature_name] = ordering
            continue
        raise TypeError(
            f"retained feature {feature_name!r} has unsupported type "
            f"{validity.feature_type!r}"
        )

    block = backend.Block(concrete=True)
    continuous_names = tuple(
        name
        for name in expected
        if validity_by_name[name].feature_type == "continuous"
    )
    block.continuous_features = backend.Set(
        initialize=continuous_names, ordered=True
    )
    block.model_coordinate = backend.Var(
        block.continuous_features,
        domain=backend.Reals,
        bounds=lambda _block, name: tuple(
            approximation_by_name[name]["model_interval"]
        ),
    )
    physical_expression_by_name = {
        name: mapping_by_name[name].physical_expression
        for name in continuous_names
    }
    block.physical_validity_lower = backend.Constraint(
        block.continuous_features,
        rule=lambda _block, name: physical_expression_by_name[name]
        >= float(approximation_by_name[name]["physical_interval"][0]),
    )
    block.physical_validity_upper = backend.Constraint(
        block.continuous_features,
        rule=lambda _block, name: physical_expression_by_name[name]
        <= float(approximation_by_name[name]["physical_interval"][1]),
    )
    block.model_validity_lower = backend.Constraint(
        block.continuous_features,
        rule=lambda _block, name: block.model_coordinate[name]
        >= float(approximation_by_name[name]["model_interval"][0]),
    )
    block.model_validity_upper = backend.Constraint(
        block.continuous_features,
        rule=lambda _block, name: block.model_coordinate[name]
        <= float(approximation_by_name[name]["model_interval"][1]),
    )

    def coordinate_link_rule(_block, name):
        normalization = normalization_by_name[name]
        physical = physical_expression_by_name[name]
        if normalization.kind == "min-max":
            coordinate = (physical - normalization.lower) / (
                normalization.upper - normalization.lower
            )
        elif normalization.kind == "identity":
            coordinate = physical
        else:
            raise ValueError(
                f"continuous feature {name!r} uses unsupported normalization "
                f"{normalization.kind!r}"
            )
        return block.model_coordinate[name] == coordinate

    block.coordinate_link = backend.Constraint(
        block.continuous_features, rule=coordinate_link_rule
    )
    decision_variables = {
        name: {
            "kind": "continuous",
            "normalized_var": block.model_coordinate[name],
        }
        for name in continuous_names
    }
    categorical_names = tuple(
        name
        for name in expected
        if validity_by_name[name].feature_type == "categorical"
    )
    block.categorical_features = backend.Set(
        initialize=categorical_names, ordered=True
    )
    categorical_indicators = {
        name: tuple(
            indicator
            for _, indicator in mapping_by_name[name].ordered_indicators
        )
        for name in categorical_names
    }
    block.categorical_exactly_one = backend.Constraint(
        block.categorical_features,
        rule=lambda _block, name: sum(categorical_indicators[name]) == 1,
    )
    for name in expected:
        feature_type = validity_by_name[name].feature_type
        mapping = mapping_by_name[name]
        if feature_type == "binary":
            decision_variables[name] = {
                "kind": "binary",
                "normalized_var": mapping.caller_variable,
            }
        elif feature_type == "categorical":
            decision_variables[name] = {
                "kind": "categorical",
                "normalized_var": categorical_indicators[name],
            }
    block.numerator = backend.Block(concrete=True)
    numerator_encoding = encode_conditioned_spflow_circuit(
        backend,
        block.numerator,
        circuit=pair.numerator.to_dict(),
        decision_variables=decision_variables,
        encoding=pair.encoding.to_dict(),
        formulation=pair.attachment_formulation.numerator,
    )
    block.denominator = backend.Block(concrete=True)
    denominator_encoding = encode_conditioned_spflow_circuit(
        backend,
        block.denominator,
        circuit=pair.denominator.to_dict(),
        decision_variables=decision_variables,
        encoding=pair.encoding.to_dict(),
        formulation=pair.attachment_formulation.denominator,
    )
    numerator_root = numerator_encoding["root"]
    denominator_root = denominator_encoding["root"]
    block.conditional_log_risk = backend.Expression(
        expr=numerator_root - denominator_root
    )
    links: dict[
        str,
        TPMConditionalDecisionLink
        | TPMBinaryDecisionLink
        | TPMCategoricalDecisionLink,
    ] = {
        name: TPMConditionalDecisionLink(
            feature_name=name,
            physical_expression=physical_expression_by_name[name],
            caller_variables=continuous_variables[name],
            model_coordinate=block.model_coordinate[name],
            coordinate_link=block.coordinate_link[name],
            physical_lower=block.physical_validity_lower[name],
            physical_upper=block.physical_validity_upper[name],
            model_lower=block.model_validity_lower[name],
            model_upper=block.model_validity_upper[name],
            normalization=validity_by_name[name].normalization,
            approximation_domain=approximation_by_name[name],
        )
        for name in continuous_names
    }
    for name in expected:
        mapping = mapping_by_name[name]
        feature_type = validity_by_name[name].feature_type
        if feature_type == "binary":
            links[name] = TPMBinaryDecisionLink(
                feature_name=name,
                caller_variable=mapping.caller_variable,
                declared_ordering=discrete_ordering[name],
            )
        elif feature_type == "categorical":
            links[name] = TPMCategoricalDecisionLink(
                feature_name=name,
                ordered_indicators=mapping.ordered_indicators,
                declared_ordering=discrete_ordering[name],
                exactly_one=block.categorical_exactly_one[name],
            )
    links = {name: links[name] for name in expected}
    diagnostic_components = tuple(
        component.getname(fully_qualified=True)
        for component in block.component_objects(active=True, descend_into=True)
    )
    result = TPMConditionalAttachment(
        pair_id=pair.pair_id,
        namespace=normalized_namespace,
        retained_decisions=expected,
        block=block,
        numerator_root=numerator_root,
        denominator_root=denominator_root,
        conditional_log_risk=block.conditional_log_risk,
        decision_links=links,
        pair_metadata={
            "event": pair.event.to_dict(),
            "retained_decisions": list(expected),
            "validity": [value.to_dict() for value in pair.validity],
            "encoding": pair.encoding.to_dict(),
            "attachment_formulation": pair.attachment_formulation.to_dict(),
            "numerical_policy": pair.numerical_policy.to_dict(),
        },
        diagnostic_components=diagnostic_components,
    )
    _add_attachment_block_atomically(
        model,
        namespace=normalized_namespace,
        block=block,
    )
    return result


def _validate_pair_for_attachment(
    pair: TPMConditionalPair,
) -> tuple[
    TPMConditionalPair,
    dict[str, TPMConditionalFeatureValidity],
    dict[str, TPMFeatureDomain],
    dict[str, TPMNormalizationSpec],
    dict[str, Mapping[str, object]],
]:
    """Revalidate identity and U-Bounds meaning before touching a caller model."""

    try:
        validated = TPMConditionalPair.from_dict(pair.to_dict())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "conditional pair failed attachment identity/schema preflight"
        ) from exc
    validity_by_name = {
        value.feature_name: value for value in validated.validity
    }
    schema_by_name = {
        str(value["feature_name"]): value for value in validated.feature_schema
    }
    domains: dict[str, TPMFeatureDomain] = {}
    normalizations: dict[str, TPMNormalizationSpec] = {}
    approximations: dict[str, Mapping[str, object]] = {}
    for feature_name in validated.retained_decisions:
        validity = validity_by_name[feature_name]
        schema = schema_by_name[feature_name]
        if schema.get("feature_type") != validity.feature_type:
            raise ValueError(
                f"retained feature {feature_name!r} has inconsistent pair feature types"
            )
        try:
            domain = TPMFeatureDomain.from_dict(validity.declared_domain)
            normalization = TPMNormalizationSpec.from_dict(
                validity.normalization
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"retained feature {feature_name!r} has invalid U-Bounds semantics"
            ) from exc
        if (
            domain.feature_name != feature_name
            or normalization.feature_name != feature_name
            or domain.feature_kind != validity.feature_type
            or normalization.feature_kind != validity.feature_type
        ):
            raise ValueError(
                f"retained feature {feature_name!r} has mismatched domain or "
                "normalization identity"
            )
        if domain.purpose != "decision-domain" or domain.origin != "caller-declared":
            raise ValueError(
                f"retained feature {feature_name!r} requires a caller-declared "
                "decision domain"
            )
        if normalization.origin != "caller-declared":
            raise ValueError(
                f"retained feature {feature_name!r} requires caller-declared "
                "normalization"
            )
        domains[feature_name] = domain
        normalizations[feature_name] = normalization
        if validity.feature_type == "continuous":
            if (
                domain.shape != "finite"
                or domain.lower is None
                or domain.upper is None
                or domain.lower >= domain.upper
            ):
                raise ValueError(
                    f"continuous feature {feature_name!r} requires a nondegenerate "
                    "finite decision domain"
                )
            if normalization.kind != "min-max":
                raise ValueError(
                    f"finite continuous decision {feature_name!r} requires "
                    "caller-declared min-max normalization"
                )
            approximation = _validate_attachment_approximation(
                validity.approximation_domain,
                feature_name=feature_name,
                feature_index=validity.feature_index,
                domain=domain,
                normalization=normalization,
            )
            approximations[feature_name] = approximation
        else:
            if normalization.kind != "ordered-index":
                raise ValueError(
                    f"discrete feature {feature_name!r} requires ordered-index "
                    "normalization"
                )
            if tuple(normalization.ordering) != tuple(domain.ordering):
                raise ValueError(
                    f"discrete feature {feature_name!r} has inconsistent declared "
                    "and normalization ordering"
                )
    return validated, validity_by_name, domains, normalizations, approximations


def _validate_attachment_approximation(
    value: Mapping[str, object] | None,
    *,
    feature_name: str,
    feature_index: int,
    domain: TPMFeatureDomain,
    normalization: TPMNormalizationSpec,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(
            f"continuous feature {feature_name!r} lacks approximation validity"
        )
    if value.get("feature_name") != feature_name:
        raise ValueError(
            f"approximation validity for {feature_name!r} has a mismatched feature"
        )
    if "feature_index" in value and value["feature_index"] != feature_index:
        raise ValueError(
            f"approximation validity for {feature_name!r} has a mismatched index"
        )
    physical = _closed_interval(
        value.get("physical_interval"),
        field_name=f"{feature_name} physical approximation interval",
    )
    coordinate = _closed_interval(
        value.get("model_interval"),
        field_name=f"{feature_name} model approximation interval",
    )
    if physical[0] < domain.lower or physical[1] > domain.upper:
        raise ValueError(
            f"approximation interval for {feature_name!r} lies outside its "
            "declared decision domain"
        )
    expected_coordinate = (
        float(normalization.normalize_value(physical[0])),
        float(normalization.normalize_value(physical[1])),
    )
    if any(
        not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        for actual, expected in zip(
            coordinate, expected_coordinate, strict=True
        )
    ):
        raise ValueError(
            f"approximation validity for {feature_name!r} is inconsistent with "
            "its persisted normalization"
        )
    for name, interval in (
        ("physical_breakpoints", physical),
        ("model_breakpoints", coordinate),
    ):
        if name not in value:
            continue
        points = _strictly_increasing_finite_sequence(
            value[name], field_name=f"{feature_name} {name}"
        )
        if not (
            math.isclose(points[0], interval[0], rel_tol=1e-12, abs_tol=1e-12)
            and math.isclose(
                points[-1], interval[1], rel_tol=1e-12, abs_tol=1e-12
            )
        ):
            raise ValueError(
                f"{feature_name} {name} must span its recorded validity interval"
            )
    embedded_normalization = value.get("normalization")
    if embedded_normalization is not None:
        if not isinstance(embedded_normalization, Mapping):
            raise ValueError(
                f"approximation validity for {feature_name!r} embeds invalid "
                "normalization semantics"
            )
        if dict(embedded_normalization) != normalization.to_dict():
            raise ValueError(
                f"approximation validity for {feature_name!r} embeds different "
                "normalization semantics"
            )
    for field_name in ("source", "encoding"):
        if not isinstance(value.get(field_name), str) or not value[field_name]:
            raise ValueError(
                f"approximation validity for {feature_name!r} requires "
                f"nonempty {field_name}"
            )
    return value


def _closed_interval(value: object, *, field_name: str) -> tuple[float, float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 2
    ):
        raise ValueError(f"{field_name} must contain exactly two endpoints")
    lower = _finite_float(value[0], field_name=f"{field_name} lower")
    upper = _finite_float(value[1], field_name=f"{field_name} upper")
    if lower >= upper:
        raise ValueError(f"{field_name} must be strictly increasing")
    return lower, upper


def _strictly_increasing_finite_sequence(
    value: object,
    *,
    field_name: str,
) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field_name} must be a sequence")
    points = tuple(
        _finite_float(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )
    if len(points) < 2 or any(
        right <= left for left, right in zip(points, points[1:])
    ):
        raise ValueError(f"{field_name} must be strictly increasing")
    return points


def _add_attachment_block_atomically(
    model: object,
    *,
    namespace: str,
    block: object,
) -> None:
    try:
        model.add_component(namespace, block)
    except Exception as add_error:
        if model.component(namespace) is block:
            try:
                model.del_component(block)
            except Exception as rollback_error:  # pragma: no cover - defensive Pyomo failure
                raise RuntimeError(
                    f"conditional attachment {namespace!r} failed and its exact "
                    "rollback also failed"
                ) from rollback_error
            if model.component(namespace) is not None:  # pragma: no cover - Pyomo invariant
                raise RuntimeError(
                    f"conditional attachment {namespace!r} failed to roll back"
                ) from add_error
        raise
    if model.component(namespace) is not block:  # pragma: no cover - Pyomo invariant
        raise RuntimeError(
            f"conditional attachment {namespace!r} was not registered as requested"
        )


def inspect_conditional_mio_attachment(
    attachment: TPMConditionalAttachment,
    *,
    solver_metadata: Mapping[str, object],
) -> TPMConditionalAttachmentDiagnostics:
    """Read solved values and active violation magnitudes inside one attachment."""

    if not isinstance(attachment, TPMConditionalAttachment):
        raise TypeError("attachment must be a TPMConditionalAttachment")
    if not isinstance(solver_metadata, Mapping):
        raise TypeError("solver_metadata must be a mapping")
    backend = require_pyomo_backend()
    try:
        numerator = _finite_float(
            backend.value(attachment.numerator_root),
            field_name="attached numerator root",
        )
        denominator = _finite_float(
            backend.value(attachment.denominator_root),
            field_name="attached denominator root",
        )
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError("attachment roots must be evaluable and finite") from exc
    conditional_log_risk = numerator - denominator
    if not math.isfinite(conditional_log_risk):
        raise ValueError("attached conditional log-risk must be finite")
    try:
        probability = math.exp(conditional_log_risk)
    except OverflowError as exc:
        raise ValueError("attached conditional probability must be finite") from exc
    if not math.isfinite(probability):
        raise ValueError("attached conditional probability must be finite")

    residuals: dict[str, float] = {}
    for constraint in attachment.block.component_data_objects(
        backend.Constraint,
        active=True,
        descend_into=True,
    ):
        name = constraint.getname(fully_qualified=True)
        try:
            body = _finite_float(
                backend.value(constraint.body),
                field_name=f"constraint {name} body",
            )
            lower = (
                None
                if constraint.lower is None
                else _finite_float(
                    backend.value(constraint.lower),
                    field_name=f"constraint {name} lower bound",
                )
            )
            upper = (
                None
                if constraint.upper is None
                else _finite_float(
                    backend.value(constraint.upper),
                    field_name=f"constraint {name} upper bound",
                )
            )
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise ValueError(
                f"attachment constraint {name} must be evaluable and finite"
            ) from exc
        if constraint.equality:
            bound = lower if lower is not None else upper
            if bound is None:  # pragma: no cover - Pyomo equality invariant
                raise ValueError(f"attachment equality {name} has no finite bound")
            residual = abs(body - bound)
        else:
            residual = max(
                0.0,
                (lower - body) if lower is not None else 0.0,
                (body - upper) if upper is not None else 0.0,
            )
        if not math.isfinite(residual):
            raise ValueError(f"attachment constraint {name} residual must be finite")
        residuals[name] = residual

    numerical_policy = attachment.pair_metadata.get("numerical_policy")
    if not isinstance(numerical_policy, Mapping):
        raise ValueError("attachment lacks persisted numerical policy metadata")
    tolerances = numerical_policy.get("tolerances")
    if not isinstance(tolerances, Mapping):
        raise ValueError("attachment lacks persisted purpose-labelled tolerances")
    positive_limit = _finite_float(
        tolerances.get("positive_log_risk_limit"),
        field_name="positive_log_risk_limit",
    )
    if positive_limit <= 0.0:
        raise ValueError("positive_log_risk_limit must be positive")
    classification = (
        "positive-numerical-noise"
        if 0.0 < conditional_log_risk <= positive_limit
        else "valid"
    )
    diagnostics = TPMConditionalAttachmentDiagnostics(
        pair_id=attachment.pair_id,
        namespace=attachment.namespace,
        solver_metadata=solver_metadata,
        numerator_log=numerator,
        denominator_log=denominator,
        conditional_log_risk=conditional_log_risk,
        conditional_probability=probability,
        classification=classification,
        constraint_residuals=residuals,
        maximum_constraint_residual=max(residuals.values(), default=0.0),
    )
    if conditional_log_risk > positive_limit:
        raise TPMConditionalDiagnosticsError(
            "attached conditional log-risk exceeds its positive numerical limit",
            diagnostics=diagnostics,
        )
    return diagnostics


def build_embedding_parity_evidence(
    pair: TPMConditionalPair,
    *,
    case_results: Mapping[
        str, tuple[TPMConditionalEvaluation, TPMConditionalAttachmentDiagnostics]
    ],
    provenance: Mapping[str, object] | None = None,
) -> TPMEmbeddingParityEvidence:
    """Compare attached values with direct execution of the identical pair."""

    if not isinstance(pair, TPMConditionalPair):
        raise TypeError("pair must be a TPMConditionalPair")
    if not isinstance(case_results, Mapping) or not case_results:
        raise ValueError("embedding parity case_results must be a nonempty mapping")
    tolerances = pair.numerical_policy.tolerances
    parity_tolerance = float(tolerances["embedding_parity_absolute_tolerance"])
    residual_tolerance = float(
        tolerances["constraint_residual_absolute_tolerance"]
    )
    cases = []
    for raw_case_name, raw_result in case_results.items():
        case_name = str(raw_case_name)
        if not case_name:
            raise ValueError("embedding parity case names must be nonempty")
        if not isinstance(raw_result, Sequence) or isinstance(
            raw_result, (str, bytes)
        ) or len(raw_result) != 2:
            raise TypeError(
                "each embedding parity result must contain direct and attached values"
            )
        direct, attached = raw_result
        if not isinstance(direct, TPMConditionalEvaluation):
            raise TypeError("embedding parity direct result has the wrong type")
        if not isinstance(attached, TPMConditionalAttachmentDiagnostics):
            raise TypeError("embedding parity attached result has the wrong type")
        if direct.pair_id != pair.pair_id or attached.pair_id != pair.pair_id:
            raise ValueError("embedding parity result references a different pair")
        fields = (
            "numerator_log",
            "denominator_log",
            "conditional_log_risk",
            "conditional_probability",
        )
        deltas = {
            name: float(getattr(attached, name)) - float(getattr(direct, name))
            for name in fields
        }
        absolute_errors = {name: abs(value) for name, value in deltas.items()}
        solver = attached.solver_metadata
        accepted = (
            str(solver["status"]).casefold() == "ok"
            and str(solver["termination_condition"]).casefold() == "optimal"
            and all(
                absolute_errors[name] <= parity_tolerance
                for name in (
                    "numerator_log",
                    "denominator_log",
                    "conditional_log_risk",
                )
            )
            and attached.maximum_constraint_residual <= residual_tolerance
        )
        cases.append(
            {
                "case_name": case_name,
                "assignment_mode": direct.assignment_mode,
                "assignments": dict(direct.assignments),
                "direct": direct.to_dict(),
                "attached": attached.to_dict(),
                "deltas": deltas,
                "absolute_errors": absolute_errors,
                "accepted": accepted,
            }
        )
    return TPMEmbeddingParityEvidence(
        pair_id=pair.pair_id,
        encoding=pair.encoding.to_dict(),
        numerical_policy=pair.numerical_policy.to_dict(),
        cases=tuple(cases),
        metric_definitions={
            "delta_direction": "attached-minus-direct",
            "acceptance_gate": "absolute-1e-6",
            "constraint_residual": (
                "active-attachment-only-violation-magnitude"
            ),
            "probability_delta": "diagnostic-not-gated",
        },
        provenance=provenance or {},
    )


def build_compiler_fidelity_evidence(
    pair: TPMConditionalPair,
    *,
    case_results: Mapping[
        str, tuple[TPMConditionalEvaluation, TPMNativeConditionalEvaluation]
    ],
    provenance: Mapping[str, object] | None = None,
) -> TPMCompilerFidelityEvidence:
    """Retain signed compiled-minus-native differences without an accuracy gate."""

    if not isinstance(pair, TPMConditionalPair):
        raise TypeError("pair must be a TPMConditionalPair")
    if not isinstance(case_results, Mapping) or not case_results:
        raise ValueError("compiler fidelity case_results must be a nonempty mapping")
    cases = []
    for raw_case_name, raw_result in case_results.items():
        case_name = str(raw_case_name)
        if not case_name:
            raise ValueError("compiler fidelity case names must be nonempty")
        if not isinstance(raw_result, Sequence) or isinstance(
            raw_result, (str, bytes)
        ) or len(raw_result) != 2:
            raise TypeError(
                "each compiler fidelity result must contain compiled and native values"
            )
        compiled, native = raw_result
        if not isinstance(compiled, TPMConditionalEvaluation):
            raise TypeError("compiler fidelity compiled result has the wrong type")
        if not isinstance(native, TPMNativeConditionalEvaluation):
            raise TypeError("compiler fidelity native result has the wrong type")
        if compiled.pair_id != pair.pair_id or native.pair_id != pair.pair_id:
            raise ValueError("compiler fidelity result references a different pair")
        if native.artifact_id != pair.source.artifact_id:
            raise ValueError("compiler fidelity result references a different artifact")
        if (
            native.backend_generation != pair.source.backend_generation
            or native.backend_api_version != pair.source.backend_api_version
        ):
            raise ValueError("compiler fidelity native backend identity is mismatched")
        fields = (
            "numerator_log",
            "denominator_log",
            "conditional_log_risk",
            "conditional_probability",
        )
        differences = {
            name: float(getattr(compiled, name)) - float(getattr(native, name))
            for name in fields
        }
        cases.append(
            {
                "case_name": case_name,
                "assignment_mode": compiled.assignment_mode,
                "assignments": dict(compiled.assignments),
                "compiled": compiled.to_dict(),
                "native": native.to_dict(),
                "differences": differences,
            }
        )
    return TPMCompilerFidelityEvidence(
        pair_id=pair.pair_id,
        source=pair.source,
        encoding=pair.encoding.to_dict(),
        numerical_policy=pair.numerical_policy.to_dict(),
        cases=tuple(cases),
        metric_definitions={
            "delta_direction": "compiled-minus-native",
            "reported_fields": [
                "numerator_log",
                "denominator_log",
                "conditional_log_risk",
                "conditional_probability",
            ],
            "numerical_gate": "none",
        },
        provenance=provenance or {},
    )


def _validate_attachment_namespace(model: object, *, namespace: str) -> str:
    normalized = str(namespace)
    if (
        not normalized
        or not normalized.isidentifier()
        or keyword.iskeyword(normalized)
    ):
        raise ValueError(
            "attachment namespace must be a nonempty Python/Pyomo identifier"
        )
    component = getattr(model, "component", None)
    add_component = getattr(model, "add_component", None)
    if not callable(component) or not callable(add_component):
        raise TypeError("attachment target must be an existing Pyomo model")
    if component(normalized) is not None:
        raise ValueError(f"attachment namespace {normalized!r} is already occupied")
    return normalized


def _validate_scalar_binary_variable(
    model: object,
    variable: object,
    *,
    feature_name: str,
) -> None:
    is_indexed = getattr(variable, "is_indexed", None)
    if callable(is_indexed) and is_indexed():
        raise TypeError(
            f"binary mapping for {feature_name!r} must use a scalar variable"
        )
    is_variable_type = getattr(variable, "is_variable_type", None)
    if not callable(is_variable_type) or not is_variable_type():
        raise TypeError(
            f"binary mapping for {feature_name!r} must use a Pyomo variable"
        )
    if variable.model() is not model:
        raise ValueError(
            f"binary mapping for {feature_name!r} references a foreign model variable"
        )
    if not variable.is_binary():
        raise ValueError(
            f"binary mapping for {feature_name!r} requires a caller-owned Binary variable"
        )


def _inspect_structural_affine_expression(
    backend: object,
    model: object,
    expression: object,
    *,
    feature_name: str,
) -> tuple[object, ...]:
    """Validate affinity with fixed caller variables kept structurally symbolic."""

    from pyomo.core.expr.numvalue import NumericValue
    from pyomo.core.expr.visitor import (
        clone_expression,
        identify_mutable_parameters,
        identify_variables,
    )
    from pyomo.repn import generate_standard_repn

    is_indexed = getattr(expression, "is_indexed", None)
    if callable(is_indexed) and is_indexed():
        raise TypeError(
            f"continuous mapping for {feature_name!r} must be a scalar expression"
        )
    if not isinstance(expression, (NumericValue, int, float)) or isinstance(
        expression, bool
    ):
        raise TypeError(
            f"continuous mapping for {feature_name!r} must be a scalar numeric expression"
        )
    variables = tuple(identify_variables(expression, include_fixed=True))
    if not variables:
        raise ValueError(
            f"continuous mapping for {feature_name!r} must reference at least one "
            "caller-owned variable; constant-only mappings are invalid"
        )
    for variable in variables:
        if variable.model() is not model:
            raise ValueError(
                f"continuous mapping for {feature_name!r} references a foreign "
                "variable outside the caller model"
            )
        if not variable.is_continuous():
            raise ValueError(
                f"continuous mapping for {feature_name!r} contains an integer or "
                "binary variable"
            )
    for parameter in identify_mutable_parameters(expression):
        try:
            value = float(backend.value(parameter))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"continuous mapping for {feature_name!r} contains an "
                "uninitialized or unfixed parameter"
            ) from exc
        if not math.isfinite(value):
            raise ValueError(
                f"continuous mapping for {feature_name!r} contains a nonfinite parameter"
            )

    dummy = backend.ConcreteModel()
    dummy.VARIABLE_INDEX = backend.Set(
        initialize=tuple(range(len(variables))), ordered=True
    )
    dummy.variable = backend.Var(dummy.VARIABLE_INDEX, domain=backend.Reals)
    symbolic = clone_expression(
        expression,
        substitute={
            id(variable): dummy.variable[index]
            for index, variable in enumerate(variables)
        },
    )
    try:
        representation = generate_standard_repn(
            symbolic, compute_values=True, quadratic=True
        )
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(
            f"continuous mapping for {feature_name!r} must have finite affine coefficients"
        ) from exc
    if representation.nonlinear_expr is not None or representation.quadratic_vars:
        raise ValueError(
            f"continuous mapping for {feature_name!r} must be structurally affine; "
            "nonlinear products remain invalid when variables are fixed"
        )
    numeric_values = (representation.constant, *representation.linear_coefs)
    for value in numeric_values:
        try:
            normalized = float(backend.value(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"continuous mapping for {feature_name!r} has a nonfinite coefficient"
            ) from exc
        if not math.isfinite(normalized):
            raise ValueError(
                f"continuous mapping for {feature_name!r} has a nonfinite coefficient"
            )
    return variables


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
        exp_y = tuple(float(value) for value in sum_configuration["exp_y_points"])
        if log_x[0] > 1.0 or log_x[-1] < float(maximum_sum_arity):
            raise ValueError(
                "piecewise logarithm curve does not cover the resolved Sum arity"
            )
        if exp_x[-1] != 0.0:
            raise ValueError("piecewise exponential curve must end exactly at zero")
        if "guard_policy" not in sum_configuration:
            cutoff = math.log(DEFAULT_EXP_PROBABILITY_FLOOR)
            base_pairs = tuple(
                (x_value, y_value)
                for x_value, y_value in zip(exp_x, exp_y, strict=True)
                if x_value >= cutoff and y_value > 0.0
            )
            if len(base_pairs) < 2:
                raise ValueError(
                    "piecewise exponential curve does not retain a base curve "
                    "covering the guarded transition"
                )
            guarded = resolve_guarded_exponential_spec(
                base_x_points=tuple(value[0] for value in base_pairs),
                base_y_points=tuple(value[1] for value in base_pairs),
                domain_floor=float(
                    sum_configuration.get(
                        "exp_domain_floor", CONDITIONAL_GUARD_DOMAIN_FLOOR
                    )
                ),
                probability_floor=DEFAULT_EXP_PROBABILITY_FLOOR,
                transition_width=CONDITIONAL_GUARD_TRANSITION_WIDTH,
            )
            sum_configuration.update(guarded)
        guarded_exponential_points(sum_configuration)
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
                    evaluate_guarded_exponential(
                        term - maximum,
                        configuration=sum_configuration,
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
    "TPMConditionalDiagnosticsError",
    "TPMConditionalEvaluationError",
    "attach_conditional_mio_pair",
    "build_compiler_fidelity_evidence",
    "build_embedding_parity_evidence",
    "compile_conditional_mio_pair",
    "evaluate_conditional_mio_pair",
    "inspect_conditional_mio_attachment",
]
