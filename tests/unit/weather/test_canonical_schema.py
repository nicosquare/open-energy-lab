"""Unit coverage for canonical weather normalization contracts."""

from __future__ import annotations

import pytest

from open_energy_lab.weather._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    LOCAL_CIVIL_TIME_BASIS,
    MissingCanonicalWeatherFieldError,
    SOURCE_FIELD_LABELS,
    normalize_recorded_tmy_response,
)


def _recorded_tmy_response() -> dict[str, object]:
    return {
        "source_name": "PVGIS TMY",
        "timezone_name": "America/Phoenix",
        "source_metadata": {
            "provider": "pvgis",
            "dataset_year": 2020,
            "resolution_hours": 1.0,
        },
        "records": [
            {
                "Date & time (UTC)": "2024-01-01T00:00:00Z",
                "T2m [°C]": 8.0,
                "G(h) [W/m2]": 0.0,
                "Gb(n) [W/m2]": 0.0,
                "Gd(h) [W/m2]": 0.0,
                "RH [%]": 45.0,
                "IR(h) [W/m2]": 280.0,
                "WS10m [m/s]": 2.1,
                "WD10m [°]": 90.0,
                "SP [Pa]": 101325.0,
            },
            {
                "Date & time (UTC)": "2024-01-01T01:00:00Z",
                "T2m [°C]": 9.0,
                "G(h) [W/m2]": 10.0,
                "Gb(n) [W/m2]": 4.0,
                "Gd(h) [W/m2]": 6.0,
                "RH [%]": 42.0,
                "IR(h) [W/m2]": 281.0,
                "WS10m [m/s]": 2.4,
                "WD10m [°]": 95.0,
                "SP [Pa]": 101300.0,
            },
            {
                "Date & time (UTC)": "2024-01-01T02:00:00Z",
                "T2m [°C]": 11.0,
                "G(h) [W/m2]": 30.0,
                "Gb(n) [W/m2]": 12.0,
                "Gd(h) [W/m2]": 18.0,
                "RH [%]": 39.0,
                "IR(h) [W/m2]": 282.0,
                "WS10m [m/s]": 2.8,
                "WD10m [°]": 100.0,
                "SP [Pa]": 101280.0,
            },
        ],
    }


def test_canonical_weather_field_order_matches_first_release_contract() -> None:
    assert CANONICAL_WEATHER_FIELD_ORDER == (
        "timestamp_utc",
        "dry_bulb_air_temperature_c",
        "global_horizontal_irradiance_w_per_m2",
        "direct_beam_irradiance_w_per_m2",
        "diffuse_horizontal_irradiance_w_per_m2",
        "relative_humidity_pct",
        "infrared_radiation_downwards_w_per_m2",
        "windspeed_10m_m_per_s",
        "wind_direction_10m_deg",
        "surface_air_pressure_pa",
    )


def test_normalize_recorded_tmy_response_covers_full_schema_and_local_time() -> None:
    dataset = normalize_recorded_tmy_response(
        _recorded_tmy_response(),
        latitude=33.4484,
        longitude=-112.0740,
        timezone_name="America/Phoenix",
    )

    assert dataset.time_basis == LOCAL_CIVIL_TIME_BASIS
    assert dataset.timestep_hours == pytest.approx(1.0)
    assert dataset.canonical_field_order == CANONICAL_WEATHER_FIELD_ORDER
    assert dataset.timestamp_utc == (
        "2024-01-01T00:00:00Z",
        "2024-01-01T01:00:00Z",
        "2024-01-01T02:00:00Z",
    )
    assert dataset.local_civil_step_labels == (
        "2023-12-31T17:00:00-07:00",
        "2023-12-31T18:00:00-07:00",
        "2023-12-31T19:00:00-07:00",
    )
    assert dataset.field_series["global_horizontal_irradiance_w_per_m2"] == (
        0.0,
        10.0,
        30.0,
    )
    assert dataset.field_series["surface_air_pressure_pa"] == (
        101325.0,
        101300.0,
        101280.0,
    )
    assert dataset.source_field_labels == SOURCE_FIELD_LABELS
    assert dataset.source_metadata["provider"] == "pvgis"


def test_normalize_recorded_tmy_response_fails_fast_on_missing_field() -> None:
    response = _recorded_tmy_response()
    records = response["records"]
    assert isinstance(records, list)
    first_record = dict(records[0])
    first_record.pop("RH [%]")
    response["records"] = [first_record, *records[1:]]

    with pytest.raises(
        MissingCanonicalWeatherFieldError,
        match="relative_humidity_pct",
    ):
        normalize_recorded_tmy_response(
            response,
            latitude=33.4484,
            longitude=-112.0740,
            timezone_name="America/Phoenix",
        )
