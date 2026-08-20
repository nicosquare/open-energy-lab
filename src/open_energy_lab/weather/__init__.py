"""Public weather package surface for the stochastic-weather feature.

The stable weather root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .artifact import load_weather_artifact
    from .fit import fit_weather_dataset, fit_weather_model
    from .sampling import WeatherSamplingRequest, sample_weather_family
    from .tmy import (
        PVGISTMYRequestConfig,
        WeatherCacheUnavailableError,
        load_or_fetch_tmy_dataset,
    )


_EXPORT_MAP = {
    "fit_weather_model": (".fit", "fit_weather_model"),
    "fit_weather_dataset": (".fit", "fit_weather_dataset"),
    "load_weather_artifact": (".artifact", "load_weather_artifact"),
    "WeatherSamplingRequest": (".sampling", "WeatherSamplingRequest"),
    "sample_weather_family": (".sampling", "sample_weather_family"),
    "PVGISTMYRequestConfig": (".tmy", "PVGISTMYRequestConfig"),
    "WeatherCacheUnavailableError": (".tmy", "WeatherCacheUnavailableError"),
    "load_or_fetch_tmy_dataset": (".tmy", "load_or_fetch_tmy_dataset"),
}

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


def __getattr__(name: str) -> Any:
    """Lazily resolve the reserved weather package exports."""

    try:
        module_name, attribute_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
