"""Simulator package boundary for the first migration target.

`open_energy_lab.simulator` is the stable package location for simulator work.
Concrete arbitrage-facing types remain experimental until later migration
phases promote them. This module intentionally stays import-light and does not
pull in optional research stacks.
"""

from __future__ import annotations

from .load import LoadComponent
from .pricing import (
    ArbitrageObjectiveRepresentation,
    DeterministicRulePolicy,
    PriceSignal,
)
from .pv import PVComponent
from .scenario import (
    ArbitrageScenario,
    BatteryLoadPVScenario,
    BatteryComponent,
    DispatchRequestSeries,
    TimeGrid,
)
from .weather import WeatherComponent

__all__ = [
    "ArbitrageObjectiveRepresentation",
    "ArbitrageScenario",
    "BatteryLoadPVScenario",
    "BatteryComponent",
    "DeterministicRulePolicy",
    "DispatchRequestSeries",
    "LoadComponent",
    "PVComponent",
    "PriceSignal",
    "TimeGrid",
    "WeatherComponent",
]
