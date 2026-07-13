"""Offline integration contracts for optional planning solve workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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
    return assemble_planning_problem(
        PlanningProblemDefinition(
            problem_id="planning-optional-solve-integration",
            decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
            decision_feature_types={
                "battery_capacity_kwh": "continuous",
                "solar_capacity_kw": "continuous",
            },
            shortfall_threshold=0.05,
            chance_limit_epsilon=0.1,
            cost_terms={
                "battery_capacity_kwh": 1200.0,
                "solar_capacity_kw": 950.0,
            },
        ),
        artifact,
    )


def test_optional_solve_repeated_runs_return_the_same_selected_design_and_summary() -> None:
    assembled_problem = _assembled_problem()
    backend = _FakePyomoBackend(__name__="pyomo.testing", __version__="0.test")

    first = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(solver_name="fake-pyomo"),
        pyomo_backend=backend,
    )
    second = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(solver_name="fake-pyomo"),
        pyomo_backend=backend,
    )

    assert first == second
    assert first.status == "optimal"
    assert first.selected_design == {
        "battery_capacity_kwh": 8.0,
        "solar_capacity_kw": 4.0,
    }
    assert first.objective_value == pytest.approx(13400.0)
    assert first.estimated_shortfall_risk == pytest.approx(0.0)
    assert first.solver_metadata["backend_module"] == "pyomo.testing"
    assert first.solver_metadata["handoff_strategy"] == "custom-backend-hook"
    assert first.feasibility_diagnostics["model_name"] == (
        "planning-optional-solve-integration-handoff"
    )


def test_optional_solve_can_report_deterministic_skip_when_backend_is_unavailable(
    monkeypatch,
) -> None:
    assembled_problem = _assembled_problem()

    def _raise_dependency_error():
        raise PlanningSolverDependencyUnavailableError("pyomo missing")

    monkeypatch.setattr(
        "open_energy_lab.planning.optional_solver.require_pyomo_backend",
        _raise_dependency_error,
    )

    summary = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(skip_if_unavailable=True),
    )

    assert summary.status == "skipped"
    assert summary.objective_value is None
    assert summary.estimated_shortfall_risk is None
    assert summary.feasibility_diagnostics["reason"] == "optional pyomo backend unavailable"
    assert summary.solver_metadata["status"] == "skipped"


def test_optional_solve_can_skip_when_requested_solver_is_unavailable() -> None:
    assembled_problem = _assembled_problem()

    summary = solve_planning_problem(
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

    assert summary.status == "skipped"
    assert summary.feasibility_diagnostics["reason"] == "requested planning solver unavailable"
    assert "fake solver unavailable" in summary.feasibility_diagnostics["error"]
    assert summary.solver_metadata["handoff_strategy"] == "custom-backend-hook"
