"""Atomic restoration-settlement availability and diagnostic tests."""

from __future__ import annotations

from datetime import timedelta
import re

import pytest

from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.restoration_service import replay_mfrr
from open_energy_lab.simulator.restoration_settlement import (
    SettlementAvailability,
    build_day_ahead_energy_price,
    build_directional_activation_price,
    build_directional_capacity_price,
    settle_restoration_services,
)
from tests.unit.simulator.test_mfrr_restoration import _request


def _valid_inputs():
    replay = replay_mfrr(_request())
    day_ahead = tuple(
        build_day_ahead_energy_price(
            price_id=f"day-ahead-{index}",
            product="MFRR",
            interval=sample.interval,
            value_state="VALUE",
            price=50.0,
            unit="EUR/MWh",
            currency="EUR",
            source_or_assumption_ref="synthetic:A44",
            source_field="day_ahead_price",
        )
        for index, sample in enumerate(replay.samples)
    )
    capacity = tuple(
        build_directional_capacity_price(
            price_id=f"capacity-{item.direction.value.lower()}-{index}",
            product="MFRR",
            direction=item.direction,
            interval=item.interval,
            value_state="VALUE",
            price=10.0,
            unit="EUR/MW/h",
            currency="EUR",
            eligibility=True,
            source_or_assumption_ref="synthetic:capacity",
            source_field=f"{item.direction.value.lower()}_capacity_price",
        )
        for index, item in enumerate(replay.request.commitments.intervals)
    )
    event = replay.request.activation_sequence.events[0]
    activation = (
        build_directional_activation_price(
            price_id="activation-downward-da",
            product="MFRR",
            direction="DOWNWARD",
            mfrr_kind="DIRECT",
            interval=event.complete_interval,
            value_state="VALUE",
            price=64.83,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="synthetic:activation",
            source_field="direct_settlement_price",
            area_price_proxy_mapping=None,
        ),
    )
    return replay, day_ahead, capacity, activation


def _settle(
    *,
    replay,
    day_ahead,
    capacity,
    activation,
):
    return settle_restoration_services(
        settlement_id="availability-test-v1",
        semantics_version="restoration-settlement-v1",
        replay_result=replay,
        day_ahead_prices=day_ahead,
        capacity_prices=capacity,
        activation_prices=activation,
        penalty_rule=None,
        degradation_rule=None,
        require_day_ahead_prices=True,
        require_capacity_prices=True,
        require_activation_prices=True,
        tolerance=1e-6,
    )


def test_complete_compatible_inputs_make_whole_settlement_available() -> None:
    replay, day_ahead, capacity, activation = _valid_inputs()

    settlement = _settle(
        replay=replay,
        day_ahead=day_ahead,
        capacity=capacity,
        activation=activation,
    )

    assert settlement.availability is SettlementAvailability.AVAILABLE
    assert settlement.unavailable_reasons == ()
    assert settlement.gross_revenue_eur is not None
    assert settlement.net_result_eur is not None
    assert settlement.physical_result_fingerprint == replay.result_fingerprint


def _missing_capacity(inputs):
    replay, day_ahead, capacity, activation = inputs
    return replay, day_ahead, capacity[1:], activation


def _null_activation(inputs):
    replay, day_ahead, capacity, _ = inputs
    event = replay.request.activation_sequence.events[0]
    activation = (
        build_directional_activation_price(
            price_id="activation-null",
            product="MFRR",
            direction="DOWNWARD",
            mfrr_kind="DIRECT",
            interval=event.complete_interval,
            value_state="SOURCE_NULL",
            price=None,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="RTE:mari",
            source_field="settlement_price_current",
            area_price_proxy_mapping=None,
        ),
    )
    return replay, day_ahead, capacity, activation


def _ambiguous_day_ahead(inputs):
    replay, day_ahead, capacity, activation = inputs
    return replay, (*day_ahead, day_ahead[0]), capacity, activation


def _wrong_product(inputs):
    replay, day_ahead, capacity, _ = inputs
    event = replay.request.activation_sequence.events[0]
    activation = (
        build_directional_activation_price(
            price_id="wrong-product",
            product="AFRR",
            direction="DOWNWARD",
            mfrr_kind=None,
            interval=event.complete_interval,
            value_state="VALUE",
            price=50.0,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="synthetic",
            source_field="wrong_product_price",
            area_price_proxy_mapping=None,
        ),
    )
    return replay, day_ahead, capacity, activation


def _wrong_direction(inputs):
    replay, day_ahead, capacity, _ = inputs
    event = replay.request.activation_sequence.events[0]
    activation = (
        build_directional_activation_price(
            price_id="wrong-direction",
            product="MFRR",
            direction="UPWARD",
            mfrr_kind="DIRECT",
            interval=event.complete_interval,
            value_state="VALUE",
            price=50.0,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="synthetic",
            source_field="wrong_direction_price",
            area_price_proxy_mapping=None,
        ),
    )
    return replay, day_ahead, capacity, activation


def _wrong_unit(inputs):
    replay, day_ahead, capacity, _ = inputs
    event = replay.request.activation_sequence.events[0]
    activation = (
        build_directional_activation_price(
            price_id="wrong-unit",
            product="MFRR",
            direction="DOWNWARD",
            mfrr_kind="DIRECT",
            interval=event.complete_interval,
            value_state="VALUE",
            price=50.0,
            unit="EUR/kWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="synthetic",
            source_field="wrong_unit_price",
            area_price_proxy_mapping=None,
        ),
    )
    return replay, day_ahead, capacity, activation


def _uncovered(inputs):
    replay, day_ahead, capacity, _ = inputs
    event = replay.request.activation_sequence.events[0]
    short_interval = CanonicalInterval.from_utc(
        event.complete_interval.start_utc,
        event.complete_interval.start_utc + timedelta(minutes=1),
    )
    activation = (
        build_directional_activation_price(
            price_id="uncovered",
            product="MFRR",
            direction="DOWNWARD",
            mfrr_kind="DIRECT",
            interval=short_interval,
            value_state="VALUE",
            price=50.0,
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="synthetic",
            source_field="uncovered_price",
            area_price_proxy_mapping=None,
        ),
    )
    return replay, day_ahead, capacity, activation


@pytest.mark.parametrize(
    "mutation,expected_text",
    (
        (_missing_capacity, "missing|capacity|coverage"),
        (_null_activation, "null|SOURCE_NULL|activation"),
        (_ambiguous_day_ahead, "ambiguous|multiple|day-ahead"),
        (_wrong_product, "product|MFRR"),
        (_wrong_direction, "direction|DOWNWARD"),
        (_wrong_unit, "unit|EUR/MWh"),
        (_uncovered, "coverage|period|interval"),
    ),
)
def test_any_required_price_failure_makes_the_entire_total_unavailable(
    mutation,
    expected_text: str,
) -> None:
    replay, day_ahead, capacity, activation = mutation(_valid_inputs())

    settlement = _settle(
        replay=replay,
        day_ahead=day_ahead,
        capacity=capacity,
        activation=activation,
    )

    assert settlement.availability is SettlementAvailability.UNAVAILABLE
    assert settlement.physical_result_fingerprint == replay.result_fingerprint
    assert settlement.unavailable_reasons
    messages = " ".join(item.public_message for item in settlement.unavailable_reasons)
    assert re.search(expected_text, messages, flags=re.IGNORECASE)
    for field_name in (
        "day_ahead_energy_revenue_eur",
        "upward_capacity_revenue_eur",
        "downward_capacity_revenue_eur",
        "upward_activation_revenue_eur",
        "downward_activation_revenue_eur",
        "non_performance_penalty_eur",
        "degradation_cost_eur",
        "gross_revenue_eur",
        "net_result_eur",
    ):
        assert getattr(settlement, field_name) is None
