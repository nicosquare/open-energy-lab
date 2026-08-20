"""Unit contracts for TPM training-data normalization."""

from __future__ import annotations

import pytest

from open_energy_lab.tpm.data import TPMTrainingData, normalize_training_data


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
