"""Explicit RTE Balancing Energy v5.2 acquisition adapter.

The source request layer is credential-free.  Authentication and transport are
available only through explicit operation functions in this focused module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
import hashlib
import math
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

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
    auth_transport: Callable[..., object] | None = None,
    data_transport: Callable[..., object] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> object:
    """Execute an explicit credentialed request (transport implemented in T028)."""

    del request, client_id, client_secret, auth_transport, data_transport, clock, sleeper
    raise NotImplementedError("RTE OAuth transport is not implemented yet")


__all__ = [
    "RTE_CATALOG_VERSION",
    "RTE_API_PATH_VERSION",
    "RTE_SOURCE_NAME",
    "RTE_SOURCE_ORIGIN",
    "RTE_TOKEN_ENDPOINT",
    "RTE_EXPECTED_RESOLUTION",
    "RTE_MAX_RESPONSE_BYTES",
    "RTEAcquisitionMode",
    "RTERequestValidationError",
    "RTEAuthenticationError",
    "RTETransportError",
    "RTEParseError",
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
