"""Integration coverage for the TPM fit-reload-query workflow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from open_energy_lab.planning import load_planning_dataset
from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.fit import fit_tpm_artifact
from open_energy_lab.tpm.query import TPMQueryRequest, query_tpm_artifact
from tests.integration.planning.fixture_utils import PLANNING_DATASET_ARTIFACT_FIXTURE_PATH


def test_planning_dataset_fixture_exposes_tpm_fit_preconditions() -> None:
    dataset = load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)
    feature_types = {
        entry["feature_name"]: entry["feature_type"] for entry in dataset.design_feature_schema
    }

    assert dataset.dataset_id == "planning-dataset-export-integration"
    assert dataset.target_metadata["target_name"] == "shortfall"
    assert dataset.export_configuration["flattened_series_fields"] == [
        "global_horizontal_irradiance_w_per_m2",
        "site_electric_load_kw",
        "unmet_load_kw",
    ]
    assert feature_types == {
        "battery_capacity_kwh": "continuous",
        "solar_capacity_kw": "continuous",
        "design_name": "categorical",
    }


def test_fit_reload_workflow_persists_tpm_artifact_offline(
    tmp_path: Path,
) -> None:
    dataset = load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)
    artifact_path = tmp_path / "tpm-artifact-v1.json"
    fake_backend = SimpleNamespace(__name__="spflow.testing", __version__="0.test")

    fitted_artifact = fit_tpm_artifact(
        dataset,
        output_path=artifact_path,
        spflow_backend=fake_backend,
    )
    reloaded_artifact = load_tpm_artifact(artifact_path)

    assert artifact_path.is_file()
    assert reloaded_artifact.artifact_id == fitted_artifact.artifact_id
    assert reloaded_artifact.dataset_reference == dataset.dataset_id
    assert reloaded_artifact.fit_configuration["backend_name"] == "spflow"
    assert reloaded_artifact.query_configuration["required_decision_features"] == [
        "battery_capacity_kwh",
        "solar_capacity_kw",
        "design_name",
    ]


def test_fit_reload_query_workflow_runs_from_exported_planning_dataset(
    tmp_path: Path,
) -> None:
    dataset = load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)
    artifact_path = tmp_path / "tpm-artifact-v1.json"
    fake_backend = SimpleNamespace(__name__="spflow.testing", __version__="0.test")

    fitted_artifact = fit_tpm_artifact(
        dataset,
        output_path=artifact_path,
        spflow_backend=fake_backend,
    )
    reloaded_artifact = load_tpm_artifact(artifact_path)
    result = query_tpm_artifact(
        reloaded_artifact,
        TPMQueryRequest(
            decision_assignments={
                "battery_capacity_kwh": 8.0,
                "design_name": "baseline-a",
            },
            marginalized_features=("solar_capacity_kw",),
            output_mode="conditional_probability",
            target_name="shortfall",
        ),
    )

    assert artifact_path.is_file()
    assert reloaded_artifact.artifact_id == fitted_artifact.artifact_id
    assert result["target_name"] == "shortfall"
    assert result["output_mode"] == "conditional_probability"
    assert result["marginalized_features"] == ("solar_capacity_kw",)
    assert result["value"] == pytest.approx(0.0)
