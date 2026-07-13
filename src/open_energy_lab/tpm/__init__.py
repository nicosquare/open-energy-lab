"""Public TPM package surface for planning-dataset fit, reload, and query flows.

The stable TPM root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .artifact import (
        TPMArtifact,
        UnsupportedTPMArtifactVersionError,
        load_tpm_artifact,
    )
    from .data import TPMTrainingData, normalize_training_data
    from .features import (
        TPMFeatureSpec,
        dump_feature_schema,
        infer_feature_role,
        load_feature_schema,
    )
    from .fit import TPMFitConfig, fit_tpm_artifact
    from .optional_spflow import SPFlowDependencyUnavailableError
    from .piecewise import (
        PiecewiseApproximationMetadata,
        PiecewiseBreakpointPolicy,
        build_piecewise_metadata,
        load_piecewise_metadata,
    )
    from .query import TPMQueryRequest, query_tpm_artifact

_EXPORT_MAP = {
    "TPMArtifact": (".artifact", "TPMArtifact"),
    "UnsupportedTPMArtifactVersionError": (
        ".artifact",
        "UnsupportedTPMArtifactVersionError",
    ),
    "load_tpm_artifact": (".artifact", "load_tpm_artifact"),
    "TPMTrainingData": (".data", "TPMTrainingData"),
    "normalize_training_data": (".data", "normalize_training_data"),
    "TPMFeatureSpec": (".features", "TPMFeatureSpec"),
    "dump_feature_schema": (".features", "dump_feature_schema"),
    "infer_feature_role": (".features", "infer_feature_role"),
    "load_feature_schema": (".features", "load_feature_schema"),
    "TPMFitConfig": (".fit", "TPMFitConfig"),
    "fit_tpm_artifact": (".fit", "fit_tpm_artifact"),
    "SPFlowDependencyUnavailableError": (
        ".optional_spflow",
        "SPFlowDependencyUnavailableError",
    ),
    "PiecewiseApproximationMetadata": (
        ".piecewise",
        "PiecewiseApproximationMetadata",
    ),
    "PiecewiseBreakpointPolicy": (".piecewise", "PiecewiseBreakpointPolicy"),
    "build_piecewise_metadata": (".piecewise", "build_piecewise_metadata"),
    "load_piecewise_metadata": (".piecewise", "load_piecewise_metadata"),
    "TPMQueryRequest": (".query", "TPMQueryRequest"),
    "query_tpm_artifact": (".query", "query_tpm_artifact"),
}

__all__ = [
    "TPMArtifact",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "TPMTrainingData",
    "normalize_training_data",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
    "TPMFitConfig",
    "fit_tpm_artifact",
    "SPFlowDependencyUnavailableError",
    "PiecewiseApproximationMetadata",
    "PiecewiseBreakpointPolicy",
    "build_piecewise_metadata",
    "load_piecewise_metadata",
    "TPMQueryRequest",
    "query_tpm_artifact",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the reserved TPM package exports."""

    try:
        module_name, attribute_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
