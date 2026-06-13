"""Schema checks for stochastic-weather fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.weather.fixture_utils import (
    COMMON_TOP_LEVEL_KEYS,
    FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
    LOCATION_UNAVAILABLE_RESPONSE_FIXTURE_PATH,
    RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH,
    WEATHER_FIXTURE_PATHS,
    load_all_weather_fixtures,
)


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


def test_weather_artifact_fixture_schema() -> None:
    fixture_data = next(
        data
        for path, data in load_all_weather_fixtures()
        if path == FITTED_WEATHER_ARTIFACT_FIXTURE_PATH
    )

    assert "schema_version" in fixture_data
    assert isinstance(fixture_data["schema_version"], str)
    assert fixture_data["schema_version"]
    assert "source_service" not in fixture_data

    if fixture_data["fixture_status"] == "scaffold":
        assert fixture_data["schema_version"] == "v1-scaffold"
    else:
        assert fixture_data["schema_version"].startswith("v")
