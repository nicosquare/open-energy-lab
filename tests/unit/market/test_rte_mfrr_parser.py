"""Exact RTE v5.2 standard_mfrr_data parser contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from open_energy_lab.market.restoration_artifact import ObservationValueState
from open_energy_lab.market.rte import (
    RTE_MFRR_PROFILE,
    RTEParseError,
    RTERawMarketResponse,
    build_rte_query_windows,
    build_rte_restoration_request,
    parse_rte_restoration_responses,
)


FIXTURES = Path("tests/fixtures/restoration/synthetic_rte")
START = datetime(2026, 8, 15, 10, 15, tzinfo=UTC)
END = START + timedelta(minutes=15)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _request(*, series_ids=None, required_ids=None):
    selected = RTE_MFRR_PROFILE.series_ids if series_ids is None else tuple(series_ids)
    required = (
        RTE_MFRR_PROFILE.required_series_ids
        if required_ids is None
        else tuple(required_ids)
    )
    return build_rte_restoration_request(
        resource="standard_mfrr_data",
        requested_start_utc=START,
        requested_end_utc=END,
        requested_series_ids=selected,
        required_series_ids=required,
        normalization_version="rte-balancing-energy-v5.2-v1",
        raw_retention_policy="DIGEST_ONLY",
        mode="FETCH",
    )


def _raw(request, body: bytes) -> RTERawMarketResponse:
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


def _parse(body: bytes | None = None, *, request=None):
    selected_request = _request() if request is None else request
    return parse_rte_restoration_responses(
        selected_request,
        (_raw(selected_request, _fixture("mfrr_success.json") if body is None else body),),
    )


def _series(parsed, series_id: str):
    return next(item for item in parsed.series if item.series_id == series_id)


def test_mfrr_preserves_directional_sa_da_requested_satisfied_and_activated_meanings() -> None:
    parsed = _parse()

    assert parsed.profile.resource == "standard_mfrr_data"
    assert parsed.covered_period.start_utc == START
    assert parsed.covered_period.end_utc == END
    downward_sa = _series(parsed, "mfrr_sa_requested_volume_downward")
    assert downward_sa.source_field == "total_requested_volume_SA"
    assert downward_sa.product == "MFRR"
    assert downward_sa.process == "scheduled_activation"
    assert downward_sa.direction == "DOWNWARD"
    assert downward_sa.observations[0].value == 357.0
    assert _series(parsed, "mfrr_sa_satisfied_need_downward").observations[0].value == 340.0
    assert _series(parsed, "mfrr_sa_activated_volume_downward").observations[0].value == 300.0
    assert _series(parsed, "mfrr_da_requested_volume_downward").observations[0].value is None
    assert (
        _series(parsed, "mfrr_da_requested_volume_downward").observations[0].value_state
        is ObservationValueState.SOURCE_NULL
    )
    assert _series(parsed, "mfrr_sa_requested_volume_upward").observations[0].value == 0.0


def test_mfrr_nested_price_entries_remain_typed_directional_context() -> None:
    parsed = _parse()
    assert len(parsed.nested_price_entries) == 1
    entry = parsed.nested_price_entries[0]

    assert entry.direction == "DOWNWARD"
    assert entry.activation_type == "SA"
    assert entry.activation_type_state is ObservationValueState.VALUE
    assert entry.requested_price == 90.0
    assert entry.requested_price_state is ObservationValueState.VALUE
    assert entry.requested_volume == 357.0
    assert entry.requested_volume_state is ObservationValueState.VALUE
    assert entry.satisfied_need == 340.0
    assert entry.satisfied_need_state is ObservationValueState.VALUE
    assert entry.source_row == 0
    assert entry.interval.start_utc == START


def test_mfrr_preserves_null_nested_fields_without_inferring_or_imputing() -> None:
    payload = json.loads(_fixture("mfrr_success.json"))
    nested = payload["mari"]["mari_mesures"][0][
        "requested_activated_volumes_by_prices"
    ][0]
    nested["activation_type"] = None
    nested["requested_price"] = None
    nested["requested_volume"] = None
    nested["satisfied_need"] = None

    parsed = _parse(json.dumps(payload).encode())

    entry = parsed.nested_price_entries[0]
    assert entry.activation_type is None
    assert entry.activation_type_state is ObservationValueState.SOURCE_NULL
    assert entry.requested_price is None
    assert entry.requested_price_state is ObservationValueState.SOURCE_NULL
    assert entry.requested_volume is None
    assert entry.requested_volume_state is ObservationValueState.SOURCE_NULL
    assert entry.satisfied_need is None
    assert entry.satisfied_need_state is ObservationValueState.SOURCE_NULL


def test_mfrr_preserves_atp_requested_price_meaning_as_a_source_code() -> None:
    payload = json.loads(_fixture("mfrr_success.json"))
    payload["mari"]["mari_mesures"][0]["requested_activated_volumes_by_prices"][
        0
    ]["requested_price"] = "ATP"

    entry = _parse(json.dumps(payload).encode()).nested_price_entries[0]

    assert entry.requested_price == "ATP"
    assert entry.requested_price_state is ObservationValueState.VALUE


def test_mfrr_preserves_field_absent_source_null_and_numeric_zero() -> None:
    selected = (
        "mfrr_sa_requested_volume_downward",
        "mfrr_sa_activated_volume_downward",
        "mfrr_da_requested_volume_downward",
        "mfrr_da_satisfied_need_downward",
        "mfrr_settlement_price_current_downward",
        "mfrr_settlement_price_previous_downward",
    )
    request = _request(
        series_ids=selected,
        required_ids=("mfrr_sa_requested_volume_downward",),
    )
    parsed = _parse(_fixture("mfrr_missing_null_zero.json"), request=request)

    assert (
        _series(parsed, "mfrr_sa_requested_volume_downward").observations[0].value_state
        is ObservationValueState.VALUE
    )
    assert _series(parsed, "mfrr_sa_requested_volume_downward").observations[0].value == 0.0
    assert (
        _series(parsed, "mfrr_sa_activated_volume_downward").observations[0].value_state
        is ObservationValueState.SOURCE_NULL
    )
    assert (
        _series(parsed, "mfrr_settlement_price_previous_downward")
        .observations[0]
        .value_state
        is ObservationValueState.FIELD_ABSENT
    )


def test_sparse_null_da_fields_do_not_create_an_activation_event() -> None:
    parsed = _parse()
    assert not hasattr(parsed, "events")
    assert not hasattr(parsed, "activation_sequence")
    da = _series(parsed, "mfrr_da_requested_volume_downward")
    assert da.observations[0].value_state is ObservationValueState.SOURCE_NULL


def test_mfrr_accepts_aware_source_offsets_and_normalizes_them_to_utc() -> None:
    payload = json.loads(_fixture("mfrr_success.json"))
    paris = ZoneInfo("Europe/Paris")

    def localize(value: str) -> str:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            paris
        ).isoformat()

    root = payload["mari"]
    root["start_date"] = localize(root["start_date"])
    root["end_date"] = localize(root["end_date"])
    for row in root["mari_mesures"]:
        row["start_date"] = localize(row["start_date"])
        row["end_date"] = localize(row["end_date"])

    parsed = _parse(json.dumps(payload).encode())

    assert parsed.covered_period.start_utc == START
    assert parsed.covered_period.end_utc == END


def test_mfrr_accepts_source_direction_case_without_changing_identity() -> None:
    payload = json.loads(_fixture("mfrr_success.json"))
    for row in payload["mari"]["mari_mesures"]:
        row["direction"] = row["direction"].upper()

    parsed = _parse(json.dumps(payload).encode())

    directions = {
        item.direction
        for item in parsed.series
        if item.series_id.startswith("mfrr_sa_requested_volume_")
    }
    assert directions == {"UPWARD", "DOWNWARD"}


def test_mfrr_rejects_unknown_direction_and_malformed_nested_price_entries() -> None:
    with pytest.raises(RTEParseError, match="direction|upward|downward"):
        _parse(_fixture("mfrr_wrong_direction.json"))

    payload = json.loads(_fixture("mfrr_success.json"))
    del payload["mari"]["mari_mesures"][0]["requested_activated_volumes_by_prices"][0][
        "requested_volume"
    ]
    with pytest.raises(RTEParseError, match="requested_volume|nested|price"):
        _parse(json.dumps(payload).encode())

    payload = json.loads(_fixture("mfrr_success.json"))
    payload["mari"]["mari_mesures"][0]["requested_activated_volumes_by_prices"][
        0
    ]["activation_type"] = "UNKNOWN"
    with pytest.raises(RTEParseError, match="activation_type|SA|DA"):
        _parse(json.dumps(payload).encode())

    payload = json.loads(_fixture("mfrr_success.json"))
    payload["mari"]["mari_mesures"][0]["requested_activated_volumes_by_prices"][
        0
    ]["requested_price"] = "UNSUPPORTED"
    with pytest.raises(RTEParseError, match="requested_price|ATP|number"):
        _parse(json.dumps(payload).encode())


def test_mfrr_rejects_duplicate_directional_rows_instead_of_netting() -> None:
    payload = json.loads(_fixture("mfrr_success.json"))
    payload["mari"]["mari_mesures"].append(
        dict(payload["mari"]["mari_mesures"][0])
    )
    with pytest.raises(RTEParseError, match="duplicate|direction|overlap"):
        _parse(json.dumps(payload).encode())
