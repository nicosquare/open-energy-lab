"""Operation-local OAuth and bounded RTE transport contracts."""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import json

import pytest

from open_energy_lab.market.rte import (
    RTE_MAX_RESPONSE_BYTES,
    RTEAuthenticationError,
    RTEHTTPResponse,
    RTETransportError,
    execute_rte_request,
)
from tests.unit.market.test_rte_request import _request


CLIENT_ID = "client-id-SENTINEL-4f3a"
CLIENT_SECRET = "client-secret-SENTINEL-9c2b"
ACCESS_TOKEN_1 = "access-token-SENTINEL-first-1a7e"
ACCESS_TOKEN_2 = "access-token-SENTINEL-renewed-8d5c"


def _auth_response(token: str = ACCESS_TOKEN_1, *, status: int = 200) -> RTEHTTPResponse:
    body = (
        json.dumps({"access_token": token, "token_type": "Bearer", "expires_in": 3600}).encode()
        if status == 200
        else b'{"error":"synthetic_auth_rejection"}'
    )
    return RTEHTTPResponse(
        status=status,
        media_type="application/json",
        body=body,
        headers={},
    )


def _data_response(
    *,
    status: int = 200,
    body: bytes = b'{"picasso":{"synthetic":true}}',
    headers: dict[str, str] | None = None,
    media_type: str = "application/json; charset=utf-8",
) -> RTEHTTPResponse:
    return RTEHTTPResponse(
        status=status,
        media_type=media_type,
        body=body,
        headers={} if headers is None else headers,
    )


class _SequenceTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("transport received an unexpected extra attempt")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _fixed_clock() -> datetime:
    return datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def test_basic_and_bearer_values_are_confined_to_ephemeral_transport_requests() -> None:
    auth = _SequenceTransport([_auth_response()])
    data_body = b'{"picasso":{"transport":"success"}}'
    data = _SequenceTransport([_data_response(body=data_body)])

    result = execute_rte_request(
        _request(),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        auth_transport=auth,
        data_transport=data,
        clock=_fixed_clock,
        sleeper=lambda _: None,
    )

    assert len(result) == 1
    assert auth.requests[0].method == "POST"
    assert auth.requests[0].url.endswith("/token/oauth/")
    basic_header = auth.requests[0].headers["Authorization"]
    assert basic_header.startswith("Basic ")
    assert base64.b64decode(basic_header.removeprefix("Basic ")).decode() == (
        f"{CLIENT_ID}:{CLIENT_SECRET}"
    )
    assert data.requests[0].method == "GET"
    assert data.requests[0].headers["Authorization"] == f"Bearer {ACCESS_TOKEN_1}"
    assert "start_date=" in data.requests[0].url
    assert "end_date=" in data.requests[0].url
    assert result[0].body == data_body
    assert result[0].raw_sha256 == hashlib.sha256(data_body).hexdigest()
    assert result[0].attempt_count == 1
    assert result[0].retrieved_at_utc == "2026-08-23T12:00:00Z"

    persisted_views = repr(result) + repr(auth.requests) + repr(data.requests)
    for sentinel in (CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN_1, basic_header):
        assert sentinel not in persisted_views


def test_oauth_response_is_never_market_evidence_or_digest_input() -> None:
    auth_response = _auth_response()
    data_body = b'{"mari":{"market":"only"}}'
    result = execute_rte_request(
        _request(),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        auth_transport=_SequenceTransport([auth_response]),
        data_transport=_SequenceTransport([_data_response(body=data_body)]),
        clock=_fixed_clock,
        sleeper=lambda _: None,
    )

    assert result[0].raw_sha256 == hashlib.sha256(data_body).hexdigest()
    assert result[0].raw_sha256 != hashlib.sha256(auth_response.body).hexdigest()
    assert ACCESS_TOKEN_1.encode() not in result[0].body


def test_expired_data_token_is_renewed_once_in_memory() -> None:
    auth = _SequenceTransport([_auth_response(ACCESS_TOKEN_1), _auth_response(ACCESS_TOKEN_2)])
    data = _SequenceTransport(
        [_data_response(status=401), _data_response(body=b'{"renewed":true}')]
    )

    result = execute_rte_request(
        _request(),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        auth_transport=auth,
        data_transport=data,
        clock=_fixed_clock,
        sleeper=lambda _: None,
    )

    assert len(auth.requests) == 2
    assert len(data.requests) == 2
    assert data.requests[0].headers["Authorization"] == f"Bearer {ACCESS_TOKEN_1}"
    assert data.requests[1].headers["Authorization"] == f"Bearer {ACCESS_TOKEN_2}"
    assert result[0].attempt_count == 2


def test_transient_statuses_and_timeout_retry_at_most_three_total_attempts() -> None:
    sleeps: list[float] = []
    data = _SequenceTransport(
        [
            TimeoutError("synthetic timeout body must not escape"),
            _data_response(status=429, headers={"Retry-After": "2"}),
            _data_response(body=b'{"third_attempt":true}'),
        ]
    )
    result = execute_rte_request(
        _request(),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        auth_transport=_SequenceTransport([_auth_response()]),
        data_transport=data,
        clock=_fixed_clock,
        sleeper=sleeps.append,
    )

    assert len(data.requests) == 3
    assert result[0].attempt_count == 3
    assert sleeps == [1.0, 2.0]

    failing = _SequenceTransport([_data_response(status=503) for _ in range(3)])
    with pytest.raises(RTETransportError, match="3 attempts|transient|503"):
        execute_rte_request(
            _request(),
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            auth_transport=_SequenceTransport([_auth_response()]),
            data_transport=failing,
            clock=_fixed_clock,
            sleeper=lambda _: None,
        )
    assert len(failing.requests) == 3


def test_valid_retry_after_is_bounded_and_invalid_value_uses_backoff() -> None:
    sleeps: list[float] = []
    data = _SequenceTransport(
        [
            _data_response(status=429, headers={"Retry-After": "999999"}),
            _data_response(status=503, headers={"Retry-After": "invalid"}),
            _data_response(),
        ]
    )
    execute_rte_request(
        _request(),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        auth_transport=_SequenceTransport([_auth_response()]),
        data_transport=data,
        clock=_fixed_clock,
        sleeper=sleeps.append,
    )

    assert sleeps == [30.0, 2.0]


def test_authentication_and_permanent_client_fail_after_one_attempt() -> None:
    auth = _SequenceTransport([_auth_response(status=401)])
    with pytest.raises(RTEAuthenticationError, match="authentication|one attempt|401"):
        execute_rte_request(
            _request(),
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            auth_transport=auth,
            data_transport=_SequenceTransport([]),
            clock=_fixed_clock,
            sleeper=lambda _: None,
        )
    assert len(auth.requests) == 1

    data = _SequenceTransport([_data_response(status=400)])
    with pytest.raises(RTETransportError, match="permanent|400|one attempt"):
        execute_rte_request(
            _request(),
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            auth_transport=_SequenceTransport([_auth_response()]),
            data_transport=data,
            clock=_fixed_clock,
            sleeper=lambda _: None,
        )
    assert len(data.requests) == 1


def test_bounded_body_and_media_type_fail_without_exposing_raw_content() -> None:
    oversized = b"x" * (RTE_MAX_RESPONSE_BYTES + 1)
    with pytest.raises(RTETransportError, match="maximum|body|bytes") as oversized_error:
        execute_rte_request(
            _request(),
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            auth_transport=_SequenceTransport([_auth_response()]),
            data_transport=_SequenceTransport([_data_response(body=oversized)]),
            clock=_fixed_clock,
            sleeper=lambda _: None,
        )
    assert "xxxx" not in str(oversized_error.value)

    raw_sentinel = b"RAW-BODY-SENTINEL-must-not-escape"
    with pytest.raises(RTETransportError, match="media|JSON") as media_error:
        execute_rte_request(
            _request(),
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            auth_transport=_SequenceTransport([_auth_response()]),
            data_transport=_SequenceTransport(
                [_data_response(body=raw_sentinel, media_type="text/html")]
            ),
            clock=_fixed_clock,
            sleeper=lambda _: None,
        )
    assert raw_sentinel.decode() not in str(media_error.value)


def test_all_transport_errors_redact_client_token_header_and_raw_body_sentinels() -> None:
    raw_body = "RAW-ERROR-BODY-SENTINEL-7b9d"
    with pytest.raises(RTETransportError) as captured:
        execute_rte_request(
            _request(),
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            auth_transport=_SequenceTransport([_auth_response()]),
            data_transport=_SequenceTransport(
                [_data_response(status=400, body=raw_body.encode())]
            ),
            clock=_fixed_clock,
            sleeper=lambda _: None,
        )

    rendered = repr(captured.value) + str(captured.value)
    for sentinel in (CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN_1, raw_body, "Authorization"):
        assert sentinel not in rendered
