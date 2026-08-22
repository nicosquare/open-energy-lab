"""Private, publication-gated generation of the Feature 010 reference replay."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import socket

import pytest

from examples.bess_stacked_services.authorize_reference_market import (
    MarketPublicationPermissionError,
    authorize_reference_market_artifact,
    load_market_publication_permission,
    write_authorized_reference_market_fixture,
)
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
PERMISSION_TEMPLATE_PATH = Path(
    "examples/bess_stacked_services/epex_publication_permission.example.json"
)
PERMISSION_EVIDENCE = b"synthetic rights-holder grant used only by this test"


def _permission_payload() -> dict[str, object]:
    return {
        "schema_version": "oel.epex-publication-permission.v1",
        "rights_holder": "EPEX SPOT SE",
        "grant_type": "written_permission",
        "permission_reference": "SYNTHETIC-TEST-PERMISSION-001",
        "permission_evidence_sha256": hashlib.sha256(
            PERMISSION_EVIDENCE
        ).hexdigest(),
        "effective_date": "2026-08-22",
        "reviewed_at_utc": "2026-08-22T10:30:00Z",
        "reviewed_by": "synthetic test legal-review role",
        "repository_url": "https://github.com/nicosquare/open-energy-lab",
        "covered_data": {
            "area_eic": "10YFR-RTE------C",
            "document_type": "A44",
            "delivery_start_utc": "2022-08-18T22:00:00Z",
            "delivery_end_utc": "2022-08-19T22:00:00Z",
            "description": "24 normalized France hourly day-ahead prices",
        },
        "grant_scope": {
            "public_repository_distribution": True,
            "normalized_a44_value_distribution": True,
            "derived_replay_fixture_distribution": True,
            "adaptation_and_normalization": True,
            "public_forks_and_source_archives": True,
        },
        "attribution": "Source: EPEX SPOT SE; normalized by Open Energy Lab",
        "downstream_terms": (
            "Synthetic test terms standing in for the rights-holder grant"
        ),
        "ai_ml_terms": (
            "Synthetic test field; the real grant must state the applicable terms"
        ),
        "source_terms": {
            "title": "EPEX SPOT General Conditions for Market Data",
            "version_date": "2025-11-01",
            "url": (
                "https://www.epexspot.com/sites/default/files/"
                "download_center_files/EPEX%20SPOT%20GENERAL%20CONDITIONS_"
                "Market%20Data%20as%20of%201st%20November%202025.pdf"
            ),
        },
    }


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


def test_exact_permission_attestation_authorizes_only_repository_metadata() -> None:
    market = _reference_market(
        publication="blocked_while_any_series_is_local_only"
    )
    permission = load_market_publication_permission(_permission_payload())

    authorized = authorize_reference_market_artifact(
        market,
        permission,
        permission_evidence=PERMISSION_EVIDENCE,
    )

    assert authorized.content_fingerprint == market.content_fingerprint
    assert authorized.artifact_fingerprint != market.artifact_fingerprint
    assert authorized.predecessor_artifact_fingerprint == market.artifact_fingerprint
    assert authorized.created_at_utc == "2026-08-22T10:30:00Z"
    policy = authorized.retention_and_license
    assert policy["repository_publication"] == "permitted"
    assert policy["series_redistribution"]["day_ahead_price"] == {
        "status": "rights_holder_permission",
        "source_document_type": "A44",
        "rights_holder": "EPEX SPOT SE",
        "permission_reference": "SYNTHETIC-TEST-PERMISSION-001",
    }
    assert policy["publication_permission"]["permission_evidence_sha256"] == (
        hashlib.sha256(PERMISSION_EVIDENCE).hexdigest()
    )
    assert all(
        item.retention_status == "digest_only" for item in authorized.raw_responses
    )
    assert market.retention_and_license["repository_publication"].startswith(
        "blocked"
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload.update(rights_holder="unverified owner"),
            "EPEX SPOT SE",
        ),
        (
            lambda payload: payload["grant_scope"].update(
                public_repository_distribution=False
            ),
            "public_repository_distribution",
        ),
        (
            lambda payload: payload.update(permission_evidence_sha256="placeholder"),
            "permission_evidence_sha256",
        ),
        (
            lambda payload: payload.update(repository_url="https://example.test/repo"),
            "repository_url",
        ),
    ],
)
def test_incomplete_or_misdirected_permission_is_rejected(
    mutate: object,
    message: str,
) -> None:
    payload = _permission_payload()
    mutate(payload)

    with pytest.raises(MarketPublicationPermissionError, match=message):
        load_market_publication_permission(payload)


def test_committed_permission_template_cannot_authorize_publication() -> None:
    with pytest.raises(
        MarketPublicationPermissionError,
        match="placeholder|explicitly true|SHA-256",
    ):
        load_market_publication_permission(PERMISSION_TEMPLATE_PATH)


def test_permission_must_cover_the_artifact_period() -> None:
    payload = _permission_payload()
    payload["covered_data"]["delivery_end_utc"] = "2022-08-20T22:00:00Z"
    permission = load_market_publication_permission(payload)

    with pytest.raises(
        MarketPublicationPermissionError,
        match="covered data|period",
    ):
        authorize_reference_market_artifact(
            _reference_market(),
            permission,
            permission_evidence=PERMISSION_EVIDENCE,
        )


def test_permission_evidence_bytes_must_match_the_recorded_digest() -> None:
    permission = load_market_publication_permission(_permission_payload())

    with pytest.raises(
        MarketPublicationPermissionError,
        match="evidence.*SHA-256|SHA-256.*evidence",
    ):
        authorize_reference_market_artifact(
            _reference_market(),
            permission,
            permission_evidence=b"different evidence",
        )


def test_authorization_revalidates_an_already_constructed_permission() -> None:
    permission = load_market_publication_permission(_permission_payload())
    bypass_attempt = replace(permission, rights_holder="unverified owner")

    with pytest.raises(MarketPublicationPermissionError, match="EPEX SPOT SE"):
        authorize_reference_market_artifact(
            _reference_market(),
            bypass_attempt,
            permission_evidence=PERMISSION_EVIDENCE,
        )


def test_permission_workflow_writes_fixed_fixture_and_unblocks_replay_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_market = _reference_market(
        publication="blocked_while_any_series_is_local_only"
    )
    local_market_path = write_market_data_artifact(
        local_market,
        destination_dir=tmp_path / "private",
    )
    permission_path = tmp_path / "permission.json"
    permission_path.write_text(
        json.dumps(_permission_payload()),
        encoding="utf-8",
    )
    evidence_path = tmp_path / "private-rights-holder-grant.pdf"
    evidence_path.write_bytes(PERMISSION_EVIDENCE)

    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("publication authorization attempted network access")

    monkeypatch.setattr(socket, "socket", _network_forbidden)

    first = write_authorized_reference_market_fixture(
        local_market_path,
        permission_path=permission_path,
        permission_evidence_path=evidence_path,
        destination_dir=tmp_path / "published",
    )
    first_bytes = first.read_bytes()
    second = write_authorized_reference_market_fixture(
        local_market_path,
        permission_path=permission_path,
        permission_evidence_path=evidence_path,
        destination_dir=tmp_path / "published",
    )

    assert first.name == "france_2022-08-19_market_v1.json"
    assert second == first
    assert second.read_bytes() == first_bytes
    assert PERMISSION_EVIDENCE not in first_bytes
    assert str(evidence_path).encode() not in first_bytes
    published = json.loads(first_bytes)
    assert published["retention_and_license"]["repository_publication"] == (
        "permitted"
    )
    expected_path = write_reference_replay_fixture(
        first,
        activation_path=ACTIVATION_PATH,
        destination_dir=tmp_path / "published",
    )
    assert expected_path.name == "france_2022-08-19_expected_replay_v1.json"
