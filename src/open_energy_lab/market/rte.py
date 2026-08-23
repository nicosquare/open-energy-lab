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
from pathlib import Path
import time
from types import MappingProxyType
from typing import Any
import urllib.error
from urllib.parse import urlencode, urlsplit
import urllib.request

from .restoration_artifact import (
    ObservationValueState,
    RawRetentionPolicy,
    RestorationMarketArtifact,
    SeriesAvailability,
    build_restoration_market_artifact,
    canonical_restoration_json_bytes,
    write_restoration_market_artifact,
)
from .time import CanonicalInterval


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
    # mFRR is directionally sparse: the source retains both directional rows,
    # but either row may legitimately contain null SA/DA values.  A bounded
    # study that needs a non-null driver validates that selected field after
    # acquisition rather than redefining source-null as missing coverage.
    required_series_ids=(),
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
    identity_payload = dict(payload)
    identity_payload.pop("mode")
    identity = hashlib.sha256(
        canonical_restoration_json_bytes(identity_payload)
    ).hexdigest()
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
    except RTETransportError:
        raise RTEAuthenticationError(
            "RTE authentication failed after one attempt"
        ) from None
    except Exception:
        raise RTEAuthenticationError(
            "RTE authentication transport failed after one attempt"
        ) from None
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


@dataclass(frozen=True, slots=True)
class RTEParsedObservation:
    interval: CanonicalInterval
    value_state: ObservationValueState
    value: float | None
    source_row: int
    source_field: str
    document_ref: str
    conversion_ref: str | None = None


@dataclass(frozen=True, slots=True)
class RTEParsedSeries:
    series_id: str
    semantic_version: str
    source: str
    source_version: str
    resource: str
    source_field: str
    product: str
    process: str
    direction: str
    area: str
    requested_period: CanonicalInterval
    covered_period: CanonicalInterval
    source_resolution: str
    canonical_resolution: str
    source_unit: str
    canonical_unit: str
    currency: str | None
    availability: SeriesAvailability
    transformations: tuple[str, ...]
    observations: tuple[RTEParsedObservation, ...]


@dataclass(frozen=True, slots=True)
class RTENestedPriceEntry:
    interval: CanonicalInterval
    direction: str
    activation_type: str | None
    activation_type_state: ObservationValueState
    requested_price: float | str | None
    requested_price_state: ObservationValueState
    requested_volume: float | None
    requested_volume_state: ObservationValueState
    satisfied_need: float | None
    satisfied_need_state: ObservationValueState
    source_row: int
    source_entry: int


@dataclass(frozen=True, slots=True)
class RTEParsedRestorationData:
    profile: RTERestorationProfile
    requested_period: CanonicalInterval
    covered_period: CanonicalInterval
    series: tuple[RTEParsedSeries, ...]
    nested_price_entries: tuple[RTENestedPriceEntry, ...]
    transformations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ParsedRow:
    interval: CanonicalInterval
    source_row: int
    document_ref: str
    values: Mapping[str, object]
    direction: str | None = None


def _parse_error(message: str) -> RTEParseError:
    return RTEParseError(f"RTE response semantic validation failed: {message}")


def _response_json(raw: RTERawMarketResponse) -> Mapping[str, object]:
    if hashlib.sha256(raw.body).hexdigest() != raw.raw_sha256:
        raise _parse_error("raw response SHA-256 digest mismatch")
    if not _is_json_media_type(raw.media_type):
        raise _parse_error("response media type must be JSON")

    def _reject_constant(value: str) -> object:
        raise _parse_error(f"non-finite JSON number {value}")

    try:
        payload = json.loads(raw.body, parse_constant=_reject_constant)
    except RTEParseError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise _parse_error("malformed JSON response") from exc
    if not isinstance(payload, Mapping):
        raise _parse_error("top-level JSON value must be an object")
    return payload


def _source_datetime(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise _parse_error(f"{field_name} must be an aware ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _parse_error(f"{field_name} must be an aware ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _parse_error(f"{field_name} must include an explicit UTC offset")
    return parsed.astimezone(UTC)


def _source_number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        observed = repr(value)[:80] if isinstance(value, (str, type(None))) else (
            f"<{type(value).__name__}>"
        )
        raise _parse_error(
            f"{field_name} must be a finite number; observed sanitized value {observed}"
        )
    normalized = float(value)
    if not math.isfinite(normalized):
        raise _parse_error(f"{field_name} must be a finite number")
    return normalized


def _value_state(
    values: Mapping[str, object], *, field_name: str
) -> tuple[ObservationValueState, float | None]:
    if field_name not in values:
        return ObservationValueState.FIELD_ABSENT, None
    value = values[field_name]
    if value is None:
        return ObservationValueState.SOURCE_NULL, None
    return ObservationValueState.VALUE, _source_number(value, field_name=field_name)


def _root_for_response(
    request: RestorationMarketDataRequest,
    raw: RTERawMarketResponse,
) -> tuple[Mapping[str, object], Sequence[object]]:
    payload = _response_json(raw)
    if set(payload) != {request.profile.root_field}:
        raise _parse_error(
            f"expected exact {request.profile.root_field} root object"
        )
    root = payload[request.profile.root_field]
    if not isinstance(root, Mapping):
        raise _parse_error(f"{request.profile.root_field} root must be an object")
    root_start = _source_datetime(root.get("start_date"), field_name="root.start_date")
    root_end = _source_datetime(root.get("end_date"), field_name="root.end_date")
    if root_start != raw.start_utc or root_end != raw.end_utc:
        raise _parse_error("root coverage does not match the requested source window")
    if root.get("resolution") != request.profile.expected_resolution:
        raise _parse_error(
            f"root resolution must be {request.profile.expected_resolution}"
        )
    volume_unit = root.get("volume_unit", "MW")
    price_unit = root.get("price_unit", "EUR/MWh")
    if volume_unit != "MW" or price_unit != "EUR/MWh":
        raise _parse_error("source units must be MW and EUR/MWh")
    rows = root.get(request.profile.rows_field)
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise _parse_error(f"{request.profile.rows_field} must be an array")
    if not rows:
        raise _parse_error(f"{request.profile.rows_field} is empty; coverage is absent")
    return root, rows


def _row_interval(
    row: Mapping[str, object], *, row_index: int
) -> CanonicalInterval:
    start = _source_datetime(
        row.get("start_date"), field_name=f"row[{row_index}].start_date"
    )
    end = _source_datetime(
        row.get("end_date"), field_name=f"row[{row_index}].end_date"
    )
    if end - start != timedelta(minutes=15):
        raise _parse_error(
            f"row[{row_index}] duration must match PT15M resolution"
        )
    try:
        return CanonicalInterval.from_utc(start, end)
    except ValueError as exc:
        raise _parse_error(f"row[{row_index}] interval is invalid") from exc


def _validate_coverage(
    rows: Sequence[_ParsedRow],
    *,
    start: datetime,
    end: datetime,
    label: str,
) -> None:
    ordered = sorted(rows, key=lambda item: item.interval.start_utc)
    cursor = start
    seen: set[tuple[datetime, datetime]] = set()
    for row in ordered:
        identity = (row.interval.start_utc, row.interval.end_utc)
        if identity in seen:
            raise _parse_error(f"{label} contains a duplicate or conflicting interval")
        seen.add(identity)
        if row.interval.start_utc < cursor:
            raise _parse_error(f"{label} intervals overlap")
        if row.interval.start_utc > cursor:
            raise _parse_error(f"{label} coverage contains a gap")
        cursor = row.interval.end_utc
    if cursor != end:
        raise _parse_error(f"{label} coverage is incomplete or contains a gap")


_AFRR_FIELD_CONTRACT = {
    "afrr_requested_need_upward": (
        "upward_afrr_requested_need",
        "UPWARD",
        "MW",
        None,
    ),
    "afrr_requested_need_downward": (
        "downward_afrr_requested_need",
        "DOWNWARD",
        "MW",
        None,
    ),
    "afrr_activated_for_fr_upward": (
        "upward_afrr_activated_volume_for_fr",
        "UPWARD",
        "MW",
        None,
    ),
    "afrr_activated_for_fr_downward": (
        "downward_afrr_activated_volume_for_fr",
        "DOWNWARD",
        "MW",
        None,
    ),
    "afrr_activated_in_fr_upward": (
        "upward_afrr_activated_volume_in_fr",
        "UPWARD",
        "MW",
        None,
    ),
    "afrr_activated_in_fr_downward": (
        "downward_afrr_activated_volume_in_fr",
        "DOWNWARD",
        "MW",
        None,
    ),
    "afrr_weighted_average_price_upward": (
        "upward_weighted_average_price_afrr_activated_for_fr",
        "UPWARD",
        "EUR/MWh",
        "EUR",
    ),
    "afrr_weighted_average_price_downward": (
        "downward_weighted_average_price_afrr_activated_for_fr",
        "DOWNWARD",
        "EUR/MWh",
        "EUR",
    ),
}


def _parse_afrr_rows(
    request: RestorationMarketDataRequest,
    responses: Sequence[RTERawMarketResponse],
) -> tuple[tuple[_ParsedRow, ...], tuple[RTENestedPriceEntry, ...]]:
    required_fields = {
        "start_date",
        "end_date",
        *(contract[0] for contract in _AFRR_FIELD_CONTRACT.values()),
    }
    parsed: list[_ParsedRow] = []
    source_row_offset = 0
    for raw in responses:
        _, rows = _root_for_response(request, raw)
        window_rows = []
        for index, value in enumerate(rows):
            if not isinstance(value, Mapping):
                raise _parse_error(f"picasso row[{index}] must be an object")
            missing = sorted(required_fields - set(value))
            if missing:
                raise _parse_error(
                    f"picasso row[{index}] is missing field {missing[0]}"
                )
            interval = _row_interval(value, row_index=index)
            for field_name in required_fields - {"start_date", "end_date"}:
                _source_number(value[field_name], field_name=field_name)
            window_rows.append(
                _ParsedRow(
                    interval=interval,
                    source_row=source_row_offset + index,
                    document_ref=raw.request_id,
                    values=MappingProxyType(dict(value)),
                )
            )
        _validate_coverage(
            window_rows,
            start=raw.start_utc,
            end=raw.end_utc,
            label="aFRR source window",
        )
        parsed.extend(window_rows)
        source_row_offset += len(rows)
    _validate_coverage(
        parsed,
        start=request.requested_start_utc,
        end=request.requested_end_utc,
        label="aFRR requested period",
    )
    return tuple(sorted(parsed, key=lambda item: item.interval.start_utc)), ()


def _mfrr_contract(series_id: str) -> tuple[str, str, str, str, str | None]:
    direction = "UPWARD" if series_id.endswith("_upward") else "DOWNWARD"
    without_direction = series_id.removesuffix("_upward").removesuffix("_downward")
    if without_direction.startswith("mfrr_sa_"):
        meaning = without_direction.removeprefix("mfrr_sa_")
        field_name = {
            "requested_volume": "total_requested_volume_SA",
            "satisfied_need": "total_satisfied_need_SA",
            "activated_volume": "total_activated_volume_SA",
        }[meaning]
        return field_name, direction, "scheduled_activation", "MW", None
    if without_direction.startswith("mfrr_da_"):
        meaning = without_direction.removeprefix("mfrr_da_")
        field_name = {
            "requested_volume": "total_requested_volume_DA",
            "satisfied_need": "total_satisfied_need_DA",
            "activated_volume": "total_activated_volume_DA",
        }[meaning]
        return field_name, direction, "direct_activation", "MW", None
    meaning = without_direction.removeprefix("mfrr_")
    field_name = {
        "clearing_price": "clearing_price",
        "settlement_price_current": "settlement_price_current",
        "settlement_price_previous": "settlement_price_previous",
        "submitted_offer_volume": "total_volume_submitted_offers",
        "filtered_offer_volume": "total_volume_filtered_offers",
    }[meaning]
    is_price = "price" in meaning
    return (
        field_name,
        direction,
        "manual_restoration_context",
        "EUR/MWh" if is_price else "MW",
        "EUR" if is_price else None,
    )


def _nested_entries(
    row: Mapping[str, object],
    *,
    interval: CanonicalInterval,
    direction: str,
    source_row: int,
) -> tuple[RTENestedPriceEntry, ...]:
    values = row.get("requested_activated_volumes_by_prices")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _parse_error("nested requested_activated_volumes_by_prices must be an array")
    built = []

    def optional_number(
        raw_value: object, *, field_name: str
    ) -> tuple[ObservationValueState, float | None]:
        if raw_value is None:
            return ObservationValueState.SOURCE_NULL, None
        return ObservationValueState.VALUE, _source_number(
            raw_value, field_name=field_name
        )

    def optional_requested_price(
        raw_value: object,
    ) -> tuple[ObservationValueState, float | str | None]:
        if raw_value is None:
            return ObservationValueState.SOURCE_NULL, None
        if raw_value == "ATP":
            return ObservationValueState.VALUE, "ATP"
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            observed = repr(raw_value)[:80]
            raise _parse_error(
                "nested.requested_price must be finite numeric price evidence, "
                f"the ATP source meaning code, or null; observed {observed}"
            )
        return ObservationValueState.VALUE, _source_number(
            raw_value, field_name="nested.requested_price"
        )

    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise _parse_error("nested price entry must be an object")
        required = {
            "activation_type",
            "requested_price",
            "requested_volume",
            "satisfied_need",
        }
        missing = sorted(required - set(value))
        if missing:
            raise _parse_error(f"nested price entry is missing {missing[0]}")
        source_activation_type = value["activation_type"]
        if source_activation_type is None:
            activation_type = None
            activation_type_state = ObservationValueState.SOURCE_NULL
        elif isinstance(source_activation_type, str) and (
            source_activation_type.casefold() in {"sa", "da"}
        ):
            activation_type = source_activation_type.upper()
            activation_type_state = ObservationValueState.VALUE
        else:
            observed = (
                repr(source_activation_type)
                if isinstance(
                    source_activation_type, (str, int, float, bool, type(None))
                )
                else f"<{type(source_activation_type).__name__}>"
            )
            raise _parse_error(
                "nested price activation_type must be SA, DA, or source null; "
                f"observed sanitized value {observed}"
            )
        requested_price_state, requested_price = optional_requested_price(
            value["requested_price"]
        )
        requested_volume_state, requested_volume = optional_number(
            value["requested_volume"], field_name="nested.requested_volume"
        )
        satisfied_need_state, satisfied_need = optional_number(
            value["satisfied_need"], field_name="nested.satisfied_need"
        )
        built.append(
            RTENestedPriceEntry(
                interval=interval,
                direction=direction,
                activation_type=activation_type,
                activation_type_state=activation_type_state,
                requested_price=requested_price,
                requested_price_state=requested_price_state,
                requested_volume=requested_volume,
                requested_volume_state=requested_volume_state,
                satisfied_need=satisfied_need,
                satisfied_need_state=satisfied_need_state,
                source_row=source_row,
                source_entry=index,
            )
        )
    return tuple(built)


def _parse_mfrr_rows(
    request: RestorationMarketDataRequest,
    responses: Sequence[RTERawMarketResponse],
) -> tuple[tuple[_ParsedRow, ...], tuple[RTENestedPriceEntry, ...]]:
    parsed: list[_ParsedRow] = []
    nested: list[RTENestedPriceEntry] = []
    source_row_offset = 0
    for raw in responses:
        _, rows = _root_for_response(request, raw)
        window_rows: list[_ParsedRow] = []
        for index, value in enumerate(rows):
            if not isinstance(value, Mapping):
                raise _parse_error(f"mari row[{index}] must be an object")
            for field_name in (
                "start_date",
                "end_date",
                "direction",
                "requested_activated_volumes_by_prices",
            ):
                if field_name not in value:
                    raise _parse_error(f"mari row[{index}] is missing {field_name}")
            source_direction = value["direction"]
            normalized_direction = (
                source_direction.casefold()
                if isinstance(source_direction, str)
                else None
            )
            if normalized_direction not in {"upward", "downward"}:
                observed = (
                    repr(source_direction)
                    if isinstance(source_direction, (str, int, float, bool, type(None)))
                    else f"<{type(source_direction).__name__}>"
                )
                raise _parse_error(
                    "mFRR direction must be upward or downward; "
                    f"observed sanitized value {observed}"
                )
            direction = normalized_direction.upper()
            interval = _row_interval(value, row_index=index)
            source_row = source_row_offset + index
            parsed_row = _ParsedRow(
                interval=interval,
                source_row=source_row,
                document_ref=raw.request_id,
                values=MappingProxyType(dict(value)),
                direction=direction,
            )
            window_rows.append(parsed_row)
            nested.extend(
                _nested_entries(
                    value,
                    interval=interval,
                    direction=direction,
                    source_row=source_row,
                )
            )
        for direction in {item.direction for item in window_rows}:
            selected = [item for item in window_rows if item.direction == direction]
            _validate_coverage(
                selected,
                start=raw.start_utc,
                end=raw.end_utc,
                label=f"mFRR {direction} source window",
            )
        parsed.extend(window_rows)
        source_row_offset += len(rows)
    required_directions = {
        "UPWARD" if series_id.endswith("_upward") else "DOWNWARD"
        for series_id in request.requested_series_ids
    }
    for direction in required_directions:
        selected = [item for item in parsed if item.direction == direction]
        if not selected:
            raise _parse_error(f"mFRR {direction} direction coverage is missing")
        _validate_coverage(
            selected,
            start=request.requested_start_utc,
            end=request.requested_end_utc,
            label=f"mFRR {direction} requested period",
        )
    return (
        tuple(sorted(parsed, key=lambda item: (item.interval.start_utc, item.direction or ""))),
        tuple(nested),
    )


def _build_parsed_series(
    request: RestorationMarketDataRequest,
    rows: Sequence[_ParsedRow],
) -> tuple[RTEParsedSeries, ...]:
    period = CanonicalInterval.from_utc(
        request.requested_start_utc, request.requested_end_utc
    )
    built = []
    for series_id in request.requested_series_ids:
        if request.profile is RTE_AFRR_PROFILE:
            source_field, direction, unit, currency = _AFRR_FIELD_CONTRACT[series_id]
            process = "automatic_restoration"
            selected_rows = rows
        else:
            source_field, direction, process, unit, currency = _mfrr_contract(series_id)
            selected_rows = [item for item in rows if item.direction == direction]
        observations = []
        for row in selected_rows:
            state, value = _value_state(row.values, field_name=source_field)
            observations.append(
                RTEParsedObservation(
                    interval=row.interval,
                    value_state=state,
                    value=value,
                    source_row=row.source_row,
                    source_field=source_field,
                    document_ref=row.document_ref,
                )
            )
        if not observations:
            availability = SeriesAvailability.SOURCE_ABSENT
        elif any(
            item.value_state is not ObservationValueState.VALUE
            for item in observations
        ):
            availability = SeriesAvailability.PRESENT_WITH_NULLS
        else:
            availability = SeriesAvailability.PRESENT
        if series_id in request.required_series_ids and availability is not SeriesAvailability.PRESENT:
            raise _parse_error(
                f"required series {series_id} contains null or field-absent source values"
            )
        built.append(
            RTEParsedSeries(
                series_id=series_id,
                semantic_version=f"rte-v5.2-{series_id}-v1",
                source="RTE",
                source_version=RTE_CATALOG_VERSION,
                resource=request.resource_identity,
                source_field=source_field,
                product="AFRR" if request.profile is RTE_AFRR_PROFILE else "MFRR",
                process=process,
                direction=direction,
                area=RTE_AREA,
                requested_period=period,
                covered_period=period,
                source_resolution=RTE_EXPECTED_RESOLUTION,
                canonical_resolution=RTE_EXPECTED_RESOLUTION,
                source_unit=unit,
                canonical_unit=unit,
                currency=currency,
                availability=availability,
                transformations=("rte-v5.2-chronological-row-order",),
                observations=tuple(observations),
            )
        )
    return tuple(built)


def parse_rte_restoration_responses(
    request: RestorationMarketDataRequest,
    responses: Sequence[RTERawMarketResponse],
) -> RTEParsedRestorationData:
    """Parse all source windows exactly without filling, netting, or interpolation."""

    if not isinstance(request, RestorationMarketDataRequest):
        raise RTEParseError("request must be a RestorationMarketDataRequest")
    normalized = tuple(responses)
    expected_windows = build_rte_query_windows(request)
    if len(normalized) != len(expected_windows) or any(
        not isinstance(item, RTERawMarketResponse) for item in normalized
    ):
        raise _parse_error("response windows are incomplete")
    for index, (raw, window) in enumerate(zip(normalized, expected_windows, strict=True)):
        if (
            raw.request_id != window.request_id
            or raw.resource != window.resource
            or raw.start_utc != window.start_utc
            or raw.end_utc != window.end_utc
        ):
            raise _parse_error(f"response window {index} identity is incompatible")
    if request.profile is RTE_AFRR_PROFILE:
        rows, nested = _parse_afrr_rows(request, normalized)
    elif request.profile is RTE_MFRR_PROFILE:
        rows, nested = _parse_mfrr_rows(request, normalized)
    else:
        raise _parse_error("request profile is not a closed RTE restoration profile")
    period = CanonicalInterval.from_utc(
        request.requested_start_utc, request.requested_end_utc
    )
    return RTEParsedRestorationData(
        profile=request.profile,
        requested_period=period,
        covered_period=period,
        series=_build_parsed_series(request, rows),
        nested_price_entries=nested,
        transformations=("rte-v5.2-chronological-row-order",),
    )


class RestorationRefreshStatus(str, Enum):
    """Immutable refresh outcome."""

    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"


@dataclass(frozen=True, slots=True)
class RestorationFetchResult:
    artifact: RestorationMarketArtifact
    path: Path


@dataclass(frozen=True, slots=True)
class RestorationRefreshResult:
    status: RestorationRefreshStatus
    artifact: RestorationMarketArtifact
    path: Path | None


def _series_artifact_payload(series: RTEParsedSeries) -> dict[str, object]:
    return {
        "series_id": series.series_id,
        "semantic_version": series.semantic_version,
        "source": series.source,
        "source_version": series.source_version,
        "resource": series.resource,
        "source_field": series.source_field,
        "product": series.product,
        "process": series.process,
        "direction": series.direction,
        "area": series.area,
        "requested_period": series.requested_period.to_dict(),
        "covered_period": series.covered_period.to_dict(),
        "source_resolution": series.source_resolution,
        "canonical_resolution": series.canonical_resolution,
        "source_unit": series.source_unit,
        "canonical_unit": series.canonical_unit,
        "currency": series.currency,
        "availability": series.availability.value,
        "transformations": list(series.transformations),
        "observations": [
            {
                "interval": observation.interval.to_dict(),
                "value_state": observation.value_state.value,
                "value": observation.value,
                "source_row": observation.source_row,
                "source_field": observation.source_field,
                "document_ref": observation.document_ref,
                "conversion_ref": observation.conversion_ref,
            }
            for observation in series.observations
        ],
    }


def _restricted_rte_policy() -> dict[str, object]:
    return {
        "owner": "RTE",
        "attribution": "RTE Balancing Energy API v5.2; normalized by Open Energy Lab",
        "repository_storage": "permitted_private_restricted",
        "repository_publication": "prohibited",
        "package_distribution": "prohibited",
        "release_distribution": "prohibited",
        "public_ci_artifact": "prohibited",
        "public_mirror_or_fork": "prohibited",
        "external_artifact_store": "prohibited",
        "visibility_change_action": "remove_or_reassess_before_change",
    }


def _artifact_from_responses(
    request: RestorationMarketDataRequest,
    responses: tuple[RTERawMarketResponse, ...],
    *,
    predecessor_artifact_fingerprint: str | None,
) -> RestorationMarketArtifact:
    parsed = parse_rte_restoration_responses(request, responses)
    by_id = {series.series_id: series for series in parsed.series}
    retrieved_at = max(response.retrieved_at_utc for response in responses)
    payload = {
        "schema_version": "oel.restoration.market.v1",
        "artifact_id": f"rte-{request.resource_identity}-{request.request_identity[:16]}",
        "source": "RTE",
        "source_version": RTE_CATALOG_VERSION,
        "profile_id": request.profile.profile_id,
        "resource": request.resource_identity,
        "request_identity": request.request_identity,
        "requested_period": parsed.requested_period.to_dict(),
        "covered_period": parsed.covered_period.to_dict(),
        "retrieved_at_utc": retrieved_at,
        "series_manifest": {
            series_id: {
                "requested": True,
                "required": series_id in request.required_series_ids,
                "availability": by_id[series_id].availability.value,
            }
            for series_id in request.requested_series_ids
        },
        "series": [_series_artifact_payload(series) for series in parsed.series],
        "request_evidence": [
            {
                "request_id": response.request_id,
                "resource": response.resource,
                "start_utc": response.start_utc.isoformat().replace("+00:00", "Z"),
                "end_utc": response.end_utc.isoformat().replace("+00:00", "Z"),
                "attempt_count": response.attempt_count,
                "http_status_class": "2xx",
                "response_media_type": response.media_type,
                "response_bytes": len(response.body),
                "raw_sha256": response.raw_sha256,
                "source_revision": response.source_revision,
            }
            for response in responses
        ],
        "raw_retention": {
            "policy": request.raw_retention_policy.value,
            "responses": {
                response.request_id: {
                    "status": "digest_only",
                    "sidecar_locator": None,
                    "sidecar_sha256": None,
                }
                for response in responses
            },
        },
        "redistribution_policy": _restricted_rte_policy(),
        "predecessor_artifact_fingerprint": predecessor_artifact_fingerprint,
    }
    return build_restoration_market_artifact(payload)


def fetch_rte_restoration_data(
    request: RestorationMarketDataRequest,
    *,
    client_id: str,
    client_secret: str,
    output_directory: str | Path,
    auth_transport: Callable[[RTETransportRequest], RTEHTTPResponse] | None = None,
    data_transport: Callable[[RTETransportRequest], RTEHTTPResponse] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> RestorationFetchResult:
    """Retrieve, normalize, validate, then atomically publish one artifact."""

    if not isinstance(request, RestorationMarketDataRequest):
        raise RTERequestValidationError(
            "request must be a RestorationMarketDataRequest"
        )
    if request.mode is not RTEAcquisitionMode.FETCH:
        raise RTERequestValidationError("fetch operation requires request mode FETCH")
    responses = execute_rte_request(
        request,
        client_id=client_id,
        client_secret=client_secret,
        auth_transport=auth_transport,
        data_transport=data_transport,
        clock=clock,
        sleeper=sleeper,
    )
    artifact = _artifact_from_responses(
        request, responses, predecessor_artifact_fingerprint=None
    )
    path = write_restoration_market_artifact(
        artifact, destination_dir=output_directory
    )
    return RestorationFetchResult(artifact=artifact, path=path)


def refresh_rte_restoration_data(
    current_artifact: RestorationMarketArtifact,
    request: RestorationMarketDataRequest,
    *,
    client_id: str,
    client_secret: str,
    output_directory: str | Path,
    auth_transport: Callable[[RTETransportRequest], RTEHTTPResponse] | None = None,
    data_transport: Callable[[RTETransportRequest], RTEHTTPResponse] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> RestorationRefreshResult:
    """Publish one linked successor only when normalized content changed."""

    if not isinstance(current_artifact, RestorationMarketArtifact):
        raise RTERequestValidationError(
            "current_artifact must be a RestorationMarketArtifact"
        )
    if not isinstance(request, RestorationMarketDataRequest):
        raise RTERequestValidationError(
            "request must be a RestorationMarketDataRequest"
        )
    if request.mode is not RTEAcquisitionMode.REFRESH:
        raise RTERequestValidationError(
            "refresh operation requires request mode REFRESH"
        )
    if (
        current_artifact.source.value != "RTE"
        or current_artifact.request_identity != request.request_identity
        or current_artifact.profile_id != request.profile.profile_id
        or current_artifact.resource != request.resource_identity
    ):
        raise RTERequestValidationError(
            "refresh request identity/profile/resource does not match current artifact"
        )
    responses = execute_rte_request(
        request,
        client_id=client_id,
        client_secret=client_secret,
        auth_transport=auth_transport,
        data_transport=data_transport,
        clock=clock,
        sleeper=sleeper,
    )
    candidate = _artifact_from_responses(
        request,
        responses,
        predecessor_artifact_fingerprint=current_artifact.artifact_fingerprint,
    )
    if candidate.content_fingerprint == current_artifact.content_fingerprint:
        return RestorationRefreshResult(
            status=RestorationRefreshStatus.UNCHANGED,
            artifact=current_artifact,
            path=None,
        )
    path = write_restoration_market_artifact(
        candidate, destination_dir=output_directory
    )
    return RestorationRefreshResult(
        status=RestorationRefreshStatus.CHANGED,
        artifact=candidate,
        path=path,
    )


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
    "RTEParsedObservation",
    "RTEParsedSeries",
    "RTENestedPriceEntry",
    "RTEParsedRestorationData",
    "RestorationRefreshStatus",
    "RestorationFetchResult",
    "RestorationRefreshResult",
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
    "parse_rte_restoration_responses",
    "fetch_rte_restoration_data",
    "refresh_rte_restoration_data",
]
