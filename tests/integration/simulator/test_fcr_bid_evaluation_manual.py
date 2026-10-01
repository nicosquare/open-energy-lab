"""End-to-end independent oracle for the bidder-neutral FCR evaluator."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from open_energy_lab.core.serialization import fingerprint
from open_energy_lab.simulator.fcr_bid_evaluation import (
    evaluate_fixed_fcr_bid,
    replay_invalid_fcr_bid_diagnostic,
)
from open_energy_lab.simulator.fcr_settlement import FCRPenaltyRule
from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
    build_test_battery,
    build_test_evaluation_case,
    build_test_time_contract,
)


FIXTURE_PATH = Path("tests/fixtures/fcr_bid_evaluation/manual_fcr_bid_evaluation_v1.json")
TOLERANCE = 1e-6


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _case(fixture: dict[str, object]):
    period = fixture["period"]
    grids = fixture["grids"]
    mapping = fixture["mapping"]
    battery = fixture["battery"]
    energy = fixture["energy_schedule"]
    fcr = fixture["fcr_schedule"]
    activation = fixture["activation"]
    contract = build_test_time_contract(
        start_utc=_instant(period["start_utc"]),
        end_utc=_instant(period["end_utc"]),
        activation_resolution=grids["activation_resolution"],
        checkpoint_resolution=grids["checkpoint_resolution"],
    )
    return build_test_evaluation_case(
        powers_kw=tuple(mapping["library_baseline_kw"]),
        capacities_kw=tuple(mapping["library_fcr_capacity_kw"]),
        activation_values=tuple(activation["values"]),
        day_ahead_prices_eur_per_mwh=tuple(energy["prices_eur_per_mwh"]),
        fcr_capacity_prices_eur_per_kw_block=tuple(
            fcr["capacity_price_eur_per_kw_block"]
        ),
        time_contract=contract,
        battery=build_test_battery(
            capacity_kwh=battery["capacity_kwh"],
            max_charge_kw=battery["max_charge_kw"],
            max_discharge_kw=battery["max_discharge_kw"],
            charge_efficiency=battery["charge_efficiency"],
            discharge_efficiency=battery["discharge_efficiency"],
            initial_soc=battery["initial_soc"],
            min_soc=battery["min_soc"],
            max_soc=battery["max_soc"],
        ),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
    )


def _dynamic_saturation_case(fixture: dict[str, object]):
    values = fixture["dynamic_saturation_case"]
    battery = values["battery"]
    penalty = values["penalty_rule"]
    return build_test_evaluation_case(
        powers_kw=tuple(values["energy_baseline_kw"]),
        capacities_kw=tuple(values["fcr_capacity_kw"]),
        activation_values=tuple(values["activation"]),
        day_ahead_prices_eur_per_mwh=tuple(
            values["day_ahead_prices_eur_per_mwh"]
        ),
        fcr_capacity_prices_eur_per_kw_block=tuple(
            values["fcr_capacity_prices_eur_per_kw_block"]
        ),
        battery=build_test_battery(**battery),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        penalty_rule=FCRPenaltyRule(**penalty),
    )


def _invalid_static_case(fixture: dict[str, object]):
    values = fixture["invalid_static_headroom_case"]
    return build_test_evaluation_case(
        powers_kw=tuple(values["energy_baseline_kw"]),
        capacities_kw=tuple(values["fcr_capacity_kw"]),
        activation_values=tuple(fixture["activation"]["values"]),
        day_ahead_prices_eur_per_mwh=tuple(
            fixture["energy_schedule"]["prices_eur_per_mwh"]
        ),
        fcr_capacity_prices_eur_per_kw_block=tuple(
            fixture["fcr_schedule"]["capacity_price_eur_per_kw_block"]
        ),
        battery=build_test_battery(
            capacity_kwh=5.0,
            max_charge_kw=values["battery_max_charge_kw"],
            max_discharge_kw=values["battery_max_discharge_kw"],
            charge_efficiency=0.8,
            discharge_efficiency=0.8,
            initial_soc=0.5,
            min_soc=0.0,
            max_soc=1.0,
        ),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
    )


def test_authored_fixture_independently_encodes_mapping_and_arithmetic() -> None:
    fixture = _fixture()
    mapping = fixture["mapping"]
    expected = fixture["expected"]

    assert fixture["schema_version"] == "oel.fcr-bid-evaluation-manual.v1"
    assert mapping["library_baseline_kw"] == [
        -value for value in mapping["reference_x0_kw"]
    ]
    assert mapping["library_fcr_capacity_kw"] == mapping["reference_xr_kw"]
    assert all(value >= 0.0 for value in mapping["reference_xr_kw"])
    for sample in fixture["expected_samples"]:
        expected_fcr = -sample["activation"] * mapping["reference_xr_kw"][0]
        assert sample["requested_fcr_power_kw"] == expected_fcr
        assert sample["requested_combined_power_kw"] == (
            sample["baseline_power_kw"] + expected_fcr
        )
    assert expected["settlement"]["day_ahead_revenue_eur"] == pytest.approx(
        -1.0 * 50.0 / 1000.0 + 1.0 * 100.0 / 1000.0,
        abs=TOLERANCE,
    )
    assert expected["settlement"]["activation_energy_revenue_eur"] == pytest.approx(
        0.025 - 0.03 + 0.05 - 0.05,
        abs=TOLERANCE,
    )
    assert fixture["fingerprints"]["status"] == (
        "pinned_after_independent_numeric_oracle_passed"
    )


def test_manual_fcr_bid_evaluation_matches_every_authored_value() -> None:
    fixture = _fixture()
    case = _case(fixture)
    expected = fixture["expected"]

    report = evaluate_fixed_fcr_bid(case.request)
    repeated = evaluate_fixed_fcr_bid(case.request)

    assert report.status == "settled"
    assert [item.code for item in report.diagnostics] == ["preflight_valid"]
    trace = report.physical_trace
    assert len(trace["samples"]) == fixture["grids"]["activation_count"]
    assert len(trace["state_checkpoints"]) == fixture["grids"]["checkpoint_count"] + 1
    for actual, oracle in zip(
        trace["samples"],
        fixture["expected_samples"],
        strict=True,
    ):
        for field in (
            "baseline_power_kw",
            "activation",
            "requested_fcr_power_kw",
            "requested_combined_power_kw",
            "delivered_fcr_power_kw",
            "delivered_combined_power_kw",
            "charge_energy_kwh",
            "discharge_energy_kwh",
            "stored_energy_before_kwh",
            "stored_energy_after_kwh",
        ):
            assert actual[field] == pytest.approx(oracle[field], abs=TOLERANCE)
        assert actual["signed_tracking_error_kw"] == pytest.approx(0.0, abs=TOLERANCE)
        assert actual["non_delivery_energy_kwh"] == pytest.approx(0.0, abs=TOLERANCE)
        assert actual["saturation_causes"] == ()

    checkpoint_energy = [
        checkpoint["stored_energy_kwh"]
        for checkpoint in trace["state_checkpoints"]
    ]
    assert checkpoint_energy == pytest.approx(
        [fixture["battery"]["initial_stored_energy_kwh"]]
        + [item["stored_energy_after_kwh"] for item in fixture["expected_samples"]],
        abs=TOLERANCE,
    )
    metrics = report.physical_metrics
    assert metrics["stored_energy_kwh"] == pytest.approx(
        expected["stored_energy_kwh"],
        abs=TOLERANCE,
    )
    assert metrics["requested_power_kw"] == pytest.approx(
        expected["requested_power_kw"],
        abs=TOLERANCE,
    )
    assert metrics["delivered_power_kw"] == pytest.approx(
        expected["delivered_power_kw"],
        abs=TOLERANCE,
    )
    for field in (
        "requested_fcr_energy_kwh",
        "delivered_fcr_energy_kwh",
    ):
        assert metrics[field] == pytest.approx(expected[field], abs=TOLERANCE)
    for field in (
        "charge_energy_kwh",
        "discharge_energy_kwh",
        "throughput_kwh",
        "signed_tracking_error_kw_sum",
        "absolute_tracking_error_kw_sum",
        "non_delivery_energy_kwh",
        "saturation_sample_count",
        "saturation_event_count",
    ):
        assert metrics[field] == pytest.approx(expected[field], abs=TOLERANCE)

    settlement = report.settlement
    for field in (
        "day_ahead_revenue",
        "fcr_capacity_revenue",
        "activation_energy_revenue",
        "penalty",
    ):
        expected_key = field + "_eur" if field != "penalty" else "penalty_eur"
        assert settlement[field]["value_eur"] == pytest.approx(
            expected["settlement"][expected_key],
            abs=TOLERANCE,
        )
    assert settlement["total_profit_eur"] == pytest.approx(
        expected["settlement"]["total_profit_eur"],
        abs=TOLERANCE,
    )
    assert report.physical_trace == repeated.physical_trace
    assert report.canonical_bytes() == repeated.canonical_bytes()
    pinned = fixture["fingerprints"]
    assert case.plan.plan_fingerprint == pinned["plan"]
    assert fingerprint(report.to_dict()["physical_trace"]) == pinned["trace"]
    assert fingerprint(report.to_dict()["settlement"]) == pinned["settlement"]
    assert fingerprint(report.to_dict()) == pinned["result"]


def test_dynamic_soc_saturation_matches_independent_delivery_and_penalty_oracle() -> None:
    fixture = _fixture()
    case = _dynamic_saturation_case(fixture)
    expected = fixture["dynamic_saturation_case"]["expected"]

    report = evaluate_fixed_fcr_bid(case.request)

    assert report.status == "settled"
    assert report.physical_metrics["stored_energy_kwh"] == pytest.approx(
        expected["stored_energy_kwh"], abs=TOLERANCE
    )
    for field in (
        "requested_power_kw",
        "delivered_power_kw",
        "requested_fcr_energy_kwh",
        "delivered_fcr_energy_kwh",
    ):
        assert report.physical_metrics[field] == pytest.approx(
            expected[field], abs=TOLERANCE
        )
    for field in (
        "signed_tracking_error_kw_sum",
        "absolute_tracking_error_kw_sum",
        "non_delivery_energy_kwh",
        "charge_energy_kwh",
        "discharge_energy_kwh",
        "throughput_kwh",
        "saturation_sample_count",
        "saturation_duration_hours",
        "saturation_event_count",
    ):
        assert report.physical_metrics[field] == pytest.approx(
            expected[field], abs=TOLERANCE
        )
    event = report.physical_trace["saturation_events"][0]
    expected_event = expected["saturation_event"]
    assert event["event_id"] == expected_event["event_id"]
    assert event["cause"] == expected_event["cause"]
    assert event["sample_count"] == expected_event["sample_count"]
    assert event["duration_hours"] == pytest.approx(expected_event["duration_hours"])
    assert event["undelivered_energy_kwh"] == pytest.approx(
        expected_event["undelivered_energy_kwh"]
    )
    assert report.physical_trace["samples"][0]["saturation_causes"] == ()
    assert all(
        sample["saturation_causes"] == ("minimum_soc_limit",)
        for sample in report.physical_trace["samples"][1:]
    )

    settlement = report.settlement
    expected_settlement = expected["settlement"]
    for component in (
        "day_ahead_revenue",
        "fcr_capacity_revenue",
        "activation_energy_revenue",
        "combined_fcr_revenue",
        "penalty",
    ):
        key = component + "_eur"
        assert settlement[component]["value_eur"] == pytest.approx(
            expected_settlement[key], abs=TOLERANCE
        )
    assert settlement["total_profit_eur"] == pytest.approx(
        expected_settlement["total_profit_eur"], abs=TOLERANCE
    )
    assert settlement["requested_fcr_energy"] == pytest.approx(
        {
            "upward_discharge_kwh": 4.0,
            "downward_charge_kwh": 0.0,
            "signed_net_charge_positive_kwh": -4.0,
        }
    )
    assert settlement["delivered_fcr_energy"] == pytest.approx(
        {
            "upward_discharge_kwh": 0.5,
            "downward_charge_kwh": 0.0,
            "signed_net_charge_positive_kwh": -0.5,
        }
    )
    assert fingerprint(report.to_dict()) == fixture["fingerprints"][
        "dynamic_saturation_result"
    ]


def test_static_failure_and_diagnostic_replay_remain_distinct() -> None:
    fixture = _fixture()
    case = _invalid_static_case(fixture)
    expected = fixture["invalid_static_headroom_case"]

    failed = evaluate_fixed_fcr_bid(case.request)
    diagnostic = replay_invalid_fcr_bid_diagnostic(case.request)

    assert failed.status == expected["expected_status"]
    assert [item.code for item in failed.diagnostics] == expected[
        "expected_diagnostic_codes"
    ]
    assert failed.physical_trace is expected["expected_trace"]
    assert failed.settlement is expected["expected_settlement"]
    assert failed.total_profit_eur is expected["expected_profit"]
    assert diagnostic.status == expected["diagnostic_replay_status"]
    assert diagnostic.settlement is None
    assert diagnostic.total_profit_eur is None
    saturation = expected["diagnostic_replay_expected_saturation"]
    assert diagnostic.physical_trace["samples"][saturation["sample_index"]][
        "saturation_causes"
    ] == (saturation["cause"],)
    assert fingerprint(failed.to_dict()) == fixture["fingerprints"]["failed_report"]
    assert fingerprint(diagnostic.to_dict()) == fixture["fingerprints"][
        "diagnostic_replay"
    ]
