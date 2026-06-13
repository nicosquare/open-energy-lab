"""Offline weather-sampling placeholders for the stochastic-weather feature."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WeatherSamplingRequest:
    """Minimal placeholder for the planned family-sampling request surface."""

    num_steps: int
    scenario_count: int
    family_seed: int


def sample_weather_family(*args: object, **kwargs: object) -> object:
    """Reserve the planned offline family-sampling entry point."""

    raise NotImplementedError(
        "Offline weather sampling is planned but not implemented in the foundational scaffolding."
    )


__all__ = ["WeatherSamplingRequest", "sample_weather_family"]
