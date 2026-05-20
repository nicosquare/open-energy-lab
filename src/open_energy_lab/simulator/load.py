"""Deterministic exogenous load profile types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario import TimeGrid


@dataclass(slots=True)
class LoadComponent:
    """Time-aligned deterministic exogenous demand profile."""

    name: str
    demand_kw: list[float]
    interpretation: str
    time_grid: TimeGrid
    source: str | None = None

    def __post_init__(self) -> None:
        if len(self.demand_kw) != self.time_grid.num_steps:
            raise ValueError("load profile length must match the time grid")
        if any(value < 0 for value in self.demand_kw):
            raise ValueError("load values must be non-negative")
        if self.interpretation != "exogenous-consumption":
            raise ValueError("interpretation must be 'exogenous-consumption'")


__all__ = ["LoadComponent"]
