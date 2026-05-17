"""Import-boundary tests for the simulator package."""

from __future__ import annotations

import importlib
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
    assert module.__all__ == []


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
