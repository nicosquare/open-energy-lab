"""Required-backend compatibility and optional-exact isolation for Feature 013."""

from __future__ import annotations

from importlib import import_module as real_import_module
from types import SimpleNamespace

import pytest

from open_energy_lab.control._robust_fcr_solver import (
    REQUIRED_HIGHSPY_VERSION,
    REQUIRED_PYOMO_VERSION,
    load_optional_gurobi_backend,
    require_highs_backend,
)
from open_energy_lab.control.robust_fcr_bidding import RobustFCRSolverDependencyUnavailableError


def test_locked_pyomo_and_highs_versions_are_available_through_explicit_boundary() -> None:
    backend = require_highs_backend()

    assert backend.pyomo_version == REQUIRED_PYOMO_VERSION == "6.10.1"
    assert backend.highspy_version == REQUIRED_HIGHSPY_VERSION == "1.15.1"
    assert backend.pyomo_environ.SolverFactory("highs").available(
        exception_flag=False
    )


@pytest.mark.parametrize("missing", ("pyomo", "highspy"))
def test_missing_required_packages_have_actionable_sync_guidance(
    missing: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_import(name: str):
        if name == missing:
            raise ModuleNotFoundError(name)
        return real_import_module(name)

    monkeypatch.setattr(
        "open_energy_lab.control._robust_fcr_solver.import_module",
        fake_import,
    )
    with pytest.raises(
        RobustFCRSolverDependencyUnavailableError,
        match=r"Feature 013 requires.*uv sync --dev",
    ):
        require_highs_backend()


@pytest.mark.parametrize(
    ("package", "installed", "expected"),
    (
        ("pyomo", "6.9.9", r"Pyomo 6\.10\.1.*6\.9\.9"),
        ("highspy", "1.14.0", r"highspy 1\.15\.1.*1\.14\.0"),
    ),
)
def test_incompatible_required_versions_are_rejected_before_solve(
    package: str,
    installed: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_import(name: str):
        if name == package == "pyomo":
            return SimpleNamespace(__version__=installed)
        if name == package == "highspy":
            return SimpleNamespace(__version__=installed)
        return real_import_module(name)

    monkeypatch.setattr(
        "open_energy_lab.control._robust_fcr_solver.import_module",
        fake_import,
    )
    with pytest.raises(
        RobustFCRSolverDependencyUnavailableError,
        match=expected,
    ):
        require_highs_backend()


def test_required_highs_boundary_never_probes_optional_gurobi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imports: list[str] = []

    def recorded_import(name: str):
        imports.append(name)
        if name == "gurobipy":
            raise AssertionError("required HiGHS boundary probed optional Gurobi")
        return real_import_module(name)

    monkeypatch.setattr(
        "open_energy_lab.control._robust_fcr_solver.import_module",
        recorded_import,
    )
    backend = require_highs_backend()

    assert backend.highspy_version == REQUIRED_HIGHSPY_VERSION
    assert "gurobipy" not in imports


def test_optional_gurobi_absence_is_structured_and_does_not_weaken_highs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_import(name: str):
        if name == "gurobipy":
            raise ModuleNotFoundError("gurobipy deliberately unavailable")
        return real_import_module(name)

    monkeypatch.setattr(
        "open_energy_lab.control._robust_fcr_solver.import_module",
        fake_import,
    )
    optional, reason = load_optional_gurobi_backend()

    assert optional is None
    assert reason is not None
    assert "optional Gurobi evidence is unavailable" in reason
    assert "uv sync --extra gurobi" in reason
    assert "restriction and relaxation remain available in HiGHS" in reason
    assert require_highs_backend().highspy_version == REQUIRED_HIGHSPY_VERSION
