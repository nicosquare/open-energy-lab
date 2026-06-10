"""Integration coverage for persisted-output inspection reuse."""

from __future__ import annotations

import importlib

import pytest

from tests.integration.visualization.arbitrage_result_utils import (
    build_direct_arbitrage_trace,
    make_persisted_arbitrage_output,
)


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _persistence_module():
    return importlib.import_module("open_energy_lab.visualization._persistence")


def _series_by_name(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {series["series_name"]: series for series in view["trace_series"]}


def _summary_by_name(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["summary_name"]: item for item in view["summary_outcomes"]}


def test_persisted_arbitrage_output_rebuilds_the_same_inspection_surface() -> None:
    inspection = _inspection_module()
    persistence = _persistence_module()

    scenario, trace = build_direct_arbitrage_trace()
    persisted_output = make_persisted_arbitrage_output(scenario, trace)

    loaded_output = persistence.load_persisted_run_output(persisted_output)
    direct_view = inspection.build_inspection_view(trace, scenario=scenario)
    persisted_view = inspection.build_inspection_view(loaded_output)

    assert loaded_output["scenario_id"] == scenario.scenario_id
    assert loaded_output["scenario_kind"] == "ArbitrageScenario"
    assert loaded_output["realized_power_kw"] == pytest.approx(trace.realized_power_kw, abs=1e-6)

    assert direct_view["source_kind"] == "simulation_trace"
    assert persisted_view["source_kind"] == "persisted_output"

    direct_series = _series_by_name(direct_view)
    persisted_series = _series_by_name(persisted_view)
    assert list(persisted_series) == list(direct_series)
    for series_name in direct_series:
        assert persisted_series[series_name]["values"] == pytest.approx(
            direct_series[series_name]["values"],
            abs=1e-6,
        )
        assert persisted_series[series_name]["units"] == direct_series[series_name]["units"]

    direct_summary = _summary_by_name(direct_view)
    persisted_summary = _summary_by_name(persisted_view)
    assert persisted_summary["total_settlement"]["value"] == pytest.approx(
        direct_summary["total_settlement"]["value"],
        abs=1e-6,
    )
    assert persisted_view["available_sections"] == direct_view["available_sections"]
