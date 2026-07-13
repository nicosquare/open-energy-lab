"""Unit contracts for the optional planning-solver boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from open_energy_lab.planning.optional_solver import (
    PlanningSolveConfig,
    PlanningSolverDependencyUnavailableError,
    require_pyomo_backend,
    solve_planning_problem,
)
from open_energy_lab.planning.problem import (
    PlanningDecisionCandidate,
    PlanningProblemAssembly,
)


def _assembled_problem() -> PlanningProblemAssembly:
    return PlanningProblemAssembly(
        problem_id="planning-problem-unit",
        artifact_id="tpm-artifact:planning-dataset-export-integration",
        dataset_reference="planning-dataset-export-integration",
        decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
        target_name="shortfall",
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.1,
        objective_direction="minimize",
        cost_terms={
            "battery_capacity_kwh": 1200.0,
            "solar_capacity_kw": 950.0,
        },
        candidate_designs=(
            PlanningDecisionCandidate(
                selected_design={
                    "battery_capacity_kwh": 8.0,
                    "solar_capacity_kw": 4.0,
                },
                objective_value=13400.0,
                estimated_shortfall_risk=0.0,
                matched_row_count=1,
            ),
        ),
        piecewise_terms=SimpleNamespace(
            approximation_kind="piecewise",
            fit_numeric_tolerance=1e-9,
            query_numeric_tolerance=1e-9,
        ),
        solver_metadata={
            "canonical_backend": "pyomo",
            "solver_execution_optional": True,
        },
    )


def test_require_pyomo_backend_raises_documented_lazy_dependency_error(monkeypatch) -> None:
    def _raise_import_error(module_name: str):
        raise ImportError(module_name)

    monkeypatch.setattr(
        "open_energy_lab.planning.optional_solver.import_module",
        _raise_import_error,
    )

    with pytest.raises(PlanningSolverDependencyUnavailableError, match="optional 'pyomo'"):
        require_pyomo_backend()


def test_solve_planning_problem_returns_deterministic_skip_when_backend_is_unavailable(
    monkeypatch,
) -> None:
    def _raise_dependency_error():
        raise PlanningSolverDependencyUnavailableError("pyomo missing")

    monkeypatch.setattr(
        "open_energy_lab.planning.optional_solver.require_pyomo_backend",
        _raise_dependency_error,
    )

    summary = solve_planning_problem(
        _assembled_problem(),
        solve_config=PlanningSolveConfig(skip_if_unavailable=True),
    )

    assert summary.status == "skipped"
    assert summary.selected_design == {}
    assert summary.objective_value is None
    assert summary.estimated_shortfall_risk is None
    assert "optional pyomo backend unavailable" in summary.feasibility_diagnostics["reason"]
    assert summary.solver_metadata["requested_solver_name"] == "pyomo"


def test_solve_planning_problem_uses_injected_backend_without_importing_pyomo() -> None:
    summary = solve_planning_problem(
        _assembled_problem(),
        solve_config=PlanningSolveConfig(solver_name="fake-pyomo"),
        pyomo_backend=SimpleNamespace(__name__="pyomo.testing", __version__="0.test"),
    )

    assert summary.status == "optimal"
    assert summary.selected_design == {
        "battery_capacity_kwh": 8.0,
        "solar_capacity_kw": 4.0,
    }
    assert summary.objective_value == pytest.approx(13400.0)
    assert summary.estimated_shortfall_risk == pytest.approx(0.0)
    assert summary.solver_metadata["backend_module"] == "pyomo.testing"
