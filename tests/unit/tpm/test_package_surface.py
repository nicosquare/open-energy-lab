"""Package-surface maturity checks for the planned TPM package."""

from __future__ import annotations

import importlib


TPM_PACKAGE = "open_energy_lab.tpm"
SCAFFOLD_DOCSTRING_FRAGMENT = "Future TPM interface scaffold"


def test_tpm_root_surface_stays_explicit_about_surface_maturity() -> None:
    module = importlib.import_module(TPM_PACKAGE)

    if hasattr(module, "__all__"):
        assert isinstance(module.__all__, list)
        for name in module.__all__:
            export = getattr(module, name)
            assert export.__module__.startswith("open_energy_lab.tpm.")
    else:
        assert module.__doc__ is not None
        assert SCAFFOLD_DOCSTRING_FRAGMENT in module.__doc__


def test_tpm_root_reserves_only_documented_public_exports() -> None:
    module = importlib.import_module(TPM_PACKAGE)

    if not hasattr(module, "__all__"):
        assert module.__doc__ is not None
        assert SCAFFOLD_DOCSTRING_FRAGMENT in module.__doc__
        return

    assert all("." not in export_name for export_name in module.__all__)
    assert all(not export_name.startswith("_") for export_name in module.__all__)
