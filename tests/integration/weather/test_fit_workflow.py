"""Integration coverage for the recorded fit-to-artifact workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_energy_lab.weather._canonical import MissingCanonicalWeatherFieldError
from open_energy_lab.weather.artifact import load_weather_artifact
from open_energy_lab.weather.fit import WeatherFitConfig, fit_weather_model
from open_energy_lab.weather.tmy import WeatherLocationUnavailableError
from tests.integration.weather.fixture_utils import (
    LOCATION_UNAVAILABLE_RESPONSE_FIXTURE_PATH,
    MISSING_REQUIRED_FIELD_RESPONSE_FIXTURE_PATH,
    RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH,
    load_weather_fixture,
)


def test_recorded_fit_workflow_persists_and_reloads_offline(tmp_path: Path) -> None:
    artifact_path = tmp_path / "fitted-weather-artifact.json"
    fetch_calls = 0

    def fetcher(latitude: float, longitude: float) -> dict[str, object]:
        nonlocal fetch_calls
        fetch_calls += 1
        assert latitude == pytest.approx(33.4484)
        assert longitude == pytest.approx(-112.0740)
        return load_weather_fixture(RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH)

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
    with pytest.raises(
        MissingCanonicalWeatherFieldError,
        match="direct_beam_irradiance_w_per_m2",
    ):
        fit_weather_model(
            33.4484,
            -112.0740,
            recorded_response=load_weather_fixture(
                MISSING_REQUIRED_FIELD_RESPONSE_FIXTURE_PATH
            ),
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
            recorded_response=load_weather_fixture(
                LOCATION_UNAVAILABLE_RESPONSE_FIXTURE_PATH
            ),
            fit_config=WeatherFitConfig(timestep_hours=1.0),
        )
