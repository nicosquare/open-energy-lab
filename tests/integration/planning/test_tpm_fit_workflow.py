"""Integration coverage for the TPM fit-reload-query workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_energy_lab.planning import load_planning_dataset
from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.fit import fit_tpm_artifact
from open_energy_lab.tpm.query import TPMQueryRequest, query_tpm_artifact
from tests.integration.planning.fixture_utils import PLANNING_DATASET_ARTIFACT_FIXTURE_PATH


_PENDING_US2_IMPLEMENTATION = (
    "User Story 2 implementation tasks T025-T029 are still pending."
)


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


@pytest.mark.xfail(strict=True, reason=_PENDING_US2_IMPLEMENTATION)
def test_fit_reload_query_workflow_runs_from_exported_planning_dataset(
    tmp_path: Path,
) -> None:
    dataset = load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)
    artifact_path = tmp_path / "tpm-artifact-v1.json"

    fitted_artifact = fit_tpm_artifact(dataset, output_path=artifact_path)
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

