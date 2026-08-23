"""Canonical restoration market artifact contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import re
from types import MappingProxyType
from typing import Any

import pytest

from open_energy_lab.market.restoration_artifact import (
    RESTORATION_MARKET_SCHEMA_VERSION,
    ObservationValueState,
    RestorationArtifactValidationError,
    RestorationMarketArtifact,
    SeriesAvailability,
    UnsupportedRestorationArtifactVersionError,
    build_restoration_market_artifact,
)
from open_energy_lab.market.time import CanonicalInterval


PERIOD_START = datetime(2022, 11, 18, 23, 0, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(hours=1)
RTE_PROFILE = "fr-rte-balancing-energy-v5.2-afrr-v1"
RTE_RESOURCE = "standard_afrr_data"
FRANCE_AREA = "France control area"


def _interval_payload(start: datetime, end: datetime) -> dict[str, object]:
    return CanonicalInterval.from_utc(start, end).to_dict()


def _observation(
    index: int,
    value: float | None,
    *,
    state: str = "VALUE",
    field: str = "afrr_need_up",
) -> dict[str, object]:
    start = PERIOD_START + timedelta(minutes=15 * index)
    return {
        "interval": _interval_payload(start, start + timedelta(minutes=15)),
        "value_state": state,
        "value": value,
        "source_row": index,
        "source_field": field,
        "document_ref": "rte-afrr-hour-1",
        "conversion_ref": None,
    }


def _series(
    series_id: str,
    *,
    source: str = "RTE",
    availability: str = "PRESENT",
    observations: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "series_id": series_id,
        "semantic_version": f"{series_id}-v1",
        "source": source,
        "source_version": "5.2",
        "resource": RTE_RESOURCE,
        "source_field": series_id,
        "product": "AFRR",
        "process": "automatic_restoration",
        "direction": "UPWARD",
        "area": FRANCE_AREA,
        "requested_period": _interval_payload(PERIOD_START, PERIOD_END),
        "covered_period": _interval_payload(PERIOD_START, PERIOD_END),
        "source_resolution": "PT15M",
        "canonical_resolution": "PT15M",
        "source_unit": "MW",
        "canonical_unit": "MW",
        "currency": None,
        "availability": availability,
        "transformations": [],
        "observations": observations
        if observations is not None
        else [
            _observation(index, float(index), field=series_id) for index in range(4)
        ],
    }


def _policy(**overrides: object) -> dict[str, object]:
    policy: dict[str, object] = {
        "owner": "RTE",
        "attribution": "RTE Balancing Energy API v5.2",
        "repository_storage": "permitted_private_restricted",
        "repository_publication": "prohibited",
        "package_distribution": "prohibited",
        "release_distribution": "prohibited",
        "public_ci_artifact": "prohibited",
        "public_mirror_or_fork": "prohibited",
        "external_artifact_store": "prohibited",
        "visibility_change_action": "remove_or_reassess_before_change",
    }
    policy.update(overrides)
    return policy


def _valid_restoration_artifact_input() -> dict[str, object]:
    response = b'{"synthetic":"rte-afrr-hour"}'
    return {
        "schema_version": RESTORATION_MARKET_SCHEMA_VERSION,
        "artifact_id": "rte-afrr-2022-11-18t23-v1",
        "source": "RTE",
        "source_version": "5.2",
        "profile_id": RTE_PROFILE,
        "resource": RTE_RESOURCE,
        "request_identity": hashlib.sha256(b"token-free-request").hexdigest(),
        "requested_period": _interval_payload(PERIOD_START, PERIOD_END),
        "covered_period": _interval_payload(PERIOD_START, PERIOD_END),
        "retrieved_at_utc": "2026-08-23T08:00:00Z",
        "series_manifest": {
            "afrr_need_up": {
                "requested": True,
                "required": True,
                "availability": "PRESENT",
            }
        },
        "series": [_series("afrr_need_up")],
        "request_evidence": [
            {
                "request_id": "rte-afrr-hour-1",
                "resource": RTE_RESOURCE,
                "start_utc": "2022-11-18T23:00:00Z",
                "end_utc": "2022-11-19T00:00:00Z",
                "attempt_count": 1,
                "http_status_class": "2xx",
                "response_media_type": "application/json",
                "response_bytes": len(response),
                "raw_sha256": hashlib.sha256(response).hexdigest(),
                "source_revision": None,
            }
        ],
        "raw_retention": {
            "policy": "DIGEST_ONLY",
            "responses": {
                "rte-afrr-hour-1": {
                    "status": "digest_only",
                    "sidecar_locator": None,
                    "sidecar_sha256": None,
                }
            },
        },
        "redistribution_policy": _policy(),
        "predecessor_artifact_fingerprint": None,
    }


def _build_restoration_artifact(
    payload: dict[str, object] | None = None,
) -> RestorationMarketArtifact:
    return build_restoration_market_artifact(
        _valid_restoration_artifact_input() if payload is None else payload
    )


def test_v1_artifact_is_immutable_and_preserves_one_source_provenance() -> None:
    artifact = _build_restoration_artifact()
    series = artifact.series[0]

    assert artifact.schema_version == "oel.restoration.market.v1"
    assert artifact.source.value == "RTE"
    assert series.source is artifact.source
    assert series.source_version == artifact.source_version
    assert series.resource == artifact.resource
    assert series.source_field == "afrr_need_up"
    assert series.requested_period == artifact.requested_period
    assert artifact.requested_period.start_utc == PERIOD_START
    assert artifact.requested_period.local_start.isoformat().startswith(
        "2022-11-19T00:00:00+01:00"
    )
    assert isinstance(artifact.series_manifest, MappingProxyType)
    assert isinstance(artifact.redistribution_policy, MappingProxyType)
    with pytest.raises((AttributeError, TypeError)):
        artifact.series_manifest["afrr_need_up"] = {}  # type: ignore[index]


def test_schema_gate_and_cross_source_series_fail_closed() -> None:
    unknown = _valid_restoration_artifact_input()
    unknown["schema_version"] = "oel.restoration.market.v999"
    with pytest.raises(UnsupportedRestorationArtifactVersionError, match="v999"):
        _build_restoration_artifact(unknown)

    mixed = _valid_restoration_artifact_input()
    mixed["series"] = [
        _series("afrr_need_up"),
        _series("external_price", source="ENTSOE"),
    ]
    mixed["series_manifest"] = {
        "afrr_need_up": {
            "requested": True,
            "required": True,
            "availability": "PRESENT",
        },
        "external_price": {
            "requested": True,
            "required": False,
            "availability": "PRESENT",
        },
    }
    with pytest.raises(RestorationArtifactValidationError, match="one source|source"):
        _build_restoration_artifact(mixed)


def test_missingness_states_keep_zero_null_absent_and_not_requested_distinct() -> None:
    payload = _valid_restoration_artifact_input()
    payload["series"] = [
        _series(
            "zero_value",
            observations=[
                _observation(index, 0.0, field="zero_value") for index in range(4)
            ],
        ),
        _series(
            "nullable_price",
            availability="PRESENT_WITH_NULLS",
            observations=[
                _observation(0, None, state="SOURCE_NULL", field="nullable_price"),
                _observation(1, None, state="FIELD_ABSENT", field="nullable_price"),
            ],
        ),
        _series("source_absent", availability="SOURCE_ABSENT", observations=[]),
        _series("not_requested", availability="NOT_REQUESTED", observations=[]),
    ]
    payload["series_manifest"] = {
        "zero_value": {
            "requested": True,
            "required": True,
            "availability": "PRESENT",
        },
        "nullable_price": {
            "requested": True,
            "required": False,
            "availability": "PRESENT_WITH_NULLS",
        },
        "source_absent": {
            "requested": True,
            "required": False,
            "availability": "SOURCE_ABSENT",
        },
        "not_requested": {
            "requested": False,
            "required": False,
            "availability": "NOT_REQUESTED",
        },
    }

    artifact = _build_restoration_artifact(payload)
    by_id = {series.series_id: series for series in artifact.series}

    assert by_id["zero_value"].observations[0].value_state is ObservationValueState.VALUE
    assert by_id["zero_value"].observations[0].value == 0.0
    assert [
        observation.value_state
        for observation in by_id["nullable_price"].observations
    ] == [ObservationValueState.SOURCE_NULL, ObservationValueState.FIELD_ABSENT]
    assert all(
        observation.value is None
        for observation in by_id["nullable_price"].observations
    )
    assert by_id["source_absent"].availability is SeriesAvailability.SOURCE_ABSENT
    assert by_id["not_requested"].availability is SeriesAvailability.NOT_REQUESTED

    invalid = deepcopy(payload)
    invalid["series"][0]["observations"][0]["value_state"] = "SOURCE_NULL"
    with pytest.raises(RestorationArtifactValidationError, match="SOURCE_NULL|value"):
        _build_restoration_artifact(invalid)


def test_required_coverage_and_manifest_identity_are_validated() -> None:
    gap = _valid_restoration_artifact_input()
    gap["series"][0]["observations"].pop(1)
    with pytest.raises(RestorationArtifactValidationError, match="coverage|gap"):
        _build_restoration_artifact(gap)

    mismatch = _valid_restoration_artifact_input()
    mismatch["series_manifest"]["afrr_need_up"]["availability"] = "SOURCE_ABSENT"
    with pytest.raises(RestorationArtifactValidationError, match="manifest|availability"):
        _build_restoration_artifact(mismatch)


def test_series_content_and_artifact_fingerprints_have_separate_meanings() -> None:
    baseline = _build_restoration_artifact()
    refreshed_payload = _valid_restoration_artifact_input()
    refreshed_payload["retrieved_at_utc"] = "2026-08-23T09:00:00Z"
    refreshed_payload["predecessor_artifact_fingerprint"] = baseline.artifact_fingerprint
    refreshed = _build_restoration_artifact(refreshed_payload)

    changed_payload = _valid_restoration_artifact_input()
    changed_payload["series"][0]["observations"][0]["value"] = 99.0
    changed = _build_restoration_artifact(changed_payload)

    digest = re.compile(r"^[0-9a-f]{64}$")
    assert digest.fullmatch(baseline.series[0].series_fingerprint)
    assert digest.fullmatch(baseline.content_fingerprint)
    assert digest.fullmatch(baseline.artifact_fingerprint)
    assert refreshed.series[0].series_fingerprint == baseline.series[0].series_fingerprint
    assert refreshed.content_fingerprint == baseline.content_fingerprint
    assert refreshed.artifact_fingerprint != baseline.artifact_fingerprint
    assert changed.series[0].series_fingerprint != baseline.series[0].series_fingerprint
    assert changed.content_fingerprint != baseline.content_fingerprint


def test_persisted_fingerprints_are_verified_instead_of_trusted() -> None:
    artifact = _build_restoration_artifact()
    payload: dict[str, Any] = artifact.to_dict()
    payload["content_fingerprint"] = "a" * 64

    with pytest.raises(RestorationArtifactValidationError, match="content_fingerprint"):
        RestorationMarketArtifact.from_dict(payload)
