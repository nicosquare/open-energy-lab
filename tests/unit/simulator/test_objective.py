"""Settlement-accounting tests for the battery arbitrage MVP."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE
from open_energy_lab.simulator.objective import evaluate_arbitrage_settlement
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
        objective_name="arbitrage",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=0.8,
    )


def test_evaluate_arbitrage_settlement_applies_discounted_export_prices() -> None:
    grid = _time_grid()
    settlement = evaluate_arbitrage_settlement(
        realized_power_kw=[2.0, 0.0, -3.0],
        time_step_hours=grid.time_step_hours,
        price_signal=_price_signal(grid),
        objective=_objective(),
    )

    assert settlement.step_settlement == pytest.approx(
        [-0.2, 0.0, 0.72],
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_evaluate_arbitrage_settlement_total_matches_step_sum() -> None:
    grid = _time_grid()
    settlement = evaluate_arbitrage_settlement(
        realized_power_kw=[1.0, -2.0, 0.5],
        time_step_hours=grid.time_step_hours,
        price_signal=_price_signal(grid),
        objective=_objective(),
    )

    assert settlement.total_settlement == pytest.approx(
        sum(settlement.step_settlement),
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
