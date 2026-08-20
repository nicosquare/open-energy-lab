"""Schema checks for aligned-demand and artifact fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.demand.fixture_utils import (
    ALIGNED_TRAINING_FIXTURE_PATH,
    ALIGNED_TRAINING_MISSING_COOLING_FIXTURE_PATH,
    ALIGNED_TRAINING_MISSING_NON_THERMAL_FIXTURE_PATH,
    ARTIFACT_FIXTURE_PATHS,
    COMMON_PROVENANCE_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    DEMAND_FIXTURE_PATHS,
    FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
    TRAINING_FIXTURE_PATHS,
    UNSUPPORTED_DEMAND_ARTIFACT_FIXTURE_PATH,
    load_all_demand_fixtures,
)
from tests.integration.legacy_reference_utils import assert_legacy_reference_path


@pytest.mark.parametrize(
    ("fixture_path", "fixture_data"),
    load_all_demand_fixtures(),
    ids=lambda item: item.name if isinstance(item, Path) else repr(item),
)
def test_demand_fixture_common_schema(
    fixture_path: Path,
    fixture_data: dict[str, object],
) -> None:
    missing_top_level_keys = [
        key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data
    ]
    assert missing_top_level_keys == []
    assert fixture_path in DEMAND_FIXTURE_PATHS
    assert fixture_data["fixture_name"] == fixture_path.stem
    assert fixture_data["fixture_status"] in {"scaffold", "active"}
    assert fixture_data["spec_feature"] == "008-weather-demand-modeling"
    assert isinstance(fixture_data["purpose"], str) and fixture_data["purpose"]

    provenance = fixture_data["provenance"]
    assert isinstance(provenance, dict)
    missing_provenance_keys = [
        key for key in COMMON_PROVENANCE_KEYS if key not in provenance
    ]
    assert missing_provenance_keys == []
    assert isinstance(provenance["author"], str) and provenance["author"]
    assert isinstance(provenance["origin"], str) and provenance["origin"]

    legacy_evidence_paths = provenance["legacy_evidence_paths"]
    assert isinstance(legacy_evidence_paths, list)
    for legacy_path in legacy_evidence_paths:
        assert isinstance(legacy_path, str)
        assert legacy_path.startswith("legacy/")
        assert_legacy_reference_path(legacy_path)

    generation_command = provenance["generation_command"]
    assert generation_command is None or (
        isinstance(generation_command, str) and generation_command
    )

    random_seed = provenance["random_seed"]
    assert random_seed is None or isinstance(random_seed, int)

    refresh_policy = provenance["refresh_policy"]
    assert isinstance(refresh_policy, str) and refresh_policy


@pytest.mark.parametrize("fixture_path", TRAINING_FIXTURE_PATHS)
def test_training_fixtures_use_the_aligned_history_placeholder_contract(
    fixture_path: Path,
) -> None:
    fixture_data = next(
        data for path, data in load_all_demand_fixtures() if path == fixture_path
    )

    assert "sampling_request" not in fixture_data
    assert "required_weather_field_order" not in fixture_data

    if fixture_data["fixture_status"] == "active":
        assert fixture_data["dataset_id"]
        assert fixture_data["timezone_name"]
        assert fixture_data["timestep_hours"] > 0
        assert fixture_data["canonical_weather_fields"]
        assert fixture_data["weather_field_series"]
        if fixture_path == ALIGNED_TRAINING_FIXTURE_PATH:
            assert fixture_data["non_thermal_electric_demand_kw"]
            assert fixture_data["cooling_demand_rt"]
        elif fixture_path == ALIGNED_TRAINING_MISSING_COOLING_FIXTURE_PATH:
            assert "cooling_demand_rt" not in fixture_data
        else:
            assert fixture_path == ALIGNED_TRAINING_MISSING_NON_THERMAL_FIXTURE_PATH
            assert "non_thermal_electric_demand_kw" not in fixture_data
    else:
        assert fixture_data["fixture_status"] == "scaffold"


@pytest.mark.parametrize(
    ("fixture_path", "expected_version"),
    (
        (FITTED_DEMAND_ARTIFACT_FIXTURE_PATH, "v1"),
        (UNSUPPORTED_DEMAND_ARTIFACT_FIXTURE_PATH, "v999"),
    ),
)
def test_artifact_fixtures_track_versioning_contract(
    fixture_path: Path,
    expected_version: str,
) -> None:
    fixture_data = next(
        data for path, data in load_all_demand_fixtures() if path == fixture_path
    )

    assert fixture_path in ARTIFACT_FIXTURE_PATHS

    if fixture_data["fixture_status"] == "active":
        assert fixture_data["schema_version"] == expected_version
        assert fixture_data["feature_name"] == "008-weather-demand-modeling"
        assert fixture_data["artifact_id"]
        assert fixture_data["timestep_hours"] > 0
        assert fixture_data["required_weather_field_order"]
        assert fixture_data["double_counting_policy"]
    else:
        assert fixture_data["fixture_status"] == "scaffold"
        assert "schema_version" not in fixture_data
