"""Scenario-support integration coverage for shipped native controllers."""

from __future__ import annotations

import pytest

from open_energy_lab.control import (
    PVSelfConsumptionConfig,
    PVSelfConsumptionController,
    PriceThresholdConfig,
    PriceThresholdController,
    SocGuardrailConfig,
    SocGuardrailController,
)
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
    evaluate_with_controller,
)
from open_energy_lab.simulator._units import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    POSITIVE_DISPATCH_MEANING,
)


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
        source="controller-support-integration",
    )


def _arbitrage_scenario(*, initial_soc: float = 0.5) -> ArbitrageScenario:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    return ArbitrageScenario(
        scenario_id="controller-support-arbitrage",
        time_grid=grid,
        battery=_battery(initial_soc=initial_soc),
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
        source="controller-support-integration",
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


def _battery_load_pv_scenario(*, initial_soc: float = 0.5) -> BatteryLoadPVScenario:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    return BatteryLoadPVScenario(
        scenario_id="controller-support-battery-load-pv",
        time_grid=grid,
        battery=_battery(initial_soc=initial_soc),
        load=_load(grid),
        weather=_weather(grid),
        pv=_pv(),
        price_signal=_price_signal(grid),
        objective=_objective(),
        dispatch_requests=_dispatch_requests(grid.num_steps),
    )


@pytest.mark.parametrize(
    ("controller", "scenario", "expected_scenario_kind"),
    (
        (
            PriceThresholdController(
                PriceThresholdConfig(
                    charge_below_import_price=0.15,
                    discharge_above_import_price=0.25,
                    charge_request_kw=5.0,
                    discharge_request_kw=5.0,
                )
            ),
            _arbitrage_scenario(),
            "ArbitrageScenario",
        ),
        (
            SocGuardrailController(
                SocGuardrailConfig(
                    target_min_soc=0.25,
                    target_max_soc=0.75,
                    charge_request_kw=5.0,
                    discharge_request_kw=4.0,
                )
            ),
            _arbitrage_scenario(initial_soc=0.2),
            "ArbitrageScenario",
        ),
        (
            SocGuardrailController(
                SocGuardrailConfig(
                    target_min_soc=0.25,
                    target_max_soc=0.75,
                    charge_request_kw=5.0,
                    discharge_request_kw=4.0,
                )
            ),
            _battery_load_pv_scenario(initial_soc=0.8),
            "BatteryLoadPVScenario",
        ),
        (
            PVSelfConsumptionController(
                PVSelfConsumptionConfig(
                    reserve_min_soc=0.20,
                    reserve_max_soc=0.80,
                    charge_request_kw=5.0,
                    discharge_request_kw=4.0,
                )
            ),
            _battery_load_pv_scenario(),
            "BatteryLoadPVScenario",
        ),
    ),
)
def test_native_controllers_run_deterministically_on_their_supported_scenarios(
    controller: object,
    scenario: ArbitrageScenario | BatteryLoadPVScenario,
    expected_scenario_kind: str,
) -> None:
    first_result = evaluate_with_controller(scenario, controller)
    second_result = evaluate_with_controller(scenario, controller)

    assert first_result.rejection is None
    assert first_result.scenario_kind == expected_scenario_kind
    assert first_result.controller_name == controller.__class__.__name__
    assert len(first_result.step_records) == scenario.time_grid.num_steps
    assert first_result.requested_power_kw == pytest.approx(
        second_result.requested_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.realized_power_kw == pytest.approx(
        second_result.realized_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.total_settlement == pytest.approx(
        second_result.total_settlement,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    if expected_scenario_kind == "ArbitrageScenario":
        assert all(record.context.step_inputs == {} for record in first_result.step_records)
    else:
        assert all("load_kw" in record.context.step_inputs for record in first_result.step_records)
        assert all(
            "pv_generation_kw" in record.context.step_inputs
            for record in first_result.step_records
        )


@pytest.mark.parametrize(
    ("controller", "scenario", "scenario_kind"),
    (
        (
            PriceThresholdController(
                PriceThresholdConfig(
                    charge_below_import_price=0.15,
                    discharge_above_import_price=0.25,
                    charge_request_kw=5.0,
                    discharge_request_kw=5.0,
                )
            ),
            _battery_load_pv_scenario(),
            "BatteryLoadPVScenario",
        ),
        (
            PVSelfConsumptionController(
                PVSelfConsumptionConfig(
                    reserve_min_soc=0.20,
                    reserve_max_soc=0.80,
                    charge_request_kw=5.0,
                    discharge_request_kw=4.0,
                )
            ),
            _arbitrage_scenario(),
            "ArbitrageScenario",
        ),
    ),
)
def test_native_controllers_fail_fast_on_unsupported_scenarios(
    controller: object,
    scenario: ArbitrageScenario | BatteryLoadPVScenario,
    scenario_kind: str,
) -> None:
    with pytest.raises(ValueError) as first_error:
        evaluate_with_controller(scenario, controller)

    with pytest.raises(ValueError) as second_error:
        evaluate_with_controller(scenario, controller)

    assert str(first_error.value) == str(second_error.value)
    assert controller.__class__.__name__ in str(first_error.value)
    assert scenario_kind in str(first_error.value)
    assert "supported scenarios" in str(first_error.value)
