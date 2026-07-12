"""Lazy SPFlow dependency boundary for TPM workflows."""

from __future__ import annotations

from importlib import import_module
from typing import Any


class SPFlowDependencyUnavailableError(ImportError):
    """Raised when a TPM workflow requires SPFlow but it is unavailable."""


def require_spflow_backend() -> Any:
    """Import SPFlow only when a TPM fit or backend-backed query is invoked."""

    try:
        return import_module("spflow")
    except ImportError as exc:  # pragma: no cover - depends on optional install state
        raise SPFlowDependencyUnavailableError(
            "SPFlow-backed TPM workflows require the optional 'spflow' dependency. "
            "This import boundary is intentionally lazy so open_energy_lab.tpm "
            "stays import-light until the backend is used."
        ) from exc


__all__ = ["SPFlowDependencyUnavailableError", "require_spflow_backend"]
