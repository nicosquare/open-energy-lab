"""Scaffolding for typed TPM feature metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


SUPPORTED_TPM_FEATURE_TYPES = (
    "continuous",
    "binary",
    "categorical",
    "mixed",
)


@dataclass(frozen=True, slots=True)
class TPMFeatureSpec:
    """Minimal placeholder for persisted TPM feature metadata."""

    feature_name: str
    feature_type: str
    feature_role: str = "input"
    modifiable: bool = False
    discrete_values: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["SUPPORTED_TPM_FEATURE_TYPES", "TPMFeatureSpec"]
