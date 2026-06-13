"""Artifact-fitting placeholders for the stochastic-weather feature."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WeatherFitConfig:
    """Minimal placeholder for the planned fit-configuration surface."""

    timestep_hours: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def fit_weather_model(*args: object, **kwargs: object) -> object:
    """Reserve the planned weather-artifact fitting entry point."""

    raise NotImplementedError(
        "Weather-model fitting is planned but not implemented in the foundational scaffolding."
    )


__all__ = ["WeatherFitConfig", "fit_weather_model"]
