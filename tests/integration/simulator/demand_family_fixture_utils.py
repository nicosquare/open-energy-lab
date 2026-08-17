"""Shared helpers for cooling-aware paired simulator family fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path("tests/fixtures/simulator")
DEMAND_LOCAL_ELECTRIC_FAMILY_FIXTURE_PATH = (
    FIXTURE_DIR / "demand_local_electric_family_case.json"
)
DEMAND_DISTRICT_COOLING_FAMILY_FIXTURE_PATH = (
    FIXTURE_DIR / "demand_district_cooling_family_case.json"
)
DEMAND_INVALID_MIXED_COOLING_FIXTURE_PATH = (
    FIXTURE_DIR / "demand_invalid_mixed_cooling_case.json"
)
DEMAND_FAMILY_FIXTURE_PATHS = (
    DEMAND_LOCAL_ELECTRIC_FAMILY_FIXTURE_PATH,
    DEMAND_DISTRICT_COOLING_FAMILY_FIXTURE_PATH,
    DEMAND_INVALID_MIXED_COOLING_FIXTURE_PATH,
)
COMMON_TOP_LEVEL_KEYS = (
    "fixture_name",
    "fixture_status",
    "purpose",
    "spec_feature",
    "provenance",
)
COMMON_PROVENANCE_KEYS = (
    "author",
    "origin",
    "legacy_evidence_paths",
    "generation_command",
    "random_seed",
    "refresh_policy",
)


def load_demand_family_fixture(path: Path) -> dict[str, Any]:
    """Load one committed simulator demand-family fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_all_demand_family_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load every committed simulator demand-family fixture."""

    return [
        (path, load_demand_family_fixture(path))
        for path in DEMAND_FAMILY_FIXTURE_PATHS
    ]


def resolve_repo_relative_path(path_text: str) -> Path:
    """Resolve a repository-relative path referenced by a fixture."""

    return Path(path_text)
