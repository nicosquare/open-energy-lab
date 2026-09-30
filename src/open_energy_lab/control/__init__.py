"""Controllers, heuristic baselines, robust FCR bidding, and rolling FCR studies.

The root exports the main workflows and types; everything else stays
importable from its submodule.
"""

from __future__ import annotations

from ._config import (
    PVSelfConsumptionConfig,
    PriceThresholdConfig,
    SocGuardrailConfig,
)
from .fcr_rolling_backtest import (
    RollingFCRDayInput,
    RollingFCRStudyResult,
    RollingFCRValidationError,
    aggregate_rolling_fcr_records,
    build_rolling_fcr_experiment_profile,
    build_rolling_fcr_study_manifest,
    load_rolling_fcr_study_result,
    run_rolling_fcr_study,
)
from .price_threshold import (
    PriceThresholdController,
)
from .pv_self_consumption import (
    PVSelfConsumptionController,
)
from .restoration_service import (
    AFRRBaselineMode,
    MFRRBaselineMode,
    build_afrr_baseline,
    build_afrr_baseline_config,
    build_mfrr_baseline,
    build_mfrr_baseline_config,
)
from .robust_fcr_bidding import (
    RecoveryWindowActivationBudget,
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRSolveResult,
    RobustFCRUncertaintyProfile,
    RobustFCRValidationError,
    TerminalStoredEnergyRule,
    build_robust_fcr_bidding_problem,
    build_robust_fcr_time_contract,
    compare_robust_fcr_bounds,
    derive_non_intraday_horizon_budget,
    solve_robust_fcr_bid,
)
from .soc_guardrail import (
    SocGuardrailController,
)
from .stacked_service import (
    StackedHeuristicConfig,
    build_arbitrage_only_baseline,
    build_regulation_only_baseline,
    build_stacked_heuristic_baseline,
)

__all__ = [
    "AFRRBaselineMode",
    "MFRRBaselineMode",
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "RecoveryWindowActivationBudget",
    "RobustFCRBatteryParameters",
    "RobustFCRPriceInputs",
    "RobustFCRSolvePolicy",
    "RobustFCRSolveResult",
    "RobustFCRUncertaintyProfile",
    "RobustFCRValidationError",
    "RollingFCRDayInput",
    "RollingFCRStudyResult",
    "RollingFCRValidationError",
    "SocGuardrailConfig",
    "SocGuardrailController",
    "StackedHeuristicConfig",
    "TerminalStoredEnergyRule",
    "aggregate_rolling_fcr_records",
    "build_afrr_baseline",
    "build_afrr_baseline_config",
    "build_arbitrage_only_baseline",
    "build_mfrr_baseline",
    "build_mfrr_baseline_config",
    "build_regulation_only_baseline",
    "build_robust_fcr_bidding_problem",
    "build_robust_fcr_time_contract",
    "build_rolling_fcr_experiment_profile",
    "build_rolling_fcr_study_manifest",
    "build_stacked_heuristic_baseline",
    "compare_robust_fcr_bounds",
    "derive_non_intraday_horizon_budget",
    "load_rolling_fcr_study_result",
    "run_rolling_fcr_study",
    "solve_robust_fcr_bid",
]
