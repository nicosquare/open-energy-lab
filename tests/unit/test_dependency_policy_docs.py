"""Documentation contract tests for dependency classification policy."""

from __future__ import annotations

from pathlib import Path


DEPENDENCY_POLICY_DOC = Path("docs/migration/dependency-policy.md")
REQUIRED_CLASSIFICATIONS = {
    "core",
    "external-service-backed",
    "hardware-bound",
    "legacy-only",
    "optional",
}


def test_dependency_policy_documents_required_classifications() -> None:
    assert DEPENDENCY_POLICY_DOC.is_file(), (
        "docs/migration/dependency-policy.md must document dependency classes"
    )

    policy_text = DEPENDENCY_POLICY_DOC.read_text(encoding="utf-8")
    missing_classifications = [
        classification
        for classification in sorted(REQUIRED_CLASSIFICATIONS)
        if classification not in policy_text
    ]

    assert missing_classifications == []
