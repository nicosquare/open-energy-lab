"""Import-boundary tests for the visualization package scaffold."""

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

PLANNED_VISUALIZATION_MODULES = (
    "open_energy_lab.visualization.inspection",
    "open_energy_lab.visualization.comparison",
    "open_energy_lab.visualization.plotting",
    "open_energy_lab.visualization._persistence",
)


def test_visualization_import_stays_lightweight() -> None:
    loaded_before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.visualization")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()
    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "visualization"
    assert module_file.parent.parent.name == "open_energy_lab"


def test_visualization_root_import_does_not_preload_plotting_module() -> None:
    loaded_before_import = set(sys.modules)

    importlib.import_module("open_energy_lab.visualization")

    loaded_by_import = set(sys.modules) - loaded_before_import
    assert "open_energy_lab.visualization.plotting" not in loaded_by_import


def test_planned_visualization_modules_reserve_lightweight_boundary() -> None:
    package = importlib.import_module("open_energy_lab.visualization")
    package_dir = Path(package.__file__).resolve().parent

    for module_name in PLANNED_VISUALIZATION_MODULES:
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
