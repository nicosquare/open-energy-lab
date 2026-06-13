"""Shared helpers for stochastic-weather integration fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path("tests/fixtures/weather")
RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH = FIXTURE_DIR / "recorded_pvgis_tmy_response.json"
LOCATION_UNAVAILABLE_RESPONSE_FIXTURE_PATH = (
    FIXTURE_DIR / "location_unavailable_response.json"
)
FITTED_WEATHER_ARTIFACT_FIXTURE_PATH = FIXTURE_DIR / "fitted_weather_artifact_v1.json"
WEATHER_FIXTURE_PATHS = (
    RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH,
    LOCATION_UNAVAILABLE_RESPONSE_FIXTURE_PATH,
    FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
)

COMMON_TOP_LEVEL_KEYS = (
    "fixture_status",
    "fixture_path",
    "purpose",
    "origin",
    "legacy_reference_paths",
    "notes",
)


def load_weather_fixture(path: Path) -> dict[str, Any]:
    """Load one committed weather fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_all_weather_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load every committed weather fixture scaffold."""

    return [(path, load_weather_fixture(path)) for path in WEATHER_FIXTURE_PATHS]


def resolve_repo_relative_path(path_text: str) -> Path:
    """Resolve a repository-relative path referenced by a fixture."""

    return Path(path_text)
