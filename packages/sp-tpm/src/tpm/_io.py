"""Canonical JSON bytes and atomic file writes shared across the TPM package."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import tempfile
from typing import BinaryIO


def canonical_json_bytes(payload: object) -> bytes:
    """Encode JSON with sorted keys, compact separators, and a trailing newline."""

    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def atomic_write(path: Path, write: Callable[[BinaryIO], object]) -> None:
    """Stream into a temporary sibling, fsync it, then replace ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            write(temporary_file)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    atomic_write(path, lambda stream: stream.write(payload))
