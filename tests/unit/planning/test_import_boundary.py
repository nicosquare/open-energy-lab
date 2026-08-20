"""Import-boundary tests for the planned planning package."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


PLANNING_PACKAGE = "open_energy_lab.planning"
PLANNED_PLANNING_SUBMODULES = (
    "open_energy_lab.planning.dataset",
    "open_energy_lab.planning.problem",
    "open_energy_lab.planning.piecewise",
    "open_energy_lab.planning.optional_solver",
)


def test_planning_package_root_reserves_a_lightweight_public_boundary() -> None:
    module_spec = importlib.util.find_spec(PLANNING_PACKAGE)
    if module_spec is None:
        assert PLANNING_PACKAGE not in sys.modules
        return

    module = importlib.import_module(PLANNING_PACKAGE)

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "planning"
    assert module_file.parent.parent.name == "open_energy_lab"


def test_planning_root_import_defers_planned_submodule_loading() -> None:
    module_spec = importlib.util.find_spec(PLANNING_PACKAGE)
    if module_spec is None:
        for module_name in PLANNED_PLANNING_SUBMODULES:
            assert module_name not in sys.modules
        return

    for module_name in (PLANNING_PACKAGE, *PLANNED_PLANNING_SUBMODULES):
        sys.modules.pop(module_name, None)

    importlib.import_module(PLANNING_PACKAGE)

    for module_name in PLANNED_PLANNING_SUBMODULES:
        assert module_name not in sys.modules


def test_planned_planning_submodules_stay_within_the_reserved_package_boundary() -> None:
    package_spec = importlib.util.find_spec(PLANNING_PACKAGE)
    if package_spec is None:
        for module_name in PLANNED_PLANNING_SUBMODULES:
            try:
                module_spec = importlib.util.find_spec(module_name)
            except ModuleNotFoundError:
                module_spec = None
            assert module_spec is None
            assert module_name not in sys.modules
        return

    package = importlib.import_module(PLANNING_PACKAGE)
    package_dir = Path(package.__file__).resolve().parent

    for module_name in PLANNED_PLANNING_SUBMODULES:
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None:
            assert module_name not in sys.modules
            continue

        module = importlib.import_module(module_name)

        assert module_spec.origin is not None
        assert module.__file__ is not None
        assert Path(module_spec.origin).resolve().parent == package_dir
        assert Path(module.__file__).resolve().parent == package_dir
