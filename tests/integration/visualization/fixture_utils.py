"""Shared helpers for visualization integration fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path("tests/fixtures/visualization")
INSPECTION_ARBITRAGE_FIXTURE_PATH = FIXTURE_DIR / "inspection_arbitrage_case.json"
INSPECTION_BATTERY_LOAD_PV_FIXTURE_PATH = (
    FIXTURE_DIR / "inspection_battery_load_pv_case.json"
)
COMPARISON_ARBITRAGE_FIXTURE_PATH = FIXTURE_DIR / "comparison_arbitrage_case.json"
PERSISTED_ARBITRAGE_FIXTURE_PATH = FIXTURE_DIR / "persisted_arbitrage_case.json"
VISUALIZATION_FIXTURE_PATHS = tuple(sorted(FIXTURE_DIR.glob("*.json")))

COMMON_TOP_LEVEL_KEYS = (
    "case_id",
    "status",
    "purpose",
    "origin",
    "scenario_kind",
    "numeric_tolerance",
    "provenance_notes",
)

COMMON_ORIGIN_KEYS = (
    "author",
    "construction",
    "seed",
    "generation_command",
    "refresh_policy",
)

INSPECTION_FIXTURE_PATHS = (
    INSPECTION_ARBITRAGE_FIXTURE_PATH,
    INSPECTION_BATTERY_LOAD_PV_FIXTURE_PATH,
)

SCENARIO_KINDS = {"ArbitrageScenario", "BatteryLoadPVScenario"}


def load_visualization_fixture(path: Path) -> dict[str, Any]:
    """Load one visualization fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_all_visualization_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load every committed visualization fixture."""

    return [(path, load_visualization_fixture(path)) for path in VISUALIZATION_FIXTURE_PATHS]


def resolve_repo_relative_path(path_text: str) -> Path:
    """Resolve a repository-relative fixture reference into a local path."""

    return Path(path_text)
