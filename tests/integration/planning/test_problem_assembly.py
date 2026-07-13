"""Offline integration contracts for fixture-backed planning-problem assembly."""

from __future__ import annotations

import pytest

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


def _planning_problem_definition() -> PlanningProblemDefinition:
    return PlanningProblemDefinition(
        problem_id="planning-problem-assembly-integration",
        tpm_artifact_reference="tests/fixtures/tpm/tpm_artifact_v1.json",
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
        solver_configuration={
            "backend_name": "pyomo",
            "solver_name": "fake-pyomo",
            "numeric_tolerance": 1e-9,
            "random_seed": 13,
        },
        approximation_contract={
            "approximation_kind": "piecewise",
            "leaf_encoding_mode": "histogram",
            "sum_encoding_mode": "piecewise",
        },
        fixture_baseline={
            "label": "planning-baseline-a",
            "source_fixture_path": "tests/fixtures/planning/planning_problem_case.json",
            "expected_status": "optimal",
            "expected_selected_design": {
                "battery_capacity_kwh": 8.0,
                "solar_capacity_kw": 4.0,
            },
            "expected_objective_value": 13400.0,
            "expected_estimated_shortfall_risk": 0.0,
            "expected_candidate_count": 2,
            "expected_feasible_candidate_count": 2,
        },
    )


def test_assemble_planning_problem_replays_committed_tpm_artifact_offline() -> None:
    artifact = load_tpm_artifact(load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH))
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)

    assert planning_fixture["spec_feature"] == "009-tpm-planning"
    assert "specs/009-tpm-planning/contracts/planning-solve-contract.md" in planning_fixture[
        "planned_contracts"
    ]

    assembled = assemble_planning_problem(
        _planning_problem_definition(),
        artifact,
    )

    assert assembled.problem_id == "planning-problem-assembly-integration"
    assert assembled.artifact_id == "tpm-artifact:planning-dataset-export-integration"
    assert assembled.dataset_reference == "planning-dataset-export-integration"
    assert assembled.decision_features == (
        "battery_capacity_kwh",
        "solar_capacity_kw",
    )
    assert assembled.target_name == "shortfall"
    assert assembled.shortfall_threshold == pytest.approx(0.05)
    assert assembled.chance_limit_epsilon == pytest.approx(0.1)
    assert assembled.objective_direction == "minimize"
    assert len(assembled.candidate_designs) == 2
    assert assembled.candidate_designs[0].selected_design == {
        "battery_capacity_kwh": 8.0,
        "solar_capacity_kw": 4.0,
    }
    assert assembled.candidate_designs[0].objective_value == pytest.approx(13400.0)
    assert assembled.candidate_designs[0].estimated_shortfall_risk == pytest.approx(0.0)
    assert assembled.piecewise_terms.decision_features == (
        "battery_capacity_kwh",
        "solar_capacity_kw",
    )
    assert assembled.piecewise_terms.decision_feature_types == {
        "battery_capacity_kwh": "continuous",
        "solar_capacity_kw": "continuous",
    }
    assert assembled.piecewise_terms.approximation_kind == "piecewise"
    assert assembled.solver_metadata["canonical_backend"] == "pyomo"
    assert assembled.solver_metadata["solver_name"] == "fake-pyomo"
    assert assembled.solver_metadata["dataset_fixture_path"] == (
        "tests/fixtures/tpm/planning_dataset_v1.json"
    )
    assert assembled.chance_constraint_metadata == {
        "target_name": "shortfall",
        "comparison": ">",
        "threshold": pytest.approx(0.05),
        "chance_limit_epsilon": pytest.approx(0.1),
        "supported_query_mode": "exceedance-probability",
    }
    assert assembled.solver_configuration["random_seed"] == 13
    assert assembled.approximation_contract["sum_encoding_mode"] == "piecewise"
    assert assembled.deterministic_fixture_baseline == {
        "candidate_count": 2,
        "feasible_candidate_count": 2,
        "dataset_fixture_path": "tests/fixtures/tpm/planning_dataset_v1.json",
        "numeric_tolerance": pytest.approx(1e-9),
        "status": "optimal",
        "selected_design": {
            "battery_capacity_kwh": 8.0,
            "solar_capacity_kw": 4.0,
        },
        "objective_value": pytest.approx(13400.0),
        "estimated_shortfall_risk": pytest.approx(0.0),
        "matched_row_count": 1,
    }
