"""Unit contracts for TPM artifact schema and loading rules."""

from __future__ import annotations

import pytest

from open_energy_lab.tpm.artifact import (
    SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS,
    TPMArtifact,
    UnsupportedTPMArtifactVersionError,
    load_tpm_artifact,
)


def _artifact_payload() -> dict[str, object]:
    return {
        "artifact_id": "tpm-artifact-unit",
        "schema_version": "v1",
        "created_at": "2026-06-24T00:00:00Z",
        "dataset_reference": "planning-dataset-export-integration",
        "feature_schema": [
            {
                "feature_name": "battery_capacity_kwh",
                "feature_role": "decision",
                "feature_type": "continuous",
                "bounds": [0.0, 20.0],
                "modifiable": True,
            },
            {
                "feature_name": "solar_has_tracking",
                "feature_role": "decision",
                "feature_type": "binary",
                "discrete_values": ["disabled", "enabled"],
                "modifiable": True,
            },
            {
                "feature_name": "design_name",
                "feature_role": "decision",
                "feature_type": "categorical",
                "discrete_values": ["baseline-a", "baseline-b"],
                "modifiable": True,
            },
            {
                "feature_name": "solar_tilt_choice",
                "feature_role": "decision",
                "feature_type": "mixed",
                "bounds": [0.0, 45.0],
                "discrete_values": ["roof-flat", "roof-pitched"],
                "modifiable": True,
            },
            {
                "feature_name": "shortfall",
                "feature_role": "metric_target",
                "feature_type": "continuous",
                "bounds": [0.0, 1.0],
                "modifiable": False,
            },
            {
                "feature_name": "shortfall_exceeds_threshold",
                "feature_role": "target",
                "feature_type": "binary",
                "discrete_values": [0.0, 1.0],
                "modifiable": False,
            },
        ],
        "target_definition": {
            "target_name": "shortfall",
            "event_target_name": "shortfall_exceeds_threshold",
            "threshold_default": 0.05,
            "supported_query_mode": "exceedance-probability",
        },
        "fit_configuration": {
            "backend_name": "spflow",
            "training_random_seed": 13,
        },
        "spn_payload": {
            "payload_kind": "inline-json-placeholder",
            "node_count": 3,
        },
        "spn_payload_format": "json-inline",
        "query_configuration": {
            "supported_output_modes": [
                "conditional_probability",
                "log_likelihood",
            ],
            "required_decision_features": [
                "battery_capacity_kwh",
                "design_name",
            ],
        },
        "approximation_metadata": {
            "approximation_kind": "piecewise",
            "tolerance": 1e-9,
        },
        "provenance": {
            "dataset_fixture_path": "tests/fixtures/tpm/planning_dataset_v1.json",
            "legacy_evidence_paths": [
                "legacy/old_tpm/src_py/tpm/data/datahandler.py",
                "legacy/old_tpm/src_py/tpm/spn/main.py",
            ],
            "training_random_seed": 13,
        },
    }


def test_supported_tpm_artifact_versions_reserve_v1() -> None:
    assert SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS == ("v1",)


def test_tpm_artifact_placeholder_preserves_minimal_identity_fields() -> None:
    artifact = TPMArtifact(
        artifact_id="tpm-artifact-unit",
        schema_version="v1",
        feature_schema=(
            {
                "feature_name": "battery_capacity_kwh",
                "feature_type": "continuous",
            },
        ),
        provenance={"dataset_reference": "planning-dataset-export-integration"},
    )

    assert artifact.artifact_id == "tpm-artifact-unit"
    assert artifact.schema_version == "v1"
    assert artifact.feature_schema[0]["feature_name"] == "battery_capacity_kwh"
    assert artifact.provenance["dataset_reference"] == "planning-dataset-export-integration"


def test_load_tpm_artifact_preserves_schema_target_and_query_metadata() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    assert artifact.artifact_id == "tpm-artifact-unit"
    assert artifact.dataset_reference == "planning-dataset-export-integration"
    assert artifact.target_definition["target_name"] == "shortfall"
    assert artifact.target_definition["event_target_name"] == "shortfall_exceeds_threshold"
    assert artifact.spn_payload_format == "json-inline"
    assert artifact.query_configuration["supported_output_modes"] == [
        "conditional_probability",
        "log_likelihood",
    ]
    assert artifact.approximation_metadata["approximation_kind"] == "piecewise"
    assert artifact.approximation_metadata["leaf_encoding_mode"] == "histogram"
    assert artifact.approximation_metadata["sum_encoding_mode"] == "piecewise"
    assert artifact.approximation_metadata["breakpoint_policy"]["policy_name"] == (
        "legacy-logspace-v1"
    )


def test_load_tpm_artifact_rejects_unsupported_schema_version() -> None:
    payload = _artifact_payload()
    payload["schema_version"] = "v999"

    with pytest.raises(
        UnsupportedTPMArtifactVersionError,
        match="unsupported tpm artifact schema_version 'v999'",
    ):
        load_tpm_artifact(payload)


def test_loaded_tpm_artifact_rejects_unseen_categorical_values_and_out_of_bounds_assignments() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    with pytest.raises(ValueError, match="design_name|categorical|baseline-z"):
        artifact.validate_feature_assignments({"design_name": "baseline-z"})

    with pytest.raises(ValueError, match="battery_capacity_kwh|bounds|21"):
        artifact.validate_feature_assignments({"battery_capacity_kwh": 21.0})
