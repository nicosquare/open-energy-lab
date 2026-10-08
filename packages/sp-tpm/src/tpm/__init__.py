"""Public TPM package surface for planning-dataset fit, reload, and query flows.

The stable TPM root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .tensorized import lower_linsum_einet, enable_linsum_contraction
    from .categorical_native import (
        CategoricalMixtureConfig,
        build_categorical_mixture,
        categorical_mixture_parameters,
        assign_categorical_mixture_parameters,
        check_categorical_mixture_against_spflow,
        initialize_categorical_mixture,
        initialize_categorical_mixture_streaming,
        categorical_mixture_step,
        save_categorical_mixture_state,
        load_categorical_mixture_state,
        load_categorical_mixture_for_inference,
    )
    from .categorical_gurobi import (
        compile_categorical_log_ratio,
        evaluate_categorical_log_ratio,
        attach_categorical_log_ratio,
        categorical_attachment_witness,
        CategoricalGroupSeparator,
        restrict_categorical_domains,
    )
    from .conditional import (
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
        TPMIntegerDecisionMapping,
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
        load_feature_schema,
    )
    from .fit import (
        TPMArtifactBuildRequest,
        TPMFitConfig,
        TPMFitMemoryError,
        fit_tpm_artifact_from_rows,
    )
    from .mio import (
        SPNSolverDependencyUnavailableError,
        UnsupportedSPFlowModuleError,
        build_spn_chance_model,
        build_compiled_spflow_decision_link_model,
        compile_spflow_model_to_mio,
        evaluate_compiled_spflow_probability,
        extract_spn_solution,
        infer_max_sum_terms,
        require_pyomo_backend,
    )
    from .spflow_backend import (
        SPFlowBackendCompatibilityError,
        require_spflow_backend,
    )
    from .piecewise import (
        PiecewiseApproximationMetadata,
        PiecewiseBreakpointPolicy,
        build_piecewise_metadata,
        load_piecewise_metadata,
        resolve_guarded_exponential_spec,
    )
    from .query import (
        TPMQueryRequest,
        evaluate_native_conditional_pair,
        query_tpm_artifact,
    )
    from .native import (
        TPMNativeMixtureConfig,
        initialize_native_mixture,
        build_native_mixture,
        native_mixture_log_likelihood,
        check_native_mixture_against_spflow,
        native_mixture_parameters,
        native_joint_conditional_log_values,
        native_full_gradient_step,
        capture_native_training_state,
        restore_native_training_state,
        restore_native_mixture_for_inference,
        materialize_native_mixture,
        export_native_mixture_scalar,
    )

_EXPORT_MAP = {
    "lower_linsum_einet": (".tensorized", "lower_linsum_einet"),
    "enable_linsum_contraction": (".tensorized", "enable_linsum_contraction"),
    "load_categorical_mixture_for_inference": (".categorical_native", "load_categorical_mixture_for_inference"),
    "CategoricalMixtureConfig": (".categorical_native", "CategoricalMixtureConfig"),
    "build_categorical_mixture": (".categorical_native", "build_categorical_mixture"),
    "categorical_mixture_parameters": (".categorical_native", "categorical_mixture_parameters"),
    "assign_categorical_mixture_parameters": (".categorical_native", "assign_categorical_mixture_parameters"),
    "check_categorical_mixture_against_spflow": (".categorical_native", "check_categorical_mixture_against_spflow"),
    "initialize_categorical_mixture": (".categorical_native", "initialize_categorical_mixture"),
    "initialize_categorical_mixture_streaming": (".categorical_native", "initialize_categorical_mixture_streaming"),
    "categorical_mixture_step": (".categorical_native", "categorical_mixture_step"),
    "save_categorical_mixture_state": (".categorical_native", "save_categorical_mixture_state"),
    "load_categorical_mixture_state": (".categorical_native", "load_categorical_mixture_state"),
    "compile_categorical_log_ratio": (".categorical_gurobi", "compile_categorical_log_ratio"),
    "evaluate_categorical_log_ratio": (".categorical_gurobi", "evaluate_categorical_log_ratio"),
    "attach_categorical_log_ratio": (".categorical_gurobi", "attach_categorical_log_ratio"),
    "categorical_attachment_witness": (".categorical_gurobi", "categorical_attachment_witness"),
    "CategoricalGroupSeparator": (".categorical_gurobi", "CategoricalGroupSeparator"),
    "restrict_categorical_domains": (".categorical_gurobi", "restrict_categorical_domains"),
    "TPMNativeMixtureConfig": (".native", "TPMNativeMixtureConfig"),
    "initialize_native_mixture": (".native", "initialize_native_mixture"),
    "build_native_mixture": (".native", "build_native_mixture"),
    "native_mixture_log_likelihood": (".native", "native_mixture_log_likelihood"),
    "check_native_mixture_against_spflow": (".native", "check_native_mixture_against_spflow"),
    "native_mixture_parameters": (".native", "native_mixture_parameters"),
    "native_joint_conditional_log_values": (".native", "native_joint_conditional_log_values"),
    "native_full_gradient_step": (".native", "native_full_gradient_step"),
    "capture_native_training_state": (".native", "capture_native_training_state"),
    "restore_native_training_state": (".native", "restore_native_training_state"),
    "restore_native_mixture_for_inference": (".native", "restore_native_mixture_for_inference"),
    "materialize_native_mixture": (".native", "materialize_native_mixture"),
    "export_native_mixture_scalar": (".native", "export_native_mixture_scalar"),
    "LegacyTPMArtifactVersionError": (
        ".artifact",
        "LegacyTPMArtifactVersionError",
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
    "TPMIntegerDecisionMapping": (".conditional", "TPMIntegerDecisionMapping"),
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
    "learn_bounded_prometheus": (".fit", "learn_bounded_prometheus"),
    "validate_refinement_spn": (".refinement", "validate_refinement_spn"),
    "project_spn_gaussian_widths": (".refinement", "project_spn_gaussian_widths"),
    "spn_binary_conditional_logs": (".refinement", "spn_binary_conditional_logs"),
    "spn_refinement_loss": (".refinement", "spn_refinement_loss"),
    "refine_spn_step": (".refinement", "refine_spn_step"),
    "save_spn_refinement_state": (".refinement", "save_spn_refinement_state"),
    "load_spn_refinement_state": (".refinement", "load_spn_refinement_state"),
    "save_supported_spn_model": (".refinement", "save_supported_spn_model"),
    "TPMFitMemoryError": (".fit", "TPMFitMemoryError"),
    "TPMArtifactBuildRequest": (".fit", "TPMArtifactBuildRequest"),
    "fit_tpm_artifact_from_rows": (".fit", "fit_tpm_artifact_from_rows"),
    "SPNSolverDependencyUnavailableError": (
        ".mio",
        "SPNSolverDependencyUnavailableError",
    ),
    "UnsupportedSPFlowModuleError": (
        ".mio",
        "UnsupportedSPFlowModuleError",
    ),
    "build_spn_chance_model": (".mio", "build_spn_chance_model"),
    "build_compiled_spflow_decision_link_model": (
        ".mio",
        "build_compiled_spflow_decision_link_model",
    ),
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
    "SPFlowBackendCompatibilityError": (
        ".spflow_backend",
        "SPFlowBackendCompatibilityError",
    ),
    "require_spflow_backend": (".spflow_backend", "require_spflow_backend"),
    "PiecewiseApproximationMetadata": (
        ".piecewise",
        "PiecewiseApproximationMetadata",
    ),
    "PiecewiseBreakpointPolicy": (".piecewise", "PiecewiseBreakpointPolicy"),
    "build_piecewise_metadata": (".piecewise", "build_piecewise_metadata"),
    "load_piecewise_metadata": (".piecewise", "load_piecewise_metadata"),
    "resolve_guarded_exponential_spec": (
        ".piecewise",
        "resolve_guarded_exponential_spec",
    ),
    "TPMQueryRequest": (".query", "TPMQueryRequest"),
    "evaluate_native_conditional_pair": (
        ".query",
        "evaluate_native_conditional_pair",
    ),
    "query_tpm_artifact": (".query", "query_tpm_artifact"),
}

__all__ = [
    "LegacyTPMArtifactVersionError",
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
    "TPMIntegerDecisionMapping",
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
    "load_feature_schema",
    "canonical_conditional_json_bytes",
    "load_conditional_evidence",
    "load_conditional_pair",
    "publish_conditional_evidence",
    "publish_conditional_pair",
    "resolve_conditional_attachment_formulation",
    "TPMFitConfig",
    "learn_bounded_prometheus",
    "validate_refinement_spn",
    "project_spn_gaussian_widths",
    "spn_binary_conditional_logs",
    "spn_refinement_loss",
    "refine_spn_step",
    "save_spn_refinement_state",
    "load_spn_refinement_state",
    "save_supported_spn_model",
    "TPMFitMemoryError",
    "TPMArtifactBuildRequest",
    "fit_tpm_artifact_from_rows",
    "SPNSolverDependencyUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_spn_chance_model",
    "build_compiled_spflow_decision_link_model",
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
    "SPFlowBackendCompatibilityError",
    "require_spflow_backend",
    "PiecewiseApproximationMetadata",
    "PiecewiseBreakpointPolicy",
    "build_piecewise_metadata",
    "load_piecewise_metadata",
    "resolve_guarded_exponential_spec",
    "TPMQueryRequest",
    "evaluate_native_conditional_pair",
    "query_tpm_artifact",
    "TPMNativeMixtureConfig",
    "initialize_native_mixture",
    "build_native_mixture",
    "native_mixture_log_likelihood",
    "check_native_mixture_against_spflow",
    "native_mixture_parameters",
    "native_joint_conditional_log_values",
    "native_full_gradient_step",
    "capture_native_training_state",
    "restore_native_training_state",
    "restore_native_mixture_for_inference",
    "materialize_native_mixture",
    "export_native_mixture_scalar",
    "CategoricalMixtureConfig",
    "lower_linsum_einet",
    "enable_linsum_contraction",
    "build_categorical_mixture",
    "categorical_mixture_parameters",
    "assign_categorical_mixture_parameters",
    "check_categorical_mixture_against_spflow",
    "initialize_categorical_mixture",
    "initialize_categorical_mixture_streaming",
    "categorical_mixture_step",
    "save_categorical_mixture_state",
    "load_categorical_mixture_state",
    "load_categorical_mixture_for_inference",
    "compile_categorical_log_ratio",
    "evaluate_categorical_log_ratio",
    "attach_categorical_log_ratio",
    "categorical_attachment_witness",
    "CategoricalGroupSeparator",
    "restrict_categorical_domains",
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
