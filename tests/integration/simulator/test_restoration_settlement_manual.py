"""Hand-calculable aFRR and mFRR restoration settlement oracles."""

from __future__ import annotations

import pytest

from open_energy_lab.market.restoration_activation import RestorationDirection
from open_energy_lab.simulator.restoration_service import replay_afrr, replay_mfrr
from open_energy_lab.simulator.restoration_settlement import (
    SettlementAvailability,
    SettlementComponentStatus,
    build_day_ahead_energy_price,
    build_directional_activation_price,
    build_directional_capacity_price,
    build_restoration_penalty_rule,
    build_throughput_degradation_rule,
    settle_restoration_services,
)
from tests.unit.simulator.test_afrr_restoration import _request as _afrr_request
from tests.unit.simulator.test_mfrr_restoration import (
    _event,
    _request as _mfrr_request,
)


def _day_ahead_prices(replay, values: tuple[float, ...]):
    return tuple(
        build_day_ahead_energy_price(
            price_id=f"day-ahead-{index}",
            product=replay.request.core.product,
            interval=sample.interval,
            value_state="VALUE",
            price=value,
            unit="EUR/MWh",
            currency="EUR",
            source_or_assumption_ref="synthetic:A44",
            source_field="day_ahead_price",
        )
        for index, (sample, value) in enumerate(
            zip(replay.samples, values, strict=True)
        )
    )


def _capacity_prices(replay, *, upward: float, downward: float):
    return tuple(
        build_directional_capacity_price(
            price_id=f"capacity-{item.direction.value.lower()}-{index}",
            product=replay.request.core.product,
            direction=item.direction,
            interval=item.interval,
            value_state="VALUE",
            price=(
                upward
                if item.direction is RestorationDirection.UPWARD
                else downward
            ),
            unit="EUR/MW/h",
            currency="EUR",
            eligibility=True,
            source_or_assumption_ref="synthetic:capacity",
            source_field=f"{item.direction.value.lower()}_capacity_price",
        )
        for index, item in enumerate(replay.request.commitments.intervals)
    )


def _settle(
    replay,
    *,
    day_ahead,
    capacity,
    activation,
    penalty=None,
    degradation=None,
):
    return settle_restoration_services(
        settlement_id="manual-restoration-settlement-v1",
        semantics_version="restoration-settlement-v1",
        replay_result=replay,
        day_ahead_prices=day_ahead,
        capacity_prices=capacity,
        activation_prices=activation,
        penalty_rule=penalty,
        degradation_rule=degradation,
        require_day_ahead_prices=True,
        require_capacity_prices=True,
        require_activation_prices=True,
        tolerance=1e-6,
    )


def test_afrr_settlement_reproduces_directional_revenue_penalty_and_degradation() -> None:
    replay = replay_afrr(
        _afrr_request(
            powers=(-30.0, 8.0),
            resolution="PT15M",
            baseline_powers=(2.0, -1.0),
            upward_kw=20.0,
            downward_kw=20.0,
        )
    )
    activation = tuple(
        build_directional_activation_price(
            price_id=f"afrr-activation-{index}",
            product="AFRR",
            direction=("UPWARD" if index == 0 else "DOWNWARD"),
            mfrr_kind=None,
            interval=sample.interval,
            value_state="VALUE",
            price=(100.0 if index == 0 else 50.0),
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="synthetic:activation",
            source_field=f"directional_activation_price_{index}",
            area_price_proxy_mapping=None,
        )
        for index, sample in enumerate(replay.samples)
    )
    penalty = build_restoration_penalty_rule(
        rule_id="afrr-upward-shortfall-v1",
        product="AFRR",
        direction="UPWARD",
        mfrr_kind=None,
        interval=replay.request.integration_grid.period,
        measure="undelivered_activation_energy_kwh",
        rate=2.0,
        rate_unit="EUR/kWh",
        application="sum_eligible_shortfall",
    )
    degradation = build_throughput_degradation_rule(
        rule_id="terminal-throughput-v1",
        cost_per_kwh=0.1,
        unit="EUR/kWh",
        description=(
            "First-order battery-terminal throughput comparison proxy; "
            "not an electrochemical aging model"
        ),
    )

    settlement = _settle(
        replay,
        day_ahead=_day_ahead_prices(replay, (50.0, 60.0)),
        capacity=_capacity_prices(replay, upward=10.0, downward=20.0),
        activation=activation,
        penalty=penalty,
        degradation=degradation,
    )

    assert settlement.availability is SettlementAvailability.AVAILABLE
    assert not hasattr(settlement, "activation_revenue_by_mfrr_kind_eur")
    assert "activation_revenue_by_mfrr_kind_eur" not in settlement.to_dict()
    assert settlement.day_ahead_energy_revenue_eur == pytest.approx(-0.01)
    assert settlement.upward_capacity_revenue_eur == pytest.approx(0.1)
    assert settlement.downward_capacity_revenue_eur == pytest.approx(0.2)
    assert settlement.upward_activation_revenue_eur == pytest.approx(0.5)
    assert settlement.downward_activation_revenue_eur == pytest.approx(0.1)
    assert settlement.non_performance_penalty_eur == pytest.approx(5.0)
    assert settlement.throughput_kwh == pytest.approx(6.25)
    assert settlement.degradation_cost_eur == pytest.approx(0.625)
    assert settlement.gross_revenue_eur == pytest.approx(0.89)
    assert settlement.net_result_eur == pytest.approx(-4.735)
    assert settlement.net_result_eur == pytest.approx(
        settlement.gross_revenue_eur
        - settlement.non_performance_penalty_eur
        - settlement.degradation_cost_eur
    )


def test_mfrr_settlement_keeps_scheduled_direct_and_directions_distinct() -> None:
    events = [
        _event(
            event_id="upward-sa",
            kind="SCHEDULED",
            direction="UPWARD",
            delay_seconds=0.0,
            ramp_up_seconds=0.0,
            hold_seconds=120.0,
            ramp_down_seconds=0.0,
            power_kw=6.0,
        ),
        _event(
            event_id="downward-da",
            kind="DIRECT",
            direction="DOWNWARD",
            start_offset_seconds=240,
            delay_seconds=0.0,
            ramp_up_seconds=0.0,
            hold_seconds=120.0,
            ramp_down_seconds=0.0,
            power_kw=3.0,
        ),
    ]
    replay = replay_mfrr(_mfrr_request(events, count=6))
    activation = tuple(
        build_directional_activation_price(
            price_id=f"mfrr-{event.kind.value.lower()}-{event.direction.value.lower()}",
            product="MFRR",
            direction=event.direction,
            mfrr_kind=event.kind,
            interval=event.complete_interval,
            value_state="VALUE",
            price=(200.0 if event.kind.value == "SCHEDULED" else 300.0),
            unit="EUR/MWh",
            currency="EUR",
            pricing_basis="STUDY_ASSUMPTION",
            source_or_assumption_ref="synthetic:activation",
            source_field=f"{event.kind.value.lower()}_activation_price",
            area_price_proxy_mapping=None,
        )
        for event in replay.request.activation_sequence.events
    )
    degradation = build_throughput_degradation_rule(
        rule_id="terminal-throughput-v1",
        cost_per_kwh=0.1,
        unit="EUR/kWh",
        description=(
            "First-order battery-terminal throughput comparison proxy; "
            "not an electrochemical aging model"
        ),
    )

    settlement = _settle(
        replay,
        day_ahead=_day_ahead_prices(replay, (50.0,) * 6),
        capacity=_capacity_prices(replay, upward=10.0, downward=10.0),
        activation=activation,
        degradation=degradation,
    )

    assert settlement.availability is SettlementAvailability.AVAILABLE
    assert settlement.day_ahead_energy_revenue_eur == 0.0
    assert settlement.upward_capacity_revenue_eur == pytest.approx(0.02)
    assert settlement.downward_capacity_revenue_eur == pytest.approx(0.02)
    assert settlement.upward_activation_revenue_eur == pytest.approx(0.04)
    assert settlement.downward_activation_revenue_eur == pytest.approx(0.03)
    assert settlement.activation_revenue_by_mfrr_kind_eur == pytest.approx(
        {"SCHEDULED": 0.04, "DIRECT": 0.03}
    )
    assert settlement.non_performance_penalty_eur == 0.0
    assert settlement.penalty_status is SettlementComponentStatus.UNCONFIGURED
    assert settlement.throughput_kwh == pytest.approx(0.3)
    assert settlement.degradation_cost_eur == pytest.approx(0.03)
    assert settlement.gross_revenue_eur == pytest.approx(0.11)
    assert settlement.net_result_eur == pytest.approx(0.08)


def test_zero_activation_has_zero_energy_revenue_but_keeps_capacity_eligibility() -> None:
    replay = replay_mfrr(
        _mfrr_request(
            [],
            count=1,
            step_seconds=900,
            baseline_power_kw=0.0,
            upward_kw=5.0,
            downward_kw=5.0,
        )
    )
    settlement = _settle(
        replay,
        day_ahead=_day_ahead_prices(replay, (50.0,)),
        capacity=_capacity_prices(replay, upward=10.0, downward=20.0),
        activation=(),
    )

    assert settlement.availability is SettlementAvailability.AVAILABLE
    assert settlement.upward_activation_revenue_eur == 0.0
    assert settlement.downward_activation_revenue_eur == 0.0
    assert settlement.upward_capacity_revenue_eur == pytest.approx(0.0125)
    assert settlement.downward_capacity_revenue_eur == pytest.approx(0.025)
    assert settlement.non_performance_penalty_eur == 0.0
    assert settlement.degradation_cost_eur == 0.0
    assert settlement.degradation_status is SettlementComponentStatus.UNCONFIGURED
