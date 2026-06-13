"""Integration coverage for battery-load-PV inspection over current result objects."""

from __future__ import annotations

import importlib

import pytest

from tests.integration.visualization.battery_load_pv_result_utils import (
    build_controller_battery_load_pv_result,
    build_direct_battery_load_pv_trace,
    load_controller_battery_load_pv_fixture,
)


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _series_by_name(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {series["series_name"]: series for series in view["trace_series"]}


def _summary_by_name(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["summary_name"]: item for item in view["summary_outcomes"]}


def _assert_series_values(actual: list[object], expected: list[object], *, tolerance: float) -> None:
    if expected and isinstance(expected[0], str):
        assert actual == expected
        return
    assert actual == pytest.approx(expected, abs=tolerance)


def test_battery_load_pv_trace_and_controller_result_share_the_weather_aware_view_surface() -> None:
    module = _inspection_module()
    fixture = load_controller_battery_load_pv_fixture()

    direct_scenario, direct_trace = build_direct_battery_load_pv_trace()
    _, controller_result = build_controller_battery_load_pv_result()

    direct_view = module.build_inspection_view(direct_trace, scenario=direct_scenario)
    controller_view = module.build_inspection_view(controller_result)

    assert direct_view["scenario_id"] == fixture["case_id"]
    assert controller_view["scenario_id"] == fixture["case_id"]
    assert direct_view["scenario_kind"] == "BatteryLoadPVScenario"
    assert controller_view["scenario_kind"] == "BatteryLoadPVScenario"
    assert direct_view["maturity"] == "stable"
    assert controller_view["maturity"] == "stable"
    assert direct_view["source_kind"] == "simulation_trace"
    assert controller_view["source_kind"] == "controller_evaluation"

    expected_sections = {
        "battery": True,
        "dispatch": True,
        "pricing": True,
        "settlement": True,
        "load": True,
        "pv": True,
        "net_grid": True,
        "weather": True,
    }
    assert direct_view["available_sections"] == expected_sections
    assert controller_view["available_sections"] == expected_sections

    direct_series = _series_by_name(direct_view)
    controller_series = _series_by_name(controller_view)
    assert list(direct_series) == list(controller_series)

    tolerance = fixture["numeric_tolerance"]
    expected_trace = fixture["expected_trace"]
    expected_weather = fixture["weather"]
    expected_pricing = fixture["pricing"]

    _assert_series_values(
        direct_series["battery_soc"]["values"],
        expected_trace["soc"],
        tolerance=tolerance,
    )
    _assert_series_values(
        controller_series["battery_soc"]["values"],
        expected_trace["soc"],
        tolerance=tolerance,
    )
    for series_name in (
        "requested_power_kw",
        "realized_power_kw",
        "load_kw",
        "pv_generation_kw",
        "net_grid_power_kw",
        "net_grid_energy_kwh",
        "step_settlement",
    ):
        _assert_series_values(
            direct_series[series_name]["values"],
            expected_trace[series_name],
            tolerance=tolerance,
        )
        _assert_series_values(
            controller_series[series_name]["values"],
            expected_trace[series_name],
            tolerance=tolerance,
        )

    _assert_series_values(
        direct_series["direction"]["values"],
        expected_trace["direction"],
        tolerance=tolerance,
    )
    _assert_series_values(
        controller_series["direction"]["values"],
        expected_trace["direction"],
        tolerance=tolerance,
    )
    _assert_series_values(
        direct_series["import_price"]["values"],
        expected_pricing["import_prices"],
        tolerance=tolerance,
    )
    _assert_series_values(
        controller_series["import_price"]["values"],
        expected_pricing["import_prices"],
        tolerance=tolerance,
    )
    _assert_series_values(
        direct_series["timestamp_utc"]["values"],
        expected_weather["timestamp_utc"]["values"],
        tolerance=tolerance,
    )
    _assert_series_values(
        controller_series["timestamp_utc"]["values"],
        expected_weather["timestamp_utc"]["values"],
        tolerance=tolerance,
    )
    for series_name in (
        "dry_bulb_air_temperature_c",
        "global_horizontal_irradiance_w_per_m2",
    ):
        _assert_series_values(
            direct_series[series_name]["values"],
            expected_weather[series_name]["values"],
            tolerance=tolerance,
        )
        _assert_series_values(
            controller_series[series_name]["values"],
            expected_weather[series_name]["values"],
            tolerance=tolerance,
        )

    direct_summary = _summary_by_name(direct_view)
    controller_summary = _summary_by_name(controller_view)
    assert direct_summary["total_settlement"]["value"] == pytest.approx(
        expected_trace["total_settlement"],
        abs=tolerance,
    )
    assert controller_summary["total_settlement"]["value"] == pytest.approx(
        expected_trace["total_settlement"],
        abs=tolerance,
    )
