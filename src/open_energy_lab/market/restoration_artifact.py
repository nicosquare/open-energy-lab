"""Immutable, source-separated restoration market artifacts and study bundles.

This module deliberately owns no live transport.  It validates producer-normalized
RTE or ENTSO-E observations, publishes immutable manifests, and resolves
reference-only study bundles entirely offline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import partial
import hashlib
import os
from pathlib import Path
from typing import Any

from open_energy_lab.core.artifact import (
    PLACEHOLDER_FINGERPRINT,
    immutable_filename,
    payload_without,
    publish_write_once,
    read_artifact_source,
    recorded_fingerprints,
    resolve_sidecar,
    safe_sidecar_locator,
    seal_fingerprints,
    verify_fingerprints,
    verify_sidecar_bytes,
)
from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import (
    canonical_json_bytes,
    freeze,
    json_document_bytes,
    thaw,
)
from open_energy_lab.core.time import utc_timestamp_text
from open_energy_lab.core.validation import (
    boolean,
    enum_member,
    finite,
    mapping,
    non_empty_str,
    non_negative_int,
    optional_str,
    positive_int,
    require_fields,
    sequence,
    sha256_digest,
)

from .time import CanonicalInterval, MarketTimeValidationError, parse_iso8601_duration


RESTORATION_MARKET_SCHEMA_VERSION = "oel.restoration.market.v1"
SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS = (
    RESTORATION_MARKET_SCHEMA_VERSION,
)
RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION = "oel.restoration.study-bundle.v1"
SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS = (
    RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION,
)

_RESTRICTED_POLICY_FIELDS = (
    "repository_storage",
    "repository_publication",
    "package_distribution",
    "release_distribution",
    "public_ci_artifact",
    "public_mirror_or_fork",
    "external_artifact_store",
    "visibility_change_action",
)


class ObservationValueState(str, Enum):
    """Exact state of one named source value."""

    VALUE = "VALUE"
    SOURCE_NULL = "SOURCE_NULL"
    FIELD_ABSENT = "FIELD_ABSENT"


class SeriesAvailability(str, Enum):
    """Availability of one requested or catalogued semantic series."""

    PRESENT = "PRESENT"
    PRESENT_WITH_NULLS = "PRESENT_WITH_NULLS"
    SOURCE_ABSENT = "SOURCE_ABSENT"
    NOT_REQUESTED = "NOT_REQUESTED"


class RestorationDataSource(str, Enum):
    """Closed source identity for a single acquisition artifact."""

    RTE = "RTE"
    ENTSOE = "ENTSOE"


class RawRetentionPolicy(str, Enum):
    """Allowed raw-response evidence handling."""

    DIGEST_ONLY = "DIGEST_ONLY"
    PERMITTED_SIDECAR = "PERMITTED_SIDECAR"


class RestorationArtifactValidationError(ValidationError):
    """Raised when a restoration artifact violates its semantic contract."""


class UnsupportedRestorationArtifactVersionError(
    RestorationArtifactValidationError
):
    """Raised before values from an unknown restoration schema are exposed."""


class RestorationArtifactIntegrityError(RestorationArtifactValidationError):
    """Raised when immutable bytes, sidecars, or fingerprints do not verify."""


class RestorationArtifactPublicationError(OSError):
    """Raised when an immutable manifest cannot be published atomically."""


_freeze = freeze
_thaw = thaw
_mapping = partial(mapping, error=RestorationArtifactValidationError)
_sequence = partial(sequence, error=RestorationArtifactValidationError)
_required = partial(require_fields, error=RestorationArtifactValidationError)
_non_empty_string = partial(non_empty_str, error=RestorationArtifactValidationError)
_optional_string = partial(optional_str, error=RestorationArtifactValidationError)
_finite_number = partial(finite, error=RestorationArtifactValidationError)
_non_negative_int = partial(non_negative_int, error=RestorationArtifactValidationError)
_positive_int = partial(positive_int, error=RestorationArtifactValidationError)
_boolean = partial(boolean, error=RestorationArtifactValidationError)
_sha256 = partial(sha256_digest, error=RestorationArtifactValidationError)
_utc_timestamp = partial(utc_timestamp_text, error=RestorationArtifactValidationError)
_enum_value = partial(enum_member, error=RestorationArtifactValidationError)


def _interval(value: object, *, field_name: str) -> CanonicalInterval:
    try:
        return CanonicalInterval.from_dict(_mapping(value, field_name=field_name))
    except MarketTimeValidationError as exc:
        raise RestorationArtifactValidationError(f"{field_name}: {exc}") from exc


def canonical_restoration_json_bytes(value: object) -> bytes:
    """Encode canonical finite JSON for restoration identities."""

    return canonical_json_bytes(value, error=RestorationArtifactValidationError)


@dataclass(frozen=True, slots=True)
class RestorationMarketObservation:
    interval: CanonicalInterval
    value_state: ObservationValueState
    value: float | None
    source_row: int
    source_field: str
    document_ref: str
    conversion_ref: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "value_state": self.value_state.value,
            "value": self.value,
            "source_row": self.source_row,
            "source_field": self.source_field,
            "document_ref": self.document_ref,
            "conversion_ref": self.conversion_ref,
        }


@dataclass(frozen=True, slots=True)
class RestorationMarketSeries:
    series_id: str
    semantic_version: str
    source: RestorationDataSource
    source_version: str
    resource: str
    source_field: str
    product: str | None
    process: str | None
    direction: str | None
    area: str
    requested_period: CanonicalInterval
    covered_period: CanonicalInterval
    source_resolution: str
    canonical_resolution: str
    source_unit: str
    canonical_unit: str
    currency: str | None
    availability: SeriesAvailability
    transformations: tuple[object, ...]
    observations: tuple[RestorationMarketObservation, ...]
    series_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "series_id": self.series_id,
            "semantic_version": self.semantic_version,
            "source": self.source.value,
            "source_version": self.source_version,
            "resource": self.resource,
            "source_field": self.source_field,
            "product": self.product,
            "process": self.process,
            "direction": self.direction,
            "area": self.area,
            "requested_period": self.requested_period.to_dict(),
            "covered_period": self.covered_period.to_dict(),
            "source_resolution": self.source_resolution,
            "canonical_resolution": self.canonical_resolution,
            "source_unit": self.source_unit,
            "canonical_unit": self.canonical_unit,
            "currency": self.currency,
            "availability": self.availability.value,
            "transformations": _thaw(self.transformations),
            "observations": [item.to_dict() for item in self.observations],
            "series_fingerprint": self.series_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class SourceRequestEvidence:
    request_id: str
    resource: str
    start_utc: str
    end_utc: str
    attempt_count: int
    http_status_class: str
    response_media_type: str
    response_bytes: int
    raw_sha256: str
    source_revision: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "resource": self.resource,
            "start_utc": self.start_utc,
            "end_utc": self.end_utc,
            "attempt_count": self.attempt_count,
            "http_status_class": self.http_status_class,
            "response_media_type": self.response_media_type,
            "response_bytes": self.response_bytes,
            "raw_sha256": self.raw_sha256,
            "source_revision": self.source_revision,
        }


@dataclass(frozen=True, slots=True)
class RestorationMarketArtifact:
    schema_version: str
    artifact_id: str
    source: RestorationDataSource
    source_version: str
    profile_id: str
    resource: str
    request_identity: str
    requested_period: CanonicalInterval
    covered_period: CanonicalInterval
    retrieved_at_utc: str
    series_manifest: Mapping[str, Mapping[str, object]]
    series: tuple[RestorationMarketSeries, ...]
    request_evidence: tuple[SourceRequestEvidence, ...]
    raw_retention: Mapping[str, object]
    redistribution_policy: Mapping[str, object]
    predecessor_artifact_fingerprint: str | None
    content_fingerprint: str
    artifact_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "source": self.source.value,
            "source_version": self.source_version,
            "profile_id": self.profile_id,
            "resource": self.resource,
            "request_identity": self.request_identity,
            "requested_period": self.requested_period.to_dict(),
            "covered_period": self.covered_period.to_dict(),
            "retrieved_at_utc": self.retrieved_at_utc,
            "series_manifest": _thaw(self.series_manifest),
            "series": [item.to_dict() for item in self.series],
            "request_evidence": [item.to_dict() for item in self.request_evidence],
            "raw_retention": _thaw(self.raw_retention),
            "redistribution_policy": _thaw(self.redistribution_policy),
            "predecessor_artifact_fingerprint": (
                self.predecessor_artifact_fingerprint
            ),
            "content_fingerprint": self.content_fingerprint,
            "artifact_fingerprint": self.artifact_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RestorationMarketArtifact:
        """Load and verify all persisted semantic and identity fields."""

        recorded = recorded_fingerprints(
            payload, ("content_fingerprint", "artifact_fingerprint"), error=RestorationArtifactValidationError
        )
        recorded_series = {
            str(item.get("series_id")): _sha256(
                item.get("series_fingerprint"),
                field_name=f"series.{item.get('series_id')}.series_fingerprint",
            )
            for item in _sequence(payload.get("series"), field_name="series")
            if isinstance(item, Mapping)
        }
        artifact = _build_restoration_market_artifact(payload)
        for series in artifact.series:
            if recorded_series.get(series.series_id) != series.series_fingerprint:
                raise RestorationArtifactIntegrityError(
                    f"series_fingerprint mismatch for {series.series_id}"
                )
        verify_fingerprints(artifact, recorded, integrity_error=RestorationArtifactIntegrityError)
        return artifact


def _observation(
    payload: object, *, series_id: str, index: int, source_field: str
) -> RestorationMarketObservation:
    prefix = f"series.{series_id}.observations[{index}]"
    data = _mapping(payload, field_name=prefix)
    _required(
        data,
        (
            "interval",
            "value_state",
            "value",
            "source_row",
            "source_field",
            "document_ref",
            "conversion_ref",
        ),
        field_name=prefix,
    )
    state = _enum_value(
        ObservationValueState,
        data["value_state"],
        field_name=f"{prefix}.value_state",
    )
    if state is ObservationValueState.VALUE:
        value = _finite_number(data["value"], field_name=f"{prefix}.value")
    else:
        if data["value"] is not None:
            raise RestorationArtifactValidationError(
                f"{prefix}.value must be null for {state.value}"
            )
        value = None
    observed_source_field = _non_empty_string(
        data["source_field"], field_name=f"{prefix}.source_field"
    )
    if observed_source_field != source_field:
        raise RestorationArtifactValidationError(
            f"{prefix}.source_field must match the series source_field"
        )
    return RestorationMarketObservation(
        interval=_interval(data["interval"], field_name=f"{prefix}.interval"),
        value_state=state,
        value=value,
        source_row=_non_negative_int(
            data["source_row"], field_name=f"{prefix}.source_row"
        ),
        source_field=observed_source_field,
        document_ref=_non_empty_string(
            data["document_ref"], field_name=f"{prefix}.document_ref"
        ),
        conversion_ref=_optional_string(
            data["conversion_ref"], field_name=f"{prefix}.conversion_ref"
        ),
    )


def _series_payload_without_fingerprint(
    series: RestorationMarketSeries,
) -> dict[str, object]:
    payload = series.to_dict()
    payload.pop("series_fingerprint")
    return payload


def _market_series(
    payload: object,
    *,
    index: int,
    artifact_source: RestorationDataSource,
    artifact_source_version: str,
    artifact_resource: str,
    artifact_requested_period: CanonicalInterval,
    artifact_covered_period: CanonicalInterval,
) -> RestorationMarketSeries:
    prefix = f"series[{index}]"
    data = _mapping(payload, field_name=prefix)
    _required(
        data,
        (
            "series_id",
            "semantic_version",
            "source",
            "source_version",
            "resource",
            "source_field",
            "product",
            "process",
            "direction",
            "area",
            "requested_period",
            "covered_period",
            "source_resolution",
            "canonical_resolution",
            "source_unit",
            "canonical_unit",
            "currency",
            "availability",
            "transformations",
            "observations",
        ),
        field_name=prefix,
    )
    series_id = _non_empty_string(data["series_id"], field_name=f"{prefix}.series_id")
    source = _enum_value(
        RestorationDataSource, data["source"], field_name=f"{prefix}.source"
    )
    if source is not artifact_source:
        raise RestorationArtifactValidationError(
            f"{prefix}.source violates the artifact one source contract"
        )
    source_version = _non_empty_string(
        data["source_version"], field_name=f"{prefix}.source_version"
    )
    resource = _non_empty_string(data["resource"], field_name=f"{prefix}.resource")
    if source_version != artifact_source_version or resource != artifact_resource:
        raise RestorationArtifactValidationError(
            f"{prefix} provenance must match the artifact source version and resource"
        )
    requested_period = _interval(
        data["requested_period"], field_name=f"{prefix}.requested_period"
    )
    covered_period = _interval(
        data["covered_period"], field_name=f"{prefix}.covered_period"
    )
    if requested_period != artifact_requested_period:
        raise RestorationArtifactValidationError(
            f"{prefix}.requested_period must match the acquisition request"
        )
    if (
        covered_period.start_utc < artifact_covered_period.start_utc
        or covered_period.end_utc > artifact_covered_period.end_utc
    ):
        raise RestorationArtifactValidationError(
            f"{prefix}.covered_period lies outside artifact covered_period"
        )
    source_resolution = _non_empty_string(
        data["source_resolution"], field_name=f"{prefix}.source_resolution"
    )
    canonical_resolution = _non_empty_string(
        data["canonical_resolution"], field_name=f"{prefix}.canonical_resolution"
    )
    try:
        parse_iso8601_duration(source_resolution)
        parse_iso8601_duration(canonical_resolution)
    except MarketTimeValidationError as exc:
        raise RestorationArtifactValidationError(f"{prefix}: {exc}") from exc
    source_field = _non_empty_string(
        data["source_field"], field_name=f"{prefix}.source_field"
    )
    observations = tuple(
        _observation(
            item,
            series_id=series_id,
            index=observation_index,
            source_field=source_field,
        )
        for observation_index, item in enumerate(
            _sequence(data["observations"], field_name=f"{prefix}.observations")
        )
    )
    for previous, current in zip(observations, observations[1:]):
        if current.interval.start_utc < previous.interval.end_utc:
            raise RestorationArtifactValidationError(
                f"{series_id} observations overlap or are not chronological"
            )
    for observation in observations:
        if (
            observation.interval.start_utc < covered_period.start_utc
            or observation.interval.end_utc > covered_period.end_utc
        ):
            raise RestorationArtifactValidationError(
                f"{series_id} observation lies outside covered_period"
            )
    availability = _enum_value(
        SeriesAvailability,
        data["availability"],
        field_name=f"{prefix}.availability",
    )
    if availability is SeriesAvailability.PRESENT:
        if not observations or any(
            item.value_state is not ObservationValueState.VALUE for item in observations
        ):
            raise RestorationArtifactValidationError(
                f"{series_id} PRESENT availability requires numeric observations"
            )
    elif availability is SeriesAvailability.PRESENT_WITH_NULLS:
        if not observations or not any(
            item.value_state is not ObservationValueState.VALUE for item in observations
        ):
            raise RestorationArtifactValidationError(
                f"{series_id} PRESENT_WITH_NULLS requires a source-null or field-absent observation"
            )
    elif observations:
        raise RestorationArtifactValidationError(
            f"{series_id} {availability.value} availability cannot contain observations"
        )
    provisional = RestorationMarketSeries(
        series_id=series_id,
        semantic_version=_non_empty_string(
            data["semantic_version"], field_name=f"{prefix}.semantic_version"
        ),
        source=source,
        source_version=source_version,
        resource=resource,
        source_field=source_field,
        product=_optional_string(data["product"], field_name=f"{prefix}.product"),
        process=_optional_string(data["process"], field_name=f"{prefix}.process"),
        direction=_optional_string(
            data["direction"], field_name=f"{prefix}.direction"
        ),
        area=_non_empty_string(data["area"], field_name=f"{prefix}.area"),
        requested_period=requested_period,
        covered_period=covered_period,
        source_resolution=source_resolution,
        canonical_resolution=canonical_resolution,
        source_unit=_non_empty_string(
            data["source_unit"], field_name=f"{prefix}.source_unit"
        ),
        canonical_unit=_non_empty_string(
            data["canonical_unit"], field_name=f"{prefix}.canonical_unit"
        ),
        currency=_optional_string(data["currency"], field_name=f"{prefix}.currency"),
        availability=availability,
        transformations=tuple(
            _freeze(item)
            for item in _sequence(
                data["transformations"], field_name=f"{prefix}.transformations"
            )
        ),
        observations=observations,
        series_fingerprint=PLACEHOLDER_FINGERPRINT,
    )
    return seal_fingerprints(
        provisional, (("series_fingerprint", _series_payload_without_fingerprint),), error=RestorationArtifactValidationError
    )


def _request_evidence(payload: object, *, index: int) -> SourceRequestEvidence:
    prefix = f"request_evidence[{index}]"
    data = _mapping(payload, field_name=prefix)
    _required(
        data,
        (
            "request_id",
            "resource",
            "start_utc",
            "end_utc",
            "attempt_count",
            "http_status_class",
            "response_media_type",
            "response_bytes",
            "raw_sha256",
            "source_revision",
        ),
        field_name=prefix,
    )
    start = _utc_timestamp(data["start_utc"], field_name=f"{prefix}.start_utc")
    end = _utc_timestamp(data["end_utc"], field_name=f"{prefix}.end_utc")
    if datetime.fromisoformat(start.replace("Z", "+00:00")) >= datetime.fromisoformat(
        end.replace("Z", "+00:00")
    ):
        raise RestorationArtifactValidationError(
            f"{prefix} start_utc must be before end_utc"
        )
    return SourceRequestEvidence(
        request_id=_non_empty_string(
            data["request_id"], field_name=f"{prefix}.request_id"
        ),
        resource=_non_empty_string(data["resource"], field_name=f"{prefix}.resource"),
        start_utc=start,
        end_utc=end,
        attempt_count=_positive_int(
            data["attempt_count"], field_name=f"{prefix}.attempt_count"
        ),
        http_status_class=_non_empty_string(
            data["http_status_class"], field_name=f"{prefix}.http_status_class"
        ),
        response_media_type=_non_empty_string(
            data["response_media_type"], field_name=f"{prefix}.response_media_type"
        ),
        response_bytes=_non_negative_int(
            data["response_bytes"], field_name=f"{prefix}.response_bytes"
        ),
        raw_sha256=_sha256(data["raw_sha256"], field_name=f"{prefix}.raw_sha256"),
        source_revision=_optional_string(
            data["source_revision"], field_name=f"{prefix}.source_revision"
        ),
    )


def _safe_sidecar_locator(value: object, *, field_name: str) -> str:
    locator = _non_empty_string(value, field_name=field_name)
    return safe_sidecar_locator(locator, field_name=field_name, error=RestorationArtifactValidationError)


def _validate_raw_retention(
    payload: object, evidence: tuple[SourceRequestEvidence, ...]
) -> Mapping[str, object]:
    data = _mapping(payload, field_name="raw_retention")
    _required(data, ("policy", "responses"), field_name="raw_retention")
    policy = _enum_value(
        RawRetentionPolicy, data["policy"], field_name="raw_retention.policy"
    )
    responses = _mapping(data["responses"], field_name="raw_retention.responses")
    evidence_by_id = {item.request_id: item for item in evidence}
    if set(responses) != set(evidence_by_id):
        raise RestorationArtifactValidationError(
            "raw_retention responses must match every request evidence ID"
        )
    normalized: dict[str, object] = {}
    for request_id in sorted(responses):
        prefix = f"raw_retention.responses.{request_id}"
        item = _mapping(responses[request_id], field_name=prefix)
        _required(
            item,
            ("status", "sidecar_locator", "sidecar_sha256"),
            field_name=prefix,
        )
        status = _non_empty_string(item["status"], field_name=f"{prefix}.status")
        locator = item["sidecar_locator"]
        sidecar_sha = item["sidecar_sha256"]
        if policy is RawRetentionPolicy.DIGEST_ONLY:
            if status != "digest_only" or locator is not None or sidecar_sha is not None:
                raise RestorationArtifactValidationError(
                    f"{prefix} must be digest_only without a sidecar"
                )
            normalized[request_id] = {
                "status": status,
                "sidecar_locator": None,
                "sidecar_sha256": None,
            }
        else:
            if status == "digest_only":
                if locator is not None or sidecar_sha is not None:
                    raise RestorationArtifactValidationError(
                        f"{prefix} digest_only status cannot claim a sidecar"
                    )
                normalized[request_id] = {
                    "status": status,
                    "sidecar_locator": None,
                    "sidecar_sha256": None,
                }
                continue
            if status != "sidecar_retained":
                raise RestorationArtifactValidationError(
                    f"{prefix}.status must be digest_only or sidecar_retained"
                )
            safe_locator = _safe_sidecar_locator(
                locator, field_name=f"{prefix}.sidecar_locator"
            )
            digest = _sha256(sidecar_sha, field_name=f"{prefix}.sidecar_sha256")
            if digest != evidence_by_id[request_id].raw_sha256:
                raise RestorationArtifactValidationError(
                    f"{prefix}.sidecar_sha256 must match raw response evidence"
                )
            normalized[request_id] = {
                "status": status,
                "sidecar_locator": safe_locator,
                "sidecar_sha256": digest,
            }
    return _freeze({"policy": policy.value, "responses": normalized})


def _validate_policy(payload: object) -> Mapping[str, object]:
    policy = _mapping(payload, field_name="redistribution_policy")
    _required(
        policy,
        ("owner", "attribution", *_RESTRICTED_POLICY_FIELDS),
        field_name="redistribution_policy",
    )
    for name in ("owner", "attribution", *_RESTRICTED_POLICY_FIELDS):
        _non_empty_string(policy[name], field_name=f"redistribution_policy.{name}")
    return _freeze(policy)


def _validate_required_coverage(
    series: RestorationMarketSeries,
    *,
    requested_period: CanonicalInterval,
) -> None:
    if series.availability is not SeriesAvailability.PRESENT:
        raise RestorationArtifactValidationError(
            f"required series {series.series_id} must have PRESENT availability"
        )
    cursor = requested_period.start_utc
    for observation in series.observations:
        if observation.interval.start_utc != cursor:
            raise RestorationArtifactValidationError(
                f"required series {series.series_id} has a coverage gap"
            )
        cursor = observation.interval.end_utc
    if cursor != requested_period.end_utc:
        raise RestorationArtifactValidationError(
            f"required series {series.series_id} has incomplete coverage"
        )


def _content_payload(artifact: RestorationMarketArtifact) -> dict[str, object]:
    return {
        "schema_version": artifact.schema_version,
        "source": artifact.source.value,
        "source_version": artifact.source_version,
        "profile_id": artifact.profile_id,
        "resource": artifact.resource,
        "request_identity": artifact.request_identity,
        "requested_period": artifact.requested_period.to_dict(),
        "covered_period": artifact.covered_period.to_dict(),
        "series_manifest": _thaw(artifact.series_manifest),
        "series": [item.to_dict() for item in artifact.series],
    }


def _build_restoration_market_artifact(
    payload: Mapping[str, Any],
) -> RestorationMarketArtifact:
    data = _mapping(payload, field_name="restoration market artifact")
    _required(
        data,
        (
            "schema_version",
            "artifact_id",
            "source",
            "source_version",
            "profile_id",
            "resource",
            "request_identity",
            "requested_period",
            "covered_period",
            "retrieved_at_utc",
            "series_manifest",
            "series",
            "request_evidence",
            "raw_retention",
            "redistribution_policy",
            "predecessor_artifact_fingerprint",
        ),
        field_name="restoration market artifact",
    )
    schema_version = _non_empty_string(
        data["schema_version"], field_name="schema_version"
    )
    if schema_version not in SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS:
        raise UnsupportedRestorationArtifactVersionError(
            f"unsupported restoration artifact schema_version {schema_version!r}"
        )
    source = _enum_value(RestorationDataSource, data["source"], field_name="source")
    source_version = _non_empty_string(
        data["source_version"], field_name="source_version"
    )
    resource = _non_empty_string(data["resource"], field_name="resource")
    requested_period = _interval(data["requested_period"], field_name="requested_period")
    covered_period = _interval(data["covered_period"], field_name="covered_period")
    if (
        covered_period.start_utc > requested_period.start_utc
        or covered_period.end_utc < requested_period.end_utc
    ):
        raise RestorationArtifactValidationError(
            "covered_period must completely cover requested_period"
        )
    series = tuple(
        _market_series(
            item,
            index=index,
            artifact_source=source,
            artifact_source_version=source_version,
            artifact_resource=resource,
            artifact_requested_period=requested_period,
            artifact_covered_period=covered_period,
        )
        for index, item in enumerate(
            _sequence(data["series"], field_name="series")
        )
    )
    if not series:
        raise RestorationArtifactValidationError("series must be non-empty")
    by_id = {item.series_id: item for item in series}
    if len(by_id) != len(series):
        raise RestorationArtifactValidationError("series IDs must be unique")
    manifest_input = _mapping(data["series_manifest"], field_name="series_manifest")
    if set(manifest_input) != set(by_id):
        raise RestorationArtifactValidationError(
            "series_manifest must identify every and only artifact series"
        )
    manifest: dict[str, object] = {}
    for series_id in sorted(by_id):
        entry = _mapping(
            manifest_input[series_id], field_name=f"series_manifest.{series_id}"
        )
        _required(
            entry,
            ("requested", "required", "availability"),
            field_name=f"series_manifest.{series_id}",
        )
        requested = _boolean(
            entry["requested"], field_name=f"series_manifest.{series_id}.requested"
        )
        required = _boolean(
            entry["required"], field_name=f"series_manifest.{series_id}.required"
        )
        availability = _enum_value(
            SeriesAvailability,
            entry["availability"],
            field_name=f"series_manifest.{series_id}.availability",
        )
        item = by_id[series_id]
        if availability is not item.availability:
            raise RestorationArtifactValidationError(
                f"series_manifest availability mismatch for {series_id}"
            )
        if required and not requested:
            raise RestorationArtifactValidationError(
                f"required series {series_id} must be requested"
            )
        if availability is SeriesAvailability.NOT_REQUESTED and requested:
            raise RestorationArtifactValidationError(
                f"NOT_REQUESTED series {series_id} cannot be marked requested"
            )
        if availability is not SeriesAvailability.NOT_REQUESTED and not requested:
            raise RestorationArtifactValidationError(
                f"unrequested series {series_id} must use NOT_REQUESTED availability"
            )
        if required:
            _validate_required_coverage(item, requested_period=requested_period)
        recorded_series_fingerprint = entry.get("series_fingerprint")
        if (
            recorded_series_fingerprint is not None
            and _sha256(
                recorded_series_fingerprint,
                field_name=f"series_manifest.{series_id}.series_fingerprint",
            )
            != item.series_fingerprint
        ):
            raise RestorationArtifactIntegrityError(
                f"series_manifest fingerprint mismatch for {series_id}"
            )
        manifest[series_id] = {
            "requested": requested,
            "required": required,
            "availability": availability.value,
            "series_fingerprint": item.series_fingerprint,
        }
    evidence = tuple(
        _request_evidence(item, index=index)
        for index, item in enumerate(
            _sequence(data["request_evidence"], field_name="request_evidence")
        )
    )
    if not evidence or len({item.request_id for item in evidence}) != len(evidence):
        raise RestorationArtifactValidationError(
            "request_evidence must be non-empty with unique request IDs"
        )
    if any(item.resource != resource for item in evidence):
        raise RestorationArtifactValidationError(
            "request evidence resource must match the artifact resource"
        )
    evidence_ids = {item.request_id for item in evidence}
    if any(
        observation.document_ref not in evidence_ids
        for item in series
        for observation in item.observations
    ):
        raise RestorationArtifactValidationError(
            "every observation document_ref must resolve to request evidence"
        )
    predecessor_value = data["predecessor_artifact_fingerprint"]
    predecessor = (
        None
        if predecessor_value is None
        else _sha256(
            predecessor_value, field_name="predecessor_artifact_fingerprint"
        )
    )
    provisional = RestorationMarketArtifact(
        schema_version=schema_version,
        artifact_id=_non_empty_string(data["artifact_id"], field_name="artifact_id"),
        source=source,
        source_version=source_version,
        profile_id=_non_empty_string(data["profile_id"], field_name="profile_id"),
        resource=resource,
        request_identity=_sha256(
            data["request_identity"], field_name="request_identity"
        ),
        requested_period=requested_period,
        covered_period=covered_period,
        retrieved_at_utc=_utc_timestamp(
            data["retrieved_at_utc"], field_name="retrieved_at_utc"
        ),
        series_manifest=_freeze(manifest),
        series=series,
        request_evidence=evidence,
        raw_retention=_validate_raw_retention(data["raw_retention"], evidence),
        redistribution_policy=_validate_policy(data["redistribution_policy"]),
        predecessor_artifact_fingerprint=predecessor,
        content_fingerprint=PLACEHOLDER_FINGERPRINT,
        artifact_fingerprint=PLACEHOLDER_FINGERPRINT,
    )
    return seal_fingerprints(
        provisional,
        (
            ("content_fingerprint", _content_payload),
            ("artifact_fingerprint", partial(payload_without, field="artifact_fingerprint")),
        ),
        error=RestorationArtifactValidationError,
    )


def build_restoration_market_artifact(
    payload: Mapping[str, Any],
) -> RestorationMarketArtifact:
    """Validate producer-normalized values and compute immutable identities."""

    return _build_restoration_market_artifact(payload)


def restoration_market_artifact_filename(
    artifact: RestorationMarketArtifact,
) -> str:
    """Return a credential-independent immutable manifest filename."""

    if not isinstance(artifact, RestorationMarketArtifact):
        raise TypeError("artifact must be a RestorationMarketArtifact")
    return immutable_filename(
        artifact.artifact_id,
        artifact.artifact_fingerprint,
        error=RestorationArtifactValidationError,
        banned_labels=("token", "credential", "secret", "client-id"),
    )


def _verify_sidecars(
    artifact: RestorationMarketArtifact, *, artifact_root: Path | None
) -> None:
    responses = artifact.raw_retention["responses"]
    assert isinstance(responses, Mapping)
    retained = [
        (request_id, item)
        for request_id, item in responses.items()
        if isinstance(item, Mapping) and item["status"] == "sidecar_retained"
    ]
    if not retained:
        return
    if artifact_root is None:
        raise RestorationArtifactIntegrityError(
            "artifact_root is required to verify retained sidecars"
        )
    evidence = {item.request_id: item for item in artifact.request_evidence}
    for request_id, retention in retained:
        locator = retention["sidecar_locator"]
        digest = retention["sidecar_sha256"]
        assert isinstance(locator, str) and isinstance(digest, str)
        if digest != evidence[request_id].raw_sha256:
            raise RestorationArtifactIntegrityError(f"retained sidecar digest or byte count mismatch: {locator}")
        verify_sidecar_bytes(
            resolve_sidecar(
                artifact_root, locator, validation_error=RestorationArtifactValidationError, integrity_error=RestorationArtifactIntegrityError
            ),
            locator=locator,
            expected_sha256=digest,
            expected_byte_count=evidence[request_id].response_bytes,
            integrity_error=RestorationArtifactIntegrityError,
        )


def load_restoration_market_artifact(
    source: str | os.PathLike[str] | Mapping[str, Any],
    *,
    artifact_root: str | os.PathLike[str] | None = None,
) -> RestorationMarketArtifact:
    """Load and fully verify one artifact without source or credential access."""

    payload, source_name, inferred_root = read_artifact_source(
        source, label="restoration artifact", error=RestorationArtifactValidationError
    )
    try:
        artifact = RestorationMarketArtifact.from_dict(payload)
    except (
        UnsupportedRestorationArtifactVersionError,
        RestorationArtifactValidationError,
    ):
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise RestorationArtifactValidationError(
            f"invalid restoration artifact {source_name}: {exc}"
        ) from exc
    root = Path(artifact_root) if artifact_root is not None else inferred_root
    _verify_sidecars(artifact, artifact_root=root)
    return artifact


def _manifest_bytes(artifact: RestorationMarketArtifact) -> bytes:
    return json_document_bytes(artifact.to_dict(), error=RestorationArtifactValidationError)


def write_restoration_market_artifact(
    artifact: RestorationMarketArtifact,
    *,
    destination_dir: str | os.PathLike[str],
) -> Path:
    """Verify sidecars first, then publish a manifest through atomic replace."""

    if not isinstance(artifact, RestorationMarketArtifact):
        raise TypeError("artifact must be a RestorationMarketArtifact")
    verified = RestorationMarketArtifact.from_dict(artifact.to_dict())
    destination = Path(destination_dir)
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RestorationArtifactPublicationError(
            f"cannot create restoration artifact directory: {destination}"
        ) from exc
    _verify_sidecars(verified, artifact_root=destination)
    output_path = destination / restoration_market_artifact_filename(verified)
    desired_bytes = _manifest_bytes(verified)
    return publish_write_once(
        output_path,
        desired_bytes,
        load_existing=partial(load_restoration_market_artifact, artifact_root=destination),
        same_identity=lambda existing: existing.artifact_fingerprint == verified.artifact_fingerprint,
        label="restoration artifact",
        validation_error=RestorationArtifactValidationError,
        integrity_error=RestorationArtifactIntegrityError,
        publication_error=RestorationArtifactPublicationError,
    )


@dataclass(frozen=True, slots=True)
class RestorationStudyBundleRef:
    artifact_id: str
    artifact_fingerprint: str
    selected_series_ids: tuple[str, ...]
    selected_series_fingerprints: Mapping[str, str]
    purpose: str

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_fingerprint": self.artifact_fingerprint,
            "selected_series_ids": list(self.selected_series_ids),
            "selected_series_fingerprints": _thaw(
                self.selected_series_fingerprints
            ),
            "purpose": self.purpose,
        }


@dataclass(frozen=True, slots=True)
class RestorationStudyBundle:
    schema_version: str
    bundle_id: str
    study_period: CanonicalInterval
    references: tuple[RestorationStudyBundleRef, ...]
    redistribution_policy: Mapping[str, object]
    source_disagreements: tuple[Mapping[str, object], ...]
    bundle_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "study_period": self.study_period.to_dict(),
            "references": [item.to_dict() for item in self.references],
            "redistribution_policy": _thaw(self.redistribution_policy),
            "source_disagreements": _thaw(self.source_disagreements),
            "bundle_fingerprint": self.bundle_fingerprint,
        }


def _artifact_lookup(
    artifacts: Sequence[object],
) -> dict[str, object]:
    lookup: dict[str, object] = {}
    for artifact in artifacts:
        fingerprint = _sha256(
            getattr(artifact, "artifact_fingerprint", None),
            field_name="resolved artifact fingerprint",
        )
        if fingerprint in lookup:
            raise RestorationArtifactValidationError(
                f"duplicate resolved artifact fingerprint {fingerprint}"
            )
        lookup[fingerprint] = artifact
    return lookup


def _resolved_series(artifact: object) -> dict[str, tuple[str, object]]:
    values = getattr(artifact, "series", None)
    if isinstance(values, Mapping):
        items = list(values.items())
    elif isinstance(values, tuple):
        items = [(getattr(item, "series_id", None), item) for item in values]
    else:
        raise RestorationArtifactValidationError(
            "resolved artifact has no supported series collection"
        )
    resolved: dict[str, tuple[str, object]] = {}
    for series_id_value, series in items:
        series_id = _non_empty_string(
            series_id_value, field_name="resolved series ID"
        )
        fingerprint_value = getattr(series, "series_fingerprint", None)
        if fingerprint_value is None:
            to_dict = getattr(series, "to_dict", None)
            if not callable(to_dict):
                raise RestorationArtifactValidationError(
                    f"resolved series {series_id} has no deterministic representation"
                )
            fingerprint = hashlib.sha256(
                canonical_restoration_json_bytes(to_dict())
            ).hexdigest()
        else:
            fingerprint = _sha256(
                fingerprint_value,
                field_name=f"resolved series {series_id} fingerprint",
            )
        resolved[series_id] = (fingerprint, series)
    return resolved


def _validate_selected_series_period(
    artifact: object,
    series: object,
    *,
    series_id: str,
    study_period: CanonicalInterval,
) -> None:
    coverage = getattr(series, "covered_period", None)
    if coverage is None:
        coverage = getattr(artifact, "actual_covered_period", None)
    if not isinstance(coverage, CanonicalInterval):
        to_dict = getattr(coverage, "to_dict", None)
        if not callable(to_dict):
            raise RestorationArtifactValidationError(
                f"selected series {series_id} has no canonical coverage metadata"
            )
        coverage = _interval(
            to_dict(), field_name=f"selected series {series_id} coverage"
        )
    if (
        coverage.start_utc > study_period.start_utc
        or coverage.end_utc < study_period.end_utc
    ):
        raise RestorationArtifactValidationError(
            f"selected series {series_id} does not cover the bundle study_period"
        )


def _merge_policies(artifacts: Sequence[object]) -> Mapping[str, object]:
    policies = [
        _mapping(
            getattr(artifact, "redistribution_policy", None)
            if hasattr(artifact, "redistribution_policy")
            else getattr(artifact, "retention_and_license", None),
            field_name="referenced artifact redistribution policy",
        )
        for artifact in artifacts
    ]
    keys = sorted({key for policy in policies for key in policy})
    merged: dict[str, object] = {}
    for key in keys:
        values = [policy[key] for policy in policies if key in policy]
        unique = []
        for value in values:
            thawed = _thaw(value)
            if thawed not in unique:
                unique.append(thawed)
        if len(unique) == 1:
            merged[key] = unique[0]
        elif any(value == "prohibited" for value in unique):
            merged[key] = "prohibited"
        elif any(value == "permitted_private_restricted" for value in unique):
            merged[key] = "permitted_private_restricted"
        else:
            merged[key] = tuple(sorted(str(value) for value in unique))
    return _freeze(merged)


def _bundle_payload_without_fingerprint(
    bundle: RestorationStudyBundle,
) -> dict[str, object]:
    payload = bundle.to_dict()
    payload.pop("bundle_fingerprint")
    return payload


def build_restoration_study_bundle(
    payload: Mapping[str, Any],
    *,
    artifacts: Sequence[object],
) -> RestorationStudyBundle:
    """Resolve exact artifacts and create a reference-only study manifest."""

    data = _mapping(payload, field_name="restoration study bundle")
    _required(
        data,
        ("schema_version", "bundle_id", "study_period", "references"),
        field_name="restoration study bundle",
    )
    schema_version = _non_empty_string(
        data["schema_version"], field_name="schema_version"
    )
    if schema_version not in SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS:
        raise UnsupportedRestorationArtifactVersionError(
            f"unsupported restoration study bundle schema_version {schema_version!r}"
        )
    study_period = _interval(data["study_period"], field_name="study_period")
    available = _artifact_lookup(artifacts)
    references_input = _sequence(data["references"], field_name="references")
    if not references_input:
        raise RestorationArtifactValidationError("bundle references must be non-empty")
    references: list[RestorationStudyBundleRef] = []
    referenced_artifacts: list[object] = []
    seen_artifacts: set[str] = set()
    selections: dict[str, list[tuple[str, str]]] = {}
    for index, value in enumerate(references_input):
        prefix = f"references[{index}]"
        item = _mapping(value, field_name=prefix)
        _required(
            item,
            (
                "artifact_id",
                "artifact_fingerprint",
                "selected_series_ids",
                "purpose",
            ),
            field_name=prefix,
        )
        fingerprint = _sha256(
            item["artifact_fingerprint"],
            field_name=f"{prefix}.artifact_fingerprint",
        )
        if fingerprint in seen_artifacts:
            raise RestorationArtifactValidationError(
                "bundle references must identify unique artifacts"
            )
        seen_artifacts.add(fingerprint)
        resolved_artifact = available.get(fingerprint)
        if resolved_artifact is None:
            raise RestorationArtifactValidationError(
                f"cannot resolve referenced artifact fingerprint {fingerprint}"
            )
        artifact_id = _non_empty_string(
            item["artifact_id"], field_name=f"{prefix}.artifact_id"
        )
        if getattr(resolved_artifact, "artifact_id", None) != artifact_id:
            raise RestorationArtifactValidationError(
                f"{prefix} artifact_id does not match resolved fingerprint"
            )
        selected_ids = tuple(
            _non_empty_string(series_id, field_name=f"{prefix}.selected_series_ids")
            for series_id in _sequence(
                item["selected_series_ids"],
                field_name=f"{prefix}.selected_series_ids",
            )
        )
        if not selected_ids or len(set(selected_ids)) != len(selected_ids):
            raise RestorationArtifactValidationError(
                f"{prefix}.selected_series_ids must be non-empty and unique"
            )
        resolved_series = _resolved_series(resolved_artifact)
        missing = [series_id for series_id in selected_ids if series_id not in resolved_series]
        if missing:
            raise RestorationArtifactValidationError(
                f"{prefix} selected series are missing: {', '.join(missing)}"
            )
        selected_fingerprints = {
            series_id: resolved_series[series_id][0] for series_id in selected_ids
        }
        for series_id in selected_ids:
            _validate_selected_series_period(
                resolved_artifact,
                resolved_series[series_id][1],
                series_id=series_id,
                study_period=study_period,
            )
        recorded = item.get("selected_series_fingerprints")
        if recorded is not None and _mapping(
            recorded, field_name=f"{prefix}.selected_series_fingerprints"
        ) != selected_fingerprints:
            raise RestorationArtifactIntegrityError(
                f"{prefix} selected series fingerprint mismatch"
            )
        for series_id, series_fingerprint in selected_fingerprints.items():
            selections.setdefault(series_id, []).append(
                (fingerprint, series_fingerprint)
            )
        references.append(
            RestorationStudyBundleRef(
                artifact_id=artifact_id,
                artifact_fingerprint=fingerprint,
                selected_series_ids=selected_ids,
                selected_series_fingerprints=_freeze(selected_fingerprints),
                purpose=_non_empty_string(
                    item["purpose"], field_name=f"{prefix}.purpose"
                ),
            )
        )
        referenced_artifacts.append(resolved_artifact)
    disagreements = tuple(
        _freeze(
            {
                "series_id": series_id,
                "series_fingerprints": [entry[1] for entry in entries],
                "artifact_fingerprints": [entry[0] for entry in entries],
            }
        )
        for series_id, entries in selections.items()
        if len(entries) > 1 and len({entry[1] for entry in entries}) > 1
    )
    provisional = RestorationStudyBundle(
        schema_version=schema_version,
        bundle_id=_non_empty_string(data["bundle_id"], field_name="bundle_id"),
        study_period=study_period,
        references=tuple(references),
        redistribution_policy=_merge_policies(referenced_artifacts),
        source_disagreements=disagreements,
        bundle_fingerprint=PLACEHOLDER_FINGERPRINT,
    )
    return seal_fingerprints(
        provisional,
        (("bundle_fingerprint", _bundle_payload_without_fingerprint),),
        error=RestorationArtifactValidationError,
    )


def load_restoration_study_bundle(
    source: str | os.PathLike[str] | Mapping[str, Any],
    *,
    artifacts: Sequence[object],
) -> RestorationStudyBundle:
    """Load a bundle and re-resolve every exact artifact and series offline."""

    payload, _, _ = read_artifact_source(
        source, label="restoration study bundle", error=RestorationArtifactValidationError
    )
    recorded = _sha256(
        payload.get("bundle_fingerprint"), field_name="bundle_fingerprint"
    )
    bundle = build_restoration_study_bundle(payload, artifacts=artifacts)
    if bundle.bundle_fingerprint != recorded:
        raise RestorationArtifactIntegrityError("bundle_fingerprint mismatch")
    if "redistribution_policy" in payload and _thaw(bundle.redistribution_policy) != _thaw(
        payload["redistribution_policy"]
    ):
        raise RestorationArtifactIntegrityError(
            "bundle redistribution_policy mismatch"
        )
    if "source_disagreements" in payload and _thaw(bundle.source_disagreements) != _thaw(
        payload["source_disagreements"]
    ):
        raise RestorationArtifactIntegrityError("bundle source_disagreements mismatch")
    return bundle


__all__ = [
    "RESTORATION_MARKET_SCHEMA_VERSION",
    "RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION",
    "SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS",
    "SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS",
    "ObservationValueState",
    "SeriesAvailability",
    "RestorationDataSource",
    "RawRetentionPolicy",
    "RestorationArtifactValidationError",
    "UnsupportedRestorationArtifactVersionError",
    "RestorationArtifactIntegrityError",
    "RestorationArtifactPublicationError",
    "RestorationMarketObservation",
    "RestorationMarketSeries",
    "SourceRequestEvidence",
    "RestorationMarketArtifact",
    "RestorationStudyBundleRef",
    "RestorationStudyBundle",
    "build_restoration_market_artifact",
    "canonical_restoration_json_bytes",
    "restoration_market_artifact_filename",
    "write_restoration_market_artifact",
    "load_restoration_market_artifact",
    "build_restoration_study_bundle",
    "load_restoration_study_bundle",
]
