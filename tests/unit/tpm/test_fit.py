"""Unit coverage for TPM artifact fitting and lazy SPFlow loading."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from open_energy_lab.planning import load_planning_dataset
from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.fit import TPMFitConfig, fit_tpm_artifact
from open_energy_lab.tpm.optional_spflow import SPFlowDependencyUnavailableError
from tests.integration.planning.fixture_utils import PLANNING_DATASET_ARTIFACT_FIXTURE_PATH


def _planning_dataset():
    return load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)


def test_fit_tpm_artifact_persists_training_configuration_with_injected_backend(
    tmp_path: Path,
) -> None:
    dataset = _planning_dataset()
    artifact_path = tmp_path / "tpm-artifact-v1.json"
    fake_backend = SimpleNamespace(__name__="spflow.testing", __version__="0.test")

    artifact = fit_tpm_artifact(
        dataset,
        output_path=artifact_path,
        fit_config=TPMFitConfig(
            training_random_seed=97,
            notes=("fixture-backed-fit",),
        ),
        spflow_backend=fake_backend,
    )
    reloaded = load_tpm_artifact(artifact_path)

    assert artifact_path.is_file()
    assert artifact.artifact_id == "tpm-artifact:planning-dataset-export-integration"
    assert reloaded.fit_configuration["backend_name"] == "spflow"
    assert reloaded.fit_configuration["training_random_seed"] == 97
    assert reloaded.spn_payload_format == "json-inline"
    assert reloaded.spn_payload["backend_module"] == "spflow.testing"
    assert reloaded.spn_payload["backend_version"] == "0.test"
    assert reloaded.spn_payload["row_count"] == dataset.row_count
    assert reloaded.query_configuration["required_decision_features"] == [
        "battery_capacity_kwh",
        "solar_capacity_kw",
        "design_name",
    ]

    feature_roles = {
        entry["feature_name"]: entry["feature_role"] for entry in reloaded.feature_schema
    }
    assert feature_roles["battery_capacity_kwh"] == "decision"
    assert feature_roles["ghi_0"] == "context"
    assert feature_roles["shortfall"] == "target"


def test_fit_tpm_artifact_fails_lazily_when_spflow_is_unavailable(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "should-not-exist.json"

    with pytest.raises(SPFlowDependencyUnavailableError, match="optional 'spflow' dependency"):
        fit_tpm_artifact(_planning_dataset(), output_path=artifact_path)

    assert not artifact_path.exists()
