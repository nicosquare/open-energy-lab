"""Integration coverage for the package-root price-threshold controller."""

from __future__ import annotations

import pytest

from open_energy_lab.control import PriceThresholdConfig, PriceThresholdController
from open_energy_lab.simulator import (
    ArbitrageScenario,
    BatteryComponent,
    DispatchRequestSeries,
    PriceSignal,
    TimeGrid,
    evaluate_with_controller,
)
from open_energy_lab.simulator.pricing import ArbitrageObjectiveRepresentation
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


def _scenario(*, battery: BatteryComponent | None = None) -> ArbitrageScenario:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    return ArbitrageScenario(
        scenario_id="price-threshold-controller-integration",
        time_grid=grid,
        battery=_battery() if battery is None else battery,
        price_signal=PriceSignal(
            currency="USD",
            unit_rate_name="energy-price",
            import_prices=[0.10, 0.20, 0.30],
            export_price_ratio=0.8,
            interpretation="discounted export relative to import prices",
            time_alignment="step-start",
            time_grid=grid,
        ),
        objective=_objective(),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=[0.0] * grid.num_steps,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="price-threshold-controller-integration",
        ),
    )


def test_package_root_price_threshold_controller_produces_a_deterministic_arbitrage_trace() -> None:
    controller = PriceThresholdController(
        PriceThresholdConfig(
            charge_below_import_price=0.15,
            discharge_above_import_price=0.25,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
        )
    )

    first_result = evaluate_with_controller(_scenario(), controller)
    second_result = evaluate_with_controller(_scenario(), controller)

    assert first_result.rejection is None
    assert first_result.controller_name == "PriceThresholdController"
    assert first_result.requested_power_kw == pytest.approx([5.0, 0.0, -5.0])
    assert first_result.realized_power_kw == pytest.approx([5.0, 0.0, -5.0])
    assert [state.soc for state in first_result.underlying_trace.states] == pytest.approx(
        [0.975, 0.975, 0.4486842105263158],
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.underlying_trace.step_settlement == pytest.approx(
        [-0.5, 0.0, 1.2],
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert first_result.total_settlement == pytest.approx(0.7, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert second_result.requested_power_kw == pytest.approx(
        first_result.requested_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert second_result.realized_power_kw == pytest.approx(
        first_result.realized_power_kw,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert second_result.total_settlement == pytest.approx(
        first_result.total_settlement,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_package_root_price_threshold_controller_keeps_simulator_clamping_visible() -> None:
    controller = PriceThresholdController(
        PriceThresholdConfig(
            charge_below_import_price=0.15,
            discharge_above_import_price=0.25,
            charge_request_kw=7.0,
            discharge_request_kw=8.0,
        )
    )

    result = evaluate_with_controller(_scenario(), controller)

    assert result.rejection is None
    assert result.requested_power_kw == pytest.approx([7.0, 0.0, -8.0])
    assert result.realized_power_kw == pytest.approx([5.0, 0.0, -5.0])
    assert result.underlying_trace.constraint_events == [
        "step 0: requested 7.0 kW, realized 5.0 kW",
        "step 2: requested -8.0 kW, realized -5.0 kW",
    ]
