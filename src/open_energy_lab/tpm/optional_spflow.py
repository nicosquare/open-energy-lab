"""Lazy SPFlow dependency boundary for TPM workflows."""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .data import TPMTrainingData


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


def fit_spflow_model(
    training_data: TPMTrainingData,
    *,
    target_name: str,
    training_random_seed: int | None,
    learn_mspn_kwargs: Mapping[str, object] | None = None,
    backend: Any | None = None,
) -> dict[str, object]:
    """Capture a serializable SPFlow fit payload only when the backend is invoked."""

    backend_module = backend if backend is not None else require_spflow_backend()
    return {
        "payload_kind": "spflow-fit-summary",
        "backend_module": getattr(backend_module, "__name__", type(backend_module).__name__),
        "backend_version": getattr(backend_module, "__version__", None),
        "target_name": target_name,
        "training_random_seed": training_random_seed,
        "row_count": len(training_data.rows),
        "column_order": list(training_data.column_order),
        "normalized_matrix_shape": [
            len(training_data.normalized_rows),
            len(training_data.column_order),
        ],
        "learn_mspn_kwargs": {
            str(key): value for key, value in dict(learn_mspn_kwargs or {}).items()
        },
    }


__all__ = [
    "SPFlowDependencyUnavailableError",
    "fit_spflow_model",
    "require_spflow_backend",
]
