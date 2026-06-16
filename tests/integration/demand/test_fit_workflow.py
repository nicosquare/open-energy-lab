"""Integration coverage for the aligned-history demand fit workflow."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import pytest

import open_energy_lab.demand.artifact as demand_artifact_module
import open_energy_lab.demand.fit as demand_fit_module
from open_energy_lab.weather._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    LOCAL_CIVIL_TIME_BASIS,
)


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _fit_demand_model(training_payload: dict[str, object], *, output_path: Path) -> object:
    try:
        fit = demand_fit_module.fit_demand_model
    except AttributeError:
        pytest.fail("open_energy_lab.demand.fit.fit_demand_model is not implemented")
    return fit(training_payload, output_path=output_path)


def _load_demand_artifact(
    source: Path,
    *,
    expected_timestep_hours: float,
) -> object:
    try:
        load = demand_artifact_module.load_demand_artifact
    except AttributeError:
        pytest.fail(
            "open_energy_lab.demand.artifact.load_demand_artifact is not implemented"
        )
    return load(source, expected_timestep_hours=expected_timestep_hours)


def _aligned_training_payload() -> dict[str, object]:
    return {
        "dataset_id": "aligned-demand:phoenix-daily",
        "timezone_name": "America/Phoenix",
        "time_basis": LOCAL_CIVIL_TIME_BASIS,
        "timestep_hours": 24.0,
        "timestamp_utc": [
            "2024-07-01T07:00:00Z",
            "2024-07-02T07:00:00Z",
            "2024-07-03T07:00:00Z",
        ],
        "local_civil_step_labels": [
            "2024-07-01T00:00:00-07:00",
            "2024-07-02T00:00:00-07:00",
            "2024-07-03T00:00:00-07:00",
        ],
        "canonical_weather_fields": list(CANONICAL_WEATHER_FIELD_ORDER[1:]),
        "weather_field_series": {
            "dry_bulb_air_temperature_c": [39.0, 41.5, 37.0],
            "global_horizontal_irradiance_w_per_m2": [910.0, 935.0, 880.0],
            "direct_beam_irradiance_w_per_m2": [640.0, 655.0, 620.0],
            "diffuse_horizontal_irradiance_w_per_m2": [120.0, 126.0, 118.0],
            "relative_humidity_pct": [18.0, 22.0, 20.0],
            "infrared_radiation_downwards_w_per_m2": [355.0, 360.0, 350.0],
            "windspeed_10m_m_per_s": [3.0, 3.5, 2.8],
            "wind_direction_10m_deg": [180.0, 195.0, 205.0],
            "surface_air_pressure_pa": [100850.0, 100790.0, 100900.0],
        },
        "non_thermal_electric_demand_kw": [48.0, 50.5, 46.0],
        "cooling_demand_rt": [11.0, 13.5, 9.5],
        "provenance": {
            "origin": "integration-test",
            "generation_command": None,
        },
    }


def test_fit_demand_model_persists_and_reloads_offline(tmp_path: Path) -> None:
    artifact_path = tmp_path / "fitted-demand-artifact.json"

    artifact = _fit_demand_model(_aligned_training_payload(), output_path=artifact_path)
    persisted_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    reloaded = _load_demand_artifact(artifact_path, expected_timestep_hours=24.0)

    assert artifact_path.is_file()
    assert _field(artifact, "artifact_id") == _field(reloaded, "artifact_id")
    assert persisted_payload["schema_version"] == "v1"
    assert persisted_payload["feature_name"] == "008-weather-demand-modeling"
    assert persisted_payload["provenance"]["origin"] == "integration-test"
    assert tuple(_field(reloaded, "required_weather_field_order"))
    assert _field(reloaded, "double_counting_policy")
    assert _field(reloaded, "training_record_summary")["record_count"] == 3


@pytest.mark.parametrize(
    ("mutator", "match_text"),
    (
        (
            lambda payload: payload.pop("cooling_demand_rt"),
            "cooling_demand_rt",
        ),
        (
            lambda payload: payload.pop("non_thermal_electric_demand_kw"),
            "non_thermal_electric_demand_kw",
        ),
        (
            lambda payload: payload["timestamp_utc"].__setitem__(
                1,
                "2024-07-02T01:00:00Z",
            ),
            "timestep|align",
        ),
    ),
)
def test_fit_demand_model_fails_fast_on_invalid_aligned_inputs(
    tmp_path: Path,
    mutator,
    match_text: str,
) -> None:
    artifact_path = tmp_path / "should-not-exist.json"
    payload = deepcopy(_aligned_training_payload())
    mutator(payload)

    with pytest.raises(ValueError, match=match_text):
        _fit_demand_model(payload, output_path=artifact_path)

    assert not artifact_path.exists()
