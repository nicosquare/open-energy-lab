"""Documentation contract tests for fixture provenance policy."""

from __future__ import annotations

from pathlib import Path


FIXTURE_PROVENANCE_DOC = Path("docs/migration/fixture-provenance.md")
FIXTURE_PROVENANCE_README = Path("tests/fixtures/README.md")
REQUIRED_TERMS = (
    "fixture path",
    "purpose",
    "origin",
    "source legacy path or generation script",
    "generation command",
    "random seed",
    "input data",
    "expected output or invariant",
    "tolerance",
    "license, access, or privacy notes",
    "refresh policy",
)


def _read_text(path: Path) -> str:
    assert path.is_file(), f"{path} must exist"
    return path.read_text(encoding="utf-8").lower()


def test_fixture_provenance_docs_cover_required_fields() -> None:
    provenance_doc = _read_text(FIXTURE_PROVENANCE_DOC)
    fixture_readme = _read_text(FIXTURE_PROVENANCE_README)

    missing_doc_terms = [term for term in REQUIRED_TERMS if term not in provenance_doc]
    missing_readme_terms = [term for term in REQUIRED_TERMS if term not in fixture_readme]

    assert missing_doc_terms == [], f"{FIXTURE_PROVENANCE_DOC} is missing: {missing_doc_terms}"
    assert missing_readme_terms == [], f"{FIXTURE_PROVENANCE_README} is missing: {missing_readme_terms}"
