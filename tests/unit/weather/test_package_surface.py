"""Package-surface maturity checks for the planned weather package."""

from __future__ import annotations

import importlib
import importlib.util
import sys


WEATHER_PACKAGE = "open_energy_lab.weather"
EXPECTED_ROOT_EXPORTS = [
    "fit_weather_model",
    "fit_weather_dataset",
    "load_weather_artifact",
    "WeatherSamplingRequest",
    "sample_weather_family",
    "PVGISTMYRequestConfig",
    "WeatherCacheUnavailableError",
    "load_or_fetch_tmy_dataset",
]


def _weather_package_spec():
    try:
        return importlib.util.find_spec(WEATHER_PACKAGE)
    except ModuleNotFoundError:
        return None


def _clear_weather_modules() -> None:
    for module_name in tuple(sys.modules):
        if module_name == WEATHER_PACKAGE or module_name.startswith(f"{WEATHER_PACKAGE}."):
            sys.modules.pop(module_name, None)


def test_weather_root_surface_stays_explicit_about_stable_exports() -> None:
    if _weather_package_spec() is None:
        assert WEATHER_PACKAGE not in sys.modules
        return

    module = importlib.import_module(WEATHER_PACKAGE)

    assert module.__all__ == EXPECTED_ROOT_EXPORTS
    assert sorted(name for name in dir(module) if name in EXPECTED_ROOT_EXPORTS) == sorted(
        EXPECTED_ROOT_EXPORTS
    )


def test_weather_root_reserves_only_the_documented_public_surface() -> None:
    if _weather_package_spec() is None:
        assert WEATHER_PACKAGE not in sys.modules
        return

    module = importlib.import_module(WEATHER_PACKAGE)

    assert all("." not in export_name for export_name in module.__all__)
    assert "tmy" not in module.__all__
    assert "_canonical" not in module.__all__
