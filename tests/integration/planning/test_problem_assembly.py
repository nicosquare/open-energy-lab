"""Offline integration contracts for SPN chance-constrained planning assembly."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import open_energy_lab.planning.problem as problem_module
import tpm.conditional_mio as conditional_mio_module

from open_energy_lab.planning import load_planning_dataset
from open_energy_lab.planning.problem import (
    PlanningProblemDefinition,
    assemble_planning_problem,
)
from open_energy_lab.planning import fit_tpm_artifact
from tpm import load_tpm_artifact
from tests.integration.planning.fixture_utils import (
    PLANNING_DATASET_ARTIFACT_FIXTURE_PATH,
    PLANNING_PROBLEM_FIXTURE_PATH,
    TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
)


def _planning_problem_definition(
    planning_fixture: dict[str, object],
) -> PlanningProblemDefinition:
    problem_definition = planning_fixture["problem_definition"]
    assert isinstance(problem_definition, dict)
    return PlanningProblemDefinition(**problem_definition)


def test_assemble_planning_problem_replays_committed_tpm_artifact_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        conditional_mio_module,
        "attach_conditional_mio_pair",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("planning assembly used the composable attachment path")
        ),
    )
    artifact = load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH)
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    expected_assembly = planning_fixture["expected_assembly"]
    assert isinstance(expected_assembly, dict)

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
    assert assembled.decision_features == ("battery_capacity_kwh", "solar_enabled")
    assert assembled.target_name == expected_assembly["target_name"]
    assert assembled.risk_target_name == expected_assembly["risk_target_name"]
    assert assembled.shortfall_threshold == pytest.approx(0.08)
    assert assembled.chance_limit_epsilon == pytest.approx(0.9)
    assert assembled.objective_direction == "minimize"
    assert assembled.piecewise_terms.decision_features == (
        "battery_capacity_kwh",
        "solar_enabled",
    )
    assert assembled.piecewise_terms.decision_feature_types == {
        "battery_capacity_kwh": "continuous",
        "solar_enabled": "binary",
    }
    assert assembled.piecewise_terms.approximation_kind == "piecewise"
    for key, value in expected_assembly["solver_metadata"].items():
        assert assembled.solver_metadata[key] == value
    assert assembled.chance_constraint_metadata == {
        **expected_assembly["chance_constraint_metadata"],
        "threshold": pytest.approx(
            expected_assembly["chance_constraint_metadata"]["threshold"]
        ),
        "chance_limit_epsilon": pytest.approx(
            expected_assembly["chance_constraint_metadata"]["chance_limit_epsilon"]
        ),
    }
    assert assembled.solver_configuration["random_seed"] == 13
    for key, value in expected_assembly["approximation_contract"].items():
        assert assembled.approximation_contract[key] == value
    assert assembled.spn_mip_payload["source"] == "current-spflow-mio-compiler"
    assert assembled.spn_mip_payload["decision_features"] == [
        "battery_capacity_kwh",
        "solar_enabled",
    ]


def test_assemble_planning_problem_rejects_artifacts_without_a_model_sidecar(
    tmp_path: Path,
) -> None:
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)
    dataset = load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)
    dataset_path = tmp_path / "planning-dataset.json"
    artifact_path = tmp_path / "tpm-artifact.json"
    dataset.write_json(dataset_path)
    # The default fit writes a pickle-path sidecar, not the spflow-model-sidecar
    # format that planning compiles.
    fit_tpm_artifact(dataset_path, output_path=artifact_path)
    artifact = load_tpm_artifact(artifact_path)
    definition = replace(
        _planning_problem_definition(planning_fixture),
        decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
        decision_feature_types={
            "battery_capacity_kwh": "continuous",
            "solar_capacity_kw": "continuous",
        },
        cost_terms={"battery_capacity_kwh": 1200.0, "solar_capacity_kw": 950.0},
        approximation_contract={"approximation_kind": "piecewise"},
    )

    with pytest.raises(ValueError, match="requires a current-SPFlow TPM artifact"):
        assemble_planning_problem(definition, artifact)


def test_v3_planning_requires_interval_for_retained_continuous_decision_only() -> None:
    artifact = load_tpm_artifact(
        "tests/fixtures/tpm/tpm_artifact_domains_v3.json"
    )
    definition = SimpleNamespace(
        decision_features=("x", "activation"),
        shortfall_threshold=100.0,
        chance_limit_epsilon=0.9,
        approximation_contract={},
    )

    with pytest.raises(ValueError, match="missing explicit approximation domain.*x"):
        problem_module._build_solver_facing_spn_payload(definition, artifact=artifact)
