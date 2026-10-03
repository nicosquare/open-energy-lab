"""Offline integration contracts for required planning solve workflows."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import open_energy_lab.planning.optional_solver as optional_solver_module
from open_energy_lab.planning.optional_solver import (
    PlanningSolveConfig,
    PlanningSolverDependencyUnavailableError,
    PlanningSolverUnavailableError,
    solve_planning_problem,
)
from open_energy_lab.planning.problem import (
    PlanningProblemDefinition,
    assemble_planning_problem,
)
from tpm import load_tpm_artifact
from tests.integration.planning.fixture_utils import (
    PLANNING_PROBLEM_FIXTURE_PATH,
    TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
)


class _FakePyomoBackend(SimpleNamespace):
    def build_spn_model(self, **kwargs):
        return SimpleNamespace(model_name=f"{kwargs['problem_id']}-handoff", **kwargs)

    def solve_candidate_model(self, handoff, solve_config):
        if getattr(self, "solver_unavailable", False):
            raise PlanningSolverUnavailableError("fake solver unavailable")
        raise AssertionError("the fake solver must be unavailable in these tests")


def _planning_problem_definition(**overrides: object) -> PlanningProblemDefinition:
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    problem_definition = planning_fixture["problem_definition"]
    assert isinstance(problem_definition, dict)
    return replace(PlanningProblemDefinition(**problem_definition), **overrides)


def _assembled_problem(**overrides: object):
    return assemble_planning_problem(
        _planning_problem_definition(**overrides),
        load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH),
    )


def test_required_highs_repeated_runs_match_the_committed_optimal_summary() -> None:
    assembled_problem = _assembled_problem()
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    expected_highs_solve = planning_fixture["expected_required_highs_solve"]
    assert isinstance(expected_highs_solve, dict)
    solve_config = expected_highs_solve["solve_config"]
    optimal_summary = expected_highs_solve["optimal_summary"]
    assert isinstance(solve_config, dict)
    assert isinstance(optimal_summary, dict)

    first = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(**solve_config),
    )
    second = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(**solve_config),
    )

    assert first == second
    assert first.status == optimal_summary["status"]
    repeatability_tolerance = float(expected_highs_solve["repeatability_tolerance"])
    assert first.selected_design == {
        name: pytest.approx(value, rel=0.0, abs=repeatability_tolerance)
        for name, value in optimal_summary["selected_design"].items()
    }
    assert first.objective_value == pytest.approx(
        optimal_summary["objective_value"],
        rel=0.0,
        abs=repeatability_tolerance,
    )
    # The encoded risk is a piecewise MIO estimate, accurate to the MIO epsilon.
    assert first.estimated_shortfall_risk == pytest.approx(
        optimal_summary["estimated_shortfall_risk"],
        rel=0.0,
        abs=float(expected_highs_solve["risk_tolerance"]),
    )
    for key in (
        "backend_module",
        "handoff_strategy",
        "solve_execution_mode",
        "termination_condition",
        "solutions_loaded",
        "solver_interface",
        "solver_options",
        "pyomo_version",
        "highspy_version",
    ):
        assert first.solver_metadata[key] == optimal_summary[key]


def test_required_highs_matches_the_committed_infeasible_summary() -> None:
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    expected_highs_solve = planning_fixture["expected_required_highs_solve"]
    assert isinstance(expected_highs_solve, dict)
    infeasible_case = expected_highs_solve["infeasible_case"]
    expected_summary = expected_highs_solve["infeasible_summary"]
    solve_config = expected_highs_solve["solve_config"]
    assert isinstance(infeasible_case, dict)
    assert isinstance(expected_summary, dict)
    assert isinstance(solve_config, dict)
    infeasible_problem = _assembled_problem(
        chance_limit_epsilon=float(infeasible_case["chance_limit_epsilon"]),
    )

    summary = solve_planning_problem(
        infeasible_problem,
        solve_config=PlanningSolveConfig(**solve_config),
    )

    assert summary.status == expected_summary["status"]
    assert summary.selected_design == expected_summary["selected_design"]
    assert summary.objective_value is expected_summary["objective_value"]
    assert summary.estimated_shortfall_risk is expected_summary["estimated_shortfall_risk"]
    assert (
        summary.solver_metadata["termination_condition"]
        == expected_summary["termination_condition"]
    )
    assert summary.solver_metadata["solutions_loaded"] is False


def test_optional_solve_rejects_skip_when_required_backend_is_unavailable(
    monkeypatch,
) -> None:
    assembled_problem = _assembled_problem()

    def _raise_dependency_error():
        raise PlanningSolverDependencyUnavailableError("pyomo missing")

    monkeypatch.setattr(optional_solver_module, "require_pyomo_backend", _raise_dependency_error)

    with pytest.raises(PlanningSolverDependencyUnavailableError, match="pyomo missing"):
        solve_planning_problem(
            assembled_problem,
            solve_config=PlanningSolveConfig(skip_if_unavailable=True),
        )


def test_optional_solve_rejects_skip_for_non_supplemental_solver() -> None:
    assembled_problem = _assembled_problem()

    with pytest.raises(PlanningSolverUnavailableError, match="fake solver unavailable"):
        solve_planning_problem(
            assembled_problem,
            solve_config=PlanningSolveConfig(
                solver_name="fake-pyomo",
                skip_if_unavailable=True,
            ),
            pyomo_backend=_FakePyomoBackend(
                __name__="pyomo.testing",
                __version__="0.test",
                solver_unavailable=True,
            ),
        )
