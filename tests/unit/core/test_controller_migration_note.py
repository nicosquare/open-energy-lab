"""Documentation contract tests for the controller-boundary migration note."""

from __future__ import annotations

from pathlib import Path


MIGRATION_NOTE = Path("docs/migration/controller-boundary-mvp.md")

REQUIRED_LEGACY_FILES = (
    "legacy/old_tpm/src_py/legacy/storage.py",
    "legacy/old_tpm/src_py/simulator/common/battery.py",
    "legacy/old_tpm/src_py/simulator/common/pricing.py",
    "legacy/old_tpm/src_py/simulator/common/time.py",
    "legacy/fed_trpo/src/custom/building.py",
    "legacy/fed_trpo/src/custom/citylearn.py",
    "legacy/fed_trpo/src/utils/cl_torchrl_helper.py",
)

REQUIRED_BEHAVIOR_SECTIONS = (
    "## behavior to preserve",
    "## behavior to improve",
    "## behavior to reject",
)

REQUIRED_BOUNDARY_REFERENCES = (
    "src/open_energy_lab/core/controller.py",
    "src/open_energy_lab/simulator/controller_runner.py",
    "tests/fixtures/simulator/controller_arbitrage_case.json",
    "tests/fixtures/simulator/controller_battery_load_pv_case.json",
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


def test_migration_note_mentions_target_boundary_modules_and_fixtures() -> None:
    content = MIGRATION_NOTE.read_text(encoding="utf-8").lower()

    missing = [item for item in REQUIRED_BOUNDARY_REFERENCES if item.lower() not in content]
    assert missing == []
