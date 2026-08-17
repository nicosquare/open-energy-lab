"""Settlement helpers for the battery arbitrage MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._units import validate_positive_time_step_hours

if TYPE_CHECKING:
    from .pricing import (
        ArbitrageObjectiveRepresentation,
        DistrictCoolingTariff,
        PriceSignal,
    )


@dataclass(slots=True)
class SettlementResult:
    """Per-step and aggregate arbitrage settlement values."""

    step_settlement: list[float]
    total_settlement: float


@dataclass(slots=True)
class NetGridSettlementResult:
    """Per-step and aggregate settlement values for one-net grid accounting."""

    net_grid_power_kw: list[float]
    net_grid_energy_kwh: list[float]
    direction: list[str]
    step_settlement: list[float]
    total_settlement: float


@dataclass(slots=True)
class DistrictCoolingSettlementResult:
    """Deterministic district-cooling settlement from served thermal demand."""

    served_cooling_rt: list[float]
    served_cooling_rt_hours: list[float]
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


def evaluate_net_grid_settlement(
    *,
    load_kw: list[float],
    pv_generation_kw: list[float],
    realized_battery_power_kw: list[float],
    time_step_hours: float,
    price_signal: PriceSignal,
    objective: ArbitrageObjectiveRepresentation,
) -> NetGridSettlementResult:
    """Evaluate one-net settlement for battery + load + PV traces."""

    duration_hours = validate_positive_time_step_hours(time_step_hours)
    expected_steps = price_signal.time_grid.num_steps
    for values, label in (
        (load_kw, "load"),
        (pv_generation_kw, "pv generation"),
        (realized_battery_power_kw, "realized battery power"),
    ):
        if len(values) != expected_steps:
            raise ValueError(f"{label} length must match the price signal time grid")
    if objective.allow_export and objective.export_price_ratio != price_signal.export_price_ratio:
        raise ValueError("objective export discount must match the price signal")

    net_grid_power_kw: list[float] = []
    net_grid_energy_kwh: list[float] = []
    direction: list[str] = []
    step_settlement: list[float] = []

    for step_index, (load_value, pv_value, battery_value) in enumerate(
        zip(load_kw, pv_generation_kw, realized_battery_power_kw, strict=True)
    ):
        net_power_kw = load_value + battery_value - pv_value
        net_energy_kwh = net_power_kw * duration_hours
        if net_power_kw > 0.0:
            direction_value = "import"
            step_value = -(net_energy_kwh * price_signal.price_at_step(step_index))
        elif net_power_kw < 0.0:
            direction_value = "export"
            export_price = price_signal.export_price_at_step(step_index)
            if objective.allow_export:
                step_value = abs(net_energy_kwh) * export_price
            else:
                step_value = 0.0
        else:
            direction_value = "neutral"
            step_value = 0.0

        net_grid_power_kw.append(net_power_kw)
        net_grid_energy_kwh.append(net_energy_kwh)
        direction.append(direction_value)
        step_settlement.append(step_value)

    return NetGridSettlementResult(
        net_grid_power_kw=net_grid_power_kw,
        net_grid_energy_kwh=net_grid_energy_kwh,
        direction=direction,
        step_settlement=step_settlement,
        total_settlement=sum(step_settlement),
    )


def evaluate_district_cooling_settlement(
    *,
    served_cooling_rt: list[float],
    time_step_hours: float,
    tariff: DistrictCoolingTariff,
) -> DistrictCoolingSettlementResult:
    """Evaluate deterministic district-cooling settlement from served RT."""

    duration_hours = validate_positive_time_step_hours(time_step_hours)
    served_cooling_rt_hours: list[float] = []
    step_settlement: list[float] = []

    for served_value in served_cooling_rt:
        served_cooling = float(served_value)
        if served_cooling < 0.0:
            raise ValueError("served_cooling_rt values must be non-negative")
        served_rt_hours = served_cooling * duration_hours
        served_cooling_rt_hours.append(served_rt_hours)
        step_settlement.append(served_rt_hours * tariff.rate_per_rt_hour)

    return DistrictCoolingSettlementResult(
        served_cooling_rt=list(served_cooling_rt),
        served_cooling_rt_hours=served_cooling_rt_hours,
        step_settlement=step_settlement,
        total_settlement=sum(step_settlement),
    )


__all__ = [
    "DistrictCoolingSettlementResult",
    "NetGridSettlementResult",
    "SettlementResult",
    "evaluate_arbitrage_settlement",
    "evaluate_district_cooling_settlement",
    "evaluate_net_grid_settlement",
]
