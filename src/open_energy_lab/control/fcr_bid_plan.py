"""Former location of the fixed FCR bid-plan contract.

The contract now lives in ``open_energy_lab.simulator.fcr_bid_plan`` (A2) and
the reference mapping in ``oel_validation.reference_schedule_mapping`` (A3).
These re-exports keep existing imports working until the public surface is
curated in consolidation step A4.
"""

from open_energy_lab.simulator.fcr_bid_plan import (
    BidPlanProducer,
    FCRBidPlanValidationError,
    FIXED_FCR_BID_PLAN_SEMANTICS_VERSION,
    FixedFCRBidPlan,
    OptimizationMetric,
    PlanDiagnostic,
    SerializedScheduleReference,
    build_fixed_fcr_bid_plan,
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
