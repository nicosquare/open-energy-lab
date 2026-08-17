"""Schema checks for planning-domain TPM-planning fixtures."""

from __future__ import annotations

from pathlib import Path

from tests.integration.planning.fixture_utils import (
    COMMON_LIST_KEYS,
    COMMON_PROVENANCE_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    PLANNING_DATASET_EXPORT_FIXTURE_PATH,
    PLANNING_FIXTURE_PATHS,
    PLANNING_PROBLEM_FIXTURE_PATH,
    load_all_planning_fixtures,
)


def _fixture_data_for(path: Path) -> dict[str, object]:
    return next(data for fixture_path, data in load_all_planning_fixtures() if fixture_path == path)


def test_planning_fixture_paths_are_present() -> None:
    assert len(PLANNING_FIXTURE_PATHS) == 2
    for path in PLANNING_FIXTURE_PATHS:
        assert path.is_file()


def test_planning_fixture_common_schema() -> None:
    for fixture_path, fixture_data in load_all_planning_fixtures():
        missing_top_level_keys = [key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data]
        assert missing_top_level_keys == []
        assert fixture_path in PLANNING_FIXTURE_PATHS
        assert fixture_data["fixture_name"] == fixture_path.stem
        assert fixture_data["fixture_status"] in {"placeholder", "active"}
        assert fixture_data["spec_feature"] == "009-tpm-planning"
        assert isinstance(fixture_data["purpose"], str) and fixture_data["purpose"]

        provenance = fixture_data["provenance"]
        assert isinstance(provenance, dict)
        missing_provenance_keys = [key for key in COMMON_PROVENANCE_KEYS if key not in provenance]
        assert missing_provenance_keys == []
        assert isinstance(provenance["author"], str) and provenance["author"]
        assert isinstance(provenance["origin"], str) and provenance["origin"]

        legacy_evidence_paths = provenance["legacy_evidence_paths"]
        assert isinstance(legacy_evidence_paths, list)
        assert legacy_evidence_paths != []
        for legacy_path in legacy_evidence_paths:
            assert isinstance(legacy_path, str)
            assert legacy_path.startswith("legacy/")
            assert Path(legacy_path).is_file()

        generation_command = provenance["generation_command"]
        assert generation_command is None or (
            isinstance(generation_command, str) and generation_command
        )

        random_seed = provenance["random_seed"]
        assert random_seed is None or isinstance(random_seed, int)

        refresh_policy = provenance["refresh_policy"]
        assert isinstance(refresh_policy, str) and refresh_policy

        for key in COMMON_LIST_KEYS:
            assert isinstance(fixture_data[key], list)
            assert fixture_data[key] != []

        for contract_path in fixture_data["planned_contracts"]:
            assert isinstance(contract_path, str)
            assert contract_path.startswith("specs/009-tpm-planning/contracts/")
            assert Path(contract_path).is_file()

        for note in fixture_data["notes"]:
            assert isinstance(note, str) and note


def test_planning_dataset_export_fixture_tracks_export_contracts() -> None:
    fixture_data = _fixture_data_for(PLANNING_DATASET_EXPORT_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "active"
    assert set(fixture_data["planned_contracts"]) == {
        "specs/009-tpm-planning/contracts/simulator-export-contract.md",
        "specs/009-tpm-planning/contracts/planning-dataset-contract.md",
        "specs/009-tpm-planning/contracts/validation-contract.md",
    }
    assert fixture_data["dataset_artifact_fixture_path"] == "tests/fixtures/tpm/planning_dataset_v1.json"
    assert fixture_data["expected_dataset_id"] == "planning-dataset-export-integration"
    assert fixture_data["target_name"] == "shortfall"
    assert fixture_data["flattened_series_fields"] == [
        "global_horizontal_irradiance_w_per_m2",
        "site_electric_load_kw",
        "unmet_load_kw",
    ]
    assert fixture_data["expected_row_count"] == 2
    assert fixture_data["expected_horizon_steps"] == 3
    assert len(fixture_data["design_metadata_rows"]) == fixture_data["expected_row_count"]
    assert fixture_data["expected_column_order"][0] == "scenario_index"
    assert fixture_data["expected_column_order"][-2] == "shortfall"
    assert fixture_data["expected_column_order"][-1] == "shortfall_exceeds_threshold"
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "deterministic" in notes
    assert "offline" in notes
    assert "reviewable" in notes


def test_planning_problem_fixture_tracks_first_release_scope() -> None:
    fixture_data = _fixture_data_for(PLANNING_PROBLEM_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "active"
    assert set(fixture_data["planned_contracts"]) == {
        "specs/009-tpm-planning/contracts/planning-solve-contract.md",
        "specs/009-tpm-planning/contracts/validation-contract.md",
    }
    assert fixture_data["tpm_artifact_fixture_path"] == "tests/fixtures/tpm/tpm_artifact_v1.json"
    problem_definition = fixture_data["problem_definition"]
    expected_assembly = fixture_data["expected_assembly"]
    expected_optional_solve = fixture_data["expected_optional_solve"]
    assert isinstance(problem_definition, dict)
    assert isinstance(expected_assembly, dict)
    assert isinstance(expected_optional_solve, dict)
    assert problem_definition["problem_id"] == "planning-problem-assembly-integration"
    assert problem_definition["decision_features"] == [
        "battery_capacity_kwh",
        "solar_capacity_kw",
    ]
    assert problem_definition["risk_evaluation_mode"] == "spn_mip"
    assert problem_definition["solver_configuration"]["backend_name"] == "pyomo"
    assert problem_definition["solver_configuration"]["solver_name"] == "fake-pyomo"
    assert problem_definition["fixture_baseline"]["expected_status"] == "optimal"
    assert expected_assembly["artifact_id"] == "tpm-artifact:planning-dataset-export-integration"
    assert expected_assembly["risk_target_name"] == "shortfall_exceeds_threshold"
    assert expected_assembly["deterministic_fixture_baseline"]["candidate_count"] == 2
    assert expected_optional_solve["optimal_summary"]["status"] == "optimal"
    assert expected_optional_solve["skip_when_backend_unavailable"]["status"] == "skipped"
    assert (
        expected_optional_solve["skip_when_requested_solver_unavailable"]["handoff_strategy"]
        == "custom-backend-hook"
    )
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "battery and solar" in notes
    assert "solver-optional" in notes
