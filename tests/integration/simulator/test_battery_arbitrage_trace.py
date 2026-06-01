"""Integration trace tests for the battery arbitrage MVP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    ArbitrageScenario,
    BatteryComponent,
    DeterministicRulePolicy,
    DispatchRequestSeries,
    PriceSignal,
    TimeGrid,
)
from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE, POSITIVE_DISPATCH_MEANING


FIXTURE_PATH = Path("tests/fixtures/simulator/battery_arbitrage_case.json")


def _load_case() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def _build_common_scenario_parts(case_data: dict[str, object]) -> tuple[
    TimeGrid,
    BatteryComponent,
    PriceSignal,
    ArbitrageObjectiveRepresentation,
]:
    time_grid_data = case_data["time_grid"]
    battery_data = case_data["battery"]
    pricing_data = case_data["pricing"]

    grid = TimeGrid(
        num_steps=time_grid_data["num_steps"],
        time_step_hours=time_grid_data["time_step_hours"],
    )
    battery = BatteryComponent(
        name=battery_data.get("name", "battery"),
        capacity_kwh=battery_data["capacity_kwh"],
        max_charge_kw=battery_data["max_charge_kw"],
        max_discharge_kw=battery_data["max_discharge_kw"],
        charge_efficiency=battery_data["charge_efficiency"],
        discharge_efficiency=battery_data["discharge_efficiency"],
        initial_soc=battery_data["initial_soc"],
        min_soc=battery_data.get("min_soc", 0.0),
        max_soc=battery_data.get("max_soc", 1.0),
    )
    price_signal = PriceSignal(
        currency=pricing_data.get("currency", "USD"),
        unit_rate_name=pricing_data.get("unit_rate_name", "energy-price"),
        import_prices=pricing_data["import_prices"],
        export_price_ratio=pricing_data["export_price_ratio"],
        interpretation=pricing_data.get(
            "interpretation",
            "discounted export relative to import prices",
        ),
        time_alignment=pricing_data.get("time_alignment", "step-start"),
        time_grid=grid,
    )
    objective = ArbitrageObjectiveRepresentation(
        objective_name=case_data.get("objective_name", "arbitrage"),
        settlement_basis=case_data.get("settlement_basis", "grid-settlement"),
        allow_export=True,
        export_price_ratio=pricing_data["export_price_ratio"],
    )
    return grid, battery, price_signal, objective


def _assert_trace_matches_case(trace: object, case_data: dict[str, object]) -> None:
    tolerance = case_data["validation"]["numeric_tolerance"]
    assert trace.realized_power_kw == pytest.approx(
        case_data["expected_realized_power_kw"],
        abs=tolerance,
    )
    assert [state.soc for state in trace.states] == pytest.approx(
        case_data["expected_soc"],
        abs=tolerance,
    )
    assert trace.step_settlement == pytest.approx(
        case_data["expected_step_settlement"],
        abs=tolerance,
    )
    assert trace.total_settlement == pytest.approx(
        case_data["expected_total_settlement"],
        abs=tolerance,
    )
    assert trace.total_settlement == pytest.approx(
        sum(trace.step_settlement),
        abs=tolerance,
    )
    assert trace.constraint_events == []


def test_explicit_dispatch_trace_matches_shared_fixture_expectations() -> None:
    fixture = _load_case()
    dispatch_case = fixture["dispatch_case"]
    grid, battery, price_signal, objective = _build_common_scenario_parts(fixture)
    scenario = ArbitrageScenario(
        scenario_id=fixture["case_id"],
        time_grid=grid,
        battery=battery,
        price_signal=price_signal,
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=dispatch_case["dispatch_requests_kw"],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="shared-fixture",
        ),
        objective=objective,
    )

    trace = scenario.evaluate_trace()
    second_trace = scenario.evaluate_trace()

    _assert_trace_matches_case(trace, dispatch_case)
    assert trace.requested_power_kw == pytest.approx(
        dispatch_case["dispatch_requests_kw"],
        abs=dispatch_case["validation"]["numeric_tolerance"],
    )
    assert second_trace.requested_power_kw == pytest.approx(
        trace.requested_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert second_trace.realized_power_kw == pytest.approx(
        trace.realized_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert second_trace.total_settlement == pytest.approx(
        trace.total_settlement,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_price_threshold_trace_matches_shared_fixture_expectations() -> None:
    fixture = _load_case()
    policy_case = fixture["policy_case"]
    grid, battery, price_signal, objective = _build_common_scenario_parts(fixture)
    scenario = ArbitrageScenario(
        scenario_id=f"{fixture['case_id']}-policy",
        time_grid=grid,
        battery=battery,
        price_signal=price_signal,
        dispatch_requests=None,
        rule_policy=DeterministicRulePolicy(
            policy_name=policy_case["policy_name"],
            price_threshold=policy_case["price_threshold"],
            below_threshold_action=policy_case["below_threshold_action"],
            above_threshold_action=policy_case["above_threshold_action"],
            at_threshold_action=policy_case["at_threshold_action"],
        ),
        objective=objective,
    )

    trace = scenario.evaluate_trace()

    _assert_trace_matches_case(trace, policy_case)
    assert trace.requested_power_kw == pytest.approx(
        [battery.max_charge_kw, 0.0, -battery.max_discharge_kw],
        abs=policy_case["validation"]["numeric_tolerance"],
    )
    second_trace = scenario.evaluate_trace()

    assert second_trace.realized_power_kw == pytest.approx(
        trace.realized_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert second_trace.requested_power_kw == pytest.approx(
        trace.requested_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
