"""Schema checks for TPM-domain TPM-planning fixtures."""

from __future__ import annotations

from pathlib import Path

from open_energy_lab.planning.dataset import load_planning_dataset
from tests.integration.planning.fixture_utils import (
    COMMON_LIST_KEYS,
    COMMON_PROVENANCE_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    PLANNING_DATASET_ARTIFACT_FIXTURE_PATH,
    PLANNING_DATASET_EXPORT_FIXTURE_PATH,
    TPM_ARTIFACT_FIXTURE_PATH,
    TPM_FIXTURE_PATHS,
    TPM_QUERY_FIXTURE_PATH,
    UNSUPPORTED_TPM_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
    load_all_tpm_fixtures,
)


def _fixture_data_for(path: Path) -> dict[str, object]:
    return next(data for fixture_path, data in load_all_tpm_fixtures() if fixture_path == path)


def test_tpm_fixture_paths_are_present() -> None:
    assert len(TPM_FIXTURE_PATHS) == 4
    for path in TPM_FIXTURE_PATHS:
        assert path.is_file()


def test_tpm_fixture_common_schema() -> None:
    for fixture_path, fixture_data in load_all_tpm_fixtures():
        missing_top_level_keys = [key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data]
        assert missing_top_level_keys == []
        assert fixture_path in TPM_FIXTURE_PATHS
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


def test_planning_dataset_artifact_fixture_tracks_dataset_contract() -> None:
    fixture_data = _fixture_data_for(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "active"
    assert set(fixture_data["planned_contracts"]) == {
        "specs/009-tpm-planning/contracts/planning-dataset-contract.md",
        "specs/009-tpm-planning/contracts/validation-contract.md",
    }
    loaded = load_planning_dataset(fixture_data)
    export_fixture = load_planning_fixture(PLANNING_DATASET_EXPORT_FIXTURE_PATH)

    assert loaded.dataset_id == export_fixture["expected_dataset_id"]
    assert loaded.row_count == export_fixture["expected_row_count"]
    assert loaded.horizon_steps == export_fixture["expected_horizon_steps"]
    assert list(loaded.column_order) == export_fixture["expected_column_order"]
    assert loaded.export_configuration["flattened_series_fields"] == export_fixture[
        "flattened_series_fields"
    ]
    assert loaded.provenance["dataset_fixture_path"] == (
        "tests/fixtures/planning/planning_dataset_export_case.json"
    )
    assert loaded.provenance["family_seed"] == 13
    assert loaded.provenance["paired_family_seed"] == 13
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "column order" in notes
    assert "row order" in notes
    assert "spflow" in notes
    assert "pyomo" in notes


def test_supported_tpm_artifact_fixture_tracks_schema_expectations() -> None:
    fixture_data = _fixture_data_for(TPM_ARTIFACT_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "placeholder"
    assert set(fixture_data["planned_contracts"]) == {
        "specs/009-tpm-planning/contracts/tpm-artifact-contract.md",
        "specs/009-tpm-planning/contracts/validation-contract.md",
    }
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "typed feature metadata" in notes
    assert "spn payload representation" in notes


def test_unsupported_tpm_artifact_fixture_reserves_version_failure_case() -> None:
    fixture_data = _fixture_data_for(UNSUPPORTED_TPM_ARTIFACT_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "placeholder"
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "supported tpm artifact fixture" in notes
    assert "schema version changed" in notes
    assert "fail fast" in notes


def test_tpm_query_fixture_tracks_query_reproducibility_expectations() -> None:
    fixture_data = _fixture_data_for(TPM_QUERY_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "placeholder"
    assert set(fixture_data["planned_contracts"]) == {
        "specs/009-tpm-planning/contracts/tpm-artifact-contract.md",
        "specs/009-tpm-planning/contracts/validation-contract.md",
    }
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "conditional probability" in notes or "log-likelihood" in notes
    assert "marginalization" in notes
    assert "decision-feature assignment" in notes
