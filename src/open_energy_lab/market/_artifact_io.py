"""Load and publish steps shared by the market and restoration artifacts.

Each artifact keeps its own fields, sidecar evidence, and error classes; these
helpers run the common sequence around them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
import os
from pathlib import Path
from typing import Any, TypeVar

from open_energy_lab.core.artifact import publish_write_once, read_artifact_source
from open_energy_lab.core.serialization import json_document_bytes
from open_energy_lab.core.validation import mapping

from .time import CanonicalInterval, MarketTimeValidationError

A = TypeVar("A")


@dataclass(frozen=True, slots=True)
class ArtifactErrors:
    """The error classes one artifact family raises."""

    validation: type[Exception]
    unsupported: type[Exception]
    integrity: type[Exception]
    publication: type[Exception]


def interval_field(
    value: object, *, field_name: str, error: type[Exception]
) -> CanonicalInterval:
    try:
        return CanonicalInterval.from_dict(mapping(value, field_name=field_name, error=error))
    except MarketTimeValidationError as exc:
        raise error(f"{field_name}: {exc}") from exc


def load_artifact(
    source: str | os.PathLike[str] | Mapping[str, Any],
    *,
    artifact_root: str | os.PathLike[str] | None,
    label: str,
    from_dict: Callable[[Mapping[str, Any]], A],
    verify_sidecars: Callable[..., None],
    errors: ArtifactErrors,
) -> A:
    """Decode, validate, and check retained sidecars of one saved artifact."""

    payload, source_name, inferred_root = read_artifact_source(
        source, label=label, error=errors.validation
    )
    try:
        artifact = from_dict(payload)
    except (errors.unsupported, errors.validation):
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise errors.validation(f"invalid {label} {source_name}: {exc}") from exc
    root = Path(artifact_root) if artifact_root is not None else inferred_root
    verify_sidecars(artifact, artifact_root=root)
    return artifact


def write_artifact(
    artifact: A,
    *,
    artifact_type: type[A],
    destination_dir: str | os.PathLike[str],
    filename: Callable[[A], str],
    verify_sidecars: Callable[..., None],
    load: Callable[..., A],
    label: str,
    errors: ArtifactErrors,
) -> Path:
    """Re-validate, check sidecars, then publish the manifest write-once."""

    if not isinstance(artifact, artifact_type):
        raise TypeError(f"artifact must be a {artifact_type.__name__}")
    verified = artifact_type.from_dict(artifact.to_dict())  # type: ignore[attr-defined]
    destination = Path(destination_dir)
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise errors.publication(f"cannot create {label} directory: {destination}") from exc
    verify_sidecars(verified, artifact_root=destination)
    return publish_write_once(
        destination / filename(verified),
        json_document_bytes(verified.to_dict(), error=errors.validation),  # type: ignore[attr-defined]
        load_existing=partial(load, artifact_root=destination),
        same_identity=lambda existing: (
            existing.artifact_fingerprint == verified.artifact_fingerprint  # type: ignore[attr-defined]
        ),
        label=label,
        validation_error=errors.validation,
        integrity_error=errors.integrity,
        publication_error=errors.publication,
    )
