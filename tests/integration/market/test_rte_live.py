"""Explicitly selected production compatibility check for RTE v5.2."""

from __future__ import annotations

from datetime import UTC, datetime
import os

import pytest

from open_energy_lab.market.rte import (
    RTE_AFRR_PROFILE,
    RTE_MFRR_PROFILE,
    build_rte_restoration_request,
    fetch_rte_restoration_data,
)


pytestmark = pytest.mark.live_rte


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("RTE_CLIENT_ID")
    client_secret = os.getenv("RTE_CLIENT_SECRET")
    if not client_id or not client_secret:
        pytest.skip("live RTE check requires exported RTE_CLIENT_ID and RTE_CLIENT_SECRET")
    return client_id, client_secret


def _request(profile, start: datetime, end: datetime):
    return build_rte_restoration_request(
        resource=profile.resource,
        requested_start_utc=start,
        requested_end_utc=end,
        requested_series_ids=profile.series_ids,
        required_series_ids=profile.required_series_ids,
        normalization_version="rte-balancing-energy-v5.2-v1",
        raw_retention_policy="DIGEST_ONLY",
        mode="FETCH",
    )


def test_pinned_afrr_and_mfrr_periods_remain_production_compatible(tmp_path) -> None:
    client_id, client_secret = _credentials()
    afrr = fetch_rte_restoration_data(
        _request(
            RTE_AFRR_PROFILE,
            datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 20, 1, 0, tzinfo=UTC),
        ),
        client_id=client_id,
        client_secret=client_secret,
        output_directory=tmp_path / "afrr",
    )
    mfrr = fetch_rte_restoration_data(
        _request(
            RTE_MFRR_PROFILE,
            datetime(2026, 8, 15, 10, 15, tzinfo=UTC),
            datetime(2026, 8, 15, 10, 30, tzinfo=UTC),
        ),
        client_id=client_id,
        client_secret=client_secret,
        output_directory=tmp_path / "mfrr",
    )

    requested = next(
        series
        for series in afrr.artifact.series
        if series.series_id == "afrr_requested_need_upward"
    )
    assert len(requested.observations) == 4
    assert mfrr.artifact.raw_retention["policy"] == "DIGEST_ONLY"
    assert all(
        item["status"] == "digest_only"
        for item in mfrr.artifact.raw_retention["responses"].values()
    )
