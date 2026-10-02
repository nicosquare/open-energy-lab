"""Supplemental licensed Gurobi comparison against the required HiGHS solve."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace

import pytest

from open_energy_lab.planning.optional_solver import (
    PlanningSolveConfig,
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


def _comparison_problem() -> PlanningProblemAssembly:
    artifact = load_tpm_artifact(load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH))
    fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    problem_definition = fixture["problem_definition"]
    assert isinstance(problem_definition, dict)
    assembled = assemble_planning_problem(
        PlanningProblemDefinition(**problem_definition),
        artifact,
    )
    return replace(
        assembled,
        risk_evaluation_mode="spn_mip",
        spn_mip_payload={},
        solver_configuration={
            **assembled.solver_configuration,
            "solver_name": "highs",
            "solver_backend_required": True,
            "solver_execution_optional": False,
            "numeric_tolerance": 1e-9,
            "random_seed": 13,
            "threads": 1,
            "time_limit_seconds": 30.0,
        },
    )


def _comparison_tolerances() -> tuple[float, float]:
    fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    comparison = fixture["supplemental_solver_comparison"]
    assert isinstance(comparison, dict)
    assert comparison["reference_solver"] == "highs"
    assert comparison["candidate_solver"] == "gurobi"
    return (
        float(comparison["objective_tolerance"]),
        float(comparison["risk_tolerance"]),
    )


def _required_value(value: float | None, *, field_name: str) -> float:
    assert value is not None, f"{field_name} must be recorded for an optimal solve"
    return float(value)


def _availability_skip_result(
    *,
    highs: PlanningSolveSummary,
    gurobi: PlanningSolveSummary,
    objective_tolerance: float,
    risk_tolerance: float,
) -> dict[str, object]:
    return {
        "comparison_status": "availability-skip",
        "highs_status": highs.status,
        "highs_objective_value": _required_value(
            highs.objective_value,
            field_name="highs_objective_value",
        ),
        "highs_risk_value": _required_value(
            highs.estimated_shortfall_risk,
            field_name="highs_risk_value",
        ),
        "gurobi_status": "availability-skip",
        "gurobi_objective_value": None,
        "gurobi_risk_value": None,
        "objective_absolute_difference": None,
        "risk_absolute_difference": None,
        "objective_tolerance": objective_tolerance,
        "risk_tolerance": risk_tolerance,
        "availability_skip_reason": str(
            gurobi.feasibility_diagnostics.get("error")
            or gurobi.feasibility_diagnostics.get("reason")
            or "Gurobi binary or license unavailable"
        ),
    }


def test_gurobi_objective_and_risk_match_required_highs(
    record_property: Callable[[str, object], None],
) -> None:
    objective_tolerance, risk_tolerance = _comparison_tolerances()
    problem = _comparison_problem()

    highs = solve_planning_problem(problem)
    assert highs.status == "optimal"

    gurobi = solve_planning_problem(
        problem,
        solve_config=PlanningSolveConfig(
            solver_name="gurobi",
            skip_if_unavailable=True,
        ),
    )
    if gurobi.status == "skipped":
        result = _availability_skip_result(
            highs=highs,
            gurobi=gurobi,
            objective_tolerance=objective_tolerance,
            risk_tolerance=risk_tolerance,
        )
        serialized = json.dumps(result, sort_keys=True)
        record_property("solver_comparison", serialized)
        pytest.skip(f"Gurobi comparison result: {serialized}")

    assert gurobi.status == "optimal"
    highs_objective = _required_value(
        highs.objective_value,
        field_name="highs_objective_value",
    )
    highs_risk = _required_value(
        highs.estimated_shortfall_risk,
        field_name="highs_risk_value",
    )
    gurobi_objective = _required_value(
        gurobi.objective_value,
        field_name="gurobi_objective_value",
    )
    gurobi_risk = _required_value(
        gurobi.estimated_shortfall_risk,
        field_name="gurobi_risk_value",
    )
    objective_difference = abs(highs_objective - gurobi_objective)
    risk_difference = abs(highs_risk - gurobi_risk)
    comparison_passed = (
        objective_difference <= objective_tolerance
        and risk_difference <= risk_tolerance
    )
    result = {
        "comparison_status": "pass" if comparison_passed else "fail",
        "highs_status": highs.status,
        "highs_objective_value": highs_objective,
        "highs_risk_value": highs_risk,
        "gurobi_status": gurobi.status,
        "gurobi_objective_value": gurobi_objective,
        "gurobi_risk_value": gurobi_risk,
        "objective_absolute_difference": objective_difference,
        "risk_absolute_difference": risk_difference,
        "objective_tolerance": objective_tolerance,
        "risk_tolerance": risk_tolerance,
        "availability_skip_reason": None,
    }
    record_property("solver_comparison", json.dumps(result, sort_keys=True))

    assert gurobi.selected_design == highs.selected_design
    assert objective_difference <= objective_tolerance
    assert risk_difference <= risk_tolerance
