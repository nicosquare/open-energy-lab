"""Import-boundary tests for the native control package."""

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap
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
    "AFRRBaselineConfig",
    "AFRRBaselineMode",
    "ArbitrageOnlyBaselineConfig",
    "BaselineScheduleBundle",
    "BidPlanProducer",
    "DirectionalCapacityCommitmentInterval",
    "DirectionalCapacitySchedule",
    "FCRBidPlanValidationError",
    "FixedFCRBidPlan",
    "MFRRBaselineConfig",
    "MFRRBaselineMode",
    "OptimizationMetric",
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PlanDiagnostic",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "RegulationOnlyBaselineConfig",
    "RestorationBaselineBundle",
    "RestorationCapability",
    "RestorationControlValidationError",
    "RestorationEnergyBaselineInterval",
    "RestorationEnergyBaselineSchedule",
    "SerializedScheduleReference",
    "SocGuardrailConfig",
    "SocGuardrailController",
    "StackedBaselineValidationError",
    "StackedHeuristicConfig",
    "build_afrr_baseline",
    "build_afrr_baseline_config",
    "build_afrr_directional_capacity_schedule",
    "build_arbitrage_only_baseline",
    "build_fixed_fcr_bid_plan",
    "build_mfrr_baseline",
    "build_mfrr_baseline_config",
    "build_mfrr_directional_capacity_schedule",
    "build_regulation_only_baseline",
    "build_restoration_capability",
    "build_stacked_heuristic_baseline",
]


def _optional_modules_loaded_after(before_import: set[str]) -> set[str]:
    return OPTIONAL_RESEARCH_MODULES & (set(sys.modules) - before_import)


def _run_isolated_python(source: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, (
        f"isolated import check failed\nstdout:\n{completed.stdout}"
        f"\nstderr:\n{completed.stderr}"
    )


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
    _run_isolated_python(
        """
        import sys

        import open_energy_lab.control as module

        assert "open_energy_lab.control._config" not in sys.modules
        assert "open_energy_lab.control.price_threshold" not in sys.modules
        assert "open_energy_lab.control.soc_guardrail" not in sys.modules
        assert "open_energy_lab.control.pv_self_consumption" not in sys.modules
        assert "open_energy_lab.control.stacked_service" not in sys.modules
        assert "open_energy_lab.control.restoration_service" not in sys.modules

        getattr(module, "PriceThresholdConfig")
        getattr(module, "PriceThresholdController")

        assert "open_energy_lab.control._config" in sys.modules
        assert "open_energy_lab.control.price_threshold" in sys.modules
        assert "open_energy_lab.control.soc_guardrail" not in sys.modules
        assert "open_energy_lab.control.pv_self_consumption" not in sys.modules
        assert "open_energy_lab.control.stacked_service" not in sys.modules
        assert "open_energy_lab.control.restoration_service" not in sys.modules

        getattr(module, "AFRRBaselineConfig")
        assert "open_energy_lab.control.restoration_service" in sys.modules
        """
    )


@pytest.mark.parametrize(
    ("export_name", "module_name"),
    (
        ("PVSelfConsumptionConfig", "open_energy_lab.control._config"),
        ("PVSelfConsumptionController", "open_energy_lab.control.pv_self_consumption"),
        ("PriceThresholdConfig", "open_energy_lab.control._config"),
        ("PriceThresholdController", "open_energy_lab.control.price_threshold"),
        ("SocGuardrailConfig", "open_energy_lab.control._config"),
        ("SocGuardrailController", "open_energy_lab.control.soc_guardrail"),
        ("ArbitrageOnlyBaselineConfig", "open_energy_lab.control.stacked_service"),
        ("BaselineScheduleBundle", "open_energy_lab.control.stacked_service"),
        ("RegulationOnlyBaselineConfig", "open_energy_lab.control.stacked_service"),
        ("StackedBaselineValidationError", "open_energy_lab.control.stacked_service"),
        ("StackedHeuristicConfig", "open_energy_lab.control.stacked_service"),
        ("build_arbitrage_only_baseline", "open_energy_lab.control.stacked_service"),
        ("build_regulation_only_baseline", "open_energy_lab.control.stacked_service"),
        ("build_stacked_heuristic_baseline", "open_energy_lab.control.stacked_service"),
        (
            "RestorationControlValidationError",
            "open_energy_lab.control.restoration_service",
        ),
        (
            "DirectionalCapacityCommitmentInterval",
            "open_energy_lab.control.restoration_service",
        ),
        ("DirectionalCapacitySchedule", "open_energy_lab.control.restoration_service"),
        (
            "RestorationEnergyBaselineInterval",
            "open_energy_lab.control.restoration_service",
        ),
        (
            "RestorationEnergyBaselineSchedule",
            "open_energy_lab.control.restoration_service",
        ),
        ("RestorationCapability", "open_energy_lab.control.restoration_service"),
        ("AFRRBaselineMode", "open_energy_lab.control.restoration_service"),
        ("AFRRBaselineConfig", "open_energy_lab.control.restoration_service"),
        (
            "RestorationBaselineBundle",
            "open_energy_lab.control.restoration_service",
        ),
        (
            "build_restoration_capability",
            "open_energy_lab.control.restoration_service",
        ),
        (
            "build_afrr_directional_capacity_schedule",
            "open_energy_lab.control.restoration_service",
        ),
        (
            "build_afrr_baseline_config",
            "open_energy_lab.control.restoration_service",
        ),
        ("build_afrr_baseline", "open_energy_lab.control.restoration_service"),
    ),
)
def test_control_root_exports_resolve_from_expected_modules(
    export_name: str,
    module_name: str,
) -> None:
    module = importlib.import_module("open_energy_lab.control")
    export = getattr(module, export_name)

    assert export.__module__ == module_name


def test_feature_012_plan_exports_are_lazy_and_owned_by_fcr_bid_plan() -> None:
    module = importlib.import_module("open_energy_lab.control")
    expected = {
        "BidPlanProducer",
        "FCRBidPlanValidationError",
        "FixedFCRBidPlan",
        "OptimizationMetric",
        "PlanDiagnostic",
        "SerializedScheduleReference",
        "build_fixed_fcr_bid_plan",
    }

    assert expected.issubset(module.__all__)
    assert {
        getattr(module, name).__module__
        for name in expected
    } == {"open_energy_lab.control.fcr_bid_plan"}


def test_feature_012_plan_import_loads_no_reference_or_research_runtime() -> None:
    _run_isolated_python(
        """
        import sys

        import open_energy_lab.control.fcr_bid_plan

        forbidden_roots = {
            "IPython", "baselines", "citylearn", "docplex", "gurobipy",
            "highspy", "jupyter", "legacy", "pandas", "pyomo", "spflow",
            "torch", "torchrl", "wandb",
        }
        loaded_roots = {name.split(".", 1)[0] for name in sys.modules}
        assert forbidden_roots.isdisjoint(loaded_roots)
        assert "open_energy_lab.market.reference_fcr" not in sys.modules
        """
    )


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
        (
            "open_energy_lab.control.stacked_service",
            (
                "ArbitrageOnlyBaselineConfig",
                "BaselineScheduleBundle",
                "RegulationOnlyBaselineConfig",
                "StackedBaselineValidationError",
                "StackedHeuristicConfig",
                "build_arbitrage_only_baseline",
                "build_regulation_only_baseline",
                "build_stacked_heuristic_baseline",
            ),
        ),
        (
            "open_energy_lab.control.restoration_service",
            (
                "RestorationControlValidationError",
                "DirectionalCapacityCommitmentInterval",
                "DirectionalCapacitySchedule",
                "RestorationEnergyBaselineInterval",
                "RestorationEnergyBaselineSchedule",
                "RestorationCapability",
                "AFRRBaselineMode",
                "AFRRBaselineConfig",
                "RestorationBaselineBundle",
                "build_restoration_capability",
                "build_afrr_directional_capacity_schedule",
                "build_afrr_baseline_config",
                "build_afrr_baseline",
            ),
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
