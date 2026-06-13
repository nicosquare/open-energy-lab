"""Integration coverage for the recorded fit-to-artifact workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_energy_lab.weather._canonical import MissingCanonicalWeatherFieldError
from open_energy_lab.weather.artifact import load_weather_artifact
from open_energy_lab.weather.fit import WeatherFitConfig, fit_weather_model
from open_energy_lab.weather.tmy import WeatherLocationUnavailableError


def _recorded_tmy_response() -> dict[str, object]:
    return {
        "source_name": "PVGIS TMY",
        "timezone_name": "America/Phoenix",
        "source_metadata": {
            "provider": "pvgis",
            "dataset_year": 2020,
            "fixture_kind": "recorded-test-response",
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


def _location_unavailable_response() -> dict[str, object]:
    return {
        "source_name": "PVGIS TMY",
        "timezone_name": "America/Phoenix",
        "status": "location-unavailable",
        "available": False,
        "error": "the requested coordinates are outside the supported coverage envelope",
        "records": [],
    }


def test_recorded_fit_workflow_persists_and_reloads_offline(tmp_path: Path) -> None:
    artifact_path = tmp_path / "fitted-weather-artifact.json"
    fetch_calls = 0

    def fetcher(latitude: float, longitude: float) -> dict[str, object]:
        nonlocal fetch_calls
        fetch_calls += 1
        assert latitude == pytest.approx(33.4484)
        assert longitude == pytest.approx(-112.0740)
        return _recorded_tmy_response()

    artifact = fit_weather_model(
        33.4484,
        -112.0740,
        fetcher=fetcher,
        fit_config=WeatherFitConfig(timestep_hours=1.0, notes=("integration-test",)),
        output_path=artifact_path,
    )
    reloaded = load_weather_artifact(artifact_path, expected_timestep_hours=1.0)

    assert fetch_calls == 1
    assert artifact_path.is_file()
    assert reloaded.artifact_id == artifact.artifact_id
    assert reloaded.provenance["source_metadata"]["fixture_kind"] == "recorded-test-response"
    assert reloaded.training_record_summary["record_count"] == 3


def test_fit_weather_model_fails_fast_on_missing_canonical_fields() -> None:
    response = _recorded_tmy_response()
    records = response["records"]
    assert isinstance(records, list)
    second_record = dict(records[1])
    second_record.pop("Gb(n) [W/m2]")
    response["records"] = [records[0], second_record, records[2]]

    with pytest.raises(
        MissingCanonicalWeatherFieldError,
        match="direct_beam_irradiance_w_per_m2",
    ):
        fit_weather_model(
            33.4484,
            -112.0740,
            recorded_response=response,
            fit_config=WeatherFitConfig(timestep_hours=1.0),
        )


def test_fit_weather_model_rejects_syntactically_valid_unavailable_locations() -> None:
    with pytest.raises(
        WeatherLocationUnavailableError,
        match="unable to serve location",
    ):
        fit_weather_model(
            33.4484,
            -112.0740,
            recorded_response=_location_unavailable_response(),
            fit_config=WeatherFitConfig(timestep_hours=1.0),
        )
