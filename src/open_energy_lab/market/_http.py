"""Bounded standard-library HTTP steps shared by the ENTSO-E and RTE clients.

Each client keeps its own request building, retry loop, and error reporting.
``urllib.request.urlopen`` is looked up at call time so tests can patch it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


class ResponseTooLarge(Exception):
    """The declared or read body exceeded the caller's byte ceiling."""

    def __init__(self, observed_bytes: int) -> None:
        super().__init__("bounded transport response exceeded the byte ceiling")
        self.observed_bytes = observed_bytes


@dataclass(frozen=True, slots=True)
class BoundedResponse:
    status: int
    headers: dict[str, str]
    media_type: str
    body: bytes


def header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup."""

    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return str(value)
    return None


def is_transient_status(status_code: int) -> bool:
    """Request timeout, rate limiting, and server errors are worth retrying."""

    return status_code in (408, 429) or 500 <= status_code <= 599


def _read(response: Any, max_bytes: int) -> BoundedResponse:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except (TypeError, ValueError):
            declared = -1
        if declared > max_bytes:
            raise ResponseTooLarge(declared)
    body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ResponseTooLarge(len(body))
    status = getattr(response, "status", None)
    return BoundedResponse(
        status=int(response.code if status is None else status),
        headers={str(key): str(value) for key, value in response.headers.items()},
        media_type=response.headers.get_content_type(),
        body=body,
    )


def open_bounded(
    request: urllib.request.Request, *, timeout: float, max_bytes: int
) -> BoundedResponse:
    """One HTTP call; error statuses are returned, redirects to plain HTTP refused."""

    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        with error:
            return _read(error, max_bytes)
    with response:
        if urllib.parse.urlsplit(response.geturl()).scheme.casefold() != "https":
            raise RuntimeError("transport refused a non-HTTPS redirect")
        return _read(response, max_bytes)
