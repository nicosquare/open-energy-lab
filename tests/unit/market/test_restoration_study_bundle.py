"""Reference-only restoration study bundle contracts."""

from __future__ import annotations

from copy import deepcopy

import pytest

from open_energy_lab.market.restoration_artifact import (
    RestorationArtifactIntegrityError,
    RestorationArtifactValidationError,
    RestorationStudyBundle,
    build_restoration_market_artifact,
    build_restoration_study_bundle,
    load_restoration_study_bundle,
)
from tests.unit.market.test_restoration_artifact import (
    PERIOD_END,
    PERIOD_START,
    _build_restoration_artifact,
    _interval_payload,
    _policy,
    _valid_restoration_artifact_input,
)


def _second_artifact():
    payload = _valid_restoration_artifact_input()
    payload["artifact_id"] = "entsoe-afrr-comparison-v1"
    payload["source"] = "ENTSOE"
    payload["source_version"] = "Transparency Platform 2026"
    payload["profile_id"] = "fr-entsoe-restoration-comparison-v1"
    payload["resource"] = "A83"
    payload["request_identity"] = "b" * 64
    payload["retrieved_at_utc"] = "2026-08-23T10:00:00Z"
    payload["redistribution_policy"] = _policy(
        owner="ENTSO-E",
        package_distribution="permitted",
    )
    payload["series"][0]["source"] = "ENTSOE"
    payload["series"][0]["source_version"] = "Transparency Platform 2026"
    payload["series"][0]["resource"] = "A83"
    payload["series"][0]["observations"][0]["value"] = 55.0
    payload["request_evidence"][0]["resource"] = "A83"
    return build_restoration_market_artifact(payload)


def _bundle_input(first, second) -> dict[str, object]:
    return {
        "schema_version": "oel.restoration.study-bundle.v1",
        "bundle_id": "restoration-comparison-study-v1",
        "study_period": _interval_payload(PERIOD_START, PERIOD_END),
        "references": [
            {
                "artifact_id": first.artifact_id,
                "artifact_fingerprint": first.artifact_fingerprint,
                "selected_series_ids": ["afrr_need_up"],
                "purpose": "physical driver",
            },
            {
                "artifact_id": second.artifact_id,
                "artifact_fingerprint": second.artifact_fingerprint,
                "selected_series_ids": ["afrr_need_up"],
                "purpose": "independent comparison",
            },
        ],
    }


def test_bundle_resolves_exact_artifacts_and_series_without_copying_observations() -> None:
    first = _build_restoration_artifact()
    second = _second_artifact()
    bundle = build_restoration_study_bundle(
        _bundle_input(first, second), artifacts=(first, second)
    )

    assert isinstance(bundle, RestorationStudyBundle)
    assert len(bundle.references) == 2
    assert bundle.references[0].selected_series_fingerprints == {
        "afrr_need_up": first.series[0].series_fingerprint
    }
    assert bundle.references[1].selected_series_fingerprints == {
        "afrr_need_up": second.series[0].series_fingerprint
    }
    serialized = bundle.to_dict()
    assert "observations" not in repr(serialized)
    assert "series" not in serialized
    assert serialized["source_disagreements"] == [
        {
            "series_id": "afrr_need_up",
            "series_fingerprints": [
                first.series[0].series_fingerprint,
                second.series[0].series_fingerprint,
            ],
            "artifact_fingerprints": [
                first.artifact_fingerprint,
                second.artifact_fingerprint,
            ],
        }
    ]


def test_bundle_propagates_the_strictest_redistribution_policy() -> None:
    first = _build_restoration_artifact()
    second = _second_artifact()
    bundle = build_restoration_study_bundle(
        _bundle_input(first, second), artifacts=(first, second)
    )

    assert bundle.redistribution_policy["package_distribution"] == "prohibited"
    assert bundle.redistribution_policy["repository_storage"] == (
        "permitted_private_restricted"
    )
    assert set(bundle.redistribution_policy["owner"]) == {"RTE", "ENTSO-E"}


def test_bundle_fails_on_missing_artifact_series_or_exact_fingerprint() -> None:
    first = _build_restoration_artifact()
    second = _second_artifact()
    payload = _bundle_input(first, second)

    with pytest.raises(RestorationArtifactValidationError, match="resolve|missing"):
        build_restoration_study_bundle(payload, artifacts=(first,))

    missing_series = deepcopy(payload)
    missing_series["references"][0]["selected_series_ids"] = ["unknown_series"]
    with pytest.raises(RestorationArtifactValidationError, match="unknown_series|series"):
        build_restoration_study_bundle(missing_series, artifacts=(first, second))

    wrong_fingerprint = deepcopy(payload)
    wrong_fingerprint["references"][0]["artifact_fingerprint"] = "f" * 64
    with pytest.raises(RestorationArtifactValidationError, match="fingerprint|resolve"):
        build_restoration_study_bundle(wrong_fingerprint, artifacts=(first, second))

    outside_period = deepcopy(payload)
    outside_period["study_period"] = _interval_payload(
        PERIOD_START, PERIOD_END.replace(hour=1)
    )
    with pytest.raises(RestorationArtifactValidationError, match="cover|study_period"):
        build_restoration_study_bundle(outside_period, artifacts=(first, second))


def test_persisted_bundle_fingerprint_and_series_resolution_are_verified() -> None:
    first = _build_restoration_artifact()
    second = _second_artifact()
    bundle = build_restoration_study_bundle(
        _bundle_input(first, second), artifacts=(first, second)
    )

    loaded = load_restoration_study_bundle(bundle.to_dict(), artifacts=(first, second))
    assert loaded == bundle

    tampered = bundle.to_dict()
    tampered["bundle_fingerprint"] = "a" * 64
    with pytest.raises(RestorationArtifactIntegrityError, match="bundle_fingerprint"):
        load_restoration_study_bundle(tampered, artifacts=(first, second))
