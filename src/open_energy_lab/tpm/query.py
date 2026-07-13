"""Import-light TPM query requests and deterministic artifact-backed evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from typing import Any

from .artifact import TPMArtifact, load_tpm_artifact
from .features import TPMFeatureSpec

DEFAULT_QUERY_NUMERIC_TOLERANCE = 1e-9


def _is_non_boolean_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class TPMQueryRequest:
    """Persisted query inputs for conditional TPM evaluation."""

    decision_assignments: Mapping[str, object] = field(default_factory=dict)
    marginalized_features: tuple[str, ...] = field(default_factory=tuple)
    output_mode: str = "conditional_probability"
    target_name: str = "shortfall"
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
        if not target_name:
            raise ValueError("target_name must be non-empty")
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
    target_name: str
    target_threshold: float
    numeric_tolerance: float


def query_tpm_artifact(
    artifact: TPMArtifact | str | Path | Mapping[str, Any],
    request: TPMQueryRequest,
) -> dict[str, object]:
    """Evaluate one conditional TPM query from a persisted artifact contract."""

    resolved_artifact = _load_artifact(artifact)
    context = _build_query_context(resolved_artifact, request)
    result = _evaluate_empirical_query(resolved_artifact, request, context)
    if result is None:
        result = _evaluate_fallback_query(request, context)

    response = {
        "artifact_id": resolved_artifact.artifact_id,
        "dataset_reference": resolved_artifact.dataset_reference,
        "target_name": context.target_name,
        "output_mode": request.output_mode,
        "target_threshold": context.target_threshold,
        "decision_assignments": dict(request.decision_assignments),
        "marginalized_features": tuple(request.marginalized_features),
        "matched_row_count": result["matched_row_count"],
        "total_row_count": result["total_row_count"],
        "source": result["source"],
        "value": float(result["value"]),
    }
    response[request.output_mode] = response["value"]
    return response


__all__ = [
    "DEFAULT_QUERY_NUMERIC_TOLERANCE",
    "TPMQueryRequest",
    "query_tpm_artifact",
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
    target_name = str(artifact.target_definition.get("target_name", ""))
    if request.target_name != target_name:
        raise ValueError(
            f"unsupported target request {request.target_name!r}; expected {target_name!r}"
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

    if target_name in assignment_names:
        raise ValueError(f"target feature {target_name!r} cannot appear in decision_assignments")
    if target_name in marginalized_names:
        raise ValueError(f"target feature {target_name!r} cannot be marginalized")

    artifact.validate_feature_assignments(request.decision_assignments)
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

    required_decision_features = tuple(
        str(feature_name)
        for feature_name in artifact.query_configuration.get(
            "required_decision_features",
            (),
        )
    )
    unresolved_required_features = [
        feature_name
        for feature_name in required_decision_features
        if feature_name not in assignment_names and feature_name not in marginalized_names
    ]
    if unresolved_required_features:
        raise ValueError(
            "required decision feature assignments are missing: "
            + ", ".join(unresolved_required_features)
        )

    target_threshold = float(
        request.target_threshold
        if request.target_threshold is not None
        else artifact.target_definition.get("threshold_default", 0.0)
    )
    numeric_tolerance = float(
        request.numeric_tolerance
        if request.numeric_tolerance is not None
        else artifact.approximation_metadata.get(
            "tolerance",
            DEFAULT_QUERY_NUMERIC_TOLERANCE,
        )
    )

    return _QueryContext(
        feature_by_name=feature_by_name,
        supported_output_modes=supported_output_modes,
        required_decision_features=required_decision_features,
        target_name=target_name,
        target_threshold=target_threshold,
        numeric_tolerance=numeric_tolerance,
    )


def _evaluate_empirical_query(
    artifact: TPMArtifact,
    request: TPMQueryRequest,
    context: _QueryContext,
) -> dict[str, object] | None:
    dataset = _load_empirical_dataset(artifact)
    if dataset is None:
        return None

    target_name = context.target_name
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
    }


def _load_empirical_dataset(artifact: TPMArtifact) -> Any | None:
    dataset_fixture_path = artifact.provenance.get("dataset_fixture_path")
    if not isinstance(dataset_fixture_path, str) or not dataset_fixture_path:
        return None

    from open_energy_lab.planning.dataset import load_planning_dataset

    try:
        return load_planning_dataset(Path(dataset_fixture_path))
    except (FileNotFoundError, TypeError, ValueError):
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
    }


def _fallback_probability(
    request: TPMQueryRequest,
    context: _QueryContext,
) -> float:
    del request
    del context
    return 0.0
