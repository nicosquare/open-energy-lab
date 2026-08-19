"""Assertions for reference-only paths inside optional legacy submodules."""

from __future__ import annotations

from pathlib import Path


def assert_legacy_reference_path(path: str) -> None:
    """Require a cited file only when its owning legacy submodule is populated."""

    reference = Path(path)
    assert len(reference.parts) >= 3
    assert reference.parts[0] == "legacy"

    legacy_repository = Path(*reference.parts[:2])
    if legacy_repository.is_dir() and any(legacy_repository.iterdir()):
        assert reference.is_file(), (
            f"legacy reference {path!r} is missing from populated "
            f"repository {legacy_repository}"
        )
