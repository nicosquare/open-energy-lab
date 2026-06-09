"""Import-boundary tests for the native control package."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


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

EXPECTED_ROOT_EXPORTS = [
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "SocGuardrailConfig",
    "SocGuardrailController",
]


def _optional_modules_loaded_after(before_import: set[str]) -> set[str]:
    return OPTIONAL_RESEARCH_MODULES & (set(sys.modules) - before_import)


def test_control_package_import_stays_lightweight() -> None:
    loaded_before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.control")

    optional_modules_loaded = _optional_modules_loaded_after(loaded_before_import)

    assert optional_modules_loaded == set()
    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "control"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == EXPECTED_ROOT_EXPORTS
    assert sorted(name for name in dir(module) if name in EXPECTED_ROOT_EXPORTS) == EXPECTED_ROOT_EXPORTS


def test_control_root_import_defers_controller_submodule_loading() -> None:
    for module_name in (
        "open_energy_lab.control",
        "open_energy_lab.control._config",
        "open_energy_lab.control.price_threshold",
        "open_energy_lab.control.soc_guardrail",
        "open_energy_lab.control.pv_self_consumption",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("open_energy_lab.control")

    assert "open_energy_lab.control._config" not in sys.modules
    assert "open_energy_lab.control.price_threshold" not in sys.modules
    assert "open_energy_lab.control.soc_guardrail" not in sys.modules
    assert "open_energy_lab.control.pv_self_consumption" not in sys.modules

    getattr(module, "PriceThresholdConfig")
    getattr(module, "PriceThresholdController")

    assert "open_energy_lab.control._config" in sys.modules
    assert "open_energy_lab.control.price_threshold" in sys.modules
    assert "open_energy_lab.control.soc_guardrail" not in sys.modules
    assert "open_energy_lab.control.pv_self_consumption" not in sys.modules


@pytest.mark.parametrize(
    ("export_name", "module_name"),
    (
        ("PVSelfConsumptionConfig", "open_energy_lab.control._config"),
        ("PVSelfConsumptionController", "open_energy_lab.control.pv_self_consumption"),
        ("PriceThresholdConfig", "open_energy_lab.control._config"),
        ("PriceThresholdController", "open_energy_lab.control.price_threshold"),
        ("SocGuardrailConfig", "open_energy_lab.control._config"),
        ("SocGuardrailController", "open_energy_lab.control.soc_guardrail"),
    ),
)
def test_control_root_exports_resolve_from_expected_modules(
    export_name: str,
    module_name: str,
) -> None:
    module = importlib.import_module("open_energy_lab.control")
    export = getattr(module, export_name)

    assert export.__module__ == module_name


@pytest.mark.parametrize(
    ("module_name", "expected_exports"),
    (
        (
            "open_energy_lab.control._config",
            (
                "PVSelfConsumptionConfig",
                "PriceThresholdConfig",
                "SocGuardrailConfig",
            ),
        ),
        (
            "open_energy_lab.control.price_threshold",
            ("PriceThresholdController",),
        ),
        (
            "open_energy_lab.control.soc_guardrail",
            ("SocGuardrailController",),
        ),
        (
            "open_energy_lab.control.pv_self_consumption",
            ("PVSelfConsumptionController",),
        ),
    ),
)
def test_control_submodule_imports_stay_lightweight(
    module_name: str,
    expected_exports: tuple[str, ...],
) -> None:
    loaded_before_import = set(sys.modules)

    module = importlib.import_module(module_name)

    optional_modules_loaded = _optional_modules_loaded_after(loaded_before_import)

    assert optional_modules_loaded == set()
    for export_name in expected_exports:
        export = getattr(module, export_name)
        assert export.__module__ == module_name
