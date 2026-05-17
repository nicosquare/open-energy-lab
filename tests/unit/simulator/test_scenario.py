"""Scenario assembly tests for the battery arbitrage MVP."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator._graph import ComponentGraph
from open_energy_lab.simulator._units import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    POSITIVE_DISPATCH_MEANING,
)
from open_energy_lab.simulator.pricing import (
    ArbitrageObjectiveRepresentation,
    DeterministicRulePolicy,
    PriceSignal,
)
from open_energy_lab.simulator.scenario import (
    ArbitrageScenario,
    BatteryComponent,
    DispatchRequestSeries,
    TimeGrid,
)


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
        objective_name="arbitrage",
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


def test_time_grid_requires_positive_timestep_hours() -> None:
    with pytest.raises(ValueError, match="time_step_hours must be positive"):
        TimeGrid(num_steps=3, time_step_hours=0.0)


def test_time_grid_requires_positive_step_count() -> None:
    with pytest.raises(ValueError, match="num_steps must be positive"):
        TimeGrid(num_steps=0, time_step_hours=1.0)


def test_scenario_rejects_both_dispatch_requests_and_rule_policy() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    scenario = ArbitrageScenario(
        scenario_id="invalid-double-control",
        time_grid=grid,
        battery=_battery(),
        price_signal=_price_signal(grid),
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
        objective=_objective(),
    )

    with pytest.raises(
        ValueError,
        match="exactly one of dispatch_requests or rule_policy",
    ):
        scenario.validate()


def test_scenario_requires_either_dispatch_requests_or_rule_policy() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    scenario = ArbitrageScenario(
        scenario_id="invalid-missing-control",
        time_grid=grid,
        battery=_battery(),
        price_signal=_price_signal(grid),
        dispatch_requests=None,
        rule_policy=None,
        objective=_objective(),
    )

    with pytest.raises(
        ValueError,
        match="exactly one of dispatch_requests or rule_policy",
    ):
        scenario.validate()


def test_dispatch_request_length_must_match_time_grid() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    scenario = ArbitrageScenario(
        scenario_id="invalid-dispatch-length",
        time_grid=grid,
        battery=_battery(),
        price_signal=_price_signal(grid),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=[1.0, -1.0],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="test",
        ),
        rule_policy=None,
        objective=_objective(),
    )

    with pytest.raises(ValueError, match="dispatch request length"):
        scenario.validate()


def test_valid_dispatch_scenario_builds_required_component_graph() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    scenario = ArbitrageScenario(
        scenario_id="dispatch-scenario",
        time_grid=grid,
        battery=_battery(),
        price_signal=_price_signal(grid),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=[1.0, 0.0, -1.0],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="test",
        ),
        rule_policy=None,
        objective=_objective(),
    )

    graph = scenario.validate()

    assert isinstance(graph, ComponentGraph)
    assert "time_grid" in graph.components
    assert "battery" in graph.components
    assert "price_signal" in graph.components
    assert graph.has_connection("time_grid", "price_signal", "aligns")
    assert graph.has_connection("time_grid", "dispatch_requests", "aligns")
    assert graph.has_connection("dispatch_requests", "battery", "requests")
    assert scenario.numeric_tolerance == DEFAULT_ABSOLUTE_TOLERANCE


def test_valid_rule_policy_scenario_builds_required_component_graph() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    scenario = ArbitrageScenario(
        scenario_id="policy-scenario",
        time_grid=grid,
        battery=_battery(),
        price_signal=_price_signal(grid),
        dispatch_requests=None,
        rule_policy=DeterministicRulePolicy(
            policy_name="price_threshold",
            price_threshold=0.2,
            below_threshold_action="charge",
            above_threshold_action="discharge",
            at_threshold_action="hold",
        ),
        objective=_objective(),
    )

    graph = scenario.validate()

    assert isinstance(graph, ComponentGraph)
    assert "rule_policy" in graph.components
    assert graph.has_connection("time_grid", "rule_policy", "aligns")
    assert graph.has_connection("price_signal", "rule_policy", "drives")
    assert graph.has_connection("rule_policy", "battery", "requests")
