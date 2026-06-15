"""Legacy-isolation tests for the planned demand package."""

from __future__ import annotations

from pathlib import Path


DEMAND_SOURCE_DIR = Path("src/open_energy_lab/demand")
PLANNED_DEMAND_MODULE_PATHS = (
    DEMAND_SOURCE_DIR / "__init__.py",
    DEMAND_SOURCE_DIR / "_aligned_history.py",
    DEMAND_SOURCE_DIR / "_weather_response.py",
    DEMAND_SOURCE_DIR / "fit.py",
    DEMAND_SOURCE_DIR / "artifact.py",
    DEMAND_SOURCE_DIR / "sampling.py",
)
LEGACY_IMPORT_PATTERNS = (
    "from " "legacy",
    "import " "legacy",
)


def test_demand_package_modules_do_not_import_legacy_packages() -> None:
    if not DEMAND_SOURCE_DIR.is_dir():
        assert not DEMAND_SOURCE_DIR.exists()
        return

    offending_files: list[str] = []
    for path in sorted(DEMAND_SOURCE_DIR.rglob("*.py")):
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    assert offending_files == []


def test_planned_demand_modules_stay_legacy_free_when_present() -> None:
    checked_files = 0
    offending_files: list[str] = []

    for path in PLANNED_DEMAND_MODULE_PATHS:
        if not path.is_file():
            continue

        checked_files += 1
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    if checked_files == 0:
        assert not DEMAND_SOURCE_DIR.exists()
    else:
        assert offending_files == []
