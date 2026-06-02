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


def test_root_import_does_not_load_optional_research_stacks() -> None:
    """The foundation package import must not initialize heavy optional stacks."""
    loaded_before_import = set(sys.modules)

    importlib.import_module("open_energy_lab")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()


def test_simulator_import_does_not_load_optional_research_stacks() -> None:
    """The simulator package import must stay isolated from heavy optional stacks."""
    loaded_before_import = set(sys.modules)

    importlib.import_module("open_energy_lab.simulator")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()


def test_core_import_does_not_load_optional_research_stacks() -> None:
    """The stable core package import must stay isolated from heavy optional stacks."""
    loaded_before_import = set(sys.modules)

    importlib.import_module("open_energy_lab.core")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()


@pytest.mark.parametrize(
    "module_name",
    (
        "open_energy_lab.core",
        "open_energy_lab.core.controller",
        "open_energy_lab.simulator",
        "open_energy_lab.simulator.controller_runner",
        "open_energy_lab.simulator.weather",
        "open_energy_lab.simulator.pv",
    ),
)
def test_simulator_submodule_imports_stay_clear_of_optional_research_stacks(
    module_name: str,
) -> None:
    """US3 modules must not pull optional research stacks at import time."""
    loaded_before_import = set(sys.modules)

    importlib.import_module(module_name)

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()
