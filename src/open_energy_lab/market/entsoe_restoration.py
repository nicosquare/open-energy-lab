"""Native quarter-hour ENTSO-E day-ahead acquisition for restoration studies.

This adapter is additive to Feature 010's closed hourly A44/A81 lifecycle.  It
fetches only A44, preserves the source PT15M observations without resampling,
and returns a source-separated restoration artifact held in memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from typing import Sequence

from .artifact import MarketObservation
from .entsoe import (
    DEFAULT_MAX_RESPONSE_BYTES,
    EntsoeCoverageError,
    EntsoeDiagnostic,
    EntsoeDuplicateObservationError,
    EntsoeMarketDataRequest,
    EntsoeRequestValidationError,
    EntsoeTransport,
    FranceQuarterHourDayAheadProfile,
    ParsedEntsoeDocument,
    build_entsoe_query_windows,
    extract_entsoe_xml_members,
    parse_entsoe_document,
    request_entsoe_window,
    select_current_entsoe_documents,
)
from .restoration_artifact import (
    RESTORATION_MARKET_SCHEMA_VERSION,
    RestorationMarketArtifact,
    build_restoration_market_artifact,
    canonical_restoration_json_bytes,
)
from .time import CanonicalInterval


ENTSOE_DAY_AHEAD_SOURCE_VERSION = (
    "ENTSO-E Transparency Platform Web API (unversioned endpoint), "
    "SDAC native 15-minute MTU"
)


@dataclass(frozen=True, slots=True)
class EntsoeQuarterHourDayAheadFetchResult:
    """One explicit in-memory A44 acquisition and its sanitized diagnostics."""

    artifact: RestorationMarketArtifact
    attempt_diagnostics: tuple[EntsoeDiagnostic, ...]


def _request_identity(request: EntsoeMarketDataRequest) -> str:
    payload = {
        "profile_id": request.profile.profile_id,
        "source_endpoint": request.source_endpoint,
        "requested_start_utc": request.requested_start_utc.isoformat(),
        "requested_end_utc": request.requested_end_utc.isoformat(),
        "normalization_version": request.normalization_version,
        "raw_retention_policy": request.raw_retention_policy,
    }
    return hashlib.sha256(canonical_restoration_json_bytes(payload)).hexdigest()


def _selected_observations(
    documents: Sequence[ParsedEntsoeDocument],
    *,
    requested_start_utc: datetime,
    requested_end_utc: datetime,
) -> tuple[tuple[MarketObservation, ParsedEntsoeDocument], ...]:
    by_interval: dict[
        tuple[datetime, datetime], tuple[MarketObservation, ParsedEntsoeDocument]
    ] = {}
    for document in documents:
        for observation in document.series.observations:
            interval = observation.interval
            if (
                interval.end_utc <= requested_start_utc
                or interval.start_utc >= requested_end_utc
            ):
                continue
            if (
                interval.start_utc < requested_start_utc
                or interval.end_utc > requested_end_utc
            ):
                raise EntsoeCoverageError(
                    "ENTSO-E A44 PT15M observations must align exactly with the "
                    "requested restoration period"
                )
            key = (interval.start_utc, interval.end_utc)
            existing = by_interval.get(key)
            if existing is not None:
                existing_observation, _ = existing
                if existing_observation.value != observation.value:
                    raise EntsoeDuplicateObservationError(
                        "ENTSO-E A44 selected documents contain conflicting values "
                        "for one PT15M interval"
                    )
                continue
            by_interval[key] = (observation, document)

    ordered = tuple(by_interval[key] for key in sorted(by_interval))
    cursor = requested_start_utc
    for observation, _ in ordered:
        if observation.interval.start_utc != cursor:
            raise EntsoeCoverageError(
                "ENTSO-E A44 PT15M observations do not continuously cover the "
                "requested restoration period"
            )
        if observation.interval.end_utc - observation.interval.start_utc != timedelta(
            minutes=15
        ):
            raise EntsoeCoverageError(
                "ENTSO-E A44 restoration observations must remain native PT15M"
            )
        cursor = observation.interval.end_utc
    if cursor != requested_end_utc:
        raise EntsoeCoverageError(
            "ENTSO-E A44 PT15M observations do not completely cover the requested "
            "restoration period"
        )
    return ordered


def _redistribution_policy() -> dict[str, str]:
    return {
        "owner": "ENTSO-E Transparency Platform / EPEX SPOT-derived A44 values",
        "attribution": "ENTSO-E Transparency Platform; normalized by Open Energy Lab",
        "repository_storage": "permitted_private_restricted",
        "repository_publication": "prohibited",
        "package_distribution": "prohibited",
        "release_distribution": "prohibited",
        "public_ci_artifact": "prohibited",
        "public_mirror_or_fork": "prohibited",
        "external_artifact_store": "prohibited",
        "visibility_change_action": "remove_or_reassess_before_change",
    }


def fetch_entsoe_quarter_hour_day_ahead(
    request: EntsoeMarketDataRequest,
    *,
    api_token: str,
    transport: EntsoeTransport | None = None,
) -> EntsoeQuarterHourDayAheadFetchResult:
    """Fetch native PT15M A44 prices into one source-separated in-memory artifact."""

    if not isinstance(request, EntsoeMarketDataRequest):
        raise TypeError("request must be an EntsoeMarketDataRequest")
    if not isinstance(request.profile, FranceQuarterHourDayAheadProfile):
        raise EntsoeRequestValidationError(
            "request must select FranceQuarterHourDayAheadProfile"
        )
    if request.raw_retention_policy != "digest_only":
        raise EntsoeRequestValidationError(
            "in-memory quarter-hour A44 acquisition requires digest_only raw retention"
        )

    windows = build_entsoe_query_windows(request)
    if len(windows) != 1 or windows[0].document_type != "A44":
        raise EntsoeRequestValidationError(
            "quarter-hour day-ahead acquisition must produce exactly one A44 window"
        )
    window = windows[0]
    result = request_entsoe_window(
        request=request,
        window=window,
        api_token=api_token,
        transport=transport,
    )
    retrieved_at = datetime.now(UTC)
    raw_sha256 = hashlib.sha256(result.body).hexdigest()
    response_id = f"response-a44-{raw_sha256}"
    parsed = tuple(
        parse_entsoe_document(
            member_body,
            request=request,
            window=window,
            response_id=response_id,
            attempt_count=result.attempt_count,
            archive_member=member_name,
        )
        for member_name, member_body in extract_entsoe_xml_members(
            result.body,
            media_type=result.media_type,
            max_uncompressed_bytes=DEFAULT_MAX_RESPONSE_BYTES,
        )
    )
    selection = select_current_entsoe_documents(parsed)
    selected = _selected_observations(
        selection.selected,
        requested_start_utc=request.requested_start_utc,
        requested_end_utc=request.requested_end_utc,
    )
    period = CanonicalInterval.from_utc(
        request.requested_start_utc,
        request.requested_end_utc,
    )
    identity = _request_identity(request)
    revisions = ",".join(
        sorted(
            {
                f"{document.source_document.document_mrid}:"
                f"r{document.source_document.revision_number}"
                for _, document in selected
            }
        )
    )
    source_series_mrids = sorted(
        {
            str(series_mrid)
            for _, document in selected
            for series_mrid in document.source_document.product_identity.get(
                "series_mrids", ()
            )
        }
    )
    observations = [
        {
            "interval": observation.interval.to_dict(),
            "value_state": "VALUE",
            "value": observation.value,
            "source_row": index,
            "source_field": "price.amount",
            "document_ref": response_id,
            "conversion_ref": None,
        }
        for index, (observation, _) in enumerate(selected)
    ]
    artifact = build_restoration_market_artifact(
        {
            "schema_version": RESTORATION_MARKET_SCHEMA_VERSION,
            "artifact_id": f"entsoe-a44-pt15m-{identity[:16]}",
            "source": "ENTSOE",
            "source_version": ENTSOE_DAY_AHEAD_SOURCE_VERSION,
            "profile_id": request.profile.profile_id,
            "resource": "A44",
            "request_identity": identity,
            "requested_period": period.to_dict(),
            "covered_period": period.to_dict(),
            "retrieved_at_utc": retrieved_at.isoformat().replace("+00:00", "Z"),
            "series_manifest": {
                "day_ahead_price": {
                    "requested": True,
                    "required": True,
                    "availability": "PRESENT",
                }
            },
            "series": [
                {
                    "series_id": "day_ahead_price",
                    "semantic_version": "fr-day-ahead-price-native-pt15m-v2",
                    "source": "ENTSOE",
                    "source_version": ENTSOE_DAY_AHEAD_SOURCE_VERSION,
                    "resource": "A44",
                    "source_field": "price.amount",
                    "product": "DAY_AHEAD",
                    "process": "A01",
                    "direction": None,
                    "area": request.profile.area_eic,
                    "requested_period": period.to_dict(),
                    "covered_period": period.to_dict(),
                    "source_resolution": "PT15M",
                    "canonical_resolution": "PT15M",
                    "source_unit": "EUR/MWh",
                    "canonical_unit": "EUR/MWh",
                    "currency": "EUR",
                    "availability": "PRESENT",
                    "transformations": [
                        {
                            "operation": "identity",
                            "detail": "native PT15M A44 values preserved without resampling",
                            "source_time_series_mrids": source_series_mrids,
                        }
                    ],
                    "observations": observations,
                }
            ],
            "request_evidence": [
                {
                    "request_id": response_id,
                    "resource": "A44",
                    "start_utc": window.start_utc.isoformat().replace("+00:00", "Z"),
                    "end_utc": window.end_utc.isoformat().replace("+00:00", "Z"),
                    "attempt_count": result.attempt_count,
                    "http_status_class": "2xx",
                    "response_media_type": result.media_type,
                    "response_bytes": len(result.body),
                    "raw_sha256": raw_sha256,
                    "source_revision": revisions or None,
                }
            ],
            "raw_retention": {
                "policy": "DIGEST_ONLY",
                "responses": {
                    response_id: {
                        "status": "digest_only",
                        "sidecar_locator": None,
                        "sidecar_sha256": None,
                    }
                },
            },
            "redistribution_policy": _redistribution_policy(),
            "predecessor_artifact_fingerprint": None,
        }
    )
    return EntsoeQuarterHourDayAheadFetchResult(
        artifact=artifact,
        attempt_diagnostics=result.diagnostics,
    )


__all__ = [
    "ENTSOE_DAY_AHEAD_SOURCE_VERSION",
    "EntsoeQuarterHourDayAheadFetchResult",
    "fetch_entsoe_quarter_hour_day_ahead",
]
