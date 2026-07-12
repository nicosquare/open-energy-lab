"""Scaffolding for TPM piecewise approximation metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PiecewiseApproximationMetadata:
    """Minimal placeholder for solver-facing TPM approximation metadata."""

    approximation_kind: str = "piecewise"
    leaf_encoding_mode: str = "reserved"
    sum_encoding_mode: str = "reserved"
    legacy_reference_paths: tuple[str, ...] = field(default_factory=tuple)


def build_piecewise_metadata(*args: object, **kwargs: object) -> PiecewiseApproximationMetadata:
    """Reserve the canonical TPM approximation metadata builder."""

    raise NotImplementedError(
        "open_energy_lab.tpm.piecewise.build_piecewise_metadata is reserved by "
        "spec 009 and will be implemented in User Story 2 tasks."
    )


__all__ = ["PiecewiseApproximationMetadata", "build_piecewise_metadata"]
