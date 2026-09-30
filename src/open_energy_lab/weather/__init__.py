"""Public weather package surface for the stochastic-weather feature.

The stable weather root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from .artifact import (
    load_weather_artifact,
)
from .fit import (
    fit_weather_dataset,
    fit_weather_model,
)
from .sampling import (
    WeatherSamplingRequest,
    sample_weather_family,
)
from .tmy import (
    PVGISTMYRequestConfig,
    WeatherCacheUnavailableError,
    load_or_fetch_tmy_dataset,
)

__all__ = [
    "fit_weather_model",
    "fit_weather_dataset",
    "load_weather_artifact",
    "WeatherSamplingRequest",
    "sample_weather_family",
    "PVGISTMYRequestConfig",
    "WeatherCacheUnavailableError",
    "load_or_fetch_tmy_dataset",
]
