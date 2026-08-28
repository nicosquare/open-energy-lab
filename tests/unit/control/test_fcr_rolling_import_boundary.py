"""Lazy imports and forbidden boundaries for Feature 015 modules."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import textwrap


ROLLING_MODULES = (
    Path("src/open_energy_lab/control/fcr_rolling_backtest.py"),
    Path("src/open_energy_lab/control/robust_fcr_rolling.py"),
    Path("src/open_energy_lab/control/_fcr_rolling_orchestrator.py"),
    Path("src/open_energy_lab/market/activation.py"),
    Path("src/open_energy_lab/simulator/fcr_bid_evaluation.py"),
    Path("src/open_energy_lab/simulator/fcr_rolling_evaluation.py"),
)
FORBIDDEN_DIRECT_IMPORTS = {
    "baselines",
    "gurobipy",
    "highspy",
    "httpx",
    "julia",
    "juliacall",
    "legacy",
    "pandas",
    "pyomo",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def _run_isolated(source: str) -> None:
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


def test_feature_015_foundational_modules_exist_and_avoid_forbidden_imports() -> None:
    violations: dict[str, list[str]] = {}
    for path in ROLLING_MODULES:
        assert path.is_file(), f"missing Feature 015 foundational module: {path}"
        forbidden = sorted(
            name
            for name in _imports(path)
            if any(
                name == blocked or name.startswith(f"{blocked}.")
                for blocked in FORBIDDEN_DIRECT_IMPORTS
            )
        )
        if forbidden:
            violations[path.as_posix()] = forbidden
    assert violations == {}


def test_feature_015_foundational_imports_load_no_solver_or_research_stack() -> None:
    _run_isolated(
        """
        import sys

        before = set(sys.modules)
        import open_energy_lab.market.activation
        import open_energy_lab.control.fcr_rolling_backtest
        import open_energy_lab.control.robust_fcr_rolling
        import open_energy_lab.control._fcr_rolling_orchestrator
        import open_energy_lab.simulator.fcr_bid_evaluation
        import open_energy_lab.simulator.fcr_rolling_evaluation

        newly_loaded = set(sys.modules) - before
        forbidden_roots = {
            "baselines", "gurobipy", "highspy", "julia", "juliacall",
            "legacy", "pandas", "pyomo", "requests",
        }
        loaded_roots = {name.split(".", 1)[0] for name in newly_loaded}
        assert forbidden_roots.isdisjoint(loaded_roots), sorted(
            forbidden_roots & loaded_roots
        )
        """
    )


def test_result_resume_and_persistence_exports_remain_lazy() -> None:
    _run_isolated(
        """
        import sys

        before = set(sys.modules)
        from open_energy_lab.control import (
            RollingFCRResumeEvidence,
            aggregate_rolling_fcr_records,
            assess_rolling_fcr_resume,
            load_rolling_fcr_study_result,
        )

        assert RollingFCRResumeEvidence.__name__ == "RollingFCRResumeEvidence"
        assert callable(aggregate_rolling_fcr_records)
        assert callable(assess_rolling_fcr_resume)
        assert callable(load_rolling_fcr_study_result)
        newly_loaded = set(sys.modules) - before
        forbidden = {"pyomo", "highspy", "gurobipy", "pandas"}
        assert forbidden.isdisjoint({name.split(".", 1)[0] for name in newly_loaded})
        """
    )


def test_feature_015_foundational_sources_do_not_probe_external_state() -> None:
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
    violations = {}
    for path in ROLLING_MODULES:
        source = path.read_text(encoding="utf-8")
        found = [token for token in forbidden_tokens if token in source]
        if found:
            violations[path.as_posix()] = found
    assert violations == {}
