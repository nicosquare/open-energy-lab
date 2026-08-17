"""Unit coverage for aligned demand-history normalization contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy

import pytest

import open_energy_lab.demand._aligned_history as aligned_history_module
from open_energy_lab.weather._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    LOCAL_CIVIL_TIME_BASIS,
)


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _normalize_aligned_training_history(payload: dict[str, object]) -> object:
    try:
        normalize = aligned_history_module.normalize_aligned_training_history
    except AttributeError:
        pytest.fail(
            "open_energy_lab.demand._aligned_history.normalize_aligned_training_history "
            "is not implemented"
        )
    return normalize(payload)


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
            "origin": "unit-test",
            "generation_command": None,
        },
    }


def test_normalize_aligned_training_history_preserves_time_grid_and_outputs() -> None:
    dataset = _normalize_aligned_training_history(_aligned_training_payload())

    assert _field(dataset, "dataset_id") == "aligned-demand:phoenix-daily"
    assert _field(dataset, "time_basis") == LOCAL_CIVIL_TIME_BASIS
    assert _field(dataset, "timestep_hours") == pytest.approx(24.0)
    assert tuple(_field(dataset, "timestamp_utc")) == (
        "2024-07-01T07:00:00Z",
        "2024-07-02T07:00:00Z",
        "2024-07-03T07:00:00Z",
    )
    assert tuple(_field(dataset, "local_civil_step_labels")) == (
        "2024-07-01T00:00:00-07:00",
        "2024-07-02T00:00:00-07:00",
        "2024-07-03T00:00:00-07:00",
    )
    assert tuple(_field(dataset, "canonical_weather_fields")) == CANONICAL_WEATHER_FIELD_ORDER[1:]

    weather_field_series = _field(dataset, "weather_field_series")
    assert isinstance(weather_field_series, Mapping)
    assert tuple(weather_field_series) == CANONICAL_WEATHER_FIELD_ORDER[1:]
    assert tuple(weather_field_series["dry_bulb_air_temperature_c"]) == (39.0, 41.5, 37.0)
    assert tuple(weather_field_series["relative_humidity_pct"]) == (18.0, 22.0, 20.0)

    non_thermal_electric = _field(dataset, "non_thermal_electric_demand_kw")
    cooling_demand = _field(dataset, "cooling_demand_rt")
    assert isinstance(non_thermal_electric, Sequence)
    assert isinstance(cooling_demand, Sequence)
    assert tuple(non_thermal_electric) == (48.0, 50.5, 46.0)
    assert tuple(cooling_demand) == (11.0, 13.5, 9.5)


def test_normalize_aligned_training_history_rejects_declared_timestep_mismatch() -> None:
    payload = deepcopy(_aligned_training_payload())
    payload["timestamp_utc"] = [
        "2024-07-01T07:00:00Z",
        "2024-07-02T01:00:00Z",
        "2024-07-03T07:00:00Z",
    ]
    payload["local_civil_step_labels"] = [
        "2024-07-01T00:00:00-07:00",
        "2024-07-01T18:00:00-07:00",
        "2024-07-03T00:00:00-07:00",
    ]

    with pytest.raises(ValueError, match="timestep|align"):
        _normalize_aligned_training_history(payload)


def test_normalize_aligned_training_history_requires_explicit_cooling_history() -> None:
    payload = deepcopy(_aligned_training_payload())
    payload.pop("cooling_demand_rt")

    with pytest.raises(ValueError, match="cooling_demand_rt"):
        _normalize_aligned_training_history(payload)


def test_normalize_aligned_training_history_requires_non_thermal_history() -> None:
    payload = deepcopy(_aligned_training_payload())
    payload.pop("non_thermal_electric_demand_kw")

    with pytest.raises(ValueError, match="non_thermal_electric_demand_kw"):
        _normalize_aligned_training_history(payload)


def test_normalize_aligned_training_history_rejects_ambiguous_total_electric_inputs() -> None:
    payload = deepcopy(_aligned_training_payload())
    payload["total_electric_demand_kw"] = [59.0, 65.0, 58.0]

    with pytest.raises(ValueError, match="double count|total_electric_demand_kw"):
        _normalize_aligned_training_history(payload)
