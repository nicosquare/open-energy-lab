"""Simulator package boundary for the first migration target.

`open_energy_lab.simulator` is the stable package location for simulator work.
Concrete arbitrage-facing types remain experimental until later migration
phases promote them. This module intentionally stays import-light and does not
pull in optional research stacks.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fcr_settlement import (
        EnergySettlementInterval,
        FCRPenaltyRule,
        FCRSettlementBlock,
        FCRSettlementValidationError,
        SettlementBreakdown,
        settle_stacked_services,
    )
    from .load import LoadComponent
    from .planning_export import PlanningExportRequest, export_planning_dataset
    from .planning_study import (
        PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION,
        generate_planning_study_dataset,
    )
    from .pricing import (
        ArbitrageObjectiveRepresentation,
        DeterministicRulePolicy,
        PriceSignal,
    )
    from .pv import PVComponent
    from .scenario import (
        ArbitrageScenario,
        BatteryLoadPVScenario,
        BatteryComponent,
        DispatchRequestSeries,
        TimeGrid,
    )
    from .stochastic_demand import (
        DemandFamilyEvaluationRequest,
        DemandFamilyEvaluationResult,
        DemandScenarioEvaluationResult,
        SUPPORTED_SUMMARY_OUTPUT_FIELDS as DEMAND_SUPPORTED_SUMMARY_OUTPUT_FIELDS,
        evaluate_demand_family,
    )
    from .stochastic_weather import (
        SUPPORTED_SUMMARY_OUTPUT_FIELDS,
        WeatherFamilyEvaluationRequest,
        WeatherFamilyEvaluationResult,
        WeatherScenarioEvaluationResult,
        evaluate_weather_family,
    )
    from .stacked_service import (
        EnergyBaselineInterval,
        EnergyBaselineSchedule,
        FCRCapacitySchedule,
        FCRCommitmentInterval,
        MultiRateTimeContract,
        ReplayIntervalSummary,
        ReplaySample,
        SaturationEvent,
        StackedServiceReplayRequest,
        StackedServiceReplayResult,
        StackedServiceValidationError,
        StateCheckpoint,
        TerminalSOCTarget,
        TerminalSOCReport,
        build_energy_baseline_schedule,
        build_fcr_capacity_schedule,
        replay_stacked_services,
        replay_stacked_services_diagnostic,
    )
    from .restoration_service import (
        AFRRDirectionalPerformance,
        AFRRReplayRequest,
        AFRRReplayResult,
        MFRREventPerformance,
        MFRRPerformanceAggregate,
        MFRRReplayRequest,
        MFRRReplayResult,
        RestorationEnergyTotals,
        RestorationIntegrationGrid,
        RestorationReplaySample,
        RestorationReplayValidationError,
        build_afrr_replay_request,
        build_mfrr_replay_request,
        build_restoration_integration_grid,
        replay_afrr,
        replay_mfrr,
    )
    from .restoration_settlement import (
        AFRRRestorationSettlement,
        AreaPriceProxyMapping,
        DayAheadEnergyPrice,
        DirectionalActivationPrice,
        DirectionalCapacityPrice,
        MFRRRestorationSettlement,
        RestorationPenaltyRule,
        RestorationSettlement,
        RestorationSettlementDiagnostic,
        RestorationSettlementValidationError,
        SettlementAvailability,
        SettlementComponentStatus,
        SettlementPriceState,
        ThroughputDegradationRule,
        build_area_price_proxy_mapping,
        build_day_ahead_energy_price,
        build_directional_activation_price,
        build_directional_capacity_price,
        build_restoration_penalty_rule,
        build_throughput_degradation_rule,
        settle_restoration_services,
    )
    from .weather import WeatherComponent


_EXPORT_MAP = {
    "ArbitrageObjectiveRepresentation": (".pricing", "ArbitrageObjectiveRepresentation"),
    "ArbitrageScenario": (".scenario", "ArbitrageScenario"),
    "BatteryLoadPVScenario": (".scenario", "BatteryLoadPVScenario"),
    "BatteryComponent": (".scenario", "BatteryComponent"),
    "DEMAND_SUPPORTED_SUMMARY_OUTPUT_FIELDS": (
        ".stochastic_demand",
        "SUPPORTED_SUMMARY_OUTPUT_FIELDS",
    ),
    "DemandFamilyEvaluationRequest": (
        ".stochastic_demand",
        "DemandFamilyEvaluationRequest",
    ),
    "DemandFamilyEvaluationResult": (
        ".stochastic_demand",
        "DemandFamilyEvaluationResult",
    ),
    "DemandScenarioEvaluationResult": (
        ".stochastic_demand",
        "DemandScenarioEvaluationResult",
    ),
    "DeterministicRulePolicy": (".pricing", "DeterministicRulePolicy"),
    "DispatchRequestSeries": (".scenario", "DispatchRequestSeries"),
    "evaluate_demand_family": (".stochastic_demand", "evaluate_demand_family"),
    "export_planning_dataset": (".planning_export", "export_planning_dataset"),
    "generate_planning_study_dataset": (
        ".planning_study",
        "generate_planning_study_dataset",
    ),
    "evaluate_with_controller": (".controller_runner", "evaluate_with_controller"),
    "evaluate_weather_family": (".stochastic_weather", "evaluate_weather_family"),
    "LoadComponent": (".load", "LoadComponent"),
    "PlanningExportRequest": (".planning_export", "PlanningExportRequest"),
    "PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION": (
        ".planning_study",
        "PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION",
    ),
    "PVComponent": (".pv", "PVComponent"),
    "PriceSignal": (".pricing", "PriceSignal"),
    "SUPPORTED_SUMMARY_OUTPUT_FIELDS": (
        ".stochastic_weather",
        "SUPPORTED_SUMMARY_OUTPUT_FIELDS",
    ),
    "TimeGrid": (".scenario", "TimeGrid"),
    "WeatherComponent": (".weather", "WeatherComponent"),
    "WeatherFamilyEvaluationRequest": (
        ".stochastic_weather",
        "WeatherFamilyEvaluationRequest",
    ),
    "WeatherFamilyEvaluationResult": (
        ".stochastic_weather",
        "WeatherFamilyEvaluationResult",
    ),
    "WeatherScenarioEvaluationResult": (
        ".stochastic_weather",
        "WeatherScenarioEvaluationResult",
    ),
    "EnergyBaselineInterval": (".stacked_service", "EnergyBaselineInterval"),
    "EnergyBaselineSchedule": (".stacked_service", "EnergyBaselineSchedule"),
    "FCRCapacitySchedule": (".stacked_service", "FCRCapacitySchedule"),
    "FCRCommitmentInterval": (".stacked_service", "FCRCommitmentInterval"),
    "MultiRateTimeContract": (".stacked_service", "MultiRateTimeContract"),
    "ReplayIntervalSummary": (".stacked_service", "ReplayIntervalSummary"),
    "ReplaySample": (".stacked_service", "ReplaySample"),
    "SaturationEvent": (".stacked_service", "SaturationEvent"),
    "StackedServiceReplayRequest": (
        ".stacked_service",
        "StackedServiceReplayRequest",
    ),
    "StackedServiceReplayResult": (
        ".stacked_service",
        "StackedServiceReplayResult",
    ),
    "StackedServiceValidationError": (
        ".stacked_service",
        "StackedServiceValidationError",
    ),
    "StateCheckpoint": (".stacked_service", "StateCheckpoint"),
    "TerminalSOCTarget": (".stacked_service", "TerminalSOCTarget"),
    "TerminalSOCReport": (".stacked_service", "TerminalSOCReport"),
    "build_energy_baseline_schedule": (
        ".stacked_service",
        "build_energy_baseline_schedule",
    ),
    "build_fcr_capacity_schedule": (
        ".stacked_service",
        "build_fcr_capacity_schedule",
    ),
    "replay_stacked_services": (".stacked_service", "replay_stacked_services"),
    "replay_stacked_services_diagnostic": (
        ".stacked_service",
        "replay_stacked_services_diagnostic",
    ),
    "EnergySettlementInterval": (
        ".fcr_settlement",
        "EnergySettlementInterval",
    ),
    "FCRPenaltyRule": (".fcr_settlement", "FCRPenaltyRule"),
    "FCRSettlementBlock": (".fcr_settlement", "FCRSettlementBlock"),
    "FCRSettlementValidationError": (
        ".fcr_settlement",
        "FCRSettlementValidationError",
    ),
    "SettlementBreakdown": (".fcr_settlement", "SettlementBreakdown"),
    "settle_stacked_services": (".fcr_settlement", "settle_stacked_services"),
    "RestorationSettlementValidationError": (
        ".restoration_settlement",
        "RestorationSettlementValidationError",
    ),
    "SettlementAvailability": (
        ".restoration_settlement",
        "SettlementAvailability",
    ),
    "SettlementComponentStatus": (
        ".restoration_settlement",
        "SettlementComponentStatus",
    ),
    "SettlementPriceState": (
        ".restoration_settlement",
        "SettlementPriceState",
    ),
    "DayAheadEnergyPrice": (
        ".restoration_settlement",
        "DayAheadEnergyPrice",
    ),
    "DirectionalCapacityPrice": (
        ".restoration_settlement",
        "DirectionalCapacityPrice",
    ),
    "AreaPriceProxyMapping": (
        ".restoration_settlement",
        "AreaPriceProxyMapping",
    ),
    "DirectionalActivationPrice": (
        ".restoration_settlement",
        "DirectionalActivationPrice",
    ),
    "RestorationPenaltyRule": (
        ".restoration_settlement",
        "RestorationPenaltyRule",
    ),
    "ThroughputDegradationRule": (
        ".restoration_settlement",
        "ThroughputDegradationRule",
    ),
    "RestorationSettlementDiagnostic": (
        ".restoration_settlement",
        "RestorationSettlementDiagnostic",
    ),
    "RestorationSettlement": (
        ".restoration_settlement",
        "RestorationSettlement",
    ),
    "AFRRRestorationSettlement": (
        ".restoration_settlement",
        "AFRRRestorationSettlement",
    ),
    "MFRRRestorationSettlement": (
        ".restoration_settlement",
        "MFRRRestorationSettlement",
    ),
    "build_day_ahead_energy_price": (
        ".restoration_settlement",
        "build_day_ahead_energy_price",
    ),
    "build_directional_capacity_price": (
        ".restoration_settlement",
        "build_directional_capacity_price",
    ),
    "build_area_price_proxy_mapping": (
        ".restoration_settlement",
        "build_area_price_proxy_mapping",
    ),
    "build_directional_activation_price": (
        ".restoration_settlement",
        "build_directional_activation_price",
    ),
    "build_restoration_penalty_rule": (
        ".restoration_settlement",
        "build_restoration_penalty_rule",
    ),
    "build_throughput_degradation_rule": (
        ".restoration_settlement",
        "build_throughput_degradation_rule",
    ),
    "settle_restoration_services": (
        ".restoration_settlement",
        "settle_restoration_services",
    ),
    "RestorationReplayValidationError": (
        ".restoration_service",
        "RestorationReplayValidationError",
    ),
    "RestorationIntegrationGrid": (
        ".restoration_service",
        "RestorationIntegrationGrid",
    ),
    "RestorationReplaySample": (
        ".restoration_service",
        "RestorationReplaySample",
    ),
    "RestorationEnergyTotals": (
        ".restoration_service",
        "RestorationEnergyTotals",
    ),
    "AFRRReplayRequest": (".restoration_service", "AFRRReplayRequest"),
    "AFRRDirectionalPerformance": (
        ".restoration_service",
        "AFRRDirectionalPerformance",
    ),
    "AFRRReplayResult": (".restoration_service", "AFRRReplayResult"),
    "MFRRReplayRequest": (".restoration_service", "MFRRReplayRequest"),
    "MFRREventPerformance": (
        ".restoration_service",
        "MFRREventPerformance",
    ),
    "MFRRPerformanceAggregate": (
        ".restoration_service",
        "MFRRPerformanceAggregate",
    ),
    "MFRRReplayResult": (".restoration_service", "MFRRReplayResult"),
    "build_restoration_integration_grid": (
        ".restoration_service",
        "build_restoration_integration_grid",
    ),
    "build_afrr_replay_request": (
        ".restoration_service",
        "build_afrr_replay_request",
    ),
    "replay_afrr": (".restoration_service", "replay_afrr"),
    "build_mfrr_replay_request": (
        ".restoration_service",
        "build_mfrr_replay_request",
    ),
    "replay_mfrr": (".restoration_service", "replay_mfrr"),
}

__all__ = [
    "ArbitrageObjectiveRepresentation",
    "ArbitrageScenario",
    "BatteryLoadPVScenario",
    "BatteryComponent",
    "DEMAND_SUPPORTED_SUMMARY_OUTPUT_FIELDS",
    "DemandFamilyEvaluationRequest",
    "DemandFamilyEvaluationResult",
    "DemandScenarioEvaluationResult",
    "DeterministicRulePolicy",
    "DispatchRequestSeries",
    "evaluate_demand_family",
    "export_planning_dataset",
    "generate_planning_study_dataset",
    "evaluate_with_controller",
    "evaluate_weather_family",
    "LoadComponent",
    "PlanningExportRequest",
    "PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION",
    "PVComponent",
    "PriceSignal",
    "SUPPORTED_SUMMARY_OUTPUT_FIELDS",
    "TimeGrid",
    "WeatherComponent",
    "WeatherFamilyEvaluationRequest",
    "WeatherFamilyEvaluationResult",
    "WeatherScenarioEvaluationResult",
    "EnergyBaselineInterval",
    "EnergyBaselineSchedule",
    "FCRCapacitySchedule",
    "FCRCommitmentInterval",
    "MultiRateTimeContract",
    "ReplayIntervalSummary",
    "ReplaySample",
    "SaturationEvent",
    "StackedServiceReplayRequest",
    "StackedServiceReplayResult",
    "StackedServiceValidationError",
    "StateCheckpoint",
    "TerminalSOCTarget",
    "TerminalSOCReport",
    "build_energy_baseline_schedule",
    "build_fcr_capacity_schedule",
    "replay_stacked_services",
    "replay_stacked_services_diagnostic",
    "EnergySettlementInterval",
    "FCRPenaltyRule",
    "FCRSettlementBlock",
    "FCRSettlementValidationError",
    "SettlementBreakdown",
    "settle_stacked_services",
    "RestorationSettlementValidationError",
    "SettlementAvailability",
    "SettlementComponentStatus",
    "SettlementPriceState",
    "DayAheadEnergyPrice",
    "DirectionalCapacityPrice",
    "AreaPriceProxyMapping",
    "DirectionalActivationPrice",
    "RestorationPenaltyRule",
    "ThroughputDegradationRule",
    "RestorationSettlementDiagnostic",
    "RestorationSettlement",
    "AFRRRestorationSettlement",
    "MFRRRestorationSettlement",
    "build_day_ahead_energy_price",
    "build_directional_capacity_price",
    "build_area_price_proxy_mapping",
    "build_directional_activation_price",
    "build_restoration_penalty_rule",
    "build_throughput_degradation_rule",
    "settle_restoration_services",
    "RestorationReplayValidationError",
    "RestorationIntegrationGrid",
    "RestorationReplaySample",
    "RestorationEnergyTotals",
    "AFRRReplayRequest",
    "AFRRDirectionalPerformance",
    "AFRRReplayResult",
    "MFRRReplayRequest",
    "MFRREventPerformance",
    "MFRRPerformanceAggregate",
    "MFRRReplayResult",
    "build_restoration_integration_grid",
    "build_afrr_replay_request",
    "replay_afrr",
    "build_mfrr_replay_request",
    "replay_mfrr",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve exported simulator symbols at the stable package root."""

    try:
        module_name, attribute_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
