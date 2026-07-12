"""Scaffolding for the persisted TPM artifact contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FEATURE_NAME = "009-tpm-planning"
SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS = ("v1",)


class UnsupportedTPMArtifactVersionError(ValueError):
    """Raised when artifact loading sees an unsupported schema version."""


@dataclass(frozen=True, slots=True)
class TPMArtifact:
    """Minimal placeholder for the planned TPM artifact surface."""

    artifact_id: str
    schema_version: str
    feature_schema: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    provenance: Mapping[str, object] = field(default_factory=dict)


def load_tpm_artifact(source: str | Path | Mapping[str, Any]) -> TPMArtifact:
    """Reserve the offline TPM artifact loading entry point."""

    raise NotImplementedError(
        "open_energy_lab.tpm.artifact.load_tpm_artifact is reserved by spec 009 "
        "and will be implemented in User Story 2 tasks."
    )


__all__ = [
    "FEATURE_NAME",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "TPMArtifact",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
]
