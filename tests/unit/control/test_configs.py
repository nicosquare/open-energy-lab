"""Validation coverage for typed native controller configurations."""

from __future__ import annotations

import importlib

import pytest


INVALID_NUMERIC_EXCEPTIONS = (TypeError, ValueError)


def _load_config_type(config_name: str) -> type[object]:
    module = importlib.import_module("open_energy_lab.control._config")
    return getattr(module, config_name)


@pytest.mark.parametrize(
    ("config_name", "kwargs"),
    (
        (
            "PriceThresholdConfig",
            {
                "charge_below_import_price": 0.15,
                "discharge_above_import_price": 0.25,
                "charge_request_kw": 5.0,
                "discharge_request_kw": 4.0,
                "controller_name": "price-threshold-test",
            },
        ),
        (
            "SocGuardrailConfig",
            {
                "target_min_soc": 0.25,
                "target_max_soc": 0.75,
                "charge_request_kw": 5.0,
                "discharge_request_kw": 4.0,
                "controller_name": "soc-guardrail-test",
            },
        ),
        (
            "PVSelfConsumptionConfig",
            {
                "reserve_min_soc": 0.20,
                "reserve_max_soc": 0.80,
                "charge_request_kw": 5.0,
                "discharge_request_kw": 4.0,
                "controller_name": "pv-self-consumption-test",
            },
        ),
    ),
)
def test_controller_configs_accept_valid_values(
    config_name: str,
    kwargs: dict[str, object],
) -> None:
    config_type = _load_config_type(config_name)

    config = config_type(**kwargs)

    assert config.__class__.__name__ == config_name
    for field_name, expected_value in kwargs.items():
        assert getattr(config, field_name) == expected_value


def test_price_threshold_config_rejects_non_numeric_thresholds() -> None:
    config_type = _load_config_type("PriceThresholdConfig")

    with pytest.raises(INVALID_NUMERIC_EXCEPTIONS):
        config_type(
            charge_below_import_price="0.15",
            discharge_above_import_price=0.25,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(INVALID_NUMERIC_EXCEPTIONS):
        config_type(
            charge_below_import_price=0.15,
            discharge_above_import_price=True,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )


def test_price_threshold_config_rejects_non_positive_request_magnitudes() -> None:
    config_type = _load_config_type("PriceThresholdConfig")

    with pytest.raises(ValueError):
        config_type(
            charge_below_import_price=0.15,
            discharge_above_import_price=0.25,
            charge_request_kw=0.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(ValueError):
        config_type(
            charge_below_import_price=0.15,
            discharge_above_import_price=0.25,
            charge_request_kw=5.0,
            discharge_request_kw=-1.0,
        )


@pytest.mark.parametrize(
    ("charge_below_import_price", "discharge_above_import_price"),
    (
        (0.20, 0.20),
        (0.25, 0.20),
    ),
)
def test_price_threshold_config_rejects_invalid_threshold_band(
    charge_below_import_price: float,
    discharge_above_import_price: float,
) -> None:
    config_type = _load_config_type("PriceThresholdConfig")

    with pytest.raises(ValueError):
        config_type(
            charge_below_import_price=charge_below_import_price,
            discharge_above_import_price=discharge_above_import_price,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )


def test_soc_guardrail_config_rejects_out_of_range_guardrails() -> None:
    config_type = _load_config_type("SocGuardrailConfig")

    with pytest.raises(ValueError):
        config_type(
            target_min_soc=-0.01,
            target_max_soc=0.75,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(ValueError):
        config_type(
            target_min_soc=0.25,
            target_max_soc=1.01,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )


def test_soc_guardrail_config_rejects_invalid_guardrail_band() -> None:
    config_type = _load_config_type("SocGuardrailConfig")

    with pytest.raises(ValueError):
        config_type(
            target_min_soc=0.75,
            target_max_soc=0.75,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(ValueError):
        config_type(
            target_min_soc=0.80,
            target_max_soc=0.70,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )


def test_soc_guardrail_config_rejects_non_positive_request_magnitudes() -> None:
    config_type = _load_config_type("SocGuardrailConfig")

    with pytest.raises(ValueError):
        config_type(
            target_min_soc=0.25,
            target_max_soc=0.75,
            charge_request_kw=0.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(ValueError):
        config_type(
            target_min_soc=0.25,
            target_max_soc=0.75,
            charge_request_kw=5.0,
            discharge_request_kw=0.0,
        )


def test_pv_self_consumption_config_rejects_out_of_range_reserves() -> None:
    config_type = _load_config_type("PVSelfConsumptionConfig")

    with pytest.raises(ValueError):
        config_type(
            reserve_min_soc=-0.01,
            reserve_max_soc=0.80,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(ValueError):
        config_type(
            reserve_min_soc=0.20,
            reserve_max_soc=1.01,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )


def test_pv_self_consumption_config_rejects_invalid_reserve_band() -> None:
    config_type = _load_config_type("PVSelfConsumptionConfig")

    with pytest.raises(ValueError):
        config_type(
            reserve_min_soc=0.80,
            reserve_max_soc=0.80,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(ValueError):
        config_type(
            reserve_min_soc=0.90,
            reserve_max_soc=0.80,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )


def test_pv_self_consumption_config_rejects_non_positive_request_magnitudes() -> None:
    config_type = _load_config_type("PVSelfConsumptionConfig")

    with pytest.raises(ValueError):
        config_type(
            reserve_min_soc=0.20,
            reserve_max_soc=0.80,
            charge_request_kw=-1.0,
            discharge_request_kw=5.0,
        )

    with pytest.raises(ValueError):
        config_type(
            reserve_min_soc=0.20,
            reserve_max_soc=0.80,
            charge_request_kw=5.0,
            discharge_request_kw=0.0,
        )
