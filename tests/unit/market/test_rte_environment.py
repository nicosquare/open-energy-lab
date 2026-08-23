"""Repository contract for explicit RTE credential handling."""

from __future__ import annotations

from pathlib import Path


ENV_TEMPLATE = Path(".env.example")
GITIGNORE = Path(".gitignore")

EXPECTED_PLACEHOLDERS = {
    "ENTSOE_API_TOKEN": "replace-with-your-entsoe-api-token",
    "RTE_CLIENT_ID": "replace-with-your-rte-client-id",
    "RTE_CLIENT_SECRET": "replace-with-your-rte-client-secret",
}


def _template_assignments() -> dict[str, str]:
    assignments: dict[str, str] = {}
    for raw_line in ENV_TEMPLATE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator == "=", f"unexpected .env.example line: {raw_line!r}"
        assert key not in assignments, f"duplicate template key: {key}"
        assignments[key] = value
    return assignments


def test_environment_template_contains_names_and_placeholders_only() -> None:
    assert _template_assignments() == EXPECTED_PLACEHOLDERS


def test_environment_template_documents_explicit_operation_only_loading() -> None:
    content = ENV_TEMPLATE.read_text(encoding="utf-8").lower()

    assert "explicit" in content
    assert "never load this file" in content
    assert "must never be committed" in content


def test_local_dotenv_files_are_ignored_but_the_template_is_versioned() -> None:
    patterns = {
        line.strip()
        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ".env*" in patterns
    assert "!.env.example" in patterns
