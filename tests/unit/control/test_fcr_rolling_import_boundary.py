"""Lazy imports and forbidden boundaries for Feature 015 modules."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROLLING_MODULES = (
    Path("src/open_energy_lab/control/fcr_rolling_backtest.py"),
    Path("src/open_energy_lab/control/fcr_rolling_reference.py"),
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
        import open_energy_lab.control.fcr_rolling_reference
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
            AGGREGATION_POLICY,
            FAILURE_POLICY_COUPLED,
            FAILURE_POLICY_INDEPENDENT,
            RESUME_POLICY,
            RollingFCRResumeEvidence,
            RollingFCRStateCarryEvidence,
            aggregate_rolling_fcr_records,
            assess_rolling_fcr_resume,
            derive_rolling_fcr_state_carry,
            extract_accepted_predecessor_fixings,
            load_rolling_fcr_study_result,
        )

        assert AGGREGATION_POLICY == "coverage-labelled-no-zero-fill-v1"
        assert FAILURE_POLICY_COUPLED.startswith("coupled-days-")
        assert FAILURE_POLICY_INDEPENDENT.startswith("independent-days-")
        assert RESUME_POLICY == "exact-semantic-evidence-v1"
        assert RollingFCRResumeEvidence.__name__ == "RollingFCRResumeEvidence"
        assert RollingFCRStateCarryEvidence.__name__ == "RollingFCRStateCarryEvidence"
        assert callable(aggregate_rolling_fcr_records)
        assert callable(assess_rolling_fcr_resume)
        assert callable(derive_rolling_fcr_state_carry)
        assert callable(extract_accepted_predecessor_fixings)
        assert callable(load_rolling_fcr_study_result)
        newly_loaded = set(sys.modules) - before
        forbidden = {"pyomo", "highspy", "gurobipy", "pandas"}
        assert forbidden.isdisjoint({name.split(".", 1)[0] for name in newly_loaded})
        """
    )


def test_normalized_reference_exports_remain_lazy_and_offline() -> None:
    _run_isolated(
        """
        import sys

        before = set(sys.modules)
        from open_energy_lab.control import (
            RollingFCRReferenceComparison,
            RollingFCRReferenceFieldResult,
            RollingFCRReferenceFixture,
            compare_rolling_fcr_reference,
            load_rolling_fcr_reference_fixture,
        )

        assert RollingFCRReferenceComparison.__name__ == "RollingFCRReferenceComparison"
        assert RollingFCRReferenceFieldResult.__name__ == "RollingFCRReferenceFieldResult"
        assert RollingFCRReferenceFixture.__name__ == "RollingFCRReferenceFixture"
        assert callable(compare_rolling_fcr_reference)
        assert callable(load_rolling_fcr_reference_fixture)
        newly_loaded = set(sys.modules) - before
        forbidden = {"pyomo", "highspy", "gurobipy", "pandas", "requests"}
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


def test_feature_015_sources_never_open_raw_reference_or_credential_locators() -> None:
    raw_locators = (
        "baselines/",
        "legacy/",
        "results/",
        "regulation_signal.csv",
    )
    credential_tokens = (
        "GRB_LICENSE_FILE",
        "gurobi.lic",
        ".netrc",
        "ENTSOE_API",
        "RTE_API",
    )
    violations: dict[str, list[str]] = {}
    for path in ROLLING_MODULES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=path.as_posix())
        found = [token for token in credential_tokens if token in source]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function_name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if function_name not in {
                "Path",
                "open",
                "read_bytes",
                "read_text",
                "glob",
                "rglob",
            }:
                continue
            literal_arguments = (
                item.value
                for item in node.args
                if isinstance(item, ast.Constant)
                and isinstance(item.value, str)
            )
            found.extend(
                value
                for value in literal_arguments
                if any(locator in value for locator in raw_locators)
            )
        if found:
            violations[path.as_posix()] = sorted(set(found))
    assert violations == {}


def test_public_rolling_contracts_remain_offline_when_external_access_is_poisoned() -> None:
    _run_isolated(
        """
        import builtins
        import os
        from pathlib import Path
        import socket
        import subprocess

        def forbidden(action):
            def fail(*args, **kwargs):
                raise AssertionError(f"rolling contract attempted {action}")
            return fail

        socket.socket = forbidden("network access")
        subprocess.run = forbidden("subprocess execution")
        subprocess.Popen = forbidden("subprocess execution")
        builtins.input = forbidden("credential input")
        os.getenv = forbidden("environment credential read")

        from open_energy_lab.control import (
            build_rolling_fcr_experiment_profile,
            load_rolling_fcr_reference_fixture,
        )

        profile = build_rolling_fcr_experiment_profile(
            "script-12-restriction-reset-midnight-v1"
        )
        fixture = load_rolling_fcr_reference_fixture(
            Path(
                "tests/fixtures/fcr_rolling_backtest/"
                "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json"
            )
        )
        assert profile.profile_id.startswith("script-12-")
        assert len(fixture.solve_records) == 20
        """
    )


def test_bid_selection_entry_points_have_no_activation_argument() -> None:
    import inspect

    from open_energy_lab.control import _fcr_rolling_orchestrator as orchestrator
    from open_energy_lab.control import robust_fcr_rolling

    for function in (
        orchestrator._solve_day,
        robust_fcr_rolling.solve_robust_fcr_rolling_bid,
    ):
        parameters = inspect.signature(function).parameters
        assert all("activation" not in name.casefold() for name in parameters)


def test_future_activation_cannot_be_attached_to_rolling_problem() -> None:
    from dataclasses import replace

    from open_energy_lab.control import RollingFCRValidationError
    from tests.fcr_rolling_case_utils import build_authored_rolling_problem

    problem = build_authored_rolling_problem(
        "script-14-restriction-rolling-0800-v1"
    )
    with pytest.raises((TypeError, RollingFCRValidationError)):
        replace(problem, activation_trace=object())
