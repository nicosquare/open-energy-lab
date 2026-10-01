"""Bounded HTTP steps shared by the ENTSO-E and RTE clients."""

from __future__ import annotations

from email.message import Message
import io
import urllib.error
import urllib.request

import pytest

from open_energy_lab.market import _http
from open_energy_lab.market.rte import RTETransportError, RTETransportRequest, _stdlib_transport


class _Response(io.BytesIO):
    def __init__(self, body: bytes, *, url: str = "https://example.test/x", headers=None, status=200):
        super().__init__(body)
        self.headers = Message()
        for key, value in (headers or {"Content-Type": "application/json"}).items():
            self.headers[key] = value
        self.status = status
        self._url = url

    def geturl(self) -> str:
        return self._url


def _patch(monkeypatch, outcome):
    def fake_urlopen(request, timeout):
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def _request() -> urllib.request.Request:
    return urllib.request.Request("https://example.test/x")


def test_returns_status_headers_media_type_and_body(monkeypatch) -> None:
    _patch(monkeypatch, _Response(b"{}", headers={"Content-Type": "application/json; charset=utf-8"}))
    response = _http.open_bounded(_request(), timeout=1.0, max_bytes=10)
    assert (response.status, response.media_type, response.body) == (200, "application/json", b"{}")
    assert _http.header(response.headers, "content-type") == "application/json; charset=utf-8"


def test_http_error_statuses_are_returned_not_raised(monkeypatch) -> None:
    headers = Message()
    headers["Retry-After"] = "2"
    error = urllib.error.HTTPError("https://example.test/x", 503, "busy", headers, io.BytesIO(b"later"))
    _patch(monkeypatch, error)
    response = _http.open_bounded(_request(), timeout=1.0, max_bytes=10)
    assert (response.status, response.body, response.headers["Retry-After"]) == (503, b"later", "2")
    assert _http.is_transient_status(503) and _http.is_transient_status(429)
    assert not _http.is_transient_status(404)


def test_refuses_redirect_to_plain_http(monkeypatch) -> None:
    _patch(monkeypatch, _Response(b"{}", url="http://example.test/x"))
    with pytest.raises(RuntimeError, match="non-HTTPS redirect"):
        _http.open_bounded(_request(), timeout=1.0, max_bytes=10)


@pytest.mark.parametrize(
    "response",
    [
        _Response(b"{}", headers={"Content-Length": "999"}),
        _Response(b"x" * 11),
    ],
)
def test_declared_or_read_size_above_the_ceiling_is_refused(monkeypatch, response) -> None:
    _patch(monkeypatch, response)
    with pytest.raises(_http.ResponseTooLarge):
        _http.open_bounded(_request(), timeout=1.0, max_bytes=10)


def test_rte_transport_maps_oversized_bodies_and_refuses_http_redirects(monkeypatch) -> None:
    request = RTETransportRequest(method="GET", url="https://example.test/x", headers={}, maximum_response_bytes=10)
    _patch(monkeypatch, _Response(b"{}", headers={"Content-Length": "999"}))
    with pytest.raises(RTETransportError, match="exceeds the configured maximum bytes"):
        _stdlib_transport(request)
    _patch(monkeypatch, _Response(b"{}", url="http://example.test/x"))
    with pytest.raises(RuntimeError, match="non-HTTPS redirect"):
        _stdlib_transport(request)
