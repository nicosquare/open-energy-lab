"""Backend-free model handoff and indexing for robust FCR formulations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any

from .robust_fcr_bidding import (
    DEPLOYABILITY_THRESHOLD,
    RobustFCRBiddingProblem,
    RobustFCRFormulationProfile,
    RobustFCRValidationError,
    _deep_freeze,
    _fingerprint,
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
class RobustFCRReferenceIntervalAudit:
    """Joint audit of one independently checked witness against closed boxes."""

    field_residuals: Mapping[str, float]
    maximum_interval_residual: float
    maximum_modeled_slack: float
    maximum_independent_residual: float
    tolerance: float
    passes: bool
    audit_fingerprint: str = ""

    def __post_init__(self) -> None:
        residuals: dict[str, float] = {}
        for name, value in self.field_residuals.items():
            normalized_name = _non_empty(name, field_name="reference interval field")
            normalized = _finite(
                value, field_name=f"reference interval residual {normalized_name}"
            )
            if normalized < 0.0:
                raise RobustFCRValidationError(
                    "reference interval residuals must be non-negative"
                )
            residuals[normalized_name] = normalized
        maximum_interval = _finite(
            self.maximum_interval_residual,
            field_name="maximum_interval_residual",
        )
        maximum_slack = _finite(
            self.maximum_modeled_slack,
            field_name="maximum_modeled_slack",
        )
        maximum_independent = _finite(
            self.maximum_independent_residual,
            field_name="maximum_independent_residual",
        )
        tolerance = _finite(self.tolerance, field_name="reference audit tolerance")
        if min(maximum_interval, maximum_slack, maximum_independent, tolerance) < 0.0:
            raise RobustFCRValidationError(
                "reference interval audit values must be non-negative"
            )
        expected_maximum = max(residuals.values(), default=0.0)
        if abs(maximum_interval - expected_maximum) > 1e-12:
            raise RobustFCRValidationError(
                "maximum interval residual does not reconcile field residuals"
            )
        expected_passes = max(
            maximum_interval,
            maximum_slack,
            maximum_independent,
        ) <= tolerance
        if self.passes != expected_passes:
            raise RobustFCRValidationError(
                "reference interval audit status does not reconcile evidence"
            )
        object.__setattr__(
            self,
            "field_residuals",
            MappingProxyType(dict(sorted(residuals.items()))),
        )
        object.__setattr__(self, "maximum_interval_residual", maximum_interval)
        object.__setattr__(self, "maximum_modeled_slack", maximum_slack)
        object.__setattr__(self, "maximum_independent_residual", maximum_independent)
        object.__setattr__(self, "tolerance", tolerance)
        payload = self._payload()
        expected_fingerprint = _fingerprint(payload)
        if self.audit_fingerprint and self.audit_fingerprint != expected_fingerprint:
            raise RobustFCRValidationError(
                "reference interval audit fingerprint mismatch"
            )
        object.__setattr__(self, "audit_fingerprint", expected_fingerprint)

    def _payload(self) -> dict[str, object]:
        return {
            "field_residuals": dict(self.field_residuals),
            "maximum_interval_residual": self.maximum_interval_residual,
            "maximum_modeled_slack": self.maximum_modeled_slack,
            "maximum_independent_residual": self.maximum_independent_residual,
            "tolerance": self.tolerance,
            "passes": self.passes,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "audit_fingerprint": self.audit_fingerprint}


def audit_closed_reference_witness(
    *,
    field_values: Mapping[str, float],
    closed_intervals: Mapping[str, tuple[float, float]],
    maximum_modeled_slack: float,
    maximum_independent_residual: float,
    tolerance: float,
) -> RobustFCRReferenceIntervalAudit:
    """Audit one common witness against decisions, objective, and state boxes.

    The helper deliberately consumes the independent equation-family residual
    and modeled-slack evidence produced by Feature 013.  It adds only interval
    membership checks and therefore does not create a second formulation or
    feasibility model.
    """

    if set(field_values) != set(closed_intervals):
        raise RobustFCRValidationError(
            "reference witness fields and closed intervals must match exactly"
        )
    residuals: dict[str, float] = {}
    for name in sorted(field_values):
        value = _finite(field_values[name], field_name=f"field_values.{name}")
        raw_interval = closed_intervals[name]
        if len(raw_interval) != 2:
            raise RobustFCRValidationError(
                f"closed_intervals.{name} must contain two endpoints"
            )
        lower = _finite(raw_interval[0], field_name=f"closed_intervals.{name}.lower")
        upper = _finite(raw_interval[1], field_name=f"closed_intervals.{name}.upper")
        if lower > upper:
            raise RobustFCRValidationError(
                f"closed_intervals.{name} lower endpoint exceeds upper"
            )
        residuals[name] = max(lower - value, value - upper, 0.0)
    maximum_interval = max(residuals.values(), default=0.0)
    maximum_slack = _finite(
        maximum_modeled_slack, field_name="maximum_modeled_slack"
    )
    maximum_independent = _finite(
        maximum_independent_residual,
        field_name="maximum_independent_residual",
    )
    normalized_tolerance = _finite(tolerance, field_name="tolerance")
    passes = max(
        maximum_interval,
        maximum_slack,
        maximum_independent,
    ) <= normalized_tolerance
    return RobustFCRReferenceIntervalAudit(
        field_residuals=residuals,
        maximum_interval_residual=maximum_interval,
        maximum_modeled_slack=maximum_slack,
        maximum_independent_residual=maximum_independent,
        tolerance=normalized_tolerance,
        passes=passes,
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
    battery = problem.battery
    return build_normalized_model_input(
        problem_fingerprint=problem.problem_fingerprint,
        planning_resolution_hours=0.25,
        planning_interval_count=96,
        planning_intervals_per_energy_interval=4,
        planning_intervals_per_fcr_block=16,
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


def build_normalized_model_input(
    *,
    problem_fingerprint: str,
    planning_resolution_hours: float,
    planning_interval_count: int,
    planning_intervals_per_energy_interval: int,
    planning_intervals_per_fcr_block: int,
    payload: Mapping[str, object],
) -> RobustFCRModelInput:
    """Build a backend-neutral normalized frame for daily or rolling assembly."""

    return RobustFCRModelInput(
        problem_fingerprint=problem_fingerprint,
        planning_resolution_hours=planning_resolution_hours,
        index_sets=build_normalized_index_sets(
            planning_interval_count,
            planning_intervals_per_energy_interval=(
                planning_intervals_per_energy_interval
            ),
            planning_intervals_per_fcr_block=(
                planning_intervals_per_fcr_block
            ),
        ),
        payload=payload,
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
        if self.formulation_kind not in {
            "restriction",
            "relaxation",
            "exact",
            "arbitrage_only",
        }:
            raise RobustFCRValidationError(
                "formulation_kind must be restriction, relaxation, exact, or arbitrage_only"
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

    if not isinstance(problem, RobustFCRBiddingProblem):
        raise RobustFCRValidationError(
            "problem must be a validated RobustFCRBiddingProblem"
        )
    return assemble_normalized_robust_fcr_model(
        build_model_input(problem),
        profile,
        pyomo_environ=pyomo_environ,
    )


def assemble_normalized_robust_fcr_model(
    data: RobustFCRModelInput,
    profile: RobustFCRFormulationProfile,
    *,
    pyomo_environ: Any,
) -> AssembledRobustFCRModel:
    """Assemble one validated normalized frame through injected Pyomo."""

    if not isinstance(data, RobustFCRModelInput):
        raise RobustFCRValidationError(
            "data must be a validated RobustFCRModelInput"
        )
    if not isinstance(profile, RobustFCRFormulationProfile):
        raise RobustFCRValidationError(
            "profile must be RobustFCRFormulationProfile"
        )
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


def derive_rolling_source_indices(
    bidding_time_local_hour: int,
    *,
    planning_resolution_hours: float = 0.25,
    current_planning_interval_count: int = 96,
    planning_intervals_per_fcr_block: int = 16,
) -> dict[str, tuple[int, ...] | int]:
    """Derive the executable source's signed overlap indices.

    This is the zero-I/O equivalent of ``compute_K̲`` in
    ``baselines/robust_storage_bidding/code/02_model.jl:289-291``.
    """

    if isinstance(bidding_time_local_hour, bool) or not isinstance(
        bidding_time_local_hour, int
    ):
        raise RobustFCRValidationError("bidding_time_local_hour must be an integer")
    resolution = _finite(
        planning_resolution_hours,
        field_name="planning_resolution_hours",
    )
    if resolution <= 0.0:
        raise RobustFCRValidationError("planning resolution must be positive")
    count = _integer(
        current_planning_interval_count,
        field_name="current_planning_interval_count",
        minimum=1,
    )
    fcr_stride = _integer(
        planning_intervals_per_fcr_block,
        field_name="planning_intervals_per_fcr_block",
        minimum=1,
    )
    lower = round((bidding_time_local_hour - 24) / resolution + 1)
    planning = tuple(range(lower, count + 1))
    energy_lower = math.ceil(lower * resolution)
    energy_upper = math.ceil(count * resolution)
    fcr_lower = math.ceil(lower / fcr_stride)
    fcr_upper = math.ceil(count / fcr_stride)
    return {
        "K_lower": lower,
        "planning_indices": planning,
        "energy_indices": tuple(range(energy_lower, energy_upper + 1)),
        "fcr_indices": tuple(range(fcr_lower, fcr_upper + 1)),
        "fixed_energy_indices": tuple(range(energy_lower, 1)),
        "fixed_fcr_indices": tuple(range(fcr_lower, 1)),
        "current_energy_indices": tuple(range(1, energy_upper + 1)),
        "current_fcr_indices": tuple(range(1, fcr_upper + 1)),
    }


def _source_efficiency_consumption(
    source_power_kw: float,
    *,
    charge_efficiency: float,
    discharge_efficiency: float,
) -> float:
    return max(
        charge_efficiency * source_power_kw,
        source_power_kw / discharge_efficiency,
    )


def _allocate_activation_budget(
    segments: list[tuple[float, float]],
    *,
    budget_hours: float,
) -> float:
    """Allocate a duration budget to descending non-negative marginal gains."""

    remaining = max(budget_hours, 0.0)
    total = 0.0
    for marginal_kw, maximum_hours in sorted(
        segments,
        key=lambda item: (-item[0], -item[1]),
    ):
        if remaining <= 0.0:
            break
        used = min(maximum_hours, remaining)
        total += used * max(marginal_kw, 0.0)
        remaining -= used
    return total


def propagate_fixed_tail_robust_bounds(
    *,
    initial_stored_energy_kwh: float,
    source_energy_positive_discharge_kw: tuple[float, ...],
    fcr_capacity_kw: tuple[float, ...],
    charge_efficiency: float,
    discharge_efficiency: float,
    activation_budget_hours: float,
    planning_resolution_hours: float = 0.25,
) -> tuple[float, float]:
    """Return fixed-tail minimum/maximum stored energy at current midnight.

    The calculation expands the accepted 16 hourly and four four-hour values
    into 64 quarter-hours. It applies the same horizon-budget polytope as the
    source's fixed-tail auxiliary solves, using exact piecewise marginal gains
    for charge/discharge efficiency. No realized activation is consulted.
    """

    if len(source_energy_positive_discharge_kw) != 16:
        raise RobustFCRValidationError("fixed tail must contain 16 hourly decisions")
    if len(fcr_capacity_kw) != 4:
        raise RobustFCRValidationError("fixed tail must contain four FCR decisions")
    initial = _finite(
        initial_stored_energy_kwh,
        field_name="initial_stored_energy_kwh",
    )
    eta_c = _finite(charge_efficiency, field_name="charge_efficiency")
    eta_d = _finite(discharge_efficiency, field_name="discharge_efficiency")
    delta_t = _finite(
        planning_resolution_hours,
        field_name="planning_resolution_hours",
    )
    budget = _finite(
        activation_budget_hours,
        field_name="activation_budget_hours",
    )
    if not 0.0 < eta_c <= 1.0 or not 0.0 < eta_d <= 1.0:
        raise RobustFCRValidationError("efficiencies must lie in (0, 1]")
    if delta_t <= 0.0 or budget < 0.0:
        raise RobustFCRValidationError("tail resolution must be positive and budget non-negative")
    powers = tuple(
        _finite(value, field_name="fixed energy decision")
        for value in source_energy_positive_discharge_kw
        for _ in range(4)
    )
    reserves = tuple(
        _finite(value, field_name="fixed FCR decision")
        for value in fcr_capacity_kw
        for _ in range(16)
    )
    baseline_consumption = sum(
        delta_t
        * _source_efficiency_consumption(
            power,
            charge_efficiency=eta_c,
            discharge_efficiency=eta_d,
        )
        for power in powers
    )
    upward_segments: list[tuple[float, float]] = []
    downward_segments: list[tuple[float, float]] = []
    for power, reserve in zip(powers, reserves, strict=True):
        if reserve < 0.0:
            raise RobustFCRValidationError("fixed FCR decisions must be non-negative")
        baseline = _source_efficiency_consumption(
            power,
            charge_efficiency=eta_c,
            discharge_efficiency=eta_d,
        )
        upward = _source_efficiency_consumption(
            power + reserve,
            charge_efficiency=eta_c,
            discharge_efficiency=eta_d,
        )
        upward_segments.append(((upward - baseline), delta_t))
        if reserve == 0.0:
            downward_segments.append((0.0, delta_t))
        elif power <= 0.0:
            downward_segments.append((eta_c * reserve, delta_t))
        elif power >= reserve:
            downward_segments.append((reserve / eta_d, delta_t))
        else:
            crossing_fraction = power / reserve
            downward_segments.append(
                (reserve / eta_d, delta_t * crossing_fraction)
            )
            downward_segments.append(
                (eta_c * reserve, delta_t * (1.0 - crossing_fraction))
            )
    lower = initial - baseline_consumption - _allocate_activation_budget(
        upward_segments,
        budget_hours=budget,
    )
    upper = initial - baseline_consumption + _allocate_activation_budget(
        downward_segments,
        budget_hours=budget,
    )
    return (0.0 if lower == 0.0 else lower, 0.0 if upper == 0.0 else upper)


def assemble_arbitrage_only_model(
    problem: Any,
    *,
    pyomo_environ: Any,
) -> AssembledRobustFCRModel:
    """Assemble the source's exact-zero-FCR hourly arbitrage formulation."""

    pyo = pyomo_environ
    battery = problem.battery
    terminal_rule = problem.terminal_rule
    prices = problem.current_prices.day_ahead_energy_prices_eur_per_kwh
    if len(prices) != 24:
        raise RobustFCRValidationError("arbitrage-only assembly requires 24 prices")
    model = pyo.ConcreteModel(name="robust_fcr_arbitrage_only")
    hours = tuple(range(1, 25))
    strict_hours = tuple(range(1, 24))
    blocks = tuple(range(1, 7))
    model.H = pyo.Set(initialize=hours, ordered=True)
    model.H_STRICT = pyo.Set(initialize=strict_hours, ordered=True)
    model.B = pyo.Set(initialize=blocks, ordered=True)
    model.x0 = pyo.Var(model.H, domain=pyo.Reals)
    model.xr = pyo.Var(model.B, domain=pyo.NonNegativeReals)
    for variable in model.xr.values():
        variable.fix(0.0)
    model.alpha = pyo.Var(model.H, domain=pyo.Reals)
    model.u = pyo.Var(model.H_STRICT, domain=pyo.Binary)
    model.symin = pyo.Var(model.H, domain=pyo.NonNegativeReals)
    model.symax = pyo.Var(model.H, domain=pyo.NonNegativeReals)
    model.syK = pyo.Var((0, 1), domain=pyo.NonNegativeReals)
    for component in (model.symin, model.symax, model.syK):
        for variable in component.values():
            variable.fix(0.0)
    constraints: dict[str, Any] = {}
    for name in (
        "power_lower",
        "power_upper",
        "stored_energy_lower",
        "stored_energy_upper",
        "alpha_charge_lower",
        "alpha_discharge_lower",
        "alpha_charge_upper",
        "alpha_discharge_upper",
        "arbitrage_case_lower",
        "arbitrage_case_upper",
        "terminal_stored_energy",
    ):
        constraints[name] = _add_constraint_family(model, pyo, f"c_{name}")
    x_min = battery.source_minimum_power_kw
    x_max = battery.source_maximum_power_kw
    y_min = battery.minimum_stored_energy_kwh
    y_max = battery.maximum_stored_energy_kwh
    y_initial = battery.initial_stored_energy_kwh
    eta_c = battery.charge_efficiency
    eta_d = battery.discharge_efficiency
    delta_eta = 1.0 / eta_d - eta_c
    for k in hours:
        constraints["power_lower"].add(model.x0[k] >= x_min)
        constraints["power_upper"].add(model.x0[k] <= x_max)
        constraints["stored_energy_lower"].add(
            sum(model.alpha[l] for l in range(1, k + 1))
            <= y_initial - y_min + model.symin[k]
        )
        constraints["stored_energy_upper"].add(
            y_initial
            - (
                eta_c * model.x0[k]
                + sum(model.alpha[l] for l in range(1, k))
            )
            <= y_max + model.symax[k]
        )
        constraints["alpha_charge_lower"].add(model.alpha[k] >= eta_c * model.x0[k])
        constraints["alpha_discharge_lower"].add(model.alpha[k] >= model.x0[k] / eta_d)
    for k in strict_hours:
        constraints["arbitrage_case_lower"].add(
            model.x0[k] >= (1.0 - model.u[k]) * x_min
        )
        constraints["arbitrage_case_upper"].add(
            model.x0[k] <= model.u[k] * x_max
        )
        constraints["alpha_charge_upper"].add(
            model.alpha[k]
            <= eta_c * model.x0[k] + model.u[k] * delta_eta * x_max
        )
        constraints["alpha_discharge_upper"].add(
            model.alpha[k]
            <= model.x0[k] / eta_d
            - (1.0 - model.u[k]) * delta_eta * x_min
        )
    constraints["terminal_stored_energy"].add(
        sum(model.alpha[k] for k in hours)
        <= y_initial
        - terminal_rule.minimum_terminal_stored_energy_kwh
        + model.syK[1]
    )
    model.objective = pyo.Objective(
        expr=(
            sum(prices[k - 1] * model.x0[k] for k in hours)
            - terminal_rule.shortfall_penalty_eur_per_kwh
            * (
                sum(model.syK[index] for index in (0, 1))
                + sum(model.symin[k] + model.symax[k] for k in hours)
            )
        ),
        sense=pyo.maximize,
    )
    model_input = build_normalized_model_input(
        problem_fingerprint=problem.rolling_problem_fingerprint,
        planning_resolution_hours=1.0,
        planning_interval_count=24,
        planning_intervals_per_energy_interval=1,
        planning_intervals_per_fcr_block=4,
        payload={"formulation_kind": "arbitrage_only"},
    )
    variables = {
        "x0": model.x0,
        "xr": model.xr,
        "alpha": model.alpha,
        "u": model.u,
        "symin": model.symin,
        "symax": model.symax,
        "syK": model.syK,
    }
    cardinality = {
        "planning_intervals": 24,
        "energy_intervals": 24,
        "fcr_intervals": 6,
        "variables": sum(1 for _ in model.component_data_objects(pyo.Var, active=True)),
        "binaries": sum(
            1
            for variable in model.component_data_objects(pyo.Var, active=True)
            if variable.is_binary()
        ),
        "active_constraints": sum(
            1 for _ in model.component_data_objects(pyo.Constraint, active=True)
        ),
        "fixed_zero_fcr_decisions": 6,
    }
    handoff = RobustFCRModelHandoff(
        formulation_kind="arbitrage_only",
        equation_version="robust-storage-bidding-no-reg-v1",
        model_input=model_input,
        cardinality=cardinality,
    )
    return AssembledRobustFCRModel(
        model=model,
        handoff=handoff,
        variable_handles=MappingProxyType(variables),
        constraint_handles=MappingProxyType(constraints),
    )


def assemble_rolling_0800_model(
    problem: Any,
    *,
    pyomo_environ: Any,
) -> AssembledRobustFCRModel:
    """Assemble the 40-hour fixed-overlap non-intraday restriction."""

    pyo = pyomo_environ
    indices = derive_rolling_source_indices(8)
    planning_ext = tuple(indices["planning_indices"])
    hours = tuple(indices["energy_indices"])
    blocks = tuple(indices["fcr_indices"])
    current = tuple(range(1, 97))
    current_strict = tuple(range(1, 96))
    triangular = tuple((k, l) for k in current for l in range(1, k + 1))
    strict_triangular = tuple((k, l) for k in current for l in range(1, k))
    e_of = {k: math.ceil(k * 0.25) for k in planning_ext}
    b_of = {k: math.ceil(k / 16) for k in planning_ext}
    model = pyo.ConcreteModel(name="robust_fcr_restriction_rolling_0800")
    model.K_EXT = pyo.Set(initialize=planning_ext, ordered=True)
    model.K = pyo.Set(initialize=current, ordered=True)
    model.K_STRICT = pyo.Set(initialize=current_strict, ordered=True)
    model.H = pyo.Set(initialize=hours, ordered=True)
    model.B = pyo.Set(initialize=blocks, ordered=True)
    model.TRI = pyo.Set(dimen=2, initialize=triangular, ordered=True)
    model.STRICT_TRI = pyo.Set(
        dimen=2,
        initialize=strict_triangular,
        ordered=True,
    )
    battery = problem.battery
    eta_c = battery.charge_efficiency
    eta_d = battery.discharge_efficiency
    delta_eta = 1.0 / eta_d - eta_c
    x_min = battery.source_minimum_power_kw
    x_max = battery.source_maximum_power_kw
    y_min = battery.minimum_stored_energy_kwh
    y_max = battery.maximum_stored_energy_kwh
    gamma = problem.uncertainty.horizon_wide.horizon_activation_budget_hours
    delta_t = 0.25
    terminal = problem.terminal_rule.minimum_terminal_stored_energy_kwh
    penalty = problem.terminal_rule.shortfall_penalty_eur_per_kwh
    model.x0 = pyo.Var(model.H, domain=pyo.Reals)
    model.xr = pyo.Var(model.B, domain=pyo.NonNegativeReals)
    model.xa = pyo.Var(model.K_EXT, domain=pyo.Reals)
    for variable in model.xa.values():
        variable.fix(0.0)
    model.symin = pyo.Var(model.K_EXT, domain=pyo.NonNegativeReals)
    model.symax = pyo.Var(model.K_EXT, domain=pyo.NonNegativeReals)
    model.syK = pyo.Var((0, 1), domain=pyo.NonNegativeReals)
    model.syK[0].fix(0.0)
    if not problem.terminal_rule.allow_penalized_shortfall:
        model.syK[1].fix(0.0)
    model.alpha = pyo.Var(model.K_EXT, domain=pyo.Reals)
    model.beta = pyo.Var(model.K_EXT, domain=pyo.Reals)
    model.lambda_l = pyo.Var(model.K, domain=pyo.NonNegativeReals)
    model.lambda_h = pyo.Var(model.K, bounds=(0.0, (x_max - x_min) / eta_d))
    model.Lambda_l = pyo.Var(model.TRI, domain=pyo.NonNegativeReals)
    model.Lambda_h = pyo.Var(model.TRI, domain=pyo.Reals)
    model.u1 = pyo.Var(model.K_STRICT, domain=pyo.Binary)
    model.u2 = pyo.Var(model.K_STRICT, domain=pyo.Binary)
    model.v_res = pyo.Var(model.K_STRICT, domain=pyo.Binary)
    fixings = problem.accepted_fixings
    for index, value in zip(
        indices["fixed_energy_indices"],
        fixings.source_energy_positive_discharge_kw,
        strict=True,
    ):
        model.x0[index].fix(value)
    for index, value in zip(
        indices["fixed_fcr_indices"],
        fixings.fcr_capacity_kw,
        strict=True,
    ):
        model.xr[index].fix(value)
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
        "restriction_classification_lower",
        "restriction_classification_upper",
        "restriction_tightening_charge",
        "restriction_tightening_discharge",
        "terminal_stored_energy",
    ):
        constraints[name] = _add_constraint_family(model, pyo, f"c_{name}")
    for k in planning_ext:
        x0 = model.x0[e_of[k]]
        xr = model.xr[b_of[k]]
        constraints["alpha_charge_epigraph"].add(model.alpha[k] >= eta_c * x0)
        constraints["alpha_discharge_epigraph"].add(model.alpha[k] >= x0 / eta_d)
        constraints["beta_charge_epigraph"].add(model.beta[k] >= eta_c * (x0 + xr))
        constraints["beta_discharge_epigraph"].add(model.beta[k] >= (x0 + xr) / eta_d)
    for k in current:
        x0 = model.x0[e_of[k]]
        xr = model.xr[b_of[k]]
        constraints["pointwise_charge_headroom"].add(x0 - xr >= x_min)
        constraints["pointwise_discharge_headroom"].add(x0 + xr <= x_max)
        constraints["lower_stored_energy"].add(
            problem.propagated_minimum_stored_energy_kwh
            - gamma * model.lambda_l[k]
            - delta_t * sum(model.alpha[l] + model.Lambda_l[k, l] for l in range(1, k + 1))
            >= y_min
        )
        constraints["upper_stored_energy"].add(
            problem.propagated_maximum_stored_energy_kwh
            + gamma * model.lambda_h[k]
            + delta_t * sum(model.Lambda_h[k, l] for l in range(1, k + 1))
            <= y_max
        )
        for l in range(1, k + 1):
            constraints["lower_coupling"].add(
                model.Lambda_l[k, l] + model.lambda_l[k] + model.alpha[l] - model.beta[l] >= 0.0
            )
        constraints["lambda_h_diagonal_discharge"].add(model.Lambda_h[k, k] >= -eta_c * x0)
        constraints["lambda_h_diagonal_activation"].add(
            model.Lambda_h[k, k] >= eta_c * (xr - x0) - model.lambda_h[k]
        )
        constraints["lambda_h_diagonal_nonnegative"].add(model.Lambda_h[k, k] >= 0.0)
    for l in current_strict:
        x0 = model.x0[e_of[l]]
        xr = model.xr[b_of[l]]
        constraints["u1_upper"].add(x0 - xr <= model.u1[l] * x_max)
        constraints["u1_lower"].add(x0 - xr >= (1.0 - model.u1[l]) * x_min)
        constraints["u2_lower"].add(x0 >= model.u2[l] * x_min)
        constraints["u2_upper"].add(x0 <= (1.0 - model.u2[l]) * x_max)
        classification = xr - (1.0 - eta_c * eta_d) * x0 - eta_d * model.lambda_h[l]
        constraints["restriction_classification_lower"].add(
            classification >= -((2.0 - eta_c * eta_d) * x_max - x_min) * (1.0 - model.v_res[l])
        )
        constraints["restriction_classification_upper"].add(
            classification <= model.v_res[l] * (eta_c * eta_d * x_max - x_min)
        )
    for k, l in strict_triangular:
        x0 = model.x0[e_of[l]]
        xr = model.xr[b_of[l]]
        constraints["lambda_h_offdiag_discharge_activation"].add(
            model.Lambda_h[k, l]
            >= (xr - x0) / eta_d - model.lambda_h[k] + (1.0 - model.u1[l]) * delta_eta * x_min
        )
        constraints["lambda_h_offdiag_discharge_baseline"].add(
            model.Lambda_h[k, l] >= -x0 / eta_d + model.u2[l] * delta_eta * x_min
        )
        constraints["lambda_h_offdiag_charge_activation"].add(
            model.Lambda_h[k, l]
            >= eta_c * (xr - x0) - model.lambda_h[k] - model.u1[l] * delta_eta * x_max
        )
        constraints["lambda_h_offdiag_charge_baseline"].add(
            model.Lambda_h[k, l] >= -eta_c * x0 - (1.0 - model.u2[l]) * delta_eta * x_max
        )
        constraints["restriction_tightening_charge"].add(
            model.Lambda_h[k, l]
            >= -eta_c * x0 - (model.u1[l] + 1.0 - model.v_res[l]) * delta_eta * x_max
        )
        constraints["restriction_tightening_discharge"].add(
            model.Lambda_h[k, l]
            >= (xr - x0) / eta_d - model.lambda_h[k] + (model.u2[l] + model.v_res[l]) * delta_eta * x_min
        )
    constraints["terminal_stored_energy"].add(
        battery.initial_stored_energy_kwh
        - delta_t * sum(model.alpha[k] for k in planning_ext)
        >= terminal - model.syK[1]
    )
    energy_prices = (
        tuple(problem.predecessor_prices.day_ahead_energy_prices_eur_per_kwh[8:])
        + tuple(problem.current_prices.day_ahead_energy_prices_eur_per_kwh)
    )
    fcr_prices = (
        tuple(problem.predecessor_prices.fcr_capacity_prices_eur_per_kw_block[2:])
        + tuple(problem.current_prices.fcr_capacity_prices_eur_per_kw_block)
    )
    energy_price_by_index = dict(zip(hours, energy_prices, strict=True))
    fcr_price_by_index = dict(zip(blocks, fcr_prices, strict=True))
    model.objective = pyo.Objective(
        expr=(
            delta_t * sum(energy_price_by_index[e_of[k]] * model.x0[e_of[k]] for k in planning_ext)
            + sum(fcr_price_by_index[b] * model.xr[b] for b in blocks)
            - penalty
            * (
                sum(model.syK[index] for index in (0, 1))
                + sum(model.symin[k] + model.symax[k] for k in planning_ext)
            )
        ),
        sense=pyo.maximize,
    )
    model_input = build_normalized_model_input(
        problem_fingerprint=problem.rolling_problem_fingerprint,
        planning_resolution_hours=0.25,
        planning_interval_count=160,
        planning_intervals_per_energy_interval=4,
        planning_intervals_per_fcr_block=16,
        payload={
            "formulation_kind": "restriction_rolling_0800",
            "K_lower": -63,
            "source_energy_indices": hours,
            "source_fcr_indices": blocks,
        },
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
            "v_res",
        )
    }
    cardinality = {
        "planning_intervals": 160,
        "current_robust_planning_intervals": 96,
        "energy_intervals": 40,
        "fcr_intervals": 10,
        "fixed_predecessor_energy_decisions": 16,
        "fixed_predecessor_fcr_decisions": 4,
        "variables": sum(1 for _ in model.component_data_objects(pyo.Var, active=True)),
        "binaries": sum(
            1
            for variable in model.component_data_objects(pyo.Var, active=True)
            if variable.is_binary()
        ),
        "active_constraints": sum(
            1 for _ in model.component_data_objects(pyo.Constraint, active=True)
        ),
    }
    handoff = RobustFCRModelHandoff(
        formulation_kind="restriction",
        equation_version="robust-storage-bidding-rolling-0800-restriction-v1",
        model_input=model_input,
        cardinality=cardinality,
    )
    return AssembledRobustFCRModel(
        model=model,
        handoff=handoff,
        variable_handles=MappingProxyType(variables),
        constraint_handles=MappingProxyType(constraints),
    )


def assemble_robust_fcr_reference_certificate(
    problem: RobustFCRBiddingProblem,
    request: Any,
    *,
    pyomo_environ: Any,
) -> AssembledRobustFCRModel:
    """Assemble one joint rounded-decision restriction certificate.

    ``request`` is deliberately duck-typed here so the private formulation
    module does not import the public reference module and create an import
    cycle.  Its immutable contract is validated before this lazy boundary.
    """

    profile = RobustFCRFormulationProfile.for_kind("restriction")
    assembled = assemble_robust_fcr_model(
        problem,
        profile,
        pyomo_environ=pyomo_environ,
    )
    objective_interval = getattr(request, "certification_objective_interval", None)
    decision_intervals = tuple(getattr(request, "decision_intervals", ()))
    maximum_slack = getattr(request, "maximum_deployability_slack", None)
    if objective_interval is None or len(decision_intervals) != 30:
        raise RobustFCRValidationError(
            "reference certification requires one objective interval and 30 decisions"
        )
    if maximum_slack != DEPLOYABILITY_THRESHOLD:
        raise RobustFCRValidationError(
            f"reference certification slack limit must equal {DEPLOYABILITY_THRESHOLD}"
        )
    model = assembled.model
    pyo = pyomo_environ
    constraints = dict(assembled.constraint_handles)
    decision_box = _add_constraint_family(
        model,
        pyo,
        "c_reference_decision_box",
    )
    for interval in decision_intervals:
        kind = getattr(interval, "decision_kind", None)
        index = getattr(interval, "index", None)
        lower = float(getattr(interval, "lower"))
        upper = float(getattr(interval, "upper"))
        if kind == "energy_x0":
            variable = model.x0[index]
        elif kind == "fcr_xr":
            variable = model.xr[index]
        else:  # pragma: no cover - public request validation guards this path
            raise RobustFCRValidationError(
                "reference certificate contains an unsupported decision kind"
            )
        decision_box.add(variable >= lower)
        decision_box.add(variable <= upper)
    constraints["reference_decision_box"] = decision_box

    objective_box = _add_constraint_family(
        model,
        pyo,
        "c_reference_objective_box",
    )
    objective_expression = model.objective.expr
    objective_box.add(objective_expression >= float(objective_interval[0]))
    objective_box.add(objective_expression <= float(objective_interval[1]))
    constraints["reference_objective_box"] = objective_box

    slack_bounds = _add_constraint_family(
        model,
        pyo,
        "c_reference_slack_bounds",
    )
    for index in assembled.handoff.model_input.index_sets.planning_indices:
        slack_bounds.add(model.symin[index] <= maximum_slack)
        slack_bounds.add(model.symax[index] <= maximum_slack)
    for index in (0, 1):
        slack_bounds.add(model.syK[index] <= maximum_slack)
    constraints["reference_slack_bounds"] = slack_bounds

    observed_constraints = sum(
        1 for _ in model.component_data_objects(pyo.Constraint, active=True)
    )
    cardinality = dict(assembled.handoff.cardinality)
    cardinality.update(
        {
            "reference_decision_box_constraints": 60,
            "reference_objective_box_constraints": 2,
            "reference_slack_bound_constraints": 194,
            "reference_certification_constraints": 256,
            "active_constraints": observed_constraints,
        }
    )
    if observed_constraints != assembled.handoff.cardinality["active_constraints"] + 256:
        raise RobustFCRValidationError(
            "assembled reference certificate cardinality does not reconcile"
        )
    handoff = RobustFCRModelHandoff(
        formulation_kind=assembled.handoff.formulation_kind,
        equation_version=assembled.handoff.equation_version,
        model_input=assembled.handoff.model_input,
        cardinality=cardinality,
    )
    return AssembledRobustFCRModel(
        model=model,
        handoff=handoff,
        variable_handles=assembled.variable_handles,
        constraint_handles=MappingProxyType(constraints),
    )


__all__ = [
    "AssembledRobustFCRModel",
    "NormalizedRobustFCRIndexSets",
    "RobustFCRModelHandoff",
    "RobustFCRModelInput",
    "RobustFCRReferenceIntervalAudit",
    "SOURCE_EQUATION_REFERENCES",
    "SOURCE_EQUATION_VERSION",
    "assemble_arbitrage_only_model",
    "assemble_normalized_robust_fcr_model",
    "assemble_rolling_0800_model",
    "build_normalized_index_sets",
    "build_normalized_model_input",
    "build_model_input",
    "derive_rolling_source_indices",
    "assemble_robust_fcr_model",
    "assemble_robust_fcr_reference_certificate",
    "audit_closed_reference_witness",
    "model_cardinality_basis",
    "model_cardinality_metadata",
    "propagate_fixed_tail_robust_bounds",
]
