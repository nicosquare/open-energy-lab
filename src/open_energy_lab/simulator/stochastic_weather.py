"""Import-light stochastic-weather simulator placeholders.

This module reserves the simulator-owned family-evaluation surface without
changing the current deterministic BatteryLoadPVScenario behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WeatherFamilyEvaluationRequest:
    """Placeholder for the future simulator-side family evaluation request."""

    family_id: str
    scenario_count: int
    num_steps: int
    summary_output_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class WeatherFamilyEvaluationResult:
    """Placeholder for the future simulator-side family evaluation result."""

    family_id: str
    supported_summary_fields: tuple[str, ...] = field(default_factory=tuple)


def evaluate_weather_family(*args: object, **kwargs: object) -> WeatherFamilyEvaluationResult:
    """Reserve the planned simulator weather-family evaluation entry point."""

    raise NotImplementedError(
        "Simulator stochastic weather evaluation is planned but not implemented in the foundational scaffolding."
    )


__all__ = [
    "WeatherFamilyEvaluationRequest",
    "WeatherFamilyEvaluationResult",
    "evaluate_weather_family",
]
