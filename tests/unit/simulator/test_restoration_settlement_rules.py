"""Immutable restoration price, penalty, and degradation rule contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.restoration_settlement import (
    SettlementComponentStatus,
    SettlementPriceState,
    RestorationSettlementValidationError,
    build_day_ahead_energy_price,
    build_directional_activation_price,
    build_directional_capacity_price,
    build_restoration_penalty_rule,
    build_throughput_degradation_rule,
)


START = datetime(2026, 1, 1, tzinfo=UTC)
INTERVAL = CanonicalInterval.from_utc(START, START + timedelta(minutes=15))


def test_directional_capacity_price_preserves_identity_eligibility_and_fingerprint() -> None:
    price = build_directional_capacity_price(
        price_id="afrr-up-capacity-q1",
        product="AFRR",
        direction="UPWARD",
        interval=INTERVAL,
        value_state="VALUE",
        price=12.5,
        unit="EUR/MW/h",
        currency="EUR",
        eligibility=True,
        source_or_assumption_ref="study:capacity-price",
        source_field="assumed_upward_capacity_price",
    )

    assert price.product.value == "AFRR"
    assert price.direction.value == "UPWARD"
    assert price.value_state is SettlementPriceState.VALUE
    assert price.price == 12.5
    assert price.eligibility is True
    with pytest.raises(FrozenInstanceError):
        price.price = 10.0  # type: ignore[misc]


def test_activation_price_retains_product_direction_kind_unit_and_basis() -> None:
    price = build_directional_activation_price(
        price_id="mfrr-da-down-q1",
        product="MFRR",
        direction="DOWNWARD",
        mfrr_kind="DIRECT",
        interval=INTERVAL,
        value_state="VALUE",
        price=64.83,
        unit="EUR/MWh",
        currency="EUR",
        pricing_basis="STUDY_ASSUMPTION",
        source_or_assumption_ref="study:activation-price",
        source_field="assumed_da_settlement_price",
        area_price_proxy_mapping=None,
    )

    assert price.product.value == "MFRR"
    assert price.direction.value == "DOWNWARD"
    assert price.mfrr_kind is not None
    assert price.mfrr_kind.value == "DIRECT"
    assert price.unit == "EUR/MWh"
    assert price.pricing_basis == "STUDY_ASSUMPTION"


@pytest.mark.parametrize(
    "builder,kwargs",
    (
        (
            build_directional_capacity_price,
            {
                "price_id": "bad-capacity",
                "product": "AFRR",
                "direction": "UPWARD",
                "interval": INTERVAL,
                "value_state": "SOURCE_NULL",
                "price": 0.0,
                "unit": "EUR/MW/h",
                "currency": "EUR",
                "eligibility": True,
                "source_or_assumption_ref": "source",
                "source_field": "field",
            },
        ),
        (
            build_directional_activation_price,
            {
                "price_id": "bad-activation",
                "product": "AFRR",
                "direction": "DOWNWARD",
                "mfrr_kind": "DIRECT",
                "interval": INTERVAL,
                "value_state": "VALUE",
                "price": 10.0,
                "unit": "EUR/MWh",
                "currency": "EUR",
                "pricing_basis": "STUDY_ASSUMPTION",
                "source_or_assumption_ref": "source",
                "source_field": "field",
                "area_price_proxy_mapping": None,
            },
        ),
    ),
)
def test_price_contracts_reject_state_value_and_product_kind_conflicts(
    builder,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        RestorationSettlementValidationError,
        match="state|price|kind|AFRR|MFRR",
    ):
        builder(**kwargs)


def test_day_ahead_price_is_product_bound_and_coverage_explicit() -> None:
    price = build_day_ahead_energy_price(
        price_id="day-ahead-q1",
        product="AFRR",
        interval=INTERVAL,
        value_state="VALUE",
        price=50.0,
        unit="EUR/MWh",
        currency="EUR",
        source_or_assumption_ref="synthetic:A44",
        source_field="day_ahead_price",
    )

    assert price.interval == INTERVAL
    assert price.product.value == "AFRR"
    assert price.price == 50.0


def test_penalty_and_degradation_rules_are_explicit_finite_and_fingerprinted() -> None:
    penalty = build_restoration_penalty_rule(
        rule_id="afrr-shortfall-v1",
        product="AFRR",
        direction="UPWARD",
        mfrr_kind=None,
        interval=INTERVAL,
        measure="undelivered_activation_energy_kwh",
        rate=2.0,
        rate_unit="EUR/kWh",
        application="sum_eligible_shortfall",
    )
    degradation = build_throughput_degradation_rule(
        rule_id="terminal-throughput-proxy-v1",
        cost_per_kwh=0.08,
        unit="EUR/kWh",
        description=(
            "First-order battery-terminal throughput comparison proxy; "
            "not an electrochemical aging model"
        ),
    )

    assert penalty.rate == 2.0
    assert degradation.cost_per_kwh == 0.08
    assert SettlementComponentStatus.UNCONFIGURED.value == "UNCONFIGURED"

    with pytest.raises(RestorationSettlementValidationError, match="non-negative"):
        build_throughput_degradation_rule(
            rule_id="invalid",
            cost_per_kwh=-1.0,
            unit="EUR/kWh",
            description="comparison proxy; not an electrochemical aging model",
        )
    with pytest.raises(RestorationSettlementValidationError, match="proxy|aging"):
        build_throughput_degradation_rule(
            rule_id="invalid-description",
            cost_per_kwh=1.0,
            unit="EUR/kWh",
            description="battery degradation",
        )
