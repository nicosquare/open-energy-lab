"""Map the pinned robust-storage-bidding reference decisions onto OEL schedules.

The bidder-neutral plan contract itself lives in
``open_energy_lab.simulator.fcr_bid_plan``. This module keeps only the
reference mapping, which moves to ``validation/`` in consolidation step A3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from open_energy_lab.simulator.fcr_bid_plan import (
    BidPlanProducer,
    FCRBidPlanValidationError,
    FIXED_FCR_BID_PLAN_SEMANTICS_VERSION,
    FixedFCRBidPlan,
    OptimizationMetric,
    PlanDiagnostic,
    SerializedScheduleReference,
    _fingerprint,
    _finite,
    _schedule_reference,
    build_fixed_fcr_bid_plan,
)
from open_energy_lab.simulator.stacked_service import (
    EnergyBaselineSchedule,
    FCRCapacitySchedule,
    build_energy_baseline_schedule,
    build_fcr_capacity_schedule,
)


@dataclass(frozen=True, slots=True)
class ReferenceScheduleMappingResult:
    """Existing OEL schedules produced under one declared reference mapping."""

    mapping_id: str
    energy_schedule: EnergyBaselineSchedule
    fcr_schedule: FCRCapacitySchedule
    source_field_refs: tuple[str, ...]
    mapping_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mapping_id": self.mapping_id,
            "energy_schedule_ref": _schedule_reference(self.energy_schedule).to_dict(),
            "fcr_schedule_ref": _schedule_reference(self.fcr_schedule).to_dict(),
            "source_field_refs": list(self.source_field_refs),
            "mapping_fingerprint": self.mapping_fingerprint,
        }


def map_reference_decisions_to_schedules(
    fixture: object,
) -> ReferenceScheduleMappingResult:
    """Map the pinned discharge-positive decisions into existing OEL schedules.

    The behavior follows the declared equations from
    ``code/02_model.jl`` and ``code/03_backtest_save.jl`` retained in the
    normalized fixture.  This function consumes no baseline path at runtime.
    """

    from open_energy_lab.market.reference_fcr import (
        GoldenReferenceFixture,
        REFERENCE_MAPPING_ID,
    )

    if not isinstance(fixture, GoldenReferenceFixture):
        raise FCRBidPlanValidationError(
            "fixture must be one validated GoldenReferenceFixture"
        )
    mapping = fixture.mapping
    if mapping.mapping_id != REFERENCE_MAPPING_ID:
        raise FCRBidPlanValidationError("reference mapping ID is unsupported")
    if mapping.source_sign_convention != "positive power is discharge":
        raise FCRBidPlanValidationError(
            "reference x0 sign must be explicitly discharge-positive"
        )
    if mapping.target_sign_convention != "positive power is charge":
        raise FCRBidPlanValidationError(
            "library baseline sign must be explicitly charge-positive"
        )
    if mapping.x0_formula != "library_baseline_kw[h] = -reference_x0_kw[h]":
        raise FCRBidPlanValidationError("reference x0 sign formula is unsupported")
    if mapping.xr_formula != "library_fcr_capacity_kw[b] = reference_xr_kw[b]":
        raise FCRBidPlanValidationError("reference xr mapping formula is unsupported")
    if len(fixture.rounded_x0_kw) != 24:
        raise FCRBidPlanValidationError(
            "reference x0 must contain exactly 24 hourly decisions"
        )
    if len(fixture.rounded_xr_kw) != 6:
        raise FCRBidPlanValidationError(
            "reference xr must contain exactly six four-hour decisions"
        )
    x0: list[float] = []
    for index, value in enumerate(fixture.rounded_x0_kw):
        x0.append(_finite(value, field_name=f"rounded_x0_kw[{index}]"))
    xr: list[float] = []
    for index, value in enumerate(fixture.rounded_xr_kw):
        normalized = _finite(value, field_name=f"rounded_xr_kw[{index}]")
        if normalized < 0.0:
            raise FCRBidPlanValidationError(
                f"rounded_xr_kw[{index}] must be non-negative before schedule construction"
            )
        xr.append(normalized)

    period = mapping.target_period
    duration = period.end_utc - period.start_utc
    if duration != timedelta(hours=24):
        raise FCRBidPlanValidationError(
            "reference mapping supports only an ordinary 24-hour delivery day"
        )
    energy_intervals = [
        {
            "start_utc": period.start_utc + timedelta(hours=index),
            "end_utc": period.start_utc + timedelta(hours=index + 1),
            "power_kw": -value,
            "schedule_source": "fixed",
        }
        for index, value in enumerate(x0)
    ]
    fcr_intervals = [
        {
            "start_utc": period.start_utc + timedelta(hours=4 * index),
            "end_utc": period.start_utc + timedelta(hours=4 * (index + 1)),
            "capacity_kw": value,
            "volume_observation_ref": f"reference_accepted_fcr_bid:{index}",
            "price_observation_ref": f"reference_fcr_capacity_price:{index}",
        }
        for index, value in enumerate(xr)
    ]
    energy_schedule = build_energy_baseline_schedule(
        schedule_id=f"{fixture.fixture_id}-energy",
        semantics_version="charge-positive-fixed-v1",
        covered_start_utc=period.start_utc,
        covered_end_utc=period.end_utc,
        intervals=energy_intervals,
    )
    fcr_schedule = build_fcr_capacity_schedule(
        schedule_id=f"{fixture.fixture_id}-fcr",
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=period.start_utc,
        covered_end_utc=period.end_utc,
        intervals=fcr_intervals,
    )
    source_refs = tuple(
        [f"/fixed_decisions/rounded_x0_kw/{index}" for index in range(24)]
        + [f"/fixed_decisions/rounded_xr_kw/{index}" for index in range(6)]
    )
    result_payload = {
        "mapping_declaration_fingerprint": mapping.mapping_fingerprint,
        "energy_schedule_fingerprint": energy_schedule.schedule_fingerprint,
        "fcr_schedule_fingerprint": fcr_schedule.schedule_fingerprint,
        "source_field_refs": source_refs,
    }
    return ReferenceScheduleMappingResult(
        mapping_id=mapping.mapping_id,
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        source_field_refs=source_refs,
        mapping_fingerprint=_fingerprint(result_payload),
    )


__all__ = [
    "BidPlanProducer",
    "FCRBidPlanValidationError",
    "FIXED_FCR_BID_PLAN_SEMANTICS_VERSION",
    "FixedFCRBidPlan",
    "OptimizationMetric",
    "PlanDiagnostic",
    "ReferenceScheduleMappingResult",
    "SerializedScheduleReference",
    "build_fixed_fcr_bid_plan",
    "map_reference_decisions_to_schedules",
]
