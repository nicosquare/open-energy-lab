"""Legacy-isolation tests for the planned weather package."""

from __future__ import annotations

from pathlib import Path


WEATHER_SOURCE_DIR = Path("src/open_energy_lab/weather")
PLANNED_WEATHER_MODULE_PATHS = (
    WEATHER_SOURCE_DIR / "__init__.py",
    WEATHER_SOURCE_DIR / "_canonical.py",
    WEATHER_SOURCE_DIR / "tmy.py",
    WEATHER_SOURCE_DIR / "fit.py",
    WEATHER_SOURCE_DIR / "artifact.py",
    WEATHER_SOURCE_DIR / "sampling.py",
    WEATHER_SOURCE_DIR / "events.py",
)
LEGACY_IMPORT_PATTERNS = (
    "from " "legacy",
    "import " "legacy",
)


def test_weather_package_modules_do_not_import_legacy_packages() -> None:
    if not WEATHER_SOURCE_DIR.is_dir():
        assert not WEATHER_SOURCE_DIR.exists()
        return

    offending_files: list[str] = []
    for path in sorted(WEATHER_SOURCE_DIR.rglob("*.py")):
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    assert offending_files == []


def test_planned_weather_modules_stay_legacy_free_when_present() -> None:
    checked_files = 0
    offending_files: list[str] = []

    for path in PLANNED_WEATHER_MODULE_PATHS:
        if not path.is_file():
            continue

        checked_files += 1
        contents = path.read_text()
        if any(pattern in contents for pattern in LEGACY_IMPORT_PATTERNS):
            offending_files.append(path.as_posix())

    if checked_files == 0:
        assert not WEATHER_SOURCE_DIR.exists()
    else:
        assert offending_files == []
