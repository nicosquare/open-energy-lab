"""Integration coverage for supported and unsupported visualization comparison."""

from __future__ import annotations

import importlib

import pytest

from tests.integration.visualization.arbitrage_result_utils import (
    build_controller_arbitrage_result,
    build_direct_arbitrage_trace,
)
from tests.integration.visualization.battery_load_pv_result_utils import (
    build_direct_battery_load_pv_trace,
)


def _comparison_module():
    return importlib.import_module("open_energy_lab.visualization.comparison")


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def test_supported_same_family_comparison_uses_the_canonical_arbitrage_surface() -> None:
    comparison_module = _comparison_module()
    inspection_module = _inspection_module()

    direct_scenario, direct_trace = build_direct_arbitrage_trace()
    _, controller_result = build_controller_arbitrage_result()

    left_view = inspection_module.build_inspection_view(direct_trace, scenario=direct_scenario)
    right_view = inspection_module.build_inspection_view(controller_result)

    comparison = comparison_module.compare_inspection_views(left_view, right_view)

    assert comparison["scenario_kind"] == "ArbitrageScenario"
    assert comparison["left_run"]["source_kind"] == "simulation_trace"
    assert comparison["right_run"]["source_kind"] == "controller_evaluation"
    assert [entry["series_name"] for entry in comparison["aligned_series"]] == [
        "battery_soc",
        "requested_power_kw",
        "realized_power_kw",
        "import_price",
        "step_settlement",
    ]

    series_differences = {
        entry["series_name"]: entry for entry in comparison["series_differences"]
    }
    for series_name in (
        "battery_soc",
        "requested_power_kw",
        "realized_power_kw",
        "import_price",
        "step_settlement",
    ):
        assert series_differences[series_name]["delta_values"] == pytest.approx(
            [0.0, 0.0, 0.0],
            abs=1e-6,
        )

    summary_differences = {
        entry["summary_name"]: entry for entry in comparison["summary_differences"]
    }
    assert summary_differences["total_settlement"]["delta_value"] == pytest.approx(
        0.0,
        abs=1e-6,
    )
    assert comparison.get("unsupported_reason") is None


def test_cross_family_comparison_returns_a_deterministic_unsupported_response() -> None:
    comparison_module = _comparison_module()
    inspection_module = _inspection_module()

    direct_arbitrage_scenario, direct_arbitrage_trace = build_direct_arbitrage_trace()
    direct_battery_load_pv_scenario, direct_battery_load_pv_trace = (
        build_direct_battery_load_pv_trace()
    )

    left_view = inspection_module.build_inspection_view(
        direct_arbitrage_trace,
        scenario=direct_arbitrage_scenario,
    )
    right_view = inspection_module.build_inspection_view(
        direct_battery_load_pv_trace,
        scenario=direct_battery_load_pv_scenario,
    )

    comparison = comparison_module.compare_inspection_views(left_view, right_view)

    assert comparison["left_run"] == {
        "scenario_id": left_view["scenario_id"],
        "source_kind": "simulation_trace",
    }
    assert comparison["right_run"] == {
        "scenario_id": right_view["scenario_id"],
        "source_kind": "simulation_trace",
    }
    assert comparison["aligned_series"] == []
    assert comparison["series_differences"] == []
    assert comparison["summary_differences"] == []
    assert "cross-family" in comparison["unsupported_reason"]
