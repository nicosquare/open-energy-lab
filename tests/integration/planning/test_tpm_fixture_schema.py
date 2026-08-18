"""Schema checks for TPM-domain TPM-planning fixtures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from open_energy_lab.planning.dataset import load_planning_dataset
from open_energy_lab.tpm import (
    TPMQueryRequest,
    UnsupportedTPMArtifactVersionError,
    load_tpm_artifact,
    query_tpm_artifact,
)
from tests.integration.planning.fixture_utils import (
    COMMON_LIST_KEYS,
    COMMON_PROVENANCE_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    PLANNING_DATASET_ARTIFACT_FIXTURE_PATH,
    PLANNING_DATASET_EXPORT_FIXTURE_PATH,
    TPM_ARTIFACT_FIXTURE_PATH,
    TPM_ARTIFACT_V1_FIXTURE_PATH,
    TPM_FIXTURE_PATHS,
    TPM_QUERY_FIXTURE_PATH,
    UNSUPPORTED_TPM_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
    load_all_tpm_fixtures,
)


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    return value


def _fixture_data_for(path: Path) -> dict[str, object]:
    return next(data for fixture_path, data in load_all_tpm_fixtures() if fixture_path == path)


def test_tpm_fixture_paths_are_present() -> None:
    assert len(TPM_FIXTURE_PATHS) == 5
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
    assert loaded.target_metadata["event_target_name"] == "shortfall_exceeds_threshold"
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

    assert fixture_data["fixture_status"] == "active"
    assert set(fixture_data["planned_contracts"]) == {
        "specs/009-tpm-planning/contracts/tpm-artifact-contract.md",
        "specs/009-tpm-planning/contracts/validation-contract.md",
    }
    artifact = load_tpm_artifact(TPM_ARTIFACT_FIXTURE_PATH)

    assert artifact.schema_version == "v2"
    assert artifact.artifact_id == "tpm-artifact:planning-dataset-export-integration"
    assert artifact.dataset_reference == "planning-dataset-export-integration"
    assert artifact.backend_generation == "current-spflow"
    assert artifact.backend_api_version == "1.1.0"
    assert artifact.execution_mode == "fixture_replay"
    assert artifact.payload_locator == "sidecars/tpm_artifact_v2.fixture.json"
    assert artifact.sidecar_path.is_file()
    assert artifact.provenance["dataset_fixture_path"] == "tests/fixtures/tpm/planning_dataset_v1.json"
    assert artifact.provenance["training_random_seed"] == 13
    assert artifact.target_definition["event_target_name"] == "shortfall_exceeds_threshold"
    assert artifact.query_configuration["required_decision_features"] == [
        "battery_capacity_kwh",
        "solar_capacity_kw",
        "design_name",
    ]
    assert artifact.approximation_metadata["approximation_kind"] == "piecewise"
    assert artifact.spn_payload["serialization"] == "fixture-replay-evidence-json"
    assert artifact.approximation_metadata["compiler_status"] == "contract-fixture"
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "current-spflow" in notes
    assert "sha-256" in notes


def test_schema_v1_tpm_artifact_fixture_is_retained_for_refit_rejection() -> None:
    fixture_data = _fixture_data_for(TPM_ARTIFACT_V1_FIXTURE_PATH)

    assert fixture_data["schema_version"] == "v1"
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "not a supported reload or query fixture" in notes
    assert "refit" in notes

    with pytest.raises(
        UnsupportedTPMArtifactVersionError,
        match=r"(?i)schema.?v?1|legacy|refit",
    ):
        load_tpm_artifact(fixture_data)


def test_unsupported_tpm_artifact_fixture_reserves_version_failure_case() -> None:
    fixture_data = _fixture_data_for(UNSUPPORTED_TPM_ARTIFACT_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "active"
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "supported tpm artifact fixture" in notes
    assert "schema version changed" in notes
    assert "fail fast" in notes

    with pytest.raises(
        UnsupportedTPMArtifactVersionError,
        match="unsupported tpm artifact schema_version 'v999'",
    ):
        load_tpm_artifact(fixture_data)


def test_tpm_query_fixture_tracks_query_reproducibility_expectations() -> None:
    fixture_data = _fixture_data_for(TPM_QUERY_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "active"
    assert set(fixture_data["planned_contracts"]) == {
        "specs/009-tpm-planning/contracts/tpm-artifact-contract.md",
        "specs/009-tpm-planning/contracts/validation-contract.md",
    }
    artifact_fixture_path = Path(str(fixture_data["artifact_fixture_path"]))
    assert artifact_fixture_path == TPM_ARTIFACT_FIXTURE_PATH
    assert artifact_fixture_path.is_file()

    query_request = fixture_data["query_request"]
    assert isinstance(query_request, dict)
    assert query_request["execution_mode"] == "fixture_replay"

    artifact = load_tpm_artifact(_fixture_data_for(artifact_fixture_path))
    result = query_tpm_artifact(
        artifact,
        TPMQueryRequest(
            decision_assignments=dict(query_request["decision_assignments"]),
            marginalized_features=tuple(query_request["marginalized_features"]),
            output_mode=str(query_request["output_mode"]),
            target_name=str(query_request["target_name"]),
        ),
    )

    assert _normalize(result) == _normalize(fixture_data["expected_result"])
    notes = " ".join(str(note).lower() for note in fixture_data["notes"])
    assert "conditional probability" in notes or "log-likelihood" in notes
    assert "marginalization" in notes
    assert "decision-feature assignment" in notes
