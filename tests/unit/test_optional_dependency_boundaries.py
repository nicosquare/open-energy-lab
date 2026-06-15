"""Import-boundary tests for optional research dependencies."""

from __future__ import annotations

import importlib
import importlib.util
import pytest
import sys


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
WEATHER_WORKFLOW_MODULES = {
    "pandas",
    "pvlib",
    "timezonefinder",
}

VISUALIZATION_MODULES = (
    "open_energy_lab.visualization",
    "open_energy_lab.visualization.inspection",
    "open_energy_lab.visualization.comparison",
    "open_energy_lab.visualization._persistence",
    "open_energy_lab.visualization.plotting",
)


def _optional_modules_loaded_after(before_import: set[str]) -> set[str]:
    return OPTIONAL_RESEARCH_MODULES & (set(sys.modules) - before_import)


def _forbidden_modules_loaded_after(
    before_import: set[str],
    forbidden_modules: set[str],
) -> set[str]:
    return forbidden_modules & (set(sys.modules) - before_import)


def _assert_import_stays_clear_of_optional_research_stacks(module_name: str) -> None:
    module_spec = importlib.util.find_spec(module_name)
    if module_spec is None:
        assert module_name not in sys.modules
        return

    loaded_before_import = set(sys.modules)

    importlib.import_module(module_name)

    assert _optional_modules_loaded_after(loaded_before_import) == set()


def _assert_import_stays_clear_of_forbidden_modules(
    module_name: str,
    forbidden_modules: set[str],
) -> None:
    module_spec = importlib.util.find_spec(module_name)
    if module_spec is None:
        assert module_name not in sys.modules
        return

    loaded_before_import = set(sys.modules)

    importlib.import_module(module_name)

    assert _forbidden_modules_loaded_after(loaded_before_import, forbidden_modules) == set()


def test_root_import_does_not_load_optional_research_stacks() -> None:
    """The foundation package import must not initialize heavy optional stacks."""
    _assert_import_stays_clear_of_optional_research_stacks("open_energy_lab")


def test_simulator_import_does_not_load_optional_research_stacks() -> None:
    """The simulator package import must stay isolated from heavy optional stacks."""
    _assert_import_stays_clear_of_optional_research_stacks("open_energy_lab.simulator")


def test_core_import_does_not_load_optional_research_stacks() -> None:
    """The stable core package import must stay isolated from heavy optional stacks."""
    _assert_import_stays_clear_of_optional_research_stacks("open_energy_lab.core")


def test_control_import_does_not_load_optional_research_stacks() -> None:
    """The native control package import must stay isolated from heavy optional stacks."""
    _assert_import_stays_clear_of_optional_research_stacks("open_energy_lab.control")


def test_weather_import_does_not_load_optional_research_stacks() -> None:
    """The weather package import must stay isolated from heavy optional stacks."""
    _assert_import_stays_clear_of_optional_research_stacks("open_energy_lab.weather")


def test_demand_import_does_not_load_optional_research_stacks() -> None:
    """The demand package import must stay isolated from heavy optional stacks."""
    _assert_import_stays_clear_of_optional_research_stacks("open_energy_lab.demand")


def test_visualization_import_does_not_load_optional_research_stacks() -> None:
    """The stable visualization package import must stay isolated from optional stacks."""
    _assert_import_stays_clear_of_optional_research_stacks("open_energy_lab.visualization")


@pytest.mark.parametrize(
    "module_name",
    (
        "open_energy_lab.core",
        "open_energy_lab.core.controller",
        "open_energy_lab.simulator",
        "open_energy_lab.simulator.controller_runner",
        "open_energy_lab.simulator.weather",
        "open_energy_lab.simulator.pv",
        "open_energy_lab.simulator.stochastic_weather",
        "open_energy_lab.control._config",
        "open_energy_lab.control.price_threshold",
        "open_energy_lab.control.soc_guardrail",
        "open_energy_lab.control.pv_self_consumption",
        "open_energy_lab.weather",
        "open_energy_lab.demand",
        "open_energy_lab.simulator.stochastic_demand",
        *VISUALIZATION_MODULES,
    ),
)
def test_simulator_submodule_imports_stay_clear_of_optional_research_stacks(
    module_name: str,
) -> None:
    """Stable package submodules must not pull optional research stacks at import time."""
    _assert_import_stays_clear_of_optional_research_stacks(module_name)


@pytest.mark.parametrize(
    "module_name",
    (
        "open_energy_lab.weather",
        "open_energy_lab.simulator.stochastic_weather",
        "open_energy_lab.demand",
        "open_energy_lab.simulator.stochastic_demand",
    ),
)
def test_weather_related_imports_do_not_load_isolated_fetch_dependencies(
    module_name: str,
) -> None:
    """Weather-facing imports must not eagerly load fit/fetch dependencies at import time."""
    _assert_import_stays_clear_of_forbidden_modules(
        module_name,
        WEATHER_WORKFLOW_MODULES,
    )
