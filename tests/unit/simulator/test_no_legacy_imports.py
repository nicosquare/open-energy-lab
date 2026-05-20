"""Legacy-isolation tests for simulator modules."""

from __future__ import annotations

from pathlib import Path


SIMULATOR_SOURCE_DIR = Path("src/open_energy_lab/simulator")
US3_MODULE_PATHS = (
    SIMULATOR_SOURCE_DIR / "load.py",
    SIMULATOR_SOURCE_DIR / "weather.py",
    SIMULATOR_SOURCE_DIR / "pv.py",
    SIMULATOR_SOURCE_DIR / "scenario.py",
)
LEGACY_IMPORT_PATTERNS = (
    "from legacy",
    "import legacy",
)


def test_simulator_modules_do_not_import_legacy_packages() -> None:
    offending_files: list[str] = []
    for path in sorted(SIMULATOR_SOURCE_DIR.rglob("*.py")):
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    assert offending_files == []


def test_us3_simulator_modules_exist_and_stay_legacy_free() -> None:
    offending_files: list[str] = []

    for path in US3_MODULE_PATHS:
        assert path.is_file()
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    assert offending_files == []
