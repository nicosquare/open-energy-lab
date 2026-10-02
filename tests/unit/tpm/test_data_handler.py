"""Unit contracts for TPM training-data normalization."""

from __future__ import annotations

import math

import pytest

from tpm.data import TPMTrainingData, normalize_training_data
from tpm.domains import TPMFeatureDomain


def _training_rows() -> tuple[dict[str, object], ...]:
    return (
        {
            "battery_capacity_kwh": 8.0,
            "solar_has_tracking": "enabled",
            "design_name": "baseline-a",
            "solar_tilt_choice": 15.0,
            "shortfall": 0.0,
        },
        {
            "battery_capacity_kwh": 10.0,
            "solar_has_tracking": "disabled",
            "design_name": "baseline-b",
            "solar_tilt_choice": "roof-flat",
            "shortfall": 0.1,
        },
        {
            "battery_capacity_kwh": 12.0,
            "solar_has_tracking": "enabled",
            "design_name": "baseline-a",
            "solar_tilt_choice": "roof-pitched",
            "shortfall": 0.2,
        },
    )


def test_tpm_training_data_placeholder_preserves_column_order_and_rows() -> None:
    training_data = TPMTrainingData(
        column_order=("battery_capacity_kwh", "shortfall"),
        rows=({"battery_capacity_kwh": 8.0, "shortfall": 0.0},),
    )

    assert training_data.column_order == ("battery_capacity_kwh", "shortfall")
    assert len(training_data.rows) == 1
    assert training_data.rows[0]["battery_capacity_kwh"] == pytest.approx(8.0)
    assert training_data.rows[0]["shortfall"] == pytest.approx(0.0)


def test_normalize_training_data_supports_continuous_binary_categorical_and_mixed_inputs() -> None:
    normalized = normalize_training_data(_training_rows())

    assert normalized.column_order == (
        "battery_capacity_kwh",
        "solar_has_tracking",
        "design_name",
        "solar_tilt_choice",
        "shortfall",
    )
    feature_types = {
        feature.feature_name: feature.feature_type for feature in normalized.feature_schema
    }
    assert feature_types == {
        "battery_capacity_kwh": "continuous",
        "solar_has_tracking": "binary",
        "design_name": "categorical",
        "solar_tilt_choice": "mixed",
        "shortfall": "continuous",
    }
    assert normalized.normalized_rows[0]["battery_capacity_kwh"] == pytest.approx(0.0)
    assert normalized.normalized_rows[1]["solar_has_tracking"] == pytest.approx(0.0)
    assert normalized.normalized_rows[2]["solar_tilt_choice"] == pytest.approx(-2.0)
    assert normalized.normalized_rows[2]["shortfall"] == pytest.approx(1.0)


def test_normalize_training_data_rejects_inconsistent_feature_keys_across_rows() -> None:
    invalid_rows = [dict(row) for row in _training_rows()]
    invalid_rows[1].pop("design_name")

    with pytest.raises(ValueError, match="same keys|schema|rows"):
        normalize_training_data(invalid_rows)


def test_declarations_resolve_feature_types_before_observed_value_inference() -> None:
    rows = (
        {
            "x": 60.0,
            "activation": "off",
            "service_tier": "economy",
            "demand": 72.0,
        },
        {
            "x": 140.0,
            "activation": "off",
            "service_tier": "standard",
            "demand": 134.0,
        },
    )
    domains = {
        "x": TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape="finite",
            lower=40.0,
            upper=160.0,
        ),
        "activation": TPMFeatureDomain(
            feature_name="activation",
            feature_kind="binary",
            purpose="decision-domain",
            values=("off", "on"),
        ),
        "service_tier": TPMFeatureDomain(
            feature_name="service_tier",
            feature_kind="categorical",
            purpose="decision-domain",
            values=("economy", "standard", "priority"),
            ordering=("economy", "standard", "priority"),
        ),
        "demand": TPMFeatureDomain(
            feature_name="demand",
            feature_kind="continuous",
            purpose="distribution-support",
            shape="unbounded",
        ),
    }

    normalized = normalize_training_data(
        rows,
        feature_domains=domains,
        feature_roles={
            "x": "decision",
            "activation": "decision",
            "service_tier": "decision",
            "demand": "metric_target",
        },
    )
    specs = {spec.feature_name: spec for spec in normalized.feature_schema}

    assert specs["activation"].feature_type == "binary"
    assert specs["activation"].discrete_values == ("off", "on")
    assert specs["activation"].training_support.observed_values == ("off",)
    assert specs["service_tier"].feature_type == "categorical"
    assert specs["service_tier"].discrete_values == (
        "economy",
        "standard",
        "priority",
    )
    assert specs["service_tier"].training_support.observed_values == (
        "economy",
        "standard",
    )
    assert specs["x"].training_support.minimum == pytest.approx(60.0)
    assert specs["x"].training_support.maximum == pytest.approx(140.0)
    assert specs["x"].bounds == (40.0, 160.0)
    assert specs["demand"].bounds is None
    assert specs["demand"].normalization.kind == "identity"
    assert normalized.normalized_rows[0]["x"] == pytest.approx(1.0 / 6.0)
    assert normalized.normalized_rows[1]["x"] == pytest.approx(5.0 / 6.0)
    assert normalized.normalized_rows[0]["demand"] == pytest.approx(72.0)


def test_declared_category_order_is_independent_of_observed_order() -> None:
    normalized = normalize_training_data(
        (
            {"service_tier": "standard"},
            {"service_tier": "economy"},
        ),
        feature_domains={
            "service_tier": TPMFeatureDomain(
                feature_name="service_tier",
                feature_kind="categorical",
                purpose="decision-domain",
                values=("economy", "standard", "priority"),
                ordering=("priority", "standard", "economy"),
            )
        },
        feature_roles={"service_tier": "decision"},
    )

    spec = normalized.feature_schema[0]
    assert spec.ordering == ("priority", "standard", "economy")
    assert spec.training_support.observed_values == ("standard", "economy")
    assert normalized.normalized_rows == (
        {"service_tier": 1.0},
        {"service_tier": 2.0},
    )


def _finite_x_domain() -> TPMFeatureDomain:
    return TPMFeatureDomain(
        feature_name="x",
        feature_kind="continuous",
        purpose="decision-domain",
        shape="finite",
        lower=40.0,
        upper=160.0,
    )


def test_different_observed_extrema_share_declared_physical_coordinates() -> None:
    first = normalize_training_data(
        ({"x": 60.0}, {"x": 140.0}),
        feature_domains={"x": _finite_x_domain()},
        feature_roles={"x": "decision"},
    )
    second = normalize_training_data(
        ({"x": 80.0}, {"x": 120.0}),
        feature_domains={"x": _finite_x_domain()},
        feature_roles={"x": "decision"},
    )

    first_spec = first.feature_schema[0]
    second_spec = second.feature_schema[0]
    assert first_spec.normalize_value(100.0) == pytest.approx(0.5)
    assert second_spec.normalize_value(100.0) == pytest.approx(0.5)
    assert (first_spec.training_support.minimum, first_spec.training_support.maximum) == (
        60.0,
        140.0,
    )
    assert (second_spec.training_support.minimum, second_spec.training_support.maximum) == (
        80.0,
        120.0,
    )


def test_explicit_unknown_uses_identity_while_omission_keeps_legacy_inference() -> None:
    rows = ({"x": 60.0}, {"x": 140.0})
    explicit = normalize_training_data(
        rows,
        feature_domains={
            "x": TPMFeatureDomain(
                feature_name="x",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="unknown",
            )
        },
        feature_roles={"x": "decision"},
    ).feature_schema[0]
    omitted = normalize_training_data(
        rows,
        feature_roles={"x": "decision"},
    ).feature_schema[0]

    assert explicit.mathematical_domain.shape == "unknown"
    assert explicit.mathematical_domain.origin == "caller-declared"
    assert explicit.normalization.kind == "identity"
    assert explicit.normalize_value(100.0) == pytest.approx(100.0)
    assert omitted.mathematical_domain.shape == "unknown"
    assert omitted.mathematical_domain.origin == "omitted"
    assert omitted.normalization.origin == "legacy-inferred"
    assert omitted.normalize_value(100.0) == pytest.approx(0.5)


def test_declaration_free_fit_preserves_observed_support_without_fabrication() -> None:
    normalized = normalize_training_data(
        (
            {"fixed_x": 5.0, "activation": "off", "tier": "standard"},
            {"fixed_x": 5.0, "activation": "on", "tier": "economy"},
            {"fixed_x": 5.0, "activation": "off", "tier": "standard"},
        ),
        feature_roles={
            "fixed_x": "decision",
            "activation": "decision",
            "tier": "decision",
        },
    )
    specs = {spec.feature_name: spec for spec in normalized.feature_schema}

    assert specs["fixed_x"].mathematical_domain.shape == "unknown"
    assert specs["fixed_x"].mathematical_domain.origin == "omitted"
    assert specs["fixed_x"].training_support.minimum == 5.0
    assert specs["fixed_x"].training_support.maximum == 5.0
    assert specs["fixed_x"].normalization.kind == "fixed-zero"
    assert all(row["fixed_x"] == 0.0 for row in normalized.normalized_rows)
    assert specs["activation"].feature_type == "binary"
    assert specs["activation"].ordering == ("off", "on")
    assert specs["activation"].training_support.observed_values == ("off", "on")
    assert specs["tier"].feature_type == "categorical"
    assert specs["tier"].ordering == ("economy", "standard")
    assert specs["tier"].training_support.observed_values == (
        "standard",
        "economy",
    )
    assert "priority" not in specs["tier"].training_support.observed_values


def test_exact_declared_endpoints_are_valid_physical_observations() -> None:
    normalized = normalize_training_data(
        ({"x": 40.0}, {"x": 160.0}),
        feature_domains={"x": _finite_x_domain()},
        feature_roles={"x": "decision"},
    )

    assert normalized.normalized_rows == ({"x": 0.0}, {"x": 1.0})
    assert normalized.feature_schema[0].training_support.minimum == 40.0
    assert normalized.feature_schema[0].training_support.maximum == 160.0


@pytest.mark.parametrize(
    "outside_value",
    [
        math.nextafter(40.0, -math.inf),
        math.nextafter(160.0, math.inf),
    ],
)
def test_adjacent_outside_observation_fails_without_domain_tolerance(
    outside_value: float,
) -> None:
    with pytest.raises(ValueError, match="x.*decision-domain|outside"):
        normalize_training_data(
            ({"x": outside_value}, {"x": 100.0}),
            feature_domains={"x": _finite_x_domain()},
            feature_roles={"x": "decision"},
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_physical_observation_fails_before_normalization(value: float) -> None:
    with pytest.raises(ValueError, match="x.*finite|finite.*x"):
        normalize_training_data(
            ({"x": value}, {"x": 100.0}),
            feature_domains={"x": _finite_x_domain()},
            feature_roles={"x": "decision"},
        )


def test_training_support_is_not_widened_to_declared_domain() -> None:
    normalized = normalize_training_data(
        ({"x": 60.0}, {"x": 140.0}),
        feature_domains={"x": _finite_x_domain()},
        feature_roles={"x": "decision"},
    )
    support = normalized.feature_schema[0].training_support

    assert (support.minimum, support.maximum) == (60.0, 140.0)
    assert (support.minimum, support.maximum) != (40.0, 160.0)
