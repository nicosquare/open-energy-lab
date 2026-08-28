"""Import-boundary tests for the planned TPM package."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


TPM_PACKAGE = "open_energy_lab.tpm"
PLANNED_TPM_SUBMODULES = (
    "open_energy_lab.tpm.artifact",
    "open_energy_lab.tpm.conditional",
    "open_energy_lab.tpm.conditional_mio",
    "open_energy_lab.tpm.data",
    "open_energy_lab.tpm.domains",
    "open_energy_lab.tpm.features",
    "open_energy_lab.tpm.fit",
    "open_energy_lab.tpm.query",
    "open_energy_lab.tpm.piecewise",
    "open_energy_lab.tpm.optional_spflow",
)
HEAVY_TPM_BACKENDS = {"spflow", "torch", "pyomo", "highspy"}


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
    assert module_file.parent.parent.name == "open_energy_lab"


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

    assert all(export.__module__ == "open_energy_lab.tpm.domains" for export in exported_types)
    assert "open_energy_lab.tpm.domains" in sys.modules
    assert "open_energy_lab.tpm.features" not in sys.modules
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
        package.TPMConditionalAttachment,
        package.TPMConditionalCompilationRequest,
        package.TPMContinuousDecisionMapping,
        package.TPMConditionalPair,
        package.publish_conditional_pair,
        package.compile_conditional_mio_pair,
        package.attach_conditional_mio_pair,
        package.evaluate_conditional_mio_pair,
        package.evaluate_native_conditional_pair,
    )

    assert all(
        export.__module__.startswith("open_energy_lab.tpm.") for export in exports
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
