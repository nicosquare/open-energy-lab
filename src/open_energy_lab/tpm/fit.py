"""Scaffolding for SPFlow-backed TPM fitting."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TPMFitConfig:
    """Minimal placeholder for the planned TPM fit-configuration surface."""

    backend_name: str = "spflow"
    notes: tuple[str, ...] = field(default_factory=tuple)


def fit_tpm_artifact(*args: object, **kwargs: object) -> object:
    """Reserve the TPM fitting entry point."""

    raise NotImplementedError(
        "open_energy_lab.tpm.fit.fit_tpm_artifact is reserved by spec 009 "
        "and will be implemented in User Story 2 tasks."
    )


__all__ = ["TPMFitConfig", "fit_tpm_artifact"]
