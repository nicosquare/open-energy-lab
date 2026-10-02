"""Required real Pyomo/HiGHS planning-solver integration contracts."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import highspy
import pyomo
import pyomo.environ as pyo
import pytest

from open_energy_lab.planning.optional_solver import (
    PlanningSolveSummary,
    solve_planning_problem,
)
from open_energy_lab.planning.problem import (
    PlanningProblemAssembly,
    PlanningProblemDefinition,
    assemble_planning_problem,
)
from tpm import load_tpm_artifact
from tests.integration.planning.fixture_utils import (
    PLANNING_PROBLEM_FIXTURE_PATH,
    TPM_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
)


NUMERIC_TOLERANCE = 1e-9
REQUIRED_HIGHSPY_VERSION = "1.15.1"
REQUIRED_PYOMO_VERSION = "6.10.1"
REQUIRED_SOLVER_OPTIONS = {
    "random_seed": 13,
    "threads": 1,
    "time_limit": 30.0,
}


class _TrackingHighsSolver:
    """Transparent proxy that preserves evidence from a real HiGHS solve."""

    def __init__(self, delegate: object, executions: list[dict[str, Any]]) -> None:
        self._delegate = delegate
        self._executions = executions
        self.options = getattr(delegate, "options")

    def available(self, *args: object, **kwargs: object) -> object:
        return getattr(self._delegate, "available")(*args, **kwargs)

    def solve(self, model: object, *args: object, **kwargs: object) -> object:
        execution = {
            "model": model,
            "options": dict(self.options),
            "solve_kwargs": dict(kwargs),
        }
        result = getattr(self._delegate, "solve")(model, *args, **kwargs)
        execution["result"] = result
        self._executions.append(execution)
        return result


def _track_real_highs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    real_solver_factory = pyo.SolverFactory
    executions: list[dict[str, Any]] = []

    def _solver_factory(solver_name: str) -> _TrackingHighsSolver:
        assert solver_name == "highs"
        return _TrackingHighsSolver(real_solver_factory(solver_name), executions)

    monkeypatch.setattr(pyo, "SolverFactory", _solver_factory)
    return executions


def _canonical_highs_problem(*, infeasible: bool = False) -> PlanningProblemAssembly:
    artifact = load_tpm_artifact(load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH))
    fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    problem_definition = fixture["problem_definition"]
    assert isinstance(problem_definition, dict)
    assembled = assemble_planning_problem(
        PlanningProblemDefinition(**problem_definition),
        artifact,
    )
    candidates = assembled.candidate_designs
    if infeasible:
        candidates = tuple(
            replace(candidate, estimated_shortfall_risk=0.25)
            for candidate in candidates
        )
    return replace(
        assembled,
        # An empty payload deliberately exercises the native candidate MILP,
        # while this mode lets HiGHS report infeasibility instead of returning
        # the empirical pre-solve shortcut.
        risk_evaluation_mode="spn_mip",
        spn_mip_payload={},
        candidate_designs=candidates,
        solver_configuration={
            **assembled.solver_configuration,
            "solver_name": "highs",
            "solver_backend_required": True,
            "solver_execution_optional": False,
            "numeric_tolerance": NUMERIC_TOLERANCE,
            "random_seed": 13,
            "threads": 1,
            "time_limit_seconds": 30.0,
        },
    )


def _assert_required_solver_metadata(
    summary: PlanningSolveSummary,
    *,
    termination: str,
) -> None:
    metadata = summary.solver_metadata
    assert metadata["requested_solver_name"] == "highs"
    assert metadata["solver_interface"] == "pyomo.SolverFactory"
    assert metadata["solver_options"] == REQUIRED_SOLVER_OPTIONS
    assert metadata["termination_condition"] == termination
    assert metadata["pyomo_version"] == REQUIRED_PYOMO_VERSION == pyomo.__version__
    assert (
        metadata["highspy_version"]
        == REQUIRED_HIGHSPY_VERSION
        == highspy.Highs().version()
    )


def test_real_highs_solves_integral_model_loads_solution_and_repeats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executions = _track_real_highs(monkeypatch)
    assembled = _canonical_highs_problem()

    first = solve_planning_problem(assembled)
    second = solve_planning_problem(assembled)

    assert first.status == second.status == "optimal"
    assert first.selected_design == second.selected_design == {
        "battery_capacity_kwh": 8.0,
        "solar_capacity_kw": 4.0,
    }
    assert first.objective_value == pytest.approx(
        second.objective_value,
        rel=0.0,
        abs=NUMERIC_TOLERANCE,
    )
    assert first.estimated_shortfall_risk == pytest.approx(
        second.estimated_shortfall_risk,
        rel=0.0,
        abs=NUMERIC_TOLERANCE,
    )
    assert first.solver_metadata["solutions_loaded"] is True
    assert second.solver_metadata["solutions_loaded"] is True
    _assert_required_solver_metadata(first, termination="optimal")
    _assert_required_solver_metadata(second, termination="optimal")

    assert len(executions) == 2
    for execution in executions:
        assert execution["options"] == REQUIRED_SOLVER_OPTIONS
        assert execution["solve_kwargs"]["load_solutions"] is False
        model = execution["model"]
        indicator_values = [
            float(pyo.value(model.choose[candidate_id]))
            for candidate_id in model.CANDIDATES
        ]
        assert sum(indicator_values) == pytest.approx(1.0, abs=NUMERIC_TOLERANCE)
        assert all(
            value == pytest.approx(round(value), abs=NUMERIC_TOLERANCE)
            for value in indicator_values
        )


def test_real_highs_reports_infeasible_without_loading_a_solution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executions = _track_real_highs(monkeypatch)

    summary = solve_planning_problem(_canonical_highs_problem(infeasible=True))

    assert summary.status == "infeasible"
    assert summary.selected_design == {}
    assert summary.objective_value is None
    assert summary.solver_metadata["solutions_loaded"] is False
    _assert_required_solver_metadata(summary, termination="infeasible")

    assert len(executions) == 1
    execution = executions[0]
    assert execution["options"] == REQUIRED_SOLVER_OPTIONS
    assert execution["solve_kwargs"]["load_solutions"] is False
    assert all(
        execution["model"].choose[candidate_id].value is None
        for candidate_id in execution["model"].CANDIDATES
    )
