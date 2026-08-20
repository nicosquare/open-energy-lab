"""Required-install compatibility contracts for Pyomo and HiGHS."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import open_energy_lab.planning.optional_solver as optional_solver_module


def _pyomo(version: str = "6.10.1") -> SimpleNamespace:
    return SimpleNamespace(__name__="pyomo.environ", __version__=version)


def _highspy(version: str = "1.15.1") -> SimpleNamespace:
    return SimpleNamespace(
        __name__="highspy",
        __version__=version,
        Highs=lambda: SimpleNamespace(version=lambda: version),
    )


def test_missing_pyomo_is_a_required_install_failure(monkeypatch) -> None:
    def _missing_pyomo(module_name: str):
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _missing_pyomo)

    with pytest.raises(ImportError, match=r"(?i)required.*pyomo|pyomo.*required") as exc_info:
        optional_solver_module.require_pyomo_backend()

    assert "optional 'pyomo'" not in str(exc_info.value).lower()


def test_missing_highspy_is_a_required_install_failure(monkeypatch) -> None:
    pyomo_backend = _pyomo()

    def _missing_highspy(module_name: str):
        if module_name in {"pyomo", "pyomo.environ"}:
            return pyomo_backend
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _missing_highspy)

    with pytest.raises(ImportError, match=r"(?i)required.*highspy|highspy.*required"):
        optional_solver_module.require_pyomo_backend()


@pytest.mark.parametrize(
    ("pyomo_version", "highspy_version", "backend_name", "required", "installed"),
    (
        ("6.9.5", "1.15.1", "pyomo", "6.10.1", "6.9.5"),
        ("6.10.1", "1.14.0", "highspy", "1.15.1", "1.14.0"),
    ),
)
def test_incompatible_required_solver_versions_report_actionable_diagnostics(
    monkeypatch,
    pyomo_version: str,
    highspy_version: str,
    backend_name: str,
    required: str,
    installed: str,
) -> None:
    pyomo_backend = _pyomo(pyomo_version)
    highspy_backend = _highspy(highspy_version)

    def _import_backend(module_name: str):
        if module_name in {"pyomo", "pyomo.environ"}:
            return pyomo_backend
        if module_name == "highspy":
            return highspy_backend
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _import_backend)

    with pytest.raises(ImportError) as exc_info:
        optional_solver_module.require_pyomo_backend()

    diagnostic = str(exc_info.value).lower()
    assert backend_name in diagnostic
    assert "required" in diagnostic
    assert required in diagnostic
    assert installed in diagnostic
    assert "incompatible" in diagnostic
