"""Shared helpers for TPM-planning integration fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PLANNING_FIXTURE_DIR = Path("tests/fixtures/planning")
TPM_FIXTURE_DIR = Path("tests/fixtures/tpm")

PLANNING_DATASET_EXPORT_FIXTURE_PATH = (
    PLANNING_FIXTURE_DIR / "planning_dataset_export_case.json"
)
PLANNING_PROBLEM_FIXTURE_PATH = PLANNING_FIXTURE_DIR / "planning_problem_case.json"
PLANNING_DATASET_ARTIFACT_FIXTURE_PATH = TPM_FIXTURE_DIR / "planning_dataset_v1.json"
TPM_ARTIFACT_FIXTURE_PATH = TPM_FIXTURE_DIR / "tpm_artifact_v1.json"
UNSUPPORTED_TPM_ARTIFACT_FIXTURE_PATH = (
    TPM_FIXTURE_DIR / "tpm_artifact_unsupported_version.json"
)
TPM_QUERY_FIXTURE_PATH = TPM_FIXTURE_DIR / "tpm_query_case.json"

PLANNING_FIXTURE_PATHS = (
    PLANNING_DATASET_EXPORT_FIXTURE_PATH,
    PLANNING_PROBLEM_FIXTURE_PATH,
)
TPM_FIXTURE_PATHS = (
    PLANNING_DATASET_ARTIFACT_FIXTURE_PATH,
    TPM_ARTIFACT_FIXTURE_PATH,
    UNSUPPORTED_TPM_ARTIFACT_FIXTURE_PATH,
    TPM_QUERY_FIXTURE_PATH,
)
ALL_PLANNING_TPM_FIXTURE_PATHS = (*PLANNING_FIXTURE_PATHS, *TPM_FIXTURE_PATHS)

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
COMMON_LIST_KEYS = (
    "planned_contracts",
    "notes",
)


def load_planning_fixture(path: Path) -> dict[str, Any]:
    """Load one committed planning or TPM fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture_group(paths: tuple[Path, ...]) -> list[tuple[Path, dict[str, Any]]]:
    """Load a deterministic fixture group."""

    return [(path, load_planning_fixture(path)) for path in paths]


def load_all_planning_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load planning-domain fixtures."""

    return load_fixture_group(PLANNING_FIXTURE_PATHS)


def load_all_tpm_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load TPM-domain fixtures."""

    return load_fixture_group(TPM_FIXTURE_PATHS)


def resolve_repo_relative_path(path_text: str) -> Path:
    """Resolve a repository-relative path referenced by a fixture."""

    return Path(path_text)
