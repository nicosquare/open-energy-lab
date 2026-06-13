"""Canonical weather schema placeholders for the stochastic-weather feature."""

from __future__ import annotations

from open_energy_lab.simulator._weather_schema import (
    DEFERRED_STANDARD_WEATHER_FIELD_NAMES,
    REQUIRED_WEATHER_FIELD_NAMES,
)


CANONICAL_WEATHER_FIELD_ORDER = REQUIRED_WEATHER_FIELD_NAMES + DEFERRED_STANDARD_WEATHER_FIELD_NAMES
LOCAL_CIVIL_TIME_BASIS = "local_civil_time"

__all__ = [
    "CANONICAL_WEATHER_FIELD_ORDER",
    "LOCAL_CIVIL_TIME_BASIS",
]
