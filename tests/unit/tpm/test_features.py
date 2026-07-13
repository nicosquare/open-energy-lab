"""Unit contracts for TPM typed-feature metadata."""

from __future__ import annotations

from dataclasses import fields

import pytest

from open_energy_lab.tpm.features import SUPPORTED_TPM_FEATURE_TYPES, TPMFeatureSpec


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
