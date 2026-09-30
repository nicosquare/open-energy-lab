"""Import-boundary tests for the simulator package."""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import textwrap
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


def test_controller_runner_import_and_export_stay_lightweight() -> None:
    loaded_before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.simulator.controller_runner")

    loaded_by_import = set(sys.modules) - loaded_before_import
    optional_modules_loaded = OPTIONAL_RESEARCH_MODULES & loaded_by_import

    assert optional_modules_loaded == set()
    assert module.__all__ == ["evaluate_with_controller"]
    assert module.evaluate_with_controller.__module__ == module.__name__


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
    assert graph.Relation.DERIVES.value == "derives"
    assert graph.Relation.FEEDS.value == "feeds"


def test_future_multi_component_modules_reserve_import_light_boundary() -> None:
    package = importlib.import_module("open_energy_lab.simulator")
    package_dir = Path(package.__file__).resolve().parent

    for module_name in (
        "open_energy_lab.simulator.load",
        "open_energy_lab.simulator.weather",
        "open_energy_lab.simulator.pv",
    ):
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


def test_simulator_modules_never_load_control() -> None:
    """The simulator owns the plan/schedule contracts; control depends on it, not back."""

    _run_isolated_python(
        """
        import pkgutil
        import sys

        import open_energy_lab.simulator as simulator

        for info in pkgutil.iter_modules(simulator.__path__):
            __import__(f"open_energy_lab.simulator.{info.name}")

        loaded = sorted(name for name in sys.modules if name.startswith("open_energy_lab.control"))
        assert loaded == [], loaded
        """
    )
