"""Corrective unit contracts for the required default HiGHS solver stack."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import open_energy_lab.planning.optional_solver as optional_solver_module
from open_energy_lab.planning.optional_solver import (
    PlanningSolveConfig,
    PlanningSolverDependencyUnavailableError,
    require_pyomo_backend,
)
from open_energy_lab.planning.problem import PlanningProblemDefinition


REQUIRED_PYOMO_VERSION = "6.10.1"
REQUIRED_HIGHSPY_VERSION = "1.15.1"


def _problem_definition() -> PlanningProblemDefinition:
    return PlanningProblemDefinition(
        problem_id="required-highs-default-unit",
        tpm_artifact_reference="tests/fixtures/tpm/tpm_artifact_spflow_v1.json",
        decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
        decision_feature_types={
            "battery_capacity_kwh": "continuous",
            "solar_capacity_kw": "continuous",
        },
        shortfall_threshold=0.08,
        chance_limit_epsilon=0.1,
        cost_terms={
            "battery_capacity_kwh": 1200.0,
            "solar_capacity_kw": 950.0,
        },
    )


def _pyomo(version: str = REQUIRED_PYOMO_VERSION) -> SimpleNamespace:
    return SimpleNamespace(__name__="pyomo.environ", __version__=version)


def _highspy(version: str = REQUIRED_HIGHSPY_VERSION) -> SimpleNamespace:
    return SimpleNamespace(
        __name__="highspy",
        __version__=version,
        Highs=lambda: SimpleNamespace(version=lambda: version),
    )


def test_omitted_solver_configuration_selects_required_highs() -> None:
    problem = _problem_definition()

    assert problem.solver_configuration["backend_name"] == "pyomo"
    assert problem.solver_configuration["solver_name"] == "highs"
    assert problem.solver_configuration["solver_backend_required"] is True
    assert problem.solver_configuration["solver_execution_optional"] is False
    assert PlanningSolveConfig().solver_name == "highs"


def test_missing_pyomo_is_a_required_install_failure(monkeypatch) -> None:
    def _missing_pyomo(module_name: str):
        assert module_name in {"pyomo", "pyomo.environ"}
        raise ImportError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _missing_pyomo)

    with pytest.raises(PlanningSolverDependencyUnavailableError) as exc_info:
        require_pyomo_backend()

    diagnostic = str(exc_info.value).lower()
    assert "required" in diagnostic
    assert "pyomo" in diagnostic
    assert REQUIRED_PYOMO_VERSION in diagnostic


def test_incompatible_pyomo_is_a_required_install_failure(monkeypatch) -> None:
    incompatible = _pyomo("6.9.5")

    def _import_backend(module_name: str):
        if module_name in {"pyomo", "pyomo.environ"}:
            return incompatible
        if module_name == "highspy":
            return _highspy()
        raise ImportError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _import_backend)

    with pytest.raises(PlanningSolverDependencyUnavailableError) as exc_info:
        require_pyomo_backend()

    diagnostic = str(exc_info.value).lower()
    assert "incompatible" in diagnostic
    assert "pyomo" in diagnostic
    assert REQUIRED_PYOMO_VERSION in diagnostic
    assert "6.9.5" in diagnostic


def test_missing_highspy_is_a_required_install_failure(monkeypatch) -> None:
    def _missing_highspy(module_name: str):
        if module_name in {"pyomo", "pyomo.environ"}:
            return _pyomo()
        assert module_name == "highspy"
        raise ImportError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _missing_highspy)

    with pytest.raises(PlanningSolverDependencyUnavailableError) as exc_info:
        require_pyomo_backend()

    diagnostic = str(exc_info.value).lower()
    assert "required" in diagnostic
    assert "highspy" in diagnostic
    assert REQUIRED_HIGHSPY_VERSION in diagnostic


def test_incompatible_highspy_is_a_required_install_failure(monkeypatch) -> None:
    def _import_backend(module_name: str):
        if module_name in {"pyomo", "pyomo.environ"}:
            return _pyomo()
        if module_name == "highspy":
            return _highspy("1.14.0")
        raise ImportError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _import_backend)

    with pytest.raises(PlanningSolverDependencyUnavailableError) as exc_info:
        require_pyomo_backend()

    diagnostic = str(exc_info.value).lower()
    assert "incompatible" in diagnostic
    assert "highspy" in diagnostic
    assert REQUIRED_HIGHSPY_VERSION in diagnostic
    assert "1.14.0" in diagnostic
