"""Import-boundary tests for the source-independent market package."""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


MARKET_PACKAGE = "open_energy_lab.market"
PLANNED_MARKET_SUBMODULES = (
    "open_energy_lab.market.time",
    "open_energy_lab.market.artifact",
    "open_energy_lab.market.activation",
    "open_energy_lab.market.entsoe",
)
SOURCE_INDEPENDENT_SUBMODULES = (
    "open_energy_lab.market.time",
    "open_energy_lab.market.artifact",
    "open_energy_lab.market.activation",
)
RELOADED_MARKET_MODULES = (
    "open_energy_lab.market.rte",
    "open_energy_lab.market.entsoe",
    "open_energy_lab.market.restoration_artifact",
    "open_energy_lab.market.restoration_activation",
    "open_energy_lab.market.activation",
    "open_energy_lab.market.artifact",
    "open_energy_lab.market.time",
    MARKET_PACKAGE,
)

FORBIDDEN_IMPORT_ROOTS = {
    # Network and source transports.
    "aiohttp",
    "http",
    "httpx",
    "requests",
    "socket",
    "ssl",
    "urllib",
    "xml",
    # Notebook and interactive stacks.
    "IPython",
    "ipykernel",
    "jupyter",
    "nbformat",
    "notebook",
    # Solvers and heavyweight research stacks.
    "citylearn",
    "docplex",
    "gurobipy",
    "highspy",
    "pandas",
    "pvlib",
    "pyomo",
    "spflow",
    "torch",
    "torchrl",
    "wandb",
    # Credential helpers and reference repositories.
    "boto3",
    "keyring",
    "legacy",
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
        "isolated market import check failed\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )


@pytest.fixture(autouse=True)
def _restore_market_module_identity_after_in_process_reload():
    """Keep fresh-import assertions from invalidating collected class objects."""

    before = {
        name: sys.modules[name]
        for name in RELOADED_MARKET_MODULES
        if name in sys.modules
    }
    root = sys.modules.get("open_energy_lab")
    root_market = getattr(root, "market", None) if root is not None else None
    yield
    for name in RELOADED_MARKET_MODULES:
        sys.modules.pop(name, None)
    sys.modules.update(before)
    if root is not None:
        if root_market is None:
            root.__dict__.pop("market", None)
        else:
            root.market = root_market


def test_market_package_root_is_a_regular_source_tree_package() -> None:
    module_spec = importlib.util.find_spec(MARKET_PACKAGE)
    assert module_spec is not None

    module = importlib.import_module(MARKET_PACKAGE)

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == MARKET_PACKAGE
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "market"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module_file.parent.parent.parent.name == "src"
    assert "legacy" not in module_file.parts


def test_market_root_exports_no_transport_or_credential_capability() -> None:
    module = importlib.import_module(MARKET_PACKAGE)
    forbidden_name_fragments = (
        "api_token",
        "credential",
        "entsoe_client",
        "transport",
        "fetch_on_missing",
    )

    exported_names = tuple(getattr(module, "__all__", ()))

    assert all(isinstance(name, str) and name for name in exported_names)
    assert not any(
        fragment in name.casefold()
        for name in exported_names
        for fragment in forbidden_name_fragments
    )
    assert "ENTSOE_API_TOKEN" not in module.__dict__


def test_market_root_import_loads_no_network_notebook_solver_or_legacy_stack() -> None:
    forbidden = sorted(FORBIDDEN_IMPORT_ROOTS)
    _run_isolated_python(
        f"""
        import importlib
        import os
        import sys

        forbidden = set({forbidden!r})
        credential_key = "ENTSOE_API_TOKEN"

        class GuardedEnvironment(dict):
            def __getitem__(self, key):
                if key == credential_key:
                    raise AssertionError("market root read ENTSOE_API_TOKEN")
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key == credential_key:
                    raise AssertionError("market root read ENTSOE_API_TOKEN")
                return super().get(key, default)

            def __contains__(self, key):
                if key == credential_key:
                    raise AssertionError("market root inspected ENTSOE_API_TOKEN")
                return super().__contains__(key)

        os.environ = GuardedEnvironment(os.environ)
        loaded_before = set(sys.modules)
        module = importlib.import_module("open_energy_lab.market")
        newly_loaded = set(sys.modules) - loaded_before
        loaded_roots = {{name.split(".", 1)[0] for name in newly_loaded}}

        unexpected = forbidden & loaded_roots
        assert not unexpected, (
            "market root eagerly loaded forbidden stacks: "
            + ", ".join(sorted(unexpected))
        )
        assert module.__name__ == "open_energy_lab.market"
        """
    )


def test_source_independent_market_modules_remain_import_light_when_present() -> None:
    forbidden = sorted(FORBIDDEN_IMPORT_ROOTS)
    submodules = list(SOURCE_INDEPENDENT_SUBMODULES)
    _run_isolated_python(
        f"""
        import importlib
        import importlib.util
        import os
        import sys

        forbidden = set({forbidden!r})
        submodules = {submodules!r}
        credential_key = "ENTSOE_API_TOKEN"

        class GuardedEnvironment(dict):
            def __getitem__(self, key):
                if key == credential_key:
                    raise AssertionError(f"{{key}} was read during canonical import")
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key == credential_key:
                    raise AssertionError(f"{{key}} was read during canonical import")
                return super().get(key, default)

            def __contains__(self, key):
                if key == credential_key:
                    raise AssertionError(f"{{key}} was inspected during canonical import")
                return super().__contains__(key)

        os.environ = GuardedEnvironment(os.environ)
        for module_name in submodules:
            if importlib.util.find_spec(module_name) is None:
                assert module_name not in sys.modules
                continue
            loaded_before = set(sys.modules)
            importlib.import_module(module_name)
            newly_loaded = set(sys.modules) - loaded_before
            loaded_roots = {{name.split(".", 1)[0] for name in newly_loaded}}
            unexpected = forbidden & loaded_roots
            assert not unexpected, (
                f"{{module_name}} eagerly loaded forbidden stacks: "
                + ", ".join(sorted(unexpected))
            )
        """
    )


def test_planned_market_submodules_cannot_resolve_outside_package_boundary() -> None:
    package = importlib.import_module(MARKET_PACKAGE)
    assert package.__file__ is not None
    package_dir = Path(package.__file__).resolve().parent

    for module_name in PLANNED_MARKET_SUBMODULES:
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None:
            assert module_name not in sys.modules
            continue

        assert module_spec.origin is not None
        origin = Path(module_spec.origin).resolve()
        assert origin.parent == package_dir
        assert "legacy" not in origin.parts


def test_feature_012_offline_types_do_not_import_the_external_reference_loader() -> None:
    _run_isolated_python(
        """
        import sys

        import open_energy_lab.simulator.fcr_bid_plan
        import open_energy_lab.simulator.fcr_bid_evaluation

        assert "oel_validation.reference_fcr" not in sys.modules
        assert not any(
            name == "baselines" or name.startswith("baselines.")
            or name == "legacy" or name.startswith("legacy.")
            for name in sys.modules
        )
        """
    )
