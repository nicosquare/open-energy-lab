"""Documentation contract tests for the battery load PV MVP migration note."""

from __future__ import annotations

from pathlib import Path


MIGRATION_NOTE = Path("docs/migration/battery-load-pv-mvp.md")

REQUIRED_LEGACY_FILES = (
    "legacy/old_tpm/src_py/legacy/storage.py",
    "legacy/old_tpm/scripts/test_battery_consistency.py",
    "legacy/old_tpm/src_py/simulator/common/battery.py",
    "legacy/old_tpm/src_py/simulator/common/pricing.py",
    "legacy/old_tpm/src_py/simulator/common/time.py",
    "legacy/old_tpm/src_py/simulator/common/specs.py",
    "legacy/fed_trpo/src/custom/building.py",
)

REQUIRED_BEHAVIOR_SECTIONS = (
    "## intended preserved scope",
    "## intended improved scope",
    "## intended rejected scope",
)


def test_migration_note_lists_exact_legacy_files() -> None:
    assert MIGRATION_NOTE.is_file()
    content = MIGRATION_NOTE.read_text(encoding="utf-8").lower()

    missing = [path for path in REQUIRED_LEGACY_FILES if path.lower() not in content]
    assert missing == []


def test_migration_note_covers_preserve_improve_reject_split() -> None:
    content = MIGRATION_NOTE.read_text(encoding="utf-8").lower()

    missing = [section for section in REQUIRED_BEHAVIOR_SECTIONS if section not in content]
    assert missing == []
