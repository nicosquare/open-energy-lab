"""Contract tests for the additive reference-result FCR settlement profile."""

from __future__ import annotations

import importlib

import pytest

from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
    build_test_battery,
    build_test_evaluation_case,
)


def _evaluation_module():
    return importlib.import_module("open_energy_lab.simulator.fcr_bid_evaluation")


def _manual_case():
    return build_test_evaluation_case(
        powers_kw=(1.0, 0.0, 0.0, -1.0),
        capacities_kw=(1.0,),
        activation_values=(1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0, -1.0),
        day_ahead_prices_eur_per_mwh=(50.0, 60.0, 70.0, 100.0),
        fcr_capacity_prices_eur_per_kw_block=(0.08,),
        battery=build_test_battery(
            capacity_kwh=5.0,
            max_charge_kw=2.0,
            max_discharge_kw=2.0,
            charge_efficiency=0.8,
            discharge_efficiency=0.8,
            initial_soc=0.5,
            min_soc=0.0,
            max_soc=1.0,
        ),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
    )


def test_reference_profile_reports_independent_revenue_formulas() -> None:
    report = _evaluation_module().evaluate_fixed_fcr_bid(_manual_case().request)
    settlement = report.settlement

    expected_day_ahead = -(1.0 * 1.0 * 50.0 / 1000.0) - (
        -1.0 * 1.0 * 100.0 / 1000.0
    )
    expected_capacity = 1.0 * 0.08
    expected_activation = (
        -(-1.0 * 0.5 * 50.0 / 1000.0)
        -(1.0 * 0.5 * 60.0 / 1000.0)
        -(-1.0 * 0.5 * 100.0 / 1000.0)
        -(1.0 * 0.5 * 100.0 / 1000.0)
    )

    assert settlement["profile_id"] == (
        "robust-storage-bidding-reference-settlement-v1"
    )
    assert settlement["day_ahead_revenue"]["value_eur"] == pytest.approx(
        expected_day_ahead,
        abs=1e-6,
    )
    assert settlement["fcr_capacity_revenue"]["value_eur"] == pytest.approx(
        expected_capacity,
        abs=1e-6,
    )
    assert settlement["activation_energy_revenue"]["value_eur"] == pytest.approx(
        expected_activation,
        abs=1e-6,
    )


def test_reference_profile_has_explicit_zero_penalty_and_unavailable_components() -> None:
    report = _evaluation_module().evaluate_fixed_fcr_bid(_manual_case().request)
    settlement = report.settlement

    assert settlement["penalty_rule_id"] == "no_penalty_rule"
    assert settlement["penalty"] == {
        "status": "available",
        "value_eur": 0.0,
        "reason": None,
    }
    for component in ("intraday", "imbalance", "degradation", "terminal_value"):
        assert settlement[component]["status"] == "unavailable"
        assert settlement[component]["value_eur"] is None
        assert settlement[component]["reason"]


def test_reference_profile_reconciles_available_components_within_one_e_minus_six() -> None:
    report = _evaluation_module().evaluate_fixed_fcr_bid(_manual_case().request)
    settlement = report.settlement
    available_total = (
        settlement["day_ahead_revenue"]["value_eur"]
        + settlement["fcr_capacity_revenue"]["value_eur"]
        + settlement["activation_energy_revenue"]["value_eur"]
        - settlement["penalty"]["value_eur"]
    )

    assert settlement["total_profit_eur"] == pytest.approx(0.125, abs=1e-6)
    assert settlement["total_profit_eur"] == pytest.approx(
        available_total,
        abs=1e-6,
    )
    assert abs(settlement["reconciliation_error_eur"]) <= 1e-6
    assert settlement["charge_energy_kwh"] == pytest.approx(1.0, abs=1e-6)
    assert settlement["discharge_energy_kwh"] == pytest.approx(1.0, abs=1e-6)
    assert settlement["throughput_kwh"] == pytest.approx(2.0, abs=1e-6)
