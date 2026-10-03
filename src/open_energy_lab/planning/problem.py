"""Scaffolding for chance-constrained planning problem definitions."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from typing import Any

from open_energy_lab.planning.piecewise import (
    PiecewisePlanningTerms,
    SUPPORTED_FIRST_RELEASE_DECISION_TYPES,
    SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES,
    build_current_spflow_planning_payload,
    build_piecewise_planning_terms,
    validate_first_release_decision_features,
)
from tpm.artifact import TPMArtifact, load_tpm_artifact
from tpm.domains import TPMApproximationDomain
from tpm.mio import compile_spflow_model_to_mio, infer_max_sum_terms
from tpm.optional_spflow import (
    load_spflow_payload,
)
from tpm.query import marginalize_spflow_model

SUPPORTED_OBJECTIVE_DIRECTIONS = ("minimize",)
SUPPORTED_PLANNING_BACKENDS = ("pyomo",)
DEFAULT_SOLVER_NUMERIC_TOLERANCE = 1e-9
DEFAULT_SOLVER_NAME = "highs"
DEFAULT_SOLVER_RANDOM_SEED = 13
DEFAULT_SOLVER_THREADS = 1
DEFAULT_SOLVER_TIME_LIMIT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class PlanningProblemDefinition:
    """Validated first-release planning-problem definition."""

    problem_id: str
    decision_features: tuple[str, ...] = field(default_factory=tuple)
    decision_feature_types: Mapping[str, str] = field(default_factory=dict)
    shortfall_threshold: float = 0.0
    chance_limit_epsilon: float = 0.0
    cost_terms: Mapping[str, float] = field(default_factory=dict)
    option_costs: Mapping[str, Mapping[object, float]] = field(default_factory=dict)
    tpm_artifact_reference: str = ""
    objective_direction: str = "minimize"
    solver_configuration: Mapping[str, object] = field(default_factory=dict)
    approximation_contract: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        problem_id = str(self.problem_id)
        if not problem_id:
            raise ValueError("problem_id must be non-empty")
        object.__setattr__(self, "problem_id", problem_id)

        decision_features, decision_feature_types = validate_first_release_decision_features(
            self.decision_features,
            decision_feature_types=(
                self.decision_feature_types if self.decision_feature_types else None
            ),
        )
        object.__setattr__(self, "decision_features", decision_features)
        object.__setattr__(self, "decision_feature_types", decision_feature_types)

        shortfall_threshold = _coerce_non_negative_real(
            self.shortfall_threshold, field_name="shortfall_threshold"
        )
        chance_limit_epsilon = _coerce_probability(
            self.chance_limit_epsilon,
            field_name="chance_limit_epsilon",
        )
        object.__setattr__(self, "shortfall_threshold", shortfall_threshold)
        object.__setattr__(self, "chance_limit_epsilon", chance_limit_epsilon)

        cost_terms = {str(name): float(value) for name, value in self.cost_terms.items()}
        object.__setattr__(self, "cost_terms", cost_terms)
        option_costs = {
            str(name): {option: float(cost) for option, cost in values.items()}
            for name, values in self.option_costs.items()
        }
        object.__setattr__(self, "option_costs", option_costs)

        tpm_artifact_reference = str(self.tpm_artifact_reference)
        object.__setattr__(self, "tpm_artifact_reference", tpm_artifact_reference)

        objective_direction = str(self.objective_direction)
        if objective_direction not in SUPPORTED_OBJECTIVE_DIRECTIONS:
            raise ValueError(
                "objective_direction must be one of "
                f"{SUPPORTED_OBJECTIVE_DIRECTIONS!r}"
            )
        object.__setattr__(self, "objective_direction", objective_direction)

        solver_configuration = _normalize_solver_configuration(self.solver_configuration)
        object.__setattr__(self, "solver_configuration", solver_configuration)

        approximation_contract = _normalize_approximation_contract(
            self.approximation_contract
        )
        object.__setattr__(self, "approximation_contract", approximation_contract)


@dataclass(frozen=True, slots=True)
class PlanningProblemAssembly:
    """Offline assembly result for a first-release planning problem."""

    problem_id: str
    artifact_id: str
    dataset_reference: str
    decision_features: tuple[str, ...]
    target_name: str
    risk_target_name: str
    shortfall_threshold: float
    chance_limit_epsilon: float
    objective_direction: str
    cost_terms: Mapping[str, float]
    piecewise_terms: PiecewisePlanningTerms
    solver_metadata: Mapping[str, object]
    option_costs: Mapping[str, Mapping[object, float]] = field(default_factory=dict)
    chance_constraint_metadata: Mapping[str, object] = field(default_factory=dict)
    solver_configuration: Mapping[str, object] = field(default_factory=dict)
    approximation_contract: Mapping[str, object] = field(default_factory=dict)
    spn_mip_payload: Mapping[str, object] = field(default_factory=dict)


def assemble_planning_problem(
    problem_definition: PlanningProblemDefinition,
    artifact: TPMArtifact | str | Path | Mapping[str, Any] | None = None,
) -> PlanningProblemAssembly:
    """Assemble an SPN chance-constrained planning problem from a current-SPFlow artifact."""

    resolved_artifact = _load_artifact(
        artifact,
        artifact_reference=problem_definition.tpm_artifact_reference,
    )
    target_name = str(resolved_artifact.target_definition.get("target_name", ""))
    risk_target_name = str(
        resolved_artifact.target_definition.get("event_target_name", target_name)
    )
    if not target_name:
        raise ValueError("planning artifact target_name must be non-empty")
    supported_query_mode = str(
        resolved_artifact.target_definition.get("supported_query_mode", "")
    )
    if supported_query_mode != "exceedance-probability":
        raise ValueError(
            "planning assembly requires target_definition.supported_query_mode "
            "to be 'exceedance-probability'"
        )

    if bool(problem_definition.cost_terms) == bool(problem_definition.option_costs):
        raise ValueError("define exactly one of cost_terms or option_costs")

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

    active_costs = (
        problem_definition.option_costs
        if problem_definition.option_costs
        else problem_definition.cost_terms
    )
    missing_cost_terms = [
        feature_name
        for feature_name in problem_definition.decision_features
        if feature_name not in active_costs
    ]
    if missing_cost_terms:
        raise ValueError(
            "cost configuration must define deterministic costs for each decision feature: "
            + ", ".join(missing_cost_terms)
        )

    resolved_decision_feature_types: dict[str, str] = {}
    for feature_name in problem_definition.decision_features:
        feature_spec = feature_specs[feature_name]
        if feature_spec.feature_role != "decision" or not feature_spec.modifiable:
            raise ValueError(
                f"{feature_name!r} must be a modifiable decision feature in the TPM artifact"
            )
        if (
            feature_spec.feature_type
            not in SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES
        ):
            raise ValueError(
                f"{feature_name!r} uses unsupported decision_variable_type "
                f"{feature_spec.feature_type!r} in the TPM artifact"
            )
        expected_type = problem_definition.decision_feature_types.get(feature_name)
        if expected_type is not None and feature_spec.feature_type != expected_type:
            raise ValueError(
                f"{feature_name!r} expected decision_variable_type {expected_type!r} "
                f"but the TPM artifact declares {feature_spec.feature_type!r}"
            )
        resolved_decision_feature_types[feature_name] = feature_spec.feature_type

        if problem_definition.option_costs:
            if feature_spec.feature_type != "categorical":
                raise ValueError("option_costs require categorical decision features")
            categories = tuple(feature_spec.ordering or feature_spec.discrete_values)
            supplied = problem_definition.option_costs[feature_name]
            if set(supplied) != set(categories):
                raise ValueError(
                    f"option_costs for {feature_name!r} must exactly match {categories!r}"
                )

    spn_payload = _build_solver_facing_spn_payload(
        problem_definition,
        artifact=resolved_artifact,
    )

    piecewise_terms = build_piecewise_planning_terms(
        resolved_artifact.approximation_metadata,
        max_terms=infer_max_sum_terms(spn_payload),
        decision_features=problem_definition.decision_features,
        decision_feature_types=resolved_decision_feature_types,
    )
    _validate_approximation_contract(
        problem_definition.approximation_contract,
        piecewise_terms=piecewise_terms,
    )
    chance_constraint_metadata = {
        "target_name": target_name,
        "event_target_name": risk_target_name,
        "comparison": ">",
        "threshold": problem_definition.shortfall_threshold,
        "chance_limit_epsilon": problem_definition.chance_limit_epsilon,
        "supported_query_mode": supported_query_mode,
    }
    approximation_contract = {
        **dict(problem_definition.approximation_contract),
        "leaf_encoding_mode": piecewise_terms.leaf_encoding_mode,
        "sum_encoding_mode": piecewise_terms.sum_encoding_mode,
        "mio_epsilon": piecewise_terms.mio_epsilon,
    }

    solver_metadata = {
        "canonical_backend": problem_definition.solver_configuration["backend_name"],
        "solver_backend_required": problem_definition.solver_configuration[
            "solver_backend_required"
        ],
        "solver_execution_optional": problem_definition.solver_configuration[
            "solver_execution_optional"
        ],
        "solver_name": problem_definition.solver_configuration["solver_name"],
        "dataset_fixture_path": _resolved_dataset_path_text(resolved_artifact.provenance),
        "training_random_seed": resolved_artifact.provenance.get("training_random_seed"),
        "fit_numeric_tolerance": piecewise_terms.fit_numeric_tolerance,
        "query_numeric_tolerance": piecewise_terms.query_numeric_tolerance,
        "approximation_kind": piecewise_terms.approximation_kind,
        "solver_numeric_tolerance": problem_definition.solver_configuration[
            "numeric_tolerance"
        ],
        "solver_random_seed": problem_definition.solver_configuration["random_seed"],
        "solver_threads": problem_definition.solver_configuration["threads"],
        "time_limit_seconds": problem_definition.solver_configuration[
            "time_limit_seconds"
        ],
        "chance_constraint_event": chance_constraint_metadata,
        "spn_payload_source": spn_payload["source"],
        "spn_payload_locator": spn_payload["payload_locator"],
    }

    return PlanningProblemAssembly(
        problem_id=problem_definition.problem_id,
        artifact_id=resolved_artifact.artifact_id,
        dataset_reference=resolved_artifact.dataset_reference,
        decision_features=problem_definition.decision_features,
        target_name=target_name,
        risk_target_name=risk_target_name,
        shortfall_threshold=problem_definition.shortfall_threshold,
        chance_limit_epsilon=problem_definition.chance_limit_epsilon,
        objective_direction=problem_definition.objective_direction,
        cost_terms=dict(problem_definition.cost_terms),
        option_costs={
            name: dict(values) for name, values in problem_definition.option_costs.items()
        },
        piecewise_terms=piecewise_terms,
        solver_metadata=solver_metadata,
        chance_constraint_metadata=chance_constraint_metadata,
        solver_configuration=dict(problem_definition.solver_configuration),
        approximation_contract=approximation_contract,
        spn_mip_payload=dict(spn_payload),
    )


__all__ = [
    "PlanningProblemDefinition",
    "PlanningProblemAssembly",
    "SUPPORTED_FIRST_RELEASE_DECISION_TYPES",
    "SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES",
    "SUPPORTED_OBJECTIVE_DIRECTIONS",
    "SUPPORTED_PLANNING_BACKENDS",
    "assemble_planning_problem",
]


def _coerce_probability(value: object, *, field_name: str) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a real number between 0.0 and 1.0")
    probability = float(value)
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return probability


def _coerce_non_negative_real(value: object, *, field_name: str) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative real number")
    result = float(value)
    if result < 0.0 or not math.isfinite(result):
        raise ValueError(f"{field_name} must be a finite non-negative real number")
    return result


def _load_artifact(
    artifact: TPMArtifact | str | Path | Mapping[str, Any] | None,
    *,
    artifact_reference: str,
) -> TPMArtifact:
    if artifact is None:
        if not artifact_reference:
            raise ValueError(
                "assemble_planning_problem requires either an artifact argument "
                "or PlanningProblemDefinition.tpm_artifact_reference"
            )
        return load_tpm_artifact(Path(artifact_reference))
    if isinstance(artifact, TPMArtifact):
        return artifact
    return load_tpm_artifact(artifact)


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


def _resolved_dataset_path_text(provenance: Mapping[str, object]) -> str | None:
    dataset_path = _resolved_dataset_path(provenance)
    if dataset_path is None:
        return None
    return dataset_path.as_posix()


def _has_current_spflow_compiler_payload(artifact: TPMArtifact) -> bool:
    return (
        artifact.execution_mode == "production"
        and artifact.backend_generation == "current-spflow"
        and artifact.spn_payload_format == "spflow-model-sidecar"
    )


def _build_solver_facing_spn_payload(
    problem_definition: PlanningProblemDefinition,
    *,
    artifact: TPMArtifact,
) -> dict[str, object]:
    if not _has_current_spflow_compiler_payload(artifact):
        raise ValueError(
            "planning requires a current-SPFlow production TPM artifact with a model "
            f"sidecar; artifact {artifact.artifact_id!r} has execution_mode "
            f"{artifact.execution_mode!r}, backend_generation "
            f"{artifact.backend_generation!r} and spn_payload_format "
            f"{artifact.spn_payload_format!r}"
        )

    artifact_threshold = float(
        artifact.target_definition.get("threshold_default", 0.0)
    )
    if not math.isclose(
        problem_definition.shortfall_threshold,
        artifact_threshold,
        rel_tol=0.0,
        abs_tol=DEFAULT_SOLVER_NUMERIC_TOLERANCE,
    ):
        raise ValueError(
            "production current-SPFlow planning requires shortfall_threshold "
            f"{artifact_threshold!r} from the fitted event target; found "
            f"{problem_definition.shortfall_threshold!r}"
        )

    runtime_payload = load_spflow_payload(artifact)
    if runtime_payload is None or runtime_payload.get("model") is None:
        raise ValueError(
            "production current-SPFlow planning requires a persisted model sidecar"
        )
    retained_names = {
        *problem_definition.decision_features,
        str(artifact.target_definition["event_target_name"]),
    }
    marginalized_indices = tuple(
        index
        for index, spec in enumerate(artifact.feature_specs)
        if spec.feature_name not in retained_names
    )
    compilation_model = (
        marginalize_spflow_model(runtime_payload["model"], marginalized_indices)
        if marginalized_indices
        else runtime_payload["model"]
    )
    approximation_domains = _approximation_domains_from_contract(
        problem_definition.approximation_contract
    )
    retained_scope = tuple(int(index) for index in compilation_model.scope.query)
    retained_continuous = tuple(
        index
        for index in retained_scope
        if artifact.feature_specs[index].feature_type == "continuous"
    )
    if artifact.schema_version == "v3" and (
        approximation_domains is not None or retained_continuous
    ):
        compiled = compile_spflow_model_to_mio(
            compilation_model,
            fitted_artifact=artifact,
            approximation_domains=approximation_domains or (),
        )
    else:
        if approximation_domains is not None:
            raise ValueError(
                "physical approximation domains require refitting the source artifact "
                "as schema v3 with declared domains"
            )
        compiled = compile_spflow_model_to_mio(
            compilation_model,
            feature_schema=artifact.feature_specs,
        )
    return build_current_spflow_planning_payload(
        compiled,
        approximation_metadata=artifact.approximation_metadata,
        decision_features=problem_definition.decision_features,
        event_target_name=str(artifact.target_definition["event_target_name"]),
        chance_limit_epsilon=problem_definition.chance_limit_epsilon,
        shortfall_threshold=problem_definition.shortfall_threshold,
        payload_locator=artifact.payload_locator,
    )


def _approximation_domains_from_contract(
    approximation_contract: Mapping[str, object],
) -> tuple[TPMApproximationDomain, ...] | None:
    if "approximation_domains" not in approximation_contract:
        return None
    raw_domains = approximation_contract["approximation_domains"]
    if isinstance(raw_domains, Mapping) or isinstance(raw_domains, (str, bytes)):
        raise TypeError("approximation_contract.approximation_domains must be a sequence")
    if not isinstance(raw_domains, Sequence):
        raise TypeError("approximation_contract.approximation_domains must be a sequence")
    domains: list[TPMApproximationDomain] = []
    for index, raw_domain in enumerate(raw_domains):
        if isinstance(raw_domain, TPMApproximationDomain):
            domains.append(raw_domain)
        elif isinstance(raw_domain, Mapping):
            domains.append(TPMApproximationDomain.from_dict(raw_domain))
        else:
            raise TypeError(
                "approximation_contract.approximation_domains entries must be "
                f"TPMApproximationDomain records or mappings; found index {index}"
            )
    return tuple(domains)


def _normalize_solver_configuration(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("solver_configuration must be a mapping")

    backend_name = str(value.get("backend_name", "pyomo"))
    if backend_name not in SUPPORTED_PLANNING_BACKENDS:
        raise ValueError(
            "solver_configuration.backend_name must be one of "
            f"{SUPPORTED_PLANNING_BACKENDS!r}"
        )

    solver_name = str(value.get("solver_name", DEFAULT_SOLVER_NAME))
    numeric_tolerance = _positive_float(
        value.get("numeric_tolerance", DEFAULT_SOLVER_NUMERIC_TOLERANCE),
        field_name="solver_configuration.numeric_tolerance",
    )

    random_seed = value.get("random_seed", DEFAULT_SOLVER_RANDOM_SEED)
    if random_seed is not None:
        if isinstance(random_seed, bool) or not isinstance(random_seed, int):
            raise ValueError("solver_configuration.random_seed must be an int or null")
        random_seed = int(random_seed)

    threads = value.get("threads", DEFAULT_SOLVER_THREADS)
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError("solver_configuration.threads must be a positive integer")
    threads = int(threads)

    time_limit_seconds = value.get(
        "time_limit_seconds",
        DEFAULT_SOLVER_TIME_LIMIT_SECONDS,
    )
    if time_limit_seconds is not None:
        time_limit_seconds = _positive_float(
            time_limit_seconds,
            field_name="solver_configuration.time_limit_seconds",
        )

    solver_backend_required = value.get("solver_backend_required", True)
    if not isinstance(solver_backend_required, bool):
        raise TypeError("solver_configuration.solver_backend_required must be a bool")

    solver_execution_optional = value.get(
        "solver_execution_optional",
        solver_name != DEFAULT_SOLVER_NAME,
    )
    if not isinstance(solver_execution_optional, bool):
        raise TypeError("solver_configuration.solver_execution_optional must be a bool")

    normalized = {
        "backend_name": backend_name,
        "solver_name": solver_name,
        "solver_backend_required": solver_backend_required,
        "solver_execution_optional": solver_execution_optional,
        "numeric_tolerance": numeric_tolerance,
        "random_seed": random_seed,
        "threads": threads,
        "time_limit_seconds": time_limit_seconds,
    }
    for key, inner_value in value.items():
        key_text = str(key)
        if key_text not in normalized:
            normalized[key_text] = inner_value
    return normalized


def _normalize_approximation_contract(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("approximation_contract must be a mapping")

    approximation_kind = str(value.get("approximation_kind", "piecewise"))
    if approximation_kind != "piecewise":
        raise ValueError(
            "approximation_contract.approximation_kind must be 'piecewise'"
        )

    normalized = {"approximation_kind": approximation_kind}
    for key, inner_value in value.items():
        key_text = str(key)
        if key_text == "approximation_kind":
            continue
        normalized[key_text] = inner_value
    return normalized


def _validate_approximation_contract(
    approximation_contract: Mapping[str, object],
    *,
    piecewise_terms: PiecewisePlanningTerms,
) -> None:
    if (
        str(approximation_contract.get("approximation_kind", "piecewise"))
        != piecewise_terms.approximation_kind
    ):
        raise ValueError(
            "approximation_contract.approximation_kind must match the TPM artifact "
            "approximation metadata"
        )

    if "leaf_encoding_mode" in approximation_contract and str(
        approximation_contract["leaf_encoding_mode"]
    ) != piecewise_terms.leaf_encoding_mode:
        raise ValueError(
            "approximation_contract.leaf_encoding_mode must match the TPM artifact "
            "approximation metadata"
        )

    if "sum_encoding_mode" in approximation_contract and str(
        approximation_contract["sum_encoding_mode"]
    ) != piecewise_terms.sum_encoding_mode:
        raise ValueError(
            "approximation_contract.sum_encoding_mode must match the TPM artifact "
            "approximation metadata"
        )


def _positive_float(value: object, *, field_name: str) -> float:
    normalized = _real_number(value, field_name=field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _real_number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a real number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized
