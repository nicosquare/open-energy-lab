"""Explicitly selected credentialed ENTSO-E France compatibility check."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib
import os
from pathlib import Path

import pytest


PRODUCTION_ENDPOINT = "https://web-api.tp.entsoe.eu/api"


def _assert_secret_absent(
    token: str,
    *,
    destination: Path,
    values: tuple[object, ...],
) -> None:
    for value in values:
        assert token not in str(value)
        assert token not in repr(value)
    for path in destination.rglob("*"):
        assert token not in str(path)
        if path.is_file():
            assert token.encode() not in path.read_bytes()


@pytest.mark.live_entsoe
def test_live_france_a44_and_combined_a81_profile_is_currently_compatible(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = os.environ.get("ENTSOE_API_TOKEN", "").strip()
    if not token:
        pytest.skip(
            "live ENTSO-E compatibility check requires ENTSOE_API_TOKEN and "
            "explicit selection with -m live_entsoe"
        )

    entsoe = importlib.import_module("open_energy_lab.market.entsoe")
    request = entsoe.EntsoeMarketDataRequest(
        requested_start_utc=datetime(2022, 8, 18, 22, tzinfo=UTC),
        requested_end_utc=datetime(2022, 8, 19, 22, tzinfo=UTC),
        source_endpoint=PRODUCTION_ENDPOINT,
        raw_retention_policy="digest_only",
        normalization_version="entsoe-fr-v1",
    )

    try:
        result = entsoe.fetch_entsoe_market_data(
            request,
            api_token=token,
            destination_dir=tmp_path,
        )
    except Exception as exc:
        captured = capsys.readouterr()
        _assert_secret_absent(
            token,
            destination=tmp_path,
            values=(exc, getattr(exc, "diagnostic", None), captured, caplog.text),
        )
        transient_type = getattr(entsoe, "EntsoeTransientExhaustedError")
        if isinstance(exc, transient_type):
            pytest.skip(
                "live ENTSO-E endpoint was unavailable after the bounded "
                "three-attempt retry policy"
            )
        raise

    captured = capsys.readouterr()
    artifact = result.artifact
    assert result.outcome == "published"
    assert artifact.profile_id == "fr-day-ahead-symmetric-fcr-v1"
    assert artifact.area["eic"] == "10YFR-RTE------C"
    assert len(artifact.series["day_ahead_price"].observations) == 24
    assert len(artifact.series["fcr_contracted_volume"].observations) == 6
    assert len(artifact.series["fcr_capacity_price"].observations) == 6
    assert {
        document.document_type for document in artifact.source_documents
    } >= {"A44", "A81"}
    assert {
        observation.document_ref
        for observation in artifact.series["fcr_contracted_volume"].observations
    } == {
        observation.document_ref
        for observation in artifact.series["fcr_capacity_price"].observations
    }
    assert all(
        evidence.retention_status == "digest_only"
        and evidence.sidecar_locator is None
        for evidence in artifact.raw_responses
    )
    _assert_secret_absent(
        token,
        destination=tmp_path,
        values=(result, artifact.to_dict(), captured, caplog.text),
    )
