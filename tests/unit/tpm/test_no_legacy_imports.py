"""Legacy-isolation tests for the planned TPM package."""

from __future__ import annotations

import ast
from pathlib import Path


TPM_SOURCE_DIR = Path("packages/sp-tpm/src/tpm")
PLANNED_TPM_MODULE_PATHS = (
    TPM_SOURCE_DIR / "__init__.py",
    TPM_SOURCE_DIR / "artifact.py",
    TPM_SOURCE_DIR / "data.py",
    TPM_SOURCE_DIR / "features.py",
    TPM_SOURCE_DIR / "fit.py",
    TPM_SOURCE_DIR / "query.py",
    TPM_SOURCE_DIR / "piecewise.py",
    TPM_SOURCE_DIR / "spflow_backend.py",
)
def _imports_legacy(path):
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [node.module] if isinstance(node, ast.ImportFrom) and not node.level and node.module
                 else [])
        if any(name == "legacy" or name.startswith("legacy.") for name in names):
            return True
    return False


def test_tpm_package_modules_do_not_import_legacy_packages() -> None:
    if not TPM_SOURCE_DIR.is_dir():
        assert not TPM_SOURCE_DIR.exists()
        return

    offending_files: list[str] = []
    for path in sorted(TPM_SOURCE_DIR.rglob("*.py")):
        if _imports_legacy(path):
            offending_files.append(path.as_posix())

    assert offending_files == []


def test_planned_tpm_modules_stay_legacy_free_when_present() -> None:
    checked_files = 0
    offending_files: list[str] = []

    for path in PLANNED_TPM_MODULE_PATHS:
        if not path.is_file():
            continue

        checked_files += 1
        if _imports_legacy(path):
            offending_files.append(path.as_posix())

    if checked_files == 0:
        assert not TPM_SOURCE_DIR.exists()
    else:
        assert offending_files == []
