"""Legacy-isolation checks for the stable core controller boundary."""

from __future__ import annotations

from pathlib import Path


CORE_PACKAGE_DIR = Path("src/open_energy_lab/core")
LEGACY_IMPORT_MARKERS = (
    "from " "legacy",
    "import " "legacy",
)


def test_core_runtime_modules_do_not_import_legacy_packages() -> None:
    assert CORE_PACKAGE_DIR.is_dir()

    for module_path in sorted(CORE_PACKAGE_DIR.glob("*.py")):
        content = module_path.read_text(encoding="utf-8")
        assert not any(marker in content for marker in LEGACY_IMPORT_MARKERS), module_path.as_posix()
