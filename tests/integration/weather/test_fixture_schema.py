"""Schema checks for stochastic-weather fixtures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

from open_energy_lab.weather import WeatherSamplingRequest
from open_energy_lab.weather.artifact import (
    UnsupportedWeatherArtifactVersionError,
    load_weather_artifact,
)
from tests.integration.weather.fixture_utils import (
    COMMON_TOP_LEVEL_KEYS,
    FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
    LOCATION_UNAVAILABLE_RESPONSE_FIXTURE_PATH,
    MISSING_REQUIRED_FIELD_RESPONSE_FIXTURE_PATH,
    RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH,
    SAMPLED_WEATHER_FAMILY_FIXTURE_PATH,
    SAMPLING_REQUEST_FIXTURE_PATH,
    UNSUPPORTED_WEATHER_ARTIFACT_FIXTURE_PATH,
    WEATHER_FIXTURE_PATHS,
    load_all_weather_fixtures,
)


def _normalize(value: object) -> object:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Mapping):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    return value


def _fixture_payload(fixture_path: Path) -> dict[str, object]:
    fixture_data = next(
        data for path, data in load_all_weather_fixtures() if path == fixture_path
    )
    return {
        key: value for key, value in fixture_data.items() if key not in COMMON_TOP_LEVEL_KEYS
    }


@pytest.mark.parametrize(
    ("fixture_path", "fixture_data"),
    load_all_weather_fixtures(),
    ids=lambda item: item.name if isinstance(item, Path) else repr(item),
)
def test_weather_fixture_common_schema(
    fixture_path: Path,
    fixture_data: dict[str, object],
) -> None:
    missing_top_level_keys = [
        key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data
    ]
    assert missing_top_level_keys == []
    assert fixture_path in WEATHER_FIXTURE_PATHS
    assert fixture_data["fixture_status"] in {"scaffold", "active"}
    assert fixture_data["fixture_path"] == fixture_path.as_posix()
    assert isinstance(fixture_data["purpose"], str) and fixture_data["purpose"]
    assert isinstance(fixture_data["origin"], str) and fixture_data["origin"]

    legacy_reference_paths = fixture_data["legacy_reference_paths"]
    assert isinstance(legacy_reference_paths, list)
    assert legacy_reference_paths != []
    for legacy_path in legacy_reference_paths:
        assert isinstance(legacy_path, str)
        assert legacy_path.startswith("legacy/")
        assert Path(legacy_path).is_file()

    notes = fixture_data["notes"]
    assert isinstance(notes, list)
    assert notes != []
    assert all(isinstance(note, str) and note for note in notes)


@pytest.mark.parametrize(
    ("fixture_path", "expected_source_service"),
    (
        (RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH, "PVGIS TMY"),
        (MISSING_REQUIRED_FIELD_RESPONSE_FIXTURE_PATH, "PVGIS TMY"),
        (LOCATION_UNAVAILABLE_RESPONSE_FIXTURE_PATH, "PVGIS TMY"),
    ),
)
def test_weather_provider_response_fixture_schema(
    fixture_path: Path,
    expected_source_service: str,
) -> None:
    fixture_data = next(
        data for path, data in load_all_weather_fixtures() if path == fixture_path
    )

    assert fixture_data["source_service"] == expected_source_service
    assert "schema_version" not in fixture_data


@pytest.mark.parametrize(
    ("fixture_path", "expected_schema_version"),
    (
        (FITTED_WEATHER_ARTIFACT_FIXTURE_PATH, "v1"),
        (UNSUPPORTED_WEATHER_ARTIFACT_FIXTURE_PATH, "v999"),
    ),
)
def test_weather_artifact_fixture_schema(
    fixture_path: Path,
    expected_schema_version: str,
) -> None:
    fixture_data = _fixture_payload(fixture_path)

    assert fixture_data["schema_version"] == expected_schema_version
    assert "source_service" not in fixture_data


def test_weather_sampling_request_fixture_schema() -> None:
    fixture_data = _fixture_payload(SAMPLING_REQUEST_FIXTURE_PATH)

    assert fixture_data["artifact_fixture_path"] == FITTED_WEATHER_ARTIFACT_FIXTURE_PATH.as_posix()
    assert fixture_data["expected_timestep_hours"] == pytest.approx(24.0)
    assert fixture_data["num_steps"] == 3
    assert fixture_data["scenario_count"] == 2
    assert fixture_data["family_seed"] == 13


def test_sampled_weather_family_fixture_schema() -> None:
    fixture_data = _fixture_payload(SAMPLED_WEATHER_FAMILY_FIXTURE_PATH)

    assert fixture_data["artifact_reference"] == "weather-artifact:synthetic-us1-daily"
    assert fixture_data["family_seed"] == 13
    assert fixture_data["num_steps"] == 3
    assert fixture_data["scenario_count"] == 2
    assert fixture_data["timestep_hours"] == pytest.approx(24.0)
    assert len(fixture_data["sampled_traces"]) == fixture_data["scenario_count"]


def test_supported_weather_artifact_fixture_loads_offline() -> None:
    fixture_data = _fixture_payload(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH)

    artifact = load_weather_artifact(fixture_data, expected_timestep_hours=24.0)

    assert artifact.artifact_id == "weather-artifact:synthetic-us1-daily"
    assert artifact.training_record_summary["record_count"] == 2


def test_sampling_request_fixture_replays_the_committed_sampled_family() -> None:
    artifact = load_weather_artifact(
        _fixture_payload(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )
    request_fixture = _fixture_payload(SAMPLING_REQUEST_FIXTURE_PATH)
    expected_family = _fixture_payload(SAMPLED_WEATHER_FAMILY_FIXTURE_PATH)

    sampled_family = artifact.sample_family(
        request=WeatherSamplingRequest(
            num_steps=int(request_fixture["num_steps"]),
            scenario_count=int(request_fixture["scenario_count"]),
            family_seed=int(request_fixture["family_seed"]),
        ),
        expected_timestep_hours=float(request_fixture["expected_timestep_hours"]),
    )

    assert _normalize(sampled_family) == expected_family


def test_unsupported_weather_artifact_fixture_fails_fast() -> None:
    fixture_data = _fixture_payload(UNSUPPORTED_WEATHER_ARTIFACT_FIXTURE_PATH)

    with pytest.raises(
        UnsupportedWeatherArtifactVersionError,
        match="unsupported weather artifact schema_version 'v999'",
    ):
        load_weather_artifact(fixture_data)
