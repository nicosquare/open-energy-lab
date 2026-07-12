"""Scaffolding for TPM conditional-query requests and responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TPMQueryRequest:
    """Minimal placeholder for the planned TPM query contract."""

    decision_assignments: Mapping[str, object] = field(default_factory=dict)
    marginalized_features: tuple[str, ...] = field(default_factory=tuple)
    output_mode: str = "conditional_probability"
    target_name: str = "shortfall"


def query_tpm_artifact(*args: object, **kwargs: object) -> object:
    """Reserve the TPM conditional-query entry point."""

    raise NotImplementedError(
        "open_energy_lab.tpm.query.query_tpm_artifact is reserved by spec 009 "
        "and will be implemented in User Story 2 tasks."
    )


__all__ = ["TPMQueryRequest", "query_tpm_artifact"]
