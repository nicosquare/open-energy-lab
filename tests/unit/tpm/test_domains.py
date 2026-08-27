"""Contracts for import-light TPM domain semantic records."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import math

import pytest

from open_energy_lab.tpm.domains import (
    TPMFeatureDomain,
    TPMNormalizationSpec,
    TPMTrainingSupport,
)


@pytest.mark.parametrize(
    ("shape", "lower", "upper"),
    [
        ("finite", 40.0, 160.0),
        ("finite", 100.0, 100.0),
        ("lower-bounded", 0.0, None),
        ("upper-bounded", None, 100.0),
        ("unbounded", None, None),
        ("unknown", None, None),
    ],
)
def test_continuous_domain_shapes_round_trip_without_numeric_infinity(
    shape: str,
    lower: float | None,
    upper: float | None,
) -> None:
    domain = TPMFeatureDomain(
        feature_name="x",
        feature_kind="continuous",
        purpose="decision-domain",
        shape=shape,
        lower=lower,
        upper=upper,
        origin="caller-declared",
    )

    payload = domain.to_dict()
    encoded = json.dumps(payload, allow_nan=False)

    assert TPMFeatureDomain.from_dict(json.loads(encoded)) == domain
    assert "Infinity" not in encoded


def test_unknown_and_unbounded_remain_distinct_after_round_trip() -> None:
    unknown = TPMFeatureDomain(
        feature_name="demand",
        feature_kind="continuous",
        purpose="distribution-support",
        shape="unknown",
        origin="caller-declared",
    )
    unbounded = TPMFeatureDomain(
        feature_name="demand",
        feature_kind="continuous",
        purpose="distribution-support",
        shape="unbounded",
        origin="caller-declared",
    )

    assert unknown != unbounded
    assert TPMFeatureDomain.from_dict(unknown.to_dict()).shape == "unknown"
    assert TPMFeatureDomain.from_dict(unbounded.to_dict()).shape == "unbounded"


def test_domain_preserves_purpose_and_omission_origin() -> None:
    domain = TPMFeatureDomain(
        feature_name="x",
        feature_kind="continuous",
        purpose="decision-domain",
        shape="unknown",
        origin="omitted",
    )

    assert domain.purpose == "decision-domain"
    assert domain.origin == "omitted"


@pytest.mark.parametrize("endpoint", [math.nan, math.inf, -math.inf, True, "40"])
def test_continuous_domain_rejects_non_finite_or_non_numeric_endpoints(
    endpoint: object,
) -> None:
    with pytest.raises((TypeError, ValueError), match="finite numeric"):
        TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape="finite",
            lower=endpoint,  # type: ignore[arg-type]
            upper=160.0,
        )


def test_continuous_domain_rejects_reversed_endpoints_exactly() -> None:
    with pytest.raises(ValueError, match="lower.*upper"):
        TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape="finite",
            lower=math.nextafter(40.0, math.inf),
            upper=40.0,
        )


@pytest.mark.parametrize(
    ("shape", "lower", "upper"),
    [
        ("finite", None, 10.0),
        ("finite", 0.0, None),
        ("lower-bounded", None, None),
        ("lower-bounded", 0.0, 10.0),
        ("upper-bounded", None, None),
        ("upper-bounded", 0.0, 10.0),
        ("unbounded", 0.0, None),
        ("unknown", None, 10.0),
    ],
)
def test_continuous_shape_rejects_contradictory_endpoint_structure(
    shape: str,
    lower: float | None,
    upper: float | None,
) -> None:
    with pytest.raises(ValueError, match="shape"):
        TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape=shape,
            lower=lower,
            upper=upper,
        )


def test_binary_domain_preserves_caller_order_even_when_one_value_is_unobserved() -> None:
    domain = TPMFeatureDomain(
        feature_name="activation",
        feature_kind="binary",
        purpose="decision-domain",
        values=("off", "on"),
    )

    assert domain.values == ("off", "on")
    assert domain.ordering == ("off", "on")
    assert TPMFeatureDomain.from_dict(domain.to_dict()) == domain


@pytest.mark.parametrize("values", [(), ("off",), ("off", "off"), ("a", "b", "c")])
def test_binary_domain_requires_exactly_two_distinct_values(
    values: tuple[object, ...],
) -> None:
    with pytest.raises(ValueError, match="exactly two distinct"):
        TPMFeatureDomain(
            feature_name="activation",
            feature_kind="binary",
            purpose="decision-domain",
            values=values,
        )


def test_categorical_domain_preserves_complete_values_and_authoritative_order() -> None:
    domain = TPMFeatureDomain(
        feature_name="service_tier",
        feature_kind="categorical",
        purpose="decision-domain",
        values=("economy", "standard", "priority"),
        ordering=("priority", "standard", "economy"),
    )

    assert domain.values == ("economy", "standard", "priority")
    assert domain.ordering == ("priority", "standard", "economy")
    assert TPMFeatureDomain.from_dict(domain.to_dict()) == domain


@pytest.mark.parametrize(
    ("values", "ordering"),
    [
        ((), ()),
        (("economy", "economy"), ()),
        (("economy", "priority"), ("economy",)),
        (("economy", "priority"), ("economy", "standard")),
    ],
)
def test_categorical_domain_requires_complete_distinct_ordering(
    values: tuple[object, ...],
    ordering: tuple[object, ...],
) -> None:
    with pytest.raises(ValueError, match="categorical"):
        TPMFeatureDomain(
            feature_name="service_tier",
            feature_kind="categorical",
            purpose="decision-domain",
            values=values,
            ordering=ordering,
        )


def test_domain_payload_owns_one_named_feature_and_rejects_constraint_data() -> None:
    valid_payload = {
        "feature_name": "quantity",
        "feature_kind": "continuous",
        "purpose": "decision-domain",
        "shape": "lower-bounded",
        "lower": 0.0,
        "origin": "caller-declared",
    }

    assert TPMFeatureDomain.from_dict(valid_payload).feature_name == "quantity"

    for invalid_key in ("feature_names", "capacity_constraint", "expression"):
        payload = {**valid_payload, invalid_key: "quantity + reserve <= capacity"}
        with pytest.raises(ValueError, match="unknown field"):
            TPMFeatureDomain.from_dict(payload)


def test_domain_record_is_immutable() -> None:
    domain = TPMFeatureDomain(
        feature_name="x",
        feature_kind="continuous",
        purpose="decision-domain",
        shape="finite",
        lower=40.0,
        upper=160.0,
    )

    with pytest.raises(FrozenInstanceError):
        domain.lower = 0.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "support",
    [
        TPMTrainingSupport(
            feature_name="x",
            feature_kind="continuous",
            minimum=60.0,
            maximum=140.0,
        ),
        TPMTrainingSupport(
            feature_name="activation",
            feature_kind="binary",
            observed_values=("off",),
        ),
        TPMTrainingSupport(
            feature_name="service_tier",
            feature_kind="categorical",
            observed_values=("economy", "standard"),
        ),
    ],
)
def test_training_support_round_trip_records_observed_physical_evidence_only(
    support: TPMTrainingSupport,
) -> None:
    assert TPMTrainingSupport.from_dict(support.to_dict()) == support
    json.dumps(support.to_dict(), allow_nan=False)


def test_training_support_rejects_theoretical_or_contradictory_data() -> None:
    with pytest.raises(ValueError, match="continuous training support"):
        TPMTrainingSupport(
            feature_name="x",
            feature_kind="continuous",
            minimum=60.0,
            maximum=140.0,
            observed_values=(60.0, 140.0),
        )

    with pytest.raises(ValueError, match="observed values"):
        TPMTrainingSupport(
            feature_name="activation",
            feature_kind="binary",
            observed_values=("off", "off"),
        )


@pytest.mark.parametrize(
    "normalization",
    [
        TPMNormalizationSpec(
            feature_name="x",
            feature_kind="continuous",
            kind="min-max",
            origin="caller-declared",
            lower=40.0,
            upper=160.0,
        ),
        TPMNormalizationSpec(
            feature_name="fixed_x",
            feature_kind="continuous",
            kind="fixed-zero",
            origin="caller-declared",
            lower=100.0,
            upper=100.0,
        ),
        TPMNormalizationSpec(
            feature_name="demand",
            feature_kind="continuous",
            kind="identity",
            origin="caller-declared",
        ),
        TPMNormalizationSpec(
            feature_name="activation",
            feature_kind="binary",
            kind="ordered-index",
            origin="caller-declared",
            ordering=("off", "on"),
        ),
        TPMNormalizationSpec(
            feature_name="legacy_x",
            feature_kind="continuous",
            kind="min-max",
            origin="legacy-inferred",
            lower=60.0,
            upper=140.0,
        ),
    ],
)
def test_normalization_metadata_round_trip_without_changing_provenance(
    normalization: TPMNormalizationSpec,
) -> None:
    payload = normalization.to_dict()

    assert TPMNormalizationSpec.from_dict(payload) == normalization
    assert TPMNormalizationSpec.from_dict(payload).origin == normalization.origin
    json.dumps(payload, allow_nan=False)


def test_normalization_rejects_parameters_that_conflict_with_transform_kind() -> None:
    with pytest.raises(ValueError, match="min-max"):
        TPMNormalizationSpec(
            feature_name="x",
            feature_kind="continuous",
            kind="min-max",
            origin="caller-declared",
            lower=100.0,
            upper=100.0,
        )

    with pytest.raises(ValueError, match="identity"):
        TPMNormalizationSpec(
            feature_name="demand",
            feature_kind="continuous",
            kind="identity",
            origin="caller-declared",
            lower=0.0,
        )

    with pytest.raises(ValueError, match="ordered-index"):
        TPMNormalizationSpec(
            feature_name="activation",
            feature_kind="binary",
            kind="ordered-index",
            origin="caller-declared",
            ordering=("off",),
        )


@pytest.mark.parametrize(
    ("record_type", "payload"),
    [
        (TPMFeatureDomain, {"feature_name": "x"}),
        (TPMTrainingSupport, {"feature_name": "x"}),
        (TPMNormalizationSpec, {"feature_name": "x"}),
    ],
)
def test_semantic_record_loaders_reject_incomplete_payloads(
    record_type: type,
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="missing required field"):
        record_type.from_dict(payload)
