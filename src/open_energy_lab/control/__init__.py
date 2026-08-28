"""Stable package-root public surface for shipped native controllers.

Ordinary ``open_energy_lab.control`` imports stay import-light by resolving the
documented controller exports lazily.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fcr_rolling_backtest import (
        AGGREGATION_POLICY,
        FAILURE_POLICY_COUPLED,
        FAILURE_POLICY_INDEPENDENT,
        RESUME_POLICY,
        AcceptedBidPolicy,
        AggregateMetricEvidence,
        CallerSuppliedRollingState,
        ContinuitySegment,
        DeliveryDateClassification,
        DeliveryDateRecordEnvelope,
        RollingFCRBatteryBinding,
        RollingFCRDataDescriptor,
        RollingFCRDayInput,
        RollingFCRDayRevision,
        RollingFCRExperimentProfile,
        RollingFCRNumericPolicy,
        RollingFCRStateLink,
        RollingFCRStudyManifest,
        RollingFCRStudyResult,
        RollingFCRValidationError,
        build_rolling_fcr_experiment_profile,
        build_rolling_fcr_study_manifest,
        run_rolling_fcr_study,
    )
    from .robust_fcr_reference import (
        JointReferenceCertificate,
        RobustFCRReferenceComparison,
        RobustFCRReferenceFixture,
        build_robust_fcr_reference_problem,
        compare_robust_fcr_reference,
        load_robust_fcr_reference_fixture,
    )
    from .robust_fcr_rolling import (
        RobustFCRAcceptedDecisionFixings,
        RobustFCRRollingBiddingProblem,
        RobustFCRRollingSolveResult,
        build_robust_fcr_rolling_problem,
        solve_robust_fcr_rolling_bid,
    )
    from .robust_fcr_bidding import (
        ConstraintFamilyResidual,
        FeasibilityAudit,
        HorizonWideActivationBudget,
        ObjectiveBreakdown,
        RecoveryWindowActivationBudget,
        RobustFCRBatteryParameters,
        RobustFCRBiddingProblem,
        RobustFCRBoundComparison,
        RobustFCRDecisions,
        RobustFCRFormulationProfile,
        RobustFCRPriceInputs,
        RobustFCRSolvePolicy,
        RobustFCRSolveResult,
        RobustFCRSolverDependencyUnavailableError,
        RobustFCRSolverUnavailableError,
        RobustFCRTimeContract,
        RobustFCRUncertaintyProfile,
        RobustFCRValidationError,
        TerminalStoredEnergyRule,
        build_robust_fcr_bidding_problem,
        build_robust_fcr_time_contract,
        compare_robust_fcr_bounds,
        derive_non_intraday_horizon_budget,
        solve_robust_fcr_bid,
    )
    from .fcr_bid_plan import (
        BidPlanProducer,
        FCRBidPlanValidationError,
        FixedFCRBidPlan,
        OptimizationMetric,
        PlanDiagnostic,
        SerializedScheduleReference,
        build_fixed_fcr_bid_plan,
    )
    from ._config import (
        PVSelfConsumptionConfig,
        PriceThresholdConfig,
        SocGuardrailConfig,
    )
    from .price_threshold import PriceThresholdController
    from .pv_self_consumption import PVSelfConsumptionController
    from .soc_guardrail import SocGuardrailController
    from .stacked_service import (
        ArbitrageOnlyBaselineConfig,
        BaselineScheduleBundle,
        RegulationOnlyBaselineConfig,
        StackedBaselineValidationError,
        StackedHeuristicConfig,
        build_arbitrage_only_baseline,
        build_regulation_only_baseline,
        build_stacked_heuristic_baseline,
    )
    from .restoration_service import (
        AFRRBaselineConfig,
        AFRRBaselineMode,
        DirectionalCapacityCommitmentInterval,
        DirectionalCapacitySchedule,
        MFRRBaselineConfig,
        MFRRBaselineMode,
        RestorationBaselineBundle,
        RestorationCapability,
        RestorationControlValidationError,
        RestorationEnergyBaselineInterval,
        RestorationEnergyBaselineSchedule,
        build_afrr_baseline,
        build_afrr_baseline_config,
        build_afrr_directional_capacity_schedule,
        build_mfrr_baseline,
        build_mfrr_baseline_config,
        build_mfrr_directional_capacity_schedule,
        build_restoration_capability,
    )


_EXPORT_MAP = {
    "AGGREGATION_POLICY": (".fcr_rolling_backtest", "AGGREGATION_POLICY"),
    "FAILURE_POLICY_COUPLED": (
        ".fcr_rolling_backtest",
        "FAILURE_POLICY_COUPLED",
    ),
    "FAILURE_POLICY_INDEPENDENT": (
        ".fcr_rolling_backtest",
        "FAILURE_POLICY_INDEPENDENT",
    ),
    "RESUME_POLICY": (".fcr_rolling_backtest", "RESUME_POLICY"),
    "AcceptedBidPolicy": (".fcr_rolling_backtest", "AcceptedBidPolicy"),
    "AggregateMetricEvidence": (
        ".fcr_rolling_backtest",
        "AggregateMetricEvidence",
    ),
    "CallerSuppliedRollingState": (
        ".fcr_rolling_backtest",
        "CallerSuppliedRollingState",
    ),
    "ContinuitySegment": (".fcr_rolling_backtest", "ContinuitySegment"),
    "DeliveryDateClassification": (
        ".fcr_rolling_backtest",
        "DeliveryDateClassification",
    ),
    "DeliveryDateRecordEnvelope": (
        ".fcr_rolling_backtest",
        "DeliveryDateRecordEnvelope",
    ),
    "RollingFCRBatteryBinding": (
        ".fcr_rolling_backtest",
        "RollingFCRBatteryBinding",
    ),
    "RollingFCRDataDescriptor": (
        ".fcr_rolling_backtest",
        "RollingFCRDataDescriptor",
    ),
    "RollingFCRDayInput": (".fcr_rolling_backtest", "RollingFCRDayInput"),
    "RollingFCRDayRevision": (
        ".fcr_rolling_backtest",
        "RollingFCRDayRevision",
    ),
    "RollingFCRExperimentProfile": (
        ".fcr_rolling_backtest",
        "RollingFCRExperimentProfile",
    ),
    "RollingFCRNumericPolicy": (
        ".fcr_rolling_backtest",
        "RollingFCRNumericPolicy",
    ),
    "RollingFCRStateLink": (
        ".fcr_rolling_backtest",
        "RollingFCRStateLink",
    ),
    "RollingFCRStudyManifest": (
        ".fcr_rolling_backtest",
        "RollingFCRStudyManifest",
    ),
    "RollingFCRStudyResult": (
        ".fcr_rolling_backtest",
        "RollingFCRStudyResult",
    ),
    "RollingFCRValidationError": (
        ".fcr_rolling_backtest",
        "RollingFCRValidationError",
    ),
    "build_rolling_fcr_experiment_profile": (
        ".fcr_rolling_backtest",
        "build_rolling_fcr_experiment_profile",
    ),
    "build_rolling_fcr_study_manifest": (
        ".fcr_rolling_backtest",
        "build_rolling_fcr_study_manifest",
    ),
    "run_rolling_fcr_study": (
        ".fcr_rolling_backtest",
        "run_rolling_fcr_study",
    ),
    "RobustFCRAcceptedDecisionFixings": (
        ".robust_fcr_rolling",
        "RobustFCRAcceptedDecisionFixings",
    ),
    "RobustFCRRollingBiddingProblem": (
        ".robust_fcr_rolling",
        "RobustFCRRollingBiddingProblem",
    ),
    "RobustFCRRollingSolveResult": (
        ".robust_fcr_rolling",
        "RobustFCRRollingSolveResult",
    ),
    "build_robust_fcr_rolling_problem": (
        ".robust_fcr_rolling",
        "build_robust_fcr_rolling_problem",
    ),
    "solve_robust_fcr_rolling_bid": (
        ".robust_fcr_rolling",
        "solve_robust_fcr_rolling_bid",
    ),
    "JointReferenceCertificate": (
        ".robust_fcr_reference",
        "JointReferenceCertificate",
    ),
    "RobustFCRReferenceComparison": (
        ".robust_fcr_reference",
        "RobustFCRReferenceComparison",
    ),
    "RobustFCRReferenceFixture": (
        ".robust_fcr_reference",
        "RobustFCRReferenceFixture",
    ),
    "build_robust_fcr_reference_problem": (
        ".robust_fcr_reference",
        "build_robust_fcr_reference_problem",
    ),
    "compare_robust_fcr_reference": (
        ".robust_fcr_reference",
        "compare_robust_fcr_reference",
    ),
    "load_robust_fcr_reference_fixture": (
        ".robust_fcr_reference",
        "load_robust_fcr_reference_fixture",
    ),
    "ConstraintFamilyResidual": (
        ".robust_fcr_bidding",
        "ConstraintFamilyResidual",
    ),
    "FeasibilityAudit": (".robust_fcr_bidding", "FeasibilityAudit"),
    "HorizonWideActivationBudget": (
        ".robust_fcr_bidding",
        "HorizonWideActivationBudget",
    ),
    "ObjectiveBreakdown": (".robust_fcr_bidding", "ObjectiveBreakdown"),
    "RecoveryWindowActivationBudget": (
        ".robust_fcr_bidding",
        "RecoveryWindowActivationBudget",
    ),
    "RobustFCRBatteryParameters": (
        ".robust_fcr_bidding",
        "RobustFCRBatteryParameters",
    ),
    "RobustFCRBiddingProblem": (
        ".robust_fcr_bidding",
        "RobustFCRBiddingProblem",
    ),
    "RobustFCRBoundComparison": (
        ".robust_fcr_bidding",
        "RobustFCRBoundComparison",
    ),
    "RobustFCRDecisions": (".robust_fcr_bidding", "RobustFCRDecisions"),
    "RobustFCRFormulationProfile": (
        ".robust_fcr_bidding",
        "RobustFCRFormulationProfile",
    ),
    "RobustFCRPriceInputs": (
        ".robust_fcr_bidding",
        "RobustFCRPriceInputs",
    ),
    "RobustFCRSolvePolicy": (".robust_fcr_bidding", "RobustFCRSolvePolicy"),
    "RobustFCRSolveResult": (".robust_fcr_bidding", "RobustFCRSolveResult"),
    "RobustFCRSolverDependencyUnavailableError": (
        ".robust_fcr_bidding",
        "RobustFCRSolverDependencyUnavailableError",
    ),
    "RobustFCRSolverUnavailableError": (
        ".robust_fcr_bidding",
        "RobustFCRSolverUnavailableError",
    ),
    "RobustFCRTimeContract": (".robust_fcr_bidding", "RobustFCRTimeContract"),
    "RobustFCRUncertaintyProfile": (
        ".robust_fcr_bidding",
        "RobustFCRUncertaintyProfile",
    ),
    "RobustFCRValidationError": (
        ".robust_fcr_bidding",
        "RobustFCRValidationError",
    ),
    "TerminalStoredEnergyRule": (
        ".robust_fcr_bidding",
        "TerminalStoredEnergyRule",
    ),
    "build_robust_fcr_bidding_problem": (
        ".robust_fcr_bidding",
        "build_robust_fcr_bidding_problem",
    ),
    "build_robust_fcr_time_contract": (
        ".robust_fcr_bidding",
        "build_robust_fcr_time_contract",
    ),
    "compare_robust_fcr_bounds": (
        ".robust_fcr_bidding",
        "compare_robust_fcr_bounds",
    ),
    "derive_non_intraday_horizon_budget": (
        ".robust_fcr_bidding",
        "derive_non_intraday_horizon_budget",
    ),
    "solve_robust_fcr_bid": (".robust_fcr_bidding", "solve_robust_fcr_bid"),
    "BidPlanProducer": (".fcr_bid_plan", "BidPlanProducer"),
    "FCRBidPlanValidationError": (
        ".fcr_bid_plan",
        "FCRBidPlanValidationError",
    ),
    "FixedFCRBidPlan": (".fcr_bid_plan", "FixedFCRBidPlan"),
    "OptimizationMetric": (".fcr_bid_plan", "OptimizationMetric"),
    "PlanDiagnostic": (".fcr_bid_plan", "PlanDiagnostic"),
    "SerializedScheduleReference": (
        ".fcr_bid_plan",
        "SerializedScheduleReference",
    ),
    "build_fixed_fcr_bid_plan": (
        ".fcr_bid_plan",
        "build_fixed_fcr_bid_plan",
    ),
    "PVSelfConsumptionConfig": ("._config", "PVSelfConsumptionConfig"),
    "PVSelfConsumptionController": (
        ".pv_self_consumption",
        "PVSelfConsumptionController",
    ),
    "PriceThresholdConfig": ("._config", "PriceThresholdConfig"),
    "PriceThresholdController": (".price_threshold", "PriceThresholdController"),
    "SocGuardrailConfig": ("._config", "SocGuardrailConfig"),
    "SocGuardrailController": (".soc_guardrail", "SocGuardrailController"),
    "ArbitrageOnlyBaselineConfig": (
        ".stacked_service",
        "ArbitrageOnlyBaselineConfig",
    ),
    "BaselineScheduleBundle": (".stacked_service", "BaselineScheduleBundle"),
    "RegulationOnlyBaselineConfig": (
        ".stacked_service",
        "RegulationOnlyBaselineConfig",
    ),
    "StackedBaselineValidationError": (
        ".stacked_service",
        "StackedBaselineValidationError",
    ),
    "StackedHeuristicConfig": (".stacked_service", "StackedHeuristicConfig"),
    "build_arbitrage_only_baseline": (
        ".stacked_service",
        "build_arbitrage_only_baseline",
    ),
    "build_regulation_only_baseline": (
        ".stacked_service",
        "build_regulation_only_baseline",
    ),
    "build_stacked_heuristic_baseline": (
        ".stacked_service",
        "build_stacked_heuristic_baseline",
    ),
    "RestorationControlValidationError": (
        ".restoration_service",
        "RestorationControlValidationError",
    ),
    "DirectionalCapacityCommitmentInterval": (
        ".restoration_service",
        "DirectionalCapacityCommitmentInterval",
    ),
    "DirectionalCapacitySchedule": (
        ".restoration_service",
        "DirectionalCapacitySchedule",
    ),
    "RestorationEnergyBaselineInterval": (
        ".restoration_service",
        "RestorationEnergyBaselineInterval",
    ),
    "RestorationEnergyBaselineSchedule": (
        ".restoration_service",
        "RestorationEnergyBaselineSchedule",
    ),
    "RestorationCapability": (
        ".restoration_service",
        "RestorationCapability",
    ),
    "AFRRBaselineMode": (".restoration_service", "AFRRBaselineMode"),
    "AFRRBaselineConfig": (".restoration_service", "AFRRBaselineConfig"),
    "MFRRBaselineMode": (".restoration_service", "MFRRBaselineMode"),
    "MFRRBaselineConfig": (".restoration_service", "MFRRBaselineConfig"),
    "RestorationBaselineBundle": (
        ".restoration_service",
        "RestorationBaselineBundle",
    ),
    "build_restoration_capability": (
        ".restoration_service",
        "build_restoration_capability",
    ),
    "build_afrr_directional_capacity_schedule": (
        ".restoration_service",
        "build_afrr_directional_capacity_schedule",
    ),
    "build_afrr_baseline_config": (
        ".restoration_service",
        "build_afrr_baseline_config",
    ),
    "build_afrr_baseline": (".restoration_service", "build_afrr_baseline"),
    "build_mfrr_directional_capacity_schedule": (
        ".restoration_service",
        "build_mfrr_directional_capacity_schedule",
    ),
    "build_mfrr_baseline_config": (
        ".restoration_service",
        "build_mfrr_baseline_config",
    ),
    "build_mfrr_baseline": (".restoration_service", "build_mfrr_baseline"),
}

__all__ = sorted([
    "AGGREGATION_POLICY",
    "AFRRBaselineConfig",
    "AFRRBaselineMode",
    "ArbitrageOnlyBaselineConfig",
    "BaselineScheduleBundle",
    "BidPlanProducer",
    "AcceptedBidPolicy",
    "AggregateMetricEvidence",
    "CallerSuppliedRollingState",
    "ContinuitySegment",
    "ConstraintFamilyResidual",
    "DirectionalCapacityCommitmentInterval",
    "DirectionalCapacitySchedule",
    "DeliveryDateClassification",
    "DeliveryDateRecordEnvelope",
    "FAILURE_POLICY_COUPLED",
    "FAILURE_POLICY_INDEPENDENT",
    "FCRBidPlanValidationError",
    "FeasibilityAudit",
    "FixedFCRBidPlan",
    "HorizonWideActivationBudget",
    "JointReferenceCertificate",
    "MFRRBaselineConfig",
    "MFRRBaselineMode",
    "ObjectiveBreakdown",
    "OptimizationMetric",
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PlanDiagnostic",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "RegulationOnlyBaselineConfig",
    "RecoveryWindowActivationBudget",
    "RESUME_POLICY",
    "RestorationBaselineBundle",
    "RestorationCapability",
    "RestorationControlValidationError",
    "RestorationEnergyBaselineInterval",
    "RestorationEnergyBaselineSchedule",
    "RobustFCRBatteryParameters",
    "RobustFCRAcceptedDecisionFixings",
    "RobustFCRBiddingProblem",
    "RobustFCRBoundComparison",
    "RobustFCRDecisions",
    "RobustFCRFormulationProfile",
    "RobustFCRPriceInputs",
    "RobustFCRReferenceComparison",
    "RobustFCRReferenceFixture",
    "RobustFCRRollingBiddingProblem",
    "RobustFCRRollingSolveResult",
    "RobustFCRSolvePolicy",
    "RobustFCRSolveResult",
    "RobustFCRSolverDependencyUnavailableError",
    "RobustFCRSolverUnavailableError",
    "RobustFCRTimeContract",
    "RobustFCRUncertaintyProfile",
    "RobustFCRValidationError",
    "RollingFCRBatteryBinding",
    "RollingFCRDataDescriptor",
    "RollingFCRDayInput",
    "RollingFCRDayRevision",
    "RollingFCRExperimentProfile",
    "RollingFCRNumericPolicy",
    "RollingFCRStateLink",
    "RollingFCRStudyManifest",
    "RollingFCRStudyResult",
    "RollingFCRValidationError",
    "SerializedScheduleReference",
    "SocGuardrailConfig",
    "SocGuardrailController",
    "StackedBaselineValidationError",
    "StackedHeuristicConfig",
    "TerminalStoredEnergyRule",
    "build_afrr_baseline",
    "build_afrr_baseline_config",
    "build_afrr_directional_capacity_schedule",
    "build_arbitrage_only_baseline",
    "build_fixed_fcr_bid_plan",
    "build_mfrr_baseline",
    "build_mfrr_baseline_config",
    "build_mfrr_directional_capacity_schedule",
    "build_regulation_only_baseline",
    "build_restoration_capability",
    "build_robust_fcr_bidding_problem",
    "build_robust_fcr_reference_problem",
    "build_robust_fcr_rolling_problem",
    "build_robust_fcr_time_contract",
    "build_rolling_fcr_experiment_profile",
    "build_rolling_fcr_study_manifest",
    "build_stacked_heuristic_baseline",
    "compare_robust_fcr_bounds",
    "compare_robust_fcr_reference",
    "derive_non_intraday_horizon_budget",
    "load_robust_fcr_reference_fixture",
    "run_rolling_fcr_study",
    "solve_robust_fcr_bid",
    "solve_robust_fcr_rolling_bid",
])


def __getattr__(name: str) -> Any:
    """Lazily resolve the stable control package exports."""

    try:
        module_name, attribute_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
