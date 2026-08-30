"""Public TPM package surface for planning-dataset fit, reload, and query flows.

The stable TPM root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .conditional import (
        CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND,
        CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND,
        CONDITIONAL_EVIDENCE_EVALUATOR_VERSION,
        CONDITIONAL_EVIDENCE_SCHEMA_VERSION,
        CONDITIONAL_PAIR_COMPILER_VERSION,
        CONDITIONAL_PAIR_RECORD_KIND,
        CONDITIONAL_PAIR_SCHEMA_VERSION,
        TPMBinaryDecisionLink,
        TPMBinaryDecisionMapping,
        TPMCategoricalDecisionLink,
        TPMCategoricalDecisionMapping,
        TPMConditionalAttachment,
        TPMConditionalAttachmentDiagnostics,
        TPMConditionalAttachmentFormulation,
        TPMConditionalCircuit,
        TPMConditionalCircuitNode,
        TPMConditionalCompilationRequest,
        TPMConditionalDecisionLink,
        TPMConditionalEncodingPolicy,
        TPMConditionalEvaluation,
        TPMConditionalEvent,
        TPMConditionalFeatureValidity,
        TPMConditionalNumericalPolicy,
        TPMConditionalPair,
        TPMConditionalPublication,
        TPMConditionalSourceReference,
        TPMCompilerFidelityEvidence,
        TPMContinuousDecisionMapping,
        TPMEmbeddingParityEvidence,
        TPMNativeConditionalEvaluation,
        canonical_conditional_json_bytes,
        load_conditional_evidence,
        load_conditional_pair,
        publish_conditional_evidence,
        publish_conditional_pair,
        resolve_conditional_attachment_formulation,
    )
    from .conditional_mio import (
        TPMConditionalDiagnosticsError,
        TPMConditionalEvaluationError,
        attach_conditional_mio_pair,
        build_compiler_fidelity_evidence,
        build_embedding_parity_evidence,
        compile_conditional_mio_pair,
        evaluate_conditional_mio_pair,
        initialize_conditional_mio_attachment,
        inspect_conditional_mio_attachment,
    )
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
    from .domains import (
        TPMApproximationDomain,
        TPMCompiledValidityRecord,
        TPMFeatureDomain,
        TPMNormalizationSpec,
        TPMTrainingSupport,
    )
    from .features import (
        TPMFeatureSpec,
        dump_feature_schema,
        infer_feature_role,
        load_feature_schema,
    )
    from .fit import (
        TPMArtifactBuildRequest,
        TPMFitConfig,
        TPMFitMemoryError,
        fit_tpm_artifact,
        fit_tpm_artifact_from_rows,
        fit_tpm_artifact_from_study_manifest,
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
        build_compiled_spflow_decision_link_model,
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
    from .query import (
        TPMQueryRequest,
        evaluate_native_conditional_pair,
        query_tpm_artifact,
    )

_EXPORT_MAP = {
    "CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND": (
        ".conditional",
        "CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND",
    ),
    "CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND": (
        ".conditional",
        "CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND",
    ),
    "CONDITIONAL_EVIDENCE_EVALUATOR_VERSION": (
        ".conditional",
        "CONDITIONAL_EVIDENCE_EVALUATOR_VERSION",
    ),
    "CONDITIONAL_EVIDENCE_SCHEMA_VERSION": (
        ".conditional",
        "CONDITIONAL_EVIDENCE_SCHEMA_VERSION",
    ),
    "CONDITIONAL_PAIR_COMPILER_VERSION": (
        ".conditional",
        "CONDITIONAL_PAIR_COMPILER_VERSION",
    ),
    "CONDITIONAL_PAIR_RECORD_KIND": (
        ".conditional",
        "CONDITIONAL_PAIR_RECORD_KIND",
    ),
    "CONDITIONAL_PAIR_SCHEMA_VERSION": (
        ".conditional",
        "CONDITIONAL_PAIR_SCHEMA_VERSION",
    ),
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
    "TPMBinaryDecisionLink": (".conditional", "TPMBinaryDecisionLink"),
    "TPMBinaryDecisionMapping": (".conditional", "TPMBinaryDecisionMapping"),
    "TPMCategoricalDecisionLink": (
        ".conditional",
        "TPMCategoricalDecisionLink",
    ),
    "TPMCategoricalDecisionMapping": (
        ".conditional",
        "TPMCategoricalDecisionMapping",
    ),
    "TPMConditionalAttachment": (
        ".conditional",
        "TPMConditionalAttachment",
    ),
    "TPMConditionalAttachmentDiagnostics": (
        ".conditional",
        "TPMConditionalAttachmentDiagnostics",
    ),
    "TPMConditionalAttachmentFormulation": (
        ".conditional",
        "TPMConditionalAttachmentFormulation",
    ),
    "TPMConditionalCircuit": (".conditional", "TPMConditionalCircuit"),
    "TPMConditionalCircuitNode": (
        ".conditional",
        "TPMConditionalCircuitNode",
    ),
    "TPMConditionalCompilationRequest": (
        ".conditional",
        "TPMConditionalCompilationRequest",
    ),
    "TPMConditionalDecisionLink": (
        ".conditional",
        "TPMConditionalDecisionLink",
    ),
    "TPMConditionalEncodingPolicy": (
        ".conditional",
        "TPMConditionalEncodingPolicy",
    ),
    "TPMConditionalEvaluation": (
        ".conditional",
        "TPMConditionalEvaluation",
    ),
    "TPMConditionalEvaluationError": (
        ".conditional_mio",
        "TPMConditionalEvaluationError",
    ),
    "TPMConditionalDiagnosticsError": (
        ".conditional_mio",
        "TPMConditionalDiagnosticsError",
    ),
    "TPMConditionalEvent": (".conditional", "TPMConditionalEvent"),
    "TPMConditionalFeatureValidity": (
        ".conditional",
        "TPMConditionalFeatureValidity",
    ),
    "TPMConditionalNumericalPolicy": (
        ".conditional",
        "TPMConditionalNumericalPolicy",
    ),
    "TPMConditionalPair": (".conditional", "TPMConditionalPair"),
    "TPMConditionalPublication": (
        ".conditional",
        "TPMConditionalPublication",
    ),
    "TPMConditionalSourceReference": (
        ".conditional",
        "TPMConditionalSourceReference",
    ),
    "TPMCompilerFidelityEvidence": (
        ".conditional",
        "TPMCompilerFidelityEvidence",
    ),
    "TPMContinuousDecisionMapping": (
        ".conditional",
        "TPMContinuousDecisionMapping",
    ),
    "TPMEmbeddingParityEvidence": (
        ".conditional",
        "TPMEmbeddingParityEvidence",
    ),
    "TPMNativeConditionalEvaluation": (
        ".conditional",
        "TPMNativeConditionalEvaluation",
    ),
    "UnsupportedTPMArtifactVersionError": (
        ".artifact",
        "UnsupportedTPMArtifactVersionError",
    ),
    "load_tpm_artifact": (".artifact", "load_tpm_artifact"),
    "TPMTrainingData": (".data", "TPMTrainingData"),
    "normalize_training_data": (".data", "normalize_training_data"),
    "TPMApproximationDomain": (".domains", "TPMApproximationDomain"),
    "TPMCompiledValidityRecord": (".domains", "TPMCompiledValidityRecord"),
    "TPMFeatureDomain": (".domains", "TPMFeatureDomain"),
    "TPMNormalizationSpec": (".domains", "TPMNormalizationSpec"),
    "TPMTrainingSupport": (".domains", "TPMTrainingSupport"),
    "TPMFeatureSpec": (".features", "TPMFeatureSpec"),
    "dump_feature_schema": (".features", "dump_feature_schema"),
    "infer_feature_role": (".features", "infer_feature_role"),
    "load_feature_schema": (".features", "load_feature_schema"),
    "canonical_conditional_json_bytes": (
        ".conditional",
        "canonical_conditional_json_bytes",
    ),
    "load_conditional_evidence": (
        ".conditional",
        "load_conditional_evidence",
    ),
    "load_conditional_pair": (".conditional", "load_conditional_pair"),
    "publish_conditional_evidence": (
        ".conditional",
        "publish_conditional_evidence",
    ),
    "publish_conditional_pair": (".conditional", "publish_conditional_pair"),
    "resolve_conditional_attachment_formulation": (
        ".conditional",
        "resolve_conditional_attachment_formulation",
    ),
    "TPMFitConfig": (".fit", "TPMFitConfig"),
    "TPMFitMemoryError": (".fit", "TPMFitMemoryError"),
    "TPMArtifactBuildRequest": (".fit", "TPMArtifactBuildRequest"),
    "fit_tpm_artifact": (".fit", "fit_tpm_artifact"),
    "fit_tpm_artifact_from_rows": (".fit", "fit_tpm_artifact_from_rows"),
    "fit_tpm_artifact_from_study_manifest": (
        ".fit",
        "fit_tpm_artifact_from_study_manifest",
    ),
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
    "build_compiled_spflow_decision_link_model": (
        ".mio",
        "build_compiled_spflow_decision_link_model",
    ),
    "build_spn_modeling_terms": (".mio", "build_spn_modeling_terms"),
    "compile_spflow_model_to_mio": (".mio", "compile_spflow_model_to_mio"),
    "compile_conditional_mio_pair": (
        ".conditional_mio",
        "compile_conditional_mio_pair",
    ),
    "attach_conditional_mio_pair": (
        ".conditional_mio",
        "attach_conditional_mio_pair",
    ),
    "build_compiler_fidelity_evidence": (
        ".conditional_mio",
        "build_compiler_fidelity_evidence",
    ),
    "build_embedding_parity_evidence": (
        ".conditional_mio",
        "build_embedding_parity_evidence",
    ),
    "evaluate_conditional_mio_pair": (
        ".conditional_mio",
        "evaluate_conditional_mio_pair",
    ),
    "initialize_conditional_mio_attachment": (
        ".conditional_mio",
        "initialize_conditional_mio_attachment",
    ),
    "inspect_conditional_mio_attachment": (
        ".conditional_mio",
        "inspect_conditional_mio_attachment",
    ),
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
    "evaluate_native_conditional_pair": (
        ".query",
        "evaluate_native_conditional_pair",
    ),
    "query_tpm_artifact": (".query", "query_tpm_artifact"),
}

__all__ = [
    "CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND",
    "CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND",
    "CONDITIONAL_EVIDENCE_EVALUATOR_VERSION",
    "CONDITIONAL_EVIDENCE_SCHEMA_VERSION",
    "CONDITIONAL_PAIR_COMPILER_VERSION",
    "CONDITIONAL_PAIR_RECORD_KIND",
    "CONDITIONAL_PAIR_SCHEMA_VERSION",
    "LegacyTPMArtifactVersionError",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "SUPPORTED_TPM_EXECUTION_MODES",
    "TPMArtifact",
    "TPMArtifactIntegrityError",
    "TPMBinaryDecisionLink",
    "TPMBinaryDecisionMapping",
    "TPMCategoricalDecisionLink",
    "TPMCategoricalDecisionMapping",
    "TPMConditionalAttachment",
    "TPMConditionalAttachmentDiagnostics",
    "TPMConditionalAttachmentFormulation",
    "TPMConditionalCircuit",
    "TPMConditionalCircuitNode",
    "TPMConditionalCompilationRequest",
    "TPMConditionalDecisionLink",
    "TPMConditionalEncodingPolicy",
    "TPMConditionalEvaluation",
    "TPMConditionalDiagnosticsError",
    "TPMConditionalEvaluationError",
    "TPMConditionalEvent",
    "TPMConditionalFeatureValidity",
    "TPMConditionalNumericalPolicy",
    "TPMConditionalPair",
    "TPMConditionalPublication",
    "TPMConditionalSourceReference",
    "TPMCompilerFidelityEvidence",
    "TPMContinuousDecisionMapping",
    "TPMEmbeddingParityEvidence",
    "TPMNativeConditionalEvaluation",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "TPMTrainingData",
    "normalize_training_data",
    "TPMApproximationDomain",
    "TPMCompiledValidityRecord",
    "TPMFeatureDomain",
    "TPMNormalizationSpec",
    "TPMTrainingSupport",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
    "canonical_conditional_json_bytes",
    "load_conditional_evidence",
    "load_conditional_pair",
    "publish_conditional_evidence",
    "publish_conditional_pair",
    "resolve_conditional_attachment_formulation",
    "TPMFitConfig",
    "TPMFitMemoryError",
    "TPMArtifactBuildRequest",
    "fit_tpm_artifact",
    "fit_tpm_artifact_from_rows",
    "fit_tpm_artifact_from_study_manifest",
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_spn_chance_model",
    "build_spn_chance_model_from_artifact",
    "build_compiled_spflow_decision_link_model",
    "build_spn_modeling_terms",
    "compile_spflow_model_to_mio",
    "compile_conditional_mio_pair",
    "attach_conditional_mio_pair",
    "build_compiler_fidelity_evidence",
    "build_embedding_parity_evidence",
    "evaluate_conditional_mio_pair",
    "initialize_conditional_mio_attachment",
    "inspect_conditional_mio_attachment",
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
    "evaluate_native_conditional_pair",
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
