from pathlib import Path
import re


TARGET_PACKAGE = Path("src/open_energy_lab")
CONTROL_PACKAGE = TARGET_PACKAGE / "control"
LEGACY_IMPORT_PATTERN = re.compile(r"\b(?:from|import)\s+legacy\b")


def test_target_package_does_not_import_legacy_modules():
    checked_files = 0
    offending_files = []

    for path in TARGET_PACKAGE.rglob("*.py"):
        checked_files += 1
        contents = path.read_text(encoding="utf-8")
        if LEGACY_IMPORT_PATTERN.search(contents):
            offending_files.append(path.as_posix())

    assert checked_files > 0
    assert offending_files == []


def test_control_package_modules_do_not_import_legacy_modules() -> None:
    checked_files = 0
    offending_files = []

    assert CONTROL_PACKAGE.is_dir()

    for path in sorted(CONTROL_PACKAGE.glob("*.py")):
        checked_files += 1
        contents = path.read_text(encoding="utf-8")
        if LEGACY_IMPORT_PATTERN.search(contents):
            offending_files.append(path.as_posix())

    assert checked_files > 0
    assert offending_files == []
