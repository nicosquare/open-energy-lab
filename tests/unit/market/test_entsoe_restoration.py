"""Additive native-PT15M A44 contracts for restoration composition."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from open_energy_lab.market.entsoe import (
    EntsoeMarketDataRequest,
    EntsoeQueryWindow,
    EntsoeResolutionValidationError,
    EntsoeTransportResponse,
    FranceQuarterHourDayAheadProfile,
    parse_entsoe_document,
)
from open_energy_lab.market.entsoe_restoration import (
    fetch_entsoe_quarter_hour_day_ahead,
)
from open_energy_lab.market.restoration_artifact import RestorationDataSource


FIXTURE = Path("tests/fixtures/market/synthetic_entsoe/a44_success.xml")
START = datetime(2022, 8, 18, 22, tzinfo=UTC)
END = datetime(2022, 8, 18, 23, tzinfo=UTC)
TOKEN = "quarter-hour-token-must-not-escape"


def _quarter_hour_body() -> bytes:
    return (
        FIXTURE.read_bytes()
        .replace(b"2022-08-19T02:00Z", b"2022-08-18T23:00Z")
        .replace(b"<resolution>PT1H</resolution>", b"<resolution>PT15M</resolution>")
    )


def _request(*, quarter_hour: bool = True) -> EntsoeMarketDataRequest:
    values = {
        "requested_start_utc": START,
        "requested_end_utc": END,
        "source_endpoint": "https://example.test/entsoe/api",
        "raw_retention_policy": "digest_only",
        "normalization_version": (
            "entsoe-a44-native-pt15m-v2" if quarter_hour else "entsoe-fr-v1"
        ),
    }
    if quarter_hour:
        values["profile"] = FranceQuarterHourDayAheadProfile()
    return EntsoeMarketDataRequest(**values)


def _window() -> EntsoeQueryWindow:
    return EntsoeQueryWindow(
        window_id="fr-a44-2022-08-19",
        document_type="A44",
        process_type="A01",
        business_type=None,
        area_parameter="10YFR-RTE------C",
        start_utc=START,
        end_utc=END,
    )


class _Transport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls: list[dict[str, object]] = []

    def request(self, **kwargs: object) -> EntsoeTransportResponse:
        self.calls.append(kwargs)
        return EntsoeTransportResponse(
            status_code=200,
            body=self.body,
            headers={"Content-Type": "application/xml"},
        )


def test_quarter_hour_profile_preserves_four_native_a44_intervals() -> None:
    parsed = parse_entsoe_document(
        _quarter_hour_body(),
        request=_request(),
        window=_window(),
        response_id="response-quarter-hour",
    )

    assert parsed.series.source_resolution == "PT15M"
    assert parsed.series.canonical_resolution == "PT15M"
    assert [item.value for item in parsed.series.observations] == [
        475.0,
        -5.0,
        540.0,
        120.5,
    ]
    assert [item.interval.start_utc.minute for item in parsed.series.observations] == [
        0,
        15,
        30,
        45,
    ]


def test_quarter_hour_profile_records_multiple_series_ids_and_collapses_exact_rows() -> None:
    body = _quarter_hour_body()
    block_start = body.index(b"  <TimeSeries>")
    block_end = body.index(b"  </TimeSeries>") + len(b"  </TimeSeries>\n")
    second_series = body[block_start:block_end].replace(
        b"synthetic-a44-series",
        b"synthetic-a44-series-2",
    )
    body = body[:block_end] + second_series + body[block_end:]

    parsed = parse_entsoe_document(
        body,
        request=_request(),
        window=_window(),
        response_id="response-multiple-series",
    )

    assert len(parsed.series.observations) == 4
    assert parsed.series.diagnostics["exact_duplicates_collapsed"] == 4
    assert parsed.source_document.product_identity["series_mrids"] == (
        "synthetic-a44-series",
        "synthetic-a44-series-2",
    )


def test_feature_010_hourly_profile_still_rejects_pt15m() -> None:
    with pytest.raises(
        EntsoeResolutionValidationError,
        match="unexpected resolution PT15M; expected PT1H/PT60M",
    ):
        parse_entsoe_document(
            _quarter_hour_body(),
            request=_request(quarter_hour=False),
            window=_window(),
            response_id="response-hourly-profile",
        )


def test_live_a44_fetch_builds_source_separated_digest_only_artifact() -> None:
    transport = _Transport(_quarter_hour_body())

    result = fetch_entsoe_quarter_hour_day_ahead(
        _request(),
        api_token=TOKEN,
        transport=transport,
    )

    artifact = result.artifact
    assert artifact.source is RestorationDataSource.ENTSOE
    assert artifact.profile_id == "fr-day-ahead-quarter-hour-v2"
    assert artifact.resource == "A44"
    assert len(artifact.series) == 1
    series = artifact.series[0]
    assert series.series_id == "day_ahead_price"
    assert series.canonical_resolution == "PT15M"
    assert len(series.observations) == 4
    assert series.transformations[0]["source_time_series_mrids"] == (
        "synthetic-a44-series",
    )
    assert artifact.raw_retention["policy"] == "DIGEST_ONLY"
    assert TOKEN not in repr(result)
    assert TOKEN not in repr(artifact.to_dict())
    assert len(transport.calls) == 1
    assert transport.calls[0]["api_token"] == TOKEN
    assert transport.calls[0]["parameters"] == {
        "documentType": "A44",
        "processType": "A01",
        "periodStart": "202208182200",
        "periodEnd": "202208192200",
        "in_Domain": "10YFR-RTE------C",
        "out_Domain": "10YFR-RTE------C",
    }


def test_quarter_hour_profile_requires_aligned_requested_bounds() -> None:
    with pytest.raises(ValueError, match="PT15M boundary"):
        EntsoeMarketDataRequest(
            requested_start_utc=START.replace(minute=1),
            requested_end_utc=END,
            source_endpoint="https://example.test/entsoe/api",
            raw_retention_policy="digest_only",
            normalization_version="entsoe-a44-native-pt15m-v2",
            profile=FranceQuarterHourDayAheadProfile(),
        )
