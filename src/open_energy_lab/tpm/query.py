"""Import-light TPM query requests and deterministic artifact-backed evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from typing import Any

from .artifact import (
    SUPPORTED_TPM_EXECUTION_MODES,
    TPMArtifact,
    load_tpm_artifact,
)
from .features import (
    TPMFeatureSpec,
    validate_spflow_feature_assignments,
)
from .optional_spflow import evaluate_spflow_query, load_spflow_payload
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
    execution_mode: str = "production"

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

        marginalized_features = tuple(str(feature_name) for feature_name in self.marginalized_features)
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

        execution_mode = str(self.execution_mode)
        if execution_mode not in SUPPORTED_TPM_EXECUTION_MODES:
            raise ValueError(
                "execution_mode must be one of "
                f"{SUPPORTED_TPM_EXECUTION_MODES!r}; got {execution_mode!r}"
            )
        object.__setattr__(self, "execution_mode", execution_mode)


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
    result = None
    if request.execution_mode == "production":
        result = _evaluate_current_spflow_query(resolved_artifact, request, context)
    if result is None:
        result = evaluate_spflow_query(
            resolved_artifact,
            feature_specs=context.feature_by_name,
            decision_assignments=request.decision_assignments,
            marginalized_features=request.marginalized_features,
            canonical_target_name=context.canonical_target_name,
            event_target_name=context.event_target_name,
            output_mode=request.output_mode,
            numeric_tolerance=context.numeric_tolerance,
        )
    if result is None:
        result = _evaluate_empirical_query(resolved_artifact, request, context)
    if result is None:
        result = _evaluate_fallback_query(request, context)

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


__all__ = [
    "DEFAULT_QUERY_NUMERIC_TOLERANCE",
    "TPMQueryRequest",
    "marginalize_spflow_model",
    "query_tpm_artifact",
    "reduce_spflow_log_likelihood",
]


def _load_artifact(artifact: TPMArtifact | str | Path | Mapping[str, Any]) -> TPMArtifact:
    if isinstance(artifact, TPMArtifact):
        return artifact
    return load_tpm_artifact(artifact)


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
    validate_spflow_feature_assignments(
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
    marginalize = getattr(model, "marginalize", None)
    if not callable(marginalize):
        raise TypeError("current SPFlow model must provide marginalize()")
    return marginalize(list(normalized_indices))


def _evaluate_current_spflow_query(
    artifact: TPMArtifact,
    request: TPMQueryRequest,
    context: _QueryContext,
) -> dict[str, object] | None:
    runtime_payload = load_spflow_payload(artifact)
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
    total_row_count = len(raw_rows) if isinstance(raw_rows, tuple | list) else 0
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


def _evaluate_empirical_query(
    artifact: TPMArtifact,
    request: TPMQueryRequest,
    context: _QueryContext,
) -> dict[str, object] | None:
    dataset = _load_empirical_dataset(artifact)
    if dataset is None:
        return None

    target_name = context.canonical_target_name
    event_target_name = context.event_target_name
    required_columns = set(request.decision_assignments)
    required_columns.add(target_name)
    if not required_columns.issubset(dataset.column_order):
        return None

    matching_rows = [
        row
        for row in dataset.rows
        if _row_matches_assignments(
            row,
            assignments=request.decision_assignments,
            feature_by_name=context.feature_by_name,
            numeric_tolerance=context.numeric_tolerance,
        )
    ]
    total_row_count = len(dataset.rows)
    matched_row_count = len(matching_rows)

    if request.output_mode == "conditional_probability":
        if matched_row_count == 0:
            value = 0.0
        else:
            if event_target_name in dataset.column_order:
                value = sum(int(row[event_target_name]) for row in matching_rows) / matched_row_count
            else:
                value = sum(
                    float(row[target_name]) > context.target_threshold for row in matching_rows
                ) / matched_row_count
    else:
        evidence_probability = matched_row_count / total_row_count if total_row_count else 0.0
        value = math.log(max(evidence_probability, context.numeric_tolerance))

    return {
        "matched_row_count": matched_row_count,
        "total_row_count": total_row_count,
        "source": "empirical_fixture",
        "value": float(value),
        "resolved_target_name": event_target_name,
    }


def _load_empirical_dataset(artifact: TPMArtifact) -> Any | None:
    dataset_path = _resolved_dataset_path(artifact.provenance)
    if dataset_path is None:
        return None

    from open_energy_lab.planning.dataset import load_planning_dataset

    try:
        return load_planning_dataset(dataset_path)
    except (FileNotFoundError, TypeError, ValueError):
        return None


def _resolved_dataset_path(provenance: Mapping[str, object]) -> Path | None:
    for key in (
        "training_dataset_path",
        "training_dataset_fixture_path",
        "dataset_fixture_path",
    ):
        value = provenance.get(key)
        if isinstance(value, str) and value:
            return Path(value)
    return None


def _row_matches_assignments(
    row: Mapping[str, object],
    *,
    assignments: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    numeric_tolerance: float,
) -> bool:
    for feature_name, expected_value in assignments.items():
        if feature_name not in row:
            return False
        actual_value = row[feature_name]
        spec = feature_by_name[feature_name]
        if _feature_values_match(
            spec,
            actual_value,
            expected_value,
            numeric_tolerance=numeric_tolerance,
        ):
            continue
        return False
    return True


def _feature_values_match(
    spec: TPMFeatureSpec,
    actual_value: object,
    expected_value: object,
    *,
    numeric_tolerance: float,
) -> bool:
    if spec.feature_type == "continuous":
        return _numeric_match(actual_value, expected_value, numeric_tolerance)

    if spec.feature_type in {"binary", "categorical"}:
        return actual_value == expected_value

    if expected_value in spec.discrete_values:
        return actual_value == expected_value
    return _numeric_match(actual_value, expected_value, numeric_tolerance)


def _numeric_match(actual_value: object, expected_value: object, numeric_tolerance: float) -> bool:
    if not _is_non_boolean_real(actual_value) or not _is_non_boolean_real(expected_value):
        return False
    return abs(float(actual_value) - float(expected_value)) <= numeric_tolerance


def _evaluate_fallback_query(
    request: TPMQueryRequest,
    context: _QueryContext,
) -> dict[str, object]:
    probability = _fallback_probability(request, context)
    if request.output_mode == "conditional_probability":
        value = probability
    else:
        value = math.log(max(probability, context.numeric_tolerance))

    return {
        "matched_row_count": 0,
        "total_row_count": 0,
        "source": "artifact_metadata_fallback",
        "value": float(value),
        "resolved_target_name": context.event_target_name,
    }


def _fallback_probability(
    request: TPMQueryRequest,
    context: _QueryContext,
) -> float:
    del request
    del context
    return 0.0
