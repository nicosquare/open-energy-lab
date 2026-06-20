"""Deterministic exogenous load profile types."""

from __future__ import annotations

from dataclasses import field
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


@dataclass(slots=True)
class CoolingServiceBalance:
    """Scenario-side cooling service outputs aligned to one deterministic trace."""

    time_grid: TimeGrid
    local_cooling_electric_kw: list[float]
    served_cooling_rt: list[float]
    unserved_cooling_rt: list[float]
    district_cooling_settlement: list[float] = field(default_factory=list)
    source: str | None = None

    def __post_init__(self) -> None:
        expected_length = self.time_grid.num_steps
        for values, label in (
            (self.local_cooling_electric_kw, "local_cooling_electric_kw"),
            (self.served_cooling_rt, "served_cooling_rt"),
            (self.unserved_cooling_rt, "unserved_cooling_rt"),
        ):
            if len(values) != expected_length:
                raise ValueError(f"{label} length must match the time grid")
            if any(value < 0 for value in values):
                raise ValueError(f"{label} values must be non-negative")

        if not self.district_cooling_settlement:
            self.district_cooling_settlement = [0.0] * expected_length
        if len(self.district_cooling_settlement) != expected_length:
            raise ValueError("district_cooling_settlement length must match the time grid")


__all__ = ["CoolingServiceBalance", "LoadComponent"]
