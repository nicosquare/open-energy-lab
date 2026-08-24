"""Heterogeneous RTE/Feature-010 reference-only study composition."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib

from open_energy_lab.market.artifact import canonical_json_bytes
from open_energy_lab.market.restoration_artifact import (
    build_restoration_study_bundle,
    load_restoration_study_bundle,
)
from open_energy_lab.market.time import CanonicalInterval
from tests.integration.market.test_rte_restoration_workflow import _fetch
from tests.unit.market.test_artifact import (
    PERIOD_START,
    _build_artifact,
    _valid_artifact_input,
)


def _shifted_feature_010_artifact():
    payload = _valid_artifact_input()
    target_start = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    delta = target_start - PERIOD_START

    def _walk(value):
        if isinstance(value, dict):
            if {
                "start_utc",
                "end_utc",
                "local_start",
                "local_end",
                "market_timezone",
                "interval_convention",
            }.issubset(value):
                original = CanonicalInterval.from_dict(value)
                return CanonicalInterval.from_utc(
                    original.start_utc + delta, original.end_utc + delta
                ).to_dict()
            return {key: _walk(inner) for key, inner in value.items()}
        if isinstance(value, list):
            return [_walk(inner) for inner in value]
        return value

    shifted = _walk(payload)
    for window in shifted["query_windows"]:
        for key in ("start_utc", "end_utc"):
            parsed = datetime.fromisoformat(window[key].replace("Z", "+00:00"))
            window[key] = (parsed + delta).isoformat().replace("+00:00", "Z")
    shifted["artifact_id"] = "fr-market-feature010-2026-08-20-v1"
    return _build_artifact(shifted)


def test_bundle_selects_rte_restoration_and_existing_a44_by_exact_reference(
    tmp_path,
) -> None:
    rte_artifact = _fetch(tmp_path / "rte").artifact
    entsoe_artifact = _shifted_feature_010_artifact()
    a44_series = entsoe_artifact.series["day_ahead_price"]
    a44_fingerprint = hashlib.sha256(canonical_json_bytes(a44_series.to_dict())).hexdigest()
    period = CanonicalInterval.from_utc(
        datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 20, 1, 0, tzinfo=UTC),
    )
    payload = {
        "schema_version": "oel.restoration.study-bundle.v1",
        "bundle_id": "rte-afrr-plus-feature010-a44-v1",
        "study_period": period.to_dict(),
        "references": [
            {
                "artifact_id": rte_artifact.artifact_id,
                "artifact_fingerprint": rte_artifact.artifact_fingerprint,
                "selected_series_ids": ["afrr_requested_need_upward"],
                "purpose": "derived aFRR scenario driver",
            },
            {
                "artifact_id": entsoe_artifact.artifact_id,
                "artifact_fingerprint": entsoe_artifact.artifact_fingerprint,
                "selected_series_ids": ["day_ahead_price"],
                "purpose": "unchanged Feature 010 A44 day-ahead context",
            },
        ],
    }

    bundle = build_restoration_study_bundle(
        payload, artifacts=(rte_artifact, entsoe_artifact)
    )
    loaded = load_restoration_study_bundle(
        bundle.to_dict(), artifacts=(rte_artifact, entsoe_artifact)
    )

    assert loaded == bundle
    assert bundle.references[0].selected_series_fingerprints == {
        "afrr_requested_need_upward": next(
            series
            for series in rte_artifact.series
            if series.series_id == "afrr_requested_need_upward"
        ).series_fingerprint
    }
    assert bundle.references[1].selected_series_fingerprints == {
        "day_ahead_price": a44_fingerprint
    }
    serialized = bundle.to_dict()
    assert "observations" not in repr(serialized)
    assert "afrr_requested_need_upward" in repr(serialized)
    assert "day_ahead_price" in repr(serialized)
    assert "fallback" not in repr(serialized).casefold()
