"""Schema checks for demand sampling request and sampled-family fixtures."""

from __future__ import annotations

from tests.integration.demand.fixture_utils import (
    FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
    SAMPLED_DEMAND_FAMILY_FIXTURE_PATH,
    SAMPLING_REQUEST_FIXTURE_PATH,
    load_demand_fixture,
    resolve_repo_relative_path,
)


def test_sampling_request_fixture_schema() -> None:
    fixture_data = load_demand_fixture(SAMPLING_REQUEST_FIXTURE_PATH)

    if fixture_data["fixture_status"] == "active":
        artifact_fixture_path = resolve_repo_relative_path(
            fixture_data["artifact_fixture_path"]
        )
        assert artifact_fixture_path == FITTED_DEMAND_ARTIFACT_FIXTURE_PATH
        assert artifact_fixture_path.is_file()
        assert fixture_data["num_steps"] > 0
        assert fixture_data["scenario_count"] > 0
        assert isinstance(fixture_data["paired_family_seed"], int)
        assert fixture_data["expected_timestep_hours"] > 0
    else:
        assert fixture_data["fixture_status"] == "scaffold"
        assert "artifact_fixture_path" not in fixture_data


def test_sampled_demand_family_fixture_schema() -> None:
    fixture_data = load_demand_fixture(SAMPLED_DEMAND_FAMILY_FIXTURE_PATH)

    if fixture_data["fixture_status"] == "active":
        assert fixture_data["artifact_reference"]
        assert fixture_data["weather_family_reference"]
        assert isinstance(fixture_data["paired_family_seed"], int)
        assert fixture_data["scenario_count"] > 0
        assert fixture_data["num_steps"] > 0
        assert fixture_data["timestep_hours"] > 0
        assert len(fixture_data["sampled_traces"]) == fixture_data["scenario_count"]
    else:
        assert fixture_data["fixture_status"] == "scaffold"
        assert "sampled_traces" not in fixture_data
