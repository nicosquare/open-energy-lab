"""Regression coverage for comparison unsupported-case handling."""

from __future__ import annotations

from copy import deepcopy
import importlib

from tests.integration.visualization.arbitrage_result_utils import (
    build_controller_arbitrage_result,
    build_direct_arbitrage_trace,
)


def _comparison_module():
    return importlib.import_module("open_energy_lab.visualization.comparison")


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _remove_series(view: dict[str, object], series_name: str) -> dict[str, object]:
    updated_view = deepcopy(view)
    updated_view["trace_series"] = [
        series
        for series in updated_view["trace_series"]
        if series["series_name"] != series_name
    ]
    return updated_view


def _shorten_series(view: dict[str, object], series_name: str) -> dict[str, object]:
    updated_view = deepcopy(view)
    for series in updated_view["trace_series"]:
        if series["series_name"] != series_name:
            continue
        series["values"] = series["values"][:-1]
        series["step_labels"] = series["step_labels"][:-1]
        break
    return updated_view


def test_missing_series_returns_a_deterministic_unsupported_response() -> None:
    comparison_module = _comparison_module()
    inspection_module = _inspection_module()

    direct_scenario, direct_trace = build_direct_arbitrage_trace()
    _, controller_result = build_controller_arbitrage_result()

    left_view = inspection_module.build_inspection_view(direct_trace, scenario=direct_scenario)
    right_view = inspection_module.build_inspection_view(controller_result)
    missing_series_view = _remove_series(right_view, "requested_power_kw")

    comparison = comparison_module.compare_inspection_views(left_view, missing_series_view)

    assert comparison["aligned_series"] == []
    assert comparison["series_differences"] == []
    assert comparison["summary_differences"] == []
    assert "requested_power_kw" in comparison["unsupported_reason"]


def test_incompatible_series_lengths_return_a_deterministic_unsupported_response() -> None:
    comparison_module = _comparison_module()
    inspection_module = _inspection_module()

    direct_scenario, direct_trace = build_direct_arbitrage_trace()
    _, controller_result = build_controller_arbitrage_result()

    left_view = inspection_module.build_inspection_view(direct_trace, scenario=direct_scenario)
    right_view = inspection_module.build_inspection_view(controller_result)
    incompatible_length_view = _shorten_series(right_view, "step_settlement")

    comparison = comparison_module.compare_inspection_views(left_view, incompatible_length_view)

    assert comparison["aligned_series"] == []
    assert comparison["series_differences"] == []
    assert comparison["summary_differences"] == []
    assert "step_settlement" in comparison["unsupported_reason"]
    assert "length" in comparison["unsupported_reason"]
