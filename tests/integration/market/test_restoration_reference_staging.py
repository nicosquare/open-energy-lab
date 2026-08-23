"""Restricted fixed-destination staging for the real restoration references."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import urllib.request

import pytest

from examples.restoration_services.stage_private_reference_data import (
    AFRR_PLANNING_RAW_SHA256,
    AFRR_REFERENCE_FILENAME,
    MFRR_PLANNING_RAW_SHA256,
    MFRR_REFERENCE_FILENAME,
    ReferenceDataStagingError,
    stage_private_reference_data,
)
from open_energy_lab.market.restoration_artifact import (
    build_restoration_market_artifact,
    load_restoration_market_artifact,
    write_restoration_market_artifact,
)
from open_energy_lab.market.rte import (
    RTE_AFRR_PROFILE,
    RTE_MFRR_PROFILE,
    RTEHTTPResponse,
    build_rte_restoration_request,
    fetch_rte_restoration_data,
)


FIXTURES = Path("tests/fixtures/restoration/synthetic_rte")
AFRR_START = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
AFRR_END = datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
MFRR_START = datetime(2026, 8, 15, 10, 15, tzinfo=UTC)
MFRR_END = datetime(2026, 8, 15, 10, 30, tzinfo=UTC)
CLIENT_ID_SENTINEL = "STAGING-CLIENT-ID-SENTINEL-2cf0"
CLIENT_SECRET_SENTINEL = "STAGING-CLIENT-SECRET-SENTINEL-885c"
ACCESS_TOKEN_SENTINEL = "STAGING-ACCESS-TOKEN-SENTINEL-aa73"


def _source_body(resource: str) -> bytes:
    if resource == RTE_AFRR_PROFILE.resource:
        return (FIXTURES / "afrr_success.json").read_bytes()
    payload = json.loads((FIXTURES / "mfrr_success.json").read_bytes())
    downward = next(
        row
        for row in payload["mari"]["mari_mesures"]
        if row["direction"] == "downward"
    )
    downward["total_satisfied_need_SA"] = 300.0
    downward["clearing_price"] = 64.83
    downward["requested_activated_volumes_by_prices"][0]["satisfied_need"] = 300.0
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _acquire(tmp_path: Path, resource: str):
    if resource == RTE_AFRR_PROFILE.resource:
        profile = RTE_AFRR_PROFILE
        start, end = AFRR_START, AFRR_END
    else:
        profile = RTE_MFRR_PROFILE
        start, end = MFRR_START, MFRR_END
    raw = _source_body(resource)
    request = build_rte_restoration_request(
        resource=resource,
        requested_start_utc=start,
        requested_end_utc=end,
        requested_series_ids=profile.series_ids,
        required_series_ids=profile.required_series_ids,
        normalization_version="rte-balancing-energy-v5.2-v1",
        raw_retention_policy="DIGEST_ONLY",
        mode="FETCH",
    )

    def auth_transport(_request):
        return RTEHTTPResponse(
            status=200,
            media_type="application/json",
            body=json.dumps(
                {
                    "access_token": ACCESS_TOKEN_SENTINEL,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            ).encode(),
        )

    def data_transport(_request):
        return RTEHTTPResponse(
            status=200,
            media_type="application/json",
            body=raw,
            headers={"ETag": '"authored-staging-evidence-v1"'},
        )

    result = fetch_rte_restoration_data(
        request,
        client_id=CLIENT_ID_SENTINEL,
        client_secret=CLIENT_SECRET_SENTINEL,
        output_directory=tmp_path / "acquired" / resource,
        auth_transport=auth_transport,
        data_transport=data_transport,
        clock=lambda: datetime(2026, 8, 23, 12, 0, tzinfo=UTC),
        sleeper=lambda _seconds: None,
    )
    return result, raw


def _series(artifact, series_id: str):
    return next(item for item in artifact.series if item.series_id == series_id)


def test_staging_publishes_only_exact_normalized_references_to_fixed_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    afrr, afrr_raw = _acquire(tmp_path, RTE_AFRR_PROFILE.resource)
    mfrr, mfrr_raw = _acquire(tmp_path, RTE_MFRR_PROFILE.resource)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("staging attempted network or credential access")

    real_getenv = os.getenv

    def guarded_getenv(key: str, default: str | None = None) -> str | None:
        if key in {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}:
            raise AssertionError(f"staging read {key}")
        return real_getenv(key, default)

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(os, "getenv", guarded_getenv)

    first = stage_private_reference_data(
        afrr.path,
        mfrr.path,
        repository_root=tmp_path / "private-repository",
        private_repository_acknowledged=True,
        secret_sentinels=(
            CLIENT_ID_SENTINEL,
            CLIENT_SECRET_SENTINEL,
            ACCESS_TOKEN_SENTINEL,
        ),
    )
    second = stage_private_reference_data(
        afrr.path,
        mfrr.path,
        repository_root=tmp_path / "private-repository",
        private_repository_acknowledged=True,
        secret_sentinels=(
            CLIENT_ID_SENTINEL,
            CLIENT_SECRET_SENTINEL,
            ACCESS_TOKEN_SENTINEL,
        ),
    )

    assert first.afrr_path.name == AFRR_REFERENCE_FILENAME
    assert first.mfrr_path.name == MFRR_REFERENCE_FILENAME
    assert first.afrr_path == (
        tmp_path
        / "private-repository/tests/fixtures/restoration"
        / AFRR_REFERENCE_FILENAME
    )
    assert first.mfrr_path == (
        tmp_path
        / "private-repository/tests/fixtures/restoration"
        / MFRR_REFERENCE_FILENAME
    )
    assert second == first

    staged_afrr = load_restoration_market_artifact(first.afrr_path)
    staged_mfrr = load_restoration_market_artifact(first.mfrr_path)
    assert staged_afrr == afrr.artifact
    assert staged_mfrr == mfrr.artifact
    assert staged_afrr.profile_id == RTE_AFRR_PROFILE.profile_id
    assert staged_mfrr.profile_id == RTE_MFRR_PROFILE.profile_id
    assert set(staged_afrr.series_manifest) == set(RTE_AFRR_PROFILE.series_ids)
    assert set(staged_mfrr.series_manifest) == set(RTE_MFRR_PROFILE.series_ids)
    assert all(len(item.observations) == 4 for item in staged_afrr.series)
    assert [
        item.value
        for item in _series(
            staged_afrr, "afrr_requested_need_upward"
        ).observations
    ] == [425.0, 315.0, 290.0, 345.0]
    assert _series(
        staged_mfrr, "mfrr_sa_requested_volume_downward"
    ).observations[0].value == 357.0
    assert _series(
        staged_mfrr, "mfrr_sa_satisfied_need_downward"
    ).observations[0].value == 300.0

    assert first.digest_comparisons == (
        (
            "standard_afrr_data",
            AFRR_PLANNING_RAW_SHA256,
            hashlib.sha256(afrr_raw).hexdigest(),
            "DRIFT_REVIEW_REQUIRED",
        ),
        (
            "standard_mfrr_data",
            MFRR_PLANNING_RAW_SHA256,
            hashlib.sha256(mfrr_raw).hexdigest(),
            "DRIFT_REVIEW_REQUIRED",
        ),
    )
    for artifact in (staged_afrr, staged_mfrr):
        assert artifact.raw_retention["policy"] == "DIGEST_ONLY"
        assert artifact.redistribution_policy["repository_storage"] == (
            "permitted_private_restricted"
        )
        assert artifact.redistribution_policy["repository_publication"] == (
            "prohibited"
        )
        assert all(
            item.transformations == ("rte-v5.2-chronological-row-order",)
            for item in artifact.series
        )
        assert all(
            len(item.raw_sha256) == 64
            and set(item.raw_sha256) <= set("0123456789abcdef")
            for item in artifact.request_evidence
        )

    persisted = first.afrr_path.read_bytes() + first.mfrr_path.read_bytes()
    assert afrr_raw not in persisted
    assert mfrr_raw not in persisted
    for sentinel in (
        CLIENT_ID_SENTINEL,
        CLIENT_SECRET_SENTINEL,
        ACCESS_TOKEN_SENTINEL,
        f"Bearer {ACCESS_TOKEN_SENTINEL}",
    ):
        assert sentinel.encode() not in persisted


def test_staging_rejects_wrong_profile_missing_fields_and_semantic_drift(
    tmp_path: Path,
) -> None:
    afrr, _ = _acquire(tmp_path, RTE_AFRR_PROFILE.resource)
    mfrr, _ = _acquire(tmp_path, RTE_MFRR_PROFILE.resource)

    with pytest.raises(ReferenceDataStagingError, match="mFRR profile|resource"):
        stage_private_reference_data(
            afrr.path,
            afrr.path,
            repository_root=tmp_path / "wrong-profile",
            private_repository_acknowledged=True,
        )

    missing = deepcopy(mfrr.artifact.to_dict())
    missing["series"] = [
        item
        for item in missing["series"]
        if item["series_id"] != "mfrr_da_requested_volume_upward"
    ]
    del missing["series_manifest"]["mfrr_da_requested_volume_upward"]
    missing_artifact = build_restoration_market_artifact(missing)
    missing_path = write_restoration_market_artifact(
        missing_artifact, destination_dir=tmp_path / "missing-field"
    )
    with pytest.raises(ReferenceDataStagingError, match="series|fields|exact"):
        stage_private_reference_data(
            afrr.path,
            missing_path,
            repository_root=tmp_path / "missing-output",
            private_repository_acknowledged=True,
        )

    changed = deepcopy(mfrr.artifact.to_dict())
    requested = next(
        item
        for item in changed["series"]
        if item["series_id"] == "mfrr_sa_requested_volume_downward"
    )
    requested["observations"][0]["value"] = 0.0
    changed["series_manifest"]["mfrr_sa_requested_volume_downward"].pop(
        "series_fingerprint", None
    )
    changed_artifact = build_restoration_market_artifact(changed)
    changed_path = write_restoration_market_artifact(
        changed_artifact, destination_dir=tmp_path / "semantic-drift"
    )
    with pytest.raises(ReferenceDataStagingError, match="357|requested|semantic"):
        stage_private_reference_data(
            afrr.path,
            changed_path,
            repository_root=tmp_path / "changed-output",
            private_repository_acknowledged=True,
        )


def test_staging_rejects_secret_or_raw_body_material_before_loading(
    tmp_path: Path,
) -> None:
    afrr, _ = _acquire(tmp_path, RTE_AFRR_PROFILE.resource)
    mfrr, _ = _acquire(tmp_path, RTE_MFRR_PROFILE.resource)
    leaked = json.loads(afrr.path.read_text(encoding="utf-8"))
    leaked["oauth_response"] = {"access_token": ACCESS_TOKEN_SENTINEL}
    leaked_path = tmp_path / "leaked-normalized-artifact.json"
    leaked_path.write_text(json.dumps(leaked), encoding="utf-8")

    with pytest.raises(ReferenceDataStagingError, match="secret|OAuth|raw"):
        stage_private_reference_data(
            leaked_path,
            mfrr.path,
            repository_root=tmp_path / "leak-output",
            private_repository_acknowledged=True,
            secret_sentinels=(ACCESS_TOKEN_SENTINEL,),
        )


@pytest.mark.parametrize("unsafe_name", ["dist", "release", "public", "mirrors"])
def test_staging_refuses_distribution_or_public_targets(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    afrr, _ = _acquire(tmp_path, RTE_AFRR_PROFILE.resource)
    mfrr, _ = _acquire(tmp_path, RTE_MFRR_PROFILE.resource)

    with pytest.raises(ReferenceDataStagingError, match="target|restricted|public"):
        stage_private_reference_data(
            afrr.path,
            mfrr.path,
            repository_root=tmp_path / unsafe_name,
            private_repository_acknowledged=True,
        )


def test_staging_requires_explicit_private_repository_acknowledgement(
    tmp_path: Path,
) -> None:
    afrr, _ = _acquire(tmp_path, RTE_AFRR_PROFILE.resource)
    mfrr, _ = _acquire(tmp_path, RTE_MFRR_PROFILE.resource)

    with pytest.raises(ReferenceDataStagingError, match="private|acknowledge"):
        stage_private_reference_data(
            afrr.path,
            mfrr.path,
            repository_root=tmp_path / "repository",
            private_repository_acknowledged=False,
        )
