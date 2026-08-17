"""Pricing and settlement types for simulator execution paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._units import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    is_close,
    validate_positive_time_step_hours,
)

if TYPE_CHECKING:
    from .scenario import TimeGrid


_ALLOWED_POLICY_ACTIONS = {"charge", "hold", "discharge"}


@dataclass(slots=True)
class PriceSignal:
    """Step-aligned import prices with discounted export settlement."""

    currency: str
    unit_rate_name: str
    import_prices: list[float]
    export_price_ratio: float
    interpretation: str
    time_alignment: str
    time_grid: "TimeGrid"

    def __post_init__(self) -> None:
        if len(self.import_prices) != self.time_grid.num_steps:
            raise ValueError("import price length must match the time grid")
        if not 0.0 < self.export_price_ratio < 1.0:
            raise ValueError("export_price_ratio must define discounted export settlement")
        if self.time_alignment != "step-start":
            raise ValueError("time_alignment must be step-start")
        if "discount" not in self.interpretation.lower():
            raise ValueError("interpretation must describe discounted export settlement")

    def price_at_step(self, step_index: int) -> float:
        return self.import_prices[step_index]

    def export_price_at_step(self, step_index: int) -> float:
        return self.import_prices[step_index] * self.export_price_ratio


@dataclass(slots=True)
class DistrictCoolingTariff:
    """Deterministic district-cooling settlement aligned to the scenario grid."""

    currency: str
    rate_per_rt_hour: float
    time_alignment: str
    tariff_name: str

    def __post_init__(self) -> None:
        if self.rate_per_rt_hour < 0.0:
            raise ValueError("rate_per_rt_hour must be non-negative")
        if self.time_alignment != "step-start":
            raise ValueError("time_alignment must be step-start")
        if not self.currency:
            raise ValueError("currency must be provided")
        if not self.tariff_name:
            raise ValueError("tariff_name must be provided")

    def settlement_rate_for_step(self, time_step_hours: float) -> float:
        """Return the deterministic settlement rate for one served-RT step."""

        return self.rate_per_rt_hour * validate_positive_time_step_hours(time_step_hours)


@dataclass(slots=True)
class DeterministicRulePolicy:
    """Built-in deterministic policy limited to the MVP price-threshold rule."""

    policy_name: str
    price_threshold: float
    below_threshold_action: str
    above_threshold_action: str
    at_threshold_action: str

    def __post_init__(self) -> None:
        if self.policy_name != "price_threshold":
            raise ValueError("only the price_threshold policy is supported")
        for action in (
            self.below_threshold_action,
            self.above_threshold_action,
            self.at_threshold_action,
        ):
            if action not in _ALLOWED_POLICY_ACTIONS:
                raise ValueError(f"unsupported policy action: {action}")

    def action_for_price(self, price: float) -> str:
        if price < self.price_threshold:
            return self.below_threshold_action
        if is_close(price, self.price_threshold, tolerance=DEFAULT_ABSOLUTE_TOLERANCE):
            return self.at_threshold_action
        return self.above_threshold_action


@dataclass(slots=True)
class ArbitrageObjectiveRepresentation:
    """Objective metadata for discounted export settlement."""

    objective_name: str
    settlement_basis: str
    allow_export: bool
    export_price_ratio: float

    def __post_init__(self) -> None:
        if self.allow_export and not 0.0 < self.export_price_ratio < 1.0:
            raise ValueError("discounted export settlement requires 0 < export_price_ratio < 1")


__all__ = [
    "ArbitrageObjectiveRepresentation",
    "DeterministicRulePolicy",
    "DistrictCoolingTariff",
    "PriceSignal",
]
