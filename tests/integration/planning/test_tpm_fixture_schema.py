"""Schema checks for TPM-domain TPM-planning fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_energy_lab.planning.dataset import load_planning_dataset
from tpm import (
    UnsupportedTPMArtifactVersionError,
    compile_spflow_model_to_mio,
    load_tpm_artifact,
)
from tpm.spflow_backend import load_spflow_payload
from tests.integration.planning.fixture_utils import (
    COMMON_LIST_KEYS,
    COMMON_PROVENANCE_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    PLANNING_DATASET_ARTIFACT_FIXTURE_PATH,
    PLANNING_DATASET_EXPORT_FIXTURE_PATH,
    TPM_ARTIFACT_V1_FIXTURE_PATH,
    TPM_FIXTURE_PATHS,
    TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH,
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
            legacy_repository = Path(*Path(legacy_path).parts[:2])
            if legacy_repository.is_dir() and any(legacy_repository.iterdir()):
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


def test_production_tpm_fixture_contains_real_current_spflow_evidence() -> None:
    fixture_data = _fixture_data_for(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH)
    artifact = load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH)

    assert fixture_data["fixture_status"] == "active"
    assert artifact.schema_version == "v2"
    assert artifact.execution_mode == "production"
    assert artifact.backend_generation == "current-spflow"
    assert artifact.backend_api_version == "1.1.0"
    assert artifact.spn_payload_format == "spflow-model-sidecar"
    assert artifact.payload_locator == (
        "sidecars/tpm_artifact_spflow_v1.spn_payload.pkl"
    )
    assert artifact.sidecar_path.is_file()
    assert artifact.provenance["production_model"] is True
    assert artifact.provenance["training_random_seed"] == 13
    assert artifact.provenance["sidecar_sha256"] == artifact.payload_hash

    approximation = artifact.approximation_metadata
    assert approximation["compiler_version"] == "spflow-v1-mio-v1"
    assert approximation["compiler_status"] == "production-validated"
    assert approximation["leaf_encoding_mode"] == "piecewise-log-density"
    assert approximation["compiler_sum_encoding_mode"] == "weighted-logsumexp"
    assert approximation["breakpoint_policy"]["piecewise_breakpoint_count"] == 5
    assert fixture_data["approximation_metadata"]["breakpoint_policy"][
        "breakpoint_count"
    ] == 5
    assert approximation["mio_epsilon"] == 1e-6

    runtime_payload = load_spflow_payload(artifact)
    assert runtime_payload is not None
    assert runtime_payload["payload_kind"] == "current-spflow-model-sidecar"
    assert runtime_payload["model"] is not None
    compiled = compile_spflow_model_to_mio(
        runtime_payload["model"],
        feature_schema=artifact.feature_specs,
    )
    assert compiled["compiler_version"] == approximation["compiler_version"]
    assert compiled["breakpoint_policy"]["breakpoint_count"] == 5
    assert compiled["mio_epsilon"] == approximation["mio_epsilon"]


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
