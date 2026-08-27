"""Backend-free model handoff and indexing for robust FCR formulations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any

from .robust_fcr_bidding import (
    RobustFCRBiddingProblem,
    RobustFCRFormulationProfile,
    RobustFCRValidationError,
    _deep_freeze,
    _finite,
    _integer,
    _non_empty,
    _sha256,
)


SOURCE_EQUATION_VERSION = "robust-storage-bidding-non-intraday-milp-v1"
SOURCE_EQUATION_REFERENCES = MappingProxyType(
    {
        "variables": "baselines/robust_storage_bidding/code/02_model.jl:86-135",
        "power_headroom": (
            "baselines/robust_storage_bidding/code/02_model.jl:170-174"
        ),
        "robust_stored_energy": (
            "baselines/robust_storage_bidding/code/02_model.jl:183-188"
        ),
        "efficiency_epigraphs": (
            "baselines/robust_storage_bidding/code/02_model.jl:191-197"
        ),
        "upper_counterpart": (
            "baselines/robust_storage_bidding/code/02_model.jl:199-219"
        ),
        "exact_bilinear": (
            "baselines/robust_storage_bidding/code/02_model.jl:220-224"
        ),
        "restriction_tightening": (
            "baselines/robust_storage_bidding/code/02_model.jl:225-230"
        ),
        "objective_terminal": (
            "baselines/robust_storage_bidding/code/02_model.jl:252-263"
        ),
        "horizon_budget": (
            "baselines/robust_storage_bidding/code/02_model.jl:293-305"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class NormalizedRobustFCRIndexSets:
    """Zero-based deterministic indices used by private model assembly."""

    planning_indices: tuple[int, ...]
    energy_indices: tuple[int, ...]
    fcr_indices: tuple[int, ...]
    planning_to_energy: tuple[int, ...]
    planning_to_fcr: tuple[int, ...]
    triangular_pairs: tuple[tuple[int, int], ...]
    strict_triangular_pairs: tuple[tuple[int, int], ...]

    @property
    def planning_interval_count(self) -> int:
        return len(self.planning_indices)

    def semantic_counts(self) -> dict[str, int]:
        return {
            "planning_intervals": len(self.planning_indices),
            "energy_intervals": len(self.energy_indices),
            "fcr_intervals": len(self.fcr_indices),
            "triangular_pairs": len(self.triangular_pairs),
            "strict_triangular_pairs": len(self.strict_triangular_pairs),
        }


def build_normalized_index_sets(
    planning_interval_count: int,
    *,
    planning_intervals_per_energy_interval: int = 4,
    planning_intervals_per_fcr_block: int = 16,
) -> NormalizedRobustFCRIndexSets:
    count = _integer(
        planning_interval_count,
        field_name="planning_interval_count",
        minimum=1,
    )
    energy_stride = _integer(
        planning_intervals_per_energy_interval,
        field_name="planning_intervals_per_energy_interval",
        minimum=1,
    )
    fcr_stride = _integer(
        planning_intervals_per_fcr_block,
        field_name="planning_intervals_per_fcr_block",
        minimum=1,
    )
    planning = tuple(range(count))
    energy_count = math.ceil(count / energy_stride)
    fcr_count = math.ceil(count / fcr_stride)
    return NormalizedRobustFCRIndexSets(
        planning_indices=planning,
        energy_indices=tuple(range(energy_count)),
        fcr_indices=tuple(range(fcr_count)),
        planning_to_energy=tuple(index // energy_stride for index in planning),
        planning_to_fcr=tuple(index // fcr_stride for index in planning),
        triangular_pairs=tuple(
            (outer, inner)
            for outer in planning
            for inner in range(outer + 1)
        ),
        strict_triangular_pairs=tuple(
            (outer, inner) for outer in planning for inner in range(outer)
        ),
    )


def model_cardinality_basis(index_sets: NormalizedRobustFCRIndexSets) -> dict[str, int]:
    """Return stable semantic index counts before backend assembly."""

    return index_sets.semantic_counts()


def model_cardinality_metadata(
    index_sets: NormalizedRobustFCRIndexSets,
    formulation_kind: str,
) -> dict[str, int]:
    """Return exact linear/quadratic structure counts without building Pyomo."""

    if not isinstance(index_sets, NormalizedRobustFCRIndexSets):
        raise RobustFCRValidationError(
            "index_sets must be NormalizedRobustFCRIndexSets"
        )
    if formulation_kind not in {"restriction", "relaxation", "exact"}:
        raise RobustFCRValidationError(
            "formulation_kind must be restriction, relaxation, or exact"
        )
    count = index_sets.planning_interval_count
    strict_count = max(count - 1, 0)
    triangular = len(index_sets.triangular_pairs)
    strict_triangular = len(index_sets.strict_triangular_pairs)
    common_binary_variables = 2 * strict_count
    formulation_binary_variables = (
        strict_count if formulation_kind == "restriction" else 0
    )
    lambda_triangular_variables = 2 * triangular
    common_strict_triangular_constraints = 4 * strict_triangular
    formulation_strict_triangular_constraints = {
        "restriction": 2 * strict_triangular,
        "relaxation": 0,
        "exact": strict_triangular,
    }[formulation_kind]
    formulation_linear_constraints = (
        2 * strict_count if formulation_kind == "restriction" else 0
    )
    variables = (
        len(index_sets.energy_indices)
        + len(index_sets.fcr_indices)
        + 9 * count
        + lambda_triangular_variables
        + formulation_binary_variables
    )
    common_constraints = (
        15 * count
        + triangular
        + common_strict_triangular_constraints
        - 3
    )
    active_constraints = (
        common_constraints
        + formulation_linear_constraints
        + formulation_strict_triangular_constraints
    )
    return {
        **model_cardinality_basis(index_sets),
        "common_binary_variables": common_binary_variables,
        "formulation_specific_binary_variables": formulation_binary_variables,
        "lambda_triangular_variable_entries": lambda_triangular_variables,
        "common_strict_triangular_constraint_entries": (
            common_strict_triangular_constraints
        ),
        "formulation_specific_linear_constraint_entries": (
            formulation_linear_constraints
        ),
        "formulation_specific_strict_triangular_constraint_entries": (
            formulation_strict_triangular_constraints
        ),
        "quadratic_structure_entries": (
            lambda_triangular_variables
            + common_strict_triangular_constraints
            + formulation_strict_triangular_constraints
        ),
        "quadratic_index_power": 2,
        "variables": variables,
        "binaries": common_binary_variables + formulation_binary_variables,
        "active_constraints": active_constraints,
    }


def build_model_input(problem: RobustFCRBiddingProblem) -> RobustFCRModelInput:
    """Translate one validated public problem into source-frame numeric data."""

    if not isinstance(problem, RobustFCRBiddingProblem):
        raise RobustFCRValidationError(
            "problem must be a validated RobustFCRBiddingProblem"
        )
    index_sets = build_normalized_index_sets(96)
    battery = problem.battery
    return RobustFCRModelInput(
        problem_fingerprint=problem.problem_fingerprint,
        planning_resolution_hours=0.25,
        index_sets=index_sets,
        payload={
            "source_minimum_power_kw": battery.source_minimum_power_kw,
            "source_maximum_power_kw": battery.source_maximum_power_kw,
            "minimum_stored_energy_kwh": battery.minimum_stored_energy_kwh,
            "maximum_stored_energy_kwh": battery.maximum_stored_energy_kwh,
            "initial_stored_energy_kwh": battery.initial_stored_energy_kwh,
            "charge_efficiency": battery.charge_efficiency,
            "discharge_efficiency": battery.discharge_efficiency,
            "efficiency_delta": 1.0 / battery.discharge_efficiency
            - battery.charge_efficiency,
            "horizon_activation_budget_hours": (
                problem.uncertainty.horizon_wide.horizon_activation_budget_hours
            ),
            "terminal_minimum_stored_energy_kwh": (
                problem.terminal_rule.minimum_terminal_stored_energy_kwh
            ),
            "allow_penalized_terminal_shortfall": (
                problem.terminal_rule.allow_penalized_shortfall
            ),
            "shortfall_penalty_eur_per_kwh": (
                problem.terminal_rule.shortfall_penalty_eur_per_kwh
            ),
            "day_ahead_energy_prices_eur_per_kwh": (
                problem.prices.day_ahead_energy_prices_eur_per_kwh
            ),
            "fcr_capacity_prices_eur_per_kw_block": (
                problem.prices.fcr_capacity_prices_eur_per_kw_block
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class RobustFCRModelInput:
    """Immutable backend-neutral values handed to private model assembly."""

    problem_fingerprint: str
    planning_resolution_hours: float
    index_sets: NormalizedRobustFCRIndexSets
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "problem_fingerprint",
            _sha256(self.problem_fingerprint, field_name="problem_fingerprint"),
        )
        resolution = _finite(
            self.planning_resolution_hours,
            field_name="planning_resolution_hours",
        )
        if resolution <= 0.0:
            raise RobustFCRValidationError(
                "planning_resolution_hours must be greater than zero"
            )
        object.__setattr__(self, "planning_resolution_hours", resolution)
        if not isinstance(self.index_sets, NormalizedRobustFCRIndexSets):
            raise RobustFCRValidationError(
                "index_sets must be NormalizedRobustFCRIndexSets"
            )
        object.__setattr__(
            self,
            "payload",
            _deep_freeze(self.payload, field_name="model_input.payload"),
        )


@dataclass(frozen=True, slots=True)
class RobustFCRModelHandoff:
    """Semantic identity and counts associated with one assembled model."""

    formulation_kind: str
    equation_version: str
    model_input: RobustFCRModelInput
    cardinality: Mapping[str, int]

    def __post_init__(self) -> None:
        if self.formulation_kind not in {"restriction", "relaxation", "exact"}:
            raise RobustFCRValidationError(
                "formulation_kind must be restriction, relaxation, or exact"
            )
        object.__setattr__(
            self,
            "equation_version",
            _non_empty(self.equation_version, field_name="equation_version"),
        )
        normalized: dict[str, int] = {}
        for name, value in self.cardinality.items():
            normalized[_non_empty(name, field_name="cardinality key")] = _integer(
                value,
                field_name=f"cardinality.{name}",
                minimum=0,
            )
        object.__setattr__(
            self,
            "cardinality",
            MappingProxyType(dict(sorted(normalized.items()))),
        )


@dataclass(frozen=True, slots=True)
class AssembledRobustFCRModel:
    """Private solver handoff retaining opaque backend handles."""

    model: Any
    handoff: RobustFCRModelHandoff
    variable_handles: Mapping[str, Any]
    constraint_handles: Mapping[str, Any]


def _add_constraint_family(model: Any, pyo: Any, name: str) -> Any:
    component = pyo.ConstraintList()
    model.add_component(name, component)
    return component


def assemble_robust_fcr_model(
    problem: RobustFCRBiddingProblem,
    profile: RobustFCRFormulationProfile,
    *,
    pyomo_environ: Any,
) -> AssembledRobustFCRModel:
    """Assemble the preserved non-intraday formulation through injected Pyomo."""

    if not isinstance(profile, RobustFCRFormulationProfile):
        raise RobustFCRValidationError(
            "profile must be RobustFCRFormulationProfile"
        )
    data = build_model_input(problem)
    indices = data.index_sets
    values = data.payload
    pyo = pyomo_environ
    model = pyo.ConcreteModel(name=f"robust_fcr_{profile.kind}")
    model.K = pyo.Set(initialize=indices.planning_indices, ordered=True)
    model.H = pyo.Set(initialize=indices.energy_indices, ordered=True)
    model.B = pyo.Set(initialize=indices.fcr_indices, ordered=True)
    model.K_STRICT = pyo.Set(
        initialize=indices.planning_indices[:-1],
        ordered=True,
    )
    model.TRI = pyo.Set(
        dimen=2,
        initialize=indices.triangular_pairs,
        ordered=True,
    )
    model.STRICT_TRI = pyo.Set(
        dimen=2,
        initialize=indices.strict_triangular_pairs,
        ordered=True,
    )

    x_min = float(values["source_minimum_power_kw"])
    x_max = float(values["source_maximum_power_kw"])
    y_min = float(values["minimum_stored_energy_kwh"])
    y_max = float(values["maximum_stored_energy_kwh"])
    y_initial = float(values["initial_stored_energy_kwh"])
    eta_c = float(values["charge_efficiency"])
    eta_d = float(values["discharge_efficiency"])
    delta_eta = float(values["efficiency_delta"])
    gamma_horizon = float(values["horizon_activation_budget_hours"])
    terminal_minimum = float(values["terminal_minimum_stored_energy_kwh"])
    penalty = float(values["shortfall_penalty_eur_per_kwh"])
    delta_t = data.planning_resolution_hours
    energy_prices = tuple(values["day_ahead_energy_prices_eur_per_kwh"])
    fcr_prices = tuple(values["fcr_capacity_prices_eur_per_kw_block"])
    e_of = indices.planning_to_energy
    b_of = indices.planning_to_fcr

    model.x0 = pyo.Var(model.H, domain=pyo.Reals)
    model.xr = pyo.Var(model.B, domain=pyo.NonNegativeReals)
    model.xa = pyo.Var(model.K, domain=pyo.Reals)
    for variable in model.xa.values():
        variable.fix(0.0)
    model.symin = pyo.Var(model.K, domain=pyo.NonNegativeReals)
    model.symax = pyo.Var(model.K, domain=pyo.NonNegativeReals)
    model.syK = pyo.Var((0, 1), domain=pyo.NonNegativeReals)
    if not bool(values["allow_penalized_terminal_shortfall"]):
        model.syK[1].fix(0.0)
    model.alpha = pyo.Var(model.K, domain=pyo.Reals)
    model.beta = pyo.Var(model.K, domain=pyo.Reals)
    model.lambda_l = pyo.Var(model.K, domain=pyo.NonNegativeReals)
    model.lambda_h = pyo.Var(
        model.K,
        bounds=(0.0, (x_max - x_min) / eta_d),
    )
    model.Lambda_l = pyo.Var(model.TRI, domain=pyo.NonNegativeReals)
    model.Lambda_h = pyo.Var(model.TRI, domain=pyo.Reals)
    model.u1 = pyo.Var(model.K_STRICT, domain=pyo.Binary)
    model.u2 = pyo.Var(model.K_STRICT, domain=pyo.Binary)
    if profile.kind == "restriction":
        model.v_res = pyo.Var(model.K_STRICT, domain=pyo.Binary)

    constraints: dict[str, Any] = {}
    for name in (
        "pointwise_charge_headroom",
        "pointwise_discharge_headroom",
        "lower_stored_energy",
        "lower_coupling",
        "upper_stored_energy",
        "alpha_charge_epigraph",
        "alpha_discharge_epigraph",
        "beta_charge_epigraph",
        "beta_discharge_epigraph",
        "lambda_h_diagonal_discharge",
        "lambda_h_diagonal_activation",
        "lambda_h_diagonal_nonnegative",
        "u1_upper",
        "u1_lower",
        "u2_lower",
        "u2_upper",
        "lambda_h_offdiag_discharge_activation",
        "lambda_h_offdiag_discharge_baseline",
        "lambda_h_offdiag_charge_activation",
        "lambda_h_offdiag_charge_baseline",
        "terminal_stored_energy",
    ):
        constraints[name] = _add_constraint_family(model, pyo, f"c_{name}")

    for k in indices.planning_indices:
        x0 = model.x0[e_of[k]]
        xr = model.xr[b_of[k]]
        constraints["pointwise_charge_headroom"].add(x0 - xr >= x_min)
        constraints["pointwise_discharge_headroom"].add(x0 + xr <= x_max)
        constraints["lower_stored_energy"].add(
            y_initial
            - gamma_horizon * model.lambda_l[k]
            - delta_t
            * sum(model.alpha[l] + model.Lambda_l[k, l] for l in range(k + 1))
            >= y_min
        )
        constraints["upper_stored_energy"].add(
            y_initial
            + gamma_horizon * model.lambda_h[k]
            + delta_t * sum(model.Lambda_h[k, l] for l in range(k + 1))
            <= y_max
        )
        for l in range(k + 1):
            constraints["lower_coupling"].add(
                model.Lambda_l[k, l]
                + model.lambda_l[k]
                + model.alpha[l]
                - model.beta[l]
                >= 0.0
            )
        constraints["alpha_charge_epigraph"].add(model.alpha[k] >= eta_c * x0)
        constraints["alpha_discharge_epigraph"].add(model.alpha[k] >= x0 / eta_d)
        constraints["beta_charge_epigraph"].add(
            model.beta[k] >= eta_c * (x0 + xr)
        )
        constraints["beta_discharge_epigraph"].add(
            model.beta[k] >= (x0 + xr) / eta_d
        )
        constraints["lambda_h_diagonal_discharge"].add(
            model.Lambda_h[k, k] >= -eta_c * x0
        )
        constraints["lambda_h_diagonal_activation"].add(
            model.Lambda_h[k, k] >= eta_c * (xr - x0) - model.lambda_h[k]
        )
        constraints["lambda_h_diagonal_nonnegative"].add(
            model.Lambda_h[k, k] >= 0.0
        )

    for l in indices.planning_indices[:-1]:
        x0 = model.x0[e_of[l]]
        xr = model.xr[b_of[l]]
        constraints["u1_upper"].add(x0 - xr <= model.u1[l] * x_max)
        constraints["u1_lower"].add(
            x0 - xr >= (1.0 - model.u1[l]) * x_min
        )
        constraints["u2_lower"].add(x0 >= model.u2[l] * x_min)
        constraints["u2_upper"].add(x0 <= (1.0 - model.u2[l]) * x_max)

    for k, l in indices.strict_triangular_pairs:
        x0 = model.x0[e_of[l]]
        xr = model.xr[b_of[l]]
        constraints["lambda_h_offdiag_discharge_activation"].add(
            model.Lambda_h[k, l]
            >= (xr - x0) / eta_d
            - model.lambda_h[k]
            + (1.0 - model.u1[l]) * delta_eta * x_min
        )
        constraints["lambda_h_offdiag_discharge_baseline"].add(
            model.Lambda_h[k, l]
            >= -x0 / eta_d + model.u2[l] * delta_eta * x_min
        )
        constraints["lambda_h_offdiag_charge_activation"].add(
            model.Lambda_h[k, l]
            >= eta_c * (xr - x0)
            - model.lambda_h[k]
            - model.u1[l] * delta_eta * x_max
        )
        constraints["lambda_h_offdiag_charge_baseline"].add(
            model.Lambda_h[k, l]
            >= -eta_c * x0 - (1.0 - model.u2[l]) * delta_eta * x_max
        )

    if profile.kind == "restriction":
        for name in (
            "restriction_classification_lower",
            "restriction_classification_upper",
            "restriction_tightening_charge",
            "restriction_tightening_discharge",
        ):
            constraints[name] = _add_constraint_family(model, pyo, f"c_{name}")
        for l in indices.planning_indices[:-1]:
            x0 = model.x0[e_of[l]]
            xr = model.xr[b_of[l]]
            classification = (
                xr - (1.0 - eta_c * eta_d) * x0 - eta_d * model.lambda_h[l]
            )
            constraints["restriction_classification_lower"].add(
                classification
                >= -((2.0 - eta_c * eta_d) * x_max - x_min)
                * (1.0 - model.v_res[l])
            )
            constraints["restriction_classification_upper"].add(
                classification <= model.v_res[l] * (eta_c * eta_d * x_max - x_min)
            )
        for k, l in indices.strict_triangular_pairs:
            x0 = model.x0[e_of[l]]
            xr = model.xr[b_of[l]]
            constraints["restriction_tightening_charge"].add(
                model.Lambda_h[k, l]
                >= -eta_c * x0
                - (model.u1[l] + 1.0 - model.v_res[l]) * delta_eta * x_max
            )
            constraints["restriction_tightening_discharge"].add(
                model.Lambda_h[k, l]
                >= (xr - x0) / eta_d
                - model.lambda_h[k]
                + (model.u2[l] + model.v_res[l]) * delta_eta * x_min
            )
    elif profile.kind == "exact":
        constraints["exact_bilinear"] = _add_constraint_family(
            model,
            pyo,
            "c_exact_bilinear",
        )
        for k, l in indices.strict_triangular_pairs:
            x0 = model.x0[e_of[l]]
            xr = model.xr[b_of[l]]
            constraints["exact_bilinear"].add(
                model.Lambda_h[k, l] * xr + model.lambda_h[k] * x0
                >= model.u2[l] * x_min * (x_max - x_min) / eta_d
                - model.u1[l] * x_max**2 / (4.0 * eta_d)
            )

    constraints["terminal_stored_energy"].add(
        y_initial - delta_t * sum(model.alpha[k] for k in indices.planning_indices)
        >= terminal_minimum - model.syK[1]
    )

    model.objective = pyo.Objective(
        expr=(
            delta_t
            * sum(
                energy_prices[e_of[k]] * model.x0[e_of[k]]
                for k in indices.planning_indices
            )
            + sum(fcr_prices[b] * model.xr[b] for b in indices.fcr_indices)
            - penalty
            * (
                sum(model.syK[index] for index in (0, 1))
                + sum(
                    model.symin[k] + model.symax[k]
                    for k in indices.planning_indices
                )
            )
        ),
        sense=pyo.maximize,
    )

    variables = {
        name: getattr(model, name)
        for name in (
            "x0",
            "xr",
            "xa",
            "symin",
            "symax",
            "syK",
            "alpha",
            "beta",
            "lambda_l",
            "lambda_h",
            "Lambda_l",
            "Lambda_h",
            "u1",
            "u2",
        )
    }
    if profile.kind == "restriction":
        variables["v_res"] = model.v_res
    variable_count = sum(1 for _ in model.component_data_objects(pyo.Var, active=True))
    binary_count = sum(
        1
        for variable in model.component_data_objects(pyo.Var, active=True)
        if variable.is_binary()
    )
    constraint_count = sum(
        1 for _ in model.component_data_objects(pyo.Constraint, active=True)
    )
    cardinality = model_cardinality_metadata(indices, profile.kind)
    observed = {
        "variables": variable_count,
        "binaries": binary_count,
        "active_constraints": constraint_count,
    }
    expected = {name: cardinality[name] for name in observed}
    if observed != expected:  # pragma: no cover - guards translation drift
        raise RobustFCRValidationError(
            f"assembled model cardinality mismatch: expected {expected}, observed {observed}"
        )
    handoff = RobustFCRModelHandoff(
        formulation_kind=profile.kind,
        equation_version=profile.equation_version,
        model_input=data,
        cardinality=cardinality,
    )
    return AssembledRobustFCRModel(
        model=model,
        handoff=handoff,
        variable_handles=MappingProxyType(variables),
        constraint_handles=MappingProxyType(constraints),
    )


__all__ = [
    "AssembledRobustFCRModel",
    "NormalizedRobustFCRIndexSets",
    "RobustFCRModelHandoff",
    "RobustFCRModelInput",
    "SOURCE_EQUATION_REFERENCES",
    "SOURCE_EQUATION_VERSION",
    "build_normalized_index_sets",
    "build_model_input",
    "assemble_robust_fcr_model",
    "model_cardinality_basis",
    "model_cardinality_metadata",
]
