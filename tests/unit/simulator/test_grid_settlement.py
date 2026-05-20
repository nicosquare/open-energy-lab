"""Net-grid settlement tests for the battery + load + PV MVP."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE
from open_energy_lab.simulator.objective import evaluate_net_grid_settlement
from open_energy_lab.simulator.pricing import (
    ArbitrageObjectiveRepresentation,
    PriceSignal,
)
from open_energy_lab.simulator.scenario import TimeGrid


def _time_grid() -> TimeGrid:
    return TimeGrid(num_steps=3, time_step_hours=1.0)


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


def _objective() -> ArbitrageObjectiveRepresentation:
    return ArbitrageObjectiveRepresentation(
        objective_name="grid-settlement",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=0.8,
    )


def test_evaluate_net_grid_settlement_applies_one_net_sign_rule() -> None:
    grid = _time_grid()
    settlement = evaluate_net_grid_settlement(
        load_kw=[2.0, 1.0, 0.0],
        pv_generation_kw=[0.0, 4.0, 0.0],
        realized_battery_power_kw=[1.0, -1.0, 0.0],
        time_step_hours=grid.time_step_hours,
        price_signal=_price_signal(grid),
        objective=_objective(),
    )

    assert settlement.net_grid_power_kw == pytest.approx(
        [3.0, -4.0, 0.0],
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert settlement.direction == ["import", "export", "neutral"]
    assert settlement.step_settlement == pytest.approx(
        [-0.30, 0.64, 0.0],
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_evaluate_net_grid_settlement_total_matches_step_sum() -> None:
    grid = _time_grid()
    settlement = evaluate_net_grid_settlement(
        load_kw=[1.0, 1.0, 1.0],
        pv_generation_kw=[0.0, 0.0, 2.0],
        realized_battery_power_kw=[0.0, 1.0, 0.0],
        time_step_hours=grid.time_step_hours,
        price_signal=_price_signal(grid),
        objective=_objective(),
    )

    assert settlement.total_settlement == pytest.approx(
        sum(settlement.step_settlement),
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
