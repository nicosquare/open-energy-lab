"""Import-boundary tests for optional research dependencies."""

from __future__ import annotations

import importlib
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


def _optional_modules_loaded_after(before_import: set[str]) -> set[str]:
    return OPTIONAL_RESEARCH_MODULES & (set(sys.modules) - before_import)


def _assert_import_stays_clear_of_optional_research_stacks(module_name: str) -> None:
    loaded_before_import = set(sys.modules)

    importlib.import_module(module_name)

    assert _optional_modules_loaded_after(loaded_before_import) == set()


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


@pytest.mark.parametrize(
    "module_name",
    (
        "open_energy_lab.core",
        "open_energy_lab.core.controller",
        "open_energy_lab.simulator",
        "open_energy_lab.simulator.controller_runner",
        "open_energy_lab.simulator.weather",
        "open_energy_lab.simulator.pv",
        "open_energy_lab.control._config",
        "open_energy_lab.control.price_threshold",
        "open_energy_lab.control.soc_guardrail",
        "open_energy_lab.control.pv_self_consumption",
    ),
)
def test_simulator_submodule_imports_stay_clear_of_optional_research_stacks(
    module_name: str,
) -> None:
    """US3 modules must not pull optional research stacks at import time."""
    _assert_import_stays_clear_of_optional_research_stacks(module_name)
