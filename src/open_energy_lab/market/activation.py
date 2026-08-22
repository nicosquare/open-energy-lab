"""Source-independent regulation activation import and immutable artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .time import CanonicalInterval, parse_iso8601_duration


ACTIVATION_SCHEMA_VERSION = "oel.regulation-activation.v1"
SUPPORTED_ACTIVATION_SCHEMA_VERSIONS = (ACTIVATION_SCHEMA_VERSION,)
ACTIVATION_VALUE_SEMANTICS = "interval-average normalized FCR activation"
ACTIVATION_SIGN_SEMANTICS = "positive is upward/discharge"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ActivationValidationError(ValueError):
    """Raised when activation inputs or artifacts violate the v1 contract."""


class UnsupportedActivationSchemaError(ActivationValidationError):
    """Raised before samples from an unknown schema are exposed."""


class ActivationIntegrityError(ActivationValidationError):
    """Raised when a persisted activation fingerprint fails verification."""


class ActivationPublicationError(OSError):
    """Raised when an activation trace cannot be published atomically."""


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
        raise ActivationValidationError(f"{field_name} must be a mapping")
    return {str(key): inner for key, inner in value.items()}


def _sequence(value: object, *, field_name: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ActivationValidationError(f"{field_name} must be a sequence")
    return list(value)


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActivationValidationError(f"{field_name} must be a non-empty string")
    return value


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ActivationValidationError(f"{field_name} must be finite")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ActivationValidationError(f"{field_name} must be finite")
    return normalized


def _utc(value: object, *, field_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ActivationValidationError(
                f"{field_name} must be an ISO 8601 UTC timestamp"
            ) from exc
    if not isinstance(value, datetime):
        raise ActivationValidationError(f"{field_name} must be an aware UTC datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ActivationValidationError(f"{field_name} must be an aware UTC datetime")
    return value.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            _thaw(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ActivationValidationError(
            f"activation artifact must contain finite canonical JSON: {exc}"
        ) from exc


@dataclass(frozen=True, slots=True)
class ActivationImportRequest:
    source_name: str
    source_locator: str
    source_revision: str
    source_timezone: str
    requested_start_utc: datetime
    requested_end_utc: datetime
    source_resolution: str
    source_value_kind: str
    source_sign_meaning: str
    normalization_rule: Mapping[str, object]
    redistribution_basis: Mapping[str, object]
    source_sha256: str | None = None
    source_document_type: str | None = None
    command_semantics_proof: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        source_name = _non_empty(self.source_name, field_name="source_name")
        source_locator = _non_empty(self.source_locator, field_name="source_locator")
        source_revision = _non_empty(self.source_revision, field_name="source_revision")
        source_timezone = _non_empty(self.source_timezone, field_name="source_timezone")
        try:
            ZoneInfo(source_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ActivationValidationError("source_timezone must be a valid IANA timezone") from exc
        start = _utc(self.requested_start_utc, field_name="requested_start_utc")
        end = _utc(self.requested_end_utc, field_name="requested_end_utc")
        if start >= end:
            raise ActivationValidationError(
                "requested_start_utc must precede requested_end_utc"
            )
        resolution = _non_empty(self.source_resolution, field_name="source_resolution")
        parse_iso8601_duration(resolution)
        if self.source_value_kind not in (
            "interval_average",
            "instantaneous_left_hold",
        ):
            raise ActivationValidationError(
                "unsupported activation source value kind or point semantics"
            )
        source_sign = _non_empty(
            self.source_sign_meaning,
            field_name="source_sign_meaning",
        )
        normalization = _mapping(
            self.normalization_rule,
            field_name="normalization_rule",
        )
        redistribution = _mapping(
            self.redistribution_basis,
            field_name="redistribution_basis",
        )
        if self.source_sha256 is not None:
            if not isinstance(self.source_sha256, str) or _SHA256.fullmatch(
                self.source_sha256
            ) is None:
                raise ActivationValidationError(
                    "source_sha256 must be a lowercase SHA-256 hexadecimal digest"
                )
        if self.source_document_type in ("A83", "A84"):
            if self.command_semantics_proof is None:
                raise ActivationValidationError(
                    f"{self.source_document_type} cannot be an activation trace without "
                    "explicit command semantics proof"
                )
            proof = _mapping(
                self.command_semantics_proof,
                field_name="command_semantics_proof",
            )
            required_proof = {
                "normalized_fcr_command",
                "direction",
                "interval_average",
                "temporal_resolution",
            }
            if not required_proof.issubset(proof):
                raise ActivationValidationError(
                    f"{self.source_document_type} activation proof is incomplete"
                )
        elif self.source_document_type is not None:
            _non_empty(self.source_document_type, field_name="source_document_type")
        object.__setattr__(self, "source_name", source_name)
        object.__setattr__(self, "source_locator", source_locator)
        object.__setattr__(self, "source_revision", source_revision)
        object.__setattr__(self, "source_timezone", source_timezone)
        object.__setattr__(self, "requested_start_utc", start)
        object.__setattr__(self, "requested_end_utc", end)
        object.__setattr__(self, "source_resolution", resolution)
        object.__setattr__(self, "source_sign_meaning", source_sign)
        object.__setattr__(self, "normalization_rule", _freeze(normalization))
        object.__setattr__(self, "redistribution_basis", _freeze(redistribution))
        if self.command_semantics_proof is not None:
            object.__setattr__(
                self,
                "command_semantics_proof",
                _freeze(_mapping(self.command_semantics_proof, field_name="command_semantics_proof")),
            )


@dataclass(frozen=True, slots=True)
class ActivationSample:
    interval: CanonicalInterval
    activation: float
    source_value: float | None
    source_unit: str
    conversion_ref: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "activation": self.activation,
            "source_value": self.source_value,
            "source_unit": self.source_unit,
            "conversion_ref": self.conversion_ref,
        }


@dataclass(frozen=True, slots=True)
class RegulationActivationTrace:
    schema_version: str
    trace_id: str
    created_at_utc: datetime
    covered_period: CanonicalInterval
    resolution: str
    value_semantics: str
    sign_semantics: str
    source: Mapping[str, object]
    normalization: Mapping[str, object]
    samples: tuple[ActivationSample, ...]
    content_fingerprint: str
    artifact_fingerprint: str
    retention_and_license: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "created_at_utc": _format_utc(self.created_at_utc),
            "covered_period": self.covered_period.to_dict(),
            "resolution": self.resolution,
            "value_semantics": self.value_semantics,
            "sign_semantics": self.sign_semantics,
            "source": _thaw(self.source),
            "normalization": _thaw(self.normalization),
            "samples": [sample.to_dict() for sample in self.samples],
            "content_fingerprint": self.content_fingerprint,
            "artifact_fingerprint": self.artifact_fingerprint,
            "retention_and_license": _thaw(self.retention_and_license),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RegulationActivationTrace:
        schema = payload.get("schema_version")
        if schema not in SUPPORTED_ACTIVATION_SCHEMA_VERSIONS:
            raise UnsupportedActivationSchemaError(
                f"unsupported activation schema version {schema!r}"
            )
        expected_content = payload.get("content_fingerprint")
        expected_artifact = payload.get("artifact_fingerprint")
        if not isinstance(expected_content, str) or _SHA256.fullmatch(expected_content) is None:
            raise ActivationIntegrityError("content fingerprint is malformed")
        if not isinstance(expected_artifact, str) or _SHA256.fullmatch(expected_artifact) is None:
            raise ActivationIntegrityError("artifact fingerprint is malformed")
        trace = _trace_from_payload(payload)
        if trace.content_fingerprint != expected_content:
            raise ActivationIntegrityError("content fingerprint mismatch")
        if trace.artifact_fingerprint != expected_artifact:
            raise ActivationIntegrityError("artifact fingerprint mismatch")
        return trace


def _normalization_for_mode(request: ActivationImportRequest) -> dict[str, Any]:
    rule = _mapping(request.normalization_rule, field_name="normalization_rule")
    target_sign = rule.get("target_sign")
    if target_sign != ACTIVATION_SIGN_SEMANTICS:
        raise ActivationValidationError(
            "normalization target sign must be positive is upward/discharge"
        )
    if rule.get("clip_min") != -1.0 or rule.get("clip_max") != 1.0:
        raise ActivationValidationError("normalization must declare clipping to [-1, 1]")
    if request.source_value_kind == "interval_average":
        if (
            rule.get("conversion") != "identity"
            or rule.get("point_to_interval") != "already_interval_average"
        ):
            raise ActivationValidationError(
                "normalization conversion does not agree with interval_average mode"
            )
    else:
        if (
            rule.get("conversion") != "clip_linear_frequency_droop"
            or rule.get("point_to_interval") != "instantaneous_left_hold"
        ):
            raise ActivationValidationError(
                "normalization conversion does not agree with instantaneous_left_hold mode"
            )
        nominal = _finite(
            rule.get("nominal_frequency_hz"),
            field_name="normalization.nominal_frequency_hz",
        )
        deviation = _finite(
            rule.get("full_activation_deviation_hz"),
            field_name="normalization.full_activation_deviation_hz",
        )
        if deviation <= 0:
            raise ActivationValidationError(
                "normalization full activation deviation must be positive"
            )
        rule["nominal_frequency_hz"] = nominal
        rule["full_activation_deviation_hz"] = deviation
    return rule


def _source_mapping(request: ActivationImportRequest) -> Mapping[str, object]:
    return MappingProxyType(
        {
            "name": request.source_name,
            "locator": request.source_locator,
            "revision": request.source_revision,
            "sha256": request.source_sha256,
            "timezone": request.source_timezone,
            "source_document_type": request.source_document_type,
            "source_sign_meaning": request.source_sign_meaning,
            "command_semantics_proof": _thaw(request.command_semantics_proof),
        }
    )


def _input_mapping(value: object, *, index: int) -> dict[str, Any]:
    return _mapping(value, field_name=f"source_samples[{index}]")


def _interval_samples(
    request: ActivationImportRequest,
    raw_samples: list[Any],
    *,
    step: timedelta,
) -> tuple[ActivationSample, ...]:
    samples: list[ActivationSample] = []
    for index, raw in enumerate(raw_samples):
        item = _input_mapping(raw, index=index)
        start = _utc(item.get("start_utc"), field_name=f"source_samples[{index}].start_utc")
        end = _utc(item.get("end_utc"), field_name=f"source_samples[{index}].end_utc")
        activation = _finite(item.get("value"), field_name=f"source_samples[{index}].value")
        if activation < -1.0 or activation > 1.0:
            raise ActivationValidationError(
                f"source_samples[{index}] activation is outside range [-1, 1]"
            )
        source_value_raw = item.get("source_value")
        source_value = (
            None
            if source_value_raw is None
            else _finite(
                source_value_raw,
                field_name=f"source_samples[{index}].source_value",
            )
        )
        samples.append(
            ActivationSample(
                interval=CanonicalInterval.from_utc(start, end),
                activation=activation,
                source_value=source_value,
                source_unit=_non_empty(
                    item.get("source_unit"),
                    field_name=f"source_samples[{index}].source_unit",
                ),
                conversion_ref=None,
            )
        )
    return tuple(samples)


def _local_point_to_utc(
    value: object,
    *,
    source_timezone: str,
    fold_value: object,
    field_name: str,
) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ActivationValidationError(f"{field_name} must be an ISO timestamp") from exc
    if not isinstance(value, datetime):
        raise ActivationValidationError(f"{field_name} must be a datetime")
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(UTC)
    zone = ZoneInfo(source_timezone)
    fold_zero = value.replace(tzinfo=zone, fold=0)
    fold_one = value.replace(tzinfo=zone, fold=1)
    ambiguous = fold_zero.utcoffset() != fold_one.utcoffset()
    if ambiguous and fold_value is None:
        raise ActivationValidationError(
            f"{field_name} is ambiguous in {source_timezone}; an explicit fold is required"
        )
    if fold_value not in (None, 0, 1):
        raise ActivationValidationError(f"{field_name} fold must be 0 or 1")
    localized = value.replace(tzinfo=zone, fold=int(fold_value or 0))
    round_trip = localized.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if round_trip != value:
        raise ActivationValidationError(
            f"{field_name} does not exist in source timezone {source_timezone}"
        )
    return localized.astimezone(UTC)


def _left_hold_samples(
    request: ActivationImportRequest,
    raw_samples: list[Any],
    *,
    step: timedelta,
    normalization: Mapping[str, Any],
) -> tuple[ActivationSample, ...]:
    nominal = float(normalization["nominal_frequency_hz"])
    deviation = float(normalization["full_activation_deviation_hz"])
    samples: list[ActivationSample] = []
    for index, raw in enumerate(raw_samples):
        item = _input_mapping(raw, index=index)
        start = _local_point_to_utc(
            item.get("timestamp"),
            source_timezone=request.source_timezone,
            fold_value=item.get("fold"),
            field_name=f"source_samples[{index}].timestamp",
        )
        source_value = _finite(
            item.get("value"),
            field_name=f"source_samples[{index}].value",
        )
        normalized = (nominal - source_value) / deviation
        activation = max(-1.0, min(1.0, normalized))
        samples.append(
            ActivationSample(
                interval=CanonicalInterval.from_utc(start, start + step),
                activation=activation,
                source_value=source_value,
                source_unit=_non_empty(
                    item.get("source_unit"),
                    field_name=f"source_samples[{index}].source_unit",
                ),
                conversion_ref="frequency-droop-left-hold-v1",
            )
        )
    return tuple(samples)


def _validate_sample_tiling(
    samples: tuple[ActivationSample, ...],
    *,
    start: datetime,
    end: datetime,
    step: timedelta,
) -> None:
    if not samples:
        raise ActivationValidationError("activation samples must not be empty")
    for index, sample in enumerate(samples):
        if index:
            previous = samples[index - 1]
            if sample.interval.start_utc != previous.interval.end_utc:
                if sample.interval.start_utc < previous.interval.end_utc:
                    relation = "duplicate or overlap"
                else:
                    relation = "gap"
                raise ActivationValidationError(
                    f"activation sample coverage contains a {relation} before index {index}"
                )
    for index, sample in enumerate(samples):
        if sample.interval.end_utc - sample.interval.start_utc != step:
            raise ActivationValidationError(
                f"source_samples[{index}] duration must match declared resolution"
            )
    if samples[0].interval.start_utc != start or samples[-1].interval.end_utc != end:
        raise ActivationValidationError(
            "activation samples must exactly cover the requested period"
        )


def _content_payload(trace: RegulationActivationTrace) -> dict[str, object]:
    return {
        "schema_version": trace.schema_version,
        "covered_period": trace.covered_period.to_dict(),
        "resolution": trace.resolution,
        "value_semantics": trace.value_semantics,
        "sign_semantics": trace.sign_semantics,
        "source": _thaw(trace.source),
        "normalization": _thaw(trace.normalization),
        "samples": [sample.to_dict() for sample in trace.samples],
        "retention_and_license": _thaw(trace.retention_and_license),
    }


def _artifact_payload(trace: RegulationActivationTrace) -> dict[str, object]:
    payload = trace.to_dict()
    payload.pop("artifact_fingerprint")
    return payload


def _build_trace(
    *,
    trace_id: str,
    created_at_utc: datetime,
    covered_period: CanonicalInterval,
    resolution: str,
    source: Mapping[str, object],
    normalization: Mapping[str, object],
    samples: tuple[ActivationSample, ...],
    retention_and_license: Mapping[str, object],
) -> RegulationActivationTrace:
    provisional = RegulationActivationTrace(
        schema_version=ACTIVATION_SCHEMA_VERSION,
        trace_id=_non_empty(trace_id, field_name="trace_id"),
        created_at_utc=_utc(created_at_utc, field_name="created_at_utc"),
        covered_period=covered_period,
        resolution=resolution,
        value_semantics=ACTIVATION_VALUE_SEMANTICS,
        sign_semantics=ACTIVATION_SIGN_SEMANTICS,
        source=_freeze(source),
        normalization=_freeze(normalization),
        samples=samples,
        content_fingerprint="0" * 64,
        artifact_fingerprint="0" * 64,
        retention_and_license=_freeze(retention_and_license),
    )
    content = hashlib.sha256(_canonical_json(_content_payload(provisional))).hexdigest()
    with_content = RegulationActivationTrace(
        **{
            **{
                name: getattr(provisional, name)
                for name in provisional.__dataclass_fields__
                if name not in {"content_fingerprint", "artifact_fingerprint"}
            },
            "content_fingerprint": content,
            "artifact_fingerprint": "0" * 64,
        }
    )
    artifact = hashlib.sha256(_canonical_json(_artifact_payload(with_content))).hexdigest()
    return RegulationActivationTrace(
        **{
            **{
                name: getattr(with_content, name)
                for name in with_content.__dataclass_fields__
                if name != "artifact_fingerprint"
            },
            "artifact_fingerprint": artifact,
        }
    )


def import_regulation_activation_trace(
    request: ActivationImportRequest,
    source_samples: Sequence[Mapping[str, object]],
    *,
    trace_id: str,
    created_at_utc: datetime,
) -> RegulationActivationTrace:
    """Import explicitly declared interval-average or left-held source values."""

    if not isinstance(request, ActivationImportRequest):
        raise TypeError("request must be an ActivationImportRequest")
    raw_samples = _sequence(source_samples, field_name="source_samples")
    normalization = _normalization_for_mode(request)
    step = parse_iso8601_duration(request.source_resolution)
    if request.source_value_kind == "interval_average":
        samples = _interval_samples(request, raw_samples, step=step)
    else:
        samples = _left_hold_samples(
            request,
            raw_samples,
            step=step,
            normalization=normalization,
        )
    _validate_sample_tiling(
        samples,
        start=request.requested_start_utc,
        end=request.requested_end_utc,
        step=step,
    )
    return _build_trace(
        trace_id=trace_id,
        created_at_utc=created_at_utc,
        covered_period=CanonicalInterval.from_utc(
            request.requested_start_utc,
            request.requested_end_utc,
        ),
        resolution=request.source_resolution,
        source=_source_mapping(request),
        normalization=normalization,
        samples=samples,
        retention_and_license=request.redistribution_basis,
    )


def _trace_from_payload(payload: Mapping[str, Any]) -> RegulationActivationTrace:
    required = {
        "schema_version",
        "trace_id",
        "created_at_utc",
        "covered_period",
        "resolution",
        "value_semantics",
        "sign_semantics",
        "source",
        "normalization",
        "samples",
        "retention_and_license",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ActivationValidationError(
            "activation artifact is missing fields: " + ", ".join(missing)
        )
    if payload["schema_version"] != ACTIVATION_SCHEMA_VERSION:
        raise UnsupportedActivationSchemaError(
            f"unsupported activation schema version {payload['schema_version']!r}"
        )
    resolution = _non_empty(payload["resolution"], field_name="resolution")
    step = parse_iso8601_duration(resolution)
    if payload["value_semantics"] != ACTIVATION_VALUE_SEMANTICS:
        raise ActivationValidationError("unsupported activation value semantics")
    if payload["sign_semantics"] != ACTIVATION_SIGN_SEMANTICS:
        raise ActivationValidationError("unsupported activation sign semantics")
    covered = CanonicalInterval.from_dict(
        _mapping(payload["covered_period"], field_name="covered_period")
    )
    samples: list[ActivationSample] = []
    for index, raw in enumerate(_sequence(payload["samples"], field_name="samples")):
        item = _mapping(raw, field_name=f"samples[{index}]")
        interval = CanonicalInterval.from_dict(
            _mapping(item.get("interval"), field_name=f"samples[{index}].interval")
        )
        if interval.end_utc - interval.start_utc != step:
            raise ActivationValidationError(
                f"samples[{index}] duration does not match resolution"
            )
        activation = _finite(item.get("activation"), field_name=f"samples[{index}].activation")
        if activation < -1.0 or activation > 1.0:
            raise ActivationValidationError(
                f"samples[{index}] activation is outside range [-1, 1]"
            )
        source_value_raw = item.get("source_value")
        samples.append(
            ActivationSample(
                interval=interval,
                activation=activation,
                source_value=(
                    None
                    if source_value_raw is None
                    else _finite(source_value_raw, field_name=f"samples[{index}].source_value")
                ),
                source_unit=_non_empty(
                    item.get("source_unit"),
                    field_name=f"samples[{index}].source_unit",
                ),
                conversion_ref=(
                    None
                    if item.get("conversion_ref") is None
                    else _non_empty(
                        item.get("conversion_ref"),
                        field_name=f"samples[{index}].conversion_ref",
                    )
                ),
            )
        )
    sample_tuple = tuple(samples)
    _validate_sample_tiling(
        sample_tuple,
        start=covered.start_utc,
        end=covered.end_utc,
        step=parse_iso8601_duration(resolution),
    )
    return _build_trace(
        trace_id=_non_empty(payload["trace_id"], field_name="trace_id"),
        created_at_utc=_utc(payload["created_at_utc"], field_name="created_at_utc"),
        covered_period=covered,
        resolution=resolution,
        source=_mapping(payload["source"], field_name="source"),
        normalization=_mapping(payload["normalization"], field_name="normalization"),
        samples=sample_tuple,
        retention_and_license=_mapping(
            payload["retention_and_license"],
            field_name="retention_and_license",
        ),
    )


def _manifest_bytes(trace: RegulationActivationTrace) -> bytes:
    try:
        return (
            json.dumps(
                trace.to_dict(),
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ActivationValidationError("activation trace is not finite JSON") from exc


def _filename(trace: RegulationActivationTrace) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", trace.trace_id).strip("-.")
    if not safe_id or any(word in safe_id.casefold() for word in ("token", "credential", "secret")):
        raise ActivationValidationError("trace_id is not safe for an immutable filename")
    return f"{safe_id}-{trace.artifact_fingerprint}.json"


def write_regulation_activation_trace(
    trace: RegulationActivationTrace,
    *,
    destination_dir: str | os.PathLike[str],
) -> Path:
    """Atomically publish or identically reuse one immutable trace manifest."""

    if not isinstance(trace, RegulationActivationTrace):
        raise TypeError("trace must be a RegulationActivationTrace")
    verified = RegulationActivationTrace.from_dict(trace.to_dict())
    destination = Path(destination_dir)
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ActivationPublicationError("cannot create activation destination") from exc
    path = destination / _filename(verified)
    desired = _manifest_bytes(verified)
    if path.exists():
        try:
            loaded = load_regulation_activation_trace(path)
            existing = path.read_bytes()
        except (OSError, ActivationValidationError) as exc:
            raise ActivationIntegrityError(
                "existing immutable activation trace failed integrity validation"
            ) from exc
        if loaded.artifact_fingerprint != verified.artifact_fingerprint or existing != desired:
            raise ActivationIntegrityError(
                "existing immutable activation trace differs from requested bytes"
            )
        return path
    file_descriptor = -1
    temporary_path: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=destination,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "wb") as handle:
            file_descriptor = -1
            handle.write(desired)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        return path
    except OSError as exc:
        raise ActivationPublicationError("cannot atomically publish activation trace") from exc
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def load_regulation_activation_trace(
    path: str | os.PathLike[str],
) -> RegulationActivationTrace:
    """Load and verify a regulation activation trace entirely offline."""

    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
        payload = json.loads(
            text,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ActivationValidationError(
                    f"activation artifact contains non-finite JSON number {value}"
                )
            ),
        )
    except ActivationValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ActivationValidationError("activation artifact is not valid UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise ActivationValidationError("activation artifact root must be a mapping")
    return RegulationActivationTrace.from_dict(payload)


__all__ = [
    "ACTIVATION_SCHEMA_VERSION",
    "ACTIVATION_SIGN_SEMANTICS",
    "ACTIVATION_VALUE_SEMANTICS",
    "ActivationImportRequest",
    "ActivationIntegrityError",
    "ActivationPublicationError",
    "ActivationSample",
    "ActivationValidationError",
    "RegulationActivationTrace",
    "SUPPORTED_ACTIVATION_SCHEMA_VERSIONS",
    "UnsupportedActivationSchemaError",
    "import_regulation_activation_trace",
    "load_regulation_activation_trace",
    "write_regulation_activation_trace",
]
