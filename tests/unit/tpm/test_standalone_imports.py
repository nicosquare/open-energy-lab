"""sp-tpm and its tests must not depend on open_energy_lab."""

from __future__ import annotations

import ast
from pathlib import Path

TPM_ROOT = Path(__file__).resolve().parents[3] / "packages" / "sp-tpm" / "src" / "tpm"


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
        elif (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None)) in {"import_module", "__import__"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            modules.add(node.args[0].value)
    return modules


def test_tpm_never_imports_open_energy_lab() -> None:
    offenders = {
        f"{path.name}: {module}"
        for path in sorted(TPM_ROOT.glob("*.py"))
        for module in _imported_modules(path)
        if module.split(".")[0] == "open_energy_lab"
    }
    absolute_self = {
        f"{path.name}: {module}"
        for path in sorted(TPM_ROOT.glob("*.py"))
        for module in _imported_modules(path)
        if module == "tpm" or module.startswith("tpm.")
    }
    assert not offenders, sorted(offenders)
    assert not absolute_self, f"use relative imports inside tpm: {sorted(absolute_self)}"


TPM_TESTS = (
    Path(__file__).resolve().parents[2] / "unit" / "tpm",
    Path(__file__).resolve().parents[2] / "integration" / "tpm",
)


def test_tpm_tests_never_import_open_energy_lab() -> None:
    """tests/{unit,integration}/tpm must run with only sp-tpm installed (the Python 3.11 job)."""

    offenders = {
        f"{path.parent.name}/{path.name}: {module}"
        for folder in TPM_TESTS
        for path in sorted(folder.glob("*.py"))
        for module in _imported_modules(path)
        if module.split(".")[0] == "open_energy_lab"
        or module.startswith(("tests.unit.planning", "tests.integration.planning"))
    }
    assert not offenders, sorted(offenders)
