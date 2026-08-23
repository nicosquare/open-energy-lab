"""Offline-verifiable RTE fetch and immutable refresh integration workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import urllib.request

import pytest

from open_energy_lab.market.restoration_artifact import (
    load_restoration_market_artifact,
)
from open_energy_lab.market.rte import (
    RTEHTTPResponse,
    RestorationRefreshStatus,
    build_rte_restoration_request,
    fetch_rte_restoration_data,
    refresh_rte_restoration_data,
)


FIXTURE = Path("tests/fixtures/restoration/synthetic_rte/afrr_success.json")
CLIENT_ID = "WORKFLOW-CLIENT-ID-SENTINEL-a3e1"
CLIENT_SECRET = "WORKFLOW-CLIENT-SECRET-SENTINEL-b7c2"
ACCESS_TOKEN = "WORKFLOW-ACCESS-TOKEN-SENTINEL-c9f4"
START = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
END = START + timedelta(hours=1)


class _AuthTransport:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        return RTEHTTPResponse(
            status=200,
            media_type="application/json",
            body=json.dumps(
                {"access_token": ACCESS_TOKEN, "token_type": "Bearer", "expires_in": 3600}
            ).encode(),
            headers={},
        )


class _DataTransport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        return RTEHTTPResponse(
            status=200,
            media_type="application/json",
            body=self.body,
            headers={"ETag": '"synthetic-rte-v1"'},
        )


def _clock_at(hour: int):
    return lambda: datetime(2026, 8, 23, hour, 0, tzinfo=UTC)


def _request(mode: str):
    from open_energy_lab.market.rte import RTE_AFRR_PROFILE

    return build_rte_restoration_request(
        resource="standard_afrr_data",
        requested_start_utc=START,
        requested_end_utc=END,
        requested_series_ids=RTE_AFRR_PROFILE.series_ids,
        required_series_ids=RTE_AFRR_PROFILE.required_series_ids,
        normalization_version="rte-balancing-energy-v5.2-v1",
        raw_retention_policy="DIGEST_ONLY",
        mode=mode,
    )


def _fetch(tmp_path: Path, body: bytes | None = None):
    return fetch_rte_restoration_data(
        _request("FETCH"),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        output_directory=tmp_path,
        auth_transport=_AuthTransport(),
        data_transport=_DataTransport(FIXTURE.read_bytes() if body is None else body),
        clock=_clock_at(12),
        sleeper=lambda _: None,
    )


def test_fetch_publishes_one_digest_backed_artifact_then_loads_fully_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = FIXTURE.read_bytes()
    result = _fetch(tmp_path)

    assert result.path.exists()
    assert result.path.name.endswith(f"{result.artifact.artifact_fingerprint}.json")
    assert result.artifact.source.value == "RTE"
    assert result.artifact.profile_id == "fr-rte-balancing-energy-v5.2-afrr-v1"
    assert result.artifact.request_evidence[0].raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.artifact.request_evidence[0].response_bytes == len(raw)
    assert result.artifact.raw_retention["policy"] == "DIGEST_ONLY"
    assert raw not in result.path.read_bytes()

    def _forbid(*args: object, **kwargs: object) -> object:
        raise AssertionError("offline workflow attempted network access")

    real_getenv = os.getenv

    def _guard_getenv(key: str, default: str | None = None) -> str | None:
        if key in {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}:
            raise AssertionError(f"offline workflow read {key}")
        return real_getenv(key, default)

    monkeypatch.setattr(socket, "create_connection", _forbid)
    monkeypatch.setattr(urllib.request, "urlopen", _forbid)
    monkeypatch.setattr(os, "getenv", _guard_getenv)
    loaded = load_restoration_market_artifact(result.path)
    assert loaded == result.artifact


def test_unchanged_refresh_writes_nothing_and_preserves_current_bytes(tmp_path: Path) -> None:
    fetched = _fetch(tmp_path)
    current_bytes = fetched.path.read_bytes()
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    refreshed = refresh_rte_restoration_data(
        fetched.artifact,
        _request("REFRESH"),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        output_directory=tmp_path,
        auth_transport=_AuthTransport(),
        data_transport=_DataTransport(FIXTURE.read_bytes()),
        clock=_clock_at(13),
        sleeper=lambda _: None,
    )

    assert refreshed.status is RestorationRefreshStatus.UNCHANGED
    assert refreshed.artifact is fetched.artifact
    assert refreshed.path is None
    assert fetched.path.read_bytes() == current_bytes
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_changed_refresh_creates_one_linked_successor_without_overwrite(tmp_path: Path) -> None:
    fetched = _fetch(tmp_path)
    current_bytes = fetched.path.read_bytes()
    changed_payload = json.loads(FIXTURE.read_bytes())
    changed_payload["picasso"]["picasso_mesures"][0]["upward_afrr_requested_need"] = 346.0
    changed_body = json.dumps(changed_payload, sort_keys=True).encode()

    refreshed = refresh_rte_restoration_data(
        fetched.artifact,
        _request("REFRESH"),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        output_directory=tmp_path,
        auth_transport=_AuthTransport(),
        data_transport=_DataTransport(changed_body),
        clock=_clock_at(14),
        sleeper=lambda _: None,
    )

    assert refreshed.status is RestorationRefreshStatus.CHANGED
    assert refreshed.path is not None and refreshed.path.exists()
    assert refreshed.artifact.predecessor_artifact_fingerprint == (
        fetched.artifact.artifact_fingerprint
    )
    assert refreshed.artifact.content_fingerprint != fetched.artifact.content_fingerprint
    assert fetched.path.read_bytes() == current_bytes
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_failed_refresh_preserves_current_and_publishes_nothing(tmp_path: Path) -> None:
    fetched = _fetch(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    malformed = Path(
        "tests/fixtures/restoration/synthetic_rte/afrr_malformed_root.json"
    ).read_bytes()

    with pytest.raises(Exception, match="picasso|root"):
        refresh_rte_restoration_data(
            fetched.artifact,
            _request("REFRESH"),
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            output_directory=tmp_path,
            auth_transport=_AuthTransport(),
            data_transport=_DataTransport(malformed),
            clock=_clock_at(15),
            sleeper=lambda _: None,
        )

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_credentials_tokens_and_headers_never_enter_results_files_or_errors(
    tmp_path: Path,
) -> None:
    result = _fetch(tmp_path)
    persisted = result.path.read_bytes()
    rendered = repr(result) + repr(result.artifact) + result.path.name
    sentinels = (
        CLIENT_ID,
        CLIENT_SECRET,
        ACCESS_TOKEN,
        f"Bearer {ACCESS_TOKEN}",
        "Authorization",
    )
    for sentinel in sentinels:
        assert sentinel.encode() not in persisted
        assert sentinel not in rendered
