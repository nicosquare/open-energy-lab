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
from decimal import Decimal
from functools import partial
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any

from open_energy_lab.core.validation import mapping
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


_mapping = partial(mapping, error=RobustFCRValidationError)


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


def reference_energy_content_fingerprint(
    source_positive_discharge_kw: Sequence[float],
) -> str:
    """Fingerprint hourly energy decisions in the declared comparison frame."""

    values = _finite_tuple(
        source_positive_discharge_kw,
        field_name="source_positive_discharge_kw",
        count=24,
    )
    return _fingerprint(
        {
            "comparison_frame": "positive_is_discharge",
            "resolution": "PT1H",
            "unit": "kW",
            "values": list(values),
        }
    )


def reference_fcr_content_fingerprint(
    symmetric_capacity_kw: Sequence[float],
) -> str:
    """Fingerprint four-hour symmetric FCR decisions without producer lineage."""

    values = _finite_tuple(
        symmetric_capacity_kw,
        field_name="symmetric_capacity_kw",
        count=6,
    )
    if any(value < 0.0 for value in values):
        raise RobustFCRValidationError("symmetric_capacity_kw must be non-negative")
    return _fingerprint(
        {
            "comparison_frame": "non_negative_symmetric_capacity",
            "resolution": "PT4H",
            "unit": "kW",
            "values": list(values),
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


@dataclass(frozen=True, slots=True)
class ReferenceDecisionInterval:
    """One closed source-rounding interval in the common source frame."""

    field_id: str
    decision_kind: str
    index: int
    displayed_value: float
    lower: float
    upper: float
    unit: str = "kW"
    interval_closure: str = "closed_outer"

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_id", _non_empty(self.field_id, field_name="field_id"))
        if self.decision_kind not in {"energy_x0", "fcr_xr"}:
            raise RobustFCRValidationError("unsupported reference decision_kind")
        maximum_index = 23 if self.decision_kind == "energy_x0" else 5
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise RobustFCRValidationError("reference decision index must be an integer")
        if not 0 <= self.index <= maximum_index:
            raise RobustFCRValidationError("reference decision index is out of range")
        displayed = _finite(self.displayed_value, field_name="displayed_value")
        lower = _finite(self.lower, field_name="lower")
        upper = _finite(self.upper, field_name="upper")
        if lower > displayed or displayed > upper:
            raise RobustFCRValidationError(
                "reference decision interval must contain its displayed value"
            )
        if self.decision_kind == "fcr_xr" and lower < 0.0:
            raise RobustFCRValidationError("FCR source interval must be non-negative")
        if self.unit != "kW" or self.interval_closure != "closed_outer":
            raise RobustFCRValidationError("unsupported reference interval semantics")
        object.__setattr__(self, "displayed_value", displayed)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    def to_dict(self) -> dict[str, object]:
        return {
            "field_id": self.field_id,
            "decision_kind": self.decision_kind,
            "index": self.index,
            "displayed_value": self.displayed_value,
            "lower": self.lower,
            "upper": self.upper,
            "unit": self.unit,
            "interval_closure": self.interval_closure,
        }


@dataclass(frozen=True, slots=True)
class ReferenceCertificationRequest:
    """Semantic inputs to one joint rounded-decision restriction certificate."""

    fixture_fingerprint: str
    native_result_fingerprint: str
    native_policy_fingerprint: str
    decision_intervals: tuple[ReferenceDecisionInterval, ...]
    source_objective_interval: tuple[float, float]
    native_objective_equivalence_band: tuple[float, float]
    certification_objective_interval: tuple[float, float] | None
    objective_comparison_allowance_eur: float
    maximum_deployability_slack: float
    objective_equivalence_possible: bool
    request_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "fixture_fingerprint",
            "native_result_fingerprint",
            "native_policy_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), field_name=name))
        intervals = tuple(self.decision_intervals)
        if len(intervals) != 30 or any(
            not isinstance(value, ReferenceDecisionInterval) for value in intervals
        ):
            raise RobustFCRValidationError(
                "certification requires exactly 30 reference decision intervals"
            )
        expected_ids = tuple(f"x0[{index}]" for index in range(24)) + tuple(
            f"xr[{index}]" for index in range(6)
        )
        if tuple(value.field_id for value in intervals) != expected_ids:
            raise RobustFCRValidationError(
                "certification decision intervals must use canonical order"
            )
        source = _numeric_interval(
            self.source_objective_interval,
            field_name="source_objective_interval",
        )
        native = _numeric_interval(
            self.native_objective_equivalence_band,
            field_name="native_objective_equivalence_band",
        )
        certification = None
        if self.certification_objective_interval is not None:
            certification = _numeric_interval(
                self.certification_objective_interval,
                field_name="certification_objective_interval",
            )
            expected_intersection = (
                max(source[0], native[0]),
                min(source[1], native[1]),
            )
            if certification != expected_intersection:
                raise RobustFCRValidationError(
                    "certification objective interval must be the source/native intersection"
                )
        if self.objective_equivalence_possible != (certification is not None):
            raise RobustFCRValidationError(
                "objective_equivalence_possible must match interval intersection"
            )
        allowance = _non_negative(
            self.objective_comparison_allowance_eur,
            field_name="objective_comparison_allowance_eur",
        )
        maximum_slack = _non_negative(
            self.maximum_deployability_slack,
            field_name="maximum_deployability_slack",
        )
        if maximum_slack != DEPLOYABILITY_THRESHOLD:
            raise RobustFCRValidationError(
                f"maximum_deployability_slack must equal {DEPLOYABILITY_THRESHOLD}"
            )
        object.__setattr__(self, "decision_intervals", intervals)
        object.__setattr__(self, "source_objective_interval", source)
        object.__setattr__(self, "native_objective_equivalence_band", native)
        object.__setattr__(self, "certification_objective_interval", certification)
        object.__setattr__(self, "objective_comparison_allowance_eur", allowance)
        object.__setattr__(self, "maximum_deployability_slack", maximum_slack)
        object.__setattr__(self, "request_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "fixture_fingerprint": self.fixture_fingerprint,
            "native_result_fingerprint": self.native_result_fingerprint,
            "native_policy_fingerprint": self.native_policy_fingerprint,
            "decision_intervals": [value.to_dict() for value in self.decision_intervals],
            "source_objective_interval": list(self.source_objective_interval),
            "native_objective_equivalence_band": list(
                self.native_objective_equivalence_band
            ),
            "certification_objective_interval": (
                list(self.certification_objective_interval)
                if self.certification_objective_interval is not None
                else None
            ),
            "objective_comparison_allowance_eur": (
                self.objective_comparison_allowance_eur
            ),
            "maximum_deployability_slack": self.maximum_deployability_slack,
            "objective_equivalence_possible": self.objective_equivalence_possible,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "request_fingerprint": self.request_fingerprint}


@dataclass(frozen=True, slots=True)
class JointReferenceCertificate:
    """Audited evidence for one simultaneous decision/objective box."""

    request_fingerprint: str
    solve_status: str
    joint_feasible: bool
    objective_equivalent: bool
    maximum_slack: float | None
    maximum_residual: float | None
    certified_objective_value_eur: float | None
    witness_fingerprint: str | None
    unavailable_reason: str | None
    certificate_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_fingerprint",
            _sha256(self.request_fingerprint, field_name="request_fingerprint"),
        )
        if self.solve_status not in {
            "optimal",
            "feasible",
            "no_solution",
            "infeasible",
            "unbounded",
            "failed",
            "unavailable",
        }:
            raise RobustFCRValidationError("unsupported certificate solve_status")
        if not isinstance(self.joint_feasible, bool) or not isinstance(
            self.objective_equivalent, bool
        ):
            raise RobustFCRValidationError("certificate booleans must be explicit")
        if not self.joint_feasible:
            if self.objective_equivalent:
                raise RobustFCRValidationError(
                    "an infeasible certificate cannot be objective-equivalent"
                )
            if any(
                value is not None
                for value in (
                    self.maximum_slack,
                    self.maximum_residual,
                    self.certified_objective_value_eur,
                    self.witness_fingerprint,
                )
            ):
                raise RobustFCRValidationError(
                    "a non-feasible certificate cannot carry witness evidence"
                )
        else:
            if self.solve_status not in {"optimal", "feasible"}:
                raise RobustFCRValidationError(
                    "a feasible certificate requires an accepted solve status"
                )
            slack = _non_negative(self.maximum_slack, field_name="maximum_slack")
            residual = _non_negative(
                self.maximum_residual,
                field_name="maximum_residual",
            )
            if slack > DEPLOYABILITY_THRESHOLD:
                raise RobustFCRValidationError(
                    "certificate deployability slack exceeds the 1e-6 limit"
                )
            if residual > DEPLOYABILITY_THRESHOLD:
                raise RobustFCRValidationError(
                    "certificate maximum residual exceeds the 1e-6 limit"
                )
            objective = _finite(
                self.certified_objective_value_eur,
                field_name="certified_objective_value_eur",
            )
            witness = _sha256(
                self.witness_fingerprint,
                field_name="witness_fingerprint",
            )
            object.__setattr__(self, "maximum_slack", slack)
            object.__setattr__(self, "maximum_residual", residual)
            object.__setattr__(self, "certified_objective_value_eur", objective)
            object.__setattr__(self, "witness_fingerprint", witness)
        if self.solve_status == "unavailable":
            object.__setattr__(
                self,
                "unavailable_reason",
                _non_empty(self.unavailable_reason, field_name="unavailable_reason"),
            )
        elif self.unavailable_reason is not None:
            raise RobustFCRValidationError(
                "unavailable_reason is valid only for unavailable certification"
            )
        object.__setattr__(
            self,
            "certificate_fingerprint",
            _fingerprint(self._payload()),
        )

    def _payload(self) -> dict[str, object]:
        return {
            "request_fingerprint": self.request_fingerprint,
            "solve_status": self.solve_status,
            "joint_feasible": self.joint_feasible,
            "objective_equivalent": self.objective_equivalent,
            "maximum_slack": self.maximum_slack,
            "maximum_residual": self.maximum_residual,
            "certified_objective_value_eur": self.certified_objective_value_eur,
            "witness_fingerprint": self.witness_fingerprint,
            "unavailable_reason": self.unavailable_reason,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "certificate_fingerprint": self.certificate_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RobustFCRReferenceFieldResult:
    """One visible native/source comparison without hidden coercion."""

    field_id: str
    status: str
    native_value: object | None
    source_value: object | None
    delta: float | None
    source_interval: tuple[float, float] | None
    source_evidence_role: str
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_id", _non_empty(self.field_id, field_name="field_id"))
        if self.status not in REFERENCE_COMPARISON_STATUSES:
            raise RobustFCRValidationError("unsupported reference field status")
        object.__setattr__(
            self,
            "source_evidence_role",
            _non_empty(self.source_evidence_role, field_name="source_evidence_role"),
        )
        if self.delta is not None:
            object.__setattr__(self, "delta", _finite(self.delta, field_name="delta"))
        if self.source_interval is not None:
            object.__setattr__(
                self,
                "source_interval",
                _numeric_interval(self.source_interval, field_name="source_interval"),
            )
        if self.status == "unavailable":
            object.__setattr__(
                self,
                "reason",
                _non_empty(self.reason, field_name="unavailable reason"),
            )
        elif self.reason is not None:
            object.__setattr__(self, "reason", _non_empty(self.reason, field_name="reason"))

    def to_dict(self) -> dict[str, object]:
        return {
            "field_id": self.field_id,
            "status": self.status,
            "native_value": self.native_value,
            "source_value": self.source_value,
            "delta": self.delta,
            "source_interval": (
                list(self.source_interval) if self.source_interval is not None else None
            ),
            "source_evidence_role": self.source_evidence_role,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RobustFCRReferenceComparison:
    """Complete offline comparison against the normalized Julia evidence."""

    fixture_fingerprint: str
    native_result_fingerprint: str
    native_policy_fingerprint: str
    certification_request: ReferenceCertificationRequest
    joint_certificate: JointReferenceCertificate
    field_results: tuple[RobustFCRReferenceFieldResult, ...]
    source_bound_proof_status: str
    comparison_frame_fingerprints: Mapping[str, object]
    producer_schedule_fingerprints: Mapping[str, object]
    overall_status: str
    status_counts: Mapping[str, int] = field(init=False)
    comparison_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "fixture_fingerprint",
            "native_result_fingerprint",
            "native_policy_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), field_name=name))
        if not isinstance(self.certification_request, ReferenceCertificationRequest):
            raise RobustFCRValidationError("certification_request has the wrong type")
        if not isinstance(self.joint_certificate, JointReferenceCertificate):
            raise RobustFCRValidationError("joint_certificate has the wrong type")
        if (
            self.joint_certificate.request_fingerprint
            != self.certification_request.request_fingerprint
        ):
            raise RobustFCRValidationError("certificate/request fingerprint mismatch")
        fields = tuple(self.field_results)
        if not fields or any(
            not isinstance(value, RobustFCRReferenceFieldResult) for value in fields
        ):
            raise RobustFCRValidationError("field_results must be non-empty")
        if len({value.field_id for value in fields}) != len(fields):
            raise RobustFCRValidationError("reference field IDs must be unique")
        if self.source_bound_proof_status != "unavailable":
            raise RobustFCRValidationError(
                "the rounded source record does not contain source bound proof"
            )
        if self.overall_status != _overall_reference_status(
            tuple(value.status for value in fields)
        ):
            raise RobustFCRValidationError("overall reference status is inconsistent")
        counts = Counter(value.status for value in fields)
        object.__setattr__(self, "field_results", fields)
        object.__setattr__(
            self,
            "comparison_frame_fingerprints",
            _deep_freeze(
                self.comparison_frame_fingerprints,
                field_name="comparison_frame_fingerprints",
            ),
        )
        object.__setattr__(
            self,
            "producer_schedule_fingerprints",
            _deep_freeze(
                self.producer_schedule_fingerprints,
                field_name="producer_schedule_fingerprints",
            ),
        )
        object.__setattr__(
            self,
            "status_counts",
            MappingProxyType(
                {name: int(counts.get(name, 0)) for name in REFERENCE_COMPARISON_STATUSES}
            ),
        )
        object.__setattr__(self, "comparison_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "fixture_fingerprint": self.fixture_fingerprint,
            "native_result_fingerprint": self.native_result_fingerprint,
            "native_policy_fingerprint": self.native_policy_fingerprint,
            "certification_request": self.certification_request.to_dict(),
            "joint_certificate": self.joint_certificate.to_dict(),
            "field_results": [value.to_dict() for value in self.field_results],
            "source_bound_proof_status": self.source_bound_proof_status,
            "comparison_frame_fingerprints": _thaw(
                self.comparison_frame_fingerprints
            ),
            "producer_schedule_fingerprints": _thaw(
                self.producer_schedule_fingerprints
            ),
            "overall_status": self.overall_status,
            "status_counts": dict(self.status_counts),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "comparison_fingerprint": self.comparison_fingerprint,
        }


def _numeric_interval(
    value: Sequence[float],
    *,
    field_name: str,
) -> tuple[float, float]:
    values = _finite_tuple(value, field_name=field_name, count=2)
    if values[0] > values[1]:
        raise RobustFCRValidationError(f"{field_name} lower bound exceeds upper bound")
    return values


def _decimal_outer_interval(value: float, half_unit: float) -> tuple[float, float]:
    """Form a decimal rounding envelope without binary-arithmetic widening."""

    center = Decimal(str(_finite(value, field_name="interval center")))
    half = Decimal(str(_non_negative(half_unit, field_name="interval half unit")))
    return float(center - half), float(center + half)


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
    _expected(
        result.objective_value_eur,
        11.028,
        field_name="recorded_result.objective_value_eur",
    )
    _expected(
        result.objective_bound_eur,
        11.028,
        field_name="recorded_result.objective_bound_eur",
    )
    _expected(
        result.solve_time_seconds,
        1070.788,
        field_name="recorded_result.solve_time_seconds",
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
    required_unavailable = {
        "source.termination_status",
        "source.primal_status",
        "source.dual_status",
        "source.optimality_proof",
        "source.exact_optimality_gap",
        "source.unrounded_decisions",
        "source.constraint_residuals",
        "source.solver_tolerances",
        "source.actual_solver_versions",
        "source.restriction_bilinear_evidence",
    }
    found_unavailable = {value.field_id for value in unavailable}
    if not required_unavailable.issubset(found_unavailable):
        raise RobustFCRValidationError(
            "reference fixture omits required unavailable source evidence"
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


def build_reference_decision_intervals(
    fixture: RobustFCRReferenceFixture,
) -> tuple[ReferenceDecisionInterval, ...]:
    """Expand every displayed source decision into its closed rounding interval."""

    if not isinstance(fixture, RobustFCRReferenceFixture):
        raise RobustFCRValidationError("fixture has the wrong contract type")
    half_unit = fixture.precision_policy.decision_half_unit_kw
    intervals: list[ReferenceDecisionInterval] = []
    for index, displayed in enumerate(fixture.recorded_result.rounded_x0_kw):
        lower, upper = _decimal_outer_interval(displayed, half_unit)
        intervals.append(
            ReferenceDecisionInterval(
                field_id=f"x0[{index}]",
                decision_kind="energy_x0",
                index=index,
                displayed_value=displayed,
                lower=lower,
                upper=upper,
            )
        )
    for index, displayed in enumerate(fixture.recorded_result.rounded_xr_kw):
        lower, upper = _decimal_outer_interval(displayed, half_unit)
        intervals.append(
            ReferenceDecisionInterval(
                field_id=f"xr[{index}]",
                decision_kind="fcr_xr",
                index=index,
                displayed_value=displayed,
                lower=max(0.0, lower),
                upper=upper,
            )
        )
    return tuple(intervals)


def _native_policy_evidence(native_result: RobustFCRSolveResult) -> tuple[str, Mapping[str, object]]:
    options = native_result.solver.configured_options
    fingerprint = _sha256(
        options.get("solve_policy_fingerprint"),
        field_name="native solve_policy_fingerprint",
    )
    raw_policy = options.get("solve_policy")
    if not isinstance(raw_policy, Mapping):
        raise RobustFCRValidationError(
            "native result must retain its complete separately supplied solve policy"
        )
    policy = dict(raw_policy)
    if policy.get("solve_policy_fingerprint") != fingerprint:
        raise RobustFCRValidationError("native solve policy evidence is inconsistent")
    return fingerprint, policy


def build_reference_certification_request(
    fixture: RobustFCRReferenceFixture,
    native_result: RobustFCRSolveResult,
) -> ReferenceCertificationRequest:
    """Build the fixed source interval/native objective-band intersection."""

    if not isinstance(fixture, RobustFCRReferenceFixture):
        raise RobustFCRValidationError("fixture has the wrong contract type")
    if not isinstance(native_result, RobustFCRSolveResult):
        raise RobustFCRValidationError("native_result has the wrong contract type")
    if native_result.formulation.kind != "restriction":
        raise RobustFCRValidationError("reference comparison requires a restriction result")
    objective = native_result.solver.objective_value_eur
    if objective is None or native_result.decisions is None:
        raise RobustFCRValidationError(
            "reference certification requires a complete native incumbent"
        )
    policy_fingerprint, policy = _native_policy_evidence(native_result)
    try:
        absolute = _non_negative(
            policy["objective_comparison_absolute_tolerance_eur"],
            field_name="native objective absolute tolerance",
        )
        relative = _non_negative(
            policy["objective_comparison_relative_tolerance"],
            field_name="native objective relative tolerance",
        )
    except KeyError as exc:
        raise RobustFCRValidationError(
            "native solve policy is missing objective comparison fields"
        ) from exc
    source_value = fixture.recorded_result.objective_value_eur
    source_half = fixture.precision_policy.objective_half_unit_eur
    source_interval = _decimal_outer_interval(source_value, source_half)
    allowance = max(
        absolute,
        relative
        * max(
            abs(objective),
            abs(source_interval[0]),
            abs(source_interval[1]),
            1.0,
        ),
    )
    native_band = (objective - allowance, objective + allowance)
    lower = max(source_interval[0], native_band[0])
    upper = min(source_interval[1], native_band[1])
    intersection = (lower, upper) if lower <= upper else None
    return ReferenceCertificationRequest(
        fixture_fingerprint=fixture.fixture_fingerprint,
        native_result_fingerprint=native_result.semantic_result_fingerprint,
        native_policy_fingerprint=policy_fingerprint,
        decision_intervals=build_reference_decision_intervals(fixture),
        source_objective_interval=source_interval,
        native_objective_equivalence_band=native_band,
        certification_objective_interval=intersection,
        objective_comparison_allowance_eur=allowance,
        maximum_deployability_slack=DEPLOYABILITY_THRESHOLD,
        objective_equivalence_possible=intersection is not None,
    )


def _compare_reference_numeric_field(
    *,
    field_id: str,
    native_value: float | None,
    source_value: float | None,
    source_half_unit: float | None,
    source_exact: bool,
    alternative_optimum_compatible: bool,
    source_evidence_role: str,
    unavailable_reason: str | None = None,
) -> RobustFCRReferenceFieldResult:
    """Classify one numeric field while retaining its visible delta."""

    if native_value is None or source_value is None or source_half_unit is None:
        return RobustFCRReferenceFieldResult(
            field_id=field_id,
            status="unavailable",
            native_value=native_value,
            source_value=source_value,
            delta=None,
            source_interval=None,
            source_evidence_role=source_evidence_role,
            reason=unavailable_reason or "numeric comparison evidence is unavailable",
        )
    native = _finite(native_value, field_name=f"{field_id} native_value")
    source = _finite(source_value, field_name=f"{field_id} source_value")
    half = _non_negative(source_half_unit, field_name=f"{field_id} source_half_unit")
    interval = (source - half, source + half)
    delta = native - source
    if source_exact and native == source:
        status = "exact"
    elif interval[0] <= native <= interval[1]:
        status = "source_precision_compatible"
    elif alternative_optimum_compatible:
        status = "alternative_optimum_compatible"
    else:
        status = "mismatch"
    return RobustFCRReferenceFieldResult(
        field_id=field_id,
        status=status,
        native_value=native,
        source_value=source,
        delta=delta,
        source_interval=interval,
        source_evidence_role=source_evidence_role,
        reason=None,
    )


def _overall_reference_status(statuses: Sequence[str]) -> str:
    """Reduce ordered field statuses under the declared evidence precedence."""

    values = tuple(statuses)
    if not values or any(value not in REFERENCE_COMPARISON_STATUSES for value in values):
        raise RobustFCRValidationError("reference statuses are empty or unsupported")
    precedence = {
        "exact": 0,
        "unavailable": 1,
        "source_precision_compatible": 2,
        "alternative_optimum_compatible": 3,
        "mismatch": 4,
    }
    return max(values, key=precedence.__getitem__)


def _status_field(
    *,
    field_id: str,
    status: str,
    native_value: object | None,
    source_value: object | None,
    source_evidence_role: str,
    reason: str | None = None,
) -> RobustFCRReferenceFieldResult:
    return RobustFCRReferenceFieldResult(
        field_id=field_id,
        status=status,
        native_value=native_value,
        source_value=source_value,
        delta=None,
        source_interval=None,
        source_evidence_role=source_evidence_role,
        reason=reason,
    )


def _comparison_frame_payloads(
    fixture: RobustFCRReferenceFixture,
    native_result: RobustFCRSolveResult,
) -> dict[str, object]:
    if native_result.decisions is None:  # guarded by request construction
        raise RobustFCRValidationError("native decisions are unavailable")
    source_x0 = fixture.recorded_result.rounded_x0_kw
    source_xr = fixture.recorded_result.rounded_xr_kw
    native_x0 = tuple(
        -value
        for value in native_result.decisions.energy_baseline_charge_positive_kw
    )
    native_xr = native_result.decisions.fcr_capacity_kw
    return {
        "comparison_frame": "positive_is_discharge",
        "source": {
            "energy": reference_energy_content_fingerprint(source_x0),
            "fcr": reference_fcr_content_fingerprint(source_xr),
            "combined": reference_decision_content_fingerprint(source_x0, source_xr),
        },
        "native": {
            "energy": reference_energy_content_fingerprint(native_x0),
            "fcr": reference_fcr_content_fingerprint(native_xr),
            "combined": reference_decision_content_fingerprint(native_x0, native_xr),
        },
    }


def _producer_schedule_fingerprints(
    native_result: RobustFCRSolveResult,
) -> dict[str, object]:
    native_plan = native_result.deployable_plan
    if native_plan is None:
        native = {
            "energy_schedule_fingerprint": None,
            "fcr_schedule_fingerprint": None,
            "plan_fingerprint": None,
            "unavailable_reason": "native result did not emit an eligible plan",
        }
    else:
        native = {
            "energy_schedule_fingerprint": native_plan.energy_schedule.schedule_fingerprint,
            "fcr_schedule_fingerprint": native_plan.fcr_schedule.schedule_fingerprint,
            "plan_fingerprint": native_plan.plan_fingerprint,
            "unavailable_reason": None,
        }
    return {
        "native": native,
        "source": {
            "energy_schedule_fingerprint": None,
            "fcr_schedule_fingerprint": None,
            "plan_fingerprint": None,
            "unavailable_reason": (
                "the Julia record contains rounded decisions but no Feature 012 "
                "producer IDs or schedule/plan envelopes"
            ),
        },
        "comparison_rule": (
            "producer-specific fingerprints are reported but never numerically equated"
        ),
    }


def compare_robust_fcr_reference(
    fixture: RobustFCRReferenceFixture,
    native_result: RobustFCRSolveResult,
) -> RobustFCRReferenceComparison:
    """Compare a native restriction with normalized rounded Julia evidence."""

    request = build_reference_certification_request(fixture, native_result)
    certificate = _certify_reference_decision_box(fixture, native_result, request)
    audit = native_result.feasibility_audit
    native_feasible = bool(audit is not None and audit.passes_deployability_audit)
    alternative_compatible = bool(
        request.objective_equivalence_possible
        and native_feasible
        and certificate.joint_feasible
        and certificate.objective_equivalent
    )
    source = fixture.recorded_result
    native_decisions = native_result.decisions
    if native_decisions is None:  # guarded by request construction
        raise RobustFCRValidationError("native decisions are unavailable")
    native_x0 = tuple(
        -value for value in native_decisions.energy_baseline_charge_positive_kw
    )
    fields: list[RobustFCRReferenceFieldResult] = [
        _compare_reference_numeric_field(
            field_id="optimization_objective_eur",
            native_value=native_result.solver.objective_value_eur,
            source_value=source.objective_value_eur,
            source_half_unit=fixture.precision_policy.objective_half_unit_eur,
            source_exact=False,
            alternative_optimum_compatible=alternative_compatible,
            source_evidence_role="rounded_objective",
        ),
        RobustFCRReferenceFieldResult(
            field_id="source_solver_bound_eur",
            status="unavailable",
            native_value=native_result.solver.best_upper_bound_eur,
            source_value=source.objective_bound_eur,
            delta=(
                native_result.solver.best_upper_bound_eur - source.objective_bound_eur
                if native_result.solver.best_upper_bound_eur is not None
                else None
            ),
            source_interval=(
                source.objective_bound_eur
                - fixture.precision_policy.objective_half_unit_eur,
                source.objective_bound_eur
                + fixture.precision_policy.objective_half_unit_eur,
            ),
            source_evidence_role="rounded_bound_metadata_without_proof",
            reason=(
                "equal displayed source objective and bound do not prove optimality, "
                "an exact gap, or source termination"
            ),
        ),
    ]
    fields.extend(
        _compare_reference_numeric_field(
            field_id=f"x0[{index}]",
            native_value=native_x0[index],
            source_value=source.rounded_x0_kw[index],
            source_half_unit=fixture.precision_policy.decision_half_unit_kw,
            source_exact=False,
            alternative_optimum_compatible=alternative_compatible,
            source_evidence_role="rounded_decision",
        )
        for index in range(24)
    )
    fields.extend(
        _compare_reference_numeric_field(
            field_id=f"xr[{index}]",
            native_value=native_decisions.fcr_capacity_kw[index],
            source_value=source.rounded_xr_kw[index],
            source_half_unit=fixture.precision_policy.decision_half_unit_kw,
            source_exact=False,
            alternative_optimum_compatible=alternative_compatible,
            source_evidence_role="rounded_decision",
        )
        for index in range(6)
    )
    frame = _comparison_frame_payloads(fixture, native_result)
    numeric_status = _overall_reference_status(
        tuple(value.status for value in fields if value.field_id.startswith(("x0[", "xr[")))
    )
    for name in ("energy", "fcr", "combined"):
        fields.append(
            _status_field(
                field_id=f"decision_content_fingerprint.{name}",
                status=numeric_status,
                native_value=frame["native"][name],
                source_value=frame["source"][name],
                source_evidence_role="canonical_positive_discharge_content",
                reason=(
                    "fingerprints retain exact payload identity; compatibility is "
                    "classified from the interval-aware numeric evidence"
                ),
            )
        )
    if audit is None:
        fields.append(
            _status_field(
                field_id="native_feasibility_audit",
                status="unavailable",
                native_value=None,
                source_value=None,
                source_evidence_role="native_independent_audit",
                reason="native result contains no feasibility audit",
            )
        )
    else:
        fields.append(
            _status_field(
                field_id="native_feasibility_audit",
                status="exact" if native_feasible else "mismatch",
                native_value=audit.audit_fingerprint,
                source_value="required_pass",
                source_evidence_role="native_independent_audit",
                reason=None if native_feasible else "native deployability audit failed",
            )
        )
    certificate_status = (
        "exact"
        if certificate.joint_feasible
        else ("unavailable" if certificate.solve_status == "unavailable" else "mismatch")
    )
    fields.append(
        _status_field(
            field_id="joint_reference_feasibility",
            status=certificate_status,
            native_value=certificate.joint_feasible,
            source_value="required_joint_feasible",
            source_evidence_role="joint_restriction_certificate",
            reason=(
                certificate.unavailable_reason
                if certificate_status == "unavailable"
                else (
                    None
                    if certificate_status == "exact"
                    else "the simultaneous rounded-decision box is infeasible"
                )
            ),
        )
    )
    fields.append(
        _status_field(
            field_id="objective_equivalence",
            status=(
                "exact"
                if certificate.objective_equivalent
                else ("unavailable" if certificate.solve_status == "unavailable" else "mismatch")
            ),
            native_value=certificate.certified_objective_value_eur,
            source_value=(
                list(request.certification_objective_interval)
                if request.certification_objective_interval is not None
                else None
            ),
            source_evidence_role="joint_objective_interval_certificate",
            reason=(
                certificate.unavailable_reason
                if certificate.solve_status == "unavailable"
                else (
                    None
                    if certificate.objective_equivalent
                    else "no jointly feasible objective-equivalent witness was certified"
                )
            ),
        )
    )
    producer = _producer_schedule_fingerprints(native_result)
    for producer_name in ("native", "source"):
        for fingerprint_name in (
            "energy_schedule_fingerprint",
            "fcr_schedule_fingerprint",
            "plan_fingerprint",
        ):
            value = producer[producer_name][fingerprint_name]
            fields.append(
                _status_field(
                    field_id=f"{producer_name}.{fingerprint_name}",
                    status="unavailable",
                    native_value=value if producer_name == "native" else None,
                    source_value=value if producer_name == "source" else None,
                    source_evidence_role="producer_specific_identity",
                    reason=producer[producer_name]["unavailable_reason"]
                    or "producer-specific identities are not parity criteria",
                )
            )
    overall = _overall_reference_status(tuple(value.status for value in fields))
    return RobustFCRReferenceComparison(
        fixture_fingerprint=fixture.fixture_fingerprint,
        native_result_fingerprint=native_result.semantic_result_fingerprint,
        native_policy_fingerprint=request.native_policy_fingerprint,
        certification_request=request,
        joint_certificate=certificate,
        field_results=tuple(fields),
        source_bound_proof_status="unavailable",
        comparison_frame_fingerprints=frame,
        producer_schedule_fingerprints=producer,
        overall_status=overall,
    )


def _certify_reference_decision_box(
    fixture: RobustFCRReferenceFixture,
    native_result: RobustFCRSolveResult,
    request: ReferenceCertificationRequest,
) -> JointReferenceCertificate:
    """Solve the auxiliary certificate lazily; implemented at the solver boundary."""

    if not request.objective_equivalence_possible:
        return JointReferenceCertificate(
            request_fingerprint=request.request_fingerprint,
            solve_status="infeasible",
            joint_feasible=False,
            objective_equivalent=False,
            maximum_slack=None,
            maximum_residual=None,
            certified_objective_value_eur=None,
            witness_fingerprint=None,
            unavailable_reason=None,
        )
    audit = native_result.feasibility_audit
    decisions = native_result.decisions
    objective = native_result.solver.objective_value_eur
    objective_interval = request.certification_objective_interval
    if (
        audit is not None
        and audit.passes_deployability_audit
        and decisions is not None
        and objective is not None
        and objective_interval is not None
        and native_result.solver.solve_status in {"optimal", "feasible"}
    ):
        source_x0 = tuple(
            -value for value in decisions.energy_baseline_charge_positive_kw
        )
        source_xr = decisions.fcr_capacity_kw
        decision_box_residual = 0.0
        for interval in request.decision_intervals:
            value = (
                source_x0[interval.index]
                if interval.decision_kind == "energy_x0"
                else source_xr[interval.index]
            )
            decision_box_residual = max(
                decision_box_residual,
                interval.lower - value,
                value - interval.upper,
                0.0,
            )
        objective_box_residual = max(
            objective_interval[0] - objective,
            objective - objective_interval[1],
            0.0,
        )
        maximum_slack = max(audit.modeled_slacks.values(), default=0.0)
        common_maximum_residual = max(
            (
                value.maximum_positive_violation
                for value in audit.constraint_families
            ),
            default=0.0,
        )
        maximum_residual = max(
            common_maximum_residual,
            decision_box_residual,
            objective_box_residual,
        )
        if (
            maximum_slack <= DEPLOYABILITY_THRESHOLD
            and maximum_residual <= DEPLOYABILITY_THRESHOLD
        ):
            # The independently audited native incumbent is already one joint
            # witness inside every recorded source interval.  Re-solving the
            # same feasibility question is necessary only when the native
            # market decisions lie outside that box.
            return JointReferenceCertificate(
                request_fingerprint=request.request_fingerprint,
                solve_status=native_result.solver.solve_status,
                joint_feasible=True,
                objective_equivalent=True,
                maximum_slack=maximum_slack,
                maximum_residual=maximum_residual,
                certified_objective_value_eur=objective,
                witness_fingerprint=audit.canonical_witness_fingerprint,
                unavailable_reason=None,
            )
    try:
        policy_payload = dict(native_result.solver.configured_options["solve_policy"])
        policy_payload.pop("solve_policy_fingerprint", None)
        # The joint rounded-vector certificate is independent validation, not a
        # continuation of the native optimization solve.  Keep it on the
        # required open-source backend even when the compared result came from
        # explicitly selected optional Gurobi evidence.
        policy_payload["solver_name"] = "highs"
        policy = RobustFCRSolvePolicy(**policy_payload)
        problem = build_robust_fcr_reference_problem(fixture, solve_policy=policy)
        from ._robust_fcr_formulation import assemble_robust_fcr_reference_certificate
        from ._robust_fcr_solver import require_highs_backend, solve_assembled_model

        backend = require_highs_backend()
        assembled = assemble_robust_fcr_reference_certificate(
            problem,
            request,
            pyomo_environ=backend.pyomo_environ,
        )
        raw = solve_assembled_model(assembled, policy, backend=backend)
    except Exception as exc:
        return JointReferenceCertificate(
            request_fingerprint=request.request_fingerprint,
            solve_status="unavailable",
            joint_feasible=False,
            objective_equivalent=False,
            maximum_slack=None,
            maximum_residual=None,
            certified_objective_value_eur=None,
            witness_fingerprint=None,
            unavailable_reason=f"joint reference certification is unavailable: {exc}",
        )
    if raw.solve_status not in {"optimal", "feasible"} or raw.witness is None:
        return JointReferenceCertificate(
            request_fingerprint=request.request_fingerprint,
            solve_status=raw.solve_status,
            joint_feasible=False,
            objective_equivalent=False,
            maximum_slack=None,
            maximum_residual=None,
            certified_objective_value_eur=None,
            witness_fingerprint=None,
            unavailable_reason=None,
        )
    from .robust_fcr_bidding import _audit_witness

    audit = _audit_witness(
        problem,
        RobustFCRFormulationProfile.for_kind("restriction"),
        raw.witness,
        reported_objective_eur=raw.objective_value_eur,
    )
    common_maximum_residual = max(
        (value.maximum_positive_violation for value in audit.constraint_families),
        default=0.0,
    )
    maximum_slack = max(audit.modeled_slacks.values(), default=0.0)
    objective = raw.objective_value_eur
    objective_interval = request.certification_objective_interval
    source_x0 = tuple(float(value) for value in raw.witness["x0"])
    source_xr = tuple(float(value) for value in raw.witness["xr"])
    decision_box_residual = 0.0
    for interval in request.decision_intervals:
        value = (
            source_x0[interval.index]
            if interval.decision_kind == "energy_x0"
            else source_xr[interval.index]
        )
        decision_box_residual = max(
            decision_box_residual,
            interval.lower - value,
            value - interval.upper,
        )
    objective_box_residual = (
        max(
            objective_interval[0] - objective,
            objective - objective_interval[1],
            0.0,
        )
        if objective is not None and objective_interval is not None
        else math.inf
    )
    maximum_residual = max(
        common_maximum_residual,
        decision_box_residual,
        objective_box_residual,
    )
    objective_equivalent = bool(
        objective is not None
        and objective_interval is not None
        and objective_interval[0] - DEPLOYABILITY_THRESHOLD
        <= objective
        <= objective_interval[1] + DEPLOYABILITY_THRESHOLD
    )
    joint_feasible = bool(
        audit.passes
        and maximum_slack <= DEPLOYABILITY_THRESHOLD
        and maximum_residual <= DEPLOYABILITY_THRESHOLD
        and objective_equivalent
    )
    if not joint_feasible:
        return JointReferenceCertificate(
            request_fingerprint=request.request_fingerprint,
            solve_status="infeasible",
            joint_feasible=False,
            objective_equivalent=False,
            maximum_slack=None,
            maximum_residual=None,
            certified_objective_value_eur=None,
            witness_fingerprint=None,
            unavailable_reason=None,
        )
    return JointReferenceCertificate(
        request_fingerprint=request.request_fingerprint,
        solve_status=raw.solve_status,
        joint_feasible=True,
        objective_equivalent=True,
        maximum_slack=maximum_slack,
        maximum_residual=maximum_residual,
        certified_objective_value_eur=objective,
        witness_fingerprint=audit.witness_fingerprint,
        unavailable_reason=None,
    )


__all__ = [
    "JointReferenceCertificate",
    "REFERENCE_FIXTURE_SCHEMA_VERSION",
    "ReferenceCertificationRequest",
    "ReferenceDecisionInterval",
    "RobustFCRReferenceComparison",
    "RobustFCRReferenceFieldResult",
    "RobustFCRReferenceFixture",
    "build_reference_certification_request",
    "build_reference_decision_intervals",
    "build_robust_fcr_reference_problem",
    "compare_robust_fcr_reference",
    "load_robust_fcr_reference_fixture",
    "reference_decision_content_fingerprint",
    "reference_energy_content_fingerprint",
    "reference_fcr_content_fingerprint",
]
