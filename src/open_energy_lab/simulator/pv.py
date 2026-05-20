"""Deterministic PV metadata and weather-driven generation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._weather_schema import IRRADIANCE_FIELD_NAMES, validate_weather_field_names

if TYPE_CHECKING:
    from .weather import WeatherComponent


@dataclass(slots=True)
class PVComponent:
    """Minimal PV metadata for deterministic MVP generation."""

    name: str
    rated_power_kw: float
    temperature_coefficient_pct_per_c: float
    reference_irradiance_w_per_m2: float
    reference_temperature_c: float
    derivation_name: str
    irradiance_field_names: tuple[str, ...]
    generation_cap_kw: float | None = None

    def __post_init__(self) -> None:
        if self.rated_power_kw <= 0:
            raise ValueError("rated_power_kw must be positive")
        if self.reference_irradiance_w_per_m2 <= 0:
            raise ValueError("reference_irradiance_w_per_m2 must be positive")
        if not self.derivation_name:
            raise ValueError("derivation_name must be provided")

        self.irradiance_field_names = validate_weather_field_names(self.irradiance_field_names)
        invalid = [
            field_name
            for field_name in self.irradiance_field_names
            if field_name not in IRRADIANCE_FIELD_NAMES
        ]
        if invalid:
            formatted = ", ".join(invalid)
            raise ValueError(f"irradiance_field_names must be irradiance fields: {formatted}")

        if not self.irradiance_field_names:
            raise ValueError("at least one irradiance field name must be provided")
        if self.generation_cap_kw is not None and self.generation_cap_kw <= 0:
            raise ValueError("generation_cap_kw must be positive when provided")

    def derive_generation_kw(self, weather: WeatherComponent) -> list[float]:
        generation_kw: list[float] = []

        for step_index in range(weather.time_grid.num_steps):
            irradiance_w_per_m2 = sum(
                float(weather.field_values(field_name)[step_index])
                for field_name in self.irradiance_field_names
            )
            irradiance_factor = irradiance_w_per_m2 / self.reference_irradiance_w_per_m2
            temperature_c = weather.dry_bulb_air_temperature_c[step_index]
            temperature_factor = 1.0 + (
                (self.temperature_coefficient_pct_per_c / 100.0)
                * (temperature_c - self.reference_temperature_c)
            )
            raw_generation_kw = self.rated_power_kw * irradiance_factor * temperature_factor
            clamped_generation_kw = max(0.0, raw_generation_kw)
            if self.generation_cap_kw is not None:
                clamped_generation_kw = min(clamped_generation_kw, self.generation_cap_kw)
            generation_kw.append(clamped_generation_kw)

        return generation_kw


__all__ = ["PVComponent"]
