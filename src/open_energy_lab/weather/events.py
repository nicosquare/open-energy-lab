"""Cloud-event placeholders for the stochastic-weather feature."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CloudEventAnnotation:
    """Minimal placeholder for contiguous irradiance-event annotations."""

    start_index: int
    duration_steps: int
    attenuation_fraction: float


__all__ = ["CloudEventAnnotation"]
