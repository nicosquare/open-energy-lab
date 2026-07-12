"""Scaffolding for TPM training-data handling and normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TPMTrainingData:
    """Minimal placeholder for the planned TPM data-handler surface."""

    column_order: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...] = field(default_factory=tuple)


def normalize_training_data(rows: Sequence[Mapping[str, object]]) -> TPMTrainingData:
    """Reserve the TPM data normalization entry point."""

    raise NotImplementedError(
        "open_energy_lab.tpm.data.normalize_training_data is reserved by spec 009 "
        "and will be implemented in User Story 2 tasks."
    )


__all__ = ["TPMTrainingData", "normalize_training_data"]
