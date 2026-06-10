"""Legacy-isolation tests for visualization runtime modules."""

from __future__ import annotations

from pathlib import Path


VISUALIZATION_SOURCE_DIR = Path("src/open_energy_lab/visualization")
PLANNED_VISUALIZATION_MODULE_PATHS = (
    VISUALIZATION_SOURCE_DIR / "__init__.py",
    VISUALIZATION_SOURCE_DIR / "inspection.py",
    VISUALIZATION_SOURCE_DIR / "comparison.py",
    VISUALIZATION_SOURCE_DIR / "plotting.py",
    VISUALIZATION_SOURCE_DIR / "_persistence.py",
)
LEGACY_IMPORT_PATTERNS = (
    "from " "legacy",
    "import " "legacy",
)


def test_visualization_modules_do_not_import_legacy_packages() -> None:
    offending_files: list[str] = []

    assert VISUALIZATION_SOURCE_DIR.is_dir()

    for path in sorted(VISUALIZATION_SOURCE_DIR.rglob("*.py")):
        contents = path.read_text(encoding="utf-8")
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    assert offending_files == []


def test_planned_visualization_modules_stay_legacy_free_if_present() -> None:
    offending_files: list[str] = []

    assert (VISUALIZATION_SOURCE_DIR / "__init__.py").is_file()

    for path in PLANNED_VISUALIZATION_MODULE_PATHS:
        if not path.exists():
            continue
        contents = path.read_text(encoding="utf-8")
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    assert offending_files == []
