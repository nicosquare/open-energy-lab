"""Strict offline reference evidence and comparison for robust FCR bidding.

This module is safe to import without Pyomo or a solver.  It reads only the
fixture path explicitly supplied by the caller.  Mathematical-programming
dependencies are loaded lazily only when joint certification is requested.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .robust_fcr_bidding import (
    DEPLOYABILITY_THRESHOLD,
    ROBUST_FCR_BIDDING_PROBLEM_VERSION,
    RecoveryWindowActivationBudget,
    RobustFCRBatteryParameters,
    RobustFCRBiddingProblem,
    RobustFCRFormulationProfile,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRSolveResult,
    RobustFCRUncertaintyProfile,
    RobustFCRValidationError,
    TerminalStoredEnergyRule,
    _deep_freeze,
    _fingerprint,
    _finite,
    _finite_tuple,
    _non_empty,
    _non_negative,
    _sha256,
    _thaw,
    build_robust_fcr_bidding_problem,
    build_robust_fcr_time_contract,
    derive_non_intraday_horizon_budget,
)


REFERENCE_FIXTURE_SCHEMA_VERSION = "oel.robust-fcr-reference-restriction.v1"
REFERENCE_FIXTURE_ID = "robust-storage-bidding-2023-06-18-restriction-v1"
REFERENCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
REFERENCE_RESULT_PATH = (
    "baselines/robust_storage_bidding/results/02/2023-06-18.json"
)
REFERENCE_RESULT_SHA256 = (
    "8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6"
)
REFERENCE_RESULT_BYTE_COUNT = 6653
REFERENCE_PRECISION_POLICY_ID = "joint-rounded-restriction-certificate-v1"
REFERENCE_COMPARISON_STATUSES = (
    "exact",
    "source_precision_compatible",
    "alternative_optimum_compatible",
    "mismatch",
    "unavailable",
)

_TOP_LEVEL_SECTIONS = {
    "schema_version",
    "fixture_id",
    "reference_provenance",
    "evaluation_fixture_reference",
    "problem",
    "reference_formulation",
    "recorded_result",
    "precision_policy",
    "unavailable_fields",
    "redistribution_status",
    "fixture_fingerprint",
}


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RobustFCRValidationError(f"{field_name} must be a JSON object")
    return {str(key): inner for key, inner in value.items()}


def _exact_mapping(
    value: object,
    *,
    field_name: str,
    expected_keys: set[str],
) -> dict[str, Any]:
    result = _mapping(value, field_name=field_name)
    if set(result) != expected_keys:
        unexpected = sorted(set(result) - expected_keys)
        missing = sorted(expected_keys - set(result))
        raise RobustFCRValidationError(
            f"{field_name} must use the exact section set; "
            f"missing={missing}, unexpected={unexpected}"
        )
    return result


def _sequence(value: object, *, field_name: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RobustFCRValidationError(f"{field_name} must be a JSON array")
    return tuple(value)


def _expected(value: object, expected: object, *, field_name: str) -> None:
    if value != expected:
        raise RobustFCRValidationError(
            f"{field_name} must equal {expected!r}, found {value!r}"
        )


def reference_decision_content_fingerprint(
    rounded_x0_kw: Sequence[float],
    rounded_xr_kw: Sequence[float],
) -> str:
    x0 = _finite_tuple(rounded_x0_kw, field_name="rounded_x0_kw", count=24)
    xr = _finite_tuple(rounded_xr_kw, field_name="rounded_xr_kw", count=6)
    if any(value < 0.0 for value in xr):
        raise RobustFCRValidationError("rounded_xr_kw must be non-negative")
    return _fingerprint(
        {
            "comparison_frame": "positive_is_discharge",
            "energy_unit": "kW",
            "fcr_sign": "non_negative_symmetric_capacity",
            "fcr_unit": "kW",
            "planning_to_energy": [index // 4 for index in range(96)],
            "planning_to_fcr": [index // 16 for index in range(96)],
            "rounded_x0_kw": list(x0),
            "rounded_xr_kw": list(xr),
        }
    )


@dataclass(frozen=True, slots=True)
class ReferenceUnavailableField:
    field_id: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_id", _non_empty(self.field_id, field_name="field_id"))
        object.__setattr__(self, "reason", _non_empty(self.reason, field_name="reason"))

    def to_dict(self) -> dict[str, object]:
        return {"field_id": self.field_id, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class ReferenceRecordedResult:
    objective_value_eur: float
    objective_bound_eur: float
    source_x0_sign: str
    rounded_x0_kw: tuple[float, ...]
    rounded_xr_kw: tuple[float, ...]
    saved_decimal_places: int
    solve_time_seconds: float
    recorded_slacks: Mapping[str, object]
    decision_content_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "objective_value_eur",
            _finite(self.objective_value_eur, field_name="objective_value_eur"),
        )
        object.__setattr__(
            self,
            "objective_bound_eur",
            _finite(self.objective_bound_eur, field_name="objective_bound_eur"),
        )
        if self.source_x0_sign != "positive_is_discharge":
            raise RobustFCRValidationError(
                "recorded source_x0_sign must be positive_is_discharge"
            )
        x0 = _finite_tuple(self.rounded_x0_kw, field_name="rounded_x0_kw", count=24)
        xr = _finite_tuple(self.rounded_xr_kw, field_name="rounded_xr_kw", count=6)
        if any(value < 0.0 for value in xr):
            raise RobustFCRValidationError("rounded_xr_kw must be non-negative")
        if self.saved_decimal_places != 3:
            raise RobustFCRValidationError("saved_decimal_places must equal 3")
        runtime = _non_negative(self.solve_time_seconds, field_name="solve_time_seconds")
        object.__setattr__(self, "rounded_x0_kw", x0)
        object.__setattr__(self, "rounded_xr_kw", xr)
        object.__setattr__(self, "solve_time_seconds", runtime)
        object.__setattr__(
            self,
            "recorded_slacks",
            _deep_freeze(self.recorded_slacks, field_name="recorded_slacks"),
        )
        object.__setattr__(
            self,
            "decision_content_fingerprint",
            reference_decision_content_fingerprint(x0, xr),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "objective_value_eur": self.objective_value_eur,
            "objective_bound_eur": self.objective_bound_eur,
            "source_x0_sign": self.source_x0_sign,
            "rounded_x0_kw": list(self.rounded_x0_kw),
            "rounded_xr_kw": list(self.rounded_xr_kw),
            "saved_decimal_places": self.saved_decimal_places,
            "solve_time_seconds": self.solve_time_seconds,
            "recorded_slacks": _thaw(self.recorded_slacks),
            "decision_content_fingerprint": self.decision_content_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class SourcePrecisionPolicy:
    policy_id: str
    interval_closure: str
    decision_decimal_places: int
    decision_half_unit_kw: float
    objective_decimal_places: int
    objective_half_unit_eur: float
    deployability_threshold: float
    deployability_rule: str
    certification_method: str
    policy_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.policy_id != REFERENCE_PRECISION_POLICY_ID:
            raise RobustFCRValidationError("unsupported source precision policy_id")
        if self.interval_closure != "closed_outer":
            raise RobustFCRValidationError("source intervals must be closed_outer")
        if self.decision_decimal_places != 3 or self.objective_decimal_places != 3:
            raise RobustFCRValidationError("source precision must record three decimals")
        decision_half = _non_negative(
            self.decision_half_unit_kw,
            field_name="decision_half_unit_kw",
        )
        objective_half = _non_negative(
            self.objective_half_unit_eur,
            field_name="objective_half_unit_eur",
        )
        if decision_half != 0.0005 or objective_half != 0.0005:
            raise RobustFCRValidationError("source half-unit precision must equal 0.0005")
        threshold = _non_negative(
            self.deployability_threshold,
            field_name="deployability_threshold",
        )
        if threshold != DEPLOYABILITY_THRESHOLD:
            raise RobustFCRValidationError(
                f"deployability threshold must equal {DEPLOYABILITY_THRESHOLD}"
            )
        if self.deployability_rule != "absolute_in_each_canonical_unit":
            raise RobustFCRValidationError("unsupported deployability threshold rule")
        if (
            self.certification_method
            != "one_joint_restriction_feasibility_and_objective_interval"
        ):
            raise RobustFCRValidationError("unsupported certification method")
        object.__setattr__(self, "decision_half_unit_kw", decision_half)
        object.__setattr__(self, "objective_half_unit_eur", objective_half)
        object.__setattr__(self, "deployability_threshold", threshold)
        object.__setattr__(self, "policy_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "interval_closure": self.interval_closure,
            "decision_decimal_places": self.decision_decimal_places,
            "decision_half_unit_kw": self.decision_half_unit_kw,
            "objective_decimal_places": self.objective_decimal_places,
            "objective_half_unit_eur": self.objective_half_unit_eur,
            "deployability_threshold": {
                "value": self.deployability_threshold,
                "rule": self.deployability_rule,
            },
            "certification_method": self.certification_method,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "policy_fingerprint": self.policy_fingerprint}


@dataclass(frozen=True, slots=True)
class RobustFCRReferenceFixture:
    schema_version: str
    fixture_id: str
    reference_provenance: Mapping[str, object]
    evaluation_fixture_reference: Mapping[str, object]
    problem: Mapping[str, object]
    reference_formulation: RobustFCRFormulationProfile
    recorded_result: ReferenceRecordedResult
    precision_policy: SourcePrecisionPolicy
    unavailable_fields: tuple[ReferenceUnavailableField, ...]
    redistribution_status: Mapping[str, str]
    fixture_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != REFERENCE_FIXTURE_SCHEMA_VERSION:
            raise RobustFCRValidationError("unsupported reference fixture schema_version")
        if self.fixture_id != REFERENCE_FIXTURE_ID:
            raise RobustFCRValidationError("unsupported reference fixture_id")
        if not isinstance(self.reference_formulation, RobustFCRFormulationProfile):
            raise RobustFCRValidationError("reference_formulation has the wrong type")
        if self.reference_formulation.kind != "restriction":
            raise RobustFCRValidationError("reference formulation must be restriction")
        if not isinstance(self.recorded_result, ReferenceRecordedResult):
            raise RobustFCRValidationError("recorded_result has the wrong type")
        if not isinstance(self.precision_policy, SourcePrecisionPolicy):
            raise RobustFCRValidationError("precision_policy has the wrong type")
        unavailable = tuple(self.unavailable_fields)
        if not unavailable or any(
            not isinstance(value, ReferenceUnavailableField) for value in unavailable
        ):
            raise RobustFCRValidationError("unavailable_fields must be non-empty")
        if len({value.field_id for value in unavailable}) != len(unavailable):
            raise RobustFCRValidationError("unavailable field IDs must be unique")
        object.__setattr__(
            self,
            "reference_provenance",
            _deep_freeze(self.reference_provenance, field_name="reference_provenance"),
        )
        object.__setattr__(
            self,
            "evaluation_fixture_reference",
            _deep_freeze(
                self.evaluation_fixture_reference,
                field_name="evaluation_fixture_reference",
            ),
        )
        object.__setattr__(
            self,
            "problem",
            _deep_freeze(self.problem, field_name="problem"),
        )
        object.__setattr__(self, "unavailable_fields", unavailable)
        object.__setattr__(
            self,
            "redistribution_status",
            _deep_freeze(self.redistribution_status, field_name="redistribution_status"),
        )
        object.__setattr__(self, "fixture_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "fixture_id": self.fixture_id,
            "reference_provenance": _thaw(self.reference_provenance),
            "evaluation_fixture_reference": _thaw(
                self.evaluation_fixture_reference
            ),
            "problem": _thaw(self.problem),
            "reference_formulation": self.reference_formulation.to_dict(),
            "recorded_result": self.recorded_result.to_dict(),
            "precision_policy": self.precision_policy.to_dict(),
            "unavailable_fields": [
                value.to_dict() for value in self.unavailable_fields
            ],
            "redistribution_status": _thaw(self.redistribution_status),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "fixture_fingerprint": self.fixture_fingerprint}


def _validate_provenance(raw: object) -> dict[str, object]:
    value = _exact_mapping(
        raw,
        field_name="reference_provenance",
        expected_keys={
            "reference_revision",
            "source_paths",
            "generation_working_directory",
            "generation_command",
            "original_result_path",
            "original_result_byte_count",
            "original_result_sha256",
            "normalization_command",
            "generated_result_revision_status",
        },
    )
    _expected(value["reference_revision"], REFERENCE_REVISION, field_name="reference_revision")
    _expected(value["original_result_path"], REFERENCE_RESULT_PATH, field_name="original_result_path")
    _expected(
        value["original_result_byte_count"],
        REFERENCE_RESULT_BYTE_COUNT,
        field_name="original_result_byte_count",
    )
    _expected(
        value["original_result_sha256"],
        REFERENCE_RESULT_SHA256,
        field_name="original_result_sha256",
    )
    _expected(
        value["generated_result_revision_status"],
        "digest_pinned_generated_file_not_tracked_at_reference_revision",
        field_name="generated_result_revision_status",
    )
    source_paths = _sequence(value["source_paths"], field_name="source_paths")
    required_paths = {
        "baselines/robust_storage_bidding/code/01_datastruct.jl",
        "baselines/robust_storage_bidding/code/02_model.jl",
        "baselines/robust_storage_bidding/code/12.jl",
        REFERENCE_RESULT_PATH,
    }
    if set(source_paths) != required_paths:
        raise RobustFCRValidationError("reference source_paths do not match the pinned inventory")
    for name in (
        "generation_working_directory",
        "generation_command",
        "normalization_command",
    ):
        _non_empty(value[name], field_name=name)
    return value


def _validate_evaluation_reference(raw: object) -> dict[str, object]:
    value = _exact_mapping(
        raw,
        field_name="evaluation_fixture_reference",
        expected_keys={"fixture_id", "relative_path", "fixture_fingerprint"},
    )
    _expected(
        value["fixture_id"],
        "robust-storage-bidding-experiment-2-2023-06-18-v1",
        field_name="evaluation fixture_id",
    )
    _expected(
        value["relative_path"],
        "tests/fixtures/fcr_bid_evaluation/robust_storage_bidding_2023-06-18_aggregate_v1.json",
        field_name="evaluation relative_path",
    )
    _sha256(value["fixture_fingerprint"], field_name="evaluation fixture_fingerprint")
    return value


def _validate_problem(raw: object) -> dict[str, object]:
    value = _exact_mapping(
        raw,
        field_name="problem",
        expected_keys={
            "semantics_version",
            "information_cutoff_utc",
            "time_contract",
            "battery",
            "uncertainty",
            "terminal_rule",
            "prices",
            "solve_profile",
            "problem_fingerprint",
        },
    )
    _expected(
        value["semantics_version"],
        ROBUST_FCR_BIDDING_PROBLEM_VERSION,
        field_name="problem.semantics_version",
    )
    cutoff = _non_empty(value["information_cutoff_utc"], field_name="information_cutoff_utc")
    if not cutoff.endswith("Z"):
        raise RobustFCRValidationError("information_cutoff_utc must end in Z")
    time_contract = _exact_mapping(
        value["time_contract"],
        field_name="problem.time_contract",
        expected_keys={
            "delivery_date",
            "market_timezone",
            "start_utc",
            "end_utc",
            "planning_interval_count",
            "planning_resolution_hours",
            "energy_interval_count",
            "energy_resolution_hours",
            "fcr_interval_count",
            "fcr_block_hours",
            "planning_intervals_per_energy_interval",
            "planning_intervals_per_fcr_block",
        },
    )
    constants = {
        "delivery_date": "2023-06-18",
        "market_timezone": "Europe/Paris",
        "start_utc": "2023-06-17T22:00:00Z",
        "end_utc": "2023-06-18T22:00:00Z",
        "planning_interval_count": 96,
        "planning_resolution_hours": 0.25,
        "energy_interval_count": 24,
        "energy_resolution_hours": 1.0,
        "fcr_interval_count": 6,
        "fcr_block_hours": 4.0,
        "planning_intervals_per_energy_interval": 4,
        "planning_intervals_per_fcr_block": 16,
    }
    for name, expected in constants.items():
        _expected(time_contract[name], expected, field_name=f"time_contract.{name}")
    battery = _exact_mapping(
        value["battery"],
        field_name="problem.battery",
        expected_keys={
            "source_power_sign",
            "maximum_charge_power_kw",
            "maximum_discharge_power_kw",
            "minimum_stored_energy_kwh",
            "maximum_stored_energy_kwh",
            "initial_stored_energy_kwh",
            "charge_efficiency",
            "discharge_efficiency",
        },
    )
    _expected(battery["source_power_sign"], "positive_is_discharge", field_name="battery.source_power_sign")
    RobustFCRBatteryParameters(
        maximum_charge_power_kw=battery["maximum_charge_power_kw"],
        maximum_discharge_power_kw=battery["maximum_discharge_power_kw"],
        minimum_stored_energy_kwh=battery["minimum_stored_energy_kwh"],
        maximum_stored_energy_kwh=battery["maximum_stored_energy_kwh"],
        initial_stored_energy_kwh=battery["initial_stored_energy_kwh"],
        charge_efficiency=battery["charge_efficiency"],
        discharge_efficiency=battery["discharge_efficiency"],
    )
    uncertainty = _exact_mapping(
        value["uncertainty"],
        field_name="problem.uncertainty",
        expected_keys={
            "recovery_activation_budget_hours",
            "recovery_window_hours",
            "horizon_activation_budget_hours",
            "horizon_hours",
            "pointwise_activation_bounds",
            "derivation_rule",
        },
    )
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=uncertainty[
            "recovery_activation_budget_hours"
        ],
        recovery_window_hours=uncertainty["recovery_window_hours"],
        pointwise_activation_lower=_sequence(
            uncertainty["pointwise_activation_bounds"],
            field_name="pointwise_activation_bounds",
        )[0],
        pointwise_activation_upper=_sequence(
            uncertainty["pointwise_activation_bounds"],
            field_name="pointwise_activation_bounds",
        )[1],
    )
    horizon = derive_non_intraday_horizon_budget(
        recovery,
        horizon_hours=uncertainty["horizon_hours"],
    )
    _expected(
        uncertainty["horizon_activation_budget_hours"],
        horizon.horizon_activation_budget_hours,
        field_name="uncertainty.horizon_activation_budget_hours",
    )
    _expected(
        uncertainty["derivation_rule"],
        horizon.derivation_rule,
        field_name="uncertainty.derivation_rule",
    )
    terminal = _exact_mapping(
        value["terminal_rule"],
        field_name="problem.terminal_rule",
        expected_keys={
            "minimum_terminal_stored_energy_kwh",
            "allow_penalized_shortfall",
            "shortfall_penalty_eur_per_kwh",
            "source_formula",
        },
    )
    _expected(
        terminal["minimum_terminal_stored_energy_kwh"],
        53.327556325823224,
        field_name="terminal minimum",
    )
    TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=terminal[
            "minimum_terminal_stored_energy_kwh"
        ],
        allow_penalized_shortfall=terminal["allow_penalized_shortfall"],
        shortfall_penalty_eur_per_kwh=terminal[
            "shortfall_penalty_eur_per_kwh"
        ],
        rule_id="reference-terminal-v1",
    )
    _non_empty(terminal["source_formula"], field_name="terminal source_formula")
    prices = _exact_mapping(
        value["prices"],
        field_name="problem.prices",
        expected_keys={
            "day_ahead_unit",
            "day_ahead_energy_prices",
            "fcr_capacity_unit",
            "fcr_capacity_prices",
        },
    )
    _expected(prices["day_ahead_unit"], "EUR/kWh", field_name="day_ahead_unit")
    _expected(prices["fcr_capacity_unit"], "EUR/kW/4h-block", field_name="fcr_capacity_unit")
    _finite_tuple(prices["day_ahead_energy_prices"], field_name="day_ahead_energy_prices", count=24)
    _finite_tuple(prices["fcr_capacity_prices"], field_name="fcr_capacity_prices", count=6)
    solve_profile = _exact_mapping(
        value["solve_profile"],
        field_name="problem.solve_profile",
        expected_keys={
            "reference_solver",
            "time_limit_seconds",
            "explicit_tolerances_status",
            "intraday_trading",
            "u_restrict",
        },
    )
    expected_profile = {
        "reference_solver": "Gurobi",
        "time_limit_seconds": 3600.0,
        "explicit_tolerances_status": "not_recorded_source_defaults",
        "intraday_trading": False,
        "u_restrict": 0.0,
    }
    for name, expected in expected_profile.items():
        _expected(solve_profile[name], expected, field_name=f"solve_profile.{name}")
    recorded_fingerprint = _sha256(
        value["problem_fingerprint"],
        field_name="problem.problem_fingerprint",
    )
    fingerprint_payload = dict(value)
    fingerprint_payload.pop("problem_fingerprint")
    if recorded_fingerprint != _fingerprint(fingerprint_payload):
        raise RobustFCRValidationError("problem fingerprint mismatch")
    return value


def _parse_recorded_result(raw: object) -> ReferenceRecordedResult:
    value = _exact_mapping(
        raw,
        field_name="recorded_result",
        expected_keys={
            "objective_value_eur",
            "objective_bound_eur",
            "source_x0_sign",
            "rounded_x0_kw",
            "rounded_xr_kw",
            "saved_decimal_places",
            "solve_time_seconds",
            "recorded_slacks",
            "decision_content_fingerprint",
        },
    )
    result = ReferenceRecordedResult(
        objective_value_eur=value["objective_value_eur"],
        objective_bound_eur=value["objective_bound_eur"],
        source_x0_sign=value["source_x0_sign"],
        rounded_x0_kw=tuple(value["rounded_x0_kw"]),
        rounded_xr_kw=tuple(value["rounded_xr_kw"]),
        saved_decimal_places=value["saved_decimal_places"],
        solve_time_seconds=value["solve_time_seconds"],
        recorded_slacks=value["recorded_slacks"],
    )
    if value["decision_content_fingerprint"] != result.decision_content_fingerprint:
        raise RobustFCRValidationError("recorded decision_content_fingerprint mismatch")
    return result


def _parse_precision_policy(raw: object) -> SourcePrecisionPolicy:
    value = _exact_mapping(
        raw,
        field_name="precision_policy",
        expected_keys={
            "policy_id",
            "interval_closure",
            "decision_decimal_places",
            "decision_half_unit_kw",
            "objective_decimal_places",
            "objective_half_unit_eur",
            "deployability_threshold",
            "certification_method",
            "policy_fingerprint",
        },
    )
    threshold = _exact_mapping(
        value["deployability_threshold"],
        field_name="precision_policy.deployability_threshold",
        expected_keys={"value", "rule"},
    )
    policy = SourcePrecisionPolicy(
        policy_id=value["policy_id"],
        interval_closure=value["interval_closure"],
        decision_decimal_places=value["decision_decimal_places"],
        decision_half_unit_kw=value["decision_half_unit_kw"],
        objective_decimal_places=value["objective_decimal_places"],
        objective_half_unit_eur=value["objective_half_unit_eur"],
        deployability_threshold=threshold["value"],
        deployability_rule=threshold["rule"],
        certification_method=value["certification_method"],
    )
    if value["policy_fingerprint"] != policy.policy_fingerprint:
        raise RobustFCRValidationError("precision policy fingerprint mismatch")
    return policy


def load_robust_fcr_reference_fixture(
    path: str | Path,
) -> RobustFCRReferenceFixture:
    """Load exactly one caller-selected normalized fixture without discovery."""

    selected = Path(path)
    try:
        raw_bytes = selected.read_bytes()
    except OSError as exc:
        raise RobustFCRValidationError(
            f"reference fixture is unavailable at explicit path {selected}: {exc}"
        ) from exc
    try:
        raw = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RobustFCRValidationError(
            f"reference fixture must be UTF-8 JSON: {exc}"
        ) from exc
    top = _exact_mapping(
        raw,
        field_name="reference fixture",
        expected_keys=_TOP_LEVEL_SECTIONS,
    )
    provenance = _validate_provenance(top["reference_provenance"])
    evaluation_reference = _validate_evaluation_reference(
        top["evaluation_fixture_reference"]
    )
    problem = _validate_problem(top["problem"])
    expected_profile = RobustFCRFormulationProfile.for_kind("restriction")
    formulation_raw = _mapping(
        top["reference_formulation"],
        field_name="reference_formulation",
    )
    if formulation_raw != expected_profile.to_dict():
        raise RobustFCRValidationError(
            "reference_formulation does not match the pinned restriction profile"
        )
    recorded = _parse_recorded_result(top["recorded_result"])
    precision = _parse_precision_policy(top["precision_policy"])
    unavailable_raw = _sequence(
        top["unavailable_fields"],
        field_name="unavailable_fields",
    )
    unavailable = tuple(
        ReferenceUnavailableField(
            **_exact_mapping(
                item,
                field_name=f"unavailable_fields[{index}]",
                expected_keys={"field_id", "reason"},
            )
        )
        for index, item in enumerate(unavailable_raw)
    )
    redistribution = _exact_mapping(
        top["redistribution_status"],
        field_name="redistribution_status",
        expected_keys={
            "normalized_problem_and_result",
            "original_result",
            "activation_data",
        },
    )
    expected_redistribution = {
        "normalized_problem_and_result": "committed_derived_evidence",
        "original_result": "digest_only",
        "activation_data": "absent_external_evaluation_only",
    }
    if redistribution != expected_redistribution:
        raise RobustFCRValidationError("unsupported redistribution_status")
    fixture = RobustFCRReferenceFixture(
        schema_version=top["schema_version"],
        fixture_id=top["fixture_id"],
        reference_provenance=provenance,
        evaluation_fixture_reference=evaluation_reference,
        problem=problem,
        reference_formulation=expected_profile,
        recorded_result=recorded,
        precision_policy=precision,
        unavailable_fields=unavailable,
        redistribution_status=redistribution,
    )
    if top["fixture_fingerprint"] != fixture.fixture_fingerprint:
        raise RobustFCRValidationError("reference fixture fingerprint mismatch")
    return fixture


def build_robust_fcr_reference_problem(
    fixture: RobustFCRReferenceFixture,
    *,
    solve_policy: RobustFCRSolvePolicy,
) -> RobustFCRBiddingProblem:
    """Reconstruct exact source inputs with a separate caller-owned policy."""

    if not isinstance(fixture, RobustFCRReferenceFixture):
        raise RobustFCRValidationError("fixture has the wrong contract type")
    if not isinstance(solve_policy, RobustFCRSolvePolicy):
        raise RobustFCRValidationError(
            "solve_policy must be a complete RobustFCRSolvePolicy"
        )
    payload = fixture.problem
    battery_values = payload["battery"]
    battery = RobustFCRBatteryParameters(
        maximum_charge_power_kw=battery_values["maximum_charge_power_kw"],
        maximum_discharge_power_kw=battery_values["maximum_discharge_power_kw"],
        minimum_stored_energy_kwh=battery_values["minimum_stored_energy_kwh"],
        maximum_stored_energy_kwh=battery_values["maximum_stored_energy_kwh"],
        initial_stored_energy_kwh=battery_values["initial_stored_energy_kwh"],
        charge_efficiency=battery_values["charge_efficiency"],
        discharge_efficiency=battery_values["discharge_efficiency"],
    )
    time_values = payload["time_contract"]
    time_contract = build_robust_fcr_time_contract(
        delivery_date=date.fromisoformat(time_values["delivery_date"]),
        market_timezone=time_values["market_timezone"],
    )
    if (
        time_contract.delivery_period.start_utc.isoformat().replace("+00:00", "Z")
        != time_values["start_utc"]
        or time_contract.delivery_period.end_utc.isoformat().replace("+00:00", "Z")
        != time_values["end_utc"]
    ):
        raise RobustFCRValidationError("fixture time contract does not reconstruct")
    price_values = payload["prices"]
    prices = RobustFCRPriceInputs(
        day_ahead_energy_prices_eur_per_kwh=tuple(
            price_values["day_ahead_energy_prices"]
        ),
        fcr_capacity_prices_eur_per_kw_block=tuple(
            price_values["fcr_capacity_prices"]
        ),
        energy_interval_refs=tuple(
            f"reference_fixture:day_ahead:{index}" for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"reference_fixture:fcr_capacity:{index}" for index in range(6)
        ),
    )
    uncertainty_values = payload["uncertainty"]
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=uncertainty_values[
            "recovery_activation_budget_hours"
        ],
        recovery_window_hours=uncertainty_values["recovery_window_hours"],
    )
    horizon = derive_non_intraday_horizon_budget(recovery)
    if (
        horizon.horizon_activation_budget_hours
        != uncertainty_values["horizon_activation_budget_hours"]
    ):
        raise RobustFCRValidationError("fixture uncertainty budget does not reconstruct")
    uncertainty = RobustFCRUncertaintyProfile(
        recovery_window=recovery,
        horizon_wide=horizon,
    )
    terminal_values = payload["terminal_rule"]
    terminal = TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=terminal_values[
            "minimum_terminal_stored_energy_kwh"
        ],
        allow_penalized_shortfall=terminal_values["allow_penalized_shortfall"],
        shortfall_penalty_eur_per_kwh=terminal_values[
            "shortfall_penalty_eur_per_kwh"
        ],
        rule_id="robust-storage-bidding-reference-terminal-v1",
    )
    cutoff = datetime.fromisoformat(
        str(payload["information_cutoff_utc"]).replace("Z", "+00:00")
    )
    return build_robust_fcr_bidding_problem(
        problem_id="robust-storage-bidding-2023-06-18-native-v1",
        battery=battery,
        time_contract=time_contract,
        prices=prices,
        uncertainty=uncertainty,
        terminal_rule=terminal,
        solve_policy=solve_policy,
        information_cutoff_utc=cutoff,
        producer_input_fingerprints={
            "reference_fixture": fixture.fixture_fingerprint,
            "reference_problem": payload["problem_fingerprint"],
            "reference_prices": prices.price_input_fingerprint,
            "reference_formulation": (
                fixture.reference_formulation.formulation_fingerprint
            ),
        },
        provenance={
            "fixture_id": fixture.fixture_id,
            "fixture_schema_version": fixture.schema_version,
            "reference_revision": fixture.reference_provenance[
                "reference_revision"
            ],
            "generated_result_sha256": fixture.reference_provenance[
                "original_result_sha256"
            ],
            "native_solve_policy_ownership": "caller_supplied",
        },
    )
