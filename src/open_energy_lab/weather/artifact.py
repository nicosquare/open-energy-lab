"""Artifact-loading placeholders for the stochastic-weather feature."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WeatherArtifactPlaceholder:
    """Small import-light stand-in for the future persisted artifact type."""

    artifact_id: str
    schema_version: str
    canonical_field_order: tuple[str, ...] = field(default_factory=tuple)


def load_weather_artifact(*args: object, **kwargs: object) -> WeatherArtifactPlaceholder:
    """Reserve the planned offline artifact-loading entry point."""

    raise NotImplementedError(
        "Weather-artifact loading is planned but not implemented in the foundational scaffolding."
    )


__all__ = ["WeatherArtifactPlaceholder", "load_weather_artifact"]
