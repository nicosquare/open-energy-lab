"""Additive exact-zero-FCR and fixed-overlap optimization contracts.

Feature 013's public 24/96/6 problem remains unchanged. This module owns only
the two source executable frames that cannot be represented by that contract:
script 13's hourly arbitrage-only model and script 14's signed-index 40-hour
accepted-overlap restriction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import math
from types import MappingProxyType
from typing import Any

from .fcr_rolling_backtest import (
    RollingFCRExperimentProfile,
    RollingFCRValidationError,
)
from .robust_fcr_bidding import (
    DEPLOYABILITY_THRESHOLD,
    ConstraintFamilyResidual,
    FeasibilityAudit,
    ObjectiveBreakdown,
    RobustFCRBatteryParameters,
    RobustFCRDecisions,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRTimeContract,
    RobustFCRUncertaintyProfile,
    SolverEvidence,
    TerminalStoredEnergyRule,
    _build_fixed_fcr_plan_from_decisions,
    _canonicalize_witness_decisions,
    _deep_freeze,
    _fingerprint,
    _normalize_maximization_gap,
    _sha256,
    _thaw,
)


ROBUST_FCR_ROLLING_PROBLEM_VERSION = "oel.robust-fcr-rolling-problem.v1"
ROBUST_FCR_ROLLING_RESULT_VERSION = "oel.robust-fcr-rolling-result.v1"
ROBUST_FCR_ACCEPTED_FIXINGS_VERSION = "oel.robust-fcr-accepted-fixings.v1"
_SUPPORTED_ROLLING_PROFILES = {
    "script-13-arbitrage-only-midnight-v1",
    "script-14-restriction-rolling-0800-v1",
}
_BIDDER_FORBIDDEN_TERMS = (
    "activation",
    "realized",
    "replay",
    "settlement",
    "comparison",
    "parity",
    "future",
    "credential",
    "secret",
    "token",
)


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RollingFCRValidationError(f"{field_name} must be a non-empty string")
    return value


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RollingFCRValidationError(f"{field_name} must be finite")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise RollingFCRValidationError(f"{field_name} must be finite")
    return 0.0 if normalized == 0.0 else normalized


def _utc(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RollingFCRValidationError(f"{field_name} must be an aware UTC datetime")
    if value.utcoffset() != timedelta(0):
        raise RollingFCRValidationError(f"{field_name} must be an aware UTC datetime")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha(value: object, *, field_name: str) -> str:
    try:
        return _sha256(value, field_name=field_name)
    except ValueError as exc:
        raise RollingFCRValidationError(str(exc)) from exc


def _finite_tuple(
    values: Sequence[object],
    *,
    field_name: str,
    count: int,
) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or len(values) != count:
        raise RollingFCRValidationError(
            f"{field_name} must contain exactly {count} values"
        )
    return tuple(
        _finite(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(values)
    )


def _freeze_visible_mapping(
    value: Mapping[str, object],
    *,
    field_name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RollingFCRValidationError(f"{field_name} must be a mapping")
    for key, inner in value.items():
        normalized = _non_empty(key, field_name=f"{field_name} key")
        if any(term in normalized.casefold() for term in _BIDDER_FORBIDDEN_TERMS):
            raise RollingFCRValidationError(
                f"{field_name}.{normalized} violates the information cutoff"
            )
        if isinstance(inner, Mapping):
            _freeze_visible_mapping(inner, field_name=f"{field_name}.{normalized}")
    try:
        return _deep_freeze(value, field_name=field_name)
    except ValueError as exc:
        raise RollingFCRValidationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class RobustFCRAcceptedDecisionFixings:
    """Accepted predecessor tail represented in both public and source signs."""

    predecessor_plan_fingerprint: str
    predecessor_problem_fingerprint: str
    predecessor_result_fingerprint: str
    energy_source_indices: tuple[int, ...]
    energy_public_charge_positive_kw: tuple[float, ...]
    source_energy_positive_discharge_kw: tuple[float, ...]
    energy_interval_refs: tuple[str, ...]
    fcr_source_indices: tuple[int, ...]
    fcr_capacity_kw: tuple[float, ...]
    fcr_interval_refs: tuple[str, ...]
    mapping_rule_id: str = "accepted-predecessor-hours-09-24-blocks-3-6-v1"
    semantics_version: str = ROBUST_FCR_ACCEPTED_FIXINGS_VERSION
    fixings_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "predecessor_plan_fingerprint",
            "predecessor_problem_fingerprint",
            "predecessor_result_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), field_name=name))
        energy_indices = tuple(self.energy_source_indices)
        fcr_indices = tuple(self.fcr_source_indices)
        if energy_indices != tuple(range(-15, 1)):
            raise RollingFCRValidationError(
                "accepted energy fixings must use source indices -15..0"
            )
        if fcr_indices != tuple(range(-3, 1)):
            raise RollingFCRValidationError(
                "accepted FCR fixings must use source indices -3..0"
            )
        public = _finite_tuple(
            self.energy_public_charge_positive_kw,
            field_name="energy_public_charge_positive_kw",
            count=16,
        )
        source = _finite_tuple(
            self.source_energy_positive_discharge_kw,
            field_name="source_energy_positive_discharge_kw",
            count=16,
        )
        if any(
            not math.isclose(source_value, -public_value, abs_tol=1e-12)
            for source_value, public_value in zip(source, public, strict=True)
        ):
            raise RollingFCRValidationError(
                "source energy fixings must be the explicit negation of public charge-positive values"
            )
        fcr = _finite_tuple(
            self.fcr_capacity_kw,
            field_name="fcr_capacity_kw",
            count=4,
        )
        if any(value < 0.0 for value in fcr):
            raise RollingFCRValidationError("accepted FCR fixings must be non-negative")
        energy_refs = tuple(
            _non_empty(value, field_name="energy_interval_ref")
            for value in self.energy_interval_refs
        )
        fcr_refs = tuple(
            _non_empty(value, field_name="fcr_interval_ref")
            for value in self.fcr_interval_refs
        )
        if len(energy_refs) != 16 or len(fcr_refs) != 4:
            raise RollingFCRValidationError("accepted fixings require 16/4 interval refs")
        if self.mapping_rule_id != "accepted-predecessor-hours-09-24-blocks-3-6-v1":
            raise RollingFCRValidationError("unsupported accepted-decision fixing rule")
        if self.semantics_version != ROBUST_FCR_ACCEPTED_FIXINGS_VERSION:
            raise RollingFCRValidationError("unsupported accepted-fixings version")
        object.__setattr__(self, "energy_source_indices", energy_indices)
        object.__setattr__(self, "fcr_source_indices", fcr_indices)
        object.__setattr__(self, "energy_public_charge_positive_kw", public)
        object.__setattr__(self, "source_energy_positive_discharge_kw", source)
        object.__setattr__(self, "fcr_capacity_kw", fcr)
        object.__setattr__(self, "energy_interval_refs", energy_refs)
        object.__setattr__(self, "fcr_interval_refs", fcr_refs)
        object.__setattr__(self, "fixings_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "predecessor_plan_fingerprint": self.predecessor_plan_fingerprint,
            "predecessor_problem_fingerprint": self.predecessor_problem_fingerprint,
            "predecessor_result_fingerprint": self.predecessor_result_fingerprint,
            "energy_source_indices": list(self.energy_source_indices),
            "energy_public_charge_positive_kw": list(
                self.energy_public_charge_positive_kw
            ),
            "source_energy_positive_discharge_kw": list(
                self.source_energy_positive_discharge_kw
            ),
            "energy_interval_refs": list(self.energy_interval_refs),
            "fcr_source_indices": list(self.fcr_source_indices),
            "fcr_capacity_kw": list(self.fcr_capacity_kw),
            "fcr_interval_refs": list(self.fcr_interval_refs),
            "mapping_rule_id": self.mapping_rule_id,
            "sign_mapping": (
                "source_positive_discharge = -public_positive_charge"
            ),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "fixings_fingerprint": self.fixings_fingerprint}


def extract_accepted_predecessor_fixings(
    *,
    plan: object,
    predecessor_problem_fingerprint: str,
    predecessor_result_fingerprint: str,
) -> RobustFCRAcceptedDecisionFixings:
    """Extract the exact accepted 09–24 and block 3–6 predecessor tail.

    Values come from the immutable native plan, never from the source fixture's
    displayed three-decimal decisions.  The public charge-positive energy sign
    is retained beside its explicit source-positive-discharge negation.
    """

    from .fcr_bid_plan import FixedFCRBidPlan

    if not isinstance(plan, FixedFCRBidPlan):
        raise RollingFCRValidationError(
            "accepted predecessor fixings require a FixedFCRBidPlan"
        )
    if plan.producer.producer_kind != "robust":
        raise RollingFCRValidationError(
            "08:00 predecessor fixings require an accepted robust plan"
        )
    if plan.solve_status not in {"optimal", "feasible"}:
        raise RollingFCRValidationError(
            "08:00 predecessor fixings require a solved accepted plan"
        )
    energy = tuple(plan.energy_schedule.intervals)
    fcr = tuple(plan.fcr_schedule.intervals)
    if len(energy) != 24 or len(fcr) != 6:
        raise RollingFCRValidationError(
            "accepted predecessor plan must retain ordinary 24/6 coverage"
        )
    if (
        energy[0].interval.start_utc
        != plan.energy_schedule.covered_period.start_utc
        or energy[-1].interval.end_utc
        != plan.energy_schedule.covered_period.end_utc
        or fcr[0].interval.start_utc
        != plan.fcr_schedule.covered_period.start_utc
        or fcr[-1].interval.end_utc
        != plan.fcr_schedule.covered_period.end_utc
    ):
        raise RollingFCRValidationError(
            "accepted predecessor schedules must retain exact interval coverage"
        )
    energy_tail = energy[8:]
    fcr_tail = fcr[2:]

    def interval_ref(kind: str, item: object) -> str:
        interval = item.interval
        return (
            f"accepted:{kind}:"
            f"{_utc_text(interval.start_utc)}/{_utc_text(interval.end_utc)}"
        )

    public_energy = tuple(item.power_kw for item in energy_tail)
    return RobustFCRAcceptedDecisionFixings(
        predecessor_plan_fingerprint=plan.plan_fingerprint,
        predecessor_problem_fingerprint=predecessor_problem_fingerprint,
        predecessor_result_fingerprint=predecessor_result_fingerprint,
        energy_source_indices=tuple(range(-15, 1)),
        energy_public_charge_positive_kw=public_energy,
        source_energy_positive_discharge_kw=tuple(
            -value for value in public_energy
        ),
        energy_interval_refs=tuple(
            interval_ref("energy", item) for item in energy_tail
        ),
        fcr_source_indices=tuple(range(-3, 1)),
        fcr_capacity_kw=tuple(item.capacity_kw for item in fcr_tail),
        fcr_interval_refs=tuple(interval_ref("fcr", item) for item in fcr_tail),
    )


@dataclass(frozen=True, slots=True)
class RobustFCRRollingBiddingProblem:
    problem_id: str
    profile: RollingFCRExperimentProfile
    current_time_contract: RobustFCRTimeContract
    battery: RobustFCRBatteryParameters
    current_prices: RobustFCRPriceInputs
    uncertainty: RobustFCRUncertaintyProfile
    terminal_rule: TerminalStoredEnergyRule
    solve_policy: RobustFCRSolvePolicy
    information_cutoff_utc: datetime
    producer_input_fingerprints: Mapping[str, str]
    provenance: Mapping[str, object]
    predecessor_prices: RobustFCRPriceInputs | None = None
    accepted_fixings: RobustFCRAcceptedDecisionFixings | None = None
    predecessor_cutoff_utc: datetime | None = None
    semantics_version: str = ROBUST_FCR_ROLLING_PROBLEM_VERSION
    K_lower: int = field(init=False)
    source_planning_indices: tuple[int, ...] = field(init=False)
    source_energy_indices: tuple[int, ...] = field(init=False)
    source_fcr_indices: tuple[int, ...] = field(init=False)
    propagated_minimum_stored_energy_kwh: float = field(init=False)
    propagated_maximum_stored_energy_kwh: float = field(init=False)
    fixed_tail_objective_eur: float = field(init=False)
    rolling_problem_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", _non_empty(self.problem_id, field_name="problem_id"))
        expected = (
            ("profile", self.profile, RollingFCRExperimentProfile),
            ("current_time_contract", self.current_time_contract, RobustFCRTimeContract),
            ("battery", self.battery, RobustFCRBatteryParameters),
            ("current_prices", self.current_prices, RobustFCRPriceInputs),
            ("uncertainty", self.uncertainty, RobustFCRUncertaintyProfile),
            ("terminal_rule", self.terminal_rule, TerminalStoredEnergyRule),
            ("solve_policy", self.solve_policy, RobustFCRSolvePolicy),
        )
        for name, value, contract in expected:
            if not isinstance(value, contract):
                raise RollingFCRValidationError(f"{name} has the wrong contract type")
        if self.profile.profile_id not in _SUPPORTED_ROLLING_PROFILES:
            raise RollingFCRValidationError(
                "rolling bidding problem supports only exact-zero-FCR or rolling-0800 profiles"
            )
        if self.semantics_version != ROBUST_FCR_ROLLING_PROBLEM_VERSION:
            raise RollingFCRValidationError("unsupported rolling problem version")
        cutoff = _utc(self.information_cutoff_utc, field_name="information_cutoff_utc")
        if cutoff > self.current_time_contract.delivery_period.start_utc:
            raise RollingFCRValidationError("information cutoff cannot follow delivery start")
        inputs: dict[str, str] = {}
        if not isinstance(self.producer_input_fingerprints, Mapping):
            raise RollingFCRValidationError("producer_input_fingerprints must be a mapping")
        for key, value in self.producer_input_fingerprints.items():
            normalized = _non_empty(key, field_name="producer_input_fingerprints key")
            if any(term in normalized.casefold() for term in _BIDDER_FORBIDDEN_TERMS):
                raise RollingFCRValidationError(
                    f"producer_input_fingerprints.{normalized} violates the information cutoff"
                )
            inputs[normalized] = _sha(value, field_name=f"producer_input_fingerprints.{normalized}")
        provenance = _freeze_visible_mapping(self.provenance, field_name="provenance")
        target = self.terminal_rule.minimum_terminal_stored_energy_kwh
        if not self.battery.minimum_stored_energy_kwh <= target <= self.battery.maximum_stored_energy_kwh:
            raise RollingFCRValidationError("terminal target lies outside battery bounds")
        if self.profile.profile_id == "script-13-arbitrage-only-midnight-v1":
            if self.predecessor_prices is not None or self.accepted_fixings is not None or self.predecessor_cutoff_utc is not None:
                raise RollingFCRValidationError(
                    "arbitrage-only daily frame must not contain accepted overlap fixings"
                )
            K_lower = 1
            planning = tuple(range(1, 25))
            energy = tuple(range(1, 25))
            fcr = tuple(range(1, 7))
            propagated_minimum = self.battery.initial_stored_energy_kwh
            propagated_maximum = self.battery.initial_stored_energy_kwh
            fixed_tail = 0.0
        else:
            if not isinstance(self.predecessor_prices, RobustFCRPriceInputs):
                raise RollingFCRValidationError("08:00 problem requires predecessor prices")
            if not isinstance(self.accepted_fixings, RobustFCRAcceptedDecisionFixings):
                raise RollingFCRValidationError("08:00 problem requires exact accepted fixings")
            if self.predecessor_cutoff_utc is None:
                raise RollingFCRValidationError("08:00 problem requires predecessor cutoff identity")
            predecessor_cutoff = _utc(self.predecessor_cutoff_utc, field_name="predecessor_cutoff_utc")
            if predecessor_cutoff > cutoff:
                raise RollingFCRValidationError("predecessor cutoff cannot follow information cutoff")
            from ._robust_fcr_formulation import (
                derive_rolling_source_indices,
                propagate_fixed_tail_robust_bounds,
            )

            index_values = derive_rolling_source_indices(8)
            K_lower = int(index_values["K_lower"])
            planning = tuple(index_values["planning_indices"])
            energy = tuple(index_values["energy_indices"])
            fcr = tuple(index_values["fcr_indices"])
            recovery = self.uncertainty.recovery_window
            duration_hours = 16.0
            full_windows = math.floor(duration_hours / recovery.recovery_window_hours)
            remainder = duration_hours - full_windows * recovery.recovery_window_hours
            prior_budget = (
                full_windows * recovery.recovery_activation_budget_hours
                + min(remainder, recovery.recovery_activation_budget_hours)
            )
            propagated_minimum, propagated_maximum = propagate_fixed_tail_robust_bounds(
                initial_stored_energy_kwh=self.battery.initial_stored_energy_kwh,
                source_energy_positive_discharge_kw=(
                    self.accepted_fixings.source_energy_positive_discharge_kw
                ),
                fcr_capacity_kw=self.accepted_fixings.fcr_capacity_kw,
                charge_efficiency=self.battery.charge_efficiency,
                discharge_efficiency=self.battery.discharge_efficiency,
                activation_budget_hours=prior_budget,
            )
            predecessor_energy_prices = (
                self.predecessor_prices.day_ahead_energy_prices_eur_per_kwh[8:]
            )
            predecessor_fcr_prices = (
                self.predecessor_prices.fcr_capacity_prices_eur_per_kw_block[2:]
            )
            fixed_tail = sum(
                price * value
                for price, value in zip(
                    predecessor_energy_prices,
                    self.accepted_fixings.source_energy_positive_discharge_kw,
                    strict=True,
                )
            ) + sum(
                price * value
                for price, value in zip(
                    predecessor_fcr_prices,
                    self.accepted_fixings.fcr_capacity_kw,
                    strict=True,
                )
            )
            object.__setattr__(self, "predecessor_cutoff_utc", predecessor_cutoff)
        object.__setattr__(self, "information_cutoff_utc", cutoff)
        object.__setattr__(self, "producer_input_fingerprints", MappingProxyType(dict(sorted(inputs.items()))))
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "K_lower", K_lower)
        object.__setattr__(self, "source_planning_indices", planning)
        object.__setattr__(self, "source_energy_indices", energy)
        object.__setattr__(self, "source_fcr_indices", fcr)
        object.__setattr__(self, "propagated_minimum_stored_energy_kwh", propagated_minimum)
        object.__setattr__(self, "propagated_maximum_stored_energy_kwh", propagated_maximum)
        object.__setattr__(self, "fixed_tail_objective_eur", fixed_tail)
        object.__setattr__(self, "rolling_problem_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "problem_id": self.problem_id,
            "profile": self.profile.to_dict(),
            "current_time_contract": self.current_time_contract.to_dict(),
            "battery": self.battery.to_dict(),
            "current_prices": self.current_prices.to_dict(),
            "uncertainty": self.uncertainty.to_dict(),
            "terminal_rule": self.terminal_rule.to_dict(),
            "solve_policy": self.solve_policy.to_dict(),
            "information_cutoff_utc": _utc_text(self.information_cutoff_utc),
            "producer_input_fingerprints": dict(self.producer_input_fingerprints),
            "provenance": _thaw(self.provenance),
            "predecessor_prices": None if self.predecessor_prices is None else self.predecessor_prices.to_dict(),
            "accepted_fixings": None if self.accepted_fixings is None else self.accepted_fixings.to_dict(),
            "predecessor_cutoff_utc": None if self.predecessor_cutoff_utc is None else _utc_text(self.predecessor_cutoff_utc),
            "indexing": {
                "K_lower": self.K_lower,
                "planning_indices": list(self.source_planning_indices),
                "energy_indices": list(self.source_energy_indices),
                "fcr_indices": list(self.source_fcr_indices),
            },
            "propagated_stored_energy_bounds_kwh": {
                "minimum": self.propagated_minimum_stored_energy_kwh,
                "maximum": self.propagated_maximum_stored_energy_kwh,
            },
            "fixed_tail_objective_eur": self.fixed_tail_objective_eur,
            "sign_mapping": "source-positive-discharge-to-public-charge-positive-negation-v1",
            "source_refs": [
                "baselines/robust_storage_bidding/code/02_model.jl:15-32,34-75",
                "baselines/robust_storage_bidding/code/02_model.jl:137-188,252-263,289-305",
            ],
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "rolling_problem_fingerprint": self.rolling_problem_fingerprint}


def build_robust_fcr_rolling_problem(**values: object) -> RobustFCRRollingBiddingProblem:
    """Build an exact-zero-FCR or signed-index fixed-overlap request."""

    return RobustFCRRollingBiddingProblem(**values)


@dataclass(frozen=True, slots=True)
class RobustFCRRollingSolveResult:
    problem_fingerprint: str
    profile_fingerprint: str
    formulation_kind: str
    solver: SolverEvidence
    objective: ObjectiveBreakdown | None
    fixed_tail_objective_eur: float
    decisions: RobustFCRDecisions | None
    feasibility_audit: FeasibilityAudit | None
    plan_classification: str
    plan: Any | None
    diagnostics: tuple[str, ...]
    runtime_metadata: Mapping[str, object]
    semantics_version: str = ROBUST_FCR_ROLLING_RESULT_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_fingerprint", _sha(self.problem_fingerprint, field_name="problem_fingerprint"))
        object.__setattr__(self, "profile_fingerprint", _sha(self.profile_fingerprint, field_name="profile_fingerprint"))
        if self.formulation_kind not in {"restriction", "arbitrage_only"}:
            raise RollingFCRValidationError("unsupported rolling result formulation")
        if not isinstance(self.solver, SolverEvidence):
            raise RollingFCRValidationError("solver has the wrong contract type")
        if self.plan_classification not in {"robust_candidate", "arbitrage_only"}:
            raise RollingFCRValidationError("unsupported rolling plan classification")
        if self.plan is not None and self.decisions is None:
            raise RollingFCRValidationError("a rolling plan requires decisions")
        object.__setattr__(self, "fixed_tail_objective_eur", _finite(self.fixed_tail_objective_eur, field_name="fixed_tail_objective_eur"))
        object.__setattr__(self, "diagnostics", tuple(sorted(_non_empty(value, field_name="diagnostic") for value in self.diagnostics)))
        object.__setattr__(self, "runtime_metadata", _deep_freeze(self.runtime_metadata, field_name="runtime_metadata"))
        object.__setattr__(self, "semantic_fingerprint", _fingerprint(self._semantic_payload()))

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "problem_fingerprint": self.problem_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "formulation_kind": self.formulation_kind,
            "solver": self.solver.semantic_dict(),
            "objective": None if self.objective is None else self.objective.to_dict(),
            "fixed_tail_objective_eur": self.fixed_tail_objective_eur,
            "decisions": None if self.decisions is None else self.decisions.to_dict(),
            "feasibility_audit": None if self.feasibility_audit is None else self.feasibility_audit.to_dict(),
            "plan_classification": self.plan_classification,
            "plan_fingerprint": None if self.plan is None else self.plan.plan_fingerprint,
            "diagnostics": list(self.diagnostics),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "runtime_metadata": _thaw(self.runtime_metadata),
            "semantic_fingerprint": self.semantic_fingerprint,
        }


class _IndependentAuditFamily:
    __slots__ = (
        "family_id",
        "relation",
        "canonical_unit",
        "maximum",
        "checked",
        "witnesses",
    )

    def __init__(self, family_id: str, relation: str, canonical_unit: str) -> None:
        self.family_id = family_id
        self.relation = relation
        self.canonical_unit = canonical_unit
        self.maximum = 0.0
        self.checked = 0
        self.witnesses: list[tuple[int, ...]] = []

    def add(self, violation: float, *indices: int) -> None:
        normalized = max(_finite(violation, field_name=self.family_id), 0.0)
        self.checked += 1
        if normalized > self.maximum:
            self.maximum = normalized
            self.witnesses = [tuple(indices)]
        elif normalized > 0.0 and normalized == self.maximum:
            self.witnesses.append(tuple(indices))

    def build(self) -> ConstraintFamilyResidual:
        return ConstraintFamilyResidual(
            family_id=self.family_id,
            relation=self.relation,
            canonical_unit=self.canonical_unit,
            checked_count=self.checked,
            maximum_positive_violation=self.maximum,
            witness_indices=tuple(self.witnesses),
            source_refs=(
                "baselines/robust_storage_bidding/code/02_model.jl:34-75,170-263",
            ),
        )


def _new_audit_families() -> dict[str, _IndependentAuditFamily]:
    definitions = {
        "alpha_charge_epigraph": (">=", "kW"),
        "alpha_charge_upper": ("<=", "kW"),
        "alpha_discharge_epigraph": (">=", "kW"),
        "alpha_discharge_upper": ("<=", "kW"),
        "arbitrage_case_lower": (">=", "kW"),
        "arbitrage_case_upper": ("<=", "kW"),
        "beta_charge_epigraph": (">=", "kW"),
        "beta_discharge_epigraph": (">=", "kW"),
        "binary_integrality": ("integrality", "dimensionless"),
        "fixed_fcr_zero": ("==", "kW"),
        "fixed_intraday_adjustment": ("==", "kW"),
        "fixed_predecessor_energy": ("==", "kW"),
        "fixed_predecessor_fcr": ("==", "kW"),
        "lambda_h_bounds": ("bounds", "kW"),
        "lambda_h_diagonal_activation": (">=", "kW"),
        "lambda_h_diagonal_discharge": (">=", "kW"),
        "lambda_h_diagonal_nonnegative": (">=", "kW"),
        "lambda_h_offdiag_charge_activation": (">=", "kW"),
        "lambda_h_offdiag_charge_baseline": (">=", "kW"),
        "lambda_h_offdiag_discharge_activation": (">=", "kW"),
        "lambda_h_offdiag_discharge_baseline": (">=", "kW"),
        "lower_coupling": (">=", "kW"),
        "lower_stored_energy": (">=", "kWh"),
        "nonnegative_variables": (">=", "dimensionless"),
        "pointwise_charge_headroom": (">=", "kW"),
        "pointwise_discharge_headroom": ("<=", "kW"),
        "restriction_classification_lower": (">=", "kW"),
        "restriction_classification_upper": ("<=", "kW"),
        "restriction_tightening_charge": (">=", "kW"),
        "restriction_tightening_discharge": (">=", "kW"),
        "terminal_stored_energy": (">=", "kWh"),
        "u1_lower": (">=", "kW"),
        "u1_upper": ("<=", "kW"),
        "u2_lower": (">=", "kW"),
        "u2_upper": ("<=", "kW"),
        "upper_stored_energy": ("<=", "kWh"),
    }
    return {
        name: _IndependentAuditFamily(name, relation, unit)
        for name, (relation, unit) in definitions.items()
    }


def _modeled_slacks(witness: Mapping[str, object]) -> dict[str, float]:
    result: dict[str, float] = {}
    for name, values in witness.items():
        if "sy" not in name.casefold() or not isinstance(values, tuple):
            continue
        flattened: list[float] = []
        for value in values:
            if isinstance(value, tuple):
                flattened.extend(float(inner) for inner in value)
            elif isinstance(value, (int, float)):
                flattened.append(float(value))
        result[name] = max((abs(value) for value in flattened), default=0.0)
    return result


def _audit_arbitrage_witness(
    problem: RobustFCRRollingBiddingProblem,
    witness: Mapping[str, object],
    families: dict[str, _IndependentAuditFamily],
) -> None:
    x0 = tuple(float(value) for value in witness["x0"])
    xr = tuple(float(value) for value in witness["xr"])
    alpha = tuple(float(value) for value in witness["alpha"])
    binary = tuple(float(value) for value in witness["u"])
    symin = tuple(float(value) for value in witness["symin"])
    symax = tuple(float(value) for value in witness["symax"])
    sy_k = tuple(float(value) for value in witness["syK"])
    battery = problem.battery
    eta_c = battery.charge_efficiency
    eta_d = battery.discharge_efficiency
    delta_eta = 1.0 / eta_d - eta_c
    x_min = battery.source_minimum_power_kw
    x_max = battery.source_maximum_power_kw
    y_initial = battery.initial_stored_energy_kwh
    for k in range(24):
        families["pointwise_charge_headroom"].add(x_min - x0[k], k)
        families["pointwise_discharge_headroom"].add(x0[k] - x_max, k)
        families["lower_stored_energy"].add(
            sum(alpha[: k + 1])
            - (y_initial - battery.minimum_stored_energy_kwh + symin[k]),
            k,
        )
        families["upper_stored_energy"].add(
            y_initial
            - (eta_c * x0[k] + sum(alpha[:k]))
            - (battery.maximum_stored_energy_kwh + symax[k]),
            k,
        )
        families["alpha_charge_epigraph"].add(eta_c * x0[k] - alpha[k], k)
        families["alpha_discharge_epigraph"].add(x0[k] / eta_d - alpha[k], k)
    for k in range(23):
        families["binary_integrality"].add(
            min(abs(binary[k]), abs(binary[k] - 1.0)),
            k,
        )
        families["arbitrage_case_lower"].add(
            (1.0 - binary[k]) * x_min - x0[k],
            k,
        )
        families["arbitrage_case_upper"].add(
            x0[k] - binary[k] * x_max,
            k,
        )
        families["alpha_charge_upper"].add(
            alpha[k] - (eta_c * x0[k] + binary[k] * delta_eta * x_max),
            k,
        )
        families["alpha_discharge_upper"].add(
            alpha[k]
            - (
                x0[k] / eta_d
                - (1.0 - binary[k]) * delta_eta * x_min
            ),
            k,
        )
    for k, value in enumerate(xr):
        families["fixed_fcr_zero"].add(abs(value), k)
    families["terminal_stored_energy"].add(
        sum(alpha)
        - (
            y_initial
            - problem.terminal_rule.minimum_terminal_stored_energy_kwh
            + sy_k[1]
        ),
        0,
    )


def _audit_rolling_0800_witness(
    problem: RobustFCRRollingBiddingProblem,
    witness: Mapping[str, object],
    families: dict[str, _IndependentAuditFamily],
) -> None:
    x0_values = tuple(float(value) for value in witness["x0_extended"])
    xr_values = tuple(float(value) for value in witness["xr_extended"])
    x0 = dict(zip(range(-15, 25), x0_values, strict=True))
    xr = dict(zip(range(-3, 7), xr_values, strict=True))
    alpha = dict(
        zip(
            range(-63, 97),
            (float(value) for value in witness["alpha_extended"]),
            strict=True,
        )
    )
    beta = dict(
        zip(
            range(-63, 97),
            (float(value) for value in witness["beta_extended"]),
            strict=True,
        )
    )
    xa = tuple(float(value) for value in witness["xa_extended"])
    lambda_l = tuple(float(value) for value in witness["lambda_l"])
    lambda_h = tuple(float(value) for value in witness["lambda_h"])
    lambda_lower = tuple(
        tuple(float(value) for value in row) for row in witness["Lambda_l"]
    )
    lambda_upper = tuple(
        tuple(float(value) for value in row) for row in witness["Lambda_h"]
    )
    u1 = tuple(float(value) for value in witness["u1"])
    u2 = tuple(float(value) for value in witness["u2"])
    v_res = tuple(float(value) for value in witness["v_res"])
    sy_k = tuple(float(value) for value in witness["syK"])
    battery = problem.battery
    eta_c = battery.charge_efficiency
    eta_d = battery.discharge_efficiency
    delta_eta = 1.0 / eta_d - eta_c
    x_min = battery.source_minimum_power_kw
    x_max = battery.source_maximum_power_kw
    gamma = problem.uncertainty.horizon_wide.horizon_activation_budget_hours
    for ordinal, (observed, expected) in enumerate(
        zip(
            x0_values[:16],
            problem.accepted_fixings.source_energy_positive_discharge_kw,
            strict=True,
        )
    ):
        families["fixed_predecessor_energy"].add(abs(observed - expected), ordinal)
    for ordinal, (observed, expected) in enumerate(
        zip(xr_values[:4], problem.accepted_fixings.fcr_capacity_kw, strict=True)
    ):
        families["fixed_predecessor_fcr"].add(abs(observed - expected), ordinal)
    for ordinal, value in enumerate(xr_values):
        families["nonnegative_variables"].add(-value, ordinal, 2)
    for ordinal, value in enumerate(xa):
        families["fixed_intraday_adjustment"].add(abs(value), ordinal)
    for ordinal, k in enumerate(range(-63, 97)):
        energy = x0[math.ceil(k * 0.25)]
        reserve = xr[math.ceil(k / 16)]
        families["alpha_charge_epigraph"].add(eta_c * energy - alpha[k], ordinal)
        families["alpha_discharge_epigraph"].add(energy / eta_d - alpha[k], ordinal)
        families["beta_charge_epigraph"].add(
            eta_c * (energy + reserve) - beta[k], ordinal
        )
        families["beta_discharge_epigraph"].add(
            (energy + reserve) / eta_d - beta[k], ordinal
        )
    for k in range(1, 97):
        ordinal = k - 1
        energy = x0[math.ceil(k * 0.25)]
        reserve = xr[math.ceil(k / 16)]
        lam_l = lambda_l[ordinal]
        lam_h = lambda_h[ordinal]
        lower_row = lambda_lower[ordinal]
        upper_row = lambda_upper[ordinal]
        families["pointwise_charge_headroom"].add(x_min - (energy - reserve), ordinal)
        families["pointwise_discharge_headroom"].add(energy + reserve - x_max, ordinal)
        lower_state = (
            problem.propagated_minimum_stored_energy_kwh
            - gamma * lam_l
            - 0.25
            * sum(alpha[l] + lower_row[l - 1] for l in range(1, k + 1))
        )
        families["lower_stored_energy"].add(
            battery.minimum_stored_energy_kwh - lower_state,
            ordinal,
        )
        upper_state = (
            problem.propagated_maximum_stored_energy_kwh
            + gamma * lam_h
            + 0.25 * sum(upper_row)
        )
        families["upper_stored_energy"].add(
            upper_state - battery.maximum_stored_energy_kwh,
            ordinal,
        )
        families["lambda_h_bounds"].add(-lam_h, ordinal, 0)
        families["lambda_h_bounds"].add(
            lam_h - (x_max - x_min) / eta_d,
            ordinal,
            1,
        )
        for l in range(1, k + 1):
            families["lower_coupling"].add(
                -(lower_row[l - 1] + lam_l + alpha[l] - beta[l]),
                ordinal,
                l - 1,
            )
            families["nonnegative_variables"].add(
                -lower_row[l - 1], ordinal, l - 1
            )
        diagonal = upper_row[-1]
        families["lambda_h_diagonal_discharge"].add(
            -eta_c * energy - diagonal,
            ordinal,
        )
        families["lambda_h_diagonal_activation"].add(
            eta_c * (reserve - energy) - lam_h - diagonal,
            ordinal,
        )
        families["lambda_h_diagonal_nonnegative"].add(-diagonal, ordinal)
    for l in range(1, 96):
        ordinal = l - 1
        energy = x0[math.ceil(l * 0.25)]
        reserve = xr[math.ceil(l / 16)]
        first = u1[ordinal]
        second = u2[ordinal]
        restriction = v_res[ordinal]
        for variable_ordinal, value in enumerate((first, second, restriction)):
            families["binary_integrality"].add(
                min(abs(value), abs(value - 1.0)),
                ordinal,
                variable_ordinal,
            )
        families["u1_upper"].add(energy - reserve - first * x_max, ordinal)
        families["u1_lower"].add(
            (1.0 - first) * x_min - (energy - reserve), ordinal
        )
        families["u2_lower"].add(second * x_min - energy, ordinal)
        families["u2_upper"].add(energy - (1.0 - second) * x_max, ordinal)
        classification = (
            reserve
            - (1.0 - eta_c * eta_d) * energy
            - eta_d * lambda_h[ordinal]
        )
        families["restriction_classification_lower"].add(
            -((2.0 - eta_c * eta_d) * x_max - x_min)
            * (1.0 - restriction)
            - classification,
            ordinal,
        )
        families["restriction_classification_upper"].add(
            classification
            - restriction * (eta_c * eta_d * x_max - x_min),
            ordinal,
        )
    for k in range(1, 97):
        outer = k - 1
        for l in range(1, k):
            inner = l - 1
            energy = x0[math.ceil(l * 0.25)]
            reserve = xr[math.ceil(l / 16)]
            observed = lambda_upper[outer][inner]
            first = u1[inner]
            second = u2[inner]
            restriction = v_res[inner]
            lam_h = lambda_h[outer]
            bounds = {
                "lambda_h_offdiag_discharge_activation": (
                    (reserve - energy) / eta_d
                    - lam_h
                    + (1.0 - first) * delta_eta * x_min
                ),
                "lambda_h_offdiag_discharge_baseline": (
                    -energy / eta_d + second * delta_eta * x_min
                ),
                "lambda_h_offdiag_charge_activation": (
                    eta_c * (reserve - energy)
                    - lam_h
                    - first * delta_eta * x_max
                ),
                "lambda_h_offdiag_charge_baseline": (
                    -eta_c * energy - (1.0 - second) * delta_eta * x_max
                ),
                "restriction_tightening_charge": (
                    -eta_c * energy
                    - (first + 1.0 - restriction) * delta_eta * x_max
                ),
                "restriction_tightening_discharge": (
                    (reserve - energy) / eta_d
                    - lam_h
                    + (second + restriction) * delta_eta * x_min
                ),
            }
            for family_name, lower_bound in bounds.items():
                families[family_name].add(
                    lower_bound - observed,
                    outer,
                    inner,
                )
    for name in ("lambda_l",):
        for ordinal, value in enumerate(witness[name]):
            families["nonnegative_variables"].add(-float(value), ordinal, 0)
    for name in ("symin_extended", "symax_extended", "syK"):
        for ordinal, value in enumerate(witness[name]):
            families["nonnegative_variables"].add(-float(value), ordinal, 1)
    families["terminal_stored_energy"].add(
        problem.terminal_rule.minimum_terminal_stored_energy_kwh
        - sy_k[1]
        - (
            problem.battery.initial_stored_energy_kwh
            - 0.25 * sum(alpha.values())
        ),
        0,
    )


def _independent_witness_audit(
    problem: RobustFCRRollingBiddingProblem,
    witness: Mapping[str, object],
    decisions: RobustFCRDecisions,
) -> FeasibilityAudit:
    families = _new_audit_families()
    if problem.profile.formulation_kind == "arbitrage_only":
        _audit_arbitrage_witness(problem, witness, families)
    else:
        _audit_rolling_0800_witness(problem, witness, families)
    built = tuple(
        families[name].build()
        for name in sorted(families)
        if families[name].checked > 0
    )
    slacks = _modeled_slacks(witness)
    maximum = max(
        (family.maximum_positive_violation for family in built),
        default=0.0,
    )
    passes = (
        maximum <= DEPLOYABILITY_THRESHOLD
        and max(slacks.values(), default=0.0) <= DEPLOYABILITY_THRESHOLD
    )
    return FeasibilityAudit(
        constraint_families=built,
        modeled_slacks=slacks,
        raw_witness_fingerprint=_fingerprint(_thaw(witness)),
        canonical_witness_fingerprint=_fingerprint(
            {
                "decisions": decisions.to_dict(),
                "audit_kind": "independent-rolling-equation-audit-v1",
            }
        ),
        deployability_threshold=DEPLOYABILITY_THRESHOLD,
        passes_deployability_audit=passes,
    )


def _objective_breakdown(
    problem: RobustFCRRollingBiddingProblem,
    witness: Mapping[str, object],
    reported_objective: float,
) -> ObjectiveBreakdown:
    if problem.profile.formulation_kind == "arbitrage_only":
        source_energy = tuple(float(value) for value in witness["x0"])
        day_ahead = sum(
            price * value
            for price, value in zip(
                problem.current_prices.day_ahead_energy_prices_eur_per_kwh,
                source_energy,
                strict=True,
            )
        )
        fcr_value = 0.0
    else:
        source_energy = tuple(float(value) for value in witness["x0_extended"])
        fcr = tuple(float(value) for value in witness["xr_extended"])
        energy_prices = (
            problem.predecessor_prices.day_ahead_energy_prices_eur_per_kwh[8:]
            + problem.current_prices.day_ahead_energy_prices_eur_per_kwh
        )
        fcr_prices = (
            problem.predecessor_prices.fcr_capacity_prices_eur_per_kw_block[2:]
            + problem.current_prices.fcr_capacity_prices_eur_per_kw_block
        )
        day_ahead = sum(
            price * value
            for price, value in zip(energy_prices, source_energy, strict=True)
        )
        fcr_value = sum(
            price * value
            for price, value in zip(fcr_prices, fcr, strict=True)
        )
    slack_values: list[float] = []
    for name, values in witness.items():
        if "sy" not in name.casefold() or not isinstance(values, tuple):
            continue
        slack_values.extend(float(value) for value in values if isinstance(value, (int, float)))
    penalty = problem.terminal_rule.shortfall_penalty_eur_per_kwh * sum(slack_values)
    calculated = day_ahead + fcr_value - penalty
    return ObjectiveBreakdown(
        day_ahead_energy_value_eur=day_ahead,
        fcr_capacity_value_eur=fcr_value,
        feasibility_slack_penalty_eur=penalty,
        total_objective_eur=calculated,
        reconciliation_residual_eur=abs(calculated - reported_objective),
    )


def _build_plan(
    problem: RobustFCRRollingBiddingProblem,
    decisions: RobustFCRDecisions,
    solver: SolverEvidence,
    classification: str,
) -> Any:
    from .fcr_bid_plan import BidPlanProducer, OptimizationMetric, PlanDiagnostic

    producer_kind = "robust" if classification == "robust_candidate" else "other"
    return _build_fixed_fcr_plan_from_decisions(
        plan_id=f"{problem.problem_id}-{classification}-plan-v1",
        energy_schedule_id=f"{problem.problem_id}-energy-v1",
        fcr_schedule_id=f"{problem.problem_id}-fcr-v1",
        producer=BidPlanProducer(
            producer_id="open-energy-lab-fcr-rolling-bidder",
            producer_kind=producer_kind,
            producer_version=f"feature-015-{classification}-v1",
            configuration_fingerprint=problem.rolling_problem_fingerprint,
            configuration_unavailable_reason=None,
        ),
        information_cutoff_utc=problem.information_cutoff_utc,
        time_contract=problem.current_time_contract,
        decisions=decisions,
        producer_input_fingerprints={
            **dict(problem.producer_input_fingerprints),
            "rolling_problem": problem.rolling_problem_fingerprint,
        },
        solve_status=solver.solve_status,
        objective=OptimizationMetric(
            availability="available",
            value=solver.objective_value_eur,
            unit="EUR",
            unavailable_reason=None,
            meaning="optimization_objective",
        ),
        objective_bound=OptimizationMetric(
            availability=("available" if solver.best_upper_bound_eur is not None else "unavailable"),
            value=solver.best_upper_bound_eur,
            unit=("EUR" if solver.best_upper_bound_eur is not None else None),
            unavailable_reason=(None if solver.best_upper_bound_eur is not None else "same-solve bound unavailable"),
            meaning="optimization_bound",
        ),
        diagnostics=(
            PlanDiagnostic(
                code="feature_015_plan_classification",
                severity="info",
                field_path="plan_classification",
                message=f"rolling output is classified {classification}",
                evidence_refs=(f"sha256:{problem.rolling_problem_fingerprint}",),
            ),
        ),
        energy_schedule_source=(
            "arbitrage_only" if classification == "arbitrage_only" else "fixed"
        ),
        accepted_volume_ref_prefix=f"{problem.problem_id}:accepted_fcr",
        capacity_price_ref_prefix=f"{problem.problem_id}:fcr_price",
    )


def _rolling_incumbent_is_accepted(
    *,
    solve_status: str,
    has_incumbent: bool,
    solve_policy: RobustFCRSolvePolicy,
) -> bool:
    """Apply the pre-solve feasible-incumbent opt-in without backend inference."""

    return has_incumbent and (
        solve_status == "optimal"
        or (
            solve_status == "feasible"
            and solve_policy.allow_feasible_incumbent_plan
        )
    )


def solve_robust_fcr_rolling_bid(
    problem: RobustFCRRollingBiddingProblem,
) -> RobustFCRRollingSolveResult:
    """Solve one additive rolling frame through the shared lazy HiGHS adapter."""

    if not isinstance(problem, RobustFCRRollingBiddingProblem):
        raise RollingFCRValidationError("problem has the wrong contract type")
    from ._robust_fcr_formulation import (
        assemble_arbitrage_only_model,
        assemble_rolling_0800_model,
    )
    from ._robust_fcr_solver import (
        extract_arbitrage_only_witness,
        extract_rolling_0800_witness,
        require_highs_backend,
        solve_assembled_model,
    )

    backend = require_highs_backend()
    if problem.profile.formulation_kind == "arbitrage_only":
        assembled = assemble_arbitrage_only_model(
            problem,
            pyomo_environ=backend.pyomo_environ,
        )
        extractor = extract_arbitrage_only_witness
        formulation_kind = "arbitrage_only"
    else:
        assembled = assemble_rolling_0800_model(
            problem,
            pyomo_environ=backend.pyomo_environ,
        )
        extractor = extract_rolling_0800_witness
        formulation_kind = "restriction"
    raw = solve_assembled_model(
        assembled,
        problem.solve_policy,
        backend=backend,
        witness_extractor=extractor,
    )
    gap = _normalize_maximization_gap(
        raw.objective_value_eur,
        raw.best_upper_bound_eur,
        problem.solve_policy,
    )
    upper_bound = None if gap.inconsistent_bound else raw.best_upper_bound_eur
    incumbent_accepted = _rolling_incumbent_is_accepted(
        solve_status=raw.solve_status,
        has_incumbent=raw.has_incumbent,
        solve_policy=problem.solve_policy,
    )
    solver = SolverEvidence(
        solve_status=raw.solve_status,
        termination_status=raw.termination_status,
        has_incumbent=raw.has_incumbent,
        incumbent_accepted=incumbent_accepted,
        objective_value_eur=raw.objective_value_eur,
        best_upper_bound_eur=upper_bound,
        absolute_gap_eur=gap.absolute_gap_eur,
        relative_gap=gap.relative_gap,
        solver_name=raw.solver_name,
        solver_version=raw.solver_version,
        pyomo_version=raw.pyomo_version,
        highspy_version=raw.highspy_version,
        configured_options=raw.configured_options,
        model_cardinality=raw.model_cardinality,
        runtime_seconds=raw.runtime_seconds,
    )
    decisions: RobustFCRDecisions | None = None
    objective: ObjectiveBreakdown | None = None
    audit: FeasibilityAudit | None = None
    plan = None
    diagnostics = [str(value.get("code", "solver_diagnostic")) for value in raw.diagnostics]
    if raw.has_incumbent and raw.witness is not None and raw.objective_value_eur is not None:
        decisions, _ = _canonicalize_witness_decisions(raw.witness)
        objective = _objective_breakdown(problem, raw.witness, raw.objective_value_eur)
        audit = _independent_witness_audit(problem, raw.witness, decisions)
        if objective.reconciliation_residual_eur > problem.solve_policy.objective_comparison_absolute_tolerance_eur:
            diagnostics.append("objective_reconciliation_failed")
        if not audit.passes_deployability_audit:
            diagnostics.append("rolling_feasibility_audit_failed")
        if incumbent_accepted and audit.passes_deployability_audit and objective.reconciliation_residual_eur <= problem.solve_policy.objective_comparison_absolute_tolerance_eur:
            plan = _build_plan(
                problem,
                decisions,
                solver,
                problem.profile.plan_classification,
            )
    return RobustFCRRollingSolveResult(
        problem_fingerprint=problem.rolling_problem_fingerprint,
        profile_fingerprint=problem.profile.profile_fingerprint,
        formulation_kind=formulation_kind,
        solver=solver,
        objective=objective,
        fixed_tail_objective_eur=problem.fixed_tail_objective_eur,
        decisions=decisions,
        feasibility_audit=audit,
        plan_classification=problem.profile.plan_classification,
        plan=plan,
        diagnostics=tuple(diagnostics),
        runtime_metadata={
            "runtime_seconds": raw.runtime_seconds,
            "backend": _thaw(raw.runtime_metadata),
        },
    )


__all__ = [
    "ROBUST_FCR_ACCEPTED_FIXINGS_VERSION",
    "ROBUST_FCR_ROLLING_PROBLEM_VERSION",
    "ROBUST_FCR_ROLLING_RESULT_VERSION",
    "RobustFCRAcceptedDecisionFixings",
    "RobustFCRRollingBiddingProblem",
    "RobustFCRRollingSolveResult",
    "build_robust_fcr_rolling_problem",
    "extract_accepted_predecessor_fixings",
    "solve_robust_fcr_rolling_bid",
]
