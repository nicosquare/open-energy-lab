"""Unit contracts for TPM typed-feature metadata."""

from __future__ import annotations

from dataclasses import fields
import math

import pytest

from open_energy_lab.tpm.features import SUPPORTED_TPM_FEATURE_TYPES, TPMFeatureSpec
from open_energy_lab.tpm.domains import (
    TPMFeatureDomain,
    TPMNormalizationSpec,
    TPMTrainingSupport,
)


@pytest.mark.parametrize(
    ("feature_type", "feature_role", "discrete_values"),
    (
        ("continuous", "decision", ()),
        ("binary", "decision", ("disabled", "enabled")),
        ("categorical", "decision", ("baseline-a", "baseline-b")),
        ("mixed", "decision", ("roof-flat", "roof-pitched")),
    ),
)
def test_tpm_feature_spec_can_represent_each_supported_feature_type(
    feature_type: str,
    feature_role: str,
    discrete_values: tuple[str, ...],
) -> None:
    spec = TPMFeatureSpec(
        feature_name=f"{feature_type}_feature",
        feature_type=feature_type,
        feature_role=feature_role,
        modifiable=True,
        discrete_values=discrete_values,
    )

    assert SUPPORTED_TPM_FEATURE_TYPES == (
        "continuous",
        "binary",
        "categorical",
        "mixed",
    )
    assert spec.feature_name == f"{feature_type}_feature"
    assert spec.feature_type == feature_type
    assert spec.feature_role == feature_role
    assert spec.modifiable is True
    assert spec.discrete_values == discrete_values


def test_tpm_feature_spec_tracks_documented_typed_schema_fields() -> None:
    field_names = {field.name for field in fields(TPMFeatureSpec)}

    assert {
        "feature_name",
        "feature_role",
        "feature_type",
        "modifiable",
        "monotonicity",
        "bounds",
        "discrete_values",
        "ordering",
        "normalization_rule",
    }.issubset(field_names)


def test_resolved_continuous_feature_derives_legacy_projection_from_semantics() -> None:
    domain = TPMFeatureDomain(
        feature_name="x",
        feature_kind="continuous",
        purpose="decision-domain",
        shape="finite",
        lower=40.0,
        upper=160.0,
    )
    support = TPMTrainingSupport(
        feature_name="x",
        feature_kind="continuous",
        minimum=60.0,
        maximum=140.0,
    )
    normalization = TPMNormalizationSpec(
        feature_name="x",
        feature_kind="continuous",
        kind="min-max",
        origin="caller-declared",
        lower=40.0,
        upper=160.0,
    )

    spec = TPMFeatureSpec(
        feature_name="x",
        feature_type="continuous",
        feature_role="decision",
        modifiable=True,
        mathematical_domain=domain,
        training_support=support,
        normalization=normalization,
    )

    assert spec.mathematical_domain is domain
    assert spec.training_support is support
    assert spec.normalization is normalization
    assert spec.bounds == (40.0, 160.0)
    assert spec.discrete_values == ()
    assert spec.normalization_rule == "minmax"


def test_resolved_declared_binary_projects_complete_caller_order() -> None:
    spec = TPMFeatureSpec(
        feature_name="activation",
        feature_type="binary",
        feature_role="decision",
        modifiable=True,
        mathematical_domain=TPMFeatureDomain(
            feature_name="activation",
            feature_kind="binary",
            purpose="decision-domain",
            values=("off", "on"),
        ),
        training_support=TPMTrainingSupport(
            feature_name="activation",
            feature_kind="binary",
            observed_values=("off",),
        ),
        normalization=TPMNormalizationSpec(
            feature_name="activation",
            feature_kind="binary",
            kind="ordered-index",
            origin="caller-declared",
            ordering=("off", "on"),
        ),
    )

    assert spec.discrete_values == ("off", "on")
    assert spec.ordering == ("off", "on")
    assert spec.training_support.observed_values == ("off",)


@pytest.mark.parametrize(
    ("feature_role", "purpose"),
    [
        ("context", "decision-domain"),
        ("metric_target", "decision-domain"),
        ("decision", "distribution-support"),
    ],
)
def test_resolved_feature_rejects_role_incompatible_domain_purpose(
    feature_role: str,
    purpose: str,
) -> None:
    with pytest.raises(ValueError, match="purpose|role"):
        TPMFeatureSpec(
            feature_name="x",
            feature_type="continuous",
            feature_role=feature_role,
            modifiable=feature_role == "decision",
            mathematical_domain=TPMFeatureDomain(
                feature_name="x",
                feature_kind="continuous",
                purpose=purpose,
                shape="unknown",
            ),
            training_support=TPMTrainingSupport(
                feature_name="x",
                feature_kind="continuous",
                minimum=60.0,
                maximum=140.0,
            ),
            normalization=TPMNormalizationSpec(
                feature_name="x",
                feature_kind="continuous",
                kind="identity",
                origin="caller-declared",
            ),
        )


@pytest.mark.parametrize(
    "record_field",
    ["mathematical_domain", "training_support", "normalization"],
)
def test_resolved_feature_rejects_semantic_record_owned_by_another_feature(
    record_field: str,
) -> None:
    records = {
        "mathematical_domain": TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape="finite",
            lower=40.0,
            upper=160.0,
        ),
        "training_support": TPMTrainingSupport(
            feature_name="x",
            feature_kind="continuous",
            minimum=60.0,
            maximum=140.0,
        ),
        "normalization": TPMNormalizationSpec(
            feature_name="x",
            feature_kind="continuous",
            kind="min-max",
            origin="caller-declared",
            lower=40.0,
            upper=160.0,
        ),
    }
    record = records[record_field]
    record_payload = record.to_dict()
    record_payload["feature_name"] = "other"
    records[record_field] = type(record).from_dict(record_payload)

    with pytest.raises(ValueError, match="feature_name|owned"):
        TPMFeatureSpec(
            feature_name="x",
            feature_type="continuous",
            feature_role="decision",
            modifiable=True,
            **records,
        )


def test_resolved_feature_rejects_kind_and_normalization_contradictions() -> None:
    with pytest.raises(ValueError, match="feature_kind|feature_type"):
        TPMFeatureSpec(
            feature_name="x",
            feature_type="continuous",
            feature_role="decision",
            modifiable=True,
            mathematical_domain=TPMFeatureDomain(
                feature_name="x",
                feature_kind="binary",
                purpose="decision-domain",
                values=("off", "on"),
            ),
            training_support=TPMTrainingSupport(
                feature_name="x",
                feature_kind="continuous",
                minimum=60.0,
                maximum=140.0,
            ),
            normalization=TPMNormalizationSpec(
                feature_name="x",
                feature_kind="continuous",
                kind="min-max",
                origin="caller-declared",
                lower=40.0,
                upper=160.0,
            ),
        )

    with pytest.raises(ValueError, match="normalization|mathematical domain"):
        TPMFeatureSpec(
            feature_name="x",
            feature_type="continuous",
            feature_role="decision",
            modifiable=True,
            mathematical_domain=TPMFeatureDomain(
                feature_name="x",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="finite",
                lower=40.0,
                upper=160.0,
            ),
            training_support=TPMTrainingSupport(
                feature_name="x",
                feature_kind="continuous",
                minimum=60.0,
                maximum=140.0,
            ),
            normalization=TPMNormalizationSpec(
                feature_name="x",
                feature_kind="continuous",
                kind="min-max",
                origin="caller-declared",
                lower=0.0,
                upper=1.0,
            ),
        )


def test_feature_domain_loader_rejects_coupled_or_multi_feature_payload() -> None:
    payload = {
        "feature_name": "quantity",
        "feature_kind": "continuous",
        "purpose": "decision-domain",
        "shape": "finite",
        "lower": 0.0,
        "upper": 100.0,
        "capacity_constraint": "quantity + reserve <= storage",
    }

    with pytest.raises(ValueError, match="unknown field.*capacity_constraint"):
        TPMFeatureDomain.from_dict(payload)


def _resolved_continuous_spec(
    *,
    shape: str,
    lower: float | None = None,
    upper: float | None = None,
    origin: str = "caller-declared",
) -> TPMFeatureSpec:
    normalization_kind = (
        "min-max"
        if shape == "finite" and lower != upper
        else "fixed-zero"
        if shape == "finite"
        else "identity"
    )
    normalization_kwargs: dict[str, object] = {}
    if normalization_kind in {"min-max", "fixed-zero"}:
        normalization_kwargs = {"lower": lower, "upper": upper}
    return TPMFeatureSpec(
        feature_name="x",
        feature_type="continuous",
        feature_role="decision",
        modifiable=True,
        mathematical_domain=TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape=shape,
            lower=lower,
            upper=upper,
            origin=origin,
        ),
        training_support=TPMTrainingSupport(
            feature_name="x",
            feature_kind="continuous",
            minimum=(lower if shape == "finite" and lower == upper else 60.0),
            maximum=(upper if shape == "finite" and lower == upper else 140.0),
        ),
        normalization=TPMNormalizationSpec(
            feature_name="x",
            feature_kind="continuous",
            kind=normalization_kind,
            origin=origin,
            **normalization_kwargs,
        ),
    )


def test_finite_domain_uses_exact_closed_validation_and_invertible_coordinates() -> None:
    spec = _resolved_continuous_spec(shape="finite", lower=40.0, upper=160.0)

    assert spec.normalize_value(40.0) == pytest.approx(0.0)
    assert spec.normalize_value(160.0) == pytest.approx(1.0)
    assert spec.denormalize_value(0.25) == pytest.approx(70.0)
    with pytest.raises(ValueError, match="decision-domain|outside"):
        spec.validate_value(math.nextafter(40.0, -math.inf))
    with pytest.raises(ValueError, match="decision-domain|outside"):
        spec.validate_value(math.nextafter(160.0, math.inf))


def test_fixed_domain_maps_sole_value_to_zero_without_division() -> None:
    spec = _resolved_continuous_spec(shape="finite", lower=100.0, upper=100.0)

    assert spec.normalize_value(100.0) == pytest.approx(0.0)
    assert spec.denormalize_value(0.0) == pytest.approx(100.0)
    with pytest.raises(ValueError, match="decision-domain|100"):
        spec.normalize_value(math.nextafter(100.0, math.inf))
    with pytest.raises(ValueError, match="fixed-zero|coordinate"):
        spec.denormalize_value(math.nextafter(0.0, math.inf))


@pytest.mark.parametrize(
    ("shape", "lower", "upper", "accepted", "rejected"),
    [
        ("lower-bounded", 40.0, None, 250.0, math.nextafter(40.0, -math.inf)),
        ("upper-bounded", None, 160.0, -250.0, math.nextafter(160.0, math.inf)),
        ("unbounded", None, None, 250.0, None),
        ("unknown", None, None, -250.0, None),
    ],
)
def test_identity_domains_preserve_physical_units_and_directional_membership(
    shape: str,
    lower: float | None,
    upper: float | None,
    accepted: float,
    rejected: float | None,
) -> None:
    spec = _resolved_continuous_spec(shape=shape, lower=lower, upper=upper)

    assert spec.normalize_value(accepted) == pytest.approx(accepted)
    assert spec.denormalize_value(accepted) == pytest.approx(accepted)
    if rejected is not None:
        with pytest.raises(ValueError, match="decision-domain|outside"):
            spec.validate_value(rejected)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_continuous_assignment_and_model_coordinate_must_be_finite(value: float) -> None:
    spec = _resolved_continuous_spec(shape="unbounded")

    with pytest.raises(ValueError, match="finite"):
        spec.normalize_value(value)
    with pytest.raises(ValueError, match="finite"):
        spec.denormalize_value(value)


@pytest.mark.parametrize(
    ("feature_kind", "values", "ordering"),
    [
        ("binary", ("off", "on"), ("off", "on")),
        (
            "categorical",
            ("economy", "standard", "priority"),
            ("priority", "standard", "economy"),
        ),
    ],
)
def test_declared_discrete_normalization_round_trips_caller_labels(
    feature_kind: str,
    values: tuple[str, ...],
    ordering: tuple[str, ...],
) -> None:
    spec = TPMFeatureSpec(
        feature_name="choice",
        feature_type=feature_kind,
        feature_role="decision",
        modifiable=True,
        mathematical_domain=TPMFeatureDomain(
            feature_name="choice",
            feature_kind=feature_kind,
            purpose="decision-domain",
            values=values,
            ordering=ordering,
        ),
        training_support=TPMTrainingSupport(
            feature_name="choice",
            feature_kind=feature_kind,
            observed_values=(values[0],),
        ),
        normalization=TPMNormalizationSpec(
            feature_name="choice",
            feature_kind=feature_kind,
            kind="ordered-index",
            origin="caller-declared",
            ordering=ordering,
        ),
    )

    for index, value in enumerate(ordering):
        assert spec.normalize_value(value) == pytest.approx(float(index))
        assert spec.denormalize_value(float(index)) == value
    with pytest.raises(ValueError, match="declared|domain|choice"):
        spec.validate_value("not-declared")
