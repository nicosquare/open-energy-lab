"""Import-boundary tests for optional research dependencies."""

from __future__ import annotations

import importlib
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
