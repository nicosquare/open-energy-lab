"""Unit contracts for TPM artifact schema-v2 persistence and loading."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from open_energy_lab.tpm.artifact import (
    SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS,
    UnsupportedTPMArtifactVersionError,
    load_tpm_artifact,
)


SIDECAR_BYTES = b"deterministic-spflow-1.1-sidecar\n"


def _sidecar_hash(payload: bytes = SIDECAR_BYTES) -> str:
    return hashlib.sha256(payload).hexdigest()


def _artifact_payload(
    *,
    execution_mode: str = "production",
    locator: str = "sidecars/tpm-artifact-unit.spflow",
    payload_hash: str | None = None,
) -> dict[str, object]:
    return {
        "artifact_id": "tpm-artifact-unit",
        "schema_version": "v2",
        "created_at": "2026-08-18T00:00:00Z",
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
        "backend_generation": "current-spflow",
        "backend_api_version": "1.1.0",
        "execution_mode": execution_mode,
        "spn_payload": {
            "locator": locator,
            "serialization": "spflow-model-sidecar",
        },
        "spn_payload_format": "spflow-model-sidecar",
        "payload_hash": payload_hash or _sidecar_hash(),
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
            "compiler_version": "spflow-v1-mio-v1",
            "breakpoint_policy": {
                "policy_name": "canonical-five-breakpoint-v1",
                "breakpoint_count": 5,
            },
            "mio_epsilon": 1e-6,
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


def _write_manifest(
    tmp_path: Path,
    *,
    sidecar_payload: bytes = SIDECAR_BYTES,
    payload: dict[str, object] | None = None,
) -> Path:
    artifact_payload = dict(
        payload or _artifact_payload(payload_hash=_sidecar_hash(sidecar_payload))
    )
    manifest_path = tmp_path / "artifacts" / "tpm-artifact.json"
    locator = str(dict(artifact_payload["spn_payload"])["locator"])
    sidecar_path = manifest_path.parent / locator
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_bytes(sidecar_payload)
    manifest_path.write_text(
        json.dumps(artifact_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def test_supported_tpm_artifact_versions_select_schema_v2() -> None:
    assert SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS == ("v2",)


def test_load_schema_v2_preserves_backend_mode_and_sidecar_metadata(tmp_path: Path) -> None:
    artifact = load_tpm_artifact(_write_manifest(tmp_path))

    assert artifact.schema_version == "v2"
    assert artifact.backend_generation == "current-spflow"
    assert artifact.backend_api_version == "1.1.0"
    assert artifact.execution_mode == "production"
    assert artifact.spn_payload["locator"] == "sidecars/tpm-artifact-unit.spflow"
    assert artifact.spn_payload_format == "spflow-model-sidecar"
    assert artifact.payload_hash == _sidecar_hash()
    assert artifact.approximation_metadata["compiler_version"] == "spflow-v1-mio-v1"


@pytest.mark.parametrize(
    "field_name",
    ("backend_generation", "backend_api_version", "execution_mode", "payload_hash"),
)
def test_schema_v2_requires_backend_and_execution_metadata(field_name: str) -> None:
    payload = _artifact_payload()
    payload.pop(field_name)

    with pytest.raises(ValueError, match=field_name):
        load_tpm_artifact(payload)


def test_schema_v2_rejects_unknown_execution_mode() -> None:
    with pytest.raises(ValueError, match=r"execution_mode.*production.*fixture_replay"):
        load_tpm_artifact(_artifact_payload(execution_mode="automatic-fallback"))


@pytest.mark.parametrize(
    "locator",
    (
        "/tmp/tpm-artifact-unit.spflow",
        "../outside-project.spflow",
        "sidecars/../../outside-project.spflow",
    ),
)
def test_schema_v2_rejects_non_project_relative_sidecar_locators(locator: str) -> None:
    with pytest.raises(ValueError, match=r"spn_payload.*locator.*relative|project-relative"):
        load_tpm_artifact(_artifact_payload(locator=locator))


def test_load_schema_v2_verifies_sidecar_sha256_integrity(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)

    artifact = load_tpm_artifact(manifest_path)
    assert artifact.payload_hash == _sidecar_hash()

    sidecar_path = manifest_path.parent / str(dict(artifact.spn_payload)["locator"])
    sidecar_path.write_bytes(b"corrupt-sidecar\n")

    with pytest.raises(ValueError, match=r"(?i)sha-256|integrity|payload hash"):
        load_tpm_artifact(manifest_path)


def test_write_json_atomically_replaces_through_a_sibling_temp_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = load_tpm_artifact(_write_manifest(tmp_path))
    output_path = tmp_path / "published" / "tpm-artifact.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("stale manifest\n", encoding="utf-8")
    replace_calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def _record_replace(
        source: str | bytes | os.PathLike[str],
        destination: str | bytes | os.PathLike[str],
    ) -> None:
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", _record_replace)

    artifact.write_json(output_path)

    assert replace_calls
    temporary_path, destination_path = replace_calls[-1]
    assert destination_path == output_path
    assert temporary_path != destination_path
    assert temporary_path.parent == destination_path.parent
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == "v2"


def test_schema_v1_legacy_payload_is_rejected_with_refit_guidance() -> None:
    payload = _artifact_payload()
    payload["schema_version"] = "v1"

    with pytest.raises(
        UnsupportedTPMArtifactVersionError,
        match=r"(?i)schema.?v?1|legacy|refit",
    ):
        load_tpm_artifact(payload)


def test_load_tpm_artifact_rejects_unknown_schema_version() -> None:
    payload = _artifact_payload()
    payload["schema_version"] = "v999"

    with pytest.raises(
        UnsupportedTPMArtifactVersionError,
        match="unsupported tpm artifact schema_version 'v999'",
    ):
        load_tpm_artifact(payload)


def test_loaded_tpm_artifact_rejects_invalid_feature_assignments(tmp_path: Path) -> None:
    artifact = load_tpm_artifact(_write_manifest(tmp_path))

    with pytest.raises(ValueError, match="design_name|categorical|baseline-z"):
        artifact.validate_feature_assignments({"design_name": "baseline-z"})

    with pytest.raises(ValueError, match="battery_capacity_kwh|bounds|21"):
        artifact.validate_feature_assignments({"battery_capacity_kwh": 21.0})
