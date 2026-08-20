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
