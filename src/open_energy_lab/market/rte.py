"""Explicit RTE Balancing Energy v5.2 acquisition adapter.

The source request layer is credential-free.  Authentication and transport are
available only through explicit operation functions in this focused module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
import hashlib
import json
import math
import time
from types import MappingProxyType
from typing import Any
import urllib.error
from urllib.parse import urlencode, urlsplit
import urllib.request

from .restoration_artifact import (
    RawRetentionPolicy,
    canonical_restoration_json_bytes,
)


RTE_CATALOG_VERSION = "5.2"
RTE_API_PATH_VERSION = "v5"
RTE_SOURCE_NAME = "RTE Balancing Energy"
RTE_SOURCE_ORIGIN = "https://digital.iservices.rte-france.com"
RTE_TOKEN_ENDPOINT = f"{RTE_SOURCE_ORIGIN}/token/oauth/"
RTE_DATA_PATH_PREFIX = "/open_api/balancing_energy/v5"
RTE_EXPECTED_RESOLUTION = "PT15M"
RTE_MAX_CALLER_WINDOW = timedelta(days=31)
RTE_MAX_SOURCE_WINDOW = timedelta(days=1)
RTE_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
RTE_MAX_AUTH_RESPONSE_BYTES = 64 * 1024
RTE_MAX_RETRY_AFTER_SECONDS = 30.0
RTE_MARKET_TIMEZONE = "Europe/Paris"
RTE_AREA = "France control/scheduling area"


_AFRR_SERIES_IDS = (
    "afrr_requested_need_upward",
    "afrr_requested_need_downward",
    "afrr_activated_for_fr_upward",
    "afrr_activated_for_fr_downward",
    "afrr_activated_in_fr_upward",
    "afrr_activated_in_fr_downward",
    "afrr_weighted_average_price_upward",
    "afrr_weighted_average_price_downward",
)
_MFRR_SERIES_IDS = tuple(
    f"mfrr_{kind}_{meaning}_{direction}"
    for direction in ("upward", "downward")
    for kind in ("sa", "da")
    for meaning in ("requested_volume", "satisfied_need", "activated_volume")
) + tuple(
    f"mfrr_{meaning}_{direction}"
    for direction in ("upward", "downward")
    for meaning in (
        "clearing_price",
        "settlement_price_current",
        "settlement_price_previous",
        "submitted_offer_volume",
        "filtered_offer_volume",
    )
)


class RTEAcquisitionMode(str, Enum):
    """Explicit source operation mode."""

    FETCH = "FETCH"
    REFRESH = "REFRESH"


class RTERequestValidationError(ValueError):
    """Raised before credentials are used when an RTE request is invalid."""


class RTEAuthenticationError(RuntimeError):
    """Sanitized failure of the operation-local OAuth exchange."""


class RTETransportError(RuntimeError):
    """Sanitized bounded-transport failure."""


class RTEParseError(ValueError):
    """Sanitized RTE response semantic failure."""


@dataclass(frozen=True, slots=True)
class RTETransportRequest:
    """Ephemeral HTTP request whose sensitive fields are excluded from repr."""

    method: str
    url: str
    headers: Mapping[str, str] = field(repr=False)
    body: bytes | None = field(default=None, repr=False)
    maximum_response_bytes: int = RTE_MAX_RESPONSE_BYTES


@dataclass(frozen=True, slots=True)
class RTEHTTPResponse:
    """Injected or stdlib transport response with bounded in-memory bytes."""

    status: int
    media_type: str
    body: bytes = field(repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class RTEOAuthSession:
    """Operation-local OAuth value that cannot reveal its token in repr."""

    access_token: str = field(repr=False)
    expires_in_seconds: float | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class RTERawMarketResponse:
    """Bounded market bytes and sanitized evidence for one source window."""

    request_id: str
    resource: str
    start_utc: datetime
    end_utc: datetime
    retrieved_at_utc: str
    media_type: str
    body: bytes = field(repr=False)
    raw_sha256: str
    attempt_count: int
    source_revision: str | None


@dataclass(frozen=True, slots=True)
class RTERestorationProfile:
    profile_id: str
    catalog_version: str
    api_path_version: str
    source_name: str
    resource: str
    root_field: str
    rows_field: str
    area: str
    market_timezone: str
    expected_resolution: str
    series_ids: tuple[str, ...]
    required_series_ids: tuple[str, ...]


RTE_AFRR_PROFILE = RTERestorationProfile(
    profile_id="fr-rte-balancing-energy-v5.2-afrr-v1",
    catalog_version=RTE_CATALOG_VERSION,
    api_path_version=RTE_API_PATH_VERSION,
    source_name=RTE_SOURCE_NAME,
    resource="standard_afrr_data",
    root_field="picasso",
    rows_field="picasso_mesures",
    area=RTE_AREA,
    market_timezone=RTE_MARKET_TIMEZONE,
    expected_resolution=RTE_EXPECTED_RESOLUTION,
    series_ids=_AFRR_SERIES_IDS,
    required_series_ids=_AFRR_SERIES_IDS[:6],
)
RTE_MFRR_PROFILE = RTERestorationProfile(
    profile_id="fr-rte-balancing-energy-v5.2-mfrr-v1",
    catalog_version=RTE_CATALOG_VERSION,
    api_path_version=RTE_API_PATH_VERSION,
    source_name=RTE_SOURCE_NAME,
    resource="standard_mfrr_data",
    root_field="mari",
    rows_field="mari_mesures",
    area=RTE_AREA,
    market_timezone=RTE_MARKET_TIMEZONE,
    expected_resolution=RTE_EXPECTED_RESOLUTION,
    series_ids=_MFRR_SERIES_IDS,
    required_series_ids=tuple(
        series_id
        for series_id in _MFRR_SERIES_IDS
        if "_sa_requested_volume_" in series_id
        or "_sa_satisfied_need_" in series_id
    ),
)
RTE_PROFILES = MappingProxyType(
    {
        RTE_AFRR_PROFILE.resource: RTE_AFRR_PROFILE,
        RTE_MFRR_PROFILE.resource: RTE_MFRR_PROFILE,
    }
)


def _utc(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise RTERequestValidationError(
            f"{field_name} must be an aware UTC datetime"
        )
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise RTERequestValidationError(
            f"{field_name} must be an aware UTC datetime"
        )
    return value.astimezone(UTC)


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RTERequestValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value


def _quarter_aligned(value: datetime) -> bool:
    return value.minute % 15 == 0 and value.second == 0 and value.microsecond == 0


def _safe_endpoint(endpoint: object, *, profile: RTERestorationProfile) -> str:
    normalized = _non_empty(endpoint, field_name="source_endpoint")
    parsed = urlsplit(normalized)
    expected_path = f"{RTE_DATA_PATH_PREFIX}/{profile.resource}"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "digital.iservices.rte-france.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != expected_path
    ):
        raise RTERequestValidationError(
            "source endpoint must be the pinned HTTPS RTE origin/path without "
            "userinfo, query, or fragment"
        )
    return normalized


def _enum_value(enum_type: type[Enum], value: object, *, field_name: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise RTERequestValidationError(f"unsupported {field_name}") from exc


def _request_payload(
    *,
    profile: RTERestorationProfile,
    endpoint: str,
    start: datetime,
    end: datetime,
    requested: tuple[str, ...],
    required: tuple[str, ...],
    normalization_version: str,
    raw_retention_policy: RawRetentionPolicy,
    mode: RTEAcquisitionMode,
) -> dict[str, object]:
    return {
        "source": "RTE",
        "profile_id": profile.profile_id,
        "catalog_version": profile.catalog_version,
        "resource_identity": profile.resource,
        "source_endpoint": endpoint,
        "requested_start_utc": start.isoformat().replace("+00:00", "Z"),
        "requested_end_utc": end.isoformat().replace("+00:00", "Z"),
        "requested_series_ids": list(requested),
        "required_series_ids": list(required),
        "normalization_version": normalization_version,
        "raw_retention_policy": raw_retention_policy.value,
        "mode": mode.value,
    }


@dataclass(frozen=True, slots=True)
class RestorationMarketDataRequest:
    source: str
    profile: RTERestorationProfile
    resource_identity: str
    source_endpoint: str
    requested_start_utc: datetime
    requested_end_utc: datetime
    requested_series_ids: tuple[str, ...]
    required_series_ids: tuple[str, ...]
    normalization_version: str
    raw_retention_policy: RawRetentionPolicy
    mode: RTEAcquisitionMode
    request_identity: str


def build_rte_restoration_request(
    *,
    resource: str,
    requested_start_utc: datetime,
    requested_end_utc: datetime,
    requested_series_ids: Sequence[str],
    required_series_ids: Sequence[str],
    normalization_version: str,
    raw_retention_policy: RawRetentionPolicy | str,
    mode: RTEAcquisitionMode | str,
    source_endpoint: str | None = None,
) -> RestorationMarketDataRequest:
    """Build one validated token-free RTE source request."""

    resource_name = _non_empty(resource, field_name="resource")
    profile = RTE_PROFILES.get(resource_name)
    if profile is None:
        raise RTERequestValidationError(
            f"resource {resource_name!r} has no registered RTE profile"
        )
    start = _utc(requested_start_utc, field_name="requested_start_utc")
    end = _utc(requested_end_utc, field_name="requested_end_utc")
    if start >= end:
        raise RTERequestValidationError(
            "requested period start must be before the later end bound"
        )
    if not _quarter_aligned(start) or not _quarter_aligned(end):
        raise RTERequestValidationError(
            "RTE requested period bounds must be 15-minute aligned"
        )
    if end - start > RTE_MAX_CALLER_WINDOW:
        raise RTERequestValidationError(
            "RTE requested period exceeds the bounded maximum caller window"
        )
    requested = tuple(
        _non_empty(item, field_name="requested_series_ids")
        for item in requested_series_ids
    )
    required = tuple(
        _non_empty(item, field_name="required_series_ids")
        for item in required_series_ids
    )
    if not requested or len(set(requested)) != len(requested):
        raise RTERequestValidationError(
            "requested series must be non-empty and unique"
        )
    if len(set(required)) != len(required):
        raise RTERequestValidationError("required series must be unique")
    if not set(required).issubset(requested):
        raise RTERequestValidationError(
            "required series must be a subset of requested series"
        )
    unknown = sorted(set(requested) - set(profile.series_ids))
    if unknown:
        raise RTERequestValidationError(
            f"requested series are unknown to the {profile.resource} profile: "
            + ", ".join(unknown)
        )
    endpoint = _safe_endpoint(
        source_endpoint
        or f"{RTE_SOURCE_ORIGIN}{RTE_DATA_PATH_PREFIX}/{profile.resource}",
        profile=profile,
    )
    retention = _enum_value(
        RawRetentionPolicy,
        raw_retention_policy,
        field_name="raw_retention_policy",
    )
    acquisition_mode = _enum_value(
        RTEAcquisitionMode, mode, field_name="acquisition mode"
    )
    normalization = _non_empty(
        normalization_version, field_name="normalization_version"
    )
    payload = _request_payload(
        profile=profile,
        endpoint=endpoint,
        start=start,
        end=end,
        requested=requested,
        required=required,
        normalization_version=normalization,
        raw_retention_policy=retention,
        mode=acquisition_mode,
    )
    identity = hashlib.sha256(canonical_restoration_json_bytes(payload)).hexdigest()
    return RestorationMarketDataRequest(
        source="RTE",
        profile=profile,
        resource_identity=profile.resource,
        source_endpoint=endpoint,
        requested_start_utc=start,
        requested_end_utc=end,
        requested_series_ids=requested,
        required_series_ids=required,
        normalization_version=normalization,
        raw_retention_policy=retention,
        mode=acquisition_mode,
        request_identity=identity,
    )


@dataclass(frozen=True, slots=True)
class RTEQueryWindow:
    request_id: str
    resource: str
    start_utc: datetime
    end_utc: datetime


def build_rte_query_windows(
    request: RestorationMarketDataRequest,
) -> tuple[RTEQueryWindow, ...]:
    """Split a caller request into deterministic contiguous source windows."""

    if not isinstance(request, RestorationMarketDataRequest):
        raise RTERequestValidationError(
            "request must be a RestorationMarketDataRequest"
        )
    windows = []
    cursor = request.requested_start_utc
    index = 0
    while cursor < request.requested_end_utc:
        end = min(cursor + RTE_MAX_SOURCE_WINDOW, request.requested_end_utc)
        payload = {
            "request_identity": request.request_identity,
            "window_index": index,
            "resource": request.resource_identity,
            "start_utc": cursor.isoformat().replace("+00:00", "Z"),
            "end_utc": end.isoformat().replace("+00:00", "Z"),
        }
        windows.append(
            RTEQueryWindow(
                request_id=hashlib.sha256(
                    canonical_restoration_json_bytes(payload)
                ).hexdigest(),
                resource=request.resource_identity,
                start_utc=cursor,
                end_utc=end,
            )
        )
        cursor = end
        index += 1
    return tuple(windows)


@dataclass(frozen=True, slots=True)
class RTEAcquisitionDiagnostic:
    code: str
    phase: str
    resource: str
    field: str
    requested_period: str
    observed_condition: str
    expected_condition: str
    attempt_count: int
    public_message: str
    source: str = field(default="RTE", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "phase": self.phase,
            "source": self.source,
            "resource": self.resource,
            "field": self.field,
            "requested_period": self.requested_period,
            "observed_condition": self.observed_condition,
            "expected_condition": self.expected_condition,
            "attempt_count": self.attempt_count,
            "public_message": self.public_message,
        }


def execute_rte_request(
    request: RestorationMarketDataRequest,
    *,
    client_id: str,
    client_secret: str,
    auth_transport: Callable[[RTETransportRequest], RTEHTTPResponse] | None = None,
    data_transport: Callable[[RTETransportRequest], RTEHTTPResponse] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[RTERawMarketResponse, ...]:
    """Authenticate in memory and retrieve all bounded source windows."""

    if not isinstance(request, RestorationMarketDataRequest):
        raise RTERequestValidationError(
            "request must be a RestorationMarketDataRequest"
        )
    if not isinstance(client_id, str) or not client_id:
        raise RTEAuthenticationError("RTE authentication requires a client ID")
    if not isinstance(client_secret, str) or not client_secret:
        raise RTEAuthenticationError("RTE authentication requires a client secret")
    selected_auth_transport = auth_transport or _stdlib_transport
    selected_data_transport = data_transport or _stdlib_transport
    selected_clock = clock or (lambda: datetime.now(UTC))
    selected_sleeper = sleeper or time.sleep
    session = _obtain_oauth_session(
        client_id=client_id,
        client_secret=client_secret,
        transport=selected_auth_transport,
    )
    responses: list[RTERawMarketResponse] = []
    for window in build_rte_query_windows(request):
        response, attempt_count, session = _retrieve_window(
            request=request,
            window=window,
            session=session,
            client_id=client_id,
            client_secret=client_secret,
            auth_transport=selected_auth_transport,
            data_transport=selected_data_transport,
            sleeper=selected_sleeper,
        )
        retrieved = selected_clock()
        if (
            not isinstance(retrieved, datetime)
            or retrieved.tzinfo is None
            or retrieved.utcoffset() != timedelta(0)
        ):
            raise RTETransportError("acquisition clock must return an aware UTC time")
        revision = _header(response.headers, "ETag") or _header(
            response.headers, "Last-Modified"
        )
        responses.append(
            RTERawMarketResponse(
                request_id=window.request_id,
                resource=window.resource,
                start_utc=window.start_utc,
                end_utc=window.end_utc,
                retrieved_at_utc=retrieved.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                media_type=response.media_type,
                body=response.body,
                raw_sha256=hashlib.sha256(response.body).hexdigest(),
                attempt_count=attempt_count,
                source_revision=revision,
            )
        )
    return tuple(responses)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return str(value)
    return None


def _is_json_media_type(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.split(";", 1)[0].strip().casefold() in {
        "application/json",
        "application/problem+json",
    }


def _validate_http_response(
    response: object,
    *,
    maximum_bytes: int,
    phase: str,
) -> RTEHTTPResponse:
    if not isinstance(response, RTEHTTPResponse):
        raise RTETransportError(
            f"RTE {phase} transport returned an invalid response type"
        )
    if isinstance(response.status, bool) or not isinstance(response.status, int):
        raise RTETransportError(f"RTE {phase} transport returned an invalid status")
    if not isinstance(response.body, bytes):
        raise RTETransportError(f"RTE {phase} response body must be bytes")
    if len(response.body) > maximum_bytes:
        raise RTETransportError(
            f"RTE {phase} response body exceeds the configured maximum bytes"
        )
    return response


def _stdlib_transport(request: RTETransportRequest) -> RTEHTTPResponse:
    """Perform one bounded synchronous HTTP call for explicit live operations."""

    transport_request = urllib.request.Request(
        request.url,
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    try:
        with urllib.request.urlopen(transport_request, timeout=30.0) as response:
            body = response.read(request.maximum_response_bytes + 1)
            headers = {str(key): str(value) for key, value in response.headers.items()}
            return RTEHTTPResponse(
                status=int(response.status),
                media_type=response.headers.get_content_type(),
                body=body,
                headers=headers,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(request.maximum_response_bytes + 1)
        headers = {str(key): str(value) for key, value in exc.headers.items()}
        return RTEHTTPResponse(
            status=int(exc.code),
            media_type=exc.headers.get_content_type(),
            body=body,
            headers=headers,
        )


def _obtain_oauth_session(
    *,
    client_id: str,
    client_secret: str,
    transport: Callable[[RTETransportRequest], RTEHTTPResponse],
) -> RTEOAuthSession:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode(
        "ascii"
    )
    request = RTETransportRequest(
        method="POST",
        url=RTE_TOKEN_ENDPOINT,
        headers=MappingProxyType(
            {
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
        ),
        body=b"grant_type=client_credentials",
        maximum_response_bytes=RTE_MAX_AUTH_RESPONSE_BYTES,
    )
    try:
        response = _validate_http_response(
            transport(request),
            maximum_bytes=RTE_MAX_AUTH_RESPONSE_BYTES,
            phase="authentication",
        )
    except RTETransportError as exc:
        raise RTEAuthenticationError(
            "RTE authentication failed after one attempt"
        ) from exc
    except Exception as exc:
        raise RTEAuthenticationError(
            "RTE authentication transport failed after one attempt"
        ) from exc
    if response.status != 200:
        raise RTEAuthenticationError(
            f"RTE authentication failed with status {response.status} after one attempt"
        )
    if not _is_json_media_type(response.media_type):
        raise RTEAuthenticationError(
            "RTE authentication returned an unsupported media type after one attempt"
        )
    try:
        payload = json.loads(response.body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise RTEAuthenticationError(
            "RTE authentication returned malformed JSON after one attempt"
        ) from exc
    if not isinstance(payload, Mapping):
        raise RTEAuthenticationError(
            "RTE authentication returned an invalid schema after one attempt"
        )
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RTEAuthenticationError(
            "RTE authentication response lacks an access token after one attempt"
        )
    expires_value = payload.get("expires_in")
    expires = None
    if isinstance(expires_value, (int, float)) and not isinstance(expires_value, bool):
        expires_float = float(expires_value)
        if math.isfinite(expires_float) and expires_float >= 0:
            expires = expires_float
    return RTEOAuthSession(access_token=token, expires_in_seconds=expires)


def _data_url(request: RestorationMarketDataRequest, window: RTEQueryWindow) -> str:
    query = urlencode(
        {
            "start_date": window.start_utc.isoformat().replace("+00:00", "Z"),
            "end_date": window.end_utc.isoformat().replace("+00:00", "Z"),
        }
    )
    return f"{request.source_endpoint}?{query}"


def _retry_delay(response: RTEHTTPResponse | None, *, attempt: int) -> float:
    if response is not None:
        value = _header(response.headers, "Retry-After")
        if value is not None:
            try:
                parsed = float(value)
            except ValueError:
                parsed = -1.0
            if math.isfinite(parsed) and parsed >= 0:
                return min(parsed, RTE_MAX_RETRY_AFTER_SECONDS)
    return float(attempt)


def _retrieve_window(
    *,
    request: RestorationMarketDataRequest,
    window: RTEQueryWindow,
    session: RTEOAuthSession,
    client_id: str,
    client_secret: str,
    auth_transport: Callable[[RTETransportRequest], RTEHTTPResponse],
    data_transport: Callable[[RTETransportRequest], RTEHTTPResponse],
    sleeper: Callable[[float], None],
) -> tuple[RTEHTTPResponse, int, RTEOAuthSession]:
    renewed = False
    active_session = session
    for attempt in range(1, 4):
        operation_request = RTETransportRequest(
            method="GET",
            url=_data_url(request, window),
            headers=MappingProxyType(
                {
                    "Authorization": f"Bearer {active_session.access_token}",
                    "Accept": "application/json",
                }
            ),
            maximum_response_bytes=RTE_MAX_RESPONSE_BYTES,
        )
        response: RTEHTTPResponse | None = None
        try:
            response = _validate_http_response(
                data_transport(operation_request),
                maximum_bytes=RTE_MAX_RESPONSE_BYTES,
                phase="market data",
            )
        except RTETransportError:
            raise
        except (TimeoutError, ConnectionError, OSError):
            if attempt == 3:
                raise RTETransportError(
                    "RTE market data transport failed transiently after 3 attempts"
                ) from None
            sleeper(_retry_delay(None, attempt=attempt))
            continue
        except Exception:
            raise RTETransportError(
                "RTE market data transport failed permanently after one attempt"
            ) from None
        if response.status == 200:
            if not _is_json_media_type(response.media_type):
                raise RTETransportError(
                    "RTE market data response media type must be JSON"
                )
            return response, attempt, active_session
        if response.status == 401 and not renewed:
            active_session = _obtain_oauth_session(
                client_id=client_id,
                client_secret=client_secret,
                transport=auth_transport,
            )
            renewed = True
            continue
        transient = response.status in {408, 429} or 500 <= response.status <= 599
        if transient:
            if attempt == 3:
                raise RTETransportError(
                    f"RTE market data status {response.status} remained transient after 3 attempts"
                )
            sleeper(_retry_delay(response, attempt=attempt))
            continue
        if response.status in {401, 403}:
            raise RTEAuthenticationError(
                f"RTE market data authorization failed with status {response.status} after one attempt"
            )
        raise RTETransportError(
            f"RTE market data returned permanent status {response.status} after one attempt"
        )
    raise RTETransportError("RTE market data transport exhausted 3 attempts")


__all__ = [
    "RTE_CATALOG_VERSION",
    "RTE_API_PATH_VERSION",
    "RTE_SOURCE_NAME",
    "RTE_SOURCE_ORIGIN",
    "RTE_TOKEN_ENDPOINT",
    "RTE_EXPECTED_RESOLUTION",
    "RTE_MAX_RESPONSE_BYTES",
    "RTE_MAX_AUTH_RESPONSE_BYTES",
    "RTE_MAX_RETRY_AFTER_SECONDS",
    "RTEAcquisitionMode",
    "RTERequestValidationError",
    "RTEAuthenticationError",
    "RTETransportError",
    "RTEParseError",
    "RTETransportRequest",
    "RTEHTTPResponse",
    "RTEOAuthSession",
    "RTERawMarketResponse",
    "RTERestorationProfile",
    "RTE_AFRR_PROFILE",
    "RTE_MFRR_PROFILE",
    "RTE_PROFILES",
    "RestorationMarketDataRequest",
    "RTEQueryWindow",
    "RTEAcquisitionDiagnostic",
    "build_rte_restoration_request",
    "build_rte_query_windows",
    "execute_rte_request",
]
