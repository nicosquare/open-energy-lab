"""Public TPM package surface for planning-dataset fit, reload, and query flows.

The stable TPM root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .artifact import (
        LegacyTPMArtifactVersionError,
        SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS,
        SUPPORTED_TPM_EXECUTION_MODES,
        TPMArtifact,
        TPMArtifactIntegrityError,
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
    from .fit import (
        TPMArtifactBuildRequest,
        TPMFitConfig,
        fit_tpm_artifact,
        fit_tpm_artifact_from_rows,
    )
    from .mio import (
        SPNModelingTerms,
        SPNPiecewiseCurveSpec,
        SPNSolveConfig,
        SPNSolveSummary,
        SPNSolverDependencyUnavailableError,
        SPNSolverUnavailableError,
        UnsupportedSPFlowModuleError,
        build_spn_chance_model,
        build_spn_chance_model_from_artifact,
        build_spn_modeling_terms,
        compile_spflow_model_to_mio,
        evaluate_compiled_spflow_probability,
        extract_spn_solution,
        infer_max_sum_terms,
        require_pyomo_backend,
        solve_spn_chance_model,
        solve_spn_chance_model_from_artifact,
    )
    from .optional_spflow import (
        CURRENT_SPFLOW_ADAPTER_NAME,
        CURRENT_SPFLOW_BACKEND_GENERATION,
        REQUIRED_SPFLOW_VERSION,
        CurrentSPFlowCapabilities,
        SPFlowBackendCompatibilityError,
        SPFlowDependencyUnavailableError,
        detect_spflow_backend_capabilities,
        register_spflow_backend_adapter,
        require_spflow_backend,
        unregister_spflow_backend_adapter,
    )
    from .piecewise import (
        PiecewiseApproximationMetadata,
        PiecewiseBreakpointPolicy,
        build_piecewise_metadata,
        load_piecewise_metadata,
    )
    from .query import TPMQueryRequest, query_tpm_artifact

_EXPORT_MAP = {
    "LegacyTPMArtifactVersionError": (
        ".artifact",
        "LegacyTPMArtifactVersionError",
    ),
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS": (
        ".artifact",
        "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    ),
    "SUPPORTED_TPM_EXECUTION_MODES": (
        ".artifact",
        "SUPPORTED_TPM_EXECUTION_MODES",
    ),
    "TPMArtifact": (".artifact", "TPMArtifact"),
    "TPMArtifactIntegrityError": (".artifact", "TPMArtifactIntegrityError"),
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
    "TPMArtifactBuildRequest": (".fit", "TPMArtifactBuildRequest"),
    "fit_tpm_artifact": (".fit", "fit_tpm_artifact"),
    "fit_tpm_artifact_from_rows": (".fit", "fit_tpm_artifact_from_rows"),
    "SPNModelingTerms": (".mio", "SPNModelingTerms"),
    "SPNPiecewiseCurveSpec": (".mio", "SPNPiecewiseCurveSpec"),
    "SPNSolveConfig": (".mio", "SPNSolveConfig"),
    "SPNSolveSummary": (".mio", "SPNSolveSummary"),
    "SPNSolverDependencyUnavailableError": (
        ".mio",
        "SPNSolverDependencyUnavailableError",
    ),
    "SPNSolverUnavailableError": (".mio", "SPNSolverUnavailableError"),
    "UnsupportedSPFlowModuleError": (
        ".mio",
        "UnsupportedSPFlowModuleError",
    ),
    "build_spn_chance_model": (".mio", "build_spn_chance_model"),
    "build_spn_chance_model_from_artifact": (
        ".mio",
        "build_spn_chance_model_from_artifact",
    ),
    "build_spn_modeling_terms": (".mio", "build_spn_modeling_terms"),
    "compile_spflow_model_to_mio": (".mio", "compile_spflow_model_to_mio"),
    "evaluate_compiled_spflow_probability": (
        ".mio",
        "evaluate_compiled_spflow_probability",
    ),
    "extract_spn_solution": (".mio", "extract_spn_solution"),
    "infer_max_sum_terms": (".mio", "infer_max_sum_terms"),
    "require_pyomo_backend": (".mio", "require_pyomo_backend"),
    "solve_spn_chance_model": (".mio", "solve_spn_chance_model"),
    "solve_spn_chance_model_from_artifact": (
        ".mio",
        "solve_spn_chance_model_from_artifact",
    ),
    "CURRENT_SPFLOW_ADAPTER_NAME": (
        ".optional_spflow",
        "CURRENT_SPFLOW_ADAPTER_NAME",
    ),
    "CURRENT_SPFLOW_BACKEND_GENERATION": (
        ".optional_spflow",
        "CURRENT_SPFLOW_BACKEND_GENERATION",
    ),
    "CurrentSPFlowCapabilities": (
        ".optional_spflow",
        "CurrentSPFlowCapabilities",
    ),
    "REQUIRED_SPFLOW_VERSION": (
        ".optional_spflow",
        "REQUIRED_SPFLOW_VERSION",
    ),
    "SPFlowBackendCompatibilityError": (
        ".optional_spflow",
        "SPFlowBackendCompatibilityError",
    ),
    "SPFlowDependencyUnavailableError": (
        ".optional_spflow",
        "SPFlowDependencyUnavailableError",
    ),
    "detect_spflow_backend_capabilities": (
        ".optional_spflow",
        "detect_spflow_backend_capabilities",
    ),
    "register_spflow_backend_adapter": (
        ".optional_spflow",
        "register_spflow_backend_adapter",
    ),
    "require_spflow_backend": (".optional_spflow", "require_spflow_backend"),
    "unregister_spflow_backend_adapter": (
        ".optional_spflow",
        "unregister_spflow_backend_adapter",
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
    "LegacyTPMArtifactVersionError",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "SUPPORTED_TPM_EXECUTION_MODES",
    "TPMArtifact",
    "TPMArtifactIntegrityError",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "TPMTrainingData",
    "normalize_training_data",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
    "TPMFitConfig",
    "TPMArtifactBuildRequest",
    "fit_tpm_artifact",
    "fit_tpm_artifact_from_rows",
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_spn_chance_model",
    "build_spn_chance_model_from_artifact",
    "build_spn_modeling_terms",
    "compile_spflow_model_to_mio",
    "evaluate_compiled_spflow_probability",
    "extract_spn_solution",
    "infer_max_sum_terms",
    "require_pyomo_backend",
    "solve_spn_chance_model",
    "solve_spn_chance_model_from_artifact",
    "CURRENT_SPFLOW_ADAPTER_NAME",
    "CURRENT_SPFLOW_BACKEND_GENERATION",
    "CurrentSPFlowCapabilities",
    "REQUIRED_SPFLOW_VERSION",
    "SPFlowBackendCompatibilityError",
    "SPFlowDependencyUnavailableError",
    "detect_spflow_backend_capabilities",
    "register_spflow_backend_adapter",
    "require_spflow_backend",
    "PiecewiseApproximationMetadata",
    "PiecewiseBreakpointPolicy",
    "build_piecewise_metadata",
    "load_piecewise_metadata",
    "TPMQueryRequest",
    "query_tpm_artifact",
    "unregister_spflow_backend_adapter",
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
