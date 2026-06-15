"""Minimal deterministic weather inputs for PV derivation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._weather_schema import (
    CANONICAL_WEATHER_FIELD_NAMES,
    DEFERRED_STANDARD_WEATHER_FIELD_NAMES,
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


def weather_component_from_sampled_trace(
    trace: object,
    *,
    time_grid: TimeGrid | None = None,
    name: str | None = None,
    notes: str | None = None,
) -> WeatherComponent:
    """Adapt one sampled canonical weather trace into simulator-owned inputs."""

    from .scenario import TimeGrid

    timestamp_utc = _string_sequence(
        _trace_value(trace, "timestamp_utc"),
        field_name="timestamp_utc",
    )
    timestep_hours = _float_value(
        _trace_value(trace, "timestep_hours"),
        field_name="timestep_hours",
    )
    canonical_field_series = _canonical_field_series(trace)
    expected_fields = tuple(
        field_name
        for field_name in CANONICAL_WEATHER_FIELD_NAMES
        if field_name != "timestamp_utc"
    )
    missing = [field_name for field_name in expected_fields if field_name not in canonical_field_series]
    unexpected = [
        field_name for field_name in canonical_field_series if field_name not in expected_fields
    ]
    if missing:
        raise ValueError(
            "sampled weather trace is missing canonical fields required by the stable artifact contract: "
            + ", ".join(missing)
        )
    if unexpected:
        raise ValueError(
            "sampled weather trace contains unsupported canonical fields for simulator adaptation: "
            + ", ".join(unexpected)
        )

    weather_time_grid = time_grid or TimeGrid(
        num_steps=len(timestamp_utc),
        time_step_hours=timestep_hours,
    )
    if len(timestamp_utc) != weather_time_grid.num_steps:
        raise ValueError("sampled weather trace length must match the scenario time grid")
    if weather_time_grid.time_step_hours != timestep_hours:
        raise ValueError(
            "sampled weather trace timestep_hours must match the scenario time grid"
        )

    scenario_index = _trace_value(trace, "scenario_index")
    source = str(_trace_value(trace, "derived_identity"))
    component_name = name or f"sampled-weather-{scenario_index}"

    return WeatherComponent(
        name=component_name,
        time_grid=weather_time_grid,
        timestamp_utc=list(timestamp_utc),
        dry_bulb_air_temperature_c=_numeric_series(
            canonical_field_series["dry_bulb_air_temperature_c"],
            field_name="dry_bulb_air_temperature_c",
            expected_length=weather_time_grid.num_steps,
        ),
        global_horizontal_irradiance_w_per_m2=_numeric_series(
            canonical_field_series["global_horizontal_irradiance_w_per_m2"],
            field_name="global_horizontal_irradiance_w_per_m2",
            expected_length=weather_time_grid.num_steps,
        ),
        direct_beam_irradiance_w_per_m2=_numeric_series(
            canonical_field_series["direct_beam_irradiance_w_per_m2"],
            field_name="direct_beam_irradiance_w_per_m2",
            expected_length=weather_time_grid.num_steps,
        ),
        diffuse_horizontal_irradiance_w_per_m2=_numeric_series(
            canonical_field_series["diffuse_horizontal_irradiance_w_per_m2"],
            field_name="diffuse_horizontal_irradiance_w_per_m2",
            expected_length=weather_time_grid.num_steps,
        ),
        deferred_fields=DEFERRED_STANDARD_WEATHER_FIELD_NAMES,
        source=source,
        notes=notes,
    )


def _trace_value(trace: object, field_name: str) -> object:
    if isinstance(trace, Mapping):
        if field_name not in trace:
            raise ValueError(f"sampled weather trace is missing {field_name!r}")
        return trace[field_name]
    if not hasattr(trace, field_name):
        raise ValueError(f"sampled weather trace is missing {field_name!r}")
    return getattr(trace, field_name)


def _canonical_field_series(trace: object) -> Mapping[str, object]:
    series = _trace_value(trace, "canonical_field_series")
    if not isinstance(series, Mapping):
        raise TypeError("sampled weather trace canonical_field_series must be a mapping")
    return series


def _float_value(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a string sequence")
    return tuple(str(item) for item in value)


def _numeric_series(
    value: object,
    *,
    field_name: str,
    expected_length: int,
) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a numeric sequence")
    series = [float(item) for item in value]
    if len(series) != expected_length:
        raise ValueError(f"{field_name} length must match the scenario time grid")
    return series


__all__ = ["WeatherComponent", "weather_component_from_sampled_trace"]
