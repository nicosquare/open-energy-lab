"""Unit coverage for the stable inspection-view surface."""

from __future__ import annotations

import importlib

import pytest


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _persistence_module():
    return importlib.import_module("open_energy_lab.visualization._persistence")


def _loaded_arbitrage_persisted_output() -> dict[str, object]:
    persistence = _persistence_module()
    payload = {
        "scenario_id": "persisted-arbitrage-unit",
        "scenario_kind": "ArbitrageScenario",
        "time_step_hours": 1.0,
        "requested_power_kw": [1.0, 0.0, -1.0],
        "realized_power_kw": [1.0, 0.0, -1.0],
        "step_settlement": [-0.1, 0.0, 0.24],
        "trace_payload": {
            "series": {
                "battery_soc": {
                    "values": [0.595, 0.595, 0.4897368421052632],
                    "units": "fraction",
                    "source_field": "states.soc",
                    "display_category": "battery",
                    "step_labels": ["step-0", "step-1", "step-2"],
                },
                "requested_power_kw": {
                    "values": [1.0, 0.0, -1.0],
                    "units": "kw",
                    "source_field": "requested_power_kw",
                    "display_category": "dispatch",
                    "step_labels": ["step-0", "step-1", "step-2"],
                },
                "realized_power_kw": {
                    "values": [1.0, 0.0, -1.0],
                    "units": "kw",
                    "source_field": "realized_power_kw",
                    "display_category": "dispatch",
                    "step_labels": ["step-0", "step-1", "step-2"],
                },
                "import_price": {
                    "values": [0.1, 0.2, 0.3],
                    "units": "usd_per_kwh",
                    "source_field": "price_signal.import_prices",
                    "display_category": "pricing",
                    "step_labels": ["step-0", "step-1", "step-2"],
                },
                "step_settlement": {
                    "values": [-0.1, 0.0, 0.24],
                    "units": "usd",
                    "source_field": "step_settlement",
                    "display_category": "settlement",
                    "step_labels": ["step-0", "step-1", "step-2"],
                },
            },
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
        },
        "summary_payload": {
            "total_settlement": {
                "value": 0.14,
                "units": "usd",
                "source_field": "total_settlement",
                "display_group": "settlement",
            }
        },
        "provenance_notes": [
            "Synthetic persisted output used only for unit-level inspection coverage."
        ],
    }
    return persistence.load_persisted_run_output(payload)


def test_build_inspection_view_preserves_series_order_and_availability_markers() -> None:
    module = _inspection_module()

    view = module.build_inspection_view(_loaded_arbitrage_persisted_output())

    assert view["scenario_id"] == "persisted-arbitrage-unit"
    assert view["scenario_kind"] == "ArbitrageScenario"
    assert view["maturity"] == "stable"
    assert view["source_kind"] == "persisted_output"
    assert [series["series_name"] for series in view["trace_series"]] == [
        "battery_soc",
        "requested_power_kw",
        "realized_power_kw",
        "import_price",
        "step_settlement",
    ]
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


def test_summarize_inspection_view_extracts_deterministic_summary_outcomes() -> None:
    module = _inspection_module()
    view = module.build_inspection_view(_loaded_arbitrage_persisted_output())

    summary = module.summarize_inspection_view(view)

    assert summary["scenario_id"] == "persisted-arbitrage-unit"
    assert summary["scenario_kind"] == "ArbitrageScenario"
    assert summary["source_kind"] == "persisted_output"
    assert [item["summary_name"] for item in summary["summary_outcomes"]] == [
        "total_settlement"
    ]
    assert summary["summary_outcomes"][0]["value"] == pytest.approx(0.14, abs=1e-6)
    assert summary["summary_outcomes"][0]["units"] == "usd"
    assert summary["available_sections"]["weather"] is False
