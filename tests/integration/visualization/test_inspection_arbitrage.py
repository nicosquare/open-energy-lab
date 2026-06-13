"""Integration coverage for arbitrage inspection over current result objects."""

from __future__ import annotations

import importlib

import pytest

from tests.integration.visualization.arbitrage_result_utils import (
    build_controller_arbitrage_result,
    build_direct_arbitrage_trace,
    load_controller_arbitrage_fixture,
)


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _series_by_name(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {series["series_name"]: series for series in view["trace_series"]}


def _summary_by_name(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["summary_name"]: item for item in view["summary_outcomes"]}


def test_arbitrage_trace_and_controller_result_share_the_stable_view_surface() -> None:
    module = _inspection_module()
    fixture = load_controller_arbitrage_fixture()

    direct_scenario, direct_trace = build_direct_arbitrage_trace()
    _, controller_result = build_controller_arbitrage_result()

    direct_view = module.build_inspection_view(direct_trace, scenario=direct_scenario)
    controller_view = module.build_inspection_view(controller_result)

    assert direct_view["scenario_id"] == fixture["case_id"]
    assert controller_view["scenario_id"] == fixture["case_id"]
    assert direct_view["scenario_kind"] == "ArbitrageScenario"
    assert controller_view["scenario_kind"] == "ArbitrageScenario"
    assert direct_view["maturity"] == "stable"
    assert controller_view["maturity"] == "stable"
    assert direct_view["source_kind"] == "simulation_trace"
    assert controller_view["source_kind"] == "controller_evaluation"

    expected_sections = {
        "battery": True,
        "dispatch": True,
        "pricing": True,
        "settlement": True,
        "load": False,
        "pv": False,
        "net_grid": False,
        "weather": False,
    }
    assert direct_view["available_sections"] == expected_sections
    assert controller_view["available_sections"] == expected_sections

    direct_series = _series_by_name(direct_view)
    controller_series = _series_by_name(controller_view)
    assert list(direct_series) == [
        "battery_soc",
        "requested_power_kw",
        "realized_power_kw",
        "import_price",
        "step_settlement",
    ]
    assert list(controller_series) == list(direct_series)

    assert direct_series["requested_power_kw"]["values"] == pytest.approx(
        fixture["expected_trace"]["requested_power_kw"],
        abs=fixture["numeric_tolerance"],
    )
    assert controller_series["requested_power_kw"]["values"] == pytest.approx(
        fixture["expected_trace"]["requested_power_kw"],
        abs=fixture["numeric_tolerance"],
    )
    assert direct_series["realized_power_kw"]["values"] == pytest.approx(
        fixture["expected_trace"]["realized_power_kw"],
        abs=fixture["numeric_tolerance"],
    )
    assert controller_series["realized_power_kw"]["values"] == pytest.approx(
        fixture["expected_trace"]["realized_power_kw"],
        abs=fixture["numeric_tolerance"],
    )
    assert direct_series["battery_soc"]["values"] == pytest.approx(
        fixture["expected_trace"]["soc"],
        abs=fixture["numeric_tolerance"],
    )
    assert controller_series["battery_soc"]["values"] == pytest.approx(
        fixture["expected_trace"]["soc"],
        abs=fixture["numeric_tolerance"],
    )
    assert direct_series["import_price"]["values"] == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)
    assert controller_series["import_price"]["values"] == pytest.approx(
        [0.1, 0.2, 0.3],
        abs=1e-6,
    )
    assert direct_series["step_settlement"]["values"] == pytest.approx(
        fixture["expected_trace"]["step_settlement"],
        abs=fixture["numeric_tolerance"],
    )
    assert controller_series["step_settlement"]["values"] == pytest.approx(
        fixture["expected_trace"]["step_settlement"],
        abs=fixture["numeric_tolerance"],
    )

    direct_summary = _summary_by_name(direct_view)
    controller_summary = _summary_by_name(controller_view)
    assert direct_summary["total_settlement"]["value"] == pytest.approx(
        fixture["expected_trace"]["total_settlement"],
        abs=fixture["numeric_tolerance"],
    )
    assert controller_summary["total_settlement"]["value"] == pytest.approx(
        fixture["expected_trace"]["total_settlement"],
        abs=fixture["numeric_tolerance"],
    )
