"""Import boundaries for required lazy backends and optional research stacks."""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import textwrap

import pytest


REQUIRED_LAZY_BACKEND_MODULES = {
    "highspy",
    "pyomo",
    "spflow",
    "torch",
}
OPTIONAL_RESEARCH_MODULES = {
    "citylearn",
    "docplex",
    "gurobipy",
    "jupyter",
    "torchrl",
    "wandb",
}
LAZY_RESEARCH_MODULES = REQUIRED_LAZY_BACKEND_MODULES | OPTIONAL_RESEARCH_MODULES
WEATHER_WORKFLOW_MODULES = {
    "pandas",
    "pvlib",
    "timezonefinder",
}
RESTORATION_OFFLINE_MODULES = (
    "open_energy_lab.market.restoration_artifact",
    "open_energy_lab.market.restoration_activation",
    "open_energy_lab.control.restoration_service",
    "open_energy_lab.simulator.restoration_service",
    "open_energy_lab.simulator.restoration_settlement",
)

VISUALIZATION_MODULES = (
    "open_energy_lab.visualization",
    "open_energy_lab.visualization.inspection",
    "open_energy_lab.visualization.comparison",
    "open_energy_lab.visualization._persistence",
    "open_energy_lab.visualization.plotting",
)


def _lazy_modules_loaded_after(before_import: set[str]) -> set[str]:
    return LAZY_RESEARCH_MODULES & (set(sys.modules) - before_import)


def _forbidden_modules_loaded_after(
    before_import: set[str],
    forbidden_modules: set[str],
) -> set[str]:
    return forbidden_modules & (set(sys.modules) - before_import)


def _assert_import_stays_clear_of_lazy_research_stacks(module_name: str) -> None:
    module_spec = importlib.util.find_spec(module_name)
    if module_spec is None:
        assert module_name not in sys.modules
        return

    loaded_before_import = set(sys.modules)

    importlib.import_module(module_name)

    assert _lazy_modules_loaded_after(loaded_before_import) == set()


def _assert_import_stays_clear_of_forbidden_modules(
    module_name: str,
    forbidden_modules: set[str],
) -> None:
    module_spec = importlib.util.find_spec(module_name)
    if module_spec is None:
        assert module_name not in sys.modules
        return

    loaded_before_import = set(sys.modules)

    importlib.import_module(module_name)

    assert _forbidden_modules_loaded_after(loaded_before_import, forbidden_modules) == set()


def _run_isolated_python(source: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, (
        f"isolated import check failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )


def test_package_roots_do_not_load_required_backends() -> None:
    """Required installation must not make ordinary package imports eager."""

    _run_isolated_python(
        """
        import sys

        import open_energy_lab
        import open_energy_lab.control
        import open_energy_lab.core
        import open_energy_lab.demand
        import open_energy_lab.market
        import open_energy_lab.planning
        import open_energy_lab.simulator
        import open_energy_lab.tpm
        import open_energy_lab.visualization
        import open_energy_lab.weather

        required = {"spflow", "torch", "pyomo", "highspy"}
        loaded = required & set(sys.modules)
        assert not loaded, f"package roots eagerly loaded required backends: {sorted(loaded)}"
        """
    )


def test_feature_011_offline_roots_and_symbols_load_no_adapters_credentials_or_research_stacks() -> None:
    _run_isolated_python(
        """
        import os
        import sys

        credential_keys = {
            "RTE_CLIENT_ID",
            "RTE_CLIENT_SECRET",
            "RTE_ACCESS_TOKEN",
            "ENTSOE_API_TOKEN",
        }
        forbidden_roots = {
            "IPython", "citylearn", "cupy", "docplex", "gurobipy",
            "highspy", "ipykernel", "jupyter", "mlflow", "nbclient",
            "nbformat", "notebook", "pyomo", "spflow", "submitit",
            "tensorboard", "torch", "torchrl", "wandb",
        }
        offline_modules = {
            "open_energy_lab.market.restoration_artifact",
            "open_energy_lab.market.restoration_activation",
            "open_energy_lab.control.restoration_service",
            "open_energy_lab.simulator.restoration_service",
            "open_energy_lab.simulator.restoration_settlement",
        }
        adapter_modules = {
            "open_energy_lab.market.rte",
            "open_energy_lab.market.entsoe",
            "open_energy_lab.market.entsoe_restoration",
        }

        class GuardedEnvironment(dict):
            def __getitem__(self, key):
                if key in credential_keys:
                    raise AssertionError(f"credential read during import: {key}")
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key in credential_keys:
                    raise AssertionError(f"credential read during import: {key}")
                return super().get(key, default)

            def __contains__(self, key):
                if key in credential_keys:
                    raise AssertionError(f"credential inspected during import: {key}")
                return super().__contains__(key)

        os.environ = GuardedEnvironment(os.environ)
        loaded_before = set(sys.modules)

        import open_energy_lab
        import open_energy_lab.control as control
        import open_energy_lab.market as market
        import open_energy_lab.simulator as simulator

        assert offline_modules.isdisjoint(sys.modules)
        assert adapter_modules.isdisjoint(sys.modules)

        assert market.RestorationMarketArtifact.__module__ == (
            "open_energy_lab.market.restoration_artifact"
        )
        assert market.AFRRActivationTrajectory.__module__ == (
            "open_energy_lab.market.restoration_activation"
        )
        assert control.AFRRBaselineConfig.__module__ == (
            "open_energy_lab.control.restoration_service"
        )
        assert simulator.AFRRReplayRequest.__module__ == (
            "open_energy_lab.simulator.restoration_service"
        )
        assert simulator.RestorationSettlement.__module__ == (
            "open_energy_lab.simulator.restoration_settlement"
        )

        assert offline_modules.issubset(sys.modules)
        assert adapter_modules.isdisjoint(sys.modules)
        newly_loaded = set(sys.modules) - loaded_before
        loaded_roots = {name.split(".", 1)[0] for name in newly_loaded}
        assert forbidden_roots.isdisjoint(loaded_roots), sorted(
            forbidden_roots & loaded_roots
        )
        assert not any(name == "legacy" or name.startswith("legacy.") for name in newly_loaded)
        """
    )


def test_feature_012_plan_and_evaluator_import_without_reference_or_solver_side_effects() -> None:
    _run_isolated_python(
        """
        import sys

        loaded_before = set(sys.modules)
        import open_energy_lab.control.fcr_bid_plan
        import open_energy_lab.simulator.fcr_bid_evaluation

        newly_loaded = set(sys.modules) - loaded_before
        forbidden_roots = {
            "IPython", "baselines", "citylearn", "docplex", "gurobipy",
            "highspy", "jupyter", "legacy", "pandas", "pyomo", "spflow",
            "torch", "torchrl", "wandb",
        }
        loaded_roots = {name.split(".", 1)[0] for name in newly_loaded}
        assert forbidden_roots.isdisjoint(loaded_roots)
        assert "open_energy_lab.market.reference_fcr" not in sys.modules
        assert not any("julia" in name.casefold() for name in newly_loaded)
        """
    )


def test_feature_012_focused_reference_loader_import_is_offline_and_lightweight() -> None:
    _run_isolated_python(
        """
        import sys

        loaded_before = set(sys.modules)
        import open_energy_lab.market.reference_fcr as reference_fcr

        newly_loaded = set(sys.modules) - loaded_before
        forbidden_roots = {
            "IPython", "baselines", "citylearn", "docplex", "gurobipy",
            "highspy", "httpx", "julia", "juliacall", "jupyter", "legacy",
            "nbclient", "nbformat", "notebook", "pandas", "pyomo", "requests",
            "spflow", "torch", "torchrl", "wandb",
        }
        loaded_roots = {name.split(".", 1)[0] for name in newly_loaded}
        assert forbidden_roots.isdisjoint(loaded_roots)
        assert reference_fcr.load_golden_reference_fixture.__module__ == (
            "open_energy_lab.market.reference_fcr"
        )
        assert not any("baselines" in name for name in newly_loaded)
        """
    )


def test_tpm_workflow_loads_spflow_and_torch_only_at_its_boundary() -> None:
    _run_isolated_python(
        """
        import importlib
        import sys

        import open_energy_lab.tpm
        from open_energy_lab.tpm.optional_spflow import require_spflow_backend

        assert "spflow" not in sys.modules
        assert "torch" not in sys.modules

        require_spflow_backend()
        importlib.import_module("spflow.learn")

        assert "spflow" in sys.modules
        assert "torch" in sys.modules
        """
    )


def test_planning_workflow_loads_pyomo_and_highspy_only_at_its_boundary() -> None:
    _run_isolated_python(
        """
        import sys

        import open_energy_lab.planning
        from open_energy_lab.planning.optional_solver import require_pyomo_backend

        assert "pyomo" not in sys.modules
        assert "highspy" not in sys.modules

        pyomo = require_pyomo_backend()
        solver = pyomo.SolverFactory("highs")
        assert solver.available(exception_flag=False)

        assert "pyomo" in sys.modules
        assert "highspy" in sys.modules
        """
    )


@pytest.mark.parametrize(
    "module_name",
    (
        "open_energy_lab",
        "open_energy_lab.simulator",
        "open_energy_lab.core",
        "open_energy_lab.control",
        "open_energy_lab.market",
        "open_energy_lab.weather",
        "open_energy_lab.demand",
        "open_energy_lab.tpm",
        "open_energy_lab.planning",
        "open_energy_lab.visualization",
    ),
)
def test_package_imports_stay_clear_of_lazy_research_stacks(module_name: str) -> None:
    _assert_import_stays_clear_of_lazy_research_stacks(module_name)


@pytest.mark.parametrize(
    "module_name",
    (
        "open_energy_lab.core",
        "open_energy_lab.core.controller",
        "open_energy_lab.simulator",
        "open_energy_lab.simulator.controller_runner",
        "open_energy_lab.simulator.weather",
        "open_energy_lab.simulator.pv",
        "open_energy_lab.simulator.stochastic_weather",
        "open_energy_lab.control._config",
        "open_energy_lab.control.price_threshold",
        "open_energy_lab.control.soc_guardrail",
        "open_energy_lab.control.pv_self_consumption",
        "open_energy_lab.weather",
        "open_energy_lab.demand",
        "open_energy_lab.simulator.stochastic_demand",
        "open_energy_lab.simulator.planning_export",
        "open_energy_lab.market.time",
        "open_energy_lab.market.artifact",
        "open_energy_lab.market.activation",
        "open_energy_lab.market.entsoe",
        "open_energy_lab.market.reference_fcr",
        *RESTORATION_OFFLINE_MODULES,
        "open_energy_lab.control.fcr_bid_plan",
        "open_energy_lab.control.robust_fcr_bidding",
        "open_energy_lab.control.robust_fcr_reference",
        "open_energy_lab.control._robust_fcr_formulation",
        "open_energy_lab.control._robust_fcr_solver",
        "open_energy_lab.control.stacked_service",
        "open_energy_lab.simulator.fcr_bid_evaluation",
        "open_energy_lab.simulator.stacked_service",
        "open_energy_lab.simulator.fcr_settlement",
        "open_energy_lab.tpm",
        "open_energy_lab.tpm.artifact",
        "open_energy_lab.tpm.data",
        "open_energy_lab.tpm.domains",
        "open_energy_lab.tpm.features",
        "open_energy_lab.tpm.fit",
        "open_energy_lab.tpm.mio",
        "open_energy_lab.tpm.query",
        "open_energy_lab.tpm.piecewise",
        "open_energy_lab.tpm.optional_spflow",
        "open_energy_lab.planning",
        "open_energy_lab.planning.dataset",
        "open_energy_lab.planning.problem",
        "open_energy_lab.planning.piecewise",
        "open_energy_lab.planning.optional_solver",
        "open_energy_lab.planning.workflow",
        *VISUALIZATION_MODULES,
    ),
)
def test_submodule_imports_stay_clear_of_lazy_research_stacks(
    module_name: str,
) -> None:
    _assert_import_stays_clear_of_lazy_research_stacks(module_name)


@pytest.mark.parametrize(
    "module_name",
    (
        "open_energy_lab.weather",
        "open_energy_lab.simulator.stochastic_weather",
        "open_energy_lab.demand",
        "open_energy_lab.simulator.stochastic_demand",
    ),
)
def test_weather_related_imports_do_not_load_isolated_fetch_dependencies(
    module_name: str,
) -> None:
    _assert_import_stays_clear_of_forbidden_modules(
        module_name,
        WEATHER_WORKFLOW_MODULES,
    )
