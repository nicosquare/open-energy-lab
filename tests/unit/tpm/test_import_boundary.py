"""Import-boundary tests for the planned TPM package."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest


TPM_PACKAGE = "tpm"
PLANNED_TPM_SUBMODULES = (
    "tpm.artifact",
    "tpm.conditional",
    "tpm.conditional_mio",
    "tpm.data",
    "tpm.domains",
    "tpm.features",
    "tpm.fit",
    "tpm.query",
    "tpm.piecewise",
    "tpm.optional_spflow",
)
HEAVY_TPM_BACKENDS = {"spflow", "torch", "pyomo", "highspy"}


@pytest.fixture(autouse=True)
def restore_tpm_modules():
    """Import-isolation probes must not invalidate classes collected elsewhere."""
    saved = {name: module for name, module in sys.modules.items()
             if name == TPM_PACKAGE or name.startswith(TPM_PACKAGE + ".")}
    parent = importlib.import_module("open_energy_lab")
    missing = object()
    old_attribute = getattr(parent, "tpm", missing)
    yield
    for name in list(sys.modules):
        if name == TPM_PACKAGE or name.startswith(TPM_PACKAGE + "."):
            del sys.modules[name]
    sys.modules.update(saved)
    if old_attribute is missing:
        parent.__dict__.pop("tpm", None)
    else:
        parent.tpm = old_attribute


def test_tpm_package_root_reserves_a_lightweight_public_boundary() -> None:
    module_spec = importlib.util.find_spec(TPM_PACKAGE)
    if module_spec is None:
        assert TPM_PACKAGE not in sys.modules
        return

    module = importlib.import_module(TPM_PACKAGE)

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "tpm"
    assert module_file.parent.parent.name == "src"
    assert module_file.parent.parent.parent.name == "sp-tpm"


def test_tpm_root_import_defers_planned_submodule_loading() -> None:
    module_spec = importlib.util.find_spec(TPM_PACKAGE)
    if module_spec is None:
        for module_name in PLANNED_TPM_SUBMODULES:
            assert module_name not in sys.modules
        return

    for module_name in (TPM_PACKAGE, *PLANNED_TPM_SUBMODULES):
        sys.modules.pop(module_name, None)

    importlib.import_module(TPM_PACKAGE)

    for module_name in PLANNED_TPM_SUBMODULES:
        assert module_name not in sys.modules


def test_declared_domain_exports_load_only_the_import_light_domain_module() -> None:
    for module_name in (TPM_PACKAGE, *PLANNED_TPM_SUBMODULES):
        sys.modules.pop(module_name, None)
    modules_before = set(sys.modules)

    package = importlib.import_module(TPM_PACKAGE)
    exported_types = (
        package.TPMFeatureDomain,
        package.TPMNormalizationSpec,
        package.TPMTrainingSupport,
    )

    assert all(export.__module__ == "tpm.domains" for export in exported_types)
    assert "tpm.domains" in sys.modules
    assert "tpm.features" not in sys.modules
    newly_loaded = set(sys.modules) - modules_before
    assert not any(
        module_name == "pyomo" or module_name.startswith("pyomo.")
        for module_name in newly_loaded
    )
    assert not any(
        module_name == "spflow" or module_name.startswith("spflow.")
        for module_name in newly_loaded
    )


def test_conditional_exports_resolve_without_loading_heavy_backends() -> None:
    for module_name in (TPM_PACKAGE, *PLANNED_TPM_SUBMODULES):
        sys.modules.pop(module_name, None)
    modules_before = set(sys.modules)

    package = importlib.import_module(TPM_PACKAGE)
    exports = (
        package.TPMBinaryDecisionMapping,
        package.TPMCategoricalDecisionMapping,
        package.TPMConditionalAttachment,
        package.TPMConditionalAttachmentDiagnostics,
        package.TPMConditionalCompilationRequest,
        package.TPMCompilerFidelityEvidence,
        package.TPMContinuousDecisionMapping,
        package.TPMEmbeddingParityEvidence,
        package.TPMConditionalPair,
        package.load_conditional_evidence,
        package.publish_conditional_evidence,
        package.publish_conditional_pair,
        package.compile_conditional_mio_pair,
        package.attach_conditional_mio_pair,
        package.build_compiler_fidelity_evidence,
        package.build_embedding_parity_evidence,
        package.evaluate_conditional_mio_pair,
        package.initialize_conditional_mio_attachment,
        package.inspect_conditional_mio_attachment,
        package.evaluate_native_conditional_pair,
    )

    assert all(
        export.__module__.startswith("tpm.") for export in exports
    )
    newly_loaded_roots = {
        module_name.split(".", 1)[0]
        for module_name in set(sys.modules) - modules_before
    }
    assert HEAVY_TPM_BACKENDS.isdisjoint(newly_loaded_roots)


def test_planned_tpm_submodules_stay_within_the_reserved_package_boundary() -> None:
    package_spec = importlib.util.find_spec(TPM_PACKAGE)
    if package_spec is None:
        for module_name in PLANNED_TPM_SUBMODULES:
            try:
                module_spec = importlib.util.find_spec(module_name)
            except ModuleNotFoundError:
                module_spec = None
            assert module_spec is None
            assert module_name not in sys.modules
        return

    package = importlib.import_module(TPM_PACKAGE)
    package_dir = Path(package.__file__).resolve().parent

    for module_name in PLANNED_TPM_SUBMODULES:
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None:
            assert module_name not in sys.modules
            continue

        module = importlib.import_module(module_name)

        assert module_spec.origin is not None
        assert module.__file__ is not None
        assert Path(module_spec.origin).resolve().parent == package_dir
        assert Path(module.__file__).resolve().parent == package_dir
