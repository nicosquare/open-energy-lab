"""Required-install compatibility contracts for the SPFlow TPM backend."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import tpm.spflow_backend as spflow_backend_module


def test_missing_spflow_raises_the_plain_import_error(monkeypatch) -> None:
    requested_modules: list[str] = []

    def _missing_backend(module_name: str):
        requested_modules.append(module_name)
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(spflow_backend_module, "import_module", _missing_backend)

    with pytest.raises(ModuleNotFoundError, match="spflow"):
        spflow_backend_module.require_spflow_backend()

    assert requested_modules == ["spflow"]


def test_incompatible_spflow_version_reports_required_and_installed_versions(
    monkeypatch,
) -> None:
    incompatible_backend = SimpleNamespace(
        __name__="spflow",
        __version__="0.9.0",
    )

    def _import_backend(module_name: str):
        if module_name == "spflow":
            return incompatible_backend
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(spflow_backend_module, "import_module", _import_backend)

    with pytest.raises(ImportError) as exc_info:
        spflow_backend_module.require_spflow_backend()

    diagnostic = str(exc_info.value).lower()
    assert "spflow" in diagnostic
    assert "required" in diagnostic
    assert "1.1.0" in diagnostic
    assert "0.9.0" in diagnostic
    assert "incompatible" in diagnostic
