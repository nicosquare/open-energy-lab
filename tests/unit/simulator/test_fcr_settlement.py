"""Contracts for day-ahead and symmetric-FCR stacked-service settlement."""

from __future__ import annotations

from datetime import timedelta
import importlib
import math
from types import ModuleType
from typing import Any

import pytest

from tests.unit.market.test_artifact import PERIOD_END, PERIOD_START
from tests.unit.simulator.test_stacked_service import (
    _activation_trace,
    _battery,
    _energy_schedule,
    _fcr_schedule,
    _replay_request,
    _require as _require_stacked,
)


def _settlement_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.simulator.fcr_settlement")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.simulator.fcr_settlement is not implemented; "
            "T030 must provide stacked-service settlement",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    module = _settlement_module()
    try:
        return getattr(module, name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.simulator.fcr_settlement.{name} is not implemented",
            pytrace=False,
        )


def _penalty_rule(rate: float = 2.0):
    rule_type = _require("FCRPenaltyRule")
    return rule_type(
        rule_id="absolute-non-delivery-v1",
        measure="absolute_fcr_non_delivery_energy_kwh",
        rate=rate,
        rate_unit="EUR/kWh",
        application="sum per activation interval",
    )


def _physical_result(
    *,
    energy_powers: list[float] | None = None,
    fcr_capacities: list[float] | None = None,
    penalty_rule: object | None = None,
    battery: object | None = None,
    activation_values: list[float] | None = None,
):
    _settlement_module()
    replay = _require_stacked("replay_stacked_services")
    trace = (
        None
        if activation_values is None
        else _activation_trace(activation_values)
    )
    request = _replay_request(
        battery=battery,
        activation_trace=trace,
        energy_schedule=(
            None if energy_powers is None else _energy_schedule(energy_powers)
        ),
        fcr_schedule=(
            None if fcr_capacities is None else _fcr_schedule(fcr_capacities)
        ),
        penalty_rule=penalty_rule,
    )
    return request, replay(request)


def _settle(request: object, physical_result: object):
    settle = _require("settle_stacked_services")
    return settle(request, physical_result.samples)


def test_day_ahead_revenue_uses_accepted_schedule_not_realized_delivery() -> None:
    powers = [1.0, -1.0, 0.0, 0.0, 2.0, -2.0, 0.0, 0.0]
    request, physical = _physical_result(energy_powers=powers)

    settlement = _settle(request, physical)

    prices = [50.0, -5.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0]
    expected_components = [
        -(power * 1.0) * price / 1000.0
        for power, price in zip(powers, prices, strict=True)
    ]
    assert [item.revenue_eur for item in settlement.energy_intervals] == pytest.approx(
        expected_components
    )
    assert settlement.day_ahead_energy_revenue_eur == pytest.approx(
        sum(expected_components)
    )


def test_soc_limited_delivery_does_not_change_schedule_based_energy_revenue() -> None:
    powers = [10.0] * 8
    healthy_request, healthy_physical = _physical_result(
        energy_powers=powers,
        fcr_capacities=[0.0, 0.0],
        battery=_battery(capacity_kwh=1_000.0, initial_soc=0.5),
    )
    limited_request, limited_physical = _physical_result(
        energy_powers=powers,
        fcr_capacities=[0.0, 0.0],
        battery=_battery(capacity_kwh=10.0, initial_soc=0.9, max_soc=0.9),
    )

    healthy = _settle(healthy_request, healthy_physical)
    limited = _settle(limited_request, limited_physical)

    assert limited_physical.samples[0].delivered_combined_power_kw == 0.0
    assert healthy.day_ahead_energy_revenue_eur == limited.day_ahead_energy_revenue_eur


def test_fcr_capacity_revenue_uses_aligned_four_hour_blocks() -> None:
    request, physical = _physical_result(fcr_capacities=[5.0, 10.0])

    settlement = _settle(request, physical)

    expected = [5.0 / 1000.0 * 20.0 * 4.0, 10.0 / 1000.0 * 21.0 * 4.0]
    assert [item.revenue_eur for item in settlement.fcr_blocks] == pytest.approx(expected)
    assert settlement.fcr_capacity_revenue_eur == pytest.approx(sum(expected))
    assert [item.duration_hours for item in settlement.fcr_blocks] == [4.0, 4.0]


def test_absent_penalty_rule_means_exactly_zero_penalty() -> None:
    count = int((PERIOD_END - PERIOD_START) / timedelta(minutes=15))
    request, physical = _physical_result(
        battery=_battery(capacity_kwh=10.0, initial_soc=0.1),
        activation_values=[1.0] * count,
    )

    settlement = _settle(request, physical)

    assert sum(sample.non_delivery_energy_kwh for sample in physical.samples) > 0.0
    assert settlement.penalty_rule_id is None
    assert settlement.penalty_eur == 0.0


def test_explicit_eur_per_kwh_penalty_sums_interval_non_delivery() -> None:
    count = int((PERIOD_END - PERIOD_START) / timedelta(minutes=15))
    rule = _penalty_rule(rate=2.0)
    request, physical = _physical_result(
        penalty_rule=rule,
        battery=_battery(capacity_kwh=10.0, initial_soc=0.1),
        activation_values=[1.0] * count,
    )

    settlement = _settle(request, physical)

    non_delivery = sum(sample.non_delivery_energy_kwh for sample in physical.samples)
    assert settlement.non_delivery_energy_kwh == pytest.approx(non_delivery)
    assert settlement.penalty_rule_id == rule.rule_id
    assert settlement.penalty_eur == pytest.approx(non_delivery * 2.0)


def test_zero_fcr_baseline_error_never_creates_an_fcr_penalty() -> None:
    rule = _penalty_rule(rate=100.0)
    request, physical = _physical_result(
        energy_powers=[10.0] * 8,
        fcr_capacities=[0.0, 0.0],
        penalty_rule=rule,
        battery=_battery(capacity_kwh=10.0, initial_soc=0.9, max_soc=0.9),
    )

    settlement = _settle(request, physical)

    assert sum(abs(sample.baseline_delivery_error_kw) for sample in physical.samples) > 0.0
    assert all(sample.non_delivery_energy_kwh == 0.0 for sample in physical.samples)
    assert settlement.penalty_eur == 0.0


def test_throughput_is_battery_terminal_charge_plus_discharge_energy() -> None:
    request, physical = _physical_result()

    settlement = _settle(request, physical)

    charge = sum(sample.charge_energy_kwh for sample in physical.samples)
    discharge = sum(sample.discharge_energy_kwh for sample in physical.samples)
    assert settlement.charge_energy_kwh == pytest.approx(charge)
    assert settlement.discharge_energy_kwh == pytest.approx(discharge)
    assert settlement.throughput_kwh == pytest.approx(charge + discharge)
    assert settlement.throughput_kwh == pytest.approx(physical.throughput_kwh)


def test_out_of_scope_settlement_components_are_explicitly_not_modeled() -> None:
    request, physical = _physical_result()

    settlement = _settle(request, physical)

    assert settlement.activation_energy_settlement_status == "not_modeled"
    assert settlement.imbalance_settlement_status == "not_modeled"
    assert settlement.degradation_cost_status == "not_modeled"


def test_total_profit_reconciles_exactly_from_documented_components() -> None:
    count = int((PERIOD_END - PERIOD_START) / timedelta(minutes=15))
    request, physical = _physical_result(
        energy_powers=[1.0, -1.0, 0.0, 0.0, 2.0, -2.0, 0.0, 0.0],
        penalty_rule=_penalty_rule(rate=0.25),
        battery=_battery(capacity_kwh=10.0, initial_soc=0.1),
        activation_values=[1.0] * count,
    )

    settlement = _settle(request, physical)

    assert settlement.total_profit_eur == pytest.approx(
        settlement.day_ahead_energy_revenue_eur
        + settlement.fcr_capacity_revenue_eur
        - settlement.penalty_eur,
        abs=1e-12,
    )
    assert sum(item.revenue_eur for item in settlement.energy_intervals) == pytest.approx(
        settlement.day_ahead_energy_revenue_eur,
        abs=1e-12,
    )
    assert sum(item.revenue_eur for item in settlement.fcr_blocks) == pytest.approx(
        settlement.fcr_capacity_revenue_eur,
        abs=1e-12,
    )


@pytest.mark.parametrize(
    ("rate", "measure", "unit"),
    [
        (-1.0, "absolute_fcr_non_delivery_energy_kwh", "EUR/kWh"),
        (math.nan, "absolute_fcr_non_delivery_energy_kwh", "EUR/kWh"),
        (1.0, "signed_tracking_error", "EUR/kWh"),
        (1.0, "absolute_fcr_non_delivery_energy_kwh", "EUR/MWh"),
    ],
)
def test_penalty_rule_rejects_implicit_or_incompatible_semantics(
    rate: float,
    measure: str,
    unit: str,
) -> None:
    validation_error = _require("FCRSettlementValidationError")
    rule_type = _require("FCRPenaltyRule")

    with pytest.raises(validation_error, match="rate|measure|unit|penalty"):
        rule_type(
            rule_id="invalid-rule",
            measure=measure,
            rate=rate,
            rate_unit=unit,
            application="sum per activation interval",
        )


def test_zero_energy_schedule_has_exactly_zero_day_ahead_revenue() -> None:
    request, physical = _physical_result(energy_powers=[0.0] * 8)

    settlement = _settle(request, physical)

    assert settlement.day_ahead_energy_revenue_eur == 0.0
    assert all(item.revenue_eur == 0.0 for item in settlement.energy_intervals)
