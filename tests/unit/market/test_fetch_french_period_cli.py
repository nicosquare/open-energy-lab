"""Credential-loading tests for the explicit ENTSO-E example consumer."""

from __future__ import annotations

import os
from pathlib import Path
import runpy

import pytest


SCRIPT = (
    Path(__file__).parents[3]
    / "examples"
    / "bess_stacked_services"
    / "fetch_french_period.py"
)
NAMESPACE = runpy.run_path(str(SCRIPT))
api_token = NAMESPACE["_api_token"]
token_from_env_file = NAMESPACE["_token_from_env_file"]


def test_exported_token_takes_precedence_without_reading_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ENTSOE_API_TOKEN", "exported-secret")

    assert api_token(tmp_path / "does-not-exist.env") == "exported-secret"


@pytest.mark.parametrize(
    "declaration",
    (
        "ENTSOE_API_TOKEN=file-secret",
        "ENTSOE_API_TOKEN='file-secret'",
        'export ENTSOE_API_TOKEN="file-secret"',
    ),
)
def test_dotenv_token_is_read_without_mutating_the_environment(
    declaration: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ENTSOE_API_TOKEN", raising=False)
    path = tmp_path / ".env"
    path.write_text(f"# local credential\n{declaration}\n", encoding="utf-8")

    assert api_token(path) == "file-secret"
    assert "ENTSOE_API_TOKEN" not in os.environ


@pytest.mark.parametrize(
    "contents, message",
    (
        ("UNRELATED=value\n", "does not define"),
        ("ENTSOE_API_TOKEN=\n", "non-empty"),
        (
            "ENTSOE_API_TOKEN=first\nENTSOE_API_TOKEN=second\n",
            "duplicate",
        ),
        ('ENTSOE_API_TOKEN="unterminated\n', "unmatched quotes"),
    ),
)
def test_invalid_dotenv_never_echoes_a_declared_value(
    contents: str,
    message: str,
    tmp_path: Path,
) -> None:
    path = tmp_path / ".env"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message) as captured:
        token_from_env_file(path)

    assert "first" not in str(captured.value)
    assert "second" not in str(captured.value)
    assert "unterminated" not in str(captured.value)
