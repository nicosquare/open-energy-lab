"""Contract tests for the canonical France market-data artifact."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import json
import re
from types import ModuleType
from typing import Any
from zoneinfo import ZoneInfo

import pytest


SCHEMA_VERSION = "oel.market-data.v1"
PROFILE_ID = "fr-day-ahead-symmetric-fcr-v1"
FRANCE_EIC = "10YFR-RTE------C"
PARIS = "Europe/Paris"
PERIOD_START = datetime(2022, 8, 18, 22, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(hours=8)


def _artifact_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.market.artifact")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.market.artifact is not implemented; T010/T011 must "
            "provide the canonical artifact contract",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    module = _artifact_module()
    try:
        return getattr(module, name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.market.artifact.{name} is not implemented",
            pytrace=False,
        )


def _z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _canonical_interval_payload(start: datetime, end: datetime) -> dict[str, object]:
    paris = ZoneInfo(PARIS)
    local_start = start.astimezone(paris)
    local_end = end.astimezone(paris)
    start_offset = local_start.utcoffset()
    end_offset = local_end.utcoffset()
    assert start_offset is not None
    assert end_offset is not None
    return {
        "start_utc": _z(start),
        "end_utc": _z(end),
        "local_start": local_start.isoformat(),
        "local_end": local_end.isoformat(),
        "start_utc_offset_seconds": int(start_offset.total_seconds()),
        "end_utc_offset_seconds": int(end_offset.total_seconds()),
        "start_fold": local_start.fold,
        "end_fold": local_end.fold,
        "market_timezone": PARIS,
        "interval_convention": "start-inclusive/end-exclusive",
    }


def _observation(
    start: datetime,
    end: datetime,
    value: float,
    *,
    document_ref: str,
    source_position: int,
    conversion_ref: str | None = None,
) -> dict[str, object]:
    return {
        "interval": _canonical_interval_payload(start, end),
        "value": value,
        "document_ref": document_ref,
        "source_position": source_position,
        "conversion_ref": conversion_ref,
    }


def _source_document(
    *,
    document_ref: str,
    response_id: str,
    document_type: str,
    process_type: str,
    business_type: str | None,
    flow_direction: str | None,
    product_identity: Mapping[str, object],
) -> dict[str, object]:
    return {
        "document_ref": document_ref,
        "response_id": response_id,
        "namespace_uri": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3",
        "root_document_type": "Publication_MarketDocument",
        "document_mrid": f"document-{document_type.lower()}-unit",
        "revision_number": 2,
        "created_at_utc": "2022-08-18T20:00:00Z",
        "document_type": document_type,
        "process_type": process_type,
        "business_type": business_type,
        "flow_direction": flow_direction,
        "area_eic": FRANCE_EIC,
        "market_agreement_type": "A01" if document_type == "A44" else "A04",
        "product_identity": dict(product_identity),
        "document_period": _canonical_interval_payload(PERIOD_START, PERIOD_END),
        "status": "selected",
    }


def _valid_artifact_input() -> dict[str, object]:
    energy_observations = [
        _observation(
            PERIOD_START + timedelta(hours=index),
            PERIOD_START + timedelta(hours=index + 1),
            -5.0 if index == 1 else 50.0 + index,
            document_ref="a44-selected",
            source_position=index + 1,
        )
        for index in range(8)
    ]
    volume_observations = [
        _observation(
            PERIOD_START + timedelta(hours=4 * index),
            PERIOD_START + timedelta(hours=4 * (index + 1)),
            300.0 + index,
            document_ref="a81-selected",
            source_position=index + 1,
        )
        for index in range(2)
    ]
    price_observations = [
        _observation(
            PERIOD_START + timedelta(hours=4 * index),
            PERIOD_START + timedelta(hours=4 * (index + 1)),
            20.0 + index,
            document_ref="a89-selected",
            source_position=index + 1,
            conversion_ref="a89-eur-per-mw-isp-to-eur-per-mw-hour",
        )
        for index in range(2)
    ]
    fcr_product = {
        "product": "symmetric-fcr",
        "tender": "daily",
        "block_duration": "PT4H",
    }

    query_windows = []
    raw_responses = []
    for document_type in ("A44", "A81", "A89"):
        window_id = f"fr-{document_type.lower()}-2022-08-19"
        response_bytes = f"synthetic-{document_type}-response".encode()
        query_windows.append(
            {
                "window_id": window_id,
                "document_type": document_type,
                "process_type": "A01" if document_type == "A44" else "A34",
                "business_type": None if document_type == "A44" else "A95",
                "area_parameter": FRANCE_EIC,
                "start_utc": _z(PERIOD_START),
                "end_utc": _z(PERIOD_END),
                "attempt_count": 1,
            }
        )
        raw_responses.append(
            {
                "response_id": f"response-{document_type.lower()}",
                "window_id": window_id,
                "retrieved_at_utc": "2026-08-21T08:00:00Z",
                "media_type": "application/xml",
                "byte_count": len(response_bytes),
                "sha256": hashlib.sha256(response_bytes).hexdigest(),
                "retention_status": "digest_only",
                "redistribution_basis": {
                    "source": "ENTSO-E Transparency Platform",
                    "terms_version": "unit-test-record",
                    "attribution": "Synthetic digest evidence only",
                    "changes": "normalized",
                },
                "sidecar_locator": None,
                "sidecar_sha256": None,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": "fr-market-unit-v1",
        "profile_id": PROFILE_ID,
        "normalization_version": "entsoe-fr-v1",
        "created_at_utc": "2026-08-21T08:05:00Z",
        "requested_period": _canonical_interval_payload(PERIOD_START, PERIOD_END),
        "actual_covered_period": _canonical_interval_payload(PERIOD_START, PERIOD_END),
        "area": {
            "eic": FRANCE_EIC,
            "name": "France",
            "market_timezone": PARIS,
        },
        "series": {
            "day_ahead_price": {
                "series_id": "day_ahead_price",
                "semantic_version": "fr-day-ahead-price-v1",
                "area_eic": FRANCE_EIC,
                "source_document_type": "A44",
                "source_resolution": "PT1H",
                "canonical_resolution": "PT1H",
                "source_unit": "EUR/MWh",
                "canonical_unit": "EUR/MWh",
                "currency": "EUR",
                "conversion": None,
                "observations": energy_observations,
                "diagnostics": {
                    "exact_duplicates_collapsed": 0,
                    "superseded_revisions": [],
                    "conversions": [],
                },
            },
            "fcr_contracted_volume": {
                "series_id": "fcr_contracted_volume",
                "semantic_version": "fr-symmetric-fcr-volume-v1",
                "area_eic": FRANCE_EIC,
                "source_document_type": "A81",
                "source_resolution": "PT4H",
                "canonical_resolution": "PT4H",
                "source_unit": "MW",
                "canonical_unit": "MW",
                "currency": None,
                "conversion": None,
                "observations": volume_observations,
                "diagnostics": {
                    "exact_duplicates_collapsed": 0,
                    "superseded_revisions": [],
                    "conversions": [],
                },
            },
            "fcr_capacity_price": {
                "series_id": "fcr_capacity_price",
                "semantic_version": "fr-symmetric-fcr-capacity-price-v1",
                "area_eic": FRANCE_EIC,
                "source_document_type": "A89",
                "source_resolution": "PT4H",
                "canonical_resolution": "PT4H",
                "source_unit": "EUR/MW/PT4H",
                "canonical_unit": "EUR/MW/h",
                "currency": "EUR",
                "conversion": {
                    "conversion_ref": "a89-eur-per-mw-isp-to-eur-per-mw-hour",
                    "formula": "source_value / 4",
                    "factor": 0.25,
                    "source_resolution": "PT4H",
                },
                "observations": price_observations,
                "diagnostics": {
                    "exact_duplicates_collapsed": 0,
                    "superseded_revisions": [],
                    "conversions": ["a89-eur-per-mw-isp-to-eur-per-mw-hour"],
                },
            },
        },
        "query_windows": query_windows,
        "raw_responses": raw_responses,
        "source_documents": [
            _source_document(
                document_ref="a44-selected",
                response_id="response-a44",
                document_type="A44",
                process_type="A01",
                business_type=None,
                flow_direction=None,
                product_identity={"market": "day-ahead"},
            ),
            _source_document(
                document_ref="a81-selected",
                response_id="response-a81",
                document_type="A81",
                process_type="A34",
                business_type="A95",
                flow_direction="A03",
                product_identity=fcr_product,
            ),
            _source_document(
                document_ref="a89-selected",
                response_id="response-a89",
                document_type="A89",
                process_type="A34",
                business_type="A95",
                flow_direction="A03",
                product_identity=fcr_product,
            ),
        ],
        "predecessor_artifact_fingerprint": None,
        "retention_and_license": {
            "normalized_fixture_redistribution": "permitted-for-tests",
            "raw_response_default": "digest_only",
            "attribution": ["ENTSO-E Transparency Platform"],
            "terms_version": "unit-test-record",
        },
    }


def _build_artifact(payload: Mapping[str, object] | None = None) -> object:
    build_market_data_artifact = _require("build_market_data_artifact")
    return build_market_data_artifact(
        deepcopy(dict(payload if payload is not None else _valid_artifact_input()))
    )


def test_v1_artifact_preserves_the_required_france_profile_and_series() -> None:
    supported_versions = _require("SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS")

    artifact = _build_artifact()

    assert supported_versions == (SCHEMA_VERSION,)
    assert artifact.schema_version == SCHEMA_VERSION
    assert artifact.profile_id == PROFILE_ID
    assert artifact.area["eic"] == FRANCE_EIC
    assert artifact.area["market_timezone"] == PARIS
    assert tuple(artifact.series) == (
        "day_ahead_price",
        "fcr_contracted_volume",
        "fcr_capacity_price",
    )
    assert artifact.series["day_ahead_price"].source_document_type == "A44"
    assert artifact.series["fcr_contracted_volume"].source_document_type == "A81"
    assert artifact.series["fcr_capacity_price"].source_document_type == "A89"
    assert artifact.series["day_ahead_price"].observations[1].value == -5.0


def test_market_artifact_and_series_entities_are_immutable() -> None:
    artifact = _build_artifact()

    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        artifact.artifact_id = "mutated"
    with pytest.raises(TypeError):
        artifact.series["extra"] = artifact.series["day_ahead_price"]
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        artifact.series["day_ahead_price"].canonical_unit = "USD/MWh"
    assert isinstance(artifact.series, Mapping)
    assert isinstance(artifact.series["day_ahead_price"].observations, tuple)


@pytest.mark.parametrize(
    ("series_id", "canonical_unit"),
    [
        ("day_ahead_price", "EUR/MWh"),
        ("fcr_contracted_volume", "MW"),
        ("fcr_capacity_price", "EUR/MW/h"),
    ],
)
def test_required_series_enforce_canonical_units_and_resolutions(
    series_id: str,
    canonical_unit: str,
) -> None:
    artifact = _build_artifact()
    series = artifact.series[series_id]

    assert series.canonical_unit == canonical_unit
    assert series.canonical_resolution == (
        "PT1H" if series_id == "day_ahead_price" else "PT4H"
    )

    payload = _valid_artifact_input()
    payload_series = payload["series"]
    assert isinstance(payload_series, dict)
    invalid_series = payload_series[series_id]
    assert isinstance(invalid_series, dict)
    invalid_series["canonical_unit"] = "invalid-unit"

    error_type = _require("MarketArtifactValidationError")
    with pytest.raises(error_type, match=f"{series_id}.*unit|unit.*{series_id}"):
        _build_artifact(payload)


def test_artifact_rejects_unknown_schema_or_missing_required_series() -> None:
    error_type = _require("MarketArtifactValidationError")

    unknown_schema = _valid_artifact_input()
    unknown_schema["schema_version"] = "oel.market-data.v999"
    with pytest.raises(error_type, match="schema|version"):
        _build_artifact(unknown_schema)

    missing_series = _valid_artifact_input()
    series = missing_series["series"]
    assert isinstance(series, dict)
    series.pop("fcr_capacity_price")
    with pytest.raises(error_type, match="fcr_capacity_price|required series"):
        _build_artifact(missing_series)


def test_series_must_cover_the_requested_period_without_gaps() -> None:
    payload = _valid_artifact_input()
    series = payload["series"]
    assert isinstance(series, dict)
    energy = series["day_ahead_price"]
    assert isinstance(energy, dict)
    observations = energy["observations"]
    assert isinstance(observations, list)
    observations.pop(3)

    error_type = _require("MarketArtifactValidationError")
    with pytest.raises(error_type, match="day_ahead_price.*gap|gap.*day_ahead_price|coverage"):
        _build_artifact(payload)


def test_non_negative_market_series_reject_negative_values() -> None:
    payload = _valid_artifact_input()
    series = payload["series"]
    assert isinstance(series, dict)
    volume = series["fcr_contracted_volume"]
    assert isinstance(volume, dict)
    observations = volume["observations"]
    assert isinstance(observations, list)
    first = observations[0]
    assert isinstance(first, dict)
    first["value"] = -0.01

    error_type = _require("MarketArtifactValidationError")
    with pytest.raises(error_type, match="fcr_contracted_volume|non-negative"):
        _build_artifact(payload)


def test_canonical_json_is_byte_deterministic_and_strict() -> None:
    canonical_json_bytes = _require("canonical_json_bytes")
    artifact = _build_artifact()
    payload = artifact.to_dict()
    reversed_payload = dict(reversed(tuple(payload.items())))

    first = canonical_json_bytes(payload)
    second = canonical_json_bytes(reversed_payload)

    assert first == second
    assert first == json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert first.endswith(b"}")
    assert not first.endswith(b"\n")


def test_content_and_artifact_fingerprints_have_separate_meanings() -> None:
    canonical_json_bytes = _require("canonical_json_bytes")
    baseline = _build_artifact()

    volatile_change = _valid_artifact_input()
    volatile_change["artifact_id"] = "fr-market-unit-refreshed"
    volatile_change["created_at_utc"] = "2026-08-22T09:00:00Z"
    volatile_change["predecessor_artifact_fingerprint"] = "a" * 64
    raw_responses = volatile_change["raw_responses"]
    assert isinstance(raw_responses, list)
    for evidence in raw_responses:
        assert isinstance(evidence, dict)
        evidence["retrieved_at_utc"] = "2026-08-22T08:55:00Z"
    refreshed = _build_artifact(volatile_change)

    semantic_change = _valid_artifact_input()
    series = semantic_change["series"]
    assert isinstance(series, dict)
    day_ahead = series["day_ahead_price"]
    assert isinstance(day_ahead, dict)
    observations = day_ahead["observations"]
    assert isinstance(observations, list)
    first_observation = observations[0]
    assert isinstance(first_observation, dict)
    first_observation["value"] = 51.25
    changed = _build_artifact(semantic_change)

    fingerprint_pattern = re.compile(r"^[0-9a-f]{64}$")
    assert fingerprint_pattern.fullmatch(baseline.content_fingerprint)
    assert fingerprint_pattern.fullmatch(baseline.artifact_fingerprint)
    assert refreshed.content_fingerprint == baseline.content_fingerprint
    assert refreshed.artifact_fingerprint != baseline.artifact_fingerprint
    assert changed.content_fingerprint != baseline.content_fingerprint
    assert changed.artifact_fingerprint != baseline.artifact_fingerprint

    full_manifest = baseline.to_dict()
    recorded_artifact_fingerprint = full_manifest.pop("artifact_fingerprint")
    assert recorded_artifact_fingerprint == hashlib.sha256(
        canonical_json_bytes(full_manifest)
    ).hexdigest()


def test_fcr_volume_and_price_require_exact_interval_alignment() -> None:
    payload = _valid_artifact_input()
    series = payload["series"]
    assert isinstance(series, dict)
    capacity_price = series["fcr_capacity_price"]
    assert isinstance(capacity_price, dict)
    observations = capacity_price["observations"]
    assert isinstance(observations, list)
    first = observations[0]
    assert isinstance(first, dict)
    first["interval"] = _canonical_interval_payload(
        PERIOD_START + timedelta(hours=1),
        PERIOD_START + timedelta(hours=5),
    )

    error_type = _require("MarketArtifactValidationError")
    with pytest.raises(
        error_type,
        match="A81|A89|FCR|fcr|align|coverage|gap|overlap",
    ):
        _build_artifact(payload)


def test_fcr_volume_and_price_require_matching_product_identity() -> None:
    payload = _valid_artifact_input()
    source_documents = payload["source_documents"]
    assert isinstance(source_documents, list)
    price_document = next(
        document
        for document in source_documents
        if isinstance(document, dict) and document["document_type"] == "A89"
    )
    price_document["product_identity"] = {
        "product": "symmetric-fcr",
        "tender": "weekly-incompatible",
        "block_duration": "PT4H",
    }

    error_type = _require("MarketArtifactValidationError")
    with pytest.raises(error_type, match="A81|A89|FCR|fcr|product|align"):
        _build_artifact(payload)
