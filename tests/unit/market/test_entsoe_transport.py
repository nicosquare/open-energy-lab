"""Contracts for token-safe synchronous ENTSO-E transport and retry behavior."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import importlib
import inspect
from types import ModuleType
from typing import Any

import pytest


SENTINEL_TOKEN = "OEL_SENTINEL_TOKEN_MUST_NEVER_ESCAPE_7f91"
PERIOD_START = datetime(2022, 8, 18, 22, tzinfo=UTC)
PERIOD_END = datetime(2022, 8, 19, 2, tzinfo=UTC)
ENDPOINT = "https://example.test/entsoe/api"


def _entsoe_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.market.entsoe")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.market.entsoe is not implemented; T018 must "
            "provide the token-safe transport contract",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    module = _entsoe_module()
    try:
        return getattr(module, name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.market.entsoe.{name} is not implemented",
            pytrace=False,
        )


def _request(**overrides: object):
    request_type = _require("EntsoeMarketDataRequest")
    values = {
        "requested_start_utc": PERIOD_START,
        "requested_end_utc": PERIOD_END,
        "source_endpoint": ENDPOINT,
        "raw_retention_policy": "digest_only",
        "normalization_version": "entsoe-fr-v1",
    }
    values.update(overrides)
    return request_type(**values)


def _window(**overrides: object):
    window_type = _require("EntsoeQueryWindow")
    values = {
        "window_id": "fr-a44-2022-08-19",
        "document_type": "A44",
        "process_type": "A01",
        "business_type": None,
        "area_parameter": "10YFR-RTE------C",
        "start_utc": PERIOD_START,
        "end_utc": PERIOD_END,
    }
    values.update(overrides)
    return window_type(**values)


def _response(
    status_code: int = 200,
    *,
    body: bytes = b"<synthetic />",
    headers: dict[str, str] | None = None,
):
    response_type = _require("EntsoeTransportResponse")
    return response_type(
        status_code=status_code,
        body=body,
        headers=headers or {"Content-Type": "application/xml"},
    )


class ScriptedTransport:
    """Synchronous transport double with a deterministic result script."""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def request(self, **kwargs: object):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _execute(
    transport: ScriptedTransport,
    *,
    api_token: str = SENTINEL_TOKEN,
    sleep: Callable[[float], None] | None = None,
    max_response_bytes: int = 1024,
):
    request_entsoe_window = _require("request_entsoe_window")
    arguments: dict[str, object] = {
        "request": _request(),
        "window": _window(),
        "api_token": api_token,
        "transport": transport,
        "max_response_bytes": max_response_bytes,
    }
    if sleep is not None:
        arguments["sleep"] = sleep
    return request_entsoe_window(**arguments)


def _error_text(error: BaseException) -> str:
    diagnostics = getattr(error, "diagnostics", ())
    return "\n".join((str(error), repr(error), repr(diagnostics)))


def test_request_and_france_profile_are_immutable_token_free_values() -> None:
    profile_type = _require("FranceEntsoeProfile")
    profile = profile_type()
    request = _request()

    assert profile.profile_id == "fr-day-ahead-symmetric-fcr-v1"
    assert profile.area_eic == "10YFR-RTE------C"
    assert profile.market_timezone == "Europe/Paris"
    assert profile.required_document_types == ("A44", "A81")
    assert request.profile == profile
    assert "token" not in request.__dataclass_fields__
    assert "credential" not in request.__dataclass_fields__
    assert SENTINEL_TOKEN not in repr(request)
    assert "securityToken" not in repr(request)
    with pytest.raises(FrozenInstanceError):
        request.source_endpoint = "https://mutated.invalid"  # type: ignore[misc]


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.test/entsoe/api",
        "https://example.test/entsoe/api?securityToken=forbidden",
        "https://example.test/entsoe/api#fragment",
        "//example.test/entsoe/api",
    ],
)
def test_request_accepts_only_an_https_origin_and_path(endpoint: str) -> None:
    validation_error = _require("EntsoeRequestValidationError")

    with pytest.raises(validation_error, match="HTTPS|query|fragment|endpoint"):
        _request(source_endpoint=endpoint)


def test_api_token_is_keyword_only_and_passed_separately_to_transport() -> None:
    operation = _require("request_entsoe_window")
    signature = inspect.signature(operation)
    assert signature.parameters["api_token"].kind is inspect.Parameter.KEYWORD_ONLY

    transport = ScriptedTransport([_response()])
    result = _execute(transport)

    assert result.body == b"<synthetic />"
    assert result.attempt_count == 1
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["endpoint"] == ENDPOINT
    assert call["api_token"] == SENTINEL_TOKEN
    assert SENTINEL_TOKEN not in repr(call["parameters"])
    assert "securityToken" not in repr(call["parameters"])
    assert SENTINEL_TOKEN not in repr(result)


def test_reserve_query_uses_required_daily_market_agreement_parameter() -> None:
    window = _window(
        document_type="A81",
        process_type="A52",
        business_type="B95",
        market_agreement_type="A01",
    )

    assert dict(window.request_parameters()) == {
        "documentType": "A81",
        "processType": "A52",
        "businessType": "B95",
        "Type_MarketAgreement.Type": "A01",
        "controlArea_Domain": "10YFR-RTE------C",
        "periodStart": "202208182200",
        "periodEnd": "202208190200",
    }


@pytest.mark.parametrize("token", ["", "   "])
def test_empty_authentication_fails_before_transport(token: str) -> None:
    authentication_error = _require("EntsoeAuthenticationError")
    transport = ScriptedTransport([_response()])

    with pytest.raises(authentication_error, match="authentication|token") as caught:
        _execute(transport, api_token=token)

    assert transport.calls == []
    assert "securityToken" not in _error_text(caught.value)


def test_response_size_ceiling_is_passed_to_transport_and_checked_again() -> None:
    too_large_error = _require("EntsoeResponseTooLargeError")
    transport = ScriptedTransport([_response(body=b"x" * 33)])

    with pytest.raises(too_large_error, match="size|byte|limit") as caught:
        _execute(transport, max_response_bytes=32)

    assert transport.calls[0]["max_response_bytes"] == 32
    assert b"x" * 33 not in str(caught.value).encode()
    assert SENTINEL_TOKEN not in _error_text(caught.value)


@pytest.mark.parametrize(
    "first_outcome",
    [
        TimeoutError("synthetic timeout"),
        ConnectionError("synthetic connection interruption"),
        pytest.param(408, id="http-408"),
        pytest.param(500, id="http-500"),
        pytest.param(503, id="http-503"),
    ],
)
def test_transient_failure_retries_and_then_returns_success(
    first_outcome: object,
) -> None:
    delays: list[float] = []
    if isinstance(first_outcome, int):
        first_outcome = _response(first_outcome)
    transport = ScriptedTransport([first_outcome, _response(body=b"<recovered />")])

    result = _execute(transport, sleep=delays.append)

    assert result.body == b"<recovered />"
    assert result.attempt_count == 2
    assert delays == [1.0]
    assert len(result.diagnostics) == 2
    assert result.diagnostics[0].attempt == 1
    assert result.diagnostics[0].delay_seconds == 1.0
    assert result.diagnostics[-1].final_outcome == "success"


def test_valid_retry_after_is_honored_for_rate_limiting() -> None:
    delays: list[float] = []
    transport = ScriptedTransport(
        [_response(429, headers={"Retry-After": "17"}), _response()]
    )

    result = _execute(transport, sleep=delays.append)

    assert delays == [17.0]
    assert result.diagnostics[0].status_code == 429
    assert result.diagnostics[0].delay_source == "retry-after"


@pytest.mark.parametrize("retry_after", ["invalid", "-1", "121", "1.5"])
def test_invalid_or_over_bound_retry_after_uses_deterministic_fallback(
    retry_after: str,
) -> None:
    delays: list[float] = []
    transport = ScriptedTransport(
        [_response(429, headers={"Retry-After": retry_after}), _response()]
    )

    result = _execute(transport, sleep=delays.append)

    assert delays == [1.0]
    assert result.diagnostics[0].delay_source == "fallback-invalid-retry-after"
    assert retry_after in result.diagnostics[0].detail


def test_three_transient_attempts_exhaust_with_one_and_two_second_delays() -> None:
    exhausted_error = _require("EntsoeTransientExhaustedError")
    delays: list[float] = []
    transport = ScriptedTransport([_response(503), _response(503), _response(503)])

    with pytest.raises(exhausted_error, match="A44|attempt|exhaust") as caught:
        _execute(transport, sleep=delays.append)

    assert len(transport.calls) == 3
    assert delays == [1.0, 2.0]
    diagnostics = caught.value.diagnostics
    assert [item.attempt for item in diagnostics] == [1, 2, 3]
    assert diagnostics[-1].final_outcome == "transient_exhausted"
    assert SENTINEL_TOKEN not in _error_text(caught.value)
    assert ENDPOINT not in _error_text(caught.value)


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_permanent_http_failures_receive_exactly_one_attempt(
    status_code: int,
) -> None:
    permanent_error = _require("EntsoePermanentTransportError")
    delays: list[float] = []
    transport = ScriptedTransport([_response(status_code)])

    with pytest.raises(permanent_error, match=str(status_code)) as caught:
        _execute(transport, sleep=delays.append)

    assert len(transport.calls) == 1
    assert delays == []
    assert caught.value.diagnostics[-1].final_outcome == "permanent_failure"
    assert SENTINEL_TOKEN not in _error_text(caught.value)


def test_unexpected_transport_exception_is_replaced_by_sanitized_failure() -> None:
    permanent_error = _require("EntsoePermanentTransportError")
    raw_message = f"wire failed at {ENDPOINT}?securityToken={SENTINEL_TOKEN}"
    transport = ScriptedTransport([RuntimeError(raw_message)])

    with pytest.raises(permanent_error) as caught:
        _execute(transport)

    diagnostic_text = _error_text(caught.value)
    assert SENTINEL_TOKEN not in diagnostic_text
    assert ENDPOINT not in diagnostic_text
    assert raw_message not in diagnostic_text
    assert "ENTSO-E" in diagnostic_text
    assert "A44" in diagnostic_text
    assert "fr-a44-2022-08-19" in diagnostic_text
    assert "fr-day-ahead-symmetric-fcr-v1" in diagnostic_text
    assert "2022-08-18" in diagnostic_text
