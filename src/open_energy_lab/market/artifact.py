"""Immutable canonical France market-data artifacts and deterministic identity."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from types import MappingProxyType
from typing import Any

from .time import CanonicalInterval, MarketTimeValidationError, parse_iso8601_duration


MARKET_DATA_SCHEMA_VERSION = "oel.market-data.v1"
SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS = (MARKET_DATA_SCHEMA_VERSION,)
FRANCE_PROFILE_ID = "fr-day-ahead-symmetric-fcr-v1"
FRANCE_AREA_EIC = "10YFR-RTE------C"
FRANCE_MARKET_TIMEZONE = "Europe/Paris"

REQUIRED_SERIES_IDS = (
    "day_ahead_price",
    "fcr_contracted_volume",
    "fcr_capacity_price",
)

_SERIES_PROFILE = {
    "day_ahead_price": {
        "document_type": "A44",
        "canonical_unit": "EUR/MWh",
        "canonical_resolution": "PT1H",
        "currency": "EUR",
        "negative_allowed": True,
    },
    "fcr_contracted_volume": {
        "document_type": "A81",
        "canonical_unit": "MW",
        "canonical_resolution": "PT4H",
        "currency": None,
        "negative_allowed": False,
    },
    "fcr_capacity_price": {
        "document_type": "A89",
        "canonical_unit": "EUR/MW/h",
        "canonical_resolution": "PT4H",
        "currency": "EUR",
        "negative_allowed": False,
    },
}

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class MarketArtifactValidationError(ValueError):
    """Raised when a canonical artifact violates its schema or semantics."""


class UnsupportedMarketArtifactVersionError(MarketArtifactValidationError):
    """Raised before values from an unknown schema can be consumed."""


class MarketArtifactIntegrityError(MarketArtifactValidationError):
    """Raised when recorded bytes or fingerprints fail integrity checks."""


class MarketArtifactPublicationError(OSError):
    """Raised when an artifact cannot be published atomically."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(inner) for key, inner in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(inner) for inner in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(inner) for key, inner in value.items()}
    if isinstance(value, tuple):
        return [_thaw(inner) for inner in value]
    return value


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MarketArtifactValidationError(f"{field_name} must be a mapping")
    return {str(key): inner for key, inner in value.items()}


def _sequence(value: object, *, field_name: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MarketArtifactValidationError(f"{field_name} must be a sequence")
    return list(value)


def _required(payload: Mapping[str, Any], names: Sequence[str], *, field_name: str) -> None:
    missing = [name for name in names if name not in payload]
    if missing:
        raise MarketArtifactValidationError(
            f"{field_name} is missing required fields: {', '.join(missing)}"
        )


def _non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise MarketArtifactValidationError(f"{field_name} must be a non-empty string")
    return value


def _optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, field_name=field_name)


def _finite_number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketArtifactValidationError(f"{field_name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise MarketArtifactValidationError(f"{field_name} must be finite")
    return normalized


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise MarketArtifactValidationError(f"{field_name} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise MarketArtifactValidationError(
            f"{field_name} must be a positive integer"
        ) from exc
    if normalized <= 0 or normalized != value:
        raise MarketArtifactValidationError(f"{field_name} must be a positive integer")
    return normalized


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise MarketArtifactValidationError(
            f"{field_name} must be a non-negative integer"
        )
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise MarketArtifactValidationError(
            f"{field_name} must be a non-negative integer"
        ) from exc
    if normalized < 0 or normalized != value:
        raise MarketArtifactValidationError(
            f"{field_name} must be a non-negative integer"
        )
    return normalized


def _sha256(value: object, *, field_name: str) -> str:
    normalized = _non_empty_string(value, field_name=field_name)
    if _SHA256_PATTERN.fullmatch(normalized) is None:
        raise MarketArtifactValidationError(
            f"{field_name} must be a lowercase SHA-256 hexadecimal digest"
        )
    return normalized


def _utc_timestamp(value: object, *, field_name: str) -> str:
    normalized = _non_empty_string(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketArtifactValidationError(
            f"{field_name} must be an ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise MarketArtifactValidationError(f"{field_name} must be an aware UTC timestamp")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _interval(value: object, *, field_name: str) -> CanonicalInterval:
    try:
        return CanonicalInterval.from_dict(_mapping(value, field_name=field_name))
    except MarketTimeValidationError as exc:
        raise MarketArtifactValidationError(f"{field_name}: {exc}") from exc


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON deterministically for hashing, rejecting NaN and infinity."""

    try:
        return json.dumps(
            _thaw(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MarketArtifactValidationError(
            f"value is not canonical finite JSON: {exc}"
        ) from exc


@dataclass(frozen=True, slots=True)
class MarketObservation:
    interval: CanonicalInterval
    value: float
    document_ref: str
    source_position: int | None
    conversion_ref: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "value": self.value,
            "document_ref": self.document_ref,
            "source_position": self.source_position,
            "conversion_ref": self.conversion_ref,
        }


@dataclass(frozen=True, slots=True)
class MarketSeries:
    series_id: str
    semantic_version: str
    area_eic: str
    source_document_type: str
    source_resolution: str | tuple[str, ...]
    canonical_resolution: str
    source_unit: str
    canonical_unit: str
    currency: str | None
    conversion: Mapping[str, object] | None
    observations: tuple[MarketObservation, ...]
    diagnostics: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "series_id": self.series_id,
            "semantic_version": self.semantic_version,
            "area_eic": self.area_eic,
            "source_document_type": self.source_document_type,
            "source_resolution": _thaw(self.source_resolution),
            "canonical_resolution": self.canonical_resolution,
            "source_unit": self.source_unit,
            "canonical_unit": self.canonical_unit,
            "currency": self.currency,
            "conversion": _thaw(self.conversion),
            "observations": [item.to_dict() for item in self.observations],
            "diagnostics": _thaw(self.diagnostics),
        }


@dataclass(frozen=True, slots=True)
class SourceQueryWindow:
    window_id: str
    document_type: str
    process_type: str | None
    business_type: str | None
    area_parameter: str
    start_utc: str
    end_utc: str
    attempt_count: int
    market_agreement_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "window_id": self.window_id,
            "document_type": self.document_type,
            "process_type": self.process_type,
            "business_type": self.business_type,
            "area_parameter": self.area_parameter,
            "start_utc": self.start_utc,
            "end_utc": self.end_utc,
            "attempt_count": self.attempt_count,
        }
        if self.market_agreement_type is not None:
            payload["market_agreement_type"] = self.market_agreement_type
        return payload


@dataclass(frozen=True, slots=True)
class RawResponseEvidence:
    response_id: str
    window_id: str
    retrieved_at_utc: str
    media_type: str
    byte_count: int
    sha256: str
    retention_status: str
    redistribution_basis: Mapping[str, object]
    sidecar_locator: str | None
    sidecar_sha256: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "response_id": self.response_id,
            "window_id": self.window_id,
            "retrieved_at_utc": self.retrieved_at_utc,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "retention_status": self.retention_status,
            "redistribution_basis": _thaw(self.redistribution_basis),
            "sidecar_locator": self.sidecar_locator,
            "sidecar_sha256": self.sidecar_sha256,
        }


@dataclass(frozen=True, slots=True)
class SourceDocumentEvidence:
    document_ref: str
    response_id: str
    namespace_uri: str
    root_document_type: str
    document_mrid: str
    revision_number: int
    created_at_utc: str
    document_type: str
    process_type: str | None
    business_type: str | None
    flow_direction: str | None
    area_eic: str
    market_agreement_type: str | None
    product_identity: Mapping[str, object]
    document_period: CanonicalInterval
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "document_ref": self.document_ref,
            "response_id": self.response_id,
            "namespace_uri": self.namespace_uri,
            "root_document_type": self.root_document_type,
            "document_mrid": self.document_mrid,
            "revision_number": self.revision_number,
            "created_at_utc": self.created_at_utc,
            "document_type": self.document_type,
            "process_type": self.process_type,
            "business_type": self.business_type,
            "flow_direction": self.flow_direction,
            "area_eic": self.area_eic,
            "market_agreement_type": self.market_agreement_type,
            "product_identity": _thaw(self.product_identity),
            "document_period": self.document_period.to_dict(),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class MarketDataArtifact:
    schema_version: str
    artifact_id: str
    profile_id: str
    normalization_version: str
    created_at_utc: str
    requested_period: CanonicalInterval
    actual_covered_period: CanonicalInterval
    area: Mapping[str, object]
    series: Mapping[str, MarketSeries]
    query_windows: tuple[SourceQueryWindow, ...]
    raw_responses: tuple[RawResponseEvidence, ...]
    source_documents: tuple[SourceDocumentEvidence, ...]
    content_fingerprint: str
    artifact_fingerprint: str
    predecessor_artifact_fingerprint: str | None
    retention_and_license: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "profile_id": self.profile_id,
            "normalization_version": self.normalization_version,
            "created_at_utc": self.created_at_utc,
            "requested_period": self.requested_period.to_dict(),
            "actual_covered_period": self.actual_covered_period.to_dict(),
            "area": _thaw(self.area),
            "series": {
                series_id: self.series[series_id].to_dict()
                for series_id in REQUIRED_SERIES_IDS
            },
            "query_windows": [item.to_dict() for item in self.query_windows],
            "raw_responses": [item.to_dict() for item in self.raw_responses],
            "source_documents": [item.to_dict() for item in self.source_documents],
            "content_fingerprint": self.content_fingerprint,
            "artifact_fingerprint": self.artifact_fingerprint,
            "predecessor_artifact_fingerprint": self.predecessor_artifact_fingerprint,
            "retention_and_license": _thaw(self.retention_and_license),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MarketDataArtifact:
        """Construct and verify one complete persisted manifest."""

        content_fingerprint = _sha256(
            payload.get("content_fingerprint"), field_name="content_fingerprint"
        )
        artifact_fingerprint = _sha256(
            payload.get("artifact_fingerprint"), field_name="artifact_fingerprint"
        )
        artifact = _build_market_data_artifact(payload)
        if artifact.content_fingerprint != content_fingerprint:
            raise MarketArtifactIntegrityError("content_fingerprint mismatch")
        if artifact.artifact_fingerprint != artifact_fingerprint:
            raise MarketArtifactIntegrityError("artifact_fingerprint mismatch")
        return artifact


def _market_observation(
    payload: object,
    *,
    series_id: str,
    index: int,
    negative_allowed: bool,
    conversion_required: bool,
) -> MarketObservation:
    data = _mapping(payload, field_name=f"series.{series_id}.observations[{index}]")
    _required(
        data,
        ("interval", "value", "document_ref", "source_position", "conversion_ref"),
        field_name=f"series.{series_id}.observations[{index}]",
    )
    value = _finite_number(
        data["value"], field_name=f"series.{series_id}.observations[{index}].value"
    )
    if not negative_allowed and value < 0:
        raise MarketArtifactValidationError(
            f"{series_id} observations must be non-negative"
        )
    position_value = data["source_position"]
    source_position = None
    if position_value is not None:
        source_position = _positive_int(
            position_value,
            field_name=f"series.{series_id}.observations[{index}].source_position",
        )
    conversion_ref = _optional_string(
        data["conversion_ref"],
        field_name=f"series.{series_id}.observations[{index}].conversion_ref",
    )
    if conversion_required and conversion_ref is None:
        raise MarketArtifactValidationError(
            f"{series_id} observations require a conversion_ref"
        )
    return MarketObservation(
        interval=_interval(
            data["interval"],
            field_name=f"series.{series_id}.observations[{index}].interval",
        ),
        value=value,
        document_ref=_non_empty_string(
            data["document_ref"],
            field_name=f"series.{series_id}.observations[{index}].document_ref",
        ),
        source_position=source_position,
        conversion_ref=conversion_ref,
    )


def _market_series(
    series_id: str,
    payload: object,
    *,
    actual_covered_period: CanonicalInterval,
) -> MarketSeries:
    data = _mapping(payload, field_name=f"series.{series_id}")
    _required(
        data,
        (
            "series_id",
            "semantic_version",
            "area_eic",
            "source_document_type",
            "source_resolution",
            "canonical_resolution",
            "source_unit",
            "canonical_unit",
            "currency",
            "conversion",
            "observations",
            "diagnostics",
        ),
        field_name=f"series.{series_id}",
    )
    if data["series_id"] != series_id:
        raise MarketArtifactValidationError(
            f"series key {series_id} does not match series_id {data['series_id']!r}"
        )
    expected = _SERIES_PROFILE[series_id]
    for field, expected_value in (
        ("source_document_type", expected["document_type"]),
        ("canonical_resolution", expected["canonical_resolution"]),
        ("canonical_unit", expected["canonical_unit"]),
        ("currency", expected["currency"]),
    ):
        if data[field] != expected_value:
            raise MarketArtifactValidationError(
                f"{series_id} {field} must be {expected_value!r}, got {data[field]!r}"
            )
    if data["area_eic"] != FRANCE_AREA_EIC:
        raise MarketArtifactValidationError(
            f"{series_id} area_eic must be the France profile {FRANCE_AREA_EIC}"
        )
    source_unit = _non_empty_string(
        data["source_unit"], field_name=f"series.{series_id}.source_unit"
    )
    canonical_unit = str(expected["canonical_unit"])
    conversion_data = data["conversion"]
    conversion: Mapping[str, object] | None
    if source_unit == canonical_unit:
        if conversion_data is not None:
            conversion = _freeze(
                _mapping(conversion_data, field_name=f"series.{series_id}.conversion")
            )
        else:
            conversion = None
    else:
        if conversion_data is None:
            raise MarketArtifactValidationError(
                f"{series_id} source/canonical unit conversion must be declared"
            )
        conversion = _freeze(
            _mapping(conversion_data, field_name=f"series.{series_id}.conversion")
        )
    source_resolution_value = data["source_resolution"]
    if isinstance(source_resolution_value, str):
        parse_iso8601_duration(source_resolution_value)
        source_resolution: str | tuple[str, ...] = source_resolution_value
    else:
        source_resolutions = tuple(
            _non_empty_string(value, field_name=f"series.{series_id}.source_resolution")
            for value in _sequence(
                source_resolution_value,
                field_name=f"series.{series_id}.source_resolution",
            )
        )
        if not source_resolutions:
            raise MarketArtifactValidationError(
                f"series.{series_id}.source_resolution must not be empty"
            )
        for value in source_resolutions:
            parse_iso8601_duration(value)
        source_resolution = source_resolutions
    canonical_resolution = str(expected["canonical_resolution"])
    expected_duration = parse_iso8601_duration(canonical_resolution)
    observations = tuple(
        _market_observation(
            raw,
            series_id=series_id,
            index=index,
            negative_allowed=bool(expected["negative_allowed"]),
            conversion_required=source_unit != canonical_unit,
        )
        for index, raw in enumerate(
            _sequence(data["observations"], field_name=f"series.{series_id}.observations")
        )
    )
    if not observations:
        raise MarketArtifactValidationError(f"{series_id} coverage is empty")
    for index, observation in enumerate(observations):
        duration = observation.interval.end_utc - observation.interval.start_utc
        if duration != expected_duration:
            raise MarketArtifactValidationError(
                f"{series_id} observation {index} has unexpected resolution"
            )
        if index:
            previous = observations[index - 1]
            if observation.interval.start_utc != previous.interval.end_utc:
                relation = (
                    "overlap"
                    if observation.interval.start_utc < previous.interval.end_utc
                    else "gap"
                )
                raise MarketArtifactValidationError(
                    f"{series_id} coverage contains a {relation} before observation {index}"
                )
    if observations[0].interval.start_utc != actual_covered_period.start_utc:
        raise MarketArtifactValidationError(
            f"{series_id} coverage does not start at actual_covered_period"
        )
    if observations[-1].interval.end_utc != actual_covered_period.end_utc:
        raise MarketArtifactValidationError(
            f"{series_id} coverage does not end at actual_covered_period"
        )
    return MarketSeries(
        series_id=series_id,
        semantic_version=_non_empty_string(
            data["semantic_version"], field_name=f"series.{series_id}.semantic_version"
        ),
        area_eic=FRANCE_AREA_EIC,
        source_document_type=str(expected["document_type"]),
        source_resolution=source_resolution,
        canonical_resolution=canonical_resolution,
        source_unit=source_unit,
        canonical_unit=canonical_unit,
        currency=expected["currency"] if isinstance(expected["currency"], str) else None,
        conversion=conversion,
        observations=observations,
        diagnostics=_freeze(
            _mapping(data["diagnostics"], field_name=f"series.{series_id}.diagnostics")
        ),
    )


def _query_window(payload: object, *, index: int) -> SourceQueryWindow:
    data = _mapping(payload, field_name=f"query_windows[{index}]")
    _required(
        data,
        (
            "window_id",
            "document_type",
            "process_type",
            "business_type",
            "area_parameter",
            "start_utc",
            "end_utc",
            "attempt_count",
        ),
        field_name=f"query_windows[{index}]",
    )
    start = _utc_timestamp(data["start_utc"], field_name=f"query_windows[{index}].start_utc")
    end = _utc_timestamp(data["end_utc"], field_name=f"query_windows[{index}].end_utc")
    if datetime.fromisoformat(start.replace("Z", "+00:00")) >= datetime.fromisoformat(
        end.replace("Z", "+00:00")
    ):
        raise MarketArtifactValidationError(f"query_windows[{index}] start must precede end")
    return SourceQueryWindow(
        window_id=_non_empty_string(data["window_id"], field_name=f"query_windows[{index}].window_id"),
        document_type=_non_empty_string(
            data["document_type"], field_name=f"query_windows[{index}].document_type"
        ),
        process_type=_optional_string(
            data["process_type"], field_name=f"query_windows[{index}].process_type"
        ),
        business_type=_optional_string(
            data["business_type"], field_name=f"query_windows[{index}].business_type"
        ),
        area_parameter=_non_empty_string(
            data["area_parameter"], field_name=f"query_windows[{index}].area_parameter"
        ),
        start_utc=start,
        end_utc=end,
        attempt_count=_positive_int(
            data["attempt_count"], field_name=f"query_windows[{index}].attempt_count"
        ),
        market_agreement_type=_optional_string(
            data.get("market_agreement_type"),
            field_name=f"query_windows[{index}].market_agreement_type",
        ),
    )


def _safe_sidecar_locator(value: str, *, field_name: str) -> str:
    if "\\" in value or ":" in value:
        raise MarketArtifactValidationError(
            f"{field_name} must be a portable safe relative sidecar path"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise MarketArtifactValidationError(
            f"{field_name} must be a safe relative sidecar path without traversal"
        )
    return value


def _raw_response(payload: object, *, index: int) -> RawResponseEvidence:
    data = _mapping(payload, field_name=f"raw_responses[{index}]")
    _required(
        data,
        (
            "response_id",
            "window_id",
            "retrieved_at_utc",
            "media_type",
            "byte_count",
            "sha256",
            "retention_status",
            "redistribution_basis",
            "sidecar_locator",
            "sidecar_sha256",
        ),
        field_name=f"raw_responses[{index}]",
    )
    status = _non_empty_string(
        data["retention_status"], field_name=f"raw_responses[{index}].retention_status"
    )
    if status not in {"digest_only", "sidecar_retained"}:
        raise MarketArtifactValidationError(
            f"raw_responses[{index}].retention_status is unsupported"
        )
    response_digest = _sha256(data["sha256"], field_name=f"raw_responses[{index}].sha256")
    locator = _optional_string(
        data["sidecar_locator"], field_name=f"raw_responses[{index}].sidecar_locator"
    )
    sidecar_digest = (
        None
        if data["sidecar_sha256"] is None
        else _sha256(
            data["sidecar_sha256"],
            field_name=f"raw_responses[{index}].sidecar_sha256",
        )
    )
    if status == "digest_only" and (locator is not None or sidecar_digest is not None):
        raise MarketArtifactValidationError(
            "digest_only raw response evidence cannot claim a sidecar"
        )
    if status == "sidecar_retained":
        if locator is None or sidecar_digest is None:
            raise MarketArtifactValidationError(
                "sidecar_retained evidence requires sidecar locator and digest"
            )
        locator = _safe_sidecar_locator(
            locator, field_name=f"raw_responses[{index}].sidecar_locator"
        )
        if sidecar_digest != response_digest:
            raise MarketArtifactValidationError(
                "retained sidecar digest must equal the raw response digest"
            )
    return RawResponseEvidence(
        response_id=_non_empty_string(
            data["response_id"], field_name=f"raw_responses[{index}].response_id"
        ),
        window_id=_non_empty_string(
            data["window_id"], field_name=f"raw_responses[{index}].window_id"
        ),
        retrieved_at_utc=_utc_timestamp(
            data["retrieved_at_utc"], field_name=f"raw_responses[{index}].retrieved_at_utc"
        ),
        media_type=_non_empty_string(
            data["media_type"], field_name=f"raw_responses[{index}].media_type"
        ),
        byte_count=_positive_int(
            data["byte_count"], field_name=f"raw_responses[{index}].byte_count"
        ),
        sha256=response_digest,
        retention_status=status,
        redistribution_basis=_freeze(
            _mapping(
                data["redistribution_basis"],
                field_name=f"raw_responses[{index}].redistribution_basis",
            )
        ),
        sidecar_locator=locator,
        sidecar_sha256=sidecar_digest,
    )


def _source_document(payload: object, *, index: int) -> SourceDocumentEvidence:
    data = _mapping(payload, field_name=f"source_documents[{index}]")
    required = (
        "document_ref",
        "response_id",
        "namespace_uri",
        "root_document_type",
        "document_mrid",
        "revision_number",
        "created_at_utc",
        "document_type",
        "process_type",
        "business_type",
        "flow_direction",
        "area_eic",
        "market_agreement_type",
        "product_identity",
        "document_period",
        "status",
    )
    _required(data, required, field_name=f"source_documents[{index}]")
    status = _non_empty_string(data["status"], field_name=f"source_documents[{index}].status")
    if status not in {"selected", "superseded"}:
        raise MarketArtifactValidationError(
            f"source_documents[{index}].status must be selected or superseded"
        )
    area = _non_empty_string(data["area_eic"], field_name=f"source_documents[{index}].area_eic")
    if area != FRANCE_AREA_EIC:
        raise MarketArtifactValidationError(
            f"source_documents[{index}] area must be the France profile"
        )
    return SourceDocumentEvidence(
        document_ref=_non_empty_string(
            data["document_ref"], field_name=f"source_documents[{index}].document_ref"
        ),
        response_id=_non_empty_string(
            data["response_id"], field_name=f"source_documents[{index}].response_id"
        ),
        namespace_uri=_non_empty_string(
            data["namespace_uri"], field_name=f"source_documents[{index}].namespace_uri"
        ),
        root_document_type=_non_empty_string(
            data["root_document_type"],
            field_name=f"source_documents[{index}].root_document_type",
        ),
        document_mrid=_non_empty_string(
            data["document_mrid"], field_name=f"source_documents[{index}].document_mrid"
        ),
        revision_number=_non_negative_int(
            data["revision_number"],
            field_name=f"source_documents[{index}].revision_number",
        ),
        created_at_utc=_utc_timestamp(
            data["created_at_utc"], field_name=f"source_documents[{index}].created_at_utc"
        ),
        document_type=_non_empty_string(
            data["document_type"], field_name=f"source_documents[{index}].document_type"
        ),
        process_type=_optional_string(
            data["process_type"], field_name=f"source_documents[{index}].process_type"
        ),
        business_type=_optional_string(
            data["business_type"], field_name=f"source_documents[{index}].business_type"
        ),
        flow_direction=_optional_string(
            data["flow_direction"], field_name=f"source_documents[{index}].flow_direction"
        ),
        area_eic=area,
        market_agreement_type=_optional_string(
            data["market_agreement_type"],
            field_name=f"source_documents[{index}].market_agreement_type",
        ),
        product_identity=_freeze(
            _mapping(
                data["product_identity"],
                field_name=f"source_documents[{index}].product_identity",
            )
        ),
        document_period=_interval(
            data["document_period"],
            field_name=f"source_documents[{index}].document_period",
        ),
        status=status,
    )


def _validate_evidence_links(
    *,
    series: Mapping[str, MarketSeries],
    query_windows: tuple[SourceQueryWindow, ...],
    raw_responses: tuple[RawResponseEvidence, ...],
    source_documents: tuple[SourceDocumentEvidence, ...],
) -> None:
    window_ids = [window.window_id for window in query_windows]
    response_ids = [response.response_id for response in raw_responses]
    document_refs = [document.document_ref for document in source_documents]
    for label, values in (
        ("query window", window_ids),
        ("raw response", response_ids),
        ("source document", document_refs),
    ):
        if len(values) != len(set(values)):
            raise MarketArtifactValidationError(f"duplicate {label} identity")
    if set(response.window_id for response in raw_responses) - set(window_ids):
        raise MarketArtifactValidationError("raw response references an unknown query window")
    if set(document.response_id for document in source_documents) - set(response_ids):
        raise MarketArtifactValidationError("source document references an unknown response")
    documents = {document.document_ref: document for document in source_documents}
    for series_id, market_series in series.items():
        for observation in market_series.observations:
            document = documents.get(observation.document_ref)
            if document is None or document.status != "selected":
                raise MarketArtifactValidationError(
                    f"{series_id} observation references an unknown or superseded document"
                )
            if document.document_type != market_series.source_document_type:
                raise MarketArtifactValidationError(
                    f"{series_id} observation document type does not match the series"
                )


def _validate_cross_series_fcr(
    series: Mapping[str, MarketSeries],
    source_documents: tuple[SourceDocumentEvidence, ...],
) -> None:
    volume = series["fcr_contracted_volume"]
    price = series["fcr_capacity_price"]
    volume_intervals = tuple(item.interval.to_dict() for item in volume.observations)
    price_intervals = tuple(item.interval.to_dict() for item in price.observations)
    if volume_intervals != price_intervals:
        raise MarketArtifactValidationError(
            "FCR A81 volume and A89 capacity price intervals must align exactly"
        )
    selected_by_type = {
        document.document_type: document
        for document in source_documents
        if document.status == "selected" and document.document_type in {"A81", "A89"}
    }
    if set(selected_by_type) != {"A81", "A89"}:
        raise MarketArtifactValidationError("FCR requires selected A81 and A89 documents")
    if _thaw(selected_by_type["A81"].product_identity) != _thaw(
        selected_by_type["A89"].product_identity
    ):
        raise MarketArtifactValidationError(
            "FCR A81 and A89 product identity must align exactly"
        )


def _content_payload(artifact: MarketDataArtifact) -> dict[str, object]:
    return {
        "schema_version": artifact.schema_version,
        "profile_id": artifact.profile_id,
        "normalization_version": artifact.normalization_version,
        "requested_period": artifact.requested_period.to_dict(),
        "actual_covered_period": artifact.actual_covered_period.to_dict(),
        "area": _thaw(artifact.area),
        "series": {
            series_id: artifact.series[series_id].to_dict()
            for series_id in REQUIRED_SERIES_IDS
        },
        "source_documents": [item.to_dict() for item in artifact.source_documents],
    }


def _artifact_payload_without_fingerprint(artifact: MarketDataArtifact) -> dict[str, object]:
    payload = artifact.to_dict()
    payload.pop("artifact_fingerprint")
    return payload


def _build_market_data_artifact(payload: Mapping[str, Any]) -> MarketDataArtifact:
    data = _mapping(payload, field_name="market artifact")
    required = (
        "schema_version",
        "artifact_id",
        "profile_id",
        "normalization_version",
        "created_at_utc",
        "requested_period",
        "actual_covered_period",
        "area",
        "series",
        "query_windows",
        "raw_responses",
        "source_documents",
        "predecessor_artifact_fingerprint",
        "retention_and_license",
    )
    _required(data, required, field_name="market artifact")
    schema_version = _non_empty_string(data["schema_version"], field_name="schema_version")
    if schema_version not in SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS:
        raise UnsupportedMarketArtifactVersionError(
            f"unsupported market artifact schema_version {schema_version!r}"
        )
    profile_id = _non_empty_string(data["profile_id"], field_name="profile_id")
    if profile_id != FRANCE_PROFILE_ID:
        raise MarketArtifactValidationError(
            f"profile_id must be the France profile {FRANCE_PROFILE_ID!r}"
        )
    requested_period = _interval(data["requested_period"], field_name="requested_period")
    actual_covered_period = _interval(
        data["actual_covered_period"], field_name="actual_covered_period"
    )
    if (
        actual_covered_period.start_utc > requested_period.start_utc
        or actual_covered_period.end_utc < requested_period.end_utc
    ):
        raise MarketArtifactValidationError(
            "actual_covered_period must completely cover requested_period"
        )
    area = _mapping(data["area"], field_name="area")
    _required(area, ("eic", "name", "market_timezone"), field_name="area")
    if area["eic"] != FRANCE_AREA_EIC or area["market_timezone"] != FRANCE_MARKET_TIMEZONE:
        raise MarketArtifactValidationError(
            "area must identify France 10YFR-RTE------C in Europe/Paris"
        )
    _non_empty_string(area["name"], field_name="area.name")
    series_payload = _mapping(data["series"], field_name="series")
    if set(series_payload) != set(REQUIRED_SERIES_IDS):
        missing = [name for name in REQUIRED_SERIES_IDS if name not in series_payload]
        extra = [name for name in series_payload if name not in REQUIRED_SERIES_IDS]
        details = []
        if missing:
            details.append("missing required series: " + ", ".join(missing))
        if extra:
            details.append("unknown series: " + ", ".join(extra))
        raise MarketArtifactValidationError("; ".join(details))
    series = MappingProxyType(
        {
            series_id: _market_series(
                series_id,
                series_payload[series_id],
                actual_covered_period=actual_covered_period,
            )
            for series_id in REQUIRED_SERIES_IDS
        }
    )
    query_windows = tuple(
        _query_window(value, index=index)
        for index, value in enumerate(
            _sequence(data["query_windows"], field_name="query_windows")
        )
    )
    raw_responses = tuple(
        _raw_response(value, index=index)
        for index, value in enumerate(
            _sequence(data["raw_responses"], field_name="raw_responses")
        )
    )
    source_documents = tuple(
        _source_document(value, index=index)
        for index, value in enumerate(
            _sequence(data["source_documents"], field_name="source_documents")
        )
    )
    if not query_windows or not raw_responses or not source_documents:
        raise MarketArtifactValidationError(
            "query_windows, raw_responses, and source_documents must be non-empty"
        )
    _validate_evidence_links(
        series=series,
        query_windows=query_windows,
        raw_responses=raw_responses,
        source_documents=source_documents,
    )
    _validate_cross_series_fcr(series, source_documents)
    predecessor_value = data["predecessor_artifact_fingerprint"]
    predecessor = (
        None
        if predecessor_value is None
        else _sha256(
            predecessor_value,
            field_name="predecessor_artifact_fingerprint",
        )
    )
    provisional = MarketDataArtifact(
        schema_version=schema_version,
        artifact_id=_non_empty_string(data["artifact_id"], field_name="artifact_id"),
        profile_id=profile_id,
        normalization_version=_non_empty_string(
            data["normalization_version"], field_name="normalization_version"
        ),
        created_at_utc=_utc_timestamp(data["created_at_utc"], field_name="created_at_utc"),
        requested_period=requested_period,
        actual_covered_period=actual_covered_period,
        area=_freeze(area),
        series=series,
        query_windows=query_windows,
        raw_responses=raw_responses,
        source_documents=source_documents,
        content_fingerprint="0" * 64,
        artifact_fingerprint="0" * 64,
        predecessor_artifact_fingerprint=predecessor,
        retention_and_license=_freeze(
            _mapping(data["retention_and_license"], field_name="retention_and_license")
        ),
    )
    content_fingerprint = hashlib.sha256(
        canonical_json_bytes(_content_payload(provisional))
    ).hexdigest()
    with_content = MarketDataArtifact(
        **{
            **{
                field: getattr(provisional, field)
                for field in provisional.__dataclass_fields__
                if field not in {"content_fingerprint", "artifact_fingerprint"}
            },
            "content_fingerprint": content_fingerprint,
            "artifact_fingerprint": "0" * 64,
        }
    )
    artifact_fingerprint = hashlib.sha256(
        canonical_json_bytes(_artifact_payload_without_fingerprint(with_content))
    ).hexdigest()
    return MarketDataArtifact(
        **{
            **{
                field: getattr(with_content, field)
                for field in with_content.__dataclass_fields__
                if field != "artifact_fingerprint"
            },
            "artifact_fingerprint": artifact_fingerprint,
        }
    )


def build_market_data_artifact(payload: Mapping[str, Any]) -> MarketDataArtifact:
    """Validate producer-normalized fields and compute both artifact fingerprints."""

    return _build_market_data_artifact(payload)


def market_data_artifact_filename(artifact: MarketDataArtifact) -> str:
    """Derive an immutable, credential-independent manifest filename."""

    artifact_id = _non_empty_string(artifact.artifact_id, field_name="artifact_id")
    if any(fragment in artifact_id.casefold() for fragment in ("token", "credential", "secret")):
        raise MarketArtifactValidationError(
            "artifact_id must not contain credential or token labels"
        )
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", artifact_id).strip("-.")
    if not safe_id:
        raise MarketArtifactValidationError(
            "artifact_id does not contain any filename-safe identity characters"
        )
    fingerprint = _sha256(
        artifact.artifact_fingerprint,
        field_name="artifact_fingerprint",
    )
    return f"{safe_id}-{fingerprint}.json"


def _decode_manifest_text(text: str, *, source_name: str) -> dict[str, Any]:
    def _reject_non_finite(value: str) -> object:
        raise MarketArtifactValidationError(
            f"{source_name} contains non-finite JSON number {value}"
        )

    try:
        payload = json.loads(text, parse_constant=_reject_non_finite)
    except MarketArtifactValidationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise MarketArtifactValidationError(
            f"malformed JSON in market artifact {source_name}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise MarketArtifactValidationError(
            f"market artifact {source_name} must contain a top-level JSON object"
        )
    return payload


def _resolve_sidecar(root: Path, locator: str) -> Path:
    _safe_sidecar_locator(locator, field_name="sidecar_locator")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise MarketArtifactIntegrityError(
            f"artifact root cannot be resolved for sidecar verification: {root}"
        ) from exc
    candidate = resolved_root.joinpath(*PurePosixPath(locator).parts)
    try:
        resolved_candidate = candidate.resolve(strict=True)
    except OSError as exc:
        raise MarketArtifactIntegrityError(
            f"retained sidecar is missing or unreadable: {locator}"
        ) from exc
    if not resolved_candidate.is_relative_to(resolved_root):
        raise MarketArtifactValidationError(
            f"sidecar locator escapes the declared artifact root: {locator}"
        )
    if not resolved_candidate.is_file():
        raise MarketArtifactIntegrityError(
            f"retained sidecar is not a regular file: {locator}"
        )
    return resolved_candidate


def _verify_retained_sidecars(
    artifact: MarketDataArtifact,
    *,
    artifact_root: Path | None,
) -> None:
    retained = [
        evidence
        for evidence in artifact.raw_responses
        if evidence.retention_status == "sidecar_retained"
    ]
    if not retained:
        return
    if artifact_root is None:
        raise MarketArtifactIntegrityError(
            "artifact_root is required to verify retained sidecars"
        )
    for evidence in retained:
        assert evidence.sidecar_locator is not None
        assert evidence.sidecar_sha256 is not None
        sidecar_path = _resolve_sidecar(artifact_root, evidence.sidecar_locator)
        try:
            sidecar_bytes = sidecar_path.read_bytes()
        except OSError as exc:
            raise MarketArtifactIntegrityError(
                f"retained sidecar cannot be read: {evidence.sidecar_locator}"
            ) from exc
        observed_digest = hashlib.sha256(sidecar_bytes).hexdigest()
        if len(sidecar_bytes) != evidence.byte_count:
            raise MarketArtifactIntegrityError(
                f"retained sidecar byte count mismatch: {evidence.sidecar_locator}"
            )
        if observed_digest != evidence.sidecar_sha256 or observed_digest != evidence.sha256:
            raise MarketArtifactIntegrityError(
                f"retained sidecar SHA-256 digest mismatch: {evidence.sidecar_locator}"
            )


def load_market_data_artifact(
    source: str | os.PathLike[str] | Mapping[str, Any],
    *,
    artifact_root: str | os.PathLike[str] | None = None,
) -> MarketDataArtifact:
    """Load and fully verify one canonical artifact without any source access."""

    inferred_root: Path | None = None
    if isinstance(source, Mapping):
        payload = dict(source)
        source_name = "in-memory manifest"
    else:
        path = Path(source)
        source_name = str(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise MarketArtifactValidationError(
                f"market artifact cannot be read: {path}"
            ) from exc
        payload = _decode_manifest_text(text, source_name=source_name)
        inferred_root = path.parent
    try:
        artifact = MarketDataArtifact.from_dict(payload)
    except UnsupportedMarketArtifactVersionError:
        raise
    except MarketArtifactValidationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketArtifactValidationError(
            f"invalid market artifact {source_name}: {exc}"
        ) from exc
    root = Path(artifact_root) if artifact_root is not None else inferred_root
    _verify_retained_sidecars(artifact, artifact_root=root)
    return artifact


def _manifest_bytes(artifact: MarketDataArtifact) -> bytes:
    try:
        return (
            json.dumps(
                artifact.to_dict(),
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MarketArtifactValidationError(
            f"market artifact cannot be serialized as finite JSON: {exc}"
        ) from exc


def write_market_data_artifact(
    artifact: MarketDataArtifact,
    *,
    destination_dir: str | os.PathLike[str],
) -> Path:
    """Publish a validated immutable manifest through a sibling atomic replace."""

    if not isinstance(artifact, MarketDataArtifact):
        raise TypeError("artifact must be a MarketDataArtifact")
    verified_artifact = MarketDataArtifact.from_dict(artifact.to_dict())
    destination = Path(destination_dir)
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MarketArtifactPublicationError(
            f"cannot create artifact destination directory: {destination}"
        ) from exc
    _verify_retained_sidecars(verified_artifact, artifact_root=destination)
    output_path = destination / market_data_artifact_filename(verified_artifact)
    desired_bytes = _manifest_bytes(verified_artifact)

    if output_path.exists():
        try:
            existing = load_market_data_artifact(
                output_path,
                artifact_root=destination,
            )
            existing_bytes = output_path.read_bytes()
        except (OSError, MarketArtifactValidationError) as exc:
            raise MarketArtifactIntegrityError(
                "immutable existing market artifact failed integrity validation"
            ) from exc
        if (
            existing.artifact_fingerprint != verified_artifact.artifact_fingerprint
            or existing_bytes != desired_bytes
        ):
            raise MarketArtifactIntegrityError(
                "immutable existing market artifact differs from requested bytes"
            )
        return output_path

    file_descriptor = -1
    temporary_path: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=destination,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "wb") as stream:
            file_descriptor = -1
            stream.write(desired_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        if output_path.exists():
            raise MarketArtifactIntegrityError(
                "immutable market artifact appeared during publication"
            )
        os.replace(temporary_path, output_path)
        temporary_path = None
    except MarketArtifactIntegrityError:
        raise
    except OSError as exc:
        raise MarketArtifactPublicationError(
            f"atomic market artifact publication failed during replace: {output_path}"
        ) from exc
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return output_path


__all__ = [
    "FRANCE_AREA_EIC",
    "FRANCE_MARKET_TIMEZONE",
    "FRANCE_PROFILE_ID",
    "MARKET_DATA_SCHEMA_VERSION",
    "MarketArtifactIntegrityError",
    "MarketArtifactPublicationError",
    "MarketArtifactValidationError",
    "MarketDataArtifact",
    "MarketObservation",
    "MarketSeries",
    "RawResponseEvidence",
    "REQUIRED_SERIES_IDS",
    "SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS",
    "SourceDocumentEvidence",
    "SourceQueryWindow",
    "UnsupportedMarketArtifactVersionError",
    "build_market_data_artifact",
    "canonical_json_bytes",
    "load_market_data_artifact",
    "market_data_artifact_filename",
    "write_market_data_artifact",
]
