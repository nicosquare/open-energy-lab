"""Unit contracts for typed SPFlow 1.1 scopes and pre-backend validation."""

from __future__ import annotations

import pytest

import open_energy_lab.tpm.features as features_module
from open_energy_lab.tpm.data import normalize_training_data
from open_energy_lab.tpm.domains import TPMFeatureDomain
from open_energy_lab.tpm.features import TPMFeatureSpec


FEATURE_SCHEMA = (
    TPMFeatureSpec(
        feature_name="battery_capacity_kwh",
        feature_type="continuous",
        feature_role="decision",
        modifiable=True,
        bounds=(0.0, 20.0),
    ),
    TPMFeatureSpec(
        feature_name="solar_enabled",
        feature_type="binary",
        feature_role="decision",
        modifiable=True,
        discrete_values=(0, 1),
    ),
    TPMFeatureSpec(
        feature_name="design_class",
        feature_type="categorical",
        feature_role="decision",
        modifiable=True,
        discrete_values=("compact", "balanced", "resilient"),
    ),
    TPMFeatureSpec(
        feature_name="ambient_temperature_c",
        feature_type="continuous",
        feature_role="context",
        bounds=(20.0, 40.0),
    ),
)

ROWS = (
    {
        "battery_capacity_kwh": 5.0,
        "solar_enabled": 0,
        "design_class": "compact",
        "ambient_temperature_c": 25.0,
    },
    {
        "battery_capacity_kwh": 10.0,
        "solar_enabled": 1,
        "design_class": "balanced",
        "ambient_temperature_c": 30.0,
    },
    {
        "battery_capacity_kwh": 15.0,
        "solar_enabled": 0,
        "design_class": "resilient",
        "ambient_temperature_c": 35.0,
    },
)

REQUIRED_DECISIONS = (
    "battery_capacity_kwh",
    "solar_enabled",
    "design_class",
)


def test_mixed_feature_schema_maps_to_disjoint_typed_scopes() -> None:
    from spflow.modules.leaves import Bernoulli, Categorical, Normal

    build_leaf_modules = getattr(features_module, "build_spflow_leaf_modules")
    leaves = build_leaf_modules(FEATURE_SCHEMA)

    assert len(leaves) == 3
    normal = next(leaf for leaf in leaves if isinstance(leaf, Normal))
    bernoulli = next(leaf for leaf in leaves if isinstance(leaf, Bernoulli))
    categorical = next(leaf for leaf in leaves if isinstance(leaf, Categorical))

    assert normal.scope.query == (0, 3)
    assert bernoulli.scope.query == (1,)
    assert categorical.scope.query == (2,)
    assert categorical.K == 3
    assert set(normal.scope.query).isdisjoint(bernoulli.scope.query)
    assert set(normal.scope.query).isdisjoint(categorical.scope.query)
    assert set(bernoulli.scope.query).isdisjoint(categorical.scope.query)


def test_training_rows_encode_to_float64_torch_tensor() -> None:
    import torch

    build_tensor = getattr(features_module, "build_spflow_training_tensor")
    tensor = build_tensor(ROWS, feature_schema=FEATURE_SCHEMA)

    assert isinstance(tensor, torch.Tensor)
    assert tensor.dtype == torch.float64
    assert tensor.device.type == "cpu"
    assert tensor.shape == (3, 4)
    assert tensor[:, 0].tolist() == pytest.approx([0.25, 0.5, 0.75])
    assert tensor[:, 1].tolist() == pytest.approx([0.0, 1.0, 0.0])
    assert tensor[:, 2].tolist() == pytest.approx([0.0, 1.0, 2.0])
    assert tensor[:, 3].tolist() == pytest.approx([0.25, 0.5, 0.75])


def test_constant_declared_columns_reach_backend_tensor_without_synthetic_values() -> None:
    rows = (
        {"fixed_x": 100.0, "activation": "off", "tier": "economy"},
        {"fixed_x": 100.0, "activation": "off", "tier": "economy"},
    )
    training_data = normalize_training_data(
        rows,
        feature_domains={
            "fixed_x": TPMFeatureDomain(
                feature_name="fixed_x",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="finite",
                lower=100.0,
                upper=100.0,
            ),
            "activation": TPMFeatureDomain(
                feature_name="activation",
                feature_kind="binary",
                purpose="decision-domain",
                values=("off", "on"),
            ),
            "tier": TPMFeatureDomain(
                feature_name="tier",
                feature_kind="categorical",
                purpose="decision-domain",
                values=("economy", "priority"),
            ),
        },
        feature_roles={
            "fixed_x": "decision",
            "activation": "decision",
            "tier": "decision",
        },
    )

    tensor = features_module.build_spflow_training_tensor(
        training_data.rows,
        feature_schema=training_data.feature_schema,
    )

    assert [dict(row) for row in training_data.normalized_rows] == [
        {"fixed_x": 0.0, "activation": 0.0, "tier": 0.0},
        {"fixed_x": 0.0, "activation": 0.0, "tier": 0.0},
    ]
    assert tensor.tolist() == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]


@pytest.mark.parametrize(
    ("assignments", "expected_feature", "expected_domain", "expected_reason", "supplied"),
    (
        (
            {"solar_enabled": 1, "design_class": "balanced"},
            "battery_capacity_kwh",
            (0.0, 20.0),
            "missing",
            None,
        ),
        (
            {
                "battery_capacity_kwh": 21.0,
                "solar_enabled": 1,
                "design_class": "balanced",
            },
            "battery_capacity_kwh",
            (0.0, 20.0),
            "out_of_bounds",
            21.0,
        ),
        (
            {
                "battery_capacity_kwh": 10.0,
                "solar_enabled": 1,
                "design_class": "unknown",
            },
            "design_class",
            ("compact", "balanced", "resilient"),
            "unseen_category",
            "unknown",
        ),
        (
            {
                "battery_capacity_kwh": 10.0,
                "solar_enabled": 2,
                "design_class": "balanced",
            },
            "solar_enabled",
            (0, 1),
            "invalid_binary",
            2,
        ),
    ),
)
def test_feature_errors_are_structured_before_spflow(
    assignments,
    expected_feature,
    expected_domain,
    expected_reason,
    supplied,
) -> None:
    validation_error = getattr(features_module, "TPMFeatureValidationError")
    validate = getattr(features_module, "validate_spflow_feature_assignments")

    with pytest.raises(validation_error) as exc_info:
        validate(
            FEATURE_SCHEMA,
            assignments,
            required_decision_features=REQUIRED_DECISIONS,
        )

    error = exc_info.value
    details = error.to_dict()
    assert error.feature_name == expected_feature
    assert tuple(error.expected_domain) == expected_domain
    assert error.reason == expected_reason
    assert details["feature_name"] == expected_feature
    assert tuple(details["expected_domain"]) == expected_domain
    assert details["reason"] == expected_reason
    if supplied is None:
        assert "supplied_value" not in details
    else:
        assert error.supplied_value == supplied
        assert details["supplied_value"] == supplied
