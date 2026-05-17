"""Settlement helpers for the battery arbitrage MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._units import validate_positive_time_step_hours

if TYPE_CHECKING:
    from .pricing import ArbitrageObjectiveRepresentation, PriceSignal


@dataclass(slots=True)
class SettlementResult:
    """Per-step and aggregate arbitrage settlement values."""

    step_settlement: list[float]
    total_settlement: float


def evaluate_arbitrage_settlement(
    *,
    realized_power_kw: list[float],
    time_step_hours: float,
    price_signal: PriceSignal,
    objective: ArbitrageObjectiveRepresentation,
) -> SettlementResult:
    """Evaluate discounted import/export settlement for a realized power trace."""

    duration_hours = validate_positive_time_step_hours(time_step_hours)
    if len(realized_power_kw) != price_signal.time_grid.num_steps:
        raise ValueError("realized power length must match the price signal time grid")
    if objective.allow_export and objective.export_price_ratio != price_signal.export_price_ratio:
        raise ValueError("objective export discount must match the price signal")

    step_values: list[float] = []
    for step_index, power_kw in enumerate(realized_power_kw):
        energy_kwh = power_kw * duration_hours
        if energy_kwh >= 0.0:
            step_value = -(energy_kwh * price_signal.price_at_step(step_index))
        else:
            export_price = price_signal.export_price_at_step(step_index)
            if objective.allow_export:
                step_value = abs(energy_kwh) * export_price
            else:
                step_value = 0.0
        step_values.append(step_value)

    return SettlementResult(
        step_settlement=step_values,
        total_settlement=sum(step_values),
    )


__all__ = ["SettlementResult", "evaluate_arbitrage_settlement"]
