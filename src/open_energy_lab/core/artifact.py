"""Shared steps for persisted, versioned JSON artifacts.

Each artifact type keeps its own fields, validation, and the payload it hashes;
these helpers cover what every persisted artifact repeats: decoding a JSON
document, resolving a path-or-mapping source, sealing and verifying
fingerprints, write-once publication, and retained sidecar files.

Every helper takes the caller's exception classes, so packages keep their own
error hierarchy.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import dataclasses
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, TypeVar

from .errors import ValidationError
from .serialization import fingerprint, sha256_hex, write_bytes_atomically
from .validation import non_empty_str, sha256_digest

T = TypeVar("T")

PLACEHOLDER_FINGERPRINT = "0" * 64
"""Value a fingerprint field holds before :func:`seal_fingerprints` fills it."""

_CREDENTIAL_LABELS = ("token", "credential", "secret")


def decode_json_document(
    text: str,
    *,
    source_name: str,
    label: str,
    error: type[Exception] = ValidationError,
) -> dict[str, Any]:
    """Parse one JSON object, rejecting NaN and infinity."""

    def _reject_non_finite(value: str) -> object:
        raise error(f"{source_name} contains non-finite JSON number {value}")

    try:
        payload = json.loads(text, parse_constant=_reject_non_finite)
    except error:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise error(f"malformed JSON in {label} {source_name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise error(f"{label} {source_name} must contain a top-level JSON object")
    return payload


def read_artifact_source(
    source: str | os.PathLike[str] | Mapping[str, Any],
    *,
    label: str,
    error: type[Exception] = ValidationError,
) -> tuple[dict[str, Any], str, Path | None]:
    """Return ``(payload, source_name, directory)`` for a path or an in-memory mapping.

    ``directory`` is the file's parent (where sidecars are resolved from), or
    ``None`` for a mapping.
    """

    if isinstance(source, Mapping):
        return dict(source), "in-memory manifest", None
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise error(f"{label} cannot be read as UTF-8: {path}") from exc
    return decode_json_document(text, source_name=str(path), label=label, error=error), str(path), path.parent


def payload_without(artifact: Any, field: str) -> dict[str, object]:
    """``artifact.to_dict()`` without ``field`` (a fingerprint cannot hash itself)."""

    payload = artifact.to_dict()
    payload.pop(field)
    return payload


def seal_fingerprints(
    provisional: T,
    stages: Sequence[tuple[str, Callable[[T], object]]],
    *,
    error: type[Exception] = ValidationError,
) -> T:
    """Fill fingerprint fields in order, each hashing a payload of the artifact sealed so far.

    ``provisional`` holds :data:`PLACEHOLDER_FINGERPRINT` in every staged field.
    """

    sealed = provisional
    for field, payload_of in stages:
        sealed = dataclasses.replace(sealed, **{field: fingerprint(payload_of(sealed), error=error)})
    return sealed


def recorded_fingerprints(
    payload: Mapping[str, Any],
    fields: Sequence[str],
    *,
    error: type[Exception] = ValidationError,
) -> dict[str, str]:
    """Read and format-check the fingerprints a persisted payload claims."""

    return {field: sha256_digest(payload.get(field), field_name=field, error=error) for field in fields}


def verify_fingerprints(
    artifact: object,
    recorded: Mapping[str, str],
    *,
    integrity_error: type[Exception],
) -> None:
    """Raise unless every recomputed fingerprint equals the recorded one."""

    for field, value in recorded.items():
        if getattr(artifact, field) != value:
            raise integrity_error(f"{field} mismatch")


def immutable_filename(
    identity: object,
    artifact_fingerprint: object,
    *,
    error: type[Exception] = ValidationError,
    banned_labels: Sequence[str] = _CREDENTIAL_LABELS,
) -> str:
    """``{safe-identity}-{fingerprint}.json``; identities naming credentials are refused."""

    artifact_id = non_empty_str(identity, field_name="artifact_id", error=error)
    if any(label in artifact_id.casefold() for label in banned_labels):
        raise error("artifact_id must not contain credential or token labels")
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", artifact_id).strip("-.")
    if not safe_id:
        raise error("artifact_id does not contain any filename-safe identity characters")
    digest = sha256_digest(artifact_fingerprint, field_name="artifact_fingerprint", error=error)
    return f"{safe_id}-{digest}.json"


def publish_write_once(
    output_path: Path,
    desired_bytes: bytes,
    *,
    load_existing: Callable[[Path], object],
    same_identity: Callable[[object], bool],
    label: str,
    validation_error: type[Exception],
    integrity_error: type[Exception],
    publication_error: type[Exception],
) -> Path:
    """Write ``desired_bytes`` once; an existing file must be the identical artifact.

    The write goes through a fsynced sibling and fails if the path appears
    meanwhile.
    """

    if output_path.exists():
        try:
            existing = load_existing(output_path)
            existing_bytes = output_path.read_bytes()
        except (OSError, validation_error) as exc:
            raise integrity_error(f"immutable existing {label} failed integrity validation") from exc
        if not same_identity(existing) or existing_bytes != desired_bytes:
            raise integrity_error(f"immutable existing {label} differs from requested bytes")
        return output_path
    try:
        write_bytes_atomically(output_path, desired_bytes, fail_if_exists=True)
    except FileExistsError as exc:
        raise integrity_error(f"immutable {label} appeared during publication") from exc
    except OSError as exc:
        raise publication_error(f"atomic {label} publication failed: {output_path}") from exc
    return output_path


def safe_sidecar_locator(
    value: str,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> str:
    """Accept only a portable relative path without traversal."""

    if "\\" in value or ":" in value:
        raise error(f"{field_name} must be a portable safe relative sidecar path")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise error(f"{field_name} must be a safe relative sidecar path without traversal")
    return value


def resolve_sidecar(
    root: Path,
    locator: str,
    *,
    validation_error: type[Exception],
    integrity_error: type[Exception],
) -> Path:
    """Resolve a sidecar under ``root``; missing files and escapes are refused."""

    safe_sidecar_locator(locator, field_name="sidecar_locator", error=validation_error)
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise integrity_error(
            f"artifact root cannot be resolved for sidecar verification: {root}"
        ) from exc
    try:
        candidate = resolved_root.joinpath(*PurePosixPath(locator).parts).resolve(strict=True)
    except OSError as exc:
        raise integrity_error(f"retained sidecar is missing or unreadable: {locator}") from exc
    if not candidate.is_relative_to(resolved_root):
        raise validation_error(f"sidecar locator escapes the declared artifact root: {locator}")
    if not candidate.is_file():
        raise integrity_error(f"retained sidecar is not a regular file: {locator}")
    return candidate


def verify_sidecar_bytes(
    path: Path,
    *,
    locator: str,
    expected_sha256: str,
    expected_byte_count: int,
    integrity_error: type[Exception],
) -> None:
    """Raise unless the sidecar has the recorded size and SHA-256 digest."""

    try:
        data = path.read_bytes()
    except OSError as exc:
        raise integrity_error(f"retained sidecar cannot be read: {locator}") from exc
    if len(data) != expected_byte_count:
        raise integrity_error(f"retained sidecar byte count mismatch: {locator}")
    if sha256_hex(data) != expected_sha256:
        raise integrity_error(f"retained sidecar SHA-256 digest mismatch: {locator}")


__all__ = [
    "PLACEHOLDER_FINGERPRINT",
    "decode_json_document",
    "immutable_filename",
    "payload_without",
    "publish_write_once",
    "read_artifact_source",
    "recorded_fingerprints",
    "resolve_sidecar",
    "safe_sidecar_locator",
    "seal_fingerprints",
    "verify_fingerprints",
    "verify_sidecar_bytes",
]
