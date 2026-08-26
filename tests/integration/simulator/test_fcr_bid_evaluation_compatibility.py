"""Closed Feature 010 contracts that Feature 012 must preserve exactly."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from open_energy_lab.simulator.stacked_service import (
    StackedServiceValidationError,
    replay_stacked_services,
)
from open_energy_lab.simulator.fcr_bid_evaluation import (
    evaluate_fixed_fcr_bid,
    replay_invalid_fcr_bid_diagnostic,
)
from open_energy_lab.simulator.fcr_settlement import FCRPenaltyRule
from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
    build_test_battery,
    build_test_evaluation_case,
)
from tests.unit.simulator.test_stacked_service import _replay_request


FIXTURE_DIGESTS = {
    "tests/fixtures/market/france_2022-08-19_market_v1.json": (
        "7558ffd7b07470d77d50b4c5baf20eb196808324e99b0ee575060f42a83b1c8d"
    ),
    "tests/fixtures/market/france_2022-08-19_activation_v1.json": (
        "859f9bfb40e94d756f1e45eaa6c9ca6dd0e31ef943fc065659a62b343a616779"
    ),
    "tests/fixtures/market/france_2022-08-19_expected_replay_v1.json": (
        "13df60b98ca511bf6f71252ab669eb828f00ba04363fec7064043e730118208f"
    ),
    "tests/fixtures/market/manual_stacked_service_v1.json": (
        "bda0615f7585c4f52507141e500ddad013e260d5c9e22ec3ff9b8dda47cdac83"
    ),
}


def test_feature_010_fixture_bytes_are_closed_compatibility_evidence() -> None:
    assert {
        path: sha256(Path(path).read_bytes()).hexdigest()
        for path in FIXTURE_DIGESTS
    } == FIXTURE_DIGESTS


@pytest.mark.parametrize(
    ("override", "message"),
    (
        ({"battery": object()}, "replay requires exactly one BatteryComponent battery"),
        ({"energy_schedule": object()}, "energy_schedule has the wrong type"),
        ({"fcr_schedule": object()}, "fcr_schedule has the wrong type"),
        ({"time_contract": object()}, "time_contract has the wrong type"),
    ),
)
def test_feature_010_request_validation_messages_remain_exact(
    override: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(StackedServiceValidationError) as caught:
        _replay_request(**override)

    assert str(caught.value) == message


def test_feature_010_sample_order_and_fingerprints_remain_exact() -> None:
    result = replay_stacked_services(_replay_request())

    assert [sample.energy_interval_ref for sample in result.samples] == [
        f"energy:{index // 4}" for index in range(32)
    ]
    assert [sample.fcr_interval_ref for sample in result.samples] == [
        f"fcr:{index // 16}" for index in range(32)
    ]
    assert [sample.activation for sample in result.samples] == [
        (1.0, -1.0, 0.0, 0.0)[index % 4] for index in range(32)
    ]
    assert [sample.interval.start_utc for sample in result.samples] == sorted(
        sample.interval.start_utc for sample in result.samples
    )
    assert result.trace_fingerprint == (
        "07c7c079e17b42fedbe544539384cac73cb85aee9ef206b9b13ac9a15a9adaab"
    )
    assert result.result_fingerprint == (
        "7bd2549dedd1c77ae826c94fb23778a1b8dab2339da81cad4e6c846c1f2d90a9"
    )


def test_feature_010_default_settlement_payload_remains_exact() -> None:
    settlement = replay_stacked_services(_replay_request()).settlement.to_dict()

    assert tuple(settlement) == (
        "energy_intervals",
        "fcr_blocks",
        "day_ahead_energy_revenue_eur",
        "fcr_capacity_revenue_eur",
        "non_delivery_energy_kwh",
        "penalty_rule_id",
        "penalty_eur",
        "charge_energy_kwh",
        "discharge_energy_kwh",
        "throughput_kwh",
        "activation_energy_settlement_status",
        "imbalance_settlement_status",
        "degradation_cost_status",
        "total_profit_eur",
    )
    assert all(
        tuple(item) == (
            "interval",
            "accepted_power_kw",
            "duration_hours",
            "price_eur_per_mwh",
            "revenue_eur",
        )
        for item in settlement["energy_intervals"]
    )
    assert all(
        tuple(item) == (
            "interval",
            "committed_capacity_kw",
            "duration_hours",
            "capacity_price_eur_per_mw_per_h",
            "revenue_eur",
        )
        for item in settlement["fcr_blocks"]
    )
    assert [item["price_eur_per_mwh"] for item in settlement["energy_intervals"]] == [
        50.0,
        -5.0,
        52.0,
        53.0,
        54.0,
        55.0,
        56.0,
        57.0,
    ]
    assert [item["revenue_eur"] for item in settlement["fcr_blocks"]] == [0.4, 0.42]
    assert settlement == {
        **settlement,
        "day_ahead_energy_revenue_eur": 0.0,
        "fcr_capacity_revenue_eur": 0.8200000000000001,
        "non_delivery_energy_kwh": 0.0,
        "penalty_rule_id": None,
        "penalty_eur": 0.0,
        "charge_energy_kwh": 10.0,
        "discharge_energy_kwh": 10.0,
        "throughput_kwh": 20.0,
        "activation_energy_settlement_status": "not_modeled",
        "imbalance_settlement_status": "not_modeled",
        "degradation_cost_status": "not_modeled",
        "total_profit_eur": 0.8200000000000001,
    }


def _dynamic_case(*, penalty_rule=None, comparison_fixture=None):
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
        penalty_rule=penalty_rule,
        comparison_fixture=comparison_fixture,
    )


def test_reference_profile_zero_fcr_zero_energy_and_both_directions_share_path() -> None:
    zero_fcr = build_test_evaluation_case(
        powers_kw=(1.0, 0.0, 0.0, -1.0),
        capacities_kw=(0.0,),
        activation_values=(1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0, -1.0),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
    )
    zero_energy = build_test_evaluation_case(
        powers_kw=(0.0, 0.0, 0.0, 0.0),
        capacities_kw=(1.0,),
        activation_values=(1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0, -1.0),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
    )

    zero_fcr_report = evaluate_fixed_fcr_bid(zero_fcr.request)
    zero_energy_report = evaluate_fixed_fcr_bid(zero_energy.request)

    assert zero_fcr_report.status == "settled"
    assert zero_fcr_report.settlement["activation_energy_revenue"]["value_eur"] == 0.0
    assert zero_energy_report.status == "settled"
    directional = zero_energy_report.physical_metrics["requested_fcr_energy_kwh"]
    assert directional["upward_discharge"] > 0.0
    assert directional["downward_charge"] > 0.0


def test_valid_dynamic_saturation_stays_settled_with_optional_explicit_penalty() -> None:
    rule = FCRPenaltyRule(
        rule_id="compatibility-non-delivery-v1",
        measure="absolute_fcr_non_delivery_energy_kwh",
        rate=0.02,
        rate_unit="EUR/kWh",
        application="sum per activation interval",
    )
    no_penalty = evaluate_fixed_fcr_bid(_dynamic_case().request)
    configured = evaluate_fixed_fcr_bid(_dynamic_case(penalty_rule=rule).request)

    assert no_penalty.status == configured.status == "settled"
    assert no_penalty.physical_metrics == configured.physical_metrics
    assert configured.physical_metrics["non_delivery_energy_kwh"] == pytest.approx(3.5)
    assert no_penalty.settlement["penalty"]["value_eur"] == 0.0
    assert configured.settlement["penalty"]["value_eur"] == pytest.approx(0.07)
    assert configured.settlement["activation_energy_revenue"]["value_eur"] == (
        pytest.approx(0.05)
    )


def test_static_headroom_failure_can_only_be_replayed_as_diagnostic() -> None:
    case = build_test_evaluation_case(
        powers_kw=(1.0, 0.0, 0.0, -1.0),
        capacities_kw=(2.0,),
        battery=build_test_battery(
            capacity_kwh=5.0,
            max_charge_kw=2.0,
            max_discharge_kw=2.0,
            initial_soc=0.5,
            min_soc=0.0,
            max_soc=1.0,
        ),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
    )

    failed = evaluate_fixed_fcr_bid(case.request)
    diagnostic = replay_invalid_fcr_bid_diagnostic(case.request)

    assert failed.status == "validation_failed"
    assert failed.settlement is None
    assert diagnostic.status == "invalid_commitment_diagnostic"
    assert diagnostic.settlement is None
    assert any(
        sample["saturation_causes"]
        for sample in diagnostic.physical_trace["samples"]
    )


def test_saturated_run_marks_reference_parity_unavailable() -> None:
    from open_energy_lab.market.reference_fcr import load_golden_reference_fixture

    fixture = load_golden_reference_fixture(
        "tests/fixtures/fcr_bid_evaluation/"
        "robust_storage_bidding_2023-06-18_aggregate_v1.json"
    )
    report = evaluate_fixed_fcr_bid(
        _dynamic_case(comparison_fixture=fixture).request
    )

    assert report.status == "settled"
    assert report.comparison["overall_status"] == "unavailable"
    assert all(
        item["status"] == "unavailable" for item in report.comparison["fields"]
    )
    assert "outside the declared" in report.comparison["fields"][0]["reason"]


def test_feature_012_rejects_non_fcr_schedule_product_before_evaluation() -> None:
    from dataclasses import replace
    from open_energy_lab.control.fcr_bid_plan import FCRBidPlanValidationError

    case = _dynamic_case()

    with pytest.raises(FCRBidPlanValidationError, match="FCRCapacitySchedule"):
        replace(case.plan, fcr_schedule=object())
