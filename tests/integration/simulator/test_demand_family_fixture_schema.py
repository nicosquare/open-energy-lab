"""Schema checks for cooling-aware paired simulator family fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.legacy_reference_utils import assert_legacy_reference_path
from tests.integration.simulator.demand_family_fixture_utils import (
    COMMON_PROVENANCE_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    DEMAND_DISTRICT_COOLING_FAMILY_FIXTURE_PATH,
    DEMAND_FAMILY_FIXTURE_PATHS,
    DEMAND_INVALID_MIXED_COOLING_FIXTURE_PATH,
    DEMAND_LOCAL_ELECTRIC_FAMILY_FIXTURE_PATH,
    load_all_demand_family_fixtures,
    resolve_repo_relative_path,
)


@pytest.mark.parametrize(
    ("fixture_path", "fixture_data"),
    load_all_demand_family_fixtures(),
    ids=lambda item: item.name if isinstance(item, Path) else repr(item),
)
def test_simulator_demand_family_fixture_common_schema(
    fixture_path: Path,
    fixture_data: dict[str, object],
) -> None:
    missing_top_level_keys = [
        key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data
    ]
    assert missing_top_level_keys == []
    assert fixture_path in DEMAND_FAMILY_FIXTURE_PATHS
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
    assert isinstance(provenance["legacy_evidence_paths"], list)
    assert provenance["legacy_evidence_paths"] != []
    for legacy_path in provenance["legacy_evidence_paths"]:
        assert isinstance(legacy_path, str)
        assert legacy_path.startswith("legacy/")
        assert_legacy_reference_path(legacy_path)
    assert provenance["generation_command"] is None or (
        isinstance(provenance["generation_command"], str)
        and provenance["generation_command"]
    )
    assert provenance["random_seed"] is None or isinstance(
        provenance["random_seed"], int
    )
    assert isinstance(provenance["refresh_policy"], str) and provenance["refresh_policy"]


@pytest.mark.parametrize(
    ("fixture_path", "expected_service_path"),
    (
        (DEMAND_LOCAL_ELECTRIC_FAMILY_FIXTURE_PATH, "local-electric"),
        (DEMAND_DISTRICT_COOLING_FAMILY_FIXTURE_PATH, "district-cooling"),
        (DEMAND_INVALID_MIXED_COOLING_FIXTURE_PATH, "mixed-invalid"),
    ),
)
def test_simulator_demand_family_fixture_service_contract(
    fixture_path: Path,
    expected_service_path: str,
) -> None:
    fixture_data = next(
        data
        for path, data in load_all_demand_family_fixtures()
        if path == fixture_path
    )

    if fixture_data["fixture_status"] == "active":
        weather_family_path = resolve_repo_relative_path(
            fixture_data["weather_family_fixture_path"]
        )
        demand_family_path = resolve_repo_relative_path(
            fixture_data["demand_family_fixture_path"]
        )
        assert weather_family_path.is_file()
        assert demand_family_path.is_file()
        assert fixture_data["cooling_service_configuration"]["service_path"] == (
            expected_service_path
        )
        assert fixture_data["numeric_tolerance"] == pytest.approx(1e-6)
    else:
        assert fixture_data["fixture_status"] == "scaffold"
        assert "cooling_service_configuration" not in fixture_data
