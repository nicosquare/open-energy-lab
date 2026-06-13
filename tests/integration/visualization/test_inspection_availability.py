"""Regression coverage for explicit inspection availability markers."""

from __future__ import annotations

import importlib

from tests.integration.visualization.arbitrage_result_utils import (
    build_controller_arbitrage_result,
    build_direct_arbitrage_trace,
    make_persisted_arbitrage_output,
)


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _persistence_module():
    return importlib.import_module("open_energy_lab.visualization._persistence")


def test_arbitrage_inputs_do_not_invent_weather_or_battery_load_pv_sections() -> None:
    inspection = _inspection_module()
    persistence = _persistence_module()

    direct_scenario, direct_trace = build_direct_arbitrage_trace()
    _, controller_result = build_controller_arbitrage_result()
    loaded_output = persistence.load_persisted_run_output(
        make_persisted_arbitrage_output(direct_scenario, direct_trace)
    )

    views = (
        inspection.build_inspection_view(direct_trace, scenario=direct_scenario),
        inspection.build_inspection_view(controller_result),
        inspection.build_inspection_view(loaded_output),
    )

    for view in views:
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
        assert "load_kw" not in series_names
        assert "pv_generation_kw" not in series_names
        assert "net_grid_power_kw" not in series_names
        assert "net_grid_energy_kwh" not in series_names
        assert "timestamp_utc" not in series_names
        assert "dry_bulb_air_temperature_c" not in series_names
        assert "global_horizontal_irradiance_w_per_m2" not in series_names
