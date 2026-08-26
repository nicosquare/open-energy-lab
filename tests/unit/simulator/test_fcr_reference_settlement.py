"""Contract tests for the additive reference-result FCR settlement profile."""

from __future__ import annotations

from dataclasses import replace
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


def _dynamic_saturation_case(*, penalty: bool = True):
    settlement = importlib.import_module("open_energy_lab.simulator.fcr_settlement")
    rule = (
        settlement.FCRPenaltyRule(
            rule_id="authored-non-delivery-penalty-v1",
            measure="absolute_fcr_non_delivery_energy_kwh",
            rate=0.02,
            rate_unit="EUR/kWh",
            application="sum per activation interval",
        )
        if penalty
        else None
    )
    return build_test_evaluation_case(
        powers_kw=(0.0, 0.0, 0.0, 0.0),
        capacities_kw=(1.0,),
        activation_values=(1.0,) * 8,
        day_ahead_prices_eur_per_mwh=(100.0,) * 4,
        fcr_capacity_prices_eur_per_kw_block=(0.08,),
        battery=build_test_battery(
            capacity_kwh=2.0,
            max_charge_kw=2.0,
            max_discharge_kw=2.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            initial_soc=0.25,
            min_soc=0.0,
            max_soc=1.0,
        ),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        penalty_rule=rule,
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


def test_directional_energy_uses_non_cancelling_upward_and_downward_totals() -> None:
    report = _evaluation_module().evaluate_fixed_fcr_bid(_manual_case().request)
    settlement = report.settlement

    assert settlement["requested_fcr_energy"] == pytest.approx(
        {
            "upward_discharge_kwh": 1.0,
            "downward_charge_kwh": 1.0,
            "signed_net_charge_positive_kwh": 0.0,
        }
    )
    assert settlement["delivered_fcr_energy"] == pytest.approx(
        {
            "upward_discharge_kwh": 1.0,
            "downward_charge_kwh": 1.0,
            "signed_net_charge_positive_kwh": 0.0,
        }
    )
    for field in ("requested_fcr_energy", "delivered_fcr_energy"):
        directional = settlement[field]
        assert directional["signed_net_charge_positive_kwh"] == pytest.approx(
            directional["downward_charge_kwh"]
            - directional["upward_discharge_kwh"]
        )


def test_dynamic_saturation_prices_only_delivered_activation_and_applies_penalty() -> None:
    report = _evaluation_module().evaluate_fixed_fcr_bid(
        _dynamic_saturation_case().request
    )
    settlement = report.settlement

    assert report.status == "settled"
    assert settlement["requested_fcr_energy"]["upward_discharge_kwh"] == 4.0
    assert settlement["delivered_fcr_energy"]["upward_discharge_kwh"] == 0.5
    assert settlement["activation_energy_revenue"]["value_eur"] == pytest.approx(
        0.05
    )
    assert settlement["activation_energy_revenue"]["value_eur"] != pytest.approx(
        0.4
    )
    assert settlement["non_delivery_energy_kwh"] == pytest.approx(3.5)
    assert settlement["penalty_rule_id"] == "authored-non-delivery-penalty-v1"
    assert settlement["penalty"]["value_eur"] == pytest.approx(0.07)
    assert settlement["fcr_capacity_revenue"]["value_eur"] == pytest.approx(0.08)
    assert settlement["combined_fcr_revenue"]["value_eur"] == pytest.approx(0.13)
    assert settlement["total_profit_eur"] == pytest.approx(0.06)
    assert settlement["charge_energy_kwh"] == 0.0
    assert settlement["discharge_energy_kwh"] == pytest.approx(0.5)
    assert settlement["throughput_kwh"] == pytest.approx(0.5)


def test_explicit_absence_of_penalty_keeps_non_delivery_as_available_zero_cost() -> None:
    report = _evaluation_module().evaluate_fixed_fcr_bid(
        _dynamic_saturation_case(penalty=False).request
    )

    assert report.settlement["non_delivery_energy_kwh"] == pytest.approx(3.5)
    assert report.settlement["penalty_rule_id"] == "no_penalty_rule"
    assert report.settlement["penalty"] == {
        "status": "available",
        "value_eur": 0.0,
        "reason": None,
    }
    assert report.settlement["total_profit_eur"] == pytest.approx(0.13)


def test_reference_settlement_rejects_internal_total_or_combined_fcr_mismatch() -> None:
    case = _manual_case()
    stacked = importlib.import_module("open_energy_lab.simulator.stacked_service")
    settlement_module = importlib.import_module(
        "open_energy_lab.simulator.fcr_settlement"
    )
    physical = stacked._replay_physical_kernel(
        stacked._PhysicalReplayInputs(
            activation_trace=case.activation_trace,
            battery=case.battery,
            energy_schedule=case.plan.energy_schedule,
            fcr_schedule=case.plan.fcr_schedule,
            time_contract=case.time_contract,
            numeric_tolerance=case.request.numeric_tolerance,
            terminal_soc_target=None,
        )
    )
    valid = settlement_module.settle_reference_fcr_bid(
        case.request,
        physical.samples,
    )

    with pytest.raises(
        settlement_module.FCRSettlementValidationError,
        match="reconcile to total profit",
    ):
        replace(valid, total_profit_eur=valid.total_profit_eur + 1.0)
    with pytest.raises(
        settlement_module.FCRSettlementValidationError,
        match="combined FCR revenue",
    ):
        replace(
            valid,
            combined_fcr_revenue=_evaluation_module().ComponentAvailability.available(
                valid.combined_fcr_revenue.value_eur + 1.0
            ),
        )
