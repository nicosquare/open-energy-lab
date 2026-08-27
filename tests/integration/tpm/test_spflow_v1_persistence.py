"""Required current-SPFlow model-sidecar persistence and integrity contracts."""

from __future__ import annotations

import hashlib

import pytest

from open_energy_lab.tpm.artifact import (
    LegacyTPMArtifactVersionError,
    TPMArtifactIntegrityError,
    load_tpm_artifact,
)
from tests.integration.planning.fixture_utils import (
    TPM_ARTIFACT_V1_FIXTURE_PATH,
    TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH,
)
from tests.integration.tpm.spflow_v1_test_support import (
    fit_real_artifact,
    load_current_model_payload,
    normalized_training_tensor,
)


def test_current_model_sidecar_round_trips_with_verified_manifest_hash(tmp_path) -> None:
    import torch

    artifact, manifest_path, _ = fit_real_artifact(tmp_path)
    sidecar_path = artifact.sidecar_path

    assert manifest_path.is_file()
    assert sidecar_path.is_file()
    assert hashlib.sha256(sidecar_path.read_bytes()).hexdigest() == artifact.payload_hash
    assert artifact.spn_payload_format == "spflow-model-sidecar"

    payload = load_current_model_payload(artifact)
    model = payload["model"]
    likelihood = model.log_likelihood(normalized_training_tensor(artifact)[0:2])

    assert isinstance(likelihood, torch.Tensor)
    assert likelihood.shape == (2, 1, 1, 1)
    assert torch.isfinite(likelihood).all()


def test_corrupt_current_model_sidecar_fails_manifest_integrity_check(tmp_path) -> None:
    artifact, manifest_path, _ = fit_real_artifact(tmp_path)
    artifact.sidecar_path.write_bytes(artifact.sidecar_path.read_bytes() + b"corrupt")

    with pytest.raises(TPMArtifactIntegrityError, match=r"SHA-256|integrity"):
        load_tpm_artifact(manifest_path)


def test_committed_production_v2_load_is_byte_stable_and_legacy_classified() -> None:
    manifest_before = TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH.read_bytes()
    first = load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH)
    sidecar_before = first.sidecar_path.read_bytes()

    second = load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH)
    battery = {
        spec.feature_name: spec for spec in second.feature_specs
    }["battery_capacity_kwh"]

    assert first.to_dict() == second.to_dict()
    assert second.schema_version == "v2"
    assert battery.mathematical_domain.shape == "unknown"
    assert battery.mathematical_domain.origin == "omitted"
    assert battery.normalization.origin == "legacy-inferred"
    assert battery.normalize_value(4.0) == pytest.approx(0.2)
    assert TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH.read_bytes() == manifest_before
    assert second.sidecar_path.read_bytes() == sidecar_before


def test_pre_v1_spflow_artifact_is_rejected_with_refit_guidance() -> None:
    with pytest.raises(
        LegacyTPMArtifactVersionError,
        match=r"current SPFlow|refit|source planning dataset",
    ):
        load_tpm_artifact(TPM_ARTIFACT_V1_FIXTURE_PATH)
