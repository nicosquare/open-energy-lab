"""Direct integration coverage for solving serialized SPN MIO models with Gurobi."""

from __future__ import annotations

import pyomo.environ as pyo
import pytest

from open_energy_lab.planning.optional_solver import PlanningSolveConfig, solve_planning_problem
from open_energy_lab.planning.piecewise import build_piecewise_planning_terms
from open_energy_lab.planning.problem import PlanningProblemAssembly


def _gurobi_available() -> bool:
    try:
        solver = pyo.SolverFactory("gurobi")
    except Exception:
        return False
    available = getattr(solver, "available", None)
    if not callable(available):
        return True
    try:
        return bool(available(exception_flag=False))
    except TypeError:
        return bool(available())


@pytest.mark.skipif(not _gurobi_available(), reason="gurobi solver unavailable")
def test_solve_planning_problem_can_solve_a_serialized_spn_model_with_gurobi() -> None:
    piecewise_terms = build_piecewise_planning_terms(
        {
            "approximation_kind": "piecewise",
            "sum_encoding_mode": "piecewise",
        },
        max_terms=2,
        decision_features=("battery_enabled", "solar_enabled"),
        decision_feature_types={
            "battery_enabled": "binary",
            "solar_enabled": "binary",
        },
    )

    assembled_problem = PlanningProblemAssembly(
        problem_id="serialized-spn-gurobi",
        artifact_id="synthetic-artifact",
        dataset_reference="synthetic-dataset",
        decision_features=("battery_enabled", "solar_enabled"),
        target_name="shortfall",
        risk_target_name="shortfall_exceeds_threshold",
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.1,
        objective_direction="minimize",
        cost_terms={
            "battery_enabled": 1200.0,
            "solar_enabled": 950.0,
        },
        piecewise_terms=piecewise_terms,
        solver_metadata={
            "canonical_backend": "pyomo",
            "solver_execution_optional": True,
            "solver_name": "gurobi",
        },
        solver_configuration={
            "backend_name": "pyomo",
            "solver_name": "gurobi",
            "numeric_tolerance": 1e-9,
            "random_seed": 13,
        },
        spn_mip_payload={
            "source": "spflow_backend",
            "decision_features": ["battery_enabled", "solar_enabled"],
            "feature_schema": [
                {
                    "feature_name": "battery_enabled",
                    "feature_role": "decision",
                    "feature_type": "binary",
                    "discrete_values": [0.0, 1.0],
                    "ordering": [0.0, 1.0],
                    "modifiable": True,
                },
                {
                    "feature_name": "solar_enabled",
                    "feature_role": "decision",
                    "feature_type": "binary",
                    "discrete_values": [0.0, 1.0],
                    "ordering": [0.0, 1.0],
                    "modifiable": True,
                },
                {
                    "feature_name": "shortfall_exceeds_threshold",
                    "feature_role": "target",
                    "feature_type": "binary",
                    "discrete_values": [0.0, 1.0],
                    "ordering": [0.0, 1.0],
                    "modifiable": False,
                },
            ],
            "sum_encoding_mode": "piecewise",
            "conditional_models": {
                "numerator_model": {
                    "root_id": 5,
                    "nodes": [
                        {
                            "id": 1,
                            "type": "leaf_binary",
                            "feature_name": "battery_enabled",
                            "densities": [0.2, 0.01],
                        },
                        {
                            "id": 2,
                            "type": "leaf_binary",
                            "feature_name": "solar_enabled",
                            "densities": [0.2, 0.01],
                        },
                        {"id": 5, "type": "product", "children": [1, 2]},
                    ],
                },
                "denominator_model": {
                    "root_id": 6,
                    "nodes": [
                        {
                            "id": 3,
                            "type": "leaf_binary",
                            "feature_name": "battery_enabled",
                            "densities": [0.5, 0.5],
                        },
                        {
                            "id": 4,
                            "type": "leaf_binary",
                            "feature_name": "solar_enabled",
                            "densities": [0.5, 0.5],
                        },
                        {"id": 6, "type": "product", "children": [3, 4]},
                    ],
                },
            },
        },
    )

    summary = solve_planning_problem(
        assembled_problem,
        solve_config=PlanningSolveConfig(solver_name="gurobi"),
    )

    assert summary.status == "optimal"
    assert summary.selected_design == {
        "battery_enabled": 0.0,
        "solar_enabled": 1.0,
    }
    assert summary.objective_value == pytest.approx(950.0)
    assert summary.estimated_shortfall_risk is not None
    assert summary.estimated_shortfall_risk <= 0.1 + 1e-9
    assert summary.solver_metadata["solve_execution_mode"] == "native-pyomo-solver"
    assert summary.solver_metadata["handoff_strategy"] == "native-pyomo-spn"
