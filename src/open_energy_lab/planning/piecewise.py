"""Import-light solver-facing piecewise planning assembly helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from open_energy_lab.tpm.piecewise import (
    PiecewiseApproximationMetadata,
    load_piecewise_metadata,
)


@dataclass(frozen=True, slots=True)
class PiecewisePlanningTerms:
    """Deterministic planning-facing view of canonical TPM piecewise metadata."""

    approximation_kind: str
    leaf_encoding_mode: str
    sum_encoding_mode: str
    breakpoint_policy: Mapping[str, object]
    exp_breakpoints: tuple[float, ...]
    exp_values: tuple[float, ...]
    log_breakpoints: tuple[float, ...]
    log_values: tuple[float, ...]
    mio_epsilon: float
    fit_numeric_tolerance: float
    query_numeric_tolerance: float
    legacy_reference_paths: tuple[str, ...]


def build_piecewise_planning_terms(
    approximation_metadata: Mapping[str, object] | PiecewiseApproximationMetadata,
    *,
    max_terms: int = 2,
) -> PiecewisePlanningTerms:
    """Resolve deterministic solver-facing approximation terms from TPM metadata."""

    resolved_metadata = load_piecewise_metadata(approximation_metadata)
    max_terms = int(max_terms)
    if max_terms < 1:
        raise ValueError("max_terms must be at least 1")

    breakpoint_policy = resolved_metadata.breakpoint_policy
    return PiecewisePlanningTerms(
        approximation_kind=resolved_metadata.approximation_kind,
        leaf_encoding_mode=resolved_metadata.leaf_encoding_mode,
        sum_encoding_mode=resolved_metadata.sum_encoding_mode,
        breakpoint_policy=breakpoint_policy.to_dict(),
        exp_breakpoints=breakpoint_policy.exp_breakpoints(),
        exp_values=breakpoint_policy.exp_values(),
        log_breakpoints=breakpoint_policy.log_breakpoints(max_terms=max_terms),
        log_values=breakpoint_policy.log_values(max_terms=max_terms),
        mio_epsilon=resolved_metadata.mio_epsilon,
        fit_numeric_tolerance=resolved_metadata.fit_numeric_tolerance,
        query_numeric_tolerance=resolved_metadata.query_numeric_tolerance,
        legacy_reference_paths=resolved_metadata.legacy_reference_paths,
    )

__all__ = ["PiecewisePlanningTerms", "build_piecewise_planning_terms"]
