"""Bidder-neutral envelopes for fixed energy and symmetric-FCR schedules.

The plan records producer-visible identity and lineage only.  Evaluation-only
activation, realized settlement inputs, and expected results are deliberately
bound later by the simulator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from types import MappingProxyType

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import canonical_json_bytes, fingerprint, thaw
from open_energy_lab.core.time import utc_datetime
from open_energy_lab.core.validation import finite, non_empty_str, sha256_digest
from .stacked_service import (
    EnergyBaselineSchedule,
    FCRCapacitySchedule,
)


FIXED_FCR_BID_PLAN_SEMANTICS_VERSION = "oel.fixed-fcr-bid-plan.v1"
_PRODUCER_KINDS = {"manual", "heuristic", "robust", "tpm", "other"}
_SOLVE_STATUSES = {
    "not_applicable",
    "optimal",
    "feasible",
    "infeasible",
    "failed",
    "unknown",
}
_EVALUATION_ONLY_LINEAGE_TERMS = (
    "activation",
    "expected",
    "comparison",
    "parity",
    "realized",
)


class FCRBidPlanValidationError(ValidationError):
    """Raised when a fixed plan violates the producer/evaluation boundary."""


_non_empty = partial(non_empty_str, error=FCRBidPlanValidationError, strip=True)
_finite = partial(finite, error=FCRBidPlanValidationError)
_sha256 = partial(sha256_digest, error=FCRBidPlanValidationError)
_utc = partial(utc_datetime, error=FCRBidPlanValidationError)
_thaw = thaw
_canonical_json = partial(canonical_json_bytes, error=FCRBidPlanValidationError)
_fingerprint = partial(fingerprint, error=FCRBidPlanValidationError)


@dataclass(frozen=True, slots=True)
class BidPlanProducer:
    producer_id: str
    producer_kind: str
    producer_version: str
    configuration_fingerprint: str | None
    configuration_unavailable_reason: str | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "producer_id",
            _non_empty(self.producer_id, field_name="producer_id"),
        )
        if self.producer_kind not in _PRODUCER_KINDS:
            raise FCRBidPlanValidationError(
                "producer kind must be manual, heuristic, robust, tpm, or other"
            )
        object.__setattr__(
            self,
            "producer_version",
            _non_empty(self.producer_version, field_name="producer_version"),
        )
        if self.configuration_fingerprint is None:
            reason = _non_empty(
                self.configuration_unavailable_reason,
                field_name="configuration unavailable reason",
            )
            object.__setattr__(self, "configuration_unavailable_reason", reason)
        else:
            object.__setattr__(
                self,
                "configuration_fingerprint",
                _sha256(
                    self.configuration_fingerprint,
                    field_name="configuration_fingerprint",
                ),
            )
            if self.configuration_unavailable_reason is not None:
                raise FCRBidPlanValidationError(
                    "configuration unavailable reason must be absent when a "
                    "configuration fingerprint is available"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "producer_id": self.producer_id,
            "producer_kind": self.producer_kind,
            "producer_version": self.producer_version,
            "configuration_fingerprint": self.configuration_fingerprint,
            "configuration_unavailable_reason": self.configuration_unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class OptimizationMetric:
    availability: str
    value: float | None
    unit: str | None
    unavailable_reason: str | None
    meaning: str

    def __post_init__(self) -> None:
        if self.meaning not in {"optimization_objective", "optimization_bound"}:
            raise FCRBidPlanValidationError(
                "metric meaning must be optimization_objective or optimization_bound"
            )
        if self.availability == "available":
            if self.value is None or not isinstance(self.unit, str) or not self.unit.strip():
                raise FCRBidPlanValidationError(
                    "available metric value and unit must both be present"
                )
            value = _finite(self.value, field_name="available metric value")
            unit = _non_empty(self.unit, field_name="available metric unit")
            if self.unavailable_reason is not None:
                raise FCRBidPlanValidationError(
                    "unavailable reason must be absent for an available metric"
                )
            object.__setattr__(self, "value", value)
            object.__setattr__(self, "unit", unit)
        elif self.availability == "unavailable":
            if self.value is not None or self.unit is not None:
                raise FCRBidPlanValidationError(
                    "unavailable metric value and unit must both be absent"
                )
            object.__setattr__(
                self,
                "unavailable_reason",
                _non_empty(
                    self.unavailable_reason,
                    field_name="metric unavailable reason",
                ),
            )
        else:
            raise FCRBidPlanValidationError(
                "metric availability must be available or unavailable"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability,
            "value": self.value,
            "unit": self.unit,
            "unavailable_reason": self.unavailable_reason,
            "meaning": self.meaning,
        }


@dataclass(frozen=True, slots=True)
class PlanDiagnostic:
    code: str
    severity: str
    field_path: str | None
    message: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _non_empty(self.code, field_name="diagnostic code"))
        if self.severity not in {"info", "warning", "error"}:
            raise FCRBidPlanValidationError(
                "diagnostic severity must be info, warning, or error"
            )
        if self.field_path is not None:
            object.__setattr__(
                self,
                "field_path",
                _non_empty(self.field_path, field_name="diagnostic field_path"),
            )
        object.__setattr__(
            self,
            "message",
            _non_empty(self.message, field_name="diagnostic message"),
        )
        if isinstance(self.evidence_refs, (str, bytes)) or not isinstance(
            self.evidence_refs, Sequence
        ):
            raise FCRBidPlanValidationError(
                "diagnostic evidence_refs must be a sequence"
            )
        refs = tuple(
            _non_empty(value, field_name="diagnostic evidence reference")
            for value in self.evidence_refs
        )
        object.__setattr__(self, "evidence_refs", refs)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field_path": self.field_path,
            "message": self.message,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class SerializedScheduleReference:
    schedule_id: str
    semantics_version: str
    schedule_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schedule_id",
            _non_empty(self.schedule_id, field_name="schedule reference id"),
        )
        object.__setattr__(
            self,
            "semantics_version",
            _non_empty(
                self.semantics_version,
                field_name="schedule reference semantics_version",
            ),
        )
        object.__setattr__(
            self,
            "schedule_fingerprint",
            _sha256(
                self.schedule_fingerprint,
                field_name="schedule reference fingerprint",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "schedule_id": self.schedule_id,
            "semantics_version": self.semantics_version,
            "schedule_fingerprint": self.schedule_fingerprint,
        }


def _schedule_reference(
    schedule: EnergyBaselineSchedule | FCRCapacitySchedule,
) -> SerializedScheduleReference:
    return SerializedScheduleReference(
        schedule_id=schedule.schedule_id,
        semantics_version=schedule.semantics_version,
        schedule_fingerprint=schedule.schedule_fingerprint,
    )


def _diagnostic_sort_key(value: PlanDiagnostic) -> tuple[object, ...]:
    return (
        value.field_path or "",
        value.code,
        value.severity,
        value.evidence_refs,
        value.message,
    )


@dataclass(frozen=True, slots=True)
class FixedFCRBidPlan:
    plan_id: str
    semantics_version: str
    producer: BidPlanProducer
    information_cutoff_utc: datetime
    energy_schedule: EnergyBaselineSchedule
    fcr_schedule: FCRCapacitySchedule
    producer_input_fingerprints: Mapping[str, str]
    solve_status: str
    objective: OptimizationMetric
    objective_bound: OptimizationMetric
    diagnostics: tuple[PlanDiagnostic, ...]
    plan_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _non_empty(self.plan_id, field_name="plan_id"))
        if self.semantics_version != FIXED_FCR_BID_PLAN_SEMANTICS_VERSION:
            raise FCRBidPlanValidationError(
                "unsupported fixed FCR bid-plan semantics version"
            )
        if not isinstance(self.producer, BidPlanProducer):
            raise FCRBidPlanValidationError("producer must be one BidPlanProducer")
        cutoff = _utc(
            self.information_cutoff_utc,
            field_name="information_cutoff_utc",
        )
        if not isinstance(self.energy_schedule, EnergyBaselineSchedule):
            raise FCRBidPlanValidationError(
                "energy_schedule must be one existing EnergyBaselineSchedule"
            )
        if not isinstance(self.fcr_schedule, FCRCapacitySchedule):
            raise FCRBidPlanValidationError(
                "fcr_schedule must be one existing FCRCapacitySchedule"
            )
        if self.energy_schedule.covered_period != self.fcr_schedule.covered_period:
            raise FCRBidPlanValidationError(
                "energy and FCR schedules must cover the same period"
            )
        if cutoff > self.energy_schedule.covered_period.start_utc:
            raise FCRBidPlanValidationError(
                "information cutoff cannot be after delivery starts"
            )
        if not isinstance(self.producer_input_fingerprints, Mapping):
            raise FCRBidPlanValidationError(
                "producer_input_fingerprints must be a mapping"
            )
        normalized_inputs: dict[str, str] = {}
        for raw_key, raw_value in self.producer_input_fingerprints.items():
            key = _non_empty(raw_key, field_name="producer input fingerprint key")
            lowered = key.casefold()
            if any(term in lowered for term in _EVALUATION_ONLY_LINEAGE_TERMS):
                raise FCRBidPlanValidationError(
                    f"producer input {key!r} is evaluation-only look-ahead lineage"
                )
            normalized_inputs[key] = _sha256(
                raw_value,
                field_name=f"producer input fingerprint {key!r}",
            )
        ordered_inputs = MappingProxyType(dict(sorted(normalized_inputs.items())))
        if self.solve_status not in _SOLVE_STATUSES:
            raise FCRBidPlanValidationError("solve_status is not supported")
        if not isinstance(self.objective, OptimizationMetric):
            raise FCRBidPlanValidationError("objective must be an OptimizationMetric")
        if self.objective.meaning != "optimization_objective":
            raise FCRBidPlanValidationError(
                "objective meaning must be optimization_objective"
            )
        if not isinstance(self.objective_bound, OptimizationMetric):
            raise FCRBidPlanValidationError(
                "objective_bound must be an OptimizationMetric"
            )
        if self.objective_bound.meaning != "optimization_bound":
            raise FCRBidPlanValidationError(
                "objective bound meaning must be optimization_bound"
            )
        if isinstance(self.diagnostics, (str, bytes)) or not isinstance(
            self.diagnostics, Sequence
        ):
            raise FCRBidPlanValidationError("diagnostics must be a sequence")
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, PlanDiagnostic) for item in diagnostics):
            raise FCRBidPlanValidationError(
                "diagnostics must contain only PlanDiagnostic values"
            )
        diagnostics = tuple(sorted(diagnostics, key=_diagnostic_sort_key))
        object.__setattr__(self, "information_cutoff_utc", cutoff)
        object.__setattr__(self, "producer_input_fingerprints", ordered_inputs)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "plan_fingerprint", _fingerprint(self._semantic_payload()))

    @property
    def energy_schedule_ref(self) -> SerializedScheduleReference:
        return _schedule_reference(self.energy_schedule)

    @property
    def fcr_schedule_ref(self) -> SerializedScheduleReference:
        return _schedule_reference(self.fcr_schedule)

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "semantics_version": self.semantics_version,
            "producer": self.producer.to_dict(),
            "information_cutoff_utc": self.information_cutoff_utc.isoformat().replace(
                "+00:00", "Z"
            ),
            "energy_schedule_ref": self.energy_schedule_ref.to_dict(),
            "fcr_schedule_ref": self.fcr_schedule_ref.to_dict(),
            "producer_input_fingerprints": dict(self.producer_input_fingerprints),
            "solve_status": self.solve_status,
            "objective": self.objective.to_dict(),
            "objective_bound": self.objective_bound.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "plan_fingerprint": self.plan_fingerprint,
        }


def build_fixed_fcr_bid_plan(
    *,
    plan_id: str,
    producer: BidPlanProducer,
    information_cutoff_utc: datetime,
    energy_schedule: EnergyBaselineSchedule,
    fcr_schedule: FCRCapacitySchedule,
    producer_input_fingerprints: Mapping[str, str],
    solve_status: str,
    objective: OptimizationMetric,
    objective_bound: OptimizationMetric,
    diagnostics: Sequence[PlanDiagnostic] = (),
    semantics_version: str = FIXED_FCR_BID_PLAN_SEMANTICS_VERSION,
) -> FixedFCRBidPlan:
    """Build one frozen plan that references existing schedule objects exactly."""

    return FixedFCRBidPlan(
        plan_id=plan_id,
        semantics_version=semantics_version,
        producer=producer,
        information_cutoff_utc=information_cutoff_utc,
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        producer_input_fingerprints=producer_input_fingerprints,
        solve_status=solve_status,
        objective=objective,
        objective_bound=objective_bound,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "BidPlanProducer",
    "FCRBidPlanValidationError",
    "FIXED_FCR_BID_PLAN_SEMANTICS_VERSION",
    "FixedFCRBidPlan",
    "OptimizationMetric",
    "PlanDiagnostic",
    "SerializedScheduleReference",
    "build_fixed_fcr_bid_plan",
]
