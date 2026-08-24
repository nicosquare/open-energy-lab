"""Offline contracts for the notebook's optional live pipeline consumer."""

from __future__ import annotations

from pathlib import Path
from datetime import UTC, datetime

import pytest

from examples.restoration_services.live_pipeline import (
    LiveRestorationPipelineError,
    run_live_restoration_pipeline,
)
from open_energy_lab.market.entsoe import (
    EntsoeMarketDataRequest,
    EntsoeTransportResponse,
    FranceQuarterHourDayAheadProfile,
)
from open_energy_lab.market.entsoe_restoration import (
    fetch_entsoe_quarter_hour_day_ahead,
)
from open_energy_lab.market.artifact import load_market_data_artifact
from open_energy_lab.market.restoration_artifact import (
    load_restoration_market_artifact,
)
from open_energy_lab.simulator.restoration_settlement import SettlementAvailability


FIXTURES = Path("tests/fixtures/restoration")


class _EntsoeTransport:
    def request(self, **_: object) -> EntsoeTransportResponse:
        body = (
            Path("tests/fixtures/market/synthetic_entsoe/a44_success.xml")
            .read_bytes()
            .replace(b"2022-08-18T22:00Z", b"2026-08-20T00:00Z")
            .replace(b"2022-08-19T02:00Z", b"2026-08-20T01:00Z")
            .replace(b"<resolution>PT1H</resolution>", b"<resolution>PT15M</resolution>")
        )
        return EntsoeTransportResponse(
            status_code=200,
            body=body,
            headers={"Content-Type": "application/xml"},
        )


def test_afrr_live_pipeline_runs_from_area_artifact_through_settlement() -> None:
    artifact = load_restoration_market_artifact(
        FIXTURES / "france_2026-08-20_afrr_market_v1.json"
    )

    result = run_live_restoration_pipeline(
        artifact,
        direction="UPWARD",
        asset_allocation_fraction=0.001,
        committed_capacity_kw=450.0,
    )

    assert result.driver_series_id == "afrr_requested_need_upward"
    assert [
        sample.requested_balancing_power_kw for sample in result.replay.samples
    ] == [-425.0, -315.0, -290.0, -345.0]
    assert [
        sample.delivered_balancing_power_kw for sample in result.replay.samples
    ] == [-425.0, -315.0, -290.0, -345.0]
    assert result.settlement.availability is SettlementAvailability.AVAILABLE
    assert result.settlement.day_ahead_energy_revenue_eur == 0.0
    assert result.day_ahead_source.startswith("study assumption")


def test_mfrr_live_pipeline_preserves_the_selected_scheduled_event() -> None:
    artifact = load_restoration_market_artifact(
        FIXTURES / "france_2026-08-15_mfrr_market_v1.json"
    )

    result = run_live_restoration_pipeline(
        artifact,
        direction="DOWNWARD",
        asset_allocation_fraction=0.001,
        committed_capacity_kw=400.0,
    )

    assert result.driver_series_id == "mfrr_sa_requested_volume_downward"
    assert len(result.activation.events) == 1
    assert result.activation.events[0].requested_power_kw == 357.0
    assert result.replay.samples[0].delivered_balancing_power_kw == 357.0
    assert result.settlement.availability is SettlementAvailability.AVAILABLE


def test_source_null_selected_driver_fails_instead_of_becoming_zero_activation() -> None:
    artifact = load_restoration_market_artifact(
        FIXTURES / "france_2026-08-15_mfrr_market_v1.json"
    )

    with pytest.raises(
        LiveRestorationPipelineError,
        match="total_requested_volume_SA.*SOURCE_NULL",
    ):
        run_live_restoration_pipeline(
            artifact,
            direction="UPWARD",
            asset_allocation_fraction=0.001,
            committed_capacity_kw=400.0,
        )


def test_entsoe_composition_failure_names_the_incompatible_period() -> None:
    artifact = load_restoration_market_artifact(
        FIXTURES / "france_2026-08-20_afrr_market_v1.json"
    )
    old_day_ahead = load_market_data_artifact(
        Path("tests/fixtures/market/france_2022-08-19_market_v1.json")
    )

    with pytest.raises(
        LiveRestorationPipelineError,
        match="A44 day_ahead_price does not cover the selected RTE period",
    ):
        run_live_restoration_pipeline(
            artifact,
            direction="UPWARD",
            asset_allocation_fraction=0.001,
            committed_capacity_kw=450.0,
            entsoe_day_ahead_artifact=old_day_ahead,
        )


def test_native_pt15m_entsoe_artifact_runs_through_live_settlement() -> None:
    rte_artifact = load_restoration_market_artifact(
        FIXTURES / "france_2026-08-20_afrr_market_v1.json"
    )
    entsoe_artifact = fetch_entsoe_quarter_hour_day_ahead(
        EntsoeMarketDataRequest(
            requested_start_utc=datetime(2026, 8, 20, 0, tzinfo=UTC),
            requested_end_utc=datetime(2026, 8, 20, 1, tzinfo=UTC),
            source_endpoint="https://example.test/entsoe/api",
            raw_retention_policy="digest_only",
            normalization_version="entsoe-a44-native-pt15m-v2",
            profile=FranceQuarterHourDayAheadProfile(),
        ),
        api_token="test-token",
        transport=_EntsoeTransport(),
    ).artifact

    result = run_live_restoration_pipeline(
        rte_artifact,
        direction="UPWARD",
        asset_allocation_fraction=0.001,
        committed_capacity_kw=450.0,
        entsoe_day_ahead_artifact=entsoe_artifact,
    )

    assert result.settlement.availability is SettlementAvailability.AVAILABLE
    assert "A44 PT15M" in result.day_ahead_source
    assert "native intervals preserved" in result.day_ahead_source
