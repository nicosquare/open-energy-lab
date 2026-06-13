"""Schema validation for supported persisted visualization inputs."""

from __future__ import annotations

import importlib

import pytest


def _load_persistence_module():
    return importlib.import_module("open_energy_lab.visualization._persistence")


def _make_valid_arbitrage_payload() -> dict[str, object]:
    return {
        "scenario_id": "arbitrage-case",
        "scenario_kind": "ArbitrageScenario",
        "time_step_hours": 1.0,
        "requested_power_kw": [1.0, 0.0, -1.0],
        "realized_power_kw": [1.0, 0.0, -1.0],
        "step_settlement": [0.4, 0.0, -0.2],
        "trace_payload": {
            "series": {
                "battery_soc": {
                    "values": [0.5, 0.75, 0.5],
                    "units": "fraction",
                    "source_field": "soc",
                    "display_category": "battery",
                },
                "price_import": {
                    "values": [0.10, 0.20, 0.30],
                    "units": "usd_per_kwh",
                    "source_field": "import_price",
                    "display_category": "pricing",
                    "step_labels": ["t0", "t1", "t2"],
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
                "value": 0.2,
                "units": "usd",
                "source_field": "total_settlement",
                "display_group": "settlement",
            }
        },
        "provenance_notes": [
            "Synthetic unit-test payload for arbitrage persisted-output validation."
        ],
    }


def _make_valid_battery_load_pv_payload() -> dict[str, object]:
    return {
        "scenario_id": "battery-load-pv-case",
        "scenario_kind": "BatteryLoadPVScenario",
        "time_step_hours": 1,
        "requested_power_kw": [0.0, 0.5, -0.5],
        "realized_power_kw": [0.0, 0.5, -0.5],
        "step_settlement": [0.0, 0.1, -0.1],
        "trace_payload": {
            "series": {
                "load_kw": {
                    "values": [2.0, 1.5, 1.0],
                    "units": "kw",
                    "source_field": "load",
                    "display_category": "load",
                },
                "timestamp_utc": {
                    "values": [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T01:00:00Z",
                        "2026-01-01T02:00:00Z",
                    ],
                    "units": "iso8601",
                    "source_field": "timestamp_utc",
                    "display_category": "weather",
                },
            },
            "available_sections": {
                "battery": True,
                "dispatch": True,
                "pricing": True,
                "settlement": True,
                "load": True,
                "pv": True,
                "net_grid": True,
                "weather": True,
            },
        },
        "summary_payload": {
            "total_settlement": {
                "value": 0.0,
                "units": "usd",
                "source_field": "total_settlement",
                "display_group": "settlement",
            }
        },
        "provenance_notes": [
            "Synthetic unit-test payload for battery-load-PV persisted-output validation."
        ],
    }


def test_normalize_persisted_output_accepts_supported_arbitrage_payload() -> None:
    module = _load_persistence_module()

    normalized = module.normalize_persisted_output(_make_valid_arbitrage_payload())

    assert normalized["scenario_kind"] == "ArbitrageScenario"
    assert normalized["time_step_hours"] == pytest.approx(1.0)
    assert normalized["requested_power_kw"] == [1.0, 0.0, -1.0]
    assert normalized["trace_payload"]["available_sections"]["weather"] is False
    assert normalized["summary_payload"]["total_settlement"]["value"] == pytest.approx(0.2)


def test_normalize_persisted_output_accepts_supported_battery_load_pv_payload() -> None:
    module = _load_persistence_module()

    normalized = module.normalize_persisted_output(_make_valid_battery_load_pv_payload())

    assert normalized["scenario_kind"] == "BatteryLoadPVScenario"
    assert normalized["time_step_hours"] == pytest.approx(1.0)
    assert normalized["trace_payload"]["available_sections"]["weather"] is True
    assert normalized["trace_payload"]["series"]["timestamp_utc"]["values"] == [
        "2026-01-01T00:00:00Z",
        "2026-01-01T01:00:00Z",
        "2026-01-01T02:00:00Z",
    ]


def test_validate_persisted_output_rejects_unsupported_scenario_kind() -> None:
    module = _load_persistence_module()
    payload = _make_valid_arbitrage_payload()
    payload["scenario_kind"] = "UnsupportedScenario"

    with pytest.raises(ValueError, match="scenario_kind must be one of"):
        module.validate_persisted_output(payload)


def test_normalize_persisted_output_rejects_length_mismatches() -> None:
    module = _load_persistence_module()
    payload = _make_valid_arbitrage_payload()
    payload["requested_power_kw"] = [1.0, 0.0]

    with pytest.raises(ValueError, match="requested_power_kw must have length 3"):
        module.normalize_persisted_output(payload)


def test_normalize_persisted_output_requires_explicit_section_availability() -> None:
    module = _load_persistence_module()
    payload = _make_valid_battery_load_pv_payload()
    payload["trace_payload"]["available_sections"]["weather"] = False

    with pytest.raises(ValueError, match="weather=True"):
        module.normalize_persisted_output(payload)


def test_normalize_persisted_output_requires_total_settlement_consistency() -> None:
    module = _load_persistence_module()
    payload = _make_valid_arbitrage_payload()
    payload["summary_payload"]["total_settlement"]["value"] = 0.25

    with pytest.raises(ValueError, match="must match the summed step_settlement"):
        module.normalize_persisted_output(payload)


def test_load_persisted_run_output_delegates_to_normalization() -> None:
    module = _load_persistence_module()

    loaded = module.load_persisted_run_output(_make_valid_arbitrage_payload())

    assert loaded["scenario_id"] == "arbitrage-case"
    assert loaded["realized_power_kw"] == [1.0, 0.0, -1.0]
