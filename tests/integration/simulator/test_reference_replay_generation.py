"""Private, publication-gated generation of the Feature 010 reference replay."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

import pytest

from examples.bess_stacked_services.generate_reference_replay import (
    ReferenceReplayGenerationError,
    _require_safe_destination,
    build_reference_replay_payload,
    write_reference_replay_fixture,
)
from open_energy_lab.market import write_market_data_artifact
from tests.unit.market.test_artifact import (
    PERIOD_START,
    _build_artifact,
    _canonical_interval_payload,
    _observation,
    _valid_artifact_input,
)


ACTIVATION_PATH = Path(
    "tests/fixtures/market/france_2022-08-19_activation_v1.json"
)


def _reference_market(*, publication: str | None = None):
    payload = deepcopy(_valid_artifact_input())
    period_end = PERIOD_START + timedelta(hours=24)
    payload["requested_period"] = _canonical_interval_payload(
        PERIOD_START,
        period_end,
    )
    payload["actual_covered_period"] = _canonical_interval_payload(
        PERIOD_START,
        period_end,
    )
    series = payload["series"]
    assert isinstance(series, dict)
    energy = series["day_ahead_price"]
    volume = series["fcr_contracted_volume"]
    price = series["fcr_capacity_price"]
    assert isinstance(energy, dict)
    assert isinstance(volume, dict)
    assert isinstance(price, dict)
    energy["observations"] = [
        _observation(
            PERIOD_START + timedelta(hours=index),
            PERIOD_START + timedelta(hours=index + 1),
            (400.0, 500.0, 600.0)[index % 3],
            document_ref="a44-selected",
            source_position=index + 1,
        )
        for index in range(24)
    ]
    volume["observations"] = [
        _observation(
            PERIOD_START + timedelta(hours=4 * index),
            PERIOD_START + timedelta(hours=4 * (index + 1)),
            300.0 + index,
            document_ref="a81-selected",
            source_position=index + 1,
        )
        for index in range(6)
    ]
    price["observations"] = [
        _observation(
            PERIOD_START + timedelta(hours=4 * index),
            PERIOD_START + timedelta(hours=4 * (index + 1)),
            20.0 + index,
            document_ref="a81-selected",
            source_position=8 * index + 1,
            conversion_ref="a81-eur-per-mw-isp-to-eur-per-mw-hour",
        )
        for index in range(6)
    ]
    query_windows = payload["query_windows"]
    assert isinstance(query_windows, list)
    for window in query_windows:
        assert isinstance(window, dict)
        window["end_utc"] = period_end.isoformat().replace("+00:00", "Z")
    source_documents = payload["source_documents"]
    assert isinstance(source_documents, list)
    for document in source_documents:
        assert isinstance(document, dict)
        document["document_period"] = _canonical_interval_payload(
            PERIOD_START,
            period_end,
        )
    if publication is not None:
        retention = payload["retention_and_license"]
        assert isinstance(retention, dict)
        retention["repository_publication"] = publication
    return _build_artifact(payload)


def test_reference_payload_records_every_threshold_and_headroom_decision() -> None:
    payload = build_reference_replay_payload(
        _reference_market(),
        ACTIVATION_PATH,
    )

    derivation = payload["baseline_derivation"]
    assert isinstance(derivation, dict)
    intervals = derivation["intervals"]
    assert isinstance(intervals, list)
    assert len(intervals) == 24
    assert [item["unmodified_threshold_request_kw"] for item in intervals[:3]] == [
        5.0,
        0.0,
        -5.0,
    ]
    assert all(
        item["admissible_power_interval_kw"] == [-45.0, 45.0]
        and item["committed_fcr_capacity_kw"] == 5.0
        and item["fixed_baseline_power_kw"]
        == item["unmodified_threshold_request_kw"]
        for item in intervals
    )
    expected = payload["expected"]
    assert isinstance(expected, dict)
    counts = expected["counts"]
    assert counts["energy_intervals"] == 24
    assert counts["checkpoint_intervals"] == 96
    assert counts["fcr_blocks"] == 6
    assert counts["activation_samples"] == 8_640
    assert isinstance(counts["saturation_events"], int)
    assert expected["totals"]["penalty_eur"] == 0.0
    assert expected["independent_checks"]["absolute_tolerance"] == 1e-6
    fingerprints = expected["fingerprints"]
    assert all(
        isinstance(fingerprints[name], str) and len(fingerprints[name]) == 64
        for name in (
            "market_artifact",
            "activation_artifact",
            "baseline_configuration",
            "energy_schedule",
            "fcr_schedule",
            "trace",
            "result",
        )
    )


def test_reference_fixture_write_is_byte_stable_for_permitted_inputs(
    tmp_path: Path,
) -> None:
    market = _reference_market(publication="permitted")
    market_path = write_market_data_artifact(
        market,
        destination_dir=tmp_path / "market",
    )

    first = write_reference_replay_fixture(
        market_path,
        activation_path=ACTIVATION_PATH,
        destination_dir=tmp_path / "expected",
    )
    first_bytes = first.read_bytes()
    second = write_reference_replay_fixture(
        market_path,
        activation_path=ACTIVATION_PATH,
        destination_dir=tmp_path / "expected",
    )

    assert first == second
    assert second.read_bytes() == first_bytes
    decoded = json.loads(first_bytes)
    assert decoded["schema_version"] == "oel.stacked-service-reference.v1"


def test_local_only_market_cannot_publish_outside_ignored_artifacts(
    tmp_path: Path,
) -> None:
    market = _reference_market(
        publication="blocked_while_any_series_is_local_only"
    )

    with pytest.raises(
        ReferenceReplayGenerationError,
        match="local-only|artifacts|A44",
    ):
        _require_safe_destination(market, tmp_path)

    _require_safe_destination(market, Path("artifacts/market/reference-gate"))
