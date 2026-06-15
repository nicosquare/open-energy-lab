"""Package-surface maturity checks for the planned demand package."""

from __future__ import annotations

import importlib
import importlib.util
import sys


DEMAND_PACKAGE = "open_energy_lab.demand"
EXPECTED_ROOT_EXPORTS: list[str] = []
PLANNED_SUBMODULES = (
    "open_energy_lab.demand._aligned_history",
    "open_energy_lab.demand._weather_response",
    "open_energy_lab.demand.fit",
    "open_energy_lab.demand.artifact",
    "open_energy_lab.demand.sampling",
)


def _demand_package_spec():
    try:
        return importlib.util.find_spec(DEMAND_PACKAGE)
    except ModuleNotFoundError:
        return None


def _clear_demand_modules() -> None:
    for module_name in tuple(sys.modules):
        if module_name == DEMAND_PACKAGE or module_name.startswith(f"{DEMAND_PACKAGE}."):
            sys.modules.pop(module_name, None)


def test_demand_root_surface_stays_explicit_about_stable_exports() -> None:
    if _demand_package_spec() is None:
        assert DEMAND_PACKAGE not in sys.modules
        return

    module = importlib.import_module(DEMAND_PACKAGE)

    assert module.__all__ == EXPECTED_ROOT_EXPORTS
    assert sorted(name for name in dir(module) if name in EXPECTED_ROOT_EXPORTS) == sorted(
        EXPECTED_ROOT_EXPORTS
    )


def test_demand_root_import_defers_planned_submodule_loading() -> None:
    if _demand_package_spec() is None:
        for module_name in PLANNED_SUBMODULES:
            assert module_name not in sys.modules
        return

    _clear_demand_modules()

    importlib.import_module(DEMAND_PACKAGE)

    for module_name in PLANNED_SUBMODULES:
        assert module_name not in sys.modules


def test_demand_root_reserves_only_the_documented_public_surface() -> None:
    if _demand_package_spec() is None:
        assert DEMAND_PACKAGE not in sys.modules
        return

    module = importlib.import_module(DEMAND_PACKAGE)

    assert all("." not in export_name for export_name in module.__all__)
    assert all(not export_name.startswith("_") for export_name in module.__all__)
