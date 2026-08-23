"""Credential and operation-boundary tests for the explicit RTE consumer."""

from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest


SCRIPT = (
    Path(__file__).parents[3]
    / "examples"
    / "restoration_services"
    / "fetch_rte_period.py"
)


def _namespace() -> dict[str, object]:
    return runpy.run_path(str(SCRIPT))


def test_script_import_defines_consumers_without_reading_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_get = os.environ.get

    def _guarded_get(key: str, default: str | None = None) -> str | None:
        if key in {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}:
            raise AssertionError(f"import read credential variable {key}")
        return real_get(key, default)

    monkeypatch.setattr(os.environ, "get", _guarded_get)

    namespace = _namespace()

    assert callable(namespace["main"])
    assert callable(namespace["_rte_credentials"])


def test_exported_rte_credentials_take_precedence_without_reading_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    credentials = namespace["_rte_credentials"]
    monkeypatch.setenv("RTE_CLIENT_ID", "exported-client")
    monkeypatch.setenv("RTE_CLIENT_SECRET", "exported-secret")

    assert credentials(tmp_path / "does-not-exist.env") == (
        "exported-client",
        "exported-secret",
    )


@pytest.mark.parametrize(
    "client_declaration,secret_declaration",
    (
        ("RTE_CLIENT_ID=file-client", "RTE_CLIENT_SECRET=file-secret"),
        ("RTE_CLIENT_ID='file-client'", 'RTE_CLIENT_SECRET="file-secret"'),
        (
            "export RTE_CLIENT_ID=file-client",
            "export RTE_CLIENT_SECRET=file-secret",
        ),
    ),
)
def test_dotenv_credentials_are_allowlisted_without_environment_mutation(
    client_declaration: str,
    secret_declaration: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    credentials = namespace["_rte_credentials"]
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(
            (
                "# explicit live acquisition only",
                "ENTSOE_API_TOKEN=ignored-by-rte-consumer",
                client_declaration,
                secret_declaration,
                "",
            )
        ),
        encoding="utf-8",
    )

    assert credentials(path) == ("file-client", "file-secret")
    assert "RTE_CLIENT_ID" not in os.environ
    assert "RTE_CLIENT_SECRET" not in os.environ


def test_exported_value_overrides_only_its_corresponding_dotenv_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    credentials = namespace["_rte_credentials"]
    monkeypatch.setenv("RTE_CLIENT_ID", "exported-client")
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "RTE_CLIENT_ID=file-client\nRTE_CLIENT_SECRET=file-secret\n",
        encoding="utf-8",
    )

    assert credentials(path) == ("exported-client", "file-secret")
    assert os.environ["RTE_CLIENT_ID"] == "exported-client"
    assert "RTE_CLIENT_SECRET" not in os.environ


def test_dotenv_values_are_literal_and_never_interpolated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    credentials = namespace["_rte_credentials"]
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-expanded")
    path = tmp_path / ".env"
    path.write_text(
        "RTE_CLIENT_ID=literal-client\n"
        "RTE_CLIENT_SECRET=${UNRELATED_SECRET}\n",
        encoding="utf-8",
    )

    assert credentials(path) == ("literal-client", "${UNRELATED_SECRET}")
    assert "RTE_CLIENT_ID" not in os.environ
    assert "RTE_CLIENT_SECRET" not in os.environ


@pytest.mark.parametrize(
    "contents,message",
    (
        ("UNRELATED=value\n", "not allowlisted"),
        ("RTE_CLIENT_ID\n", "KEY=VALUE"),
        ("RTE_CLIENT_ID=\nRTE_CLIENT_SECRET=secret\n", "non-empty"),
        (
            "RTE_CLIENT_ID=first\nRTE_CLIENT_ID=second\n"
            "RTE_CLIENT_SECRET=secret\n",
            "duplicate",
        ),
        (
            'RTE_CLIENT_ID="unterminated\nRTE_CLIENT_SECRET=secret\n',
            "unmatched quotes",
        ),
    ),
)
def test_invalid_dotenv_diagnostics_never_echo_declared_values(
    contents: str,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    read_values = namespace["_read_dotenv_values"]
    path = tmp_path / ".env"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message) as captured:
        read_values(path, requested_keys=("RTE_CLIENT_ID", "RTE_CLIENT_SECRET"))

    rendered = str(captured.value)
    for sentinel in ("value", "first", "second", "unterminated", "secret"):
        assert sentinel not in rendered


def test_invalid_request_is_rejected_before_credentials_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    main = namespace["main"]

    def _forbid_credentials(path: Path) -> tuple[str, str]:
        raise AssertionError(f"credential loader called for invalid request: {path}")

    monkeypatch.setitem(main.__globals__, "_rte_credentials", _forbid_credentials)

    result = main(
        (
            "--resource",
            "standard_afrr_data",
            "--start-utc",
            "2026-08-20T00:07:00Z",
            "--end-utc",
            "2026-08-20T01:00:00Z",
            "--output-dir",
            str(tmp_path),
        )
    )

    assert result == 2
    assert "input validation failed" in capsys.readouterr().err


def test_fetch_reads_credentials_inside_selected_operation_and_prints_no_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    main = namespace["main"]
    observed: dict[str, object] = {}
    client_id = "CLI-CLIENT-ID-SENTINEL"
    client_secret = "CLI-CLIENT-SECRET-SENTINEL"

    def _credentials(path: Path) -> tuple[str, str]:
        observed["env_file"] = path
        return client_id, client_secret

    def _fetch(request, **kwargs):
        observed["request"] = request
        observed["credentials"] = (kwargs["client_id"], kwargs["client_secret"])
        observed["output_directory"] = kwargs["output_directory"]
        return SimpleNamespace(
            path=tmp_path / "artifact.json",
            artifact=SimpleNamespace(
                content_fingerprint="a" * 64,
                artifact_fingerprint="b" * 64,
            ),
        )

    monkeypatch.setitem(main.__globals__, "_rte_credentials", _credentials)
    monkeypatch.setitem(main.__globals__, "fetch_rte_restoration_data", _fetch)

    result = main(
        (
            "--resource",
            "standard_afrr_data",
            "--start-utc",
            "2026-08-20T00:00:00Z",
            "--end-utc",
            "2026-08-20T01:00:00Z",
            "--output-dir",
            str(tmp_path),
            "--env-file",
            str(tmp_path / ".env"),
        )
    )

    assert result == 0
    request = observed["request"]
    assert request.mode.value == "FETCH"
    assert request.profile.resource == "standard_afrr_data"
    assert request.requested_start_utc == datetime(2026, 8, 20, tzinfo=UTC)
    assert observed["credentials"] == (client_id, client_secret)
    assert observed["output_directory"] == tmp_path
    output = capsys.readouterr()
    assert "outcome=created" in output.out
    assert "artifact_fingerprint=" in output.out
    assert client_id not in output.out + output.err
    assert client_secret not in output.out + output.err


def test_refresh_loads_current_artifact_and_uses_refresh_request(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    namespace = _namespace()
    main = namespace["main"]
    current = object()
    current_path = tmp_path / "current.json"
    observed: dict[str, object] = {}

    monkeypatch.setitem(
        main.__globals__, "load_restoration_market_artifact", lambda path: current
    )
    monkeypatch.setitem(
        main.__globals__, "_rte_credentials", lambda path: ("client", "secret")
    )

    def _refresh(artifact, request, **kwargs):
        observed["artifact"] = artifact
        observed["request"] = request
        return SimpleNamespace(
            status=SimpleNamespace(value="UNCHANGED"),
            artifact=SimpleNamespace(artifact_fingerprint="c" * 64),
            path=None,
        )

    monkeypatch.setitem(main.__globals__, "refresh_rte_restoration_data", _refresh)

    result = main(
        (
            "--resource",
            "standard_mfrr_data",
            "--start-utc",
            "2026-08-15T10:15:00Z",
            "--end-utc",
            "2026-08-15T10:30:00Z",
            "--output-dir",
            str(tmp_path),
            "--refresh-from",
            str(current_path),
        )
    )

    assert result == 0
    assert observed["artifact"] is current
    assert observed["request"].mode.value == "REFRESH"
    assert "outcome=unchanged" in capsys.readouterr().out
