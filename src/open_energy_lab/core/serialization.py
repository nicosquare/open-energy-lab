"""Deterministic JSON, content fingerprints, immutable containers, atomic writes."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Any

from .errors import ValidationError


def freeze(value: Any, *, sort_keys: bool = False) -> Any:
    """Recursively turn mappings into read-only proxies and lists into tuples.

    With ``sort_keys`` every mapping is rebuilt in sorted key order.
    """

    if isinstance(value, Mapping):
        items = sorted(value.items()) if sort_keys else value.items()
        return MappingProxyType(
            {str(key): freeze(inner, sort_keys=sort_keys) for key, inner in items}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze(inner, sort_keys=sort_keys) for inner in value)
    return value


def thaw(value: Any) -> Any:
    """Invert :func:`freeze` into plain JSON-compatible dicts and lists.

    Enum members become their values.
    """

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): thaw(inner) for key, inner in value.items()}
    if isinstance(value, tuple):
        return [thaw(inner) for inner in value]
    return value


def canonical_json_bytes(
    value: object,
    *,
    error: type[Exception] = ValidationError,
) -> bytes:
    """Compact, key-sorted UTF-8 JSON used for hashing; NaN and infinity are rejected."""

    try:
        return json.dumps(
            thaw(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise error(f"value is not canonical finite JSON: {exc}") from exc


def json_document_bytes(
    value: object,
    *,
    error: type[Exception] = ValidationError,
) -> bytes:
    """Indented, key-sorted UTF-8 JSON with a trailing newline, for files on disk."""

    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise error(f"value cannot be serialized as finite JSON: {exc}") from exc


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of ``data``."""

    return hashlib.sha256(data).hexdigest()


def fingerprint(
    value: object,
    *,
    error: type[Exception] = ValidationError,
) -> str:
    """Return the SHA-256 digest of ``value``'s canonical JSON."""

    return sha256_hex(canonical_json_bytes(value, error=error))


def write_bytes_atomically(path: Path, data: bytes, *, fail_if_exists: bool = False) -> None:
    """Write ``data`` to ``path`` through a fsynced sibling temporary file.

    With ``fail_if_exists`` a :class:`FileExistsError` is raised if ``path``
    appears while the temporary file is being written. Other ``OSError``s
    propagate; the temporary file is always cleaned up.
    """

    descriptor = -1
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if fail_if_exists and path.exists():
            raise FileExistsError(path)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = [
    "canonical_json_bytes",
    "fingerprint",
    "freeze",
    "json_document_bytes",
    "sha256_hex",
    "thaw",
    "write_bytes_atomically",
]
