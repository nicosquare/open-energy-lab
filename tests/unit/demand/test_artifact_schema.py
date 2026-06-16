"""Unit coverage for demand artifact schema and loading rules."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

import pytest

import open_energy_lab.demand.artifact as demand_artifact_module
from open_energy_lab.weather._canonical import LOCAL_CIVIL_TIME_BASIS


REQUIRED_WEATHER_FIELD_ORDER = (
    "dry_bulb_air_temperature_c",
    "relative_humidity_pct",
    "global_horizontal_irradiance_w_per_m2",
)


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _load_demand_artifact(
    source: object,
    *,
    expected_timestep_hours: float | None = None,
) -> object:
    try:
        load = demand_artifact_module.load_demand_artifact
    except AttributeError:
        pytest.fail(
            "open_energy_lab.demand.artifact.load_demand_artifact is not implemented"
        )
    return load(source, expected_timestep_hours=expected_timestep_hours)


def _unsupported_version_error_type() -> type[Exception]:
    try:
        error_type = demand_artifact_module.UnsupportedDemandArtifactVersionError
    except AttributeError:
        pytest.fail(
            "open_energy_lab.demand.artifact.UnsupportedDemandArtifactVersionError "
            "is not implemented"
        )
    return error_type


def _artifact_payload() -> dict[str, object]:
    return {
        "artifact_id": "demand-artifact:aligned-demand:phoenix-daily",
        "schema_version": "v1",
        "feature_name": "008-weather-demand-modeling",
        "created_at": "2026-06-15T00:00:00Z",
        "timezone_name": "America/Phoenix",
        "time_basis": LOCAL_CIVIL_TIME_BASIS,
        "timestep_hours": 24.0,
        "required_weather_field_order": list(REQUIRED_WEATHER_FIELD_ORDER),
        "training_record_summary": {
            "dataset_id": "aligned-demand:phoenix-daily",
            "record_count": 3,
            "first_timestamp_utc": "2024-07-01T07:00:00Z",
            "last_timestamp_utc": "2024-07-03T07:00:00Z",
            "local_step_count": 3,
        },
        "non_thermal_electric_model": {
            "model_kind": "local-civil-baseline",
            "local_step_baseline_kw": [48.0],
            "weather_response_terms": {
                "dry_bulb_air_temperature_c": 0.75,
                "relative_humidity_pct": 0.05,
                "global_horizontal_irradiance_w_per_m2": 0.002,
            },
            "training_day_count": 3,
            "residual_scale_summary": {
                "mae_kw": 1.2,
                "max_abs_error_kw": 2.4,
            },
            "supported_weather_drivers": list(REQUIRED_WEATHER_FIELD_ORDER),
        },
        "cooling_demand_model": {
            "model_kind": "local-civil-baseline",
            "local_step_baseline_rt": [11.0],
            "weather_response_terms": {
                "dry_bulb_air_temperature_c": 0.5,
                "relative_humidity_pct": 0.03,
                "global_horizontal_irradiance_w_per_m2": 0.001,
            },
            "training_day_count": 3,
            "residual_scale_summary": {
                "mae_rt": 0.8,
                "max_abs_error_rt": 1.5,
            },
            "supported_weather_drivers": list(REQUIRED_WEATHER_FIELD_ORDER),
            "explicit_training_requirement": "historical_cooling_demand_rt_required",
        },
        "shared_residual_model": {
            "model_kind": "gaussian-copula",
            "intervals_per_day": 1,
            "output_order": [
                "non_thermal_electric_demand_kw",
                "cooling_demand_rt",
            ],
            "joint_residual_summary": {
                "training_day_count": 3,
                "output_count": 2,
            },
            "correlation_matrix": [
                [1.0, 0.35],
                [0.35, 1.0],
            ],
            "sampling_notes": "unit-test artifact",
        },
        "double_counting_policy": (
            "explicit_cooling_separate_from_non_thermal_electric"
        ),
        "provenance": {
            "training_dataset_id": "aligned-demand:phoenix-daily",
            "fit_notes": ["unit-test"],
            "legacy_evidence_paths": [
                "legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb",
            ],
        },
        "supported_sampling_modes": ["offline"],
    }


def test_load_demand_artifact_preserves_schema_and_provenance_metadata() -> None:
    artifact = _load_demand_artifact(_artifact_payload(), expected_timestep_hours=24.0)

    assert _field(artifact, "schema_version") == "v1"
    assert _field(artifact, "feature_name") == "008-weather-demand-modeling"
    assert _field(artifact, "time_basis") == LOCAL_CIVIL_TIME_BASIS
    assert _field(artifact, "timestep_hours") == pytest.approx(24.0)
    assert tuple(_field(artifact, "required_weather_field_order")) == REQUIRED_WEATHER_FIELD_ORDER
    assert _field(artifact, "double_counting_policy") == (
        "explicit_cooling_separate_from_non_thermal_electric"
    )

    training_record_summary = _field(artifact, "training_record_summary")
    provenance = _field(artifact, "provenance")
    assert isinstance(training_record_summary, Mapping)
    assert isinstance(provenance, Mapping)
    assert training_record_summary["record_count"] == 3
    assert provenance["training_dataset_id"] == "aligned-demand:phoenix-daily"

    assert tuple(_field(artifact, "supported_sampling_modes")) == ("offline",)


def test_load_demand_artifact_enforces_timestep_lock() -> None:
    with pytest.raises(ValueError, match="expected artifact timestep_hours 12"):
        _load_demand_artifact(_artifact_payload(), expected_timestep_hours=12.0)


def test_load_demand_artifact_rejects_unsupported_versions() -> None:
    payload = deepcopy(_artifact_payload())
    payload["schema_version"] = "v999"

    with pytest.raises(
        _unsupported_version_error_type(),
        match="unsupported demand artifact schema_version 'v999'",
    ):
        _load_demand_artifact(payload)


def test_load_demand_artifact_rejects_missing_required_schema_keys() -> None:
    payload = deepcopy(_artifact_payload())
    payload.pop("double_counting_policy")

    with pytest.raises(
        ValueError,
        match="demand artifact is missing required keys: double_counting_policy",
    ):
        _load_demand_artifact(payload)
