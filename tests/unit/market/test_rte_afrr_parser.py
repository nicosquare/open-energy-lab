"""Exact RTE v5.2 standard_afrr_data parser contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from open_energy_lab.market.restoration_artifact import ObservationValueState
from open_energy_lab.market.rte import (
    RTEParseError,
    RTERawMarketResponse,
    build_rte_query_windows,
    build_rte_restoration_artifact_from_responses,
    parse_rte_restoration_responses,
)
from tests.unit.market.test_rte_request import _request


FIXTURES = Path("tests/fixtures/restoration/synthetic_rte")


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _raw(body: bytes) -> RTERawMarketResponse:
    request = _request()
    window = build_rte_query_windows(request)[0]
    return RTERawMarketResponse(
        request_id=window.request_id,
        resource=window.resource,
        start_utc=window.start_utc,
        end_utc=window.end_utc,
        retrieved_at_utc="2026-08-23T12:00:00Z",
        media_type="application/json",
        body=body,
        raw_sha256=hashlib.sha256(body).hexdigest(),
        attempt_count=1,
        source_revision=None,
    )


def _parse(body: bytes | None = None):
    request = _request()
    return parse_rte_restoration_responses(
        request,
        (_raw(_fixture("afrr_success.json") if body is None else body),),
    )


def _series(parsed, series_id: str):
    return next(item for item in parsed.series if item.series_id == series_id)


def test_afrr_success_preserves_eight_independent_semantic_series_and_provenance() -> None:
    parsed = _parse()

    assert parsed.profile.resource == "standard_afrr_data"
    assert parsed.covered_period.start_utc == datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    assert parsed.covered_period.end_utc == datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
    assert len(parsed.series) == 8
    assert parsed.transformations == ("rte-v5.2-chronological-row-order",)

    requested = _series(parsed, "afrr_requested_need_upward")
    assert requested.source_field == "upward_afrr_requested_need"
    assert requested.product == "AFRR"
    assert requested.process == "automatic_restoration"
    assert requested.direction == "UPWARD"
    assert requested.source_unit == "MW"
    assert requested.canonical_unit == "MW"
    assert requested.currency is None
    assert [item.value for item in requested.observations] == [425.0, 315.0, 290.0, 345.0]
    assert [item.source_row for item in requested.observations] == [3, 2, 1, 0]
    assert all(item.value_state is ObservationValueState.VALUE for item in requested.observations)
    assert all(item.interval.market_timezone == "Europe/Paris" for item in requested.observations)

    price = _series(parsed, "afrr_weighted_average_price_upward")
    assert price.source_field == "upward_weighted_average_price_afrr_activated_for_fr"
    assert price.source_unit == "EUR/MWh"
    assert price.currency == "EUR"
    assert _series(parsed, "afrr_activated_for_fr_upward").source_field != (
        _series(parsed, "afrr_activated_in_fr_upward").source_field
    )


def test_afrr_numeric_zero_remains_a_present_value() -> None:
    parsed = _parse()
    downward = _series(parsed, "afrr_requested_need_downward")

    assert [item.value for item in downward.observations] == [0.0] * 4
    assert all(item.value_state is ObservationValueState.VALUE for item in downward.observations)


def test_afrr_responses_can_be_normalized_to_an_in_memory_artifact() -> None:
    request = _request()

    artifact = build_rte_restoration_artifact_from_responses(
        request,
        (_raw(_fixture("afrr_success.json")),),
    )

    assert artifact.resource == "standard_afrr_data"
    assert artifact.profile_id == request.profile.profile_id
    assert len(artifact.series) == 8
    assert len(artifact.artifact_fingerprint) == 64
    assert len(artifact.content_fingerprint) == 64
    assert artifact.raw_retention["policy"] == "DIGEST_ONLY"


def test_afrr_accepts_aware_source_offsets_and_normalizes_them_to_utc() -> None:
    payload = json.loads(_fixture("afrr_success.json"))
    paris = ZoneInfo("Europe/Paris")

    def localize(value: str) -> str:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            paris
        ).isoformat()

    root = payload["picasso"]
    root["start_date"] = localize(root["start_date"])
    root["end_date"] = localize(root["end_date"])
    for row in root["picasso_mesures"]:
        row["start_date"] = localize(row["start_date"])
        row["end_date"] = localize(row["end_date"])

    parsed = _parse(json.dumps(payload).encode())

    assert parsed.covered_period.start_utc == datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    assert parsed.covered_period.end_utc == datetime(2026, 8, 20, 1, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("afrr_malformed_root.json", "picasso|root"),
        ("afrr_empty.json", "empty|picasso_mesures|coverage"),
        ("afrr_gap.json", "gap|coverage"),
        ("afrr_overlap.json", "overlap|PT15M|duration"),
        ("afrr_duplicate_conflict.json", "duplicate|conflict"),
        ("afrr_wrong_resolution.json", "PT15M|resolution"),
        ("afrr_wrong_unit.json", "unit|MW|EUR/MWh"),
    ],
)
def test_afrr_rejects_malformed_semantic_or_temporal_source_data(
    fixture: str, message: str
) -> None:
    with pytest.raises(RTEParseError, match=message):
        _parse(_fixture(fixture))


def test_afrr_requires_all_ten_named_row_fields_and_finite_numbers() -> None:
    payload = json.loads(_fixture("afrr_success.json"))
    del payload["picasso"]["picasso_mesures"][0]["upward_afrr_activated_volume_in_fr"]
    with pytest.raises(RTEParseError, match="upward_afrr_activated_volume_in_fr|missing"):
        _parse(json.dumps(payload).encode())

    payload = json.loads(_fixture("afrr_success.json"))
    payload["picasso"]["picasso_mesures"][0]["upward_afrr_requested_need"] = "not-a-number"
    with pytest.raises(RTEParseError, match="upward_afrr_requested_need|finite|number"):
        _parse(json.dumps(payload).encode())


def test_afrr_rejects_raw_digest_or_window_identity_mismatch() -> None:
    request = _request()
    raw = _raw(_fixture("afrr_success.json"))
    tampered = RTERawMarketResponse(
        request_id=raw.request_id,
        resource=raw.resource,
        start_utc=raw.start_utc,
        end_utc=raw.end_utc,
        retrieved_at_utc=raw.retrieved_at_utc,
        media_type=raw.media_type,
        body=raw.body + b" ",
        raw_sha256=raw.raw_sha256,
        attempt_count=raw.attempt_count,
        source_revision=raw.source_revision,
    )
    with pytest.raises(RTEParseError, match="digest|SHA"):
        parse_rte_restoration_responses(request, (tampered,))
