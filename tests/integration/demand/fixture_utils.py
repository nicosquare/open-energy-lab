"""Shared helpers for weather-conditioned demand integration fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path("tests/fixtures/demand")
ALIGNED_TRAINING_FIXTURE_PATH = FIXTURE_DIR / "aligned_training_case.json"
ALIGNED_TRAINING_MISSING_COOLING_FIXTURE_PATH = (
    FIXTURE_DIR / "aligned_training_case_missing_cooling.json"
)
ALIGNED_TRAINING_MISSING_NON_THERMAL_FIXTURE_PATH = (
    FIXTURE_DIR / "aligned_training_case_missing_non_thermal.json"
)
FITTED_DEMAND_ARTIFACT_FIXTURE_PATH = FIXTURE_DIR / "fitted_demand_artifact_v1.json"
UNSUPPORTED_DEMAND_ARTIFACT_FIXTURE_PATH = (
    FIXTURE_DIR / "fitted_demand_artifact_unsupported_version.json"
)
SAMPLING_REQUEST_FIXTURE_PATH = FIXTURE_DIR / "sampling_request_case.json"
SAMPLED_DEMAND_FAMILY_FIXTURE_PATH = FIXTURE_DIR / "sampled_demand_family_case.json"
DEMAND_FIXTURE_PATHS = (
    ALIGNED_TRAINING_FIXTURE_PATH,
    ALIGNED_TRAINING_MISSING_COOLING_FIXTURE_PATH,
    ALIGNED_TRAINING_MISSING_NON_THERMAL_FIXTURE_PATH,
    FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
    UNSUPPORTED_DEMAND_ARTIFACT_FIXTURE_PATH,
    SAMPLING_REQUEST_FIXTURE_PATH,
    SAMPLED_DEMAND_FAMILY_FIXTURE_PATH,
)
TRAINING_FIXTURE_PATHS = (
    ALIGNED_TRAINING_FIXTURE_PATH,
    ALIGNED_TRAINING_MISSING_COOLING_FIXTURE_PATH,
    ALIGNED_TRAINING_MISSING_NON_THERMAL_FIXTURE_PATH,
)
ARTIFACT_FIXTURE_PATHS = (
    FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
    UNSUPPORTED_DEMAND_ARTIFACT_FIXTURE_PATH,
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


def load_demand_fixture(path: Path) -> dict[str, Any]:
    """Load one committed demand fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_all_demand_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load every committed demand fixture."""

    return [(path, load_demand_fixture(path)) for path in DEMAND_FIXTURE_PATHS]


def resolve_repo_relative_path(path_text: str) -> Path:
    """Resolve a repository-relative path referenced by a fixture."""

    return Path(path_text)
