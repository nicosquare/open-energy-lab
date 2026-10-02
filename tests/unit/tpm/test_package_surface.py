"""Package-surface maturity checks for the TPM package."""

from __future__ import annotations

import importlib


TPM_PACKAGE = "open_energy_lab.tpm"
EXPECTED_TPM_EXPORTS = [
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
    "infer_feature_role",
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
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_spn_chance_model",
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
    "resolve_guarded_exponential_spec",
    "TPMQueryRequest",
    "evaluate_native_conditional_pair",
    "query_tpm_artifact",
    "unregister_spflow_backend_adapter",
    "TPMNativeMixtureConfig",
    "initialize_native_mixture",
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
METADATA_EXPORTS = {
    "CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND",
    "CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND",
    "CONDITIONAL_EVIDENCE_EVALUATOR_VERSION",
    "CONDITIONAL_EVIDENCE_SCHEMA_VERSION",
    "CONDITIONAL_PAIR_COMPILER_VERSION",
    "CONDITIONAL_PAIR_RECORD_KIND",
    "CONDITIONAL_PAIR_SCHEMA_VERSION",
    "CURRENT_SPFLOW_ADAPTER_NAME",
    "CURRENT_SPFLOW_BACKEND_GENERATION",
    "REQUIRED_SPFLOW_VERSION",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "SUPPORTED_TPM_EXECUTION_MODES",
}


def test_tpm_root_surface_stays_explicit_about_surface_maturity() -> None:
    module = importlib.import_module(TPM_PACKAGE)

    assert module.__all__ == EXPECTED_TPM_EXPORTS
    for name in module.__all__:
        export = getattr(module, name)
        if name in METADATA_EXPORTS:
            assert isinstance(export, str | tuple)
        else:
            assert export.__module__.startswith("open_energy_lab.tpm.")


def test_tpm_root_reserves_only_documented_public_exports() -> None:
    module = importlib.import_module(TPM_PACKAGE)

    assert module.__all__ == EXPECTED_TPM_EXPORTS
    assert all("." not in export_name for export_name in module.__all__)
    assert all(not export_name.startswith("_") for export_name in module.__all__)


def test_tpm_root_exposes_current_backend_and_artifact_contracts() -> None:
    module = importlib.import_module(TPM_PACKAGE)

    assert module.SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS == ("v2", "v3")
    assert module.SUPPORTED_TPM_EXECUTION_MODES == ("production", "fixture_replay")
    assert module.REQUIRED_SPFLOW_VERSION == "1.1.0"
    assert module.CURRENT_SPFLOW_BACKEND_GENERATION == "current-spflow"
    assert module.CURRENT_SPFLOW_ADAPTER_NAME == "current-spflow-api"
    assert issubclass(
        module.LegacyTPMArtifactVersionError,
        module.UnsupportedTPMArtifactVersionError,
    )
    assert issubclass(module.TPMArtifactIntegrityError, ValueError)
    assert issubclass(module.SPFlowBackendCompatibilityError, ImportError)
    assert module.CurrentSPFlowCapabilities.__module__ == (
        "open_energy_lab.tpm.optional_spflow"
    )
