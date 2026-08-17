"""Offline integration contracts for optional planning solve workflows."""

from __future__ import annotations

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
from open_energy_lab.tpm import load_tpm_artifact
from tests.integration.planning.fixture_utils import (
    PLANNING_PROBLEM_FIXTURE_PATH,
    TPM_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
)


class _FakePyomoBackend(SimpleNamespace):
    def build_candidate_model(self, **kwargs):
        return SimpleNamespace(model_name=f"{kwargs['problem_id']}-handoff", **kwargs)

    def solve_candidate_model(self, handoff, solve_config):
        if getattr(self, "solver_unavailable", False):
            raise PlanningSolverUnavailableError("fake solver unavailable")

        selected_candidate_id = min(
            handoff.feasible_candidate_ids,
            key=lambda candidate_id: (
                handoff.candidate_lookup[candidate_id].objective_value,
                handoff.candidate_lookup[candidate_id].estimated_shortfall_risk,
            ),
        )
        return {
            "status": "optimal",
            "candidate_id": selected_candidate_id,
            "solver_metadata": {"backend_solver_name": solve_config.solver_name},
            "feasibility_diagnostics": {"model_name": handoff.model.model_name},
        }


def _assembled_problem():
    artifact = load_tpm_artifact(load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH))
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    problem_definition = planning_fixture["problem_definition"]
    assert isinstance(problem_definition, dict)
    return assemble_planning_problem(
        PlanningProblemDefinition(**problem_definition),
        artifact,
    )


def test_optional_solve_repeated_runs_return_the_same_selected_design_and_summary() -> None:
    assembled_problem = _assembled_problem()
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    expected_optional_solve = planning_fixture["expected_optional_solve"]
    assert isinstance(expected_optional_solve, dict)
    solve_config = expected_optional_solve["solve_config"]
    optimal_summary = expected_optional_solve["optimal_summary"]
    assert isinstance(solve_config, dict)
    assert isinstance(optimal_summary, dict)
    backend = _FakePyomoBackend(__name__="pyomo.testing", __version__="0.test")

    first = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(**solve_config),
        pyomo_backend=backend,
    )
    second = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(**solve_config),
        pyomo_backend=backend,
    )

    assert first == second
    assert first.status == optimal_summary["status"]
    assert first.selected_design == optimal_summary["selected_design"]
    assert first.objective_value == pytest.approx(optimal_summary["objective_value"])
    assert first.estimated_shortfall_risk == pytest.approx(
        optimal_summary["estimated_shortfall_risk"]
    )
    assert first.solver_metadata["backend_module"] == optimal_summary["backend_module"]
    assert first.solver_metadata["handoff_strategy"] == optimal_summary["handoff_strategy"]
    assert (
        first.solver_metadata["solve_execution_mode"]
        == optimal_summary["solve_execution_mode"]
    )
    assert first.feasibility_diagnostics["model_name"] == optimal_summary["model_name"]


def test_optional_solve_can_report_deterministic_skip_when_backend_is_unavailable(
    monkeypatch,
) -> None:
    assembled_problem = _assembled_problem()
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    expected_optional_solve = planning_fixture["expected_optional_solve"]
    assert isinstance(expected_optional_solve, dict)
    expected_skip = expected_optional_solve["skip_when_backend_unavailable"]
    assert isinstance(expected_skip, dict)

    def _raise_dependency_error():
        raise PlanningSolverDependencyUnavailableError("pyomo missing")

    monkeypatch.setattr(optional_solver_module, "require_pyomo_backend", _raise_dependency_error)

    summary = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(skip_if_unavailable=True),
    )

    assert summary.status == expected_skip["status"]
    assert summary.objective_value is None
    assert summary.estimated_shortfall_risk is None
    assert summary.feasibility_diagnostics["reason"] == expected_skip["reason"]
    assert summary.solver_metadata["status"] == "skipped"


def test_optional_solve_can_skip_when_requested_solver_is_unavailable() -> None:
    assembled_problem = _assembled_problem()
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    expected_optional_solve = planning_fixture["expected_optional_solve"]
    assert isinstance(expected_optional_solve, dict)
    solve_config = expected_optional_solve["solve_config"]
    expected_skip = expected_optional_solve["skip_when_requested_solver_unavailable"]
    assert isinstance(solve_config, dict)
    assert isinstance(expected_skip, dict)

    summary = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(
            solver_name=str(solve_config["solver_name"]),
            skip_if_unavailable=True,
        ),
        pyomo_backend=_FakePyomoBackend(
            __name__="pyomo.testing",
            __version__="0.test",
            solver_unavailable=True,
        ),
    )

    assert summary.status == expected_skip["status"]
    assert summary.feasibility_diagnostics["reason"] == expected_skip["reason"]
    assert expected_skip["error_substring"] in summary.feasibility_diagnostics["error"]
    assert summary.solver_metadata["handoff_strategy"] == expected_skip["handoff_strategy"]
