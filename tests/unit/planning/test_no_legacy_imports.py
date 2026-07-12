"""Legacy-isolation tests for the planned planning package."""

from __future__ import annotations

from pathlib import Path


PLANNING_SOURCE_DIR = Path("src/open_energy_lab/planning")
PLANNED_PLANNING_MODULE_PATHS = (
    PLANNING_SOURCE_DIR / "__init__.py",
    PLANNING_SOURCE_DIR / "dataset.py",
    PLANNING_SOURCE_DIR / "problem.py",
    PLANNING_SOURCE_DIR / "piecewise.py",
    PLANNING_SOURCE_DIR / "optional_solver.py",
)
LEGACY_IMPORT_PATTERNS = (
    "from " "legacy",
    "import " "legacy",
)


def test_planning_package_modules_do_not_import_legacy_packages() -> None:
    if not PLANNING_SOURCE_DIR.is_dir():
        assert not PLANNING_SOURCE_DIR.exists()
        return

    offending_files: list[str] = []
    for path in sorted(PLANNING_SOURCE_DIR.rglob("*.py")):
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    assert offending_files == []


def test_planned_planning_modules_stay_legacy_free_when_present() -> None:
    checked_files = 0
    offending_files: list[str] = []

    for path in PLANNED_PLANNING_MODULE_PATHS:
        if not path.is_file():
            continue

        checked_files += 1
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    if checked_files == 0:
        assert not PLANNING_SOURCE_DIR.exists()
    else:
        assert offending_files == []
