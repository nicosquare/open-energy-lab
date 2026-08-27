"""Package-surface maturity checks for the TPM package."""

from __future__ import annotations

import importlib


TPM_PACKAGE = "open_energy_lab.tpm"
EXPECTED_TPM_EXPORTS = [
    "LegacyTPMArtifactVersionError",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "SUPPORTED_TPM_EXECUTION_MODES",
    "TPMArtifact",
    "TPMArtifactIntegrityError",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "TPMTrainingData",
    "normalize_training_data",
    "TPMFeatureDomain",
    "TPMNormalizationSpec",
    "TPMTrainingSupport",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
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
METADATA_EXPORTS = {
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

    assert module.SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS == ("v2",)
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
