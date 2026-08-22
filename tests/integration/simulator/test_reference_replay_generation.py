"""Restricted private-repository generation of the Feature 010 replay."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import socket

import pytest

from examples.bess_stacked_services.generate_reference_replay import (
    ReferenceReplayGenerationError,
    _require_safe_destination,
    build_reference_replay_payload,
    write_reference_replay_fixture,
)
from examples.bess_stacked_services.stage_private_reference_market import (
    PrivateFixtureStagingError,
    stage_private_reference_market_artifact,
    write_private_reference_market_fixture,
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


def _reference_market():
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


def test_reference_fixture_write_is_byte_stable_for_private_restricted_inputs(
    tmp_path: Path,
) -> None:
    market = stage_private_reference_market_artifact(
        _reference_market(),
        private_repository_acknowledged=True,
    )
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


def test_unstaged_market_cannot_write_outside_ignored_artifacts(
    tmp_path: Path,
) -> None:
    market = _reference_market()

    with pytest.raises(
        ReferenceReplayGenerationError,
        match="restricted|private|artifacts|A44",
    ):
        _require_safe_destination(market, tmp_path)

    _require_safe_destination(market, Path("artifacts/market/reference-gate"))


def test_private_staging_changes_only_repository_policy_metadata() -> None:
    market = _reference_market()

    staged = stage_private_reference_market_artifact(
        market,
        private_repository_acknowledged=True,
    )

    assert staged.content_fingerprint == market.content_fingerprint
    assert staged.artifact_fingerprint != market.artifact_fingerprint
    assert staged.predecessor_artifact_fingerprint == market.artifact_fingerprint
    policy = staged.retention_and_license
    assert policy["repository_storage"] == "permitted_private_restricted"
    assert policy["repository_publication"] == "prohibited"
    assert policy["series_redistribution"]["day_ahead_price"] == {
        "status": "restricted_private_repository_only",
        "source_document_type": "A44",
    }
    storage = policy["restricted_repository_policy"]
    assert storage["repository_visibility"] == "private"
    assert storage["authorized_audience"] == "repository collaborators"
    assert storage["package_distribution"] == "prohibited"
    assert storage["public_forks_and_mirrors"] == "prohibited"
    assert all(
        item.retention_status == "digest_only" for item in staged.raw_responses
    )
    assert "repository_storage" not in market.retention_and_license


def test_private_staging_requires_explicit_repository_acknowledgement() -> None:
    with pytest.raises(PrivateFixtureStagingError, match="private|acknowledge"):
        stage_private_reference_market_artifact(
            _reference_market(),
            private_repository_acknowledged=False,
        )


def test_private_staging_writes_fixed_fixture_and_unblocks_replay_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_market = _reference_market()
    local_market_path = write_market_data_artifact(
        local_market,
        destination_dir=tmp_path / "private",
    )

    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("private fixture staging attempted network access")

    monkeypatch.setattr(socket, "socket", _network_forbidden)

    first = write_private_reference_market_fixture(
        local_market_path,
        private_repository_acknowledged=True,
        destination_dir=tmp_path / "restricted",
    )
    first_bytes = first.read_bytes()
    second = write_private_reference_market_fixture(
        local_market_path,
        private_repository_acknowledged=True,
        destination_dir=tmp_path / "restricted",
    )

    assert first.name == "france_2022-08-19_market_v1.json"
    assert second == first
    assert second.read_bytes() == first_bytes
    restricted = json.loads(first_bytes)
    assert restricted["retention_and_license"]["repository_storage"] == (
        "permitted_private_restricted"
    )
    assert restricted["retention_and_license"]["repository_publication"] == (
        "prohibited"
    )
    expected_path = write_reference_replay_fixture(
        first,
        activation_path=ACTIVATION_PATH,
        destination_dir=tmp_path / "restricted",
    )
    assert expected_path.name == "france_2022-08-19_expected_replay_v1.json"
    expected = json.loads(expected_path.read_bytes())
    assert expected["restricted_data_policy"]["repository_storage"] == (
        "permitted_private_restricted"
    )
    assert expected["restricted_data_policy"]["repository_publication"] == (
        "prohibited"
    )
