"""Unit contracts for persisted planning dataset artifacts."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from open_energy_lab.planning.dataset import (
    PLANNING_DATASET_REQUIRED_KEYS,
    PlanningDatasetArtifact,
    SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS,
    UnsupportedPlanningDatasetVersionError,
    load_planning_dataset,
)


def _dataset_payload() -> dict[str, object]:
    return {
        "dataset_id": "planning-dataset-unit",
        "schema_version": "v1",
        "created_at": "2026-06-24T00:00:00Z",
        "row_count": 2,
        "horizon_steps": 3,
        "timestep_hours": 24.0,
        "column_order": [
            "scenario_index",
            "battery_capacity_kwh",
            "solar_capacity_kw",
            "ghi_0",
            "ghi_1",
            "ghi_2",
            "load_0",
            "load_1",
            "load_2",
            "unmet_load_0",
            "unmet_load_1",
            "unmet_load_2",
            "shortfall",
            "shortfall_exceeds_threshold",
        ],
        "rows": [
            {
                "scenario_index": 0,
                "battery_capacity_kwh": 8.0,
                "solar_capacity_kw": 4.0,
                "ghi_0": 500.0,
                "ghi_1": 600.0,
                "ghi_2": 700.0,
                "load_0": 10.0,
                "load_1": 20.0,
                "load_2": 30.0,
                "unmet_load_0": 0.0,
                "unmet_load_1": 0.0,
                "unmet_load_2": 3.0,
                "shortfall": 0.05,
                "shortfall_exceeds_threshold": 0,
            },
            {
                "scenario_index": 1,
                "battery_capacity_kwh": 10.0,
                "solar_capacity_kw": 5.0,
                "ghi_0": 450.0,
                "ghi_1": 550.0,
                "ghi_2": 650.0,
                "load_0": 5.0,
                "load_1": 15.0,
                "load_2": 25.0,
                "unmet_load_0": 0.0,
                "unmet_load_1": 1.0,
                "unmet_load_2": 0.0,
                "shortfall": 1.0 / 45.0,
                "shortfall_exceeds_threshold": 0,
            },
        ],
        "design_feature_schema": [
            {
                "feature_name": "battery_capacity_kwh",
                "feature_role": "decision",
                "feature_type": "continuous",
            },
            {
                "feature_name": "solar_capacity_kw",
                "feature_role": "decision",
                "feature_type": "continuous",
            },
        ],
        "series_field_schema": {
            "ghi": {
                "source_field": "global_horizontal_irradiance_w_per_m2",
                "column_prefix": "ghi",
            },
            "load": {
                "source_field": "site_electric_load_kw",
                "column_prefix": "load",
            },
            "unmet_load": {
                "source_field": "unmet_load_kw",
                "column_prefix": "unmet_load",
            },
        },
        "target_metadata": {
            "target_name": "shortfall",
            "event_target_name": "shortfall_exceeds_threshold",
            "numerator_source_field": "unmet_load_kw",
            "denominator_source_field": "site_electric_load_kw",
            "aggregation_rule": "sum(unmet_load_kw * timestep_hours) / sum(site_electric_load_kw * timestep_hours)",
            "threshold_default": 0.05,
            "event_threshold_source": "threshold_default",
            "event_threshold_comparison": ">",
            "supported_query_mode": "exceedance-probability",
        },
        "provenance": {
            "family_id": "weather-family:f7dbcc3a131d|demand-family:91a2f195442c|local-electric",
            "weather_family_id": "weather-family:f7dbcc3a131d",
            "dataset_fixture_path": "tests/fixtures/planning/planning_dataset_export_case.json",
            "family_seed": 13,
            "created_from_fixture": True,
        },
        "export_configuration": {
            "row_order_policy": "scenario_index_ascending",
            "flattened_series_fields": [
                "global_horizontal_irradiance_w_per_m2",
                "site_electric_load_kw",
                "unmet_load_kw",
            ],
            "include_provenance": True,
            "numeric_tolerance": 1e-9,
        },
    }


def test_supported_planning_dataset_versions_reserve_v1() -> None:
    assert SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS == ("v1",)


def test_planning_dataset_artifact_preserves_minimal_identity_fields() -> None:
    artifact = PlanningDatasetArtifact(
        dataset_id="planning-dataset-unit",
        schema_version="v1",
        column_order=("scenario_index", "ghi_0", "shortfall", "shortfall_exceeds_threshold"),
        provenance={"family_id": "fixture-family"},
    )

    assert artifact.dataset_id == "planning-dataset-unit"
    assert artifact.schema_version == "v1"
    assert artifact.column_order == (
        "scenario_index",
        "ghi_0",
        "shortfall",
        "shortfall_exceeds_threshold",
    )
    assert artifact.provenance["family_id"] == "fixture-family"


def test_planning_dataset_to_dict_uses_top_level_rows_payload_shape() -> None:
    artifact = load_planning_dataset(_dataset_payload())

    payload = artifact.to_dict()

    assert tuple(payload) == PLANNING_DATASET_REQUIRED_KEYS
    assert isinstance(payload["rows"], list)
    assert isinstance(payload["rows"][0], dict)
    assert "table" not in payload
    assert "metadata" not in payload


def test_planning_dataset_write_json_round_trips_without_prewrapped_payload(tmp_path) -> None:
    payload = _dataset_payload()
    payload["created_at"] = ""

    artifact = PlanningDatasetArtifact(
        dataset_id=str(payload["dataset_id"]),
        schema_version=str(payload["schema_version"]),
        created_at=str(payload["created_at"]),
        row_count=int(payload["row_count"]),
        horizon_steps=int(payload["horizon_steps"]),
        timestep_hours=float(payload["timestep_hours"]),
        column_order=tuple(payload["column_order"]),
        rows=tuple(payload["rows"]),
        design_feature_schema=tuple(payload["design_feature_schema"]),
        series_field_schema=dict(payload["series_field_schema"]),
        target_metadata=dict(payload["target_metadata"]),
        provenance=dict(payload["provenance"]),
        export_configuration=dict(payload["export_configuration"]),
    )
    dataset_path = tmp_path / "planning_dataset_v1.json"

    artifact.write_json(dataset_path)
    persisted_payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    loaded = load_planning_dataset(dataset_path)

    assert tuple(persisted_payload) == PLANNING_DATASET_REQUIRED_KEYS
    assert persisted_payload["created_at"]
    assert "table" not in persisted_payload
    assert "metadata" not in persisted_payload
    assert loaded.dataset_id == artifact.dataset_id
    assert loaded.created_at == persisted_payload["created_at"]


def test_load_planning_dataset_rejects_unsupported_schema_version() -> None:
    payload = _dataset_payload()
    payload["schema_version"] = "v9"

    with pytest.raises(UnsupportedPlanningDatasetVersionError, match="unsupported|version"):
        load_planning_dataset(payload)


def test_load_planning_dataset_rejects_wrapped_tabular_payload_shape() -> None:
    wrapped_payload = {
        "metadata": {
            key: value
            for key, value in _dataset_payload().items()
            if key != "rows"
        },
        "table": {
            "rows": _dataset_payload()["rows"],
        },
    }

    with pytest.raises(ValueError, match="top level|wrapped|rows directly"):
        load_planning_dataset(wrapped_payload)


def test_load_planning_dataset_preserves_row_and_column_order(tmp_path) -> None:
    payload = _dataset_payload()
    dataset_path = tmp_path / "planning_dataset_v1.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_planning_dataset(dataset_path)

    assert loaded.column_order == tuple(payload["column_order"])
    assert [row["scenario_index"] for row in loaded.rows] == [0, 1]
    assert loaded.row_count == 2
    assert loaded.horizon_steps == 3


def test_load_planning_dataset_preserves_shortfall_energy_ratio_metadata() -> None:
    loaded = load_planning_dataset(_dataset_payload())

    assert loaded.target_metadata["target_name"] == "shortfall"
    assert loaded.target_metadata["event_target_name"] == "shortfall_exceeds_threshold"
    assert loaded.target_metadata["numerator_source_field"] == "unmet_load_kw"
    assert loaded.target_metadata["denominator_source_field"] == "site_electric_load_kw"
    assert "timestep_hours" in loaded.target_metadata["aggregation_rule"]
    assert loaded.rows[0]["shortfall"] == pytest.approx(0.05)
    assert loaded.rows[1]["shortfall"] == pytest.approx(1.0 / 45.0)
    assert loaded.rows[0]["shortfall_exceeds_threshold"] == 0


def test_load_planning_dataset_preserves_export_reproducibility_metadata() -> None:
    payload = deepcopy(_dataset_payload())

    loaded = load_planning_dataset(payload)

    assert loaded.provenance["family_seed"] == 13
    assert loaded.provenance["created_from_fixture"] is True
    assert loaded.export_configuration["row_order_policy"] == "scenario_index_ascending"
    assert loaded.export_configuration["flattened_series_fields"] == [
        "global_horizontal_irradiance_w_per_m2",
        "site_electric_load_kw",
        "unmet_load_kw",
    ]
    assert loaded.export_configuration["numeric_tolerance"] == pytest.approx(1e-9)
