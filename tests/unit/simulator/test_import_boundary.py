"""Import-boundary tests for the simulator package."""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path


OPTIONAL_RESEARCH_MODULES = {
    "citylearn",
    "docplex",
    "gurobipy",
    "jupyter",
    "pyomo",
    "spflow",
    "torch",
    "torchrl",
    "wandb",
}


def _run_isolated_python(source: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, (
        f"isolated import check failed\nstdout:\n{completed.stdout}"
        f"\nstderr:\n{completed.stderr}"
    )


def test_simulator_import_stays_lightweight() -> None:
    loaded_before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.simulator")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()
    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "simulator"
    assert "evaluate_with_controller" in dir(module)
    assert module.__all__ == [
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
    assert module.ArbitrageScenario.__module__ == "open_energy_lab.simulator.scenario"
    assert module.BatteryLoadPVScenario.__module__ == "open_energy_lab.simulator.scenario"
    assert (
        module.evaluate_with_controller.__module__
        == "open_energy_lab.simulator.controller_runner"
    )
    assert (
        module.evaluate_demand_family.__module__
        == "open_energy_lab.simulator.stochastic_demand"
    )
    assert (
        module.export_planning_dataset.__module__
        == "open_energy_lab.simulator.planning_export"
    )
    assert (
        module.evaluate_weather_family.__module__
        == "open_energy_lab.simulator.stochastic_weather"
    )
    assert module.LoadComponent.__module__ == "open_energy_lab.simulator.load"
    assert (
        module.PlanningExportRequest.__module__
        == "open_energy_lab.simulator.planning_export"
    )
    assert module.PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION == (
        "grid-balanced-dispatch-v2"
    )
    assert module.PriceSignal.__module__ == "open_energy_lab.simulator.pricing"
    assert module.PVComponent.__module__ == "open_energy_lab.simulator.pv"
    assert module.WeatherComponent.__module__ == "open_energy_lab.simulator.weather"
    assert (
        module.DemandFamilyEvaluationRequest.__module__
        == "open_energy_lab.simulator.stochastic_demand"
    )
    assert (
        module.DemandFamilyEvaluationResult.__module__
        == "open_energy_lab.simulator.stochastic_demand"
    )
    assert (
        module.DemandScenarioEvaluationResult.__module__
        == "open_energy_lab.simulator.stochastic_demand"
    )
    assert (
        module.WeatherFamilyEvaluationRequest.__module__
        == "open_energy_lab.simulator.stochastic_weather"
    )
    assert (
        module.WeatherFamilyEvaluationResult.__module__
        == "open_energy_lab.simulator.stochastic_weather"
    )
    assert (
        module.WeatherScenarioEvaluationResult.__module__
        == "open_energy_lab.simulator.stochastic_weather"
    )
    assert module.SUPPORTED_SUMMARY_OUTPUT_FIELDS == (
        "pv_generation_kw",
        "net_grid_power_kw",
        "unmet_load_kw",
        "step_settlement",
    )
    assert module.DEMAND_SUPPORTED_SUMMARY_OUTPUT_FIELDS == (
        "site_electric_load_kw",
        "local_cooling_electric_kw",
        "served_cooling_rt",
        "unserved_cooling_rt",
        "net_grid_power_kw",
        "step_settlement",
        "district_cooling_settlement",
    )
    assert (
        module.StackedServiceReplayRequest.__module__
        == "open_energy_lab.simulator.stacked_service"
    )
    assert (
        module.FCRPenaltyRule.__module__
        == "open_energy_lab.simulator.fcr_settlement"
    )
    assert (
        module.AFRRReplayRequest.__module__
        == "open_energy_lab.simulator.restoration_service"
    )
    assert module.replay_afrr.__module__ == (
        "open_energy_lab.simulator.restoration_service"
    )


def test_stacked_service_exports_remain_lazy_and_import_light() -> None:
    _run_isolated_python(
        """
        import sys

        loaded_before_import = set(sys.modules)
        import open_energy_lab.simulator as module

        assert "open_energy_lab.simulator.stacked_service" not in sys.modules
        assert "open_energy_lab.simulator.fcr_settlement" not in sys.modules
        assert "open_energy_lab.simulator.restoration_service" not in sys.modules
        assert module.StackedServiceReplayResult.__module__ == (
            "open_energy_lab.simulator.stacked_service"
        )
        assert "open_energy_lab.simulator.stacked_service" in sys.modules
        assert "open_energy_lab.simulator.fcr_settlement" not in sys.modules
        assert module.SettlementBreakdown.__module__ == (
            "open_energy_lab.simulator.fcr_settlement"
        )
        assert "open_energy_lab.simulator.restoration_service" not in sys.modules
        assert module.AFRRReplayResult.__module__ == (
            "open_energy_lab.simulator.restoration_service"
        )
        assert "open_energy_lab.simulator.restoration_service" in sys.modules

        optional_research_modules = {
            "citylearn",
            "docplex",
            "gurobipy",
            "jupyter",
            "pyomo",
            "spflow",
            "torch",
            "torchrl",
            "wandb",
        }
        loaded_by_access = set(sys.modules) - loaded_before_import
        assert optional_research_modules.isdisjoint(loaded_by_access)
        """
    )


def test_controller_runner_import_and_export_stay_lightweight() -> None:
    loaded_before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.simulator.controller_runner")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()
    assert module.__all__ == ["evaluate_with_controller"]
    assert module.evaluate_with_controller.__module__ == module.__name__


def test_internal_foundation_helpers_import_without_optional_stacks() -> None:
    loaded_before_import = set(sys.modules)

    units = importlib.import_module("open_energy_lab.simulator._units")
    graph = importlib.import_module("open_energy_lab.simulator._graph")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()
    assert units.DEFAULT_ABSOLUTE_TOLERANCE == 1e-6
    assert units.POSITIVE_DISPATCH_MEANING == "charge"
    assert graph.ComponentGraph.__name__ == "ComponentGraph"
    assert graph.Relation.DERIVES.value == "derives"
    assert graph.Relation.FEEDS.value == "feeds"


def test_future_multi_component_modules_reserve_import_light_boundary() -> None:
    package = importlib.import_module("open_energy_lab.simulator")
    package_dir = Path(package.__file__).resolve().parent

    for module_name in (
        "open_energy_lab.simulator.load",
        "open_energy_lab.simulator.weather",
        "open_energy_lab.simulator.pv",
    ):
        loaded_before_import = set(sys.modules)
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None:
            assert module_name not in sys.modules
            continue

        importlib.import_module(module_name)
        loaded_by_import = set(sys.modules) - loaded_before_import
        optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import
        assert optional_modules_loaded == set()
        assert module_spec.origin is not None
        assert Path(module_spec.origin).resolve().parent == package_dir
