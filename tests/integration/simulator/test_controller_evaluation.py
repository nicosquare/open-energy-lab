"""Integration coverage for simulator-owned controller evaluation."""

from __future__ import annotations

import pytest

from open_energy_lab.core import ControllerContext, DispatchProposal
from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    ArbitrageScenario,
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    TimeGrid,
    WeatherComponent,
)
from open_energy_lab.simulator._units import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    POSITIVE_DISPATCH_MEANING,
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
        objective_name="grid-settlement",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=0.8,
    )


def _price_signal(grid: TimeGrid) -> PriceSignal:
    return PriceSignal(
        currency="USD",
        unit_rate_name="energy-price",
        import_prices=[0.10, 0.20, 0.30][: grid.num_steps],
        export_price_ratio=0.8,
        interpretation="discounted export relative to import prices",
        time_alignment="step-start",
        time_grid=grid,
    )


def _dispatch_requests(num_steps: int) -> DispatchRequestSeries:
    return DispatchRequestSeries(
        requested_power_kw=[0.0] * num_steps,
        sign_convention=POSITIVE_DISPATCH_MEANING,
        source="controller-evaluation-baseline",
    )


def _arbitrage_scenario() -> ArbitrageScenario:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    return ArbitrageScenario(
        scenario_id="controller-arbitrage-integration",
        time_grid=grid,
        battery=_battery(),
        price_signal=_price_signal(grid),
        objective=_objective(),
        dispatch_requests=_dispatch_requests(grid.num_steps),
    )


def _load(grid: TimeGrid) -> LoadComponent:
    return LoadComponent(
        name="load",
        demand_kw=[2.0, 1.5, 0.5][: grid.num_steps],
        interpretation="exogenous-consumption",
        time_grid=grid,
        source="controller-evaluation-baseline",
    )


def _weather(grid: TimeGrid) -> WeatherComponent:
    return WeatherComponent(
        name="weather",
        time_grid=grid,
        timestamp_utc=[
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T02:00:00Z",
        ][: grid.num_steps],
        dry_bulb_air_temperature_c=[25.0, 26.0, 27.0][: grid.num_steps],
        global_horizontal_irradiance_w_per_m2=[0.0, 500.0, 1000.0][: grid.num_steps],
    )


def _pv() -> PVComponent:
    return PVComponent(
        name="pv",
        rated_power_kw=4.0,
        temperature_coefficient_pct_per_c=-0.4,
        reference_irradiance_w_per_m2=1000.0,
        reference_temperature_c=25.0,
        derivation_name="ghi-linear-temperature-adjusted",
        irradiance_field_names=("global_horizontal_irradiance_w_per_m2",),
    )


def _battery_load_pv_scenario() -> BatteryLoadPVScenario:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    return BatteryLoadPVScenario(
        scenario_id="controller-battery-load-pv-integration",
        time_grid=grid,
        battery=_battery(),
        load=_load(grid),
        weather=_weather(grid),
        pv=_pv(),
        price_signal=_price_signal(grid),
        objective=_objective(),
        dispatch_requests=_dispatch_requests(grid.num_steps),
    )


class _SequenceController:
    def __init__(self, requested_power_kw: list[float]) -> None:
        self._requested_power_kw = requested_power_kw

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=self._requested_power_kw[context.step_index],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name="sequence-controller",
        )


class _CountingController:
    def __init__(self) -> None:
        self.calls = 0

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        self.calls += 1
        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=0.0,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name="counting-controller",
        )


def test_controller_evaluation_is_deterministic_for_arbitrage_scenarios() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    requested_power_kw = [1.0, 0.0, -1.0]

    first_result = evaluate_with_controller(
        _arbitrage_scenario(),
        _SequenceController(requested_power_kw),
    )
    second_result = evaluate_with_controller(
        _arbitrage_scenario(),
        _SequenceController(requested_power_kw),
    )

    assert first_result.rejection is None
    assert first_result.scenario_kind == "ArbitrageScenario"
    assert first_result.controller_name == "sequence-controller"
    assert first_result.requested_power_kw == pytest.approx(requested_power_kw)
    assert len(first_result.step_records) == 3
    assert all(record.context.step_inputs == {} for record in first_result.step_records)
    assert first_result.realized_power_kw == pytest.approx(
        second_result.realized_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.total_settlement == pytest.approx(
        second_result.total_settlement,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.underlying_trace is not None
    assert first_result.underlying_trace.total_settlement == pytest.approx(
        first_result.total_settlement,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_controller_evaluation_is_deterministic_for_battery_load_pv_scenarios() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    requested_power_kw = [1.0, 0.0, -1.0]

    first_result = evaluate_with_controller(
        _battery_load_pv_scenario(),
        _SequenceController(requested_power_kw),
    )
    second_result = evaluate_with_controller(
        _battery_load_pv_scenario(),
        _SequenceController(requested_power_kw),
    )

    assert first_result.rejection is None
    assert first_result.scenario_kind == "BatteryLoadPVScenario"
    assert first_result.requested_power_kw == pytest.approx(requested_power_kw)
    assert len(first_result.step_records) == 3
    assert first_result.step_records[0].context.step_inputs["load_kw"] == pytest.approx(2.0)
    assert first_result.step_records[0].context.step_inputs["pv_generation_kw"] == pytest.approx(
        0.0
    )
    assert first_result.step_records[1].context.step_inputs["load_kw"] == pytest.approx(1.5)
    assert "pv_generation_kw" in first_result.step_records[1].context.step_inputs
    assert first_result.realized_power_kw == pytest.approx(
        second_result.realized_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.total_settlement == pytest.approx(
        second_result.total_settlement,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.underlying_trace is not None
    assert second_result.underlying_trace is not None
    assert first_result.underlying_trace.net_grid_power_kw == pytest.approx(
        second_result.underlying_trace.net_grid_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_controller_evaluation_returns_named_rejection_for_incomplete_current_step_inputs() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    scenario = _battery_load_pv_scenario()
    scenario.load.demand_kw[0] = None  # type: ignore[list-item]
    controller = _CountingController()

    result = evaluate_with_controller(scenario, controller)

    assert controller.calls == 0
    assert result.rejection is not None
    assert result.rejection.failure_name == "incomplete_controller_context"
    assert result.rejection.reason
    assert result.rejection.step_index == 0
    assert result.rejection.missing_inputs == ["load_kw"]
    assert result.step_records == []
