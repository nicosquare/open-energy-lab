"""Schema checks for stochastic-weather simulator fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.simulator.weather_family_fixture_utils import (
    BLACKOUT_WEATHER_FAMILY_FIXTURE_PATH,
    COMMON_TOP_LEVEL_KEYS,
    STOCHASTIC_WEATHER_FAMILY_FIXTURE_PATH,
    WEATHER_FAMILY_FIXTURE_PATHS,
    load_all_weather_family_fixtures,
    resolve_repo_relative_path,
)


@pytest.mark.parametrize(
    ("fixture_path", "fixture_data"),
    load_all_weather_family_fixtures(),
    ids=lambda item: item.name if isinstance(item, Path) else repr(item),
)
def test_weather_family_fixture_common_schema(
    fixture_path: Path,
    fixture_data: dict[str, object],
) -> None:
    missing_top_level_keys = [
        key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data
    ]
    assert missing_top_level_keys == []
    assert fixture_path in WEATHER_FAMILY_FIXTURE_PATHS
    assert fixture_data["fixture_status"] in {"scaffold", "active"}
    assert fixture_data["fixture_path"] == fixture_path.as_posix()
    assert isinstance(fixture_data["purpose"], str) and fixture_data["purpose"]
    assert isinstance(fixture_data["origin"], str) and fixture_data["origin"]

    weather_artifact_dependency = resolve_repo_relative_path(
        fixture_data["weather_artifact_dependency"]
    )
    assert weather_artifact_dependency.is_file()
    assert weather_artifact_dependency.as_posix().startswith("tests/fixtures/weather/")

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
    ("fixture_path", "expected_phrase"),
    (
        (STOCHASTIC_WEATHER_FAMILY_FIXTURE_PATH, "scenario-family"),
        (BLACKOUT_WEATHER_FAMILY_FIXTURE_PATH, "blackout"),
    ),
)
def test_weather_family_fixture_purpose_stays_explicit(
    fixture_path: Path,
    expected_phrase: str,
) -> None:
    fixture_data = next(
        data for path, data in load_all_weather_family_fixtures() if path == fixture_path
    )

    purpose = fixture_data["purpose"].lower()
    notes = " ".join(fixture_data["notes"]).lower()
    assert expected_phrase in purpose or expected_phrase in notes
