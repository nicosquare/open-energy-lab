from __future__ import annotations

from pathlib import Path

import pytest

import open_energy_lab.weather.tmy as tmy_module
from open_energy_lab.weather.fit import WeatherFitConfig, fit_weather_dataset
from open_energy_lab.weather.tmy import (
    DEFAULT_PVGIS_TMY_ENDPOINT,
    PVGISTMYRequestConfig,
    WeatherCacheUnavailableError,
    load_or_fetch_tmy_dataset,
)
from tests.integration.weather.fixture_utils import (
    RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH,
    load_weather_fixture,
)


def test_pvgis_53_configuration_is_explicit_and_forwarded(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakePVGIS:
        class iotools:
            @staticmethod
            def get_pvgis_tmy(latitude, longitude, **kwargs):
                calls.append({"latitude": latitude, "longitude": longitude, **kwargs})
                return load_weather_fixture(RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH)

    monkeypatch.setattr(tmy_module, "_import_pvlib", lambda: FakePVGIS)
    config = PVGISTMYRequestConfig(
        endpoint_url=DEFAULT_PVGIS_TMY_ENDPOINT,
        use_horizon=False,
        start_year=2008,
        end_year=2020,
        timeout_seconds=17,
    )

    result = tmy_module.fetch_tmy_dataset(
        24.4539,
        54.3773,
        timezone_name="Asia/Dubai",
        api_config=config,
    )

    assert result.source_metadata["pvgis_request"]["endpoint_url"].endswith(
        "/api/v5_3/"
    )
    assert calls == [
        {
            "latitude": 24.4539,
            "longitude": 54.3773,
            "outputformat": "json",
            "usehorizon": False,
            "startyear": 2008,
            "endyear": 2020,
            "map_variables": True,
            "url": DEFAULT_PVGIS_TMY_ENDPOINT,
            "timeout": 17,
        }
    ]


def test_canonical_cache_prevents_a_second_fetch_and_can_be_fitted(tmp_path) -> None:
    calls = 0

    def fetcher(latitude: float, longitude: float):
        nonlocal calls
        calls += 1
        return load_weather_fixture(RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH)

    cache_path = tmp_path / "abu-dhabi-tmy.json"
    first = load_or_fetch_tmy_dataset(
        24.4539,
        54.3773,
        timezone_name="Asia/Dubai",
        cache_path=cache_path,
        fetcher=fetcher,
    )
    second = load_or_fetch_tmy_dataset(
        24.4539,
        54.3773,
        timezone_name="Asia/Dubai",
        cache_path=cache_path,
        allow_network=False,
    )
    artifact = fit_weather_dataset(
        second,
        fit_config=WeatherFitConfig(timestep_hours=second.timestep_hours),
    )

    assert calls == 1
    assert first.field_series == second.field_series
    assert first.dataset_id == second.dataset_id
    assert second.source_metadata["cache_provenance"]["status"] == "hit"
    assert artifact.training_record_summary["dataset_id"] == second.dataset_id
    assert artifact.provenance["source_metadata"]["cache_provenance"]["status"] == "hit"


def test_missing_cache_with_network_disabled_fails_clearly(tmp_path) -> None:
    cache_path = tmp_path / "missing.json"

    with pytest.raises(WeatherCacheUnavailableError, match="network access is disabled"):
        load_or_fetch_tmy_dataset(
            24.4539,
            54.3773,
            timezone_name="Asia/Dubai",
            cache_path=cache_path,
            allow_network=False,
        )

    assert not cache_path.exists()


def test_pvgis_years_must_be_supplied_as_a_pair() -> None:
    with pytest.raises(ValueError, match="start_year and end_year"):
        PVGISTMYRequestConfig(start_year=2010)
