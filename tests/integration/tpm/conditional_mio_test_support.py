"""Shared deterministic support for conditional-MIO integration evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TPM_FIXTURE_DIRECTORY = REPOSITORY_ROOT / "tests" / "fixtures" / "tpm"
CONDITIONAL_MIO_SOURCE_PATH = (
    TPM_FIXTURE_DIRECTORY / "conditional_mio_embedding_v1.json"
)
CONDITIONAL_MIO_ARTIFACT_PATH = (
    TPM_FIXTURE_DIRECTORY / "tpm_artifact_conditional_mio_v3.json"
)
CONDITIONAL_MIO_SIDECAR_PATH = (
    TPM_FIXTURE_DIRECTORY
    / "sidecars"
    / "tpm_artifact_conditional_mio_v3.spn_payload.pkl"
)
CONDITIONAL_MAX_PAIR_PATH = TPM_FIXTURE_DIRECTORY / "conditional_pair_max_v1.json"
CONDITIONAL_PWL_PAIR_PATH = TPM_FIXTURE_DIRECTORY / "conditional_pair_pwl_v1.json"
CONDITIONAL_EVIDENCE_PATH = (
    TPM_FIXTURE_DIRECTORY / "conditional_mio_evidence_v1.json"
)


@dataclass(frozen=True, slots=True)
class ConditionalMIOTemporaryPaths:
    """Fresh output locations mirroring every future committed derived fixture."""

    root: Path
    artifact_manifest: Path
    artifact_sidecar: Path
    max_pair: Path
    pwl_pair: Path
    evidence: Path

    @classmethod
    def under(cls, root: Path) -> "ConditionalMIOTemporaryPaths":
        resolved = Path(root).resolve()
        sidecars = resolved / "sidecars"
        resolved.mkdir(parents=True, exist_ok=False)
        sidecars.mkdir()
        return cls(
            root=resolved,
            artifact_manifest=resolved / "tpm_artifact_conditional_mio_v3.json",
            artifact_sidecar=(
                sidecars / "tpm_artifact_conditional_mio_v3.spn_payload.pkl"
            ),
            max_pair=resolved / "conditional_pair_max_v1.json",
            pwl_pair=resolved / "conditional_pair_pwl_v1.json",
            evidence=resolved / "conditional_mio_evidence_v1.json",
        )


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON fixture and require a top-level object."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"fixture {path} must contain a top-level JSON object")
    return payload


def load_conditional_mio_source() -> dict[str, Any]:
    """Load the authoritative model-output-free feature-016 input."""

    return load_json_object(CONDITIONAL_MIO_SOURCE_PATH)


def physical_training_rows(
    payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, object], ...]:
    """Return detached mutable copies of the committed physical source rows."""

    source = payload or load_conditional_mio_source()
    rows = source.get("physical_training_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("conditional-MIO source requires physical_training_rows")
    if not all(isinstance(row, dict) for row in rows):
        raise TypeError("every conditional-MIO training row must be a JSON object")
    return tuple(dict(row) for row in rows)


def canonical_semantic_bytes(value: object) -> bytes:
    """Encode finite JSON semantics deterministically for comparisons and digests."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def semantic_sha256(value: object) -> str:
    """Digest one semantic JSON value independently of presentation whitespace."""

    return hashlib.sha256(canonical_semantic_bytes(value)).hexdigest()


def semantic_projection(
    payload: Mapping[str, Any],
    keys: Sequence[str],
) -> dict[str, Any]:
    """Select explicitly reviewed semantic fields from a larger record."""

    missing = [key for key in keys if key not in payload]
    if missing:
        raise KeyError(f"semantic projection is missing keys: {missing}")
    return {key: payload[key] for key in keys}


def assert_semantic_evidence_equal(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    keys: Sequence[str] | None = None,
) -> None:
    """Compare complete or purpose-selected semantics deterministically."""

    actual_value: object = actual
    expected_value: object = expected
    if keys is not None:
        actual_value = semantic_projection(actual, keys)
        expected_value = semantic_projection(expected, keys)
    assert canonical_semantic_bytes(actual_value) == canonical_semantic_bytes(
        expected_value
    )


def snapshot_evidence_bytes(paths: Iterable[Path]) -> dict[Path, bytes]:
    """Snapshot source, artifact, pair, or evidence bytes before read-only reuse."""

    snapshot: dict[Path, bytes] = {}
    for path in paths:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"fixture evidence does not exist: {resolved}")
        snapshot[resolved] = resolved.read_bytes()
    return snapshot


def assert_evidence_bytes_unchanged(snapshot: Mapping[Path, bytes]) -> None:
    """Prove a workflow did not rewrite any snapshotted evidence file."""

    for path, expected in snapshot.items():
        assert path.read_bytes() == expected, f"fixture bytes changed: {path}"


def file_sha256(path: Path) -> str:
    """Return the exact byte digest used by artifact and evidence provenance."""

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def existing_derived_fixture_paths() -> tuple[Path, ...]:
    """Return only derived feature-016 fixtures that currently exist."""

    candidates = (
        CONDITIONAL_MIO_ARTIFACT_PATH,
        CONDITIONAL_MIO_SIDECAR_PATH,
        CONDITIONAL_MAX_PAIR_PATH,
        CONDITIONAL_PWL_PAIR_PATH,
        CONDITIONAL_EVIDENCE_PATH,
    )
    return tuple(path for path in candidates if path.exists())


__all__ = [
    "CONDITIONAL_EVIDENCE_PATH",
    "CONDITIONAL_MAX_PAIR_PATH",
    "CONDITIONAL_MIO_ARTIFACT_PATH",
    "CONDITIONAL_MIO_SIDECAR_PATH",
    "CONDITIONAL_MIO_SOURCE_PATH",
    "CONDITIONAL_PWL_PAIR_PATH",
    "ConditionalMIOTemporaryPaths",
    "assert_evidence_bytes_unchanged",
    "assert_semantic_evidence_equal",
    "canonical_semantic_bytes",
    "existing_derived_fixture_paths",
    "file_sha256",
    "load_conditional_mio_source",
    "load_json_object",
    "physical_training_rows",
    "semantic_projection",
    "semantic_sha256",
    "snapshot_evidence_bytes",
]
