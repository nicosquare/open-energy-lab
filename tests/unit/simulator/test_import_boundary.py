"""Import-boundary tests for the simulator package."""

from __future__ import annotations

import importlib
import importlib.util
import sys
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
        "DeterministicRulePolicy",
        "DispatchRequestSeries",
        "evaluate_with_controller",
        "evaluate_weather_family",
        "LoadComponent",
        "PVComponent",
        "PriceSignal",
        "SUPPORTED_SUMMARY_OUTPUT_FIELDS",
        "TimeGrid",
        "WeatherComponent",
        "WeatherFamilyEvaluationRequest",
        "WeatherFamilyEvaluationResult",
        "WeatherScenarioEvaluationResult",
    ]
    assert module.ArbitrageScenario.__module__ == "open_energy_lab.simulator.scenario"
    assert module.BatteryLoadPVScenario.__module__ == "open_energy_lab.simulator.scenario"
    assert (
        module.evaluate_with_controller.__module__
        == "open_energy_lab.simulator.controller_runner"
    )
    assert (
        module.evaluate_weather_family.__module__
        == "open_energy_lab.simulator.stochastic_weather"
    )
    assert module.LoadComponent.__module__ == "open_energy_lab.simulator.load"
    assert module.PriceSignal.__module__ == "open_energy_lab.simulator.pricing"
    assert module.PVComponent.__module__ == "open_energy_lab.simulator.pv"
    assert module.WeatherComponent.__module__ == "open_energy_lab.simulator.weather"
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
