"""Shared reviewable evidence helpers for declared-domain integration tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TPM_FIXTURE_DIRECTORY = REPOSITORY_ROOT / "tests" / "fixtures" / "tpm"
DECLARED_DOMAINS_FIXTURE_PATH = (
    TPM_FIXTURE_DIRECTORY / "declared_feature_domains_v1.json"
)
IMMUTABLE_V2_FIXTURE_PATHS = (
    TPM_FIXTURE_DIRECTORY / "tpm_artifact_spflow_v1.json",
    TPM_FIXTURE_DIRECTORY / "sidecars" / "tpm_artifact_spflow_v1.spn_payload.pkl",
)


def load_json_fixture(path: Path) -> dict[str, Any]:
    """Load a repository fixture as a JSON object with an explicit type check."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"fixture {path} must contain a top-level JSON object")
    return payload


def load_declared_domains_fixture() -> dict[str, Any]:
    """Load the committed, model-output-free U-Bounds input fixture."""

    return load_json_fixture(DECLARED_DOMAINS_FIXTURE_PATH)


def physical_training_rows(
    payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, object], ...]:
    """Return independent mutable copies of the fixture's physical rows."""

    source = payload or load_declared_domains_fixture()
    rows = source.get("physical_training_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("declared-domain fixture requires physical_training_rows")
    if not all(isinstance(row, dict) for row in rows):
        raise TypeError("every physical training row must be a JSON object")
    return tuple(dict(row) for row in rows)


def semantic_projection(
    payload: Mapping[str, Any],
    keys: Sequence[str],
) -> dict[str, Any]:
    """Select stable semantic evidence without comparing unrelated metadata."""

    missing = [key for key in keys if key not in payload]
    if missing:
        raise KeyError(f"semantic projection is missing keys: {missing}")
    return {key: payload[key] for key in keys}


def assert_semantic_evidence_equal(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    keys: Sequence[str],
) -> None:
    """Assert equality only for the explicitly selected semantic evidence."""

    assert semantic_projection(actual, keys) == semantic_projection(expected, keys)


def snapshot_source_bytes(paths: Iterable[Path]) -> dict[Path, bytes]:
    """Capture exact committed evidence bytes before a compatibility operation."""

    snapshot: dict[Path, bytes] = {}
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"fixture evidence does not exist: {resolved}")
        snapshot[resolved] = resolved.read_bytes()
    return snapshot


def assert_source_bytes_unchanged(snapshot: Mapping[Path, bytes]) -> None:
    """Assert that compatibility operations did not rewrite source evidence."""

    for path, expected_bytes in snapshot.items():
        assert path.read_bytes() == expected_bytes, f"fixture bytes changed: {path}"


def fixture_sha256(path: Path) -> str:
    """Return the auditable SHA-256 digest of one fixture file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()
