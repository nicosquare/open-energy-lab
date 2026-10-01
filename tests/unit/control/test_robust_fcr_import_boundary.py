"""Import and source boundaries for Feature 013's pure contract modules."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import textwrap


FEATURE_MODULES = (
    Path("src/open_energy_lab/control/robust_fcr_bidding.py"),
    Path("src/open_energy_lab/control/_robust_fcr_formulation.py"),
    Path("src/open_energy_lab/control/_robust_fcr_solver.py"),
)
FORBIDDEN_DIRECT_IMPORTS = {
    "IPython",
    "baselines",
    "gurobipy",
    "highspy",
    "httpx",
    "julia",
    "juliacall",
    "legacy",
    "nbclient",
    "nbformat",
    "notebook",
    "pandas",
    "pyomo",
    "requests",
    "socket",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


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


def test_feature_013_modules_exist_and_have_no_direct_research_imports() -> None:
    violations: dict[str, list[str]] = {}
    for path in FEATURE_MODULES:
        assert path.is_file(), f"missing Feature 013 module: {path}"
        imported = _imported_modules(path)
        forbidden = sorted(
            name
            for name in imported
            if any(
                name == blocked or name.startswith(f"{blocked}.")
                for blocked in FORBIDDEN_DIRECT_IMPORTS
            )
        )
        if forbidden:
            violations[path.as_posix()] = forbidden

    assert violations == {}


def test_feature_013_pure_imports_load_no_solver_or_reference_stack() -> None:
    _run_isolated_python(
        """
        import os
        import sys

        credentials = {
            "GUROBI_HOME", "GRB_LICENSE_FILE", "WLSACCESSID",
            "WLSSECRET", "LICENSEID", "ENTSOE_API_TOKEN",
        }
        forbidden_roots = {
            "IPython", "baselines", "gurobipy", "highspy", "httpx",
            "julia", "juliacall", "legacy", "nbclient", "nbformat",
            "notebook", "pandas", "pyomo", "requests",
        }

        class GuardedEnvironment(dict):
            def __getitem__(self, key):
                if key in credentials:
                    raise AssertionError(f"credential read during import: {key}")
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key in credentials:
                    raise AssertionError(f"credential read during import: {key}")
                return super().get(key, default)

            def __contains__(self, key):
                if key in credentials:
                    raise AssertionError(f"credential inspected during import: {key}")
                return super().__contains__(key)

        os.environ = GuardedEnvironment(os.environ)
        loaded_before = set(sys.modules)

        import open_energy_lab.control.robust_fcr_bidding as contracts
        import open_energy_lab.control._robust_fcr_formulation as formulation
        import open_energy_lab.control._robust_fcr_solver as solver

        assert contracts.ROBUST_FCR_BIDDING_PROBLEM_VERSION.endswith(".v1")
        assert formulation.SOURCE_EQUATION_VERSION.endswith("-v1")
        assert solver.REQUIRED_PYOMO_VERSION == "6.10.1"
        assert solver.REQUIRED_HIGHSPY_VERSION == "1.15.1"

        newly_loaded = set(sys.modules) - loaded_before
        loaded_roots = {name.split(".", 1)[0] for name in newly_loaded}
        # urllib.parse (pure string parsing) is allowed; pathlib imports it on Python <= 3.12.
        assert not ({"urllib.request", "urllib.response"} & newly_loaded)
        assert forbidden_roots.isdisjoint(loaded_roots), sorted(
            forbidden_roots & loaded_roots
        )
        """
    )


def test_feature_013_solver_backend_loading_is_explicit_in_source() -> None:
    source = FEATURE_MODULES[2].read_text(encoding="utf-8")
    assert "from importlib import import_module" in source
    assert 'import_module("pyomo")' in source
    assert 'import_module("pyomo.environ")' in source
    assert 'import_module("highspy")' in source
    assert "import pyomo" not in source
    assert "import highspy" not in source
    assert "import gurobipy" not in source


def test_feature_013_contract_sources_do_not_probe_external_state() -> None:
    forbidden_tokens = (
        "os.environ",
        "os.getenv",
        "socket.socket",
        "subprocess.run",
        "subprocess.Popen",
        "urlopen(",
        "requests.get(",
        "regulation_signal.csv",
    )
    violations: dict[str, list[str]] = {}
    for path in FEATURE_MODULES:
        source = path.read_text(encoding="utf-8")
        found = [token for token in forbidden_tokens if token in source]
        if found:
            violations[path.as_posix()] = found
    assert violations == {}
