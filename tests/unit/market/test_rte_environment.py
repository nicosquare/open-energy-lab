"""Repository contract for explicit RTE credential handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import traceback

import pytest

from open_energy_lab.market.rte import (
    RTEAuthenticationError,
    build_rte_restoration_request,
    execute_rte_request,
)


ENV_TEMPLATE = Path(".env.example")
GITIGNORE = Path(".gitignore")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_PLACEHOLDERS = {
    "ENTSOE_API_TOKEN": "replace-with-your-entsoe-api-token",
    "RTE_CLIENT_ID": "replace-with-your-rte-client-id",
    "RTE_CLIENT_SECRET": "replace-with-your-rte-client-secret",
}
KNOWN_TEST_SENTINELS = (
    "-".join(("client", "id", "SENTINEL", "4f3a")),
    "-".join(("client", "secret", "SENTINEL", "9c2b")),
    "-".join(("access", "token", "SENTINEL", "first", "1a7e")),
    "-".join(("access", "token", "SENTINEL", "renewed", "8d5c")),
    "-".join(("WORKFLOW", "CLIENT", "ID", "SENTINEL", "a3e1")),
    "-".join(("WORKFLOW", "CLIENT", "SECRET", "SENTINEL", "b7c2")),
    "-".join(("WORKFLOW", "ACCESS", "TOKEN", "SENTINEL", "c9f4")),
    "-".join(("STAGING", "CLIENT", "ID", "SENTINEL", "2cf0")),
    "-".join(("STAGING", "CLIENT", "SECRET", "SENTINEL", "885c")),
    "-".join(("STAGING", "ACCESS", "TOKEN", "SENTINEL", "aa73")),
    "-".join(("CLI", "CLIENT", "ID", "SENTINEL")),
    "-".join(("CLI", "CLIENT", "SECRET", "SENTINEL")),
    "_".join(("OEL", "SENTINEL", "TOKEN", "MUST", "NEVER", "ESCAPE", "7f91")),
    "-".join(("RAW", "BODY", "SENTINEL", "must", "not", "escape")),
    "-".join(("RAW", "ERROR", "BODY", "SENTINEL", "7b9d")),
)
SENTINEL_DEFINITION_FILES = {
    Path("tests/integration/market/test_restoration_reference_staging.py"),
    Path("tests/integration/market/test_rte_restoration_workflow.py"),
    Path("tests/unit/market/test_entsoe_transport.py"),
    Path("tests/unit/market/test_fetch_rte_period_cli.py"),
    Path("tests/unit/market/test_rte_transport.py"),
}
SCANNED_TEXT_SUFFIXES = {
    ".csv",
    ".ipynb",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
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


def _repository_scan_files() -> tuple[Path, ...]:
    roots = tuple(
        REPOSITORY_ROOT / name
        for name in ("src", "tests", "docs", "examples", "specs", "artifacts")
    )
    files: set[Path] = {
        REPOSITORY_ROOT / ".env.example",
        REPOSITORY_ROOT / "README.md",
        REPOSITORY_ROOT / "pyproject.toml",
    }
    for root in roots:
        if root.is_dir():
            files.update(path for path in root.rglob("*") if path.is_file())
    return tuple(sorted(files))


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


def test_synthetic_credential_and_raw_body_sentinels_never_escape_test_sources() -> None:
    hits: dict[Path, set[str]] = {}
    filenames_with_sentinels: dict[Path, set[str]] = {}

    for path in _repository_scan_files():
        relative = path.relative_to(REPOSITORY_ROOT)
        name_hits = {
            sentinel for sentinel in KNOWN_TEST_SENTINELS if sentinel in relative.as_posix()
        }
        if name_hits:
            filenames_with_sentinels[relative] = name_hits
        if path.suffix.casefold() not in SCANNED_TEXT_SUFFIXES:
            continue
        content = path.read_text(encoding="utf-8")
        content_hits = {
            sentinel for sentinel in KNOWN_TEST_SENTINELS if sentinel in content
        }
        if content_hits:
            hits[relative] = content_hits

    assert filenames_with_sentinels == {}
    assert set(hits).issubset(SENTINEL_DEFINITION_FILES), hits
    assert set().union(*hits.values()) == set(KNOWN_TEST_SENTINELS)


def test_authentication_exception_chain_and_captured_diagnostics_redact_secrets(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client_id, client_secret, access_token = KNOWN_TEST_SENTINELS[:3]
    request = build_rte_restoration_request(
        resource="standard_afrr_data",
        requested_start_utc=datetime(2026, 8, 20, tzinfo=UTC),
        requested_end_utc=datetime(2026, 8, 20, tzinfo=UTC) + timedelta(minutes=15),
        requested_series_ids=("afrr_requested_need_upward",),
        required_series_ids=("afrr_requested_need_upward",),
        normalization_version="rte-balancing-energy-v5.2-v1",
        raw_retention_policy="DIGEST_ONLY",
        mode="FETCH",
    )

    def failing_auth_transport(_request: object) -> object:
        raise RuntimeError(f"wire failure {client_id} {client_secret} {access_token}")

    with pytest.raises(RTEAuthenticationError) as captured:
        execute_rte_request(
            request,
            client_id=client_id,
            client_secret=client_secret,
            auth_transport=failing_auth_transport,
            data_transport=lambda _request: pytest.fail("data transport was reached"),
        )

    console = capsys.readouterr()
    observable = "".join(
        (
            repr(captured.value),
            str(captured.value),
            "".join(
                traceback.format_exception(
                    captured.type,
                    captured.value,
                    captured.tb,
                )
            ),
            console.out,
            console.err,
            caplog.text,
        )
    )
    for sentinel in (client_id, client_secret, access_token):
        assert sentinel not in observable
