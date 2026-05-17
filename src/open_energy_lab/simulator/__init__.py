"""Simulator package boundary for the first migration target.

`open_energy_lab.simulator` is the stable package location for simulator work.
Concrete arbitrage-facing types remain experimental until later migration
phases promote them. This module intentionally stays import-light and does not
pull in optional research stacks.
"""

from __future__ import annotations

from .pricing import (
    ArbitrageObjectiveRepresentation,
    DeterministicRulePolicy,
    PriceSignal,
)
from .scenario import (
    ArbitrageScenario,
    BatteryComponent,
    DispatchRequestSeries,
    TimeGrid,
)

__all__ = [
    "ArbitrageObjectiveRepresentation",
    "ArbitrageScenario",
    "BatteryComponent",
    "DeterministicRulePolicy",
    "DispatchRequestSeries",
    "PriceSignal",
    "TimeGrid",
]
