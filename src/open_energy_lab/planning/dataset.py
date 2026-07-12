"""Scaffolding for persisted planning dataset artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FEATURE_NAME = "009-tpm-planning"
SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS = ("v1",)


class UnsupportedPlanningDatasetVersionError(ValueError):
    """Raised when planning dataset loading sees an unsupported schema version."""


@dataclass(frozen=True, slots=True)
class PlanningDatasetArtifact:
    """Minimal placeholder for the planned persisted planning dataset."""

    dataset_id: str
    schema_version: str
    created_at: str = ""
    row_count: int = 0
    horizon_steps: int = 0
    timestep_hours: float = 0.0
    column_order: tuple[str, ...] = field(default_factory=tuple)
    rows: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    design_feature_schema: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    series_field_schema: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    target_metadata: Mapping[str, object] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)
    export_configuration: Mapping[str, object] = field(default_factory=dict)


def load_planning_dataset(source: str | Path | Mapping[str, Any]) -> PlanningDatasetArtifact:
    """Reserve the offline planning dataset loading entry point."""

    raise NotImplementedError(
        "open_energy_lab.planning.dataset.load_planning_dataset is reserved by "
        "spec 009 and will be implemented in User Story 1 tasks."
    )


__all__ = [
    "FEATURE_NAME",
    "PlanningDatasetArtifact",
    "SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS",
    "UnsupportedPlanningDatasetVersionError",
    "load_planning_dataset",
]
