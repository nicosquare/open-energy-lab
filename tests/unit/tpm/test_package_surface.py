"""Package-surface maturity checks for the TPM package."""

from __future__ import annotations

import importlib


TPM_PACKAGE = "open_energy_lab.tpm"
EXPECTED_TPM_EXPORTS = [
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


def test_tpm_root_surface_stays_explicit_about_surface_maturity() -> None:
    module = importlib.import_module(TPM_PACKAGE)

    assert module.__all__ == EXPECTED_TPM_EXPORTS
    for name in module.__all__:
        export = getattr(module, name)
        assert export.__module__.startswith("open_energy_lab.tpm.")


def test_tpm_root_reserves_only_documented_public_exports() -> None:
    module = importlib.import_module(TPM_PACKAGE)

    assert module.__all__ == EXPECTED_TPM_EXPORTS
    assert all("." not in export_name for export_name in module.__all__)
    assert all(not export_name.startswith("_") for export_name in module.__all__)
