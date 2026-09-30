"""Import-boundary tests for the planned weather package."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


WEATHER_PACKAGE = "open_energy_lab.weather"
PLANNED_WEATHER_SUBMODULES = (
    "open_energy_lab.weather._canonical",
    "open_energy_lab.weather.tmy",
    "open_energy_lab.weather.fit",
    "open_energy_lab.weather.artifact",
    "open_energy_lab.weather.sampling",
    "open_energy_lab.weather.events",
)


def test_weather_package_root_reserves_a_lightweight_public_boundary() -> None:
    module_spec = importlib.util.find_spec(WEATHER_PACKAGE)
    if module_spec is None:
        assert WEATHER_PACKAGE not in sys.modules
        return

    module = importlib.import_module(WEATHER_PACKAGE)

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "weather"
    assert module_file.parent.parent.name == "open_energy_lab"


def test_planned_weather_submodules_stay_within_the_reserved_package_boundary() -> None:
    package_spec = importlib.util.find_spec(WEATHER_PACKAGE)
    if package_spec is None:
        for module_name in PLANNED_WEATHER_SUBMODULES:
            try:
                module_spec = importlib.util.find_spec(module_name)
            except ModuleNotFoundError:
                module_spec = None
            assert module_spec is None
            assert module_name not in sys.modules
        return

    package = importlib.import_module(WEATHER_PACKAGE)
    package_dir = Path(package.__file__).resolve().parent

    for module_name in PLANNED_WEATHER_SUBMODULES:
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None:
            assert module_name not in sys.modules
            continue

        module = importlib.import_module(module_name)

        assert module_spec.origin is not None
        assert module.__file__ is not None
        assert Path(module_spec.origin).resolve().parent == package_dir
        assert Path(module.__file__).resolve().parent == package_dir
