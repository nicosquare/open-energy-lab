"""Scenario assembly tests for the battery + load + weather + PV MVP."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator._graph import ComponentGraph, Relation
from open_energy_lab.simulator._units import POSITIVE_DISPATCH_MEANING
from open_energy_lab.simulator.load import LoadComponent
from open_energy_lab.simulator.pricing import (
    ArbitrageObjectiveRepresentation,
    DeterministicRulePolicy,
    PriceSignal,
)
from open_energy_lab.simulator.pv import PVComponent
from open_energy_lab.simulator.scenario import (
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    TimeGrid,
)
from open_energy_lab.simulator.weather import WeatherComponent


def _battery() -> BatteryComponent:
    return BatteryComponent(
        name="battery",
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=0.5,
    )


def _objective() -> ArbitrageObjectiveRepresentation:
    return ArbitrageObjectiveRepresentation(
        objective_name="grid-settlement",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=0.8,
    )


def _price_signal(grid: TimeGrid) -> PriceSignal:
    return PriceSignal(
        currency="USD",
        unit_rate_name="energy-price",
        import_prices=[0.10, 0.20, 0.30],
        export_price_ratio=0.8,
        interpretation="discounted export relative to import prices",
        time_alignment="step-start",
        time_grid=grid,
    )


def _load(grid: TimeGrid) -> LoadComponent:
    return LoadComponent(
        name="load",
        demand_kw=[2.0, 1.5, 0.5],
        interpretation="exogenous-consumption",
        time_grid=grid,
        source="synthetic-fixture",
    )


def _weather(grid: TimeGrid) -> WeatherComponent:
    return WeatherComponent(
        name="weather",
        time_grid=grid,
        timestamp_utc=[
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T02:00:00Z",
        ],
        dry_bulb_air_temperature_c=[25.0, 26.0, 27.0],
        global_horizontal_irradiance_w_per_m2=[0.0, 300.0, 800.0],
    )


def _pv() -> PVComponent:
    return PVComponent(
        name="pv",
        rated_power_kw=4.0,
        temperature_coefficient_pct_per_c=-0.4,
        reference_irradiance_w_per_m2=1000.0,
        reference_temperature_c=25.0,
        derivation_name="ghi-linear",
        irradiance_field_names=("global_horizontal_irradiance_w_per_m2",),
    )


def test_multi_component_scenario_rejects_misaligned_load_or_weather_inputs() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    wrong_grid = TimeGrid(num_steps=2, time_step_hours=1.0)
    misaligned_load = LoadComponent(
        name="load",
        demand_kw=[2.0, 1.5],
        interpretation="exogenous-consumption",
        time_grid=wrong_grid,
        source="synthetic-fixture",
    )

    scenario = BatteryLoadPVScenario(
        scenario_id="invalid-alignment",
        time_grid=grid,
        battery=_battery(),
        load=misaligned_load,
        weather=_weather(grid),
        pv=_pv(),
        price_signal=_price_signal(grid),
        objective=_objective(),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=[1.0, 0.0, -1.0],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="test",
        ),
    )

    with pytest.raises(ValueError, match="load component must align to the scenario time grid"):
        scenario.validate()


def test_multi_component_scenario_rejects_both_or_neither_control_inputs() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    with pytest.raises(ValueError, match="exactly one of dispatch_requests or rule_policy"):
        BatteryLoadPVScenario(
            scenario_id="invalid-both",
            time_grid=grid,
            battery=_battery(),
            load=_load(grid),
            weather=_weather(grid),
            pv=_pv(),
            price_signal=_price_signal(grid),
            objective=_objective(),
            dispatch_requests=DispatchRequestSeries(
                requested_power_kw=[1.0, 0.0, -1.0],
                sign_convention=POSITIVE_DISPATCH_MEANING,
                source="test",
            ),
            rule_policy=DeterministicRulePolicy(
                policy_name="price_threshold",
                price_threshold=0.2,
                below_threshold_action="charge",
                above_threshold_action="discharge",
                at_threshold_action="hold",
            ),
        ).validate()

    with pytest.raises(ValueError, match="exactly one of dispatch_requests or rule_policy"):
        BatteryLoadPVScenario(
            scenario_id="invalid-neither",
            time_grid=grid,
            battery=_battery(),
            load=_load(grid),
            weather=_weather(grid),
            pv=_pv(),
            price_signal=_price_signal(grid),
            objective=_objective(),
        ).validate()


def test_valid_dispatch_scenario_builds_expected_multi_component_graph() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    scenario = BatteryLoadPVScenario(
        scenario_id="dispatch-scenario",
        time_grid=grid,
        battery=_battery(),
        load=_load(grid),
        weather=_weather(grid),
        pv=_pv(),
        price_signal=_price_signal(grid),
        objective=_objective(),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=[1.0, 0.0, -1.0],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="test",
        ),
    )

    graph = scenario.validate()

    assert isinstance(graph, ComponentGraph)
    assert graph.has_connection("time_grid", "load", Relation.ALIGNS)
    assert graph.has_connection("time_grid", "weather", Relation.ALIGNS)
    assert graph.has_connection("weather", "pv", Relation.DERIVES)
    assert graph.has_connection("load", "net_grid_trace", Relation.FEEDS)
    assert graph.has_connection("pv", "net_grid_trace", Relation.FEEDS)
    assert graph.has_connection("simulation_trace", "net_grid_trace", Relation.FEEDS)
    assert graph.has_connection("price_signal", "net_grid_trace", Relation.PRICES)
    assert graph.has_connection("net_grid_trace", "objective", Relation.SETTLES)
    assert graph.has_connection("dispatch_requests", "battery", Relation.REQUESTS)


def test_valid_policy_scenario_builds_policy_path_graph() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    scenario = BatteryLoadPVScenario(
        scenario_id="policy-scenario",
        time_grid=grid,
        battery=_battery(),
        load=_load(grid),
        weather=_weather(grid),
        pv=_pv(),
        price_signal=_price_signal(grid),
        objective=_objective(),
        rule_policy=DeterministicRulePolicy(
            policy_name="price_threshold",
            price_threshold=0.2,
            below_threshold_action="charge",
            above_threshold_action="discharge",
            at_threshold_action="hold",
        ),
    )

    graph = scenario.validate()

    assert graph.has_connection("time_grid", "rule_policy", Relation.ALIGNS)
    assert graph.has_connection("price_signal", "rule_policy", Relation.DRIVES)
    assert graph.has_connection("rule_policy", "battery", Relation.REQUESTS)
