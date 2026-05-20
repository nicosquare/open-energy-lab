"""Integration trace tests for the battery + load + PV MVP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    BatteryComponent,
    BatteryLoadPVScenario,
    DeterministicRulePolicy,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    TimeGrid,
    WeatherComponent,
)
from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE, POSITIVE_DISPATCH_MEANING


FIXTURE_PATH = Path("tests/fixtures/simulator/battery_load_pv_case.json")


def _load_case() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def _build_common_scenario_parts(case_data: dict[str, object]) -> tuple[
    TimeGrid,
    BatteryComponent,
    LoadComponent,
    WeatherComponent,
    PVComponent,
    PriceSignal,
    ArbitrageObjectiveRepresentation,
]:
    time_grid_data = case_data["time_grid"]
    battery_data = case_data["battery"]
    load_data = case_data["load"]
    weather_data = case_data["weather"]
    pv_data = case_data["pv"]
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
    load = LoadComponent(
        name=load_data.get("name", "load"),
        demand_kw=load_data["demand_kw"],
        interpretation="exogenous-consumption",
        time_grid=grid,
        source="shared-fixture",
    )
    weather = WeatherComponent(
        name=weather_data.get("name", "weather"),
        time_grid=grid,
        timestamp_utc=weather_data["timestamp_utc"]["values"],
        dry_bulb_air_temperature_c=weather_data["dry_bulb_air_temperature_c"]["values"],
        global_horizontal_irradiance_w_per_m2=weather_data["global_horizontal_irradiance_w_per_m2"]["values"],
        deferred_fields=tuple(
            item["field_name"] for item in weather_data.get("deferred_tmy_fields", [])
        ),
    )
    pv = PVComponent(
        name=pv_data.get("name", "pv"),
        rated_power_kw=pv_data["rated_power_kw"],
        temperature_coefficient_pct_per_c=pv_data["temperature_coefficient_pct_per_c"],
        reference_irradiance_w_per_m2=pv_data["reference_irradiance_w_per_m2"],
        reference_temperature_c=pv_data["reference_temperature_c"],
        derivation_name=pv_data["derivation_name"],
        generation_cap_kw=pv_data.get("generation_cap_kw"),
        irradiance_field_names=("global_horizontal_irradiance_w_per_m2",),
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
        objective_name="grid-settlement",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=pricing_data["export_price_ratio"],
    )
    return grid, battery, load, weather, pv, price_signal, objective


def _assert_trace_matches_case(trace: object, case_data: dict[str, object]) -> None:
    expected_trace = case_data["expected_trace"]
    tolerance = case_data["validation"]["numeric_tolerance"]

    assert trace.realized_power_kw == pytest.approx(
        expected_trace["realized_power_kw"],
        abs=tolerance,
    )
    assert trace.pv_generation_kw == pytest.approx(
        expected_trace["pv_generation_kw"],
        abs=tolerance,
    )
    assert trace.net_grid_power_kw == pytest.approx(
        expected_trace["net_grid_power_kw"],
        abs=tolerance,
    )
    assert trace.step_settlement == pytest.approx(
        expected_trace["step_settlement"],
        abs=tolerance,
    )
    assert trace.total_settlement == pytest.approx(
        expected_trace["total_settlement"],
        abs=tolerance,
    )


def test_explicit_dispatch_trace_matches_shared_fixture_expectations() -> None:
    fixture = _load_case()
    dispatch_case = fixture["dispatch_case"]
    grid, battery, load, weather, pv, price_signal, objective = _build_common_scenario_parts(
        fixture
    )
    scenario = BatteryLoadPVScenario(
        scenario_id=fixture["case_id"],
        time_grid=grid,
        battery=battery,
        load=load,
        weather=weather,
        pv=pv,
        price_signal=price_signal,
        objective=objective,
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=dispatch_case["dispatch_requests_kw"],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="shared-fixture",
        ),
    )

    trace = scenario.evaluate_trace()

    _assert_trace_matches_case(trace, dispatch_case)


def test_price_threshold_trace_matches_shared_fixture_expectations() -> None:
    fixture = _load_case()
    policy_case = fixture["policy_case"]
    grid, battery, load, weather, pv, price_signal, objective = _build_common_scenario_parts(
        fixture
    )
    scenario = BatteryLoadPVScenario(
        scenario_id=f"{fixture['case_id']}-policy",
        time_grid=grid,
        battery=battery,
        load=load,
        weather=weather,
        pv=pv,
        price_signal=price_signal,
        objective=objective,
        rule_policy=DeterministicRulePolicy(
            policy_name=policy_case["policy_name"],
            price_threshold=policy_case["price_threshold"],
            below_threshold_action=policy_case["below_threshold_action"],
            above_threshold_action=policy_case["above_threshold_action"],
            at_threshold_action=policy_case["at_threshold_action"],
        ),
    )

    trace = scenario.evaluate_trace()

    _assert_trace_matches_case(trace, policy_case)
    second_trace = scenario.evaluate_trace()

    assert second_trace.net_grid_power_kw == pytest.approx(
        trace.net_grid_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
