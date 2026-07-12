"""Scaffolding for the simulator-owned planning dataset export workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


FEATURE_NAME = "009-tpm-planning"
SUPPORTED_PLANNING_TARGETS = ("shortfall",)


@dataclass(frozen=True, slots=True)
class PlanningExportRequest:
    """Minimal placeholder for the planned simulator-to-dataset export contract."""

    export_id: str
    flattened_series_fields: tuple[str, ...]
    design_metadata_rows: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    target_name: str = "shortfall"
    include_provenance: bool = True
    numeric_tolerance: float = 1e-9


def export_planning_dataset(*args: object, **kwargs: object) -> object:
    """Reserve the simulator-owned planning export entry point."""

    raise NotImplementedError(
        "open_energy_lab.simulator.planning_export.export_planning_dataset "
        "is reserved by spec 009 and will be implemented in User Story 1 tasks."
    )


__all__ = [
    "FEATURE_NAME",
    "PlanningExportRequest",
    "SUPPORTED_PLANNING_TARGETS",
    "export_planning_dataset",
]
