"""Explicit, token-safe ENTSO-E acquisition for the France market profile.

This module is intentionally outside the import-light package root. Network
access happens only when a caller invokes an explicit operation and supplies a
credential as a keyword-only argument.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
import hashlib
import math
import os
from pathlib import Path
import tempfile
import time
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from .artifact import (
    FRANCE_AREA_EIC,
    FRANCE_PROFILE_ID,
    MARKET_DATA_SCHEMA_VERSION,
    MarketArtifactIntegrityError,
    MarketArtifactPublicationError,
    MarketArtifactValidationError,
    MarketDataArtifact,
    MarketObservation,
    MarketSeries,
    RawResponseEvidence,
    SourceQueryWindow,
    SourceDocumentEvidence,
    build_market_data_artifact,
    write_market_data_artifact,
)
from .time import CanonicalInterval, FRANCE_MARKET_TIMEZONE, parse_iso8601_duration


ENTSOE_SOURCE_NAME = "ENTSO-E Transparency Platform"
DEFAULT_ENTSOE_ENDPOINT = "https://web-api.tp.entsoe.eu/api"
DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_TRANSPORT_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 120
EXPECTED_FRANCE_CONTRACT = "France A44/A81/A89 market-data contract v1"

_DOCUMENT_SERIES = {
    "A44": "day_ahead_price",
    "A81": "fcr_contracted_volume",
    "A89": "fcr_capacity_price",
}


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_utc_datetime(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise EntsoeRequestValidationError(f"{field_name} must be an aware UTC datetime")
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None or offset != timedelta(0):
        raise EntsoeRequestValidationError(f"{field_name} must be an aware UTC datetime")
    return value.astimezone(UTC)


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EntsoeRequestValidationError(f"{field_name} must be a non-empty string")
    return value


class EntsoeRequestValidationError(ValueError):
    """Raised when a token-free request or query window is invalid."""


@dataclass(frozen=True, slots=True)
class FranceEntsoeProfile:
    """Closed v1 semantic profile for French day-ahead and symmetric FCR."""

    profile_id: str = FRANCE_PROFILE_ID
    area_eic: str = FRANCE_AREA_EIC
    market_timezone: str = FRANCE_MARKET_TIMEZONE
    required_document_types: tuple[str, ...] = ("A44", "A81", "A89")

    def __post_init__(self) -> None:
        if self.profile_id != FRANCE_PROFILE_ID:
            raise EntsoeRequestValidationError(
                f"profile_id must be {FRANCE_PROFILE_ID}"
            )
        if self.area_eic != FRANCE_AREA_EIC:
            raise EntsoeRequestValidationError(f"area_eic must be {FRANCE_AREA_EIC}")
        if self.market_timezone != FRANCE_MARKET_TIMEZONE:
            raise EntsoeRequestValidationError(
                f"market_timezone must be {FRANCE_MARKET_TIMEZONE}"
            )
        if self.required_document_types != ("A44", "A81", "A89"):
            raise EntsoeRequestValidationError(
                "required_document_types must be exactly A44, A81, and A89"
            )


def _validate_https_endpoint(value: object) -> str:
    endpoint = _non_empty(value, field_name="source_endpoint")
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise EntsoeRequestValidationError(
            "source_endpoint must be an absolute HTTPS origin and path"
        )
    if parsed.username is not None or parsed.password is not None:
        raise EntsoeRequestValidationError(
            "source_endpoint must not contain user information or credentials"
        )
    if parsed.query or parsed.fragment:
        raise EntsoeRequestValidationError(
            "source_endpoint must contain only an HTTPS origin and path, not a query or fragment"
        )
    return endpoint


@dataclass(frozen=True, slots=True)
class EntsoeMarketDataRequest:
    """Token-free description of one explicit France source operation."""

    requested_start_utc: datetime
    requested_end_utc: datetime
    source_endpoint: str
    raw_retention_policy: str
    normalization_version: str
    profile: FranceEntsoeProfile = field(default_factory=FranceEntsoeProfile)

    def __post_init__(self) -> None:
        start = _require_utc_datetime(
            self.requested_start_utc,
            field_name="requested_start_utc",
        )
        end = _require_utc_datetime(
            self.requested_end_utc,
            field_name="requested_end_utc",
        )
        if start >= end:
            raise EntsoeRequestValidationError(
                "requested_start_utc must be before requested_end_utc"
            )
        endpoint = _validate_https_endpoint(self.source_endpoint)
        if self.raw_retention_policy not in ("digest_only", "permitted_sidecar"):
            raise EntsoeRequestValidationError(
                "raw_retention_policy must be digest_only or permitted_sidecar"
            )
        normalization_version = _non_empty(
            self.normalization_version,
            field_name="normalization_version",
        )
        if not isinstance(self.profile, FranceEntsoeProfile):
            raise EntsoeRequestValidationError(
                "profile must be the closed FranceEntsoeProfile"
            )
        object.__setattr__(self, "requested_start_utc", start)
        object.__setattr__(self, "requested_end_utc", end)
        object.__setattr__(self, "source_endpoint", endpoint)
        object.__setattr__(self, "normalization_version", normalization_version)


@dataclass(frozen=True, slots=True)
class EntsoeQueryWindow:
    """One token-free source query for a required ENTSO-E document type."""

    window_id: str
    document_type: str
    process_type: str | None
    business_type: str | None
    area_parameter: str
    start_utc: datetime
    end_utc: datetime

    def __post_init__(self) -> None:
        window_id = _non_empty(self.window_id, field_name="window_id")
        if self.document_type not in _DOCUMENT_SERIES:
            raise EntsoeRequestValidationError(
                "document_type must be A44, A81, or A89"
            )
        expected_process = "A01" if self.document_type == "A44" else "A34"
        if self.process_type != expected_process:
            raise EntsoeRequestValidationError(
                f"{self.document_type} process_type must be {expected_process}"
            )
        expected_business = None if self.document_type == "A44" else "A95"
        if self.business_type != expected_business:
            raise EntsoeRequestValidationError(
                f"{self.document_type} business_type must be {expected_business!r}"
            )
        if self.area_parameter != FRANCE_AREA_EIC:
            raise EntsoeRequestValidationError(
                f"area_parameter must be {FRANCE_AREA_EIC}"
            )
        start = _require_utc_datetime(self.start_utc, field_name="start_utc")
        end = _require_utc_datetime(self.end_utc, field_name="end_utc")
        if start >= end:
            raise EntsoeRequestValidationError("window start_utc must precede end_utc")
        object.__setattr__(self, "window_id", window_id)
        object.__setattr__(self, "start_utc", start)
        object.__setattr__(self, "end_utc", end)

    @property
    def required_series(self) -> str:
        return _DOCUMENT_SERIES[self.document_type]

    def request_parameters(self) -> Mapping[str, str]:
        """Return the semantic ENTSO-E query without the API token."""

        parameters = {
            "documentType": self.document_type,
            "processType": self.process_type or "",
            "periodStart": self.start_utc.strftime("%Y%m%d%H%M"),
            "periodEnd": self.end_utc.strftime("%Y%m%d%H%M"),
        }
        if self.business_type is not None:
            parameters["businessType"] = self.business_type
        if self.document_type == "A44":
            parameters["in_Domain"] = self.area_parameter
            parameters["out_Domain"] = self.area_parameter
        else:
            parameters["controlArea_Domain"] = self.area_parameter
        return MappingProxyType(parameters)


@dataclass(frozen=True, slots=True)
class EntsoeTransportResponse:
    """Bounded response returned by an injected synchronous transport."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]

    def __post_init__(self) -> None:
        if isinstance(self.status_code, bool) or not isinstance(self.status_code, int):
            raise TypeError("status_code must be an integer")
        if not isinstance(self.body, bytes):
            raise TypeError("body must be bytes")
        normalized_headers = {
            str(name): str(value) for name, value in self.headers.items()
        }
        object.__setattr__(self, "headers", MappingProxyType(normalized_headers))

    def header(self, name: str) -> str | None:
        target = name.casefold()
        for candidate, value in self.headers.items():
            if candidate.casefold() == target:
                return value
        return None

    @property
    def media_type(self) -> str:
        content_type = self.header("Content-Type") or "application/xml"
        return content_type.partition(";")[0].strip().casefold()


@runtime_checkable
class EntsoeTransport(Protocol):
    """Injected synchronous transport boundary used by fetch and refresh."""

    def request(
        self,
        *,
        endpoint: str,
        parameters: Mapping[str, str],
        api_token: str,
        max_response_bytes: int,
    ) -> EntsoeTransportResponse: ...


class _TransportBodyTooLarge(Exception):
    def __init__(self, observed_bytes: int) -> None:
        super().__init__("bounded transport response exceeded the byte ceiling")
        self.observed_bytes = observed_bytes


class UrllibEntsoeTransport:
    """Standard-library HTTPS transport with bounded response reads."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _read_bounded(response: Any, max_response_bytes: int) -> bytes:
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except (TypeError, ValueError):
                declared_size = -1
            if declared_size > max_response_bytes:
                raise _TransportBodyTooLarge(declared_size)
        body = response.read(max_response_bytes + 1)
        if len(body) > max_response_bytes:
            raise _TransportBodyTooLarge(len(body))
        return body

    def request(
        self,
        *,
        endpoint: str,
        parameters: Mapping[str, str],
        api_token: str,
        max_response_bytes: int,
    ) -> EntsoeTransportResponse:
        endpoint = _validate_https_endpoint(endpoint)
        wire_parameters = dict(parameters)
        wire_parameters["securityToken"] = api_token
        wire_url = f"{endpoint}?{urllib.parse.urlencode(wire_parameters)}"
        wire_request = urllib.request.Request(
            wire_url,
            headers={
                "Accept": "application/xml, text/xml",
                "User-Agent": "open-energy-lab/entsoe-market-data-v1",
            },
            method="GET",
        )
        try:
            response = urllib.request.urlopen(
                wire_request,
                timeout=self._timeout_seconds,
            )
        except urllib.error.HTTPError as error:
            with error:
                body = self._read_bounded(error, max_response_bytes)
                return EntsoeTransportResponse(
                    status_code=error.code,
                    body=body,
                    headers=dict(error.headers.items()),
                )
        with response:
            final_url = response.geturl()
            if urllib.parse.urlsplit(final_url).scheme.casefold() != "https":
                raise RuntimeError("transport refused a non-HTTPS redirect")
            body = self._read_bounded(response, max_response_bytes)
            return EntsoeTransportResponse(
                status_code=response.status,
                body=body,
                headers=dict(response.headers.items()),
            )


@dataclass(frozen=True, slots=True)
class EntsoeDiagnostic:
    """Sanitized structured diagnostic shared by transport and parsing."""

    source: str
    document_type: str
    required_series: str
    window_id: str
    requested_start_utc: str
    requested_end_utc: str
    expected_profile: str
    expected_contract: str
    final_outcome: str
    attempt: int | None = None
    status_code: int | None = None
    failure_class: str | None = None
    delay_seconds: float | None = None
    delay_source: str | None = None
    detail: str = ""
    observed_start_utc: str | None = None
    observed_end_utc: str | None = None
    observed_resolution: str | None = None
    observed_unit: str | None = None

    @property
    def final_status(self) -> str:
        return self.final_outcome

    @property
    def attempt_count(self) -> int | None:
        return self.attempt

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "document_type": self.document_type,
            "required_series": self.required_series,
            "window_id": self.window_id,
            "requested_start_utc": self.requested_start_utc,
            "requested_end_utc": self.requested_end_utc,
            "expected_profile": self.expected_profile,
            "expected_contract": self.expected_contract,
            "final_outcome": self.final_outcome,
            "final_status": self.final_status,
            "attempt": self.attempt,
            "attempt_count": self.attempt_count,
            "status_code": self.status_code,
            "failure_class": self.failure_class,
            "delay_seconds": self.delay_seconds,
            "delay_source": self.delay_source,
            "detail": self.detail,
            "observed_start_utc": self.observed_start_utc,
            "observed_end_utc": self.observed_end_utc,
            "observed_resolution": self.observed_resolution,
            "observed_unit": self.observed_unit,
        }


class EntsoeAcquisitionError(RuntimeError):
    """Base class for sanitized typed ENTSO-E acquisition failures."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: tuple[EntsoeDiagnostic, ...] = (),
        diagnostic: EntsoeDiagnostic | None = None,
    ) -> None:
        super().__init__(message)
        if diagnostic is not None and not diagnostics:
            diagnostics = (diagnostic,)
        self.diagnostics = diagnostics
        self.diagnostic = diagnostic or (diagnostics[-1] if diagnostics else None)


class EntsoeAuthenticationError(EntsoeAcquisitionError):
    """Raised before transport when the caller credential is empty."""


class EntsoePermanentTransportError(EntsoeAcquisitionError):
    """Raised after one non-retryable HTTP or transport failure."""


class EntsoeTransientExhaustedError(EntsoeAcquisitionError):
    """Raised after exactly three transient transport attempts fail."""


class EntsoeResponseTooLargeError(EntsoePermanentTransportError):
    """Raised when a response exceeds the configured byte ceiling."""


@dataclass(frozen=True, slots=True)
class EntsoeTransportResult:
    """Successful bounded response and its complete attempt diagnostics."""

    status_code: int
    body: bytes
    media_type: str
    attempt_count: int
    diagnostics: tuple[EntsoeDiagnostic, ...]


def _diagnostic(
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    *,
    attempt: int,
    final_outcome: str,
    status_code: int | None = None,
    failure_class: str | None = None,
    delay_seconds: float | None = None,
    delay_source: str | None = None,
    detail: str = "",
) -> EntsoeDiagnostic:
    return EntsoeDiagnostic(
        source=ENTSOE_SOURCE_NAME,
        document_type=window.document_type,
        required_series=window.required_series,
        window_id=window.window_id,
        requested_start_utc=_format_utc(request.requested_start_utc),
        requested_end_utc=_format_utc(request.requested_end_utc),
        expected_profile=request.profile.profile_id,
        expected_contract=EXPECTED_FRANCE_CONTRACT,
        final_outcome=final_outcome,
        attempt=attempt,
        status_code=status_code,
        failure_class=failure_class,
        delay_seconds=delay_seconds,
        delay_source=delay_source,
        detail=detail,
    )


def _failure_message(window: EntsoeQueryWindow, request: EntsoeMarketDataRequest, outcome: str) -> str:
    return (
        f"{ENTSOE_SOURCE_NAME} {window.document_type} request {window.window_id} "
        f"for {window.required_series} over "
        f"[{_format_utc(request.requested_start_utc)}, "
        f"{_format_utc(request.requested_end_utc)}) under profile "
        f"{request.profile.profile_id} failed: {outcome}"
    )


def _retry_after(response: EntsoeTransportResponse, attempt: int) -> tuple[float, str, str]:
    fallback = float(attempt)
    raw_value = response.header("Retry-After")
    if raw_value is None:
        return fallback, "deterministic-backoff", ""
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return (
            fallback,
            "fallback-invalid-retry-after",
            f"invalid Retry-After value {raw_value!r}",
        )
    if parsed < 0 or parsed > MAX_RETRY_AFTER_SECONDS or str(parsed) != raw_value.strip():
        return (
            fallback,
            "fallback-invalid-retry-after",
            f"invalid Retry-After value {raw_value!r}",
        )
    return float(parsed), "retry-after", ""


def _is_transient_status(status_code: int) -> bool:
    return status_code in (408, 429) or 500 <= status_code <= 599


def request_entsoe_window(
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    api_token: str,
    transport: EntsoeTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> EntsoeTransportResult:
    """Execute one bounded source window with the fixed three-attempt policy."""

    if not isinstance(request, EntsoeMarketDataRequest):
        raise TypeError("request must be an EntsoeMarketDataRequest")
    if not isinstance(window, EntsoeQueryWindow):
        raise TypeError("window must be an EntsoeQueryWindow")
    if not isinstance(api_token, str) or not api_token.strip():
        raise EntsoeAuthenticationError(
            "ENTSO-E authentication token must be provided explicitly"
        )
    if isinstance(max_response_bytes, bool) or not isinstance(max_response_bytes, int):
        raise EntsoeRequestValidationError("max_response_bytes must be a positive integer")
    if max_response_bytes <= 0:
        raise EntsoeRequestValidationError("max_response_bytes must be a positive integer")
    if window.start_utc > request.requested_start_utc or window.end_utc < request.requested_end_utc:
        raise EntsoeRequestValidationError(
            "query window must enclose the exact requested period"
        )
    selected_transport = transport or UrllibEntsoeTransport()
    parameters = window.request_parameters()
    diagnostics: list[EntsoeDiagnostic] = []

    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        response: EntsoeTransportResponse | None = None
        try:
            response = selected_transport.request(
                endpoint=request.source_endpoint,
                parameters=parameters,
                api_token=api_token,
                max_response_bytes=max_response_bytes,
            )
        except _TransportBodyTooLarge as exc:
            diagnostic = _diagnostic(
                request,
                window,
                attempt=attempt,
                final_outcome="response_too_large",
                failure_class="response_too_large",
                detail=f"response exceeded {max_response_bytes} byte limit",
            )
            diagnostics.append(diagnostic)
            raise EntsoeResponseTooLargeError(
                _failure_message(window, request, "response size exceeded byte limit"),
                diagnostics=tuple(diagnostics),
            ) from None
        except (TimeoutError, ConnectionError, urllib.error.URLError) as exc:
            if isinstance(exc, TimeoutError):
                failure_class = "timeout"
            else:
                failure_class = "connection_interruption"
            if attempt < MAX_TRANSPORT_ATTEMPTS:
                delay = float(attempt)
                diagnostic = _diagnostic(
                    request,
                    window,
                    attempt=attempt,
                    final_outcome="retrying",
                    failure_class=failure_class,
                    delay_seconds=delay,
                    delay_source="deterministic-backoff",
                    detail="transient transport failure",
                )
                diagnostics.append(diagnostic)
                sleep(delay)
                continue
            diagnostic = _diagnostic(
                request,
                window,
                attempt=attempt,
                final_outcome="transient_exhausted",
                failure_class=failure_class,
                detail="transient transport attempts exhausted",
            )
            diagnostics.append(diagnostic)
            raise EntsoeTransientExhaustedError(
                _failure_message(window, request, "three transient attempts exhausted"),
                diagnostics=tuple(diagnostics),
            ) from None
        except Exception:
            diagnostic = _diagnostic(
                request,
                window,
                attempt=attempt,
                final_outcome="permanent_failure",
                failure_class="unexpected_transport_error",
                detail="unexpected transport failure",
            )
            diagnostics.append(diagnostic)
            raise EntsoePermanentTransportError(
                _failure_message(window, request, "permanent transport failure"),
                diagnostics=tuple(diagnostics),
            ) from None

        if not isinstance(response, EntsoeTransportResponse):
            diagnostic = _diagnostic(
                request,
                window,
                attempt=attempt,
                final_outcome="permanent_failure",
                failure_class="invalid_transport_response",
                detail="transport returned an invalid response type",
            )
            diagnostics.append(diagnostic)
            raise EntsoePermanentTransportError(
                _failure_message(window, request, "invalid transport response"),
                diagnostics=tuple(diagnostics),
            )
        if len(response.body) > max_response_bytes:
            diagnostic = _diagnostic(
                request,
                window,
                attempt=attempt,
                final_outcome="response_too_large",
                status_code=response.status_code,
                failure_class="response_too_large",
                detail=f"response exceeded {max_response_bytes} byte limit",
            )
            diagnostics.append(diagnostic)
            raise EntsoeResponseTooLargeError(
                _failure_message(window, request, "response size exceeded byte limit"),
                diagnostics=tuple(diagnostics),
            )
        if 200 <= response.status_code <= 299:
            diagnostic = _diagnostic(
                request,
                window,
                attempt=attempt,
                final_outcome="success",
                status_code=response.status_code,
                detail="bounded XML response received",
            )
            diagnostics.append(diagnostic)
            return EntsoeTransportResult(
                status_code=response.status_code,
                body=response.body,
                media_type=response.media_type,
                attempt_count=attempt,
                diagnostics=tuple(diagnostics),
            )
        if _is_transient_status(response.status_code):
            if attempt < MAX_TRANSPORT_ATTEMPTS:
                delay, delay_source, detail = _retry_after(response, attempt)
                diagnostic = _diagnostic(
                    request,
                    window,
                    attempt=attempt,
                    final_outcome="retrying",
                    status_code=response.status_code,
                    failure_class="transient_http_status",
                    delay_seconds=delay,
                    delay_source=delay_source,
                    detail=detail or f"transient HTTP status {response.status_code}",
                )
                diagnostics.append(diagnostic)
                sleep(delay)
                continue
            diagnostic = _diagnostic(
                request,
                window,
                attempt=attempt,
                final_outcome="transient_exhausted",
                status_code=response.status_code,
                failure_class="transient_http_status",
                detail="transient HTTP attempts exhausted",
            )
            diagnostics.append(diagnostic)
            raise EntsoeTransientExhaustedError(
                _failure_message(window, request, "three transient attempts exhausted"),
                diagnostics=tuple(diagnostics),
            )

        diagnostic = _diagnostic(
            request,
            window,
            attempt=attempt,
            final_outcome="permanent_failure",
            status_code=response.status_code,
            failure_class="permanent_http_status",
            detail=f"permanent HTTP status {response.status_code}",
        )
        diagnostics.append(diagnostic)
        raise EntsoePermanentTransportError(
            _failure_message(
                window,
                request,
                f"permanent HTTP status {response.status_code}",
            ),
            diagnostics=tuple(diagnostics),
        )

    raise AssertionError("unreachable transport attempt state")


class EntsoeXmlParseError(EntsoeAcquisitionError):
    """Raised when bounded XML bytes are malformed."""


class EntsoeUnsafeXmlError(EntsoeXmlParseError):
    """Raised before parse when DTD or entity syntax is present."""


class EntsoeXmlClassificationError(EntsoeAcquisitionError):
    """Raised when the XML root or namespace is not an accepted data family."""


class EntsoeAcknowledgementError(EntsoeAcquisitionError):
    """Raised when ENTSO-E returned an acknowledgement instead of data."""


class EntsoeEmptyResponseError(EntsoeAcquisitionError):
    """Raised when a valid data document contains no time series."""


class EntsoeSemanticValidationError(EntsoeAcquisitionError):
    """Raised when required returned source semantics are absent or inconsistent."""


class EntsoeDuplicateObservationError(EntsoeSemanticValidationError):
    """Raised when duplicate source intervals carry conflicting values."""


class EntsoeCoverageError(EntsoeSemanticValidationError):
    """Raised when normalized observations do not cover the requested period."""


class EntsoeProductValidationError(EntsoeSemanticValidationError):
    """Raised when returned reserve product semantics are incompatible."""


class EntsoeUnitValidationError(EntsoeSemanticValidationError):
    """Raised when returned source units cannot satisfy the France profile."""


class EntsoeResolutionValidationError(EntsoeSemanticValidationError):
    """Raised when returned intervals use an unsupported resolution."""


class EntsoeCurveValidationError(EntsoeSemanticValidationError):
    """Raised when a source curve cannot be expanded unambiguously."""


class EntsoeValueValidationError(EntsoeSemanticValidationError):
    """Raised when a source observation is non-finite or outside its domain."""


@dataclass(frozen=True, slots=True)
class ParsedEntsoeDocument:
    """One validated source document normalized to a canonical market series."""

    source_document: SourceDocumentEvidence
    series: MarketSeries


@dataclass(frozen=True, slots=True)
class EntsoeRevisionSelection:
    """Selected current documents plus retained superseded revision evidence."""

    selected: tuple[ParsedEntsoeDocument, ...]
    superseded: tuple[ParsedEntsoeDocument, ...]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace_uri(tag: str) -> str:
    if not tag.startswith("{") or "}" not in tag:
        return ""
    return tag[1:].split("}", 1)[0]


def _direct_children(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in element if _local_name(child.tag) == local_name]


def _direct_child(element: ET.Element, local_name: str) -> ET.Element | None:
    matches = _direct_children(element, local_name)
    return matches[0] if matches else None


def _parse_diagnostic(
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    *,
    final_outcome: str,
    detail: str,
    attempt_count: int,
    observed_start_utc: datetime | None = None,
    observed_end_utc: datetime | None = None,
    observed_resolution: str | None = None,
    observed_unit: str | None = None,
) -> EntsoeDiagnostic:
    return EntsoeDiagnostic(
        source=ENTSOE_SOURCE_NAME,
        document_type=window.document_type,
        required_series=window.required_series,
        window_id=window.window_id,
        requested_start_utc=_format_utc(request.requested_start_utc),
        requested_end_utc=_format_utc(request.requested_end_utc),
        expected_profile=request.profile.profile_id,
        expected_contract=EXPECTED_FRANCE_CONTRACT,
        final_outcome=final_outcome,
        attempt=attempt_count,
        failure_class="source_validation",
        detail=detail,
        observed_start_utc=(
            _format_utc(observed_start_utc) if observed_start_utc is not None else None
        ),
        observed_end_utc=(
            _format_utc(observed_end_utc) if observed_end_utc is not None else None
        ),
        observed_resolution=observed_resolution,
        observed_unit=observed_unit,
    )


def _raise_parse_failure(
    error_type: type[EntsoeAcquisitionError],
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    *,
    issue: str,
    final_outcome: str,
    attempt_count: int,
    observed_start_utc: datetime | None = None,
    observed_end_utc: datetime | None = None,
    observed_resolution: str | None = None,
    observed_unit: str | None = None,
) -> None:
    diagnostic = _parse_diagnostic(
        request,
        window,
        final_outcome=final_outcome,
        detail=issue,
        attempt_count=attempt_count,
        observed_start_utc=observed_start_utc,
        observed_end_utc=observed_end_utc,
        observed_resolution=observed_resolution,
        observed_unit=observed_unit,
    )
    raise error_type(
        _failure_message(window, request, issue),
        diagnostic=diagnostic,
    )


def _required_text(
    element: ET.Element,
    local_name: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
    field_label: str | None = None,
) -> str:
    child = _direct_child(element, local_name)
    if child is None or child.text is None or not child.text.strip():
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue=f"missing required semantic field {field_label or local_name}",
            final_outcome="semantic_validation_failure",
            attempt_count=attempt_count,
        )
    return child.text.strip()


def _parse_source_timestamp(
    value: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
    field_label: str,
) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue=f"invalid required UTC timestamp {field_label}",
            final_outcome="semantic_validation_failure",
            attempt_count=attempt_count,
        )
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue=f"required timestamp {field_label} must be aware UTC",
            final_outcome="semantic_validation_failure",
            attempt_count=attempt_count,
        )
    return parsed.astimezone(UTC)


def _parse_time_interval(
    owner: ET.Element,
    interval_name: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
) -> tuple[datetime, datetime]:
    interval = _direct_child(owner, interval_name)
    if interval is None:
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue=f"missing required semantic field {interval_name}",
            final_outcome="semantic_validation_failure",
            attempt_count=attempt_count,
        )
    start_text = _required_text(
        interval,
        "start",
        request=request,
        window=window,
        attempt_count=attempt_count,
        field_label=f"{interval_name}.start",
    )
    end_text = _required_text(
        interval,
        "end",
        request=request,
        window=window,
        attempt_count=attempt_count,
        field_label=f"{interval_name}.end",
    )
    start = _parse_source_timestamp(
        start_text,
        request=request,
        window=window,
        attempt_count=attempt_count,
        field_label=f"{interval_name}.start",
    )
    end = _parse_source_timestamp(
        end_text,
        request=request,
        window=window,
        attempt_count=attempt_count,
        field_label=f"{interval_name}.end",
    )
    if start >= end:
        _raise_parse_failure(
            EntsoeCoverageError,
            request,
            window,
            issue="source coverage interval start must precede end",
            final_outcome="coverage_failure",
            attempt_count=attempt_count,
            observed_start_utc=start,
            observed_end_utc=end,
        )
    return start, end


def _parse_revision(
    value: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
) -> int:
    try:
        revision = int(value)
    except ValueError:
        revision = -1
    if revision < 0 or str(revision) != value:
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue="revisionNumber must be a non-negative integer",
            final_outcome="semantic_validation_failure",
            attempt_count=attempt_count,
        )
    return revision


def _observed_unit(
    document_type: str,
    *,
    currency: str | None,
    measure_unit: str,
) -> str:
    normalized_measure = {"MWH": "MWh", "MAW": "MW"}.get(
        measure_unit,
        measure_unit,
    )
    if document_type == "A81":
        return normalized_measure
    if currency is None:
        return normalized_measure
    if document_type == "A89" and measure_unit == "MAW":
        return f"{currency}/MW/ISP"
    return f"{currency}/{normalized_measure}"


def _validate_units(
    time_series: ET.Element,
    document_type: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
    observed_start: datetime,
    observed_end: datetime,
    resolution: str,
) -> tuple[str, str | None, str, Mapping[str, object] | None, str | None]:
    if document_type == "A81":
        measure_unit = _required_text(
            time_series,
            "quantity_Measure_Unit.name",
            request=request,
            window=window,
            attempt_count=attempt_count,
        )
        unit = _observed_unit(document_type, currency=None, measure_unit=measure_unit)
        if measure_unit != "MAW":
            _raise_parse_failure(
                EntsoeUnitValidationError,
                request,
                window,
                issue=f"unexpected unit {unit}; expected MW",
                final_outcome="unit_validation_failure",
                attempt_count=attempt_count,
                observed_start_utc=observed_start,
                observed_end_utc=observed_end,
                observed_resolution=resolution,
                observed_unit=unit,
            )
        return "MW", None, "MW", None, None

    currency = _required_text(
        time_series,
        "currency_Unit.name",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    measure_unit = _required_text(
        time_series,
        "price_Measure_Unit.name",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    unit = _observed_unit(
        document_type,
        currency=currency,
        measure_unit=measure_unit,
    )
    if currency != "EUR":
        _raise_parse_failure(
            EntsoeUnitValidationError,
            request,
            window,
            issue=f"unexpected currency/unit {unit}; expected EUR profile",
            final_outcome="unit_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=observed_start,
            observed_end_utc=observed_end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    if document_type == "A44":
        if measure_unit != "MWH":
            _raise_parse_failure(
                EntsoeUnitValidationError,
                request,
                window,
                issue=f"unexpected unit {unit}; expected EUR/MWh",
                final_outcome="unit_validation_failure",
                attempt_count=attempt_count,
                observed_start_utc=observed_start,
                observed_end_utc=observed_end,
                observed_resolution=resolution,
                observed_unit=unit,
            )
        return "EUR/MWh", "EUR", "EUR/MWh", None, None
    if measure_unit != "MAW":
        _raise_parse_failure(
            EntsoeUnitValidationError,
            request,
            window,
            issue=f"unexpected unit {unit}; expected EUR/MW/ISP",
            final_outcome="unit_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=observed_start,
            observed_end_utc=observed_end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    conversion_ref = "a89-eur-per-mw-isp-to-eur-per-mw-hour"
    conversion = MappingProxyType(
        {
            "conversion_ref": conversion_ref,
            "source_unit": "EUR/MW/ISP",
            "canonical_unit": "EUR/MW/h",
            "factor": 0.25,
            "formula": "EUR/MW/ISP divided by four-hour block duration",
        }
    )
    return "EUR/MW/ISP", "EUR", "EUR/MW/h", conversion, conversion_ref


def _validate_product(
    time_series: ET.Element,
    document_type: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
    observed_start: datetime,
    observed_end: datetime,
    resolution: str,
    unit: str,
) -> tuple[str, str | None, str | None, Mapping[str, object]]:
    business_type = _required_text(
        time_series,
        "businessType",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    series_mrid = _required_text(
        time_series,
        "mRID",
        request=request,
        window=window,
        attempt_count=attempt_count,
        field_label="TimeSeries.mRID",
    )
    if document_type == "A44":
        if business_type != "A62":
            _raise_parse_failure(
                EntsoeProductValidationError,
                request,
                window,
                issue=f"wrong day-ahead business product {business_type}; expected A62",
                final_outcome="product_validation_failure",
                attempt_count=attempt_count,
                observed_start_utc=observed_start,
                observed_end_utc=observed_end,
                observed_resolution=resolution,
                observed_unit=unit,
            )
        product = MappingProxyType(
            {"business_type": business_type, "series_mrid": series_mrid}
        )
        return business_type, None, None, product

    flow_direction = _required_text(
        time_series,
        "flowDirection.direction",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    market_agreement = _required_text(
        time_series,
        "marketAgreement.type",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    auction_type = _required_text(
        time_series,
        "auction.type",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    auction_category = _required_text(
        time_series,
        "auction.category",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    if business_type != "A95" or flow_direction != "A03":
        _raise_parse_failure(
            EntsoeProductValidationError,
            request,
            window,
            issue=(
                "wrong FCR product; expected business type A95 and symmetric "
                f"direction A03, observed {business_type}/{flow_direction}"
            ),
            final_outcome="product_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=observed_start,
            observed_end_utc=observed_end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    product = MappingProxyType(
        {
            "business_type": business_type,
            "flow_direction": flow_direction,
            "market_agreement_type": market_agreement,
            "auction_type": auction_type,
            "auction_category": auction_category,
            "series_mrid": series_mrid,
        }
    )
    return business_type, flow_direction, market_agreement, product


def _validate_area(
    time_series: ET.Element,
    document_type: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
) -> None:
    if document_type == "A44":
        area_values = (
            _required_text(
                time_series,
                "in_Domain.mRID",
                request=request,
                window=window,
                attempt_count=attempt_count,
            ),
            _required_text(
                time_series,
                "out_Domain.mRID",
                request=request,
                window=window,
                attempt_count=attempt_count,
            ),
        )
    else:
        area_values = (
            _required_text(
                time_series,
                "controlArea_Domain.mRID",
                request=request,
                window=window,
                attempt_count=attempt_count,
            ),
        )
    if any(value != FRANCE_AREA_EIC for value in area_values):
        _raise_parse_failure(
            EntsoeProductValidationError,
            request,
            window,
            issue=f"wrong area; expected France {FRANCE_AREA_EIC}",
            final_outcome="area_validation_failure",
            attempt_count=attempt_count,
        )


def _value_text(
    point: ET.Element,
    document_type: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
) -> str:
    value_name = {
        "A44": "price.amount",
        "A81": "quantity",
        "A89": "procurement_Price.amount",
    }[document_type]
    return _required_text(
        point,
        value_name,
        request=request,
        window=window,
        attempt_count=attempt_count,
    )


def _point_value(
    value_text: str,
    document_type: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
    observed_start: datetime,
    observed_end: datetime,
    resolution: str,
    unit: str,
) -> float:
    try:
        value = float(value_text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        _raise_parse_failure(
            EntsoeValueValidationError,
            request,
            window,
            issue="source point value must be finite",
            final_outcome="value_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=observed_start,
            observed_end_utc=observed_end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    if document_type in ("A81", "A89") and value < 0:
        _raise_parse_failure(
            EntsoeValueValidationError,
            request,
            window,
            issue="reserve volume and capacity price values must be non-negative",
            final_outcome="value_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=observed_start,
            observed_end_utc=observed_end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    return value


def _expand_period_points(
    period: ET.Element,
    time_series: ET.Element,
    document_type: str,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    attempt_count: int,
    unit: str,
    conversion_factor: float,
) -> tuple[list[tuple[datetime, datetime, float, int]], int, int, str, str]:
    start, end = _parse_time_interval(
        period,
        "timeInterval",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    resolution = _required_text(
        period,
        "resolution",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    expected_resolution = "PT1H" if document_type == "A44" else "PT4H"
    if resolution != expected_resolution:
        _raise_parse_failure(
            EntsoeResolutionValidationError,
            request,
            window,
            issue=f"unexpected resolution {resolution}; expected {expected_resolution}",
            final_outcome="resolution_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=start,
            observed_end_utc=end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    step = parse_iso8601_duration(resolution)
    interval_count_float = (end - start) / step
    interval_count = int(interval_count_float)
    if interval_count <= 0 or interval_count != interval_count_float:
        _raise_parse_failure(
            EntsoeCoverageError,
            request,
            window,
            issue="period coverage is not exactly divisible by source resolution",
            final_outcome="coverage_failure",
            attempt_count=attempt_count,
            observed_start_utc=start,
            observed_end_utc=end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    curve_type = _required_text(
        time_series,
        "curveType",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    if curve_type not in ("A01", "A03"):
        _raise_parse_failure(
            EntsoeCurveValidationError,
            request,
            window,
            issue=f"unsupported source curve type {curve_type}",
            final_outcome="curve_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=start,
            observed_end_utc=end,
            observed_resolution=resolution,
            observed_unit=unit,
        )
    raw_points: list[tuple[int, float]] = []
    for point in _direct_children(period, "Point"):
        position_text = _required_text(
            point,
            "position",
            request=request,
            window=window,
            attempt_count=attempt_count,
        )
        try:
            position = int(position_text)
        except ValueError:
            position = -1
        if position <= 0 or str(position) != position_text or position > interval_count:
            _raise_parse_failure(
                EntsoeCurveValidationError,
                request,
                window,
                issue=f"invalid source curve position {position_text!r}",
                final_outcome="curve_validation_failure",
                attempt_count=attempt_count,
                observed_start_utc=start,
                observed_end_utc=end,
                observed_resolution=resolution,
                observed_unit=unit,
            )
        source_value = _point_value(
            _value_text(
                point,
                document_type,
                request=request,
                window=window,
                attempt_count=attempt_count,
            ),
            document_type,
            request=request,
            window=window,
            attempt_count=attempt_count,
            observed_start=start,
            observed_end=end,
            resolution=resolution,
            unit=unit,
        )
        raw_points.append((position, source_value * conversion_factor))
    if not raw_points:
        _raise_parse_failure(
            EntsoeCoverageError,
            request,
            window,
            issue="period contains no source points",
            final_outcome="coverage_failure",
            attempt_count=attempt_count,
            observed_start_utc=start,
            observed_end_utc=end,
            observed_resolution=resolution,
            observed_unit=unit,
        )

    expanded: list[tuple[datetime, datetime, float, int]] = []
    if curve_type == "A01":
        for position, value in raw_points:
            interval_start = start + (position - 1) * step
            expanded.append((interval_start, interval_start + step, value, position))
    else:
        unique_positions = sorted({position for position, _ in raw_points})
        if unique_positions[0] != 1:
            _raise_parse_failure(
                EntsoeCurveValidationError,
                request,
                window,
                issue="variable-sized-block curve must begin at position 1",
                final_outcome="curve_validation_failure",
                attempt_count=attempt_count,
                observed_start_utc=start,
                observed_end_utc=end,
                observed_resolution=resolution,
                observed_unit=unit,
            )
        value_by_position: dict[int, float] = {}
        for position, value in raw_points:
            existing = value_by_position.get(position)
            if existing is not None and existing != value:
                _raise_parse_failure(
                    EntsoeDuplicateObservationError,
                    request,
                    window,
                    issue=f"conflicting duplicate variable curve position {position}",
                    final_outcome="duplicate_validation_failure",
                    attempt_count=attempt_count,
                    observed_start_utc=start,
                    observed_end_utc=end,
                    observed_resolution=resolution,
                    observed_unit=unit,
                )
            value_by_position[position] = value
        for index, position in enumerate(unique_positions):
            stop_position = (
                unique_positions[index + 1]
                if index + 1 < len(unique_positions)
                else interval_count + 1
            )
            for expanded_position in range(position, stop_position):
                interval_start = start + (expanded_position - 1) * step
                expanded.append(
                    (
                        interval_start,
                        interval_start + step,
                        value_by_position[position],
                        position,
                    )
                )
    return expanded, interval_count, len(raw_points), resolution, curve_type


def parse_entsoe_document(
    body: bytes,
    *,
    request: EntsoeMarketDataRequest,
    window: EntsoeQueryWindow,
    response_id: str,
    attempt_count: int = 1,
) -> ParsedEntsoeDocument:
    """Classify and normalize one bounded A44, A81, or A89 XML document."""

    if not isinstance(body, bytes):
        raise TypeError("body must be bytes")
    if not isinstance(request, EntsoeMarketDataRequest):
        raise TypeError("request must be an EntsoeMarketDataRequest")
    if not isinstance(window, EntsoeQueryWindow):
        raise TypeError("window must be an EntsoeQueryWindow")
    response_id = _non_empty(response_id, field_name="response_id")
    if isinstance(attempt_count, bool) or not isinstance(attempt_count, int) or attempt_count <= 0:
        raise EntsoeRequestValidationError("attempt_count must be a positive integer")
    upper_body = body.upper()
    if b"<!DOCTYPE" in upper_body or b"<!ENTITY" in upper_body:
        _raise_parse_failure(
            EntsoeUnsafeXmlError,
            request,
            window,
            issue="unsafe XML declaration: DTD or entity declarations are forbidden",
            final_outcome="unsafe_xml",
            attempt_count=attempt_count,
        )
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, ValueError):
        _raise_parse_failure(
            EntsoeXmlParseError,
            request,
            window,
            issue="malformed XML parse failure",
            final_outcome="malformed_xml",
            attempt_count=attempt_count,
        )

    root_name = _local_name(root.tag)
    namespace = _namespace_uri(root.tag)
    if root_name in ("Acknowledgement_MarketDocument", "Problem_MarketDocument"):
        _raise_parse_failure(
            EntsoeAcknowledgementError,
            request,
            window,
            issue="ENTSO-E acknowledgement returned instead of market data",
            final_outcome="acknowledgement",
            attempt_count=attempt_count,
        )
    expected_root = (
        "Publication_MarketDocument"
        if window.document_type == "A44"
        else "ReserveAllocationResult_MarketDocument"
    )
    expected_namespace_fragment = (
        ":451-3:publicationdocument:"
        if window.document_type == "A44"
        else ":451-7:reserveallocationresultdocument:"
    )
    if (
        root_name != expected_root
        or not namespace.startswith("urn:iec62325.351:")
        or expected_namespace_fragment not in namespace
    ):
        _raise_parse_failure(
            EntsoeXmlClassificationError,
            request,
            window,
            issue="unaccepted XML root or namespace family",
            final_outcome="xml_classification_failure",
            attempt_count=attempt_count,
        )

    time_series_items = _direct_children(root, "TimeSeries")
    if not time_series_items:
        _raise_parse_failure(
            EntsoeEmptyResponseError,
            request,
            window,
            issue="valid market document contains an empty response with no time series",
            final_outcome="empty_response",
            attempt_count=attempt_count,
        )

    document_mrid = _required_text(
        root,
        "mRID",
        request=request,
        window=window,
        attempt_count=attempt_count,
        field_label="document mRID",
    )
    revision = _parse_revision(
        _required_text(
            root,
            "revisionNumber",
            request=request,
            window=window,
            attempt_count=attempt_count,
        ),
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    document_type = _required_text(
        root,
        "type",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    process_type = _required_text(
        root,
        "process.processType",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    created_at = _parse_source_timestamp(
        _required_text(
            root,
            "createdDateTime",
            request=request,
            window=window,
            attempt_count=attempt_count,
        ),
        request=request,
        window=window,
        attempt_count=attempt_count,
        field_label="createdDateTime",
    )
    document_start, document_end = _parse_time_interval(
        root,
        "period.timeInterval",
        request=request,
        window=window,
        attempt_count=attempt_count,
    )
    expected_process = "A01" if window.document_type == "A44" else "A34"
    if document_type != window.document_type or process_type != expected_process:
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue=(
                "returned document identity/process does not match required "
                f"{window.document_type}/{expected_process}"
            ),
            final_outcome="semantic_validation_failure",
            attempt_count=attempt_count,
            observed_start_utc=document_start,
            observed_end_utc=document_end,
        )

    document_ref = f"{response_id}:{document_mrid}:r{revision}"
    normalized_records: dict[
        tuple[datetime, datetime], tuple[float, int, str]
    ] = {}
    exact_duplicates = 0
    expanded_variable_blocks = 0
    resolutions: set[str] = set()
    curve_types: set[str] = set()
    business_type: str | None = None
    flow_direction: str | None = None
    market_agreement: str | None = None
    product_identity: Mapping[str, object] | None = None
    source_unit: str | None = None
    currency: str | None = None
    canonical_unit: str | None = None
    conversion: Mapping[str, object] | None = None
    conversion_ref: str | None = None

    for time_series in time_series_items:
        _validate_area(
            time_series,
            document_type,
            request=request,
            window=window,
            attempt_count=attempt_count,
        )
        periods = _direct_children(time_series, "Period")
        if not periods:
            _raise_parse_failure(
                EntsoeEmptyResponseError,
                request,
                window,
                issue="time series contains no source periods",
                final_outcome="empty_response",
                attempt_count=attempt_count,
            )
        first_period_start, first_period_end = _parse_time_interval(
            periods[0],
            "timeInterval",
            request=request,
            window=window,
            attempt_count=attempt_count,
        )
        first_resolution = _required_text(
            periods[0],
            "resolution",
            request=request,
            window=window,
            attempt_count=attempt_count,
        )
        (
            candidate_source_unit,
            candidate_currency,
            candidate_canonical_unit,
            candidate_conversion,
            candidate_conversion_ref,
        ) = _validate_units(
            time_series,
            document_type,
            request=request,
            window=window,
            attempt_count=attempt_count,
            observed_start=first_period_start,
            observed_end=first_period_end,
            resolution=first_resolution,
        )
        (
            candidate_business,
            candidate_direction,
            candidate_market_agreement,
            candidate_product,
        ) = _validate_product(
            time_series,
            document_type,
            request=request,
            window=window,
            attempt_count=attempt_count,
            observed_start=first_period_start,
            observed_end=first_period_end,
            resolution=first_resolution,
            unit=candidate_source_unit,
        )
        if source_unit is None:
            source_unit = candidate_source_unit
            currency = candidate_currency
            canonical_unit = candidate_canonical_unit
            conversion = candidate_conversion
            conversion_ref = candidate_conversion_ref
            business_type = candidate_business
            flow_direction = candidate_direction
            market_agreement = candidate_market_agreement
            product_identity = candidate_product
        elif (
            source_unit != candidate_source_unit
            or product_identity != candidate_product
            or business_type != candidate_business
            or flow_direction != candidate_direction
        ):
            _raise_parse_failure(
                EntsoeProductValidationError,
                request,
                window,
                issue="time series in one document have incompatible product identity or units",
                final_outcome="product_validation_failure",
                attempt_count=attempt_count,
                observed_start_utc=document_start,
                observed_end_utc=document_end,
                observed_resolution=first_resolution,
                observed_unit=candidate_source_unit,
            )
        conversion_factor = 0.25 if document_type == "A89" else 1.0
        series_mrid = str(candidate_product["series_mrid"])
        for period in periods:
            expanded, _, raw_count, resolution, curve_type = _expand_period_points(
                period,
                time_series,
                document_type,
                request=request,
                window=window,
                attempt_count=attempt_count,
                unit=candidate_source_unit,
                conversion_factor=conversion_factor,
            )
            resolutions.add(resolution)
            curve_types.add(curve_type)
            if curve_type == "A03":
                expanded_variable_blocks += raw_count
            for interval_start, interval_end, value, source_position in expanded:
                key = (interval_start, interval_end)
                existing = normalized_records.get(key)
                if existing is not None:
                    existing_value, _, existing_identity = existing
                    if existing_value == value and existing_identity == series_mrid:
                        exact_duplicates += 1
                        continue
                    _raise_parse_failure(
                        EntsoeDuplicateObservationError,
                        request,
                        window,
                        issue=(
                            "conflicting duplicate source observation at "
                            f"position {source_position}"
                        ),
                        final_outcome="duplicate_validation_failure",
                        attempt_count=attempt_count,
                        observed_start_utc=document_start,
                        observed_end_utc=document_end,
                        observed_resolution=resolution,
                        observed_unit=candidate_source_unit,
                    )
                normalized_records[key] = (value, source_position, series_mrid)

    assert source_unit is not None
    assert canonical_unit is not None
    assert product_identity is not None
    ordered_records = sorted(normalized_records.items(), key=lambda item: item[0])
    if not ordered_records:
        _raise_parse_failure(
            EntsoeCoverageError,
            request,
            window,
            issue="normalized source document has no observations",
            final_outcome="coverage_failure",
            attempt_count=attempt_count,
            observed_start_utc=document_start,
            observed_end_utc=document_end,
            observed_unit=source_unit,
        )
    previous_end: datetime | None = None
    for (interval_start, interval_end), _ in ordered_records:
        if previous_end is not None and interval_start != previous_end:
            relation = "gap" if interval_start > previous_end else "overlap"
            _raise_parse_failure(
                EntsoeCoverageError,
                request,
                window,
                issue=f"source observation coverage contains a {relation}",
                final_outcome="coverage_failure",
                attempt_count=attempt_count,
                observed_start_utc=document_start,
                observed_end_utc=document_end,
                observed_resolution=(
                    next(iter(resolutions)) if len(resolutions) == 1 else None
                ),
                observed_unit=source_unit,
            )
        previous_end = interval_end
    actual_start = ordered_records[0][0][0]
    actual_end = ordered_records[-1][0][1]
    if actual_start > request.requested_start_utc or actual_end < request.requested_end_utc:
        _raise_parse_failure(
            EntsoeCoverageError,
            request,
            window,
            issue="source observations do not completely cover the requested period",
            final_outcome="coverage_failure",
            attempt_count=attempt_count,
            observed_start_utc=actual_start,
            observed_end_utc=actual_end,
            observed_resolution=(next(iter(resolutions)) if len(resolutions) == 1 else None),
            observed_unit=source_unit,
        )

    observations = tuple(
        MarketObservation(
            interval=CanonicalInterval.from_utc(interval_start, interval_end),
            value=value,
            document_ref=document_ref,
            source_position=source_position,
            conversion_ref=conversion_ref,
        )
        for (interval_start, interval_end), (
            value,
            source_position,
            _,
        ) in ordered_records
    )
    series_id = _DOCUMENT_SERIES[document_type]
    semantic_version = {
        "A44": "fr-day-ahead-price-v1",
        "A81": "fr-symmetric-fcr-volume-v1",
        "A89": "fr-symmetric-fcr-capacity-price-v1",
    }[document_type]
    source_resolution: str | tuple[str, ...]
    if len(resolutions) == 1:
        source_resolution = next(iter(resolutions))
    else:
        source_resolution = tuple(sorted(resolutions))
    curve_type_diagnostic = (
        next(iter(curve_types)) if len(curve_types) == 1 else tuple(sorted(curve_types))
    )
    series = MarketSeries(
        series_id=series_id,
        semantic_version=semantic_version,
        area_eic=FRANCE_AREA_EIC,
        source_document_type=document_type,
        source_resolution=source_resolution,
        canonical_resolution="PT1H" if document_type == "A44" else "PT4H",
        source_unit=source_unit,
        canonical_unit=canonical_unit,
        currency=currency,
        conversion=conversion,
        observations=observations,
        diagnostics=MappingProxyType(
            {
                "curve_type": curve_type_diagnostic,
                "exact_duplicates_collapsed": exact_duplicates,
                "expanded_variable_blocks": expanded_variable_blocks,
            }
        ),
    )
    source_document = SourceDocumentEvidence(
        document_ref=document_ref,
        response_id=response_id,
        namespace_uri=namespace,
        root_document_type=root_name,
        document_mrid=document_mrid,
        revision_number=revision,
        created_at_utc=_format_utc(created_at),
        document_type=document_type,
        process_type=process_type,
        business_type=business_type,
        flow_direction=flow_direction,
        area_eic=FRANCE_AREA_EIC,
        market_agreement_type=market_agreement,
        product_identity=product_identity,
        document_period=CanonicalInterval.from_utc(document_start, document_end),
        status="selected",
    )
    return ParsedEntsoeDocument(source_document=source_document, series=series)


def _with_document_status(
    parsed: ParsedEntsoeDocument,
    status: str,
) -> ParsedEntsoeDocument:
    source_document = replace(parsed.source_document, status=status)
    observations = tuple(
        replace(item, document_ref=source_document.document_ref)
        for item in parsed.series.observations
    )
    return replace(
        parsed,
        source_document=source_document,
        series=replace(parsed.series, observations=observations),
    )


def select_current_entsoe_documents(
    documents: list[ParsedEntsoeDocument] | tuple[ParsedEntsoeDocument, ...],
) -> EntsoeRevisionSelection:
    """Select the highest revision for each comparable source-document key."""

    groups: dict[tuple[object, ...], list[ParsedEntsoeDocument]] = {}
    for parsed in documents:
        if not isinstance(parsed, ParsedEntsoeDocument):
            raise TypeError("documents must contain ParsedEntsoeDocument values")
        evidence = parsed.source_document
        key = (
            evidence.document_type,
            evidence.document_mrid,
            parsed.series.series_id,
            evidence.document_period.start_utc,
            evidence.document_period.end_utc,
        )
        groups.setdefault(key, []).append(parsed)

    selected: list[ParsedEntsoeDocument] = []
    superseded: list[ParsedEntsoeDocument] = []
    for key in sorted(groups, key=lambda item: tuple(str(part) for part in item)):
        ordered = sorted(
            groups[key],
            key=lambda item: (
                item.source_document.revision_number,
                item.source_document.response_id,
            ),
        )
        selected.append(_with_document_status(ordered[-1], "selected"))
        superseded.extend(
            _with_document_status(item, "superseded") for item in ordered[:-1]
        )
    return EntsoeRevisionSelection(
        selected=tuple(selected),
        superseded=tuple(superseded),
    )


class EntsoePublicationError(EntsoeAcquisitionError):
    """Raised when validated source data cannot be published atomically."""


@dataclass(frozen=True, slots=True)
class MarketDataFetchResult:
    """Successful explicit acquisition and immutable publication result."""

    outcome: str
    artifact: MarketDataArtifact
    artifact_path: Path
    attempt_diagnostics: tuple[EntsoeDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class _CandidateAcquisition:
    artifact: MarketDataArtifact
    response_bytes: Mapping[str, bytes]
    attempt_diagnostics: tuple[EntsoeDiagnostic, ...]


def _enclosing_local_day_bounds(
    request: EntsoeMarketDataRequest,
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(request.profile.market_timezone)
    first_local_date = request.requested_start_utc.astimezone(zone).date()
    last_included = request.requested_end_utc - timedelta(microseconds=1)
    last_local_date = last_included.astimezone(zone).date()
    local_start = datetime.combine(first_local_date, datetime.min.time(), tzinfo=zone)
    local_end = datetime.combine(
        last_local_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=zone,
    )
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def build_entsoe_query_windows(
    request: EntsoeMarketDataRequest,
) -> tuple[EntsoeQueryWindow, ...]:
    """Build deterministic A44/A81/A89 windows enclosing local delivery days."""

    if not isinstance(request, EntsoeMarketDataRequest):
        raise TypeError("request must be an EntsoeMarketDataRequest")
    start, end = _enclosing_local_day_bounds(request)
    local_start_date = start.astimezone(ZoneInfo(FRANCE_MARKET_TIMEZONE)).date()
    local_end_date = (
        (end - timedelta(microseconds=1))
        .astimezone(ZoneInfo(FRANCE_MARKET_TIMEZONE))
        .date()
    )
    windows = []
    for document_type in request.profile.required_document_types:
        windows.append(
            EntsoeQueryWindow(
                window_id=(
                    f"fr-{document_type.lower()}-"
                    f"{local_start_date.isoformat()}-{local_end_date.isoformat()}"
                ),
                document_type=document_type,
                process_type="A01" if document_type == "A44" else "A34",
                business_type=None if document_type == "A44" else "A95",
                area_parameter=request.profile.area_eic,
                start_utc=start,
                end_utc=end,
            )
        )
    return tuple(windows)


def _source_query_window(
    window: EntsoeQueryWindow,
    *,
    attempt_count: int,
) -> SourceQueryWindow:
    return SourceQueryWindow(
        window_id=window.window_id,
        document_type=window.document_type,
        process_type=window.process_type,
        business_type=window.business_type,
        area_parameter=window.area_parameter,
        start_utc=_format_utc(window.start_utc),
        end_utc=_format_utc(window.end_utc),
        attempt_count=attempt_count,
    )


def _retention_basis(policy: str) -> Mapping[str, object]:
    if policy == "permitted_sidecar":
        terms_version = "caller-asserted-raw-retention-v1"
        changes = "project workflow retained source bytes separately before normalization"
    else:
        terms_version = "digest-only-v1"
        changes = "raw bytes omitted; response digest and normalized values retained"
    return MappingProxyType(
        {
            "source": ENTSOE_SOURCE_NAME,
            "terms_version": terms_version,
            "attribution": "ENTSO-E Transparency Platform",
            "changes": changes,
        }
    )


def _raw_response_evidence(
    *,
    response_id: str,
    window: EntsoeQueryWindow,
    retrieved_at: datetime,
    result: EntsoeTransportResult,
    digest: str,
    retention_policy: str,
) -> RawResponseEvidence:
    retained = retention_policy == "permitted_sidecar"
    locator = f"sidecars/{window.document_type.lower()}-{digest}.xml" if retained else None
    return RawResponseEvidence(
        response_id=response_id,
        window_id=window.window_id,
        retrieved_at_utc=_format_utc(retrieved_at),
        media_type=result.media_type,
        byte_count=len(result.body),
        sha256=digest,
        retention_status="sidecar_retained" if retained else "digest_only",
        redistribution_basis=_retention_basis(retention_policy),
        sidecar_locator=locator,
        sidecar_sha256=digest if retained else None,
    )


def _common_actual_coverage(
    documents: tuple[ParsedEntsoeDocument, ...],
    *,
    request: EntsoeMarketDataRequest,
) -> CanonicalInterval:
    coverages = {
        (
            parsed.series.observations[0].interval.start_utc,
            parsed.series.observations[-1].interval.end_utc,
        )
        for parsed in documents
    }
    if len(coverages) != 1:
        culprit = next(
            item for item in documents if item.source_document.document_type == "A89"
        )
        window = next(
            item
            for item in build_entsoe_query_windows(request)
            if item.document_type == culprit.source_document.document_type
        )
        _raise_parse_failure(
            EntsoeCoverageError,
            request,
            window,
            issue="required A44/A81/A89 series have incompatible actual coverage",
            final_outcome="coverage_failure",
            attempt_count=1,
        )
    start, end = next(iter(coverages))
    return CanonicalInterval.from_utc(start, end)


def _validate_selected_profile_documents(
    selection: EntsoeRevisionSelection,
    *,
    request: EntsoeMarketDataRequest,
) -> tuple[ParsedEntsoeDocument, ...]:
    selected_by_type = {
        item.source_document.document_type: item for item in selection.selected
    }
    required = set(request.profile.required_document_types)
    if set(selected_by_type) != required:
        missing = sorted(required - set(selected_by_type))
        window = build_entsoe_query_windows(request)[0]
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue="missing required series documents: " + ", ".join(missing),
            final_outcome="missing_series",
            attempt_count=1,
        )
    volume_product = dict(selected_by_type["A81"].source_document.product_identity)
    price_product = dict(selected_by_type["A89"].source_document.product_identity)
    if volume_product != price_product:
        window = next(
            item
            for item in build_entsoe_query_windows(request)
            if item.document_type == "A89"
        )
        parsed = selected_by_type["A89"]
        _raise_parse_failure(
            EntsoeProductValidationError,
            request,
            window,
            issue="A81 volume and A89 capacity price product identity do not align",
            final_outcome="product_validation_failure",
            attempt_count=1,
            observed_start_utc=parsed.series.observations[0].interval.start_utc,
            observed_end_utc=parsed.series.observations[-1].interval.end_utc,
            observed_resolution=(
                parsed.series.source_resolution
                if isinstance(parsed.series.source_resolution, str)
                else None
            ),
            observed_unit=parsed.series.source_unit,
        )
    return tuple(selected_by_type[item] for item in request.profile.required_document_types)


def _artifact_id(request: EntsoeMarketDataRequest) -> str:
    start = request.requested_start_utc.strftime("%Y%m%dT%H%M%SZ")
    end = request.requested_end_utc.strftime("%Y%m%dT%H%M%SZ")
    return f"fr-market-{start}-{end}-v1"


def _artifact_payload(
    *,
    request: EntsoeMarketDataRequest,
    created_at: datetime,
    actual_coverage: CanonicalInterval,
    selected: tuple[ParsedEntsoeDocument, ...],
    superseded: tuple[ParsedEntsoeDocument, ...],
    query_windows: tuple[SourceQueryWindow, ...],
    raw_responses: tuple[RawResponseEvidence, ...],
    predecessor_artifact_fingerprint: str | None,
) -> dict[str, object]:
    by_series = {item.series.series_id: item.series for item in selected}
    source_documents = tuple(
        [item.source_document for item in selected]
        + [item.source_document for item in superseded]
    )
    return {
        "schema_version": MARKET_DATA_SCHEMA_VERSION,
        "artifact_id": _artifact_id(request),
        "profile_id": request.profile.profile_id,
        "normalization_version": request.normalization_version,
        "created_at_utc": _format_utc(created_at),
        "requested_period": CanonicalInterval.from_utc(
            request.requested_start_utc,
            request.requested_end_utc,
        ).to_dict(),
        "actual_covered_period": actual_coverage.to_dict(),
        "area": {
            "eic": request.profile.area_eic,
            "name": "France",
            "market_timezone": request.profile.market_timezone,
        },
        "series": {
            series_id: by_series[series_id].to_dict()
            for series_id in (
                "day_ahead_price",
                "fcr_contracted_volume",
                "fcr_capacity_price",
            )
        },
        "query_windows": [item.to_dict() for item in query_windows],
        "raw_responses": [item.to_dict() for item in raw_responses],
        "source_documents": [item.to_dict() for item in source_documents],
        "predecessor_artifact_fingerprint": predecessor_artifact_fingerprint,
        "retention_and_license": {
            "source": ENTSOE_SOURCE_NAME,
            "source_endpoint": request.source_endpoint,
            "profile": request.profile.profile_id,
            "raw_retention_policy": request.raw_retention_policy,
            "normalized_artifact_attribution": "ENTSO-E Transparency Platform",
            "normalization_version": request.normalization_version,
        },
    }


def _acquire_candidate(
    request: EntsoeMarketDataRequest,
    *,
    api_token: str,
    transport: EntsoeTransport | None,
    predecessor_artifact_fingerprint: str | None = None,
) -> _CandidateAcquisition:
    windows = build_entsoe_query_windows(request)
    parsed_documents: list[ParsedEntsoeDocument] = []
    query_evidence: list[SourceQueryWindow] = []
    raw_evidence: list[RawResponseEvidence] = []
    response_bytes: dict[str, bytes] = {}
    attempt_diagnostics: list[EntsoeDiagnostic] = []

    for window in windows:
        result = request_entsoe_window(
            request=request,
            window=window,
            api_token=api_token,
            transport=transport,
        )
        retrieved_at = datetime.now(UTC)
        digest = hashlib.sha256(result.body).hexdigest()
        response_id = f"response-{window.document_type.lower()}-{digest}"
        parsed = parse_entsoe_document(
            result.body,
            request=request,
            window=window,
            response_id=response_id,
            attempt_count=result.attempt_count,
        )
        parsed_documents.append(parsed)
        query_evidence.append(
            _source_query_window(window, attempt_count=result.attempt_count)
        )
        raw_evidence.append(
            _raw_response_evidence(
                response_id=response_id,
                window=window,
                retrieved_at=retrieved_at,
                result=result,
                digest=digest,
                retention_policy=request.raw_retention_policy,
            )
        )
        response_bytes[response_id] = result.body
        attempt_diagnostics.extend(result.diagnostics)

    selection = select_current_entsoe_documents(parsed_documents)
    selected = _validate_selected_profile_documents(selection, request=request)
    actual_coverage = _common_actual_coverage(selected, request=request)
    try:
        artifact = build_market_data_artifact(
            _artifact_payload(
                request=request,
                created_at=datetime.now(UTC),
                actual_coverage=actual_coverage,
                selected=selected,
                superseded=selection.superseded,
                query_windows=tuple(query_evidence),
                raw_responses=tuple(raw_evidence),
                predecessor_artifact_fingerprint=predecessor_artifact_fingerprint,
            )
        )
    except MarketArtifactValidationError:
        window = windows[-1]
        _raise_parse_failure(
            EntsoeSemanticValidationError,
            request,
            window,
            issue="normalized source data failed the canonical artifact contract",
            final_outcome="artifact_validation_failure",
            attempt_count=query_evidence[-1].attempt_count,
        )
    return _CandidateAcquisition(
        artifact=artifact,
        response_bytes=MappingProxyType(response_bytes),
        attempt_diagnostics=tuple(attempt_diagnostics),
    )


def _publish_sidecar(path: Path, body: bytes) -> bool:
    """Publish one immutable sidecar and return whether this call created it."""

    expected_digest = hashlib.sha256(body).hexdigest()
    if path.exists():
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise MarketArtifactPublicationError(
                "cannot read an existing immutable raw sidecar"
            ) from exc
        if existing != body or hashlib.sha256(existing).hexdigest() != expected_digest:
            raise MarketArtifactIntegrityError(
                "existing immutable raw sidecar differs from requested bytes"
            )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor = -1
    temporary_path: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "wb") as handle:
            file_descriptor = -1
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        return True
    except OSError as exc:
        raise MarketArtifactPublicationError(
            "cannot atomically publish a retained raw sidecar"
        ) from exc
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _publication_diagnostic(
    request: EntsoeMarketDataRequest,
    *,
    final_outcome: str,
) -> EntsoeDiagnostic:
    return _parse_diagnostic(
        request,
        build_entsoe_query_windows(request)[-1],
        final_outcome=final_outcome,
        detail="validated market artifact publication failed",
        attempt_count=1,
    )


def _publish_candidate(
    candidate: _CandidateAcquisition,
    *,
    request: EntsoeMarketDataRequest,
    destination_dir: str | os.PathLike[str],
) -> Path:
    destination = Path(destination_dir)
    created_sidecars: list[Path] = []
    try:
        for evidence in candidate.artifact.raw_responses:
            if evidence.retention_status != "sidecar_retained":
                continue
            assert evidence.sidecar_locator is not None
            body = candidate.response_bytes[evidence.response_id]
            sidecar_path = destination / evidence.sidecar_locator
            if _publish_sidecar(sidecar_path, body):
                created_sidecars.append(sidecar_path)
        return write_market_data_artifact(
            candidate.artifact,
            destination_dir=destination,
        )
    except (OSError, MarketArtifactValidationError):
        for path in reversed(created_sidecars):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        diagnostic = _publication_diagnostic(
            request,
            final_outcome="publication_failure",
        )
        raise EntsoePublicationError(
            "ENTSO-E validated market artifact atomic publication failed",
            diagnostic=diagnostic,
        ) from None


def fetch_entsoe_market_data(
    request: EntsoeMarketDataRequest,
    *,
    api_token: str,
    destination_dir: str | os.PathLike[str],
    transport: EntsoeTransport | None = None,
) -> MarketDataFetchResult:
    """Explicitly acquire, validate, and atomically publish all France series."""

    candidate = _acquire_candidate(
        request,
        api_token=api_token,
        transport=transport,
    )
    artifact_path = _publish_candidate(
        candidate,
        request=request,
        destination_dir=destination_dir,
    )
    return MarketDataFetchResult(
        outcome="published",
        artifact=candidate.artifact,
        artifact_path=artifact_path,
        attempt_diagnostics=candidate.attempt_diagnostics,
    )


@dataclass(frozen=True, slots=True)
class MarketDataRefreshResult:
    """One immutable refresh decision and its sanitized diagnostics."""

    outcome: str
    current_artifact_fingerprint: str
    returned_content_fingerprint: str | None
    new_artifact: MarketDataArtifact | None
    new_artifact_path: Path | None
    diagnostics: tuple[object, ...]


def _validate_refresh_identity(
    request: EntsoeMarketDataRequest,
    current: MarketDataArtifact,
) -> None:
    if current.profile_id != request.profile.profile_id:
        raise EntsoeRequestValidationError(
            "current artifact profile does not match the refresh request"
        )
    if current.area.get("eic") != request.profile.area_eic:
        raise EntsoeRequestValidationError(
            "current artifact area does not match the refresh request"
        )
    if current.normalization_version != request.normalization_version:
        raise EntsoeRequestValidationError(
            "current artifact normalization_version does not match the refresh request"
        )
    if (
        current.requested_period.start_utc != request.requested_start_utc
        or current.requested_period.end_utc != request.requested_end_utc
    ):
        raise EntsoeRequestValidationError(
            "current artifact requested period does not match the refresh request"
        )
    current_endpoint = current.retention_and_license.get("source_endpoint")
    if current_endpoint is not None and current_endpoint != request.source_endpoint:
        raise EntsoeRequestValidationError(
            "current artifact source endpoint does not match the refresh request"
        )


def _revision_key(document: SourceDocumentEvidence) -> tuple[object, ...]:
    return (
        document.document_type,
        document.document_mrid,
        document.document_period.start_utc,
        document.document_period.end_utc,
        tuple(sorted((str(key), repr(value)) for key, value in document.product_identity.items())),
    )


def _revision_regressions(
    current: MarketDataArtifact,
    returned: MarketDataArtifact,
) -> tuple[Mapping[str, object], ...]:
    current_selected = {
        _revision_key(document): document
        for document in current.source_documents
        if document.status == "selected"
    }
    diagnostics: list[Mapping[str, object]] = []
    for document in returned.source_documents:
        if document.status != "selected":
            continue
        previous = current_selected.get(_revision_key(document))
        if previous is None or document.revision_number >= previous.revision_number:
            continue
        diagnostics.append(
            MappingProxyType(
                {
                    "source": ENTSOE_SOURCE_NAME,
                    "document_type": document.document_type,
                    "document_mrid": document.document_mrid,
                    "current_revision": previous.revision_number,
                    "returned_revision": document.revision_number,
                    "final_status": "revision_regression",
                }
            )
        )
    return tuple(diagnostics)


def refresh_entsoe_market_data(
    request: EntsoeMarketDataRequest,
    *,
    current_artifact: MarketDataArtifact,
    api_token: str,
    destination_dir: str | os.PathLike[str],
    transport: EntsoeTransport | None = None,
) -> MarketDataRefreshResult:
    """Refresh one lineage without overwriting or mutating its current artifact."""

    if not isinstance(current_artifact, MarketDataArtifact):
        raise TypeError("current_artifact must be a MarketDataArtifact")
    try:
        verified_current = MarketDataArtifact.from_dict(current_artifact.to_dict())
    except MarketArtifactValidationError as exc:
        raise EntsoeRequestValidationError(
            "current artifact failed integrity validation before refresh"
        ) from exc
    _validate_refresh_identity(request, verified_current)
    candidate = _acquire_candidate(
        request,
        api_token=api_token,
        transport=transport,
        predecessor_artifact_fingerprint=verified_current.artifact_fingerprint,
    )
    regressions = _revision_regressions(verified_current, candidate.artifact)
    if regressions:
        return MarketDataRefreshResult(
            outcome="revision_regression",
            current_artifact_fingerprint=verified_current.artifact_fingerprint,
            returned_content_fingerprint=candidate.artifact.content_fingerprint,
            new_artifact=None,
            new_artifact_path=None,
            diagnostics=tuple(candidate.attempt_diagnostics) + regressions,
        )
    if candidate.artifact.content_fingerprint == verified_current.content_fingerprint:
        return MarketDataRefreshResult(
            outcome="unchanged",
            current_artifact_fingerprint=verified_current.artifact_fingerprint,
            returned_content_fingerprint=candidate.artifact.content_fingerprint,
            new_artifact=None,
            new_artifact_path=None,
            diagnostics=tuple(candidate.attempt_diagnostics),
        )
    artifact_path = _publish_candidate(
        candidate,
        request=request,
        destination_dir=destination_dir,
    )
    return MarketDataRefreshResult(
        outcome="published",
        current_artifact_fingerprint=verified_current.artifact_fingerprint,
        returned_content_fingerprint=candidate.artifact.content_fingerprint,
        new_artifact=candidate.artifact,
        new_artifact_path=artifact_path,
        diagnostics=tuple(candidate.attempt_diagnostics),
    )
