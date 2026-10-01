"""RTE area-price proxy mapping and lineage tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.restoration_settlement import (
    RestorationSettlementValidationError,
    build_area_price_proxy_mapping,
    build_directional_activation_price,
)


START = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
INTERVAL = CanonicalInterval.from_utc(START, START + timedelta(minutes=15))
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _mapping(**overrides: object):
    kwargs: dict[str, object] = {
        "mapping_id": "rte-afrr-upward-price-proxy-v1",
        "source_artifact_fingerprint": SHA_A,
        "source_series_fingerprint": SHA_B,
        "derived_activation_mapping_fingerprint": SHA_C,
        "product": "AFRR",
        "direction": "UPWARD",
        "price_field": "upward_weighted_average_price_afrr_activated_for_fr",
        "coverage": INTERVAL,
        "source_unit": "EUR/MWh",
        "canonical_unit": "EUR/MWh",
        "transformation": "identity",
        "assumptions": (
            "Area weighted-average price is used only as a simulation proxy",
        ),
        "output_label": "scenario_proxy",
    }
    kwargs.update(overrides)
    return build_area_price_proxy_mapping(**kwargs)


def test_area_price_proxy_pins_source_series_activation_mapping_and_label() -> None:
    mapping = _mapping()

    assert mapping.source_artifact_fingerprint == SHA_A
    assert mapping.source_series_fingerprint == SHA_B
    assert mapping.derived_activation_mapping_fingerprint == SHA_C
    assert mapping.price_field == (
        "upward_weighted_average_price_afrr_activated_for_fr"
    )
    assert mapping.output_label == "scenario_proxy"


def test_rte_proxy_price_requires_exact_product_direction_interval_and_unit() -> None:
    mapping = _mapping()
    price = build_directional_activation_price(
        price_id="rte-afrr-upward-price-q1",
        product="AFRR",
        direction="UPWARD",
        mfrr_kind=None,
        interval=INTERVAL,
        value_state="VALUE",
        price=100.0,
        unit="EUR/MWh",
        currency="EUR",
        pricing_basis="RTE_AREA_PRICE_PROXY",
        source_or_assumption_ref="RTE:Balancing-Energy:5.2",
        source_field="upward_weighted_average_price_afrr_activated_for_fr",
        area_price_proxy_mapping=mapping,
    )

    assert price.area_price_proxy_mapping is mapping
    assert price.result_label == "scenario_proxy"

    with pytest.raises(
        RestorationSettlementValidationError,
        match="direction|mapping|DOWNWARD|UPWARD",
    ):
        build_directional_activation_price(
            price_id="wrong-direction",
            product="AFRR",
            direction="DOWNWARD",
            mfrr_kind=None,
            interval=INTERVAL,
            value_state="VALUE",
            price=100.0,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="RTE_AREA_PRICE_PROXY",
            source_or_assumption_ref="RTE",
            source_field="field",
            area_price_proxy_mapping=mapping,
        )

    uncovered = CanonicalInterval.from_utc(
        START + timedelta(minutes=15),
        START + timedelta(minutes=30),
    )
    with pytest.raises(
        RestorationSettlementValidationError,
        match="coverage|interval|mapping",
    ):
        build_directional_activation_price(
            price_id="wrong-coverage",
            product="AFRR",
            direction="UPWARD",
            mfrr_kind=None,
            interval=uncovered,
            value_state="VALUE",
            price=100.0,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="RTE_AREA_PRICE_PROXY",
            source_or_assumption_ref="RTE",
            source_field="field",
            area_price_proxy_mapping=mapping,
        )


def test_area_price_proxy_cannot_claim_observed_asset_invoice() -> None:
    with pytest.raises(
        RestorationSettlementValidationError,
        match="scenario_proxy|asset_invoice|label",
    ):
        _mapping(output_label="asset_invoice")

    with pytest.raises(
        RestorationSettlementValidationError,
        match="proxy|mapping|required",
    ):
        build_directional_activation_price(
            price_id="unmapped-rte-price",
            product="AFRR",
            direction="UPWARD",
            mfrr_kind=None,
            interval=INTERVAL,
            value_state="VALUE",
            price=100.0,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="RTE_AREA_PRICE_PROXY",
            source_or_assumption_ref="RTE",
            source_field="field",
            area_price_proxy_mapping=None,
        )
