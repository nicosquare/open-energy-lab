"""Minimal deterministic weather inputs for PV derivation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._weather_schema import (
    IRRADIANCE_FIELD_NAMES,
    REQUIRED_WEATHER_FIELD_NAMES,
    canonical_tmy_label,
    is_deferred_standard_weather_field,
    validate_weather_field_names,
)

if TYPE_CHECKING:
    from .scenario import TimeGrid


@dataclass(slots=True)
class WeatherComponent:
    """Time-aligned weather inputs limited to the PV-driving MVP subset."""

    name: str
    time_grid: TimeGrid
    timestamp_utc: list[str]
    dry_bulb_air_temperature_c: list[float]
    global_horizontal_irradiance_w_per_m2: list[float] | None = None
    direct_beam_irradiance_w_per_m2: list[float] | None = None
    diffuse_horizontal_irradiance_w_per_m2: list[float] | None = None
    deferred_fields: tuple[str, ...] = ()
    source: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        self._validate_required_field_lengths()
        self._validate_irradiance_inputs()
        self._validate_deferred_fields()

    @property
    def deferred_field_names(self) -> tuple[str, ...]:
        return self.deferred_fields

    def included_field_names(self) -> tuple[str, ...]:
        included = list(REQUIRED_WEATHER_FIELD_NAMES)
        for field_name in IRRADIANCE_FIELD_NAMES:
            if getattr(self, field_name) is not None:
                included.append(field_name)
        return tuple(included)

    def tmy_label_for(self, field_name: str) -> str:
        return canonical_tmy_label(field_name)

    def field_values(self, field_name: str) -> list[float] | list[str]:
        if field_name not in self.included_field_names():
            raise ValueError(f"weather field '{field_name}' is not included in this component")
        return getattr(self, field_name)

    def _validate_required_field_lengths(self) -> None:
        for field_name in REQUIRED_WEATHER_FIELD_NAMES:
            values = getattr(self, field_name)
            if len(values) != self.time_grid.num_steps:
                raise ValueError(f"weather field '{field_name}' length must match the time grid")

    def _validate_irradiance_inputs(self) -> None:
        provided_irradiance_names = [
            field_name
            for field_name in IRRADIANCE_FIELD_NAMES
            if getattr(self, field_name) is not None
        ]
        if not provided_irradiance_names:
            raise ValueError("at least one irradiance field must be provided")

        for field_name in provided_irradiance_names:
            values = getattr(self, field_name)
            assert values is not None
            if len(values) != self.time_grid.num_steps:
                raise ValueError(f"weather field '{field_name}' length must match the time grid")
            if any(value < 0 for value in values):
                raise ValueError(f"irradiance field '{field_name}' must be non-negative")

    def _validate_deferred_fields(self) -> None:
        validated = validate_weather_field_names(self.deferred_fields)
        invalid = [
            field_name
            for field_name in validated
            if not is_deferred_standard_weather_field(field_name)
        ]
        if invalid:
            formatted = ", ".join(invalid)
            raise ValueError(f"deferred weather fields must come from the deferred standard set: {formatted}")
        self.deferred_fields = validated


__all__ = ["WeatherComponent"]
