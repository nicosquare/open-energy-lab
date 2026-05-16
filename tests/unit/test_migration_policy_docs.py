"""Documentation contract tests for migration governance policy."""

from __future__ import annotations

from pathlib import Path


MIGRATION_POLICY_DOCS = (
    Path("docs/migration/parity-validation.md"),
    Path("docs/migration/migration-spec-template.md"),
    Path("docs/migration/simulator-preparation.md"),
)

REQUIRED_TERMS = (
    "target module path",
    "validation/test path",
    "legacy paths",
    "behavior to preserve",
    "behavior to improve",
    "behavior to reject",
    "validation evidence",
    "tolerances",
    "out-of-scope algorithm migration",
)


def _read_text(path: Path) -> str:
    assert path.is_file(), f"{path} must exist"
    return path.read_text(encoding="utf-8").lower()


def test_migration_policy_docs_cover_required_gov_contract_terms() -> None:
    for path in MIGRATION_POLICY_DOCS:
        content = _read_text(path)
        missing_terms = [term for term in REQUIRED_TERMS if term not in content]
        assert missing_terms == [], f"{path} is missing: {missing_terms}"
