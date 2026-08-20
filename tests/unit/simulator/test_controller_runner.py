"""Unit tests defining controller-runner validation and rejection behavior."""

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
from open_energy_lab.simulator._units import POSITIVE_DISPATCH_MEANING


def _battery(*, initial_soc: float = 0.5) -> BatteryComponent:
    return BatteryComponent(
        name="battery",
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=initial_soc,
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
        import_prices=[0.10] * grid.num_steps,
        export_price_ratio=0.8,
        interpretation="discounted export relative to import prices",
        time_alignment="step-start",
        time_grid=grid,
    )


def _dispatch_requests(num_steps: int) -> DispatchRequestSeries:
    return DispatchRequestSeries(
        requested_power_kw=[0.0] * num_steps,
        sign_convention=POSITIVE_DISPATCH_MEANING,
        source="runner-test-baseline",
    )


def _arbitrage_scenario(*, num_steps: int = 3, initial_soc: float = 0.5) -> ArbitrageScenario:
    grid = TimeGrid(num_steps=num_steps, time_step_hours=1.0)
    return ArbitrageScenario(
        scenario_id="arbitrage-controller-runner",
        time_grid=grid,
        battery=_battery(initial_soc=initial_soc),
        price_signal=_price_signal(grid),
        objective=_objective(),
        dispatch_requests=_dispatch_requests(num_steps),
    )


def _load(grid: TimeGrid) -> LoadComponent:
    return LoadComponent(
        name="load",
        demand_kw=[2.0] * grid.num_steps,
        interpretation="exogenous-consumption",
        time_grid=grid,
        source="runner-test-baseline",
    )


def _weather(grid: TimeGrid) -> WeatherComponent:
    return WeatherComponent(
        name="weather",
        time_grid=grid,
        timestamp_utc=[
            f"2026-01-01T0{step_index}:00:00Z" for step_index in range(grid.num_steps)
        ],
        dry_bulb_air_temperature_c=[25.0] * grid.num_steps,
        global_horizontal_irradiance_w_per_m2=[400.0] * grid.num_steps,
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


def _battery_load_pv_scenario(*, num_steps: int = 3) -> BatteryLoadPVScenario:
    grid = TimeGrid(num_steps=num_steps, time_step_hours=1.0)
    return BatteryLoadPVScenario(
        scenario_id="battery-load-pv-controller-runner",
        time_grid=grid,
        battery=_battery(),
        load=_load(grid),
        weather=_weather(grid),
        pv=_pv(),
        price_signal=_price_signal(grid),
        objective=_objective(),
        dispatch_requests=_dispatch_requests(num_steps),
    )


class _StepMismatchController:
    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        return DispatchProposal(
            step_index=context.step_index + 1,
            requested_power_kw=1.0,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name="step-mismatch",
        )


class _WrongSignController:
    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        proposal = DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=1.0,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name="wrong-sign",
        )
        proposal.sign_convention = "discharge"
        return proposal


class _LargeChargeController:
    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=5.0,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name="large-charge",
        )


class _LargeDischargeController:
    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=-5.0,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name="large-discharge",
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


@pytest.mark.parametrize(
    ("controller", "match"),
    [
        (_StepMismatchController(), "step_index"),
        (_WrongSignController(), "sign_convention"),
    ],
)
def test_evaluate_with_controller_rejects_invalid_single_step_proposals(
    controller: object,
    match: str,
) -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    scenario = _arbitrage_scenario()

    with pytest.raises(ValueError, match=match):
        evaluate_with_controller(scenario, controller)


def test_evaluate_with_controller_records_clamping_when_requests_exceed_feasible_charge() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    scenario = _arbitrage_scenario(num_steps=1, initial_soc=0.98)

    result = evaluate_with_controller(scenario, _LargeChargeController())

    assert result.rejection is None
    assert result.requested_power_kw == pytest.approx([5.0])
    assert result.realized_power_kw[0] < result.requested_power_kw[0]
    assert result.step_records[0].proposal.requested_power_kw == pytest.approx(5.0)
    assert result.step_records[0].constraint_events
    assert "requested" in result.step_records[0].constraint_events[0]


def test_islanded_controller_charge_is_limited_to_local_pv_surplus() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    scenario = _battery_load_pv_scenario(num_steps=1)
    scenario.load.demand_kw = [2.0]
    scenario.weather.global_horizontal_irradiance_w_per_m2 = [1000.0]
    scenario.blackout_grid_available = [False]

    result = evaluate_with_controller(scenario, _LargeChargeController())

    assert result.requested_power_kw == pytest.approx([5.0])
    assert result.realized_power_kw == pytest.approx([2.0])
    assert result.underlying_trace.unmet_load_kw == pytest.approx([0.0])
    assert result.underlying_trace.net_grid_power_kw == pytest.approx([0.0])
    assert result.step_records[0].constraint_events


def test_islanded_controller_charge_does_not_become_unmet_site_load() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    scenario = _battery_load_pv_scenario(num_steps=1)
    scenario.load.demand_kw = [2.0]
    scenario.weather.global_horizontal_irradiance_w_per_m2 = [0.0]
    scenario.blackout_grid_available = [False]

    result = evaluate_with_controller(scenario, _LargeChargeController())

    assert result.requested_power_kw == pytest.approx([5.0])
    assert result.realized_power_kw == pytest.approx([0.0])
    assert result.underlying_trace.unmet_load_kw == pytest.approx([2.0])
    assert result.underlying_trace.unmet_load_kw[0] <= scenario.load.demand_kw[0]


def test_islanded_controller_discharge_is_limited_to_residual_site_load() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    scenario = _battery_load_pv_scenario(num_steps=1)
    scenario.load.demand_kw = [2.0]
    scenario.weather.global_horizontal_irradiance_w_per_m2 = [0.0]
    scenario.blackout_grid_available = [False]

    result = evaluate_with_controller(scenario, _LargeDischargeController())

    assert result.requested_power_kw == pytest.approx([-5.0])
    assert result.realized_power_kw == pytest.approx([-2.0])
    assert result.underlying_trace.unmet_load_kw == pytest.approx([0.0])
    assert result.underlying_trace.net_grid_power_kw == pytest.approx([0.0])


def test_evaluate_with_controller_returns_named_rejection_before_controller_execution() -> None:
    from open_energy_lab.simulator.controller_runner import evaluate_with_controller

    scenario = _battery_load_pv_scenario()
    scenario.load.demand_kw[0] = None  # type: ignore[list-item]
    controller = _CountingController()

    result = evaluate_with_controller(scenario, controller)

    assert controller.calls == 0
    assert result.rejection is not None
    assert result.rejection.failure_name == "incomplete_controller_context"
    assert result.rejection.step_index == 0
    assert result.rejection.missing_inputs == ["load_kw"]
    assert result.step_records == []
    assert result.requested_power_kw == []
    assert result.realized_power_kw == []
