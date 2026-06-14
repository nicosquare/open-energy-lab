"""Shared helpers for stochastic-weather simulator integration fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path("tests/fixtures/simulator")
STOCHASTIC_WEATHER_FAMILY_FIXTURE_PATH = (
    FIXTURE_DIR / "stochastic_weather_family_case.json"
)
BLACKOUT_WEATHER_FAMILY_FIXTURE_PATH = FIXTURE_DIR / "blackout_weather_family_case.json"
WEATHER_FAMILY_FIXTURE_PATHS = (
    STOCHASTIC_WEATHER_FAMILY_FIXTURE_PATH,
    BLACKOUT_WEATHER_FAMILY_FIXTURE_PATH,
)

COMMON_TOP_LEVEL_KEYS = (
    "fixture_status",
    "fixture_path",
    "purpose",
    "origin",
    "weather_artifact_dependency",
    "legacy_reference_paths",
    "notes",
)


def load_weather_family_fixture(path: Path) -> dict[str, Any]:
    """Load one committed stochastic-weather simulator fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_all_weather_family_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load every committed stochastic-weather simulator fixture."""

    return [(path, load_weather_family_fixture(path)) for path in WEATHER_FAMILY_FIXTURE_PATHS]


def resolve_repo_relative_path(path_text: str) -> Path:
    """Resolve a repository-relative path referenced by a fixture."""

    return Path(path_text)
