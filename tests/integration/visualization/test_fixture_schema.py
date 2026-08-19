"""Schema checks for visualization integration fixtures."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from tests.integration.legacy_reference_utils import assert_legacy_reference_path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixture_utils import (
    COMPARISON_ARBITRAGE_FIXTURE_PATH,
    COMMON_ORIGIN_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    INSPECTION_ARBITRAGE_FIXTURE_PATH,
    INSPECTION_BATTERY_LOAD_PV_FIXTURE_PATH,
    INSPECTION_FIXTURE_PATHS,
    PERSISTED_ARBITRAGE_FIXTURE_PATH,
    SCENARIO_KINDS,
    load_all_visualization_fixtures,
    resolve_repo_relative_path,
)


@pytest.mark.parametrize(
    ("fixture_path", "fixture_data"),
    load_all_visualization_fixtures(),
    ids=lambda item: item.name if isinstance(item, Path) else repr(item),
)
def test_visualization_fixture_common_schema(
    fixture_path: Path,
    fixture_data: dict[str, object],
) -> None:
    missing_top_level_keys = [
        key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data
    ]
    assert missing_top_level_keys == []
    assert fixture_data["case_id"]
    assert fixture_data["status"] in {"scaffold", "active"}
    assert fixture_data["purpose"]
    assert fixture_data["scenario_kind"] in SCENARIO_KINDS
    assert fixture_data["numeric_tolerance"] == pytest.approx(1e-6)

    origin = fixture_data["origin"]
    assert isinstance(origin, dict)
    missing_origin_keys = [key for key in COMMON_ORIGIN_KEYS if key not in origin]
    assert missing_origin_keys == []
    assert isinstance(origin["author"], str) and origin["author"]
    assert isinstance(origin["construction"], str) and origin["construction"]
    assert origin["seed"] is None or isinstance(origin["seed"], int | str)
    assert origin["generation_command"] is None or isinstance(
        origin["generation_command"], str
    )
    assert isinstance(origin["refresh_policy"], str) and origin["refresh_policy"]

    provenance_notes = fixture_data["provenance_notes"]
    assert isinstance(provenance_notes, list)
    assert provenance_notes != []
    assert all(isinstance(note, str) and note for note in provenance_notes)

    if "legacy_references" in fixture_data:
        legacy_references = fixture_data["legacy_references"]
        assert isinstance(legacy_references, list)
        for legacy_path in legacy_references:
            assert isinstance(legacy_path, str)
            assert legacy_path.startswith("legacy/")
            assert_legacy_reference_path(legacy_path)


@pytest.mark.parametrize(
    ("fixture_path", "scenario_kind", "required_sections"),
    (
        (
            INSPECTION_ARBITRAGE_FIXTURE_PATH,
            "ArbitrageScenario",
            {"battery", "dispatch", "pricing", "settlement"},
        ),
        (
            INSPECTION_BATTERY_LOAD_PV_FIXTURE_PATH,
            "BatteryLoadPVScenario",
            {"battery", "dispatch", "load", "net_grid", "pv", "settlement", "weather"},
        ),
    ),
)
def test_visualization_inspection_fixture_schema(
    fixture_path: Path,
    scenario_kind: str,
    required_sections: set[str],
) -> None:
    fixture_data = next(
        data for path, data in load_all_visualization_fixtures() if path == fixture_path
    )

    assert fixture_path in INSPECTION_FIXTURE_PATHS
    assert fixture_data["scenario_kind"] == scenario_kind
    assert "source_fixture" in fixture_data
    assert "expected_sections" in fixture_data
    assert "inspection_expectations" in fixture_data

    source_fixture = resolve_repo_relative_path(fixture_data["source_fixture"])
    assert source_fixture.is_file()
    assert source_fixture.as_posix().startswith("tests/fixtures/simulator/")

    expected_sections = fixture_data["expected_sections"]
    assert isinstance(expected_sections, list)
    assert required_sections.issubset(set(expected_sections))

    inspection_expectations = fixture_data["inspection_expectations"]
    assert isinstance(inspection_expectations, dict)


def test_visualization_comparison_fixture_schema() -> None:
    fixture_data = next(
        data
        for path, data in load_all_visualization_fixtures()
        if path == COMPARISON_ARBITRAGE_FIXTURE_PATH
    )

    assert fixture_data["scenario_kind"] == "ArbitrageScenario"
    assert "left_source_fixture" in fixture_data
    assert "right_source_fixture" in fixture_data
    assert "comparison_expectations" in fixture_data

    left_source_fixture = resolve_repo_relative_path(fixture_data["left_source_fixture"])
    right_source_fixture = resolve_repo_relative_path(fixture_data["right_source_fixture"])
    assert left_source_fixture.is_file()
    assert right_source_fixture.is_file()
    assert left_source_fixture != right_source_fixture

    comparison_expectations = fixture_data["comparison_expectations"]
    assert isinstance(comparison_expectations, dict)


def test_visualization_persisted_fixture_schema() -> None:
    fixture_data = next(
        data
        for path, data in load_all_visualization_fixtures()
        if path == PERSISTED_ARBITRAGE_FIXTURE_PATH
    )

    assert fixture_data["scenario_kind"] == "ArbitrageScenario"
    assert "source_fixture" in fixture_data
    assert "persisted_output" in fixture_data
    assert "inspection_expectations" in fixture_data
    assert "plot_expectations" in fixture_data

    source_fixture = resolve_repo_relative_path(fixture_data["source_fixture"])
    assert source_fixture.is_file()

    persisted_output = fixture_data["persisted_output"]
    inspection_expectations = fixture_data["inspection_expectations"]
    plot_expectations = fixture_data["plot_expectations"]
    assert isinstance(persisted_output, dict)
    assert isinstance(inspection_expectations, dict)
    assert isinstance(plot_expectations, dict)

    if fixture_data["status"] == "active":
        assert persisted_output != {}
