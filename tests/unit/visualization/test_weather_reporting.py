"""Unit coverage for weather-aware visualization inspection reporting."""

from __future__ import annotations

import importlib

from tests.integration.visualization.arbitrage_result_utils import (
    build_direct_arbitrage_trace,
    make_persisted_arbitrage_output,
)
from tests.integration.visualization.battery_load_pv_result_utils import (
    build_direct_battery_load_pv_trace,
    make_persisted_battery_load_pv_output,
)


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _persistence_module():
    return importlib.import_module("open_energy_lab.visualization._persistence")


def _series_by_name(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {series["series_name"]: series for series in view["trace_series"]}


def test_weather_backed_persisted_outputs_keep_optional_sections_explicitly_present() -> None:
    inspection = _inspection_module()
    persistence = _persistence_module()

    scenario, trace = build_direct_battery_load_pv_trace()
    loaded_output = persistence.load_persisted_run_output(
        make_persisted_battery_load_pv_output(scenario, trace)
    )

    view = inspection.build_inspection_view(loaded_output)
    series = _series_by_name(view)

    assert view["scenario_kind"] == "BatteryLoadPVScenario"
    assert view["available_sections"] == {
        "battery": True,
        "dispatch": True,
        "pricing": True,
        "settlement": True,
        "load": True,
        "pv": True,
        "net_grid": True,
        "weather": True,
    }
    assert series["timestamp_utc"]["values"] == list(scenario.weather.timestamp_utc)
    assert series["dry_bulb_air_temperature_c"]["values"] == list(
        scenario.weather.dry_bulb_air_temperature_c
    )
    assert series["global_horizontal_irradiance_w_per_m2"]["values"] == list(
        scenario.weather.global_horizontal_irradiance_w_per_m2 or []
    )


def test_non_weather_runs_keep_optional_sections_explicitly_absent() -> None:
    inspection = _inspection_module()
    persistence = _persistence_module()

    scenario, trace = build_direct_arbitrage_trace()
    loaded_output = persistence.load_persisted_run_output(
        make_persisted_arbitrage_output(scenario, trace)
    )

    view = inspection.build_inspection_view(loaded_output)
    series_names = {series["series_name"] for series in view["trace_series"]}

    assert view["scenario_kind"] == "ArbitrageScenario"
    assert view["available_sections"] == {
        "battery": True,
        "dispatch": True,
        "pricing": True,
        "settlement": True,
        "load": False,
        "pv": False,
        "net_grid": False,
        "weather": False,
    }
    assert "timestamp_utc" not in series_names
    assert "dry_bulb_air_temperature_c" not in series_names
    assert "global_horizontal_irradiance_w_per_m2" not in series_names
