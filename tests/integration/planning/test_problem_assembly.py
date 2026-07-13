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


def _planning_problem_definition(
    planning_fixture: dict[str, object],
) -> PlanningProblemDefinition:
    problem_definition = planning_fixture["problem_definition"]
    assert isinstance(problem_definition, dict)
    return PlanningProblemDefinition(**problem_definition)


def test_assemble_planning_problem_replays_committed_tpm_artifact_offline() -> None:
    artifact = load_tpm_artifact(load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH))
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    expected_assembly = planning_fixture["expected_assembly"]
    assert isinstance(expected_assembly, dict)
    expected_candidate_designs = expected_assembly["candidate_designs"]
    assert isinstance(expected_candidate_designs, list)

    assert planning_fixture["spec_feature"] == "009-tpm-planning"
    assert planning_fixture["fixture_status"] == "active"
    assert "specs/009-tpm-planning/contracts/planning-solve-contract.md" in planning_fixture[
        "planned_contracts"
    ]

    assembled = assemble_planning_problem(
        _planning_problem_definition(planning_fixture),
        artifact,
    )

    assert assembled.problem_id == planning_fixture["problem_definition"]["problem_id"]
    assert assembled.artifact_id == expected_assembly["artifact_id"]
    assert assembled.dataset_reference == expected_assembly["dataset_reference"]
    assert assembled.decision_features == (
        "battery_capacity_kwh",
        "solar_capacity_kw",
    )
    assert assembled.target_name == expected_assembly["target_name"]
    assert assembled.shortfall_threshold == pytest.approx(0.05)
    assert assembled.chance_limit_epsilon == pytest.approx(0.1)
    assert assembled.objective_direction == "minimize"
    assert len(assembled.candidate_designs) == len(expected_candidate_designs)
    assert assembled.candidate_designs[0].selected_design == expected_candidate_designs[0][
        "selected_design"
    ]
    assert assembled.candidate_designs[0].objective_value == pytest.approx(
        expected_candidate_designs[0]["objective_value"]
    )
    assert assembled.candidate_designs[0].estimated_shortfall_risk == pytest.approx(
        expected_candidate_designs[0]["estimated_shortfall_risk"]
    )
    assert assembled.candidate_designs[1].selected_design == expected_candidate_designs[1][
        "selected_design"
    ]
    assert assembled.candidate_designs[1].objective_value == pytest.approx(
        expected_candidate_designs[1]["objective_value"]
    )
    assert assembled.candidate_designs[1].estimated_shortfall_risk == pytest.approx(
        expected_candidate_designs[1]["estimated_shortfall_risk"]
    )
    assert assembled.piecewise_terms.decision_features == (
        "battery_capacity_kwh",
        "solar_capacity_kw",
    )
    assert assembled.piecewise_terms.decision_feature_types == {
        "battery_capacity_kwh": "continuous",
        "solar_capacity_kw": "continuous",
    }
    assert assembled.piecewise_terms.approximation_kind == "piecewise"
    assert (
        assembled.solver_metadata["canonical_backend"]
        == expected_assembly["solver_metadata"]["canonical_backend"]
    )
    assert assembled.solver_metadata["solver_name"] == expected_assembly["solver_metadata"][
        "solver_name"
    ]
    assert assembled.solver_metadata["dataset_fixture_path"] == expected_assembly[
        "solver_metadata"
    ]["dataset_fixture_path"]
    assert assembled.chance_constraint_metadata == {
        "target_name": expected_assembly["chance_constraint_metadata"]["target_name"],
        "comparison": expected_assembly["chance_constraint_metadata"]["comparison"],
        "threshold": pytest.approx(
            expected_assembly["chance_constraint_metadata"]["threshold"]
        ),
        "chance_limit_epsilon": pytest.approx(
            expected_assembly["chance_constraint_metadata"]["chance_limit_epsilon"]
        ),
        "supported_query_mode": expected_assembly["chance_constraint_metadata"][
            "supported_query_mode"
        ],
    }
    assert assembled.solver_configuration["random_seed"] == 13
    assert assembled.approximation_contract["sum_encoding_mode"] == expected_assembly[
        "approximation_contract"
    ]["sum_encoding_mode"]
    assert assembled.deterministic_fixture_baseline == {
        "candidate_count": expected_assembly["deterministic_fixture_baseline"][
            "candidate_count"
        ],
        "feasible_candidate_count": expected_assembly["deterministic_fixture_baseline"][
            "feasible_candidate_count"
        ],
        "dataset_fixture_path": expected_assembly["deterministic_fixture_baseline"][
            "dataset_fixture_path"
        ],
        "numeric_tolerance": pytest.approx(
            expected_assembly["deterministic_fixture_baseline"]["numeric_tolerance"]
        ),
        "status": expected_assembly["deterministic_fixture_baseline"]["status"],
        "selected_design": expected_assembly["deterministic_fixture_baseline"][
            "selected_design"
        ],
        "objective_value": pytest.approx(
            expected_assembly["deterministic_fixture_baseline"]["objective_value"]
        ),
        "estimated_shortfall_risk": pytest.approx(
            expected_assembly["deterministic_fixture_baseline"][
                "estimated_shortfall_risk"
            ]
        ),
        "matched_row_count": expected_assembly["deterministic_fixture_baseline"][
            "matched_row_count"
        ],
    }
