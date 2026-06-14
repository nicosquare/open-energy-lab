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

    if fixture_data["fixture_status"] == "active":
        sampled_family_path = resolve_repo_relative_path(
            fixture_data["sampled_weather_family_fixture_path"]
        )
        assert sampled_family_path.is_file()
        assert sampled_family_path.as_posix() == "tests/fixtures/weather/sampled_weather_family_case.json"

        weather_sampling_request = fixture_data["weather_sampling_request"]
        assert isinstance(weather_sampling_request, dict)
        assert weather_sampling_request["num_steps"] == 3
        assert weather_sampling_request["scenario_count"] == 2
        assert weather_sampling_request["family_seed"] == 13
        assert weather_sampling_request["expected_timestep_hours"] == 24.0

        summary_output_fields = fixture_data["summary_output_fields"]
        assert summary_output_fields == [
            "pv_generation_kw",
            "net_grid_power_kw",
            "unmet_load_kw",
            "step_settlement",
        ]
        assert fixture_data["numeric_tolerance"] == pytest.approx(1e-6)

        base_scenario = fixture_data["base_scenario"]
        assert isinstance(base_scenario, dict)
        assert base_scenario["battery"]["capacity_kwh"] == pytest.approx(8.0)
        assert base_scenario["load"]["demand_kw"] == [3.0, 1.0, 4.0]
        assert base_scenario["pv"]["irradiance_field_names"] == [
            "global_horizontal_irradiance_w_per_m2"
        ]
        assert base_scenario["dispatch_requests"]["requested_power_kw"] == [0.0, 0.0, 0.0]

        expected_family_result = fixture_data["expected_family_result"]
        assert isinstance(expected_family_result, dict)
        assert expected_family_result["family_id"] == "weather-family:f7dbcc3a131d"
        assert expected_family_result["family_seed"] == 13
        assert expected_family_result["timestep_hours"] == 24.0
        assert expected_family_result["supported_summary_fields"] == summary_output_fields
        assert len(expected_family_result["scenario_results"]) == 2
        assert set(expected_family_result["summary_statistics"]) == set(summary_output_fields)

        if fixture_path == BLACKOUT_WEATHER_FAMILY_FIXTURE_PATH:
            blackout_traces = fixture_data["blackout_traces"]
            assert len(blackout_traces) == 2
            assert all(trace["grid_available"] == [False, False, False] for trace in blackout_traces)
        else:
            assert "blackout_traces" not in fixture_data


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
