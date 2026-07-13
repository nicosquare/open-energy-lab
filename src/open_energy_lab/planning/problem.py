"""Scaffolding for chance-constrained planning problem definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from typing import Any

from open_energy_lab.planning.dataset import PlanningDatasetArtifact, load_planning_dataset
from open_energy_lab.planning.piecewise import (
    PiecewisePlanningTerms,
    build_piecewise_planning_terms,
)
from open_energy_lab.tpm.artifact import TPMArtifact, load_tpm_artifact


SUPPORTED_FIRST_RELEASE_DECISION_TYPES = ("battery", "solar")
SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES = (
    "continuous",
    "binary",
    "categorical",
    "mixed",
)


@dataclass(frozen=True, slots=True)
class PlanningProblemDefinition:
    """Minimal placeholder for the planned problem-definition surface."""

    problem_id: str
    decision_features: tuple[str, ...] = field(default_factory=tuple)
    decision_feature_types: Mapping[str, str] = field(default_factory=dict)
    shortfall_threshold: float = 0.0
    chance_limit_epsilon: float = 0.0
    cost_terms: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        problem_id = str(self.problem_id)
        if not problem_id:
            raise ValueError("problem_id must be non-empty")
        object.__setattr__(self, "problem_id", problem_id)

        decision_features = tuple(str(feature_name) for feature_name in self.decision_features)
        if any(not feature_name for feature_name in decision_features):
            raise ValueError("decision_features must contain non-empty names")
        if len(set(decision_features)) != len(decision_features):
            raise ValueError("decision_features must be unique")
        for feature_name in decision_features:
            _validate_first_release_decision_scope(feature_name)
        object.__setattr__(self, "decision_features", decision_features)

        decision_feature_types = {
            str(feature_name): str(feature_type)
            for feature_name, feature_type in self.decision_feature_types.items()
        }
        if decision_feature_types and set(decision_feature_types) != set(decision_features):
            raise ValueError(
                "decision_feature_types must define exactly one type for each "
                "decision feature"
            )
        for feature_name, feature_type in decision_feature_types.items():
            if feature_type not in SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES:
                raise ValueError(
                    f"{feature_name} uses unsupported decision_variable_type "
                    f"{feature_type!r}; expected one of "
                    f"{SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES!r}"
                )
        object.__setattr__(self, "decision_feature_types", decision_feature_types)

        shortfall_threshold = _coerce_probability(
            self.shortfall_threshold,
            field_name="shortfall_threshold",
        )
        chance_limit_epsilon = _coerce_probability(
            self.chance_limit_epsilon,
            field_name="chance_limit_epsilon",
        )
        object.__setattr__(self, "shortfall_threshold", shortfall_threshold)
        object.__setattr__(self, "chance_limit_epsilon", chance_limit_epsilon)

        cost_terms = {str(name): float(value) for name, value in self.cost_terms.items()}
        object.__setattr__(self, "cost_terms", cost_terms)


@dataclass(frozen=True, slots=True)
class PlanningDecisionCandidate:
    """One deterministic candidate design derived from empirical fixture rows."""

    selected_design: Mapping[str, object]
    objective_value: float
    estimated_shortfall_risk: float
    matched_row_count: int


@dataclass(frozen=True, slots=True)
class PlanningProblemAssembly:
    """Offline assembly result for a first-release planning problem."""

    problem_id: str
    artifact_id: str
    dataset_reference: str
    decision_features: tuple[str, ...]
    target_name: str
    shortfall_threshold: float
    chance_limit_epsilon: float
    objective_direction: str
    cost_terms: Mapping[str, float]
    candidate_designs: tuple[PlanningDecisionCandidate, ...]
    piecewise_terms: PiecewisePlanningTerms
    solver_metadata: Mapping[str, object]


def assemble_planning_problem(
    problem_definition: PlanningProblemDefinition,
    artifact: TPMArtifact | str | Path | Mapping[str, Any],
) -> PlanningProblemAssembly:
    """Assemble a deterministic offline planning problem from fixture-backed TPM data."""

    resolved_artifact = _load_artifact(artifact)
    target_name = str(resolved_artifact.target_definition.get("target_name", ""))
    if target_name != "shortfall":
        raise ValueError(
            f"unsupported planning target {target_name!r}; expected 'shortfall'"
        )

    if not problem_definition.cost_terms:
        raise ValueError("cost_terms must be non-empty for first-release planning")

    feature_specs = {
        feature_spec.feature_name: feature_spec
        for feature_spec in resolved_artifact.feature_specs
    }
    missing_features = [
        feature_name
        for feature_name in problem_definition.decision_features
        if feature_name not in feature_specs
    ]
    if missing_features:
        raise ValueError(
            "decision_features reference unknown TPM features: " + ", ".join(missing_features)
        )

    missing_cost_terms = [
        feature_name
        for feature_name in problem_definition.decision_features
        if feature_name not in problem_definition.cost_terms
    ]
    if missing_cost_terms:
        raise ValueError(
            "cost_terms must define deterministic costs for each decision feature: "
            + ", ".join(missing_cost_terms)
        )

    for feature_name in problem_definition.decision_features:
        feature_spec = feature_specs[feature_name]
        if feature_spec.feature_role != "decision" or not feature_spec.modifiable:
            raise ValueError(
                f"{feature_name!r} must be a modifiable decision feature in the TPM artifact"
            )
        expected_type = problem_definition.decision_feature_types.get(feature_name)
        if expected_type is not None and feature_spec.feature_type != expected_type:
            raise ValueError(
                f"{feature_name!r} expected decision_variable_type {expected_type!r} "
                f"but the TPM artifact declares {feature_spec.feature_type!r}"
            )

    dataset = _load_empirical_dataset(resolved_artifact)
    if dataset is None:
        raise ValueError(
            "planning assembly requires a fixture-backed planning dataset referenced "
            "by TPM artifact provenance"
        )

    piecewise_terms = build_piecewise_planning_terms(
        resolved_artifact.approximation_metadata,
        max_terms=len(problem_definition.decision_features),
    )
    candidate_designs = _build_candidate_designs(
        dataset,
        decision_features=problem_definition.decision_features,
        target_name=target_name,
        shortfall_threshold=problem_definition.shortfall_threshold,
        cost_terms=problem_definition.cost_terms,
    )

    solver_metadata = {
        "canonical_backend": "pyomo",
        "solver_backend_required": True,
        "solver_execution_optional": True,
        "dataset_fixture_path": resolved_artifact.provenance.get("dataset_fixture_path"),
        "training_random_seed": resolved_artifact.provenance.get("training_random_seed"),
        "fit_numeric_tolerance": piecewise_terms.fit_numeric_tolerance,
        "query_numeric_tolerance": piecewise_terms.query_numeric_tolerance,
        "approximation_kind": piecewise_terms.approximation_kind,
    }

    return PlanningProblemAssembly(
        problem_id=problem_definition.problem_id,
        artifact_id=resolved_artifact.artifact_id,
        dataset_reference=resolved_artifact.dataset_reference,
        decision_features=problem_definition.decision_features,
        target_name=target_name,
        shortfall_threshold=problem_definition.shortfall_threshold,
        chance_limit_epsilon=problem_definition.chance_limit_epsilon,
        objective_direction="minimize",
        cost_terms=dict(problem_definition.cost_terms),
        candidate_designs=candidate_designs,
        piecewise_terms=piecewise_terms,
        solver_metadata=solver_metadata,
    )


__all__ = [
    "PlanningDecisionCandidate",
    "PlanningProblemDefinition",
    "PlanningProblemAssembly",
    "SUPPORTED_FIRST_RELEASE_DECISION_TYPES",
    "SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES",
    "assemble_planning_problem",
]


def _validate_first_release_decision_scope(feature_name: str) -> None:
    if any(
        feature_name == decision_scope or feature_name.startswith(f"{decision_scope}_")
        for decision_scope in SUPPORTED_FIRST_RELEASE_DECISION_TYPES
    ):
        return
    raise ValueError(
        f"{feature_name!r} is outside the first-release planning scope; "
        f"expected battery/solar decision features"
    )


def _coerce_probability(value: object, *, field_name: str) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a real number between 0.0 and 1.0")
    probability = float(value)
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return probability


def _load_artifact(artifact: TPMArtifact | str | Path | Mapping[str, Any]) -> TPMArtifact:
    if isinstance(artifact, TPMArtifact):
        return artifact
    return load_tpm_artifact(artifact)


def _load_empirical_dataset(artifact: TPMArtifact) -> PlanningDatasetArtifact | None:
    dataset_fixture_path = artifact.provenance.get("dataset_fixture_path")
    if not isinstance(dataset_fixture_path, str) or not dataset_fixture_path:
        return None

    try:
        return load_planning_dataset(Path(dataset_fixture_path))
    except (FileNotFoundError, TypeError, ValueError):
        return None


def _build_candidate_designs(
    dataset: PlanningDatasetArtifact,
    *,
    decision_features: tuple[str, ...],
    target_name: str,
    shortfall_threshold: float,
    cost_terms: Mapping[str, float],
) -> tuple[PlanningDecisionCandidate, ...]:
    candidate_stats: dict[tuple[object, ...], dict[str, object]] = {}
    candidate_order: list[tuple[object, ...]] = []

    for row in dataset.rows:
        selected_design = {
            feature_name: row[feature_name]
            for feature_name in decision_features
        }
        candidate_key = tuple(selected_design[feature_name] for feature_name in decision_features)
        if candidate_key not in candidate_stats:
            candidate_stats[candidate_key] = {
                "selected_design": selected_design,
                "matched_row_count": 0,
                "violation_count": 0,
            }
            candidate_order.append(candidate_key)

        candidate_entry = candidate_stats[candidate_key]
        candidate_entry["matched_row_count"] = int(candidate_entry["matched_row_count"]) + 1
        if float(row[target_name]) > shortfall_threshold:
            candidate_entry["violation_count"] = int(candidate_entry["violation_count"]) + 1

    candidates: list[PlanningDecisionCandidate] = []
    for candidate_key in candidate_order:
        candidate_entry = candidate_stats[candidate_key]
        selected_design = dict(candidate_entry["selected_design"])
        matched_row_count = int(candidate_entry["matched_row_count"])
        violation_count = int(candidate_entry["violation_count"])
        estimated_shortfall_risk = (
            violation_count / matched_row_count if matched_row_count else 0.0
        )
        objective_value = sum(
            _cost_contribution(
                selected_design[feature_name],
                coefficient=float(cost_terms[feature_name]),
                feature_name=feature_name,
            )
            for feature_name in decision_features
        )
        candidates.append(
            PlanningDecisionCandidate(
                selected_design=selected_design,
                objective_value=float(objective_value),
                estimated_shortfall_risk=float(estimated_shortfall_risk),
                matched_row_count=matched_row_count,
            )
        )
    return tuple(candidates)


def _cost_contribution(value: object, *, coefficient: float, feature_name: str) -> float:
    if isinstance(value, bool):
        return float(value) * coefficient
    if not isinstance(value, Real):
        raise ValueError(
            f"{feature_name!r} must resolve to a numeric design value for "
            "deterministic first-release cost evaluation"
        )
    return float(value) * coefficient
