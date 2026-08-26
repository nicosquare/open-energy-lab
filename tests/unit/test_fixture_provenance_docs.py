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


def test_feature_012_golden_fixture_provenance_is_complete_and_external_only() -> None:
    content = _read_text(FIXTURE_PROVENANCE_DOC)
    fixture_policy = _read_text(
        Path("tests/fixtures/fcr_bid_evaluation/README.md")
    )
    required = (
        "robust_storage_bidding_2023-06-18_aggregate_v1.json",
        "7e44738bb30e5c8204efe40103b9be4c2203685c",
        "julia --project=. 12.jl 2023-06-18",
        "8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6",
        "0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13",
        "528805941",
        "datetime,frequency (hz),xi,xi_eu",
        "external_only",
        "source_precision_compatible",
        "unavailable",
        "no random seed",
        "1e-6",
    )
    for path, text in (
        (FIXTURE_PROVENANCE_DOC, content),
        (Path("tests/fixtures/fcr_bid_evaluation/README.md"), fixture_policy),
    ):
        missing = [term for term in required if term not in text]
        assert missing == [], f"{path} is missing Feature 012 evidence: {missing}"
