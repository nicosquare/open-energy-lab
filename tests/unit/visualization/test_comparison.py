"""Unit coverage for same-family visualization comparison."""

from __future__ import annotations

import importlib

import pytest


def _comparison_module():
    return importlib.import_module("open_energy_lab.visualization.comparison")


def _inspection_view(
    *,
    scenario_id: str,
    source_kind: str,
    battery_soc: list[float],
    requested_power_kw: list[float],
    step_settlement: list[float],
    total_settlement: float,
) -> dict[str, object]:
    step_labels = [f"step-{index}" for index in range(len(battery_soc))]
    return {
        "scenario_id": scenario_id,
        "scenario_kind": "ArbitrageScenario",
        "trace_series": [
            {
                "series_name": "battery_soc",
                "values": battery_soc,
                "units": "fraction",
                "source_field": "states.soc",
                "display_category": "battery",
                "step_labels": step_labels,
                "optional": False,
            },
            {
                "series_name": "requested_power_kw",
                "values": requested_power_kw,
                "units": "kw",
                "source_field": "requested_power_kw",
                "display_category": "dispatch",
                "step_labels": step_labels,
                "optional": False,
            },
            {
                "series_name": "step_settlement",
                "values": step_settlement,
                "units": "usd",
                "source_field": "step_settlement",
                "display_category": "settlement",
                "step_labels": step_labels,
                "optional": False,
            },
        ],
        "summary_outcomes": [
            {
                "summary_name": "total_settlement",
                "value": total_settlement,
                "units": "usd",
                "source_field": "total_settlement",
                "display_group": "settlement",
            }
        ],
        "available_sections": {
            "battery": True,
            "dispatch": True,
            "pricing": True,
            "settlement": True,
            "load": False,
            "pv": False,
            "net_grid": False,
            "weather": False,
        },
        "maturity": "stable",
        "source_kind": source_kind,
    }


def test_compare_inspection_views_aligns_shared_series_and_computes_summary_deltas() -> None:
    module = _comparison_module()
    left_view = _inspection_view(
        scenario_id="left-arbitrage",
        source_kind="simulation_trace",
        battery_soc=[0.50, 0.60, 0.48],
        requested_power_kw=[1.0, 0.0, -1.0],
        step_settlement=[-0.10, 0.00, 0.24],
        total_settlement=0.14,
    )
    right_view = _inspection_view(
        scenario_id="right-arbitrage",
        source_kind="controller_evaluation",
        battery_soc=[0.55, 0.58, 0.46],
        requested_power_kw=[1.0, 1.0, -1.0],
        step_settlement=[-0.10, -0.20, 0.24],
        total_settlement=-0.06,
    )

    comparison = module.compare_inspection_views(left_view, right_view)

    assert comparison["scenario_kind"] == "ArbitrageScenario"
    assert comparison["left_run"] == {
        "scenario_id": "left-arbitrage",
        "source_kind": "simulation_trace",
    }
    assert comparison["right_run"] == {
        "scenario_id": "right-arbitrage",
        "source_kind": "controller_evaluation",
    }
    assert [entry["series_name"] for entry in comparison["aligned_series"]] == [
        "battery_soc",
        "requested_power_kw",
        "step_settlement",
    ]

    aligned_series = {
        entry["series_name"]: entry for entry in comparison["aligned_series"]
    }
    assert aligned_series["battery_soc"]["step_labels"] == ["step-0", "step-1", "step-2"]
    assert aligned_series["battery_soc"]["left_values"] == pytest.approx(
        [0.50, 0.60, 0.48],
        abs=1e-6,
    )
    assert aligned_series["battery_soc"]["right_values"] == pytest.approx(
        [0.55, 0.58, 0.46],
        abs=1e-6,
    )

    series_differences = {
        entry["series_name"]: entry for entry in comparison["series_differences"]
    }
    assert series_differences["battery_soc"]["delta_values"] == pytest.approx(
        [0.05, -0.02, -0.02],
        abs=1e-6,
    )
    assert series_differences["requested_power_kw"]["delta_values"] == pytest.approx(
        [0.0, 1.0, 0.0],
        abs=1e-6,
    )
    assert series_differences["step_settlement"]["delta_values"] == pytest.approx(
        [0.0, -0.2, 0.0],
        abs=1e-6,
    )

    summary_differences = {
        entry["summary_name"]: entry for entry in comparison["summary_differences"]
    }
    assert summary_differences["total_settlement"] == {
        "summary_name": "total_settlement",
        "units": "usd",
        "left_value": pytest.approx(0.14, abs=1e-6),
        "right_value": pytest.approx(-0.06, abs=1e-6),
        "delta_value": pytest.approx(-0.20, abs=1e-6),
    }
    assert comparison.get("unsupported_reason") is None


def test_compare_inspection_views_is_deterministic_for_repeated_requests() -> None:
    module = _comparison_module()
    left_view = _inspection_view(
        scenario_id="deterministic-left",
        source_kind="simulation_trace",
        battery_soc=[0.50, 0.60, 0.48],
        requested_power_kw=[1.0, 0.0, -1.0],
        step_settlement=[-0.10, 0.00, 0.24],
        total_settlement=0.14,
    )
    right_view = _inspection_view(
        scenario_id="deterministic-right",
        source_kind="persisted_output",
        battery_soc=[0.50, 0.60, 0.50],
        requested_power_kw=[1.0, 0.5, -1.0],
        step_settlement=[-0.10, -0.10, 0.24],
        total_settlement=0.04,
    )

    first = module.compare_inspection_views(left_view, right_view)
    second = module.compare_inspection_views(left_view, right_view)

    assert first == second
