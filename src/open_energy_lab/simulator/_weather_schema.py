"""Shared weather-field metadata and TMY-label mapping helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class WeatherFieldSpec:
    """Canonical metadata for one MVP weather field."""

    field_name: str
    tmy_label: str
    deferred_by_default: bool = False


_WEATHER_FIELD_SPECS = (
    WeatherFieldSpec("timestamp_utc", "Date & time (UTC)"),
    WeatherFieldSpec("dry_bulb_air_temperature_c", "T2m [°C]"),
    WeatherFieldSpec("global_horizontal_irradiance_w_per_m2", "G(h) [W/m2]"),
    WeatherFieldSpec("direct_beam_irradiance_w_per_m2", "Gb(n) [W/m2]"),
    WeatherFieldSpec("diffuse_horizontal_irradiance_w_per_m2", "Gd(h) [W/m2]"),
    WeatherFieldSpec("relative_humidity_pct", "RH [%]", deferred_by_default=True),
    WeatherFieldSpec(
        "infrared_radiation_downwards_w_per_m2",
        "IR(h) [W/m2]",
        deferred_by_default=True,
    ),
    WeatherFieldSpec("windspeed_10m_m_per_s", "WS10m [m/s]", deferred_by_default=True),
    WeatherFieldSpec("wind_direction_10m_deg", "WD10m [°]", deferred_by_default=True),
    WeatherFieldSpec("surface_air_pressure_pa", "SP [Pa]", deferred_by_default=True),
)

_SPECS_BY_FIELD_NAME = {item.field_name: item for item in _WEATHER_FIELD_SPECS}

REQUIRED_WEATHER_FIELD_NAMES = (
    "timestamp_utc",
    "dry_bulb_air_temperature_c",
)

IRRADIANCE_FIELD_NAMES = (
    "global_horizontal_irradiance_w_per_m2",
    "direct_beam_irradiance_w_per_m2",
    "diffuse_horizontal_irradiance_w_per_m2",
)

DEFERRED_STANDARD_WEATHER_FIELD_NAMES = tuple(
    item.field_name for item in _WEATHER_FIELD_SPECS if item.deferred_by_default
)


def iter_weather_field_specs() -> tuple[WeatherFieldSpec, ...]:
    """Return the ordered canonical field metadata for the MVP subset."""

    return _WEATHER_FIELD_SPECS


def get_weather_field_spec(field_name: str) -> WeatherFieldSpec:
    """Return canonical field metadata or fail fast on unknown names."""

    try:
        return _SPECS_BY_FIELD_NAME[field_name]
    except KeyError as exc:
        raise ValueError(
            f"unknown weather field '{field_name}'; use the canonical human-readable field name"
        ) from exc


def canonical_tmy_label(field_name: str) -> str:
    """Return the canonical TMY source label for one field."""

    return get_weather_field_spec(field_name).tmy_label


def is_deferred_standard_weather_field(field_name: str) -> bool:
    """Report whether a field is standard but deferred by default for the MVP."""

    return get_weather_field_spec(field_name).deferred_by_default


def validate_weather_field_names(field_names: Iterable[str]) -> tuple[str, ...]:
    """Validate canonical weather field names while preserving input order."""

    validated: list[str] = []
    seen: set[str] = set()
    for field_name in field_names:
        spec = get_weather_field_spec(field_name)
        if spec.field_name in seen:
            raise ValueError(f"duplicate weather field '{field_name}'")
        seen.add(spec.field_name)
        validated.append(spec.field_name)
    return tuple(validated)


__all__ = [
    "DEFERRED_STANDARD_WEATHER_FIELD_NAMES",
    "IRRADIANCE_FIELD_NAMES",
    "REQUIRED_WEATHER_FIELD_NAMES",
    "WeatherFieldSpec",
    "canonical_tmy_label",
    "get_weather_field_spec",
    "is_deferred_standard_weather_field",
    "iter_weather_field_specs",
    "validate_weather_field_names",
]
