"""Internal simulator unit and validation helpers.

These helpers define the shared conventions for the battery arbitrage MVP.
They are internal on purpose: the package location is stable, but concrete
arbitrage-facing types remain experimental until later promotion.
"""

from __future__ import annotations


DEFAULT_ABSOLUTE_TOLERANCE = 1e-6
ENERGY_UNIT_KWH = "kWh"
POWER_UNIT_KW = "kW"
STATE_OF_CHARGE_UNIT = "fraction"
POSITIVE_DISPATCH_MEANING = "charge"
NEGATIVE_DISPATCH_MEANING = "discharge"
SOC_MIN = 0.0
SOC_MAX = 1.0


def validate_positive_time_step_hours(value: float) -> float:
    """Validate that a timestep is expressed in positive hours."""
    if value <= 0:
        raise ValueError("time_step_hours must be positive")
    return value


def validate_soc_fraction(value: float) -> float:
    """Validate that state of charge uses the MVP fraction convention."""
    if not SOC_MIN <= value <= SOC_MAX:
        raise ValueError("state of charge must be a fraction in [0.0, 1.0]")
    return value


def is_close(lhs: float, rhs: float, *, tolerance: float = DEFAULT_ABSOLUTE_TOLERANCE) -> bool:
    """Compare two values using the MVP default absolute tolerance."""
    return abs(lhs - rhs) <= tolerance


__all__ = [
    "DEFAULT_ABSOLUTE_TOLERANCE",
    "ENERGY_UNIT_KWH",
    "NEGATIVE_DISPATCH_MEANING",
    "POSITIVE_DISPATCH_MEANING",
    "POWER_UNIT_KW",
    "SOC_MAX",
    "SOC_MIN",
    "STATE_OF_CHARGE_UNIT",
    "is_close",
    "validate_positive_time_step_hours",
    "validate_soc_fraction",
]
