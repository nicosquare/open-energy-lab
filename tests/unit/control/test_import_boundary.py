"""Import-boundary tests for the native control package."""

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap

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

# Keep this exact public-surface snapshot synchronized with the repository-wide
# EXPECTED_CONTROL_EXPORTS contract in tests/unit/test_import_contract.py.


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


def test_feature_012_plan_import_loads_no_reference_or_research_runtime() -> None:
    _run_isolated_python(
        """
        import sys

        import open_energy_lab.simulator.fcr_bid_plan

        forbidden_roots = {
            "IPython", "baselines", "citylearn", "docplex", "gurobipy",
            "highspy", "jupyter", "legacy", "pandas", "pyomo", "spflow",
            "torch", "torchrl", "wandb",
        }
        loaded_roots = {name.split(".", 1)[0] for name in sys.modules}
        assert forbidden_roots.isdisjoint(loaded_roots)
        assert "oel_validation.reference_fcr" not in sys.modules
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
                "AFRRBaselineMode",
                "AFRRBaselineConfig",
                "RestorationBaselineBundle",
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
