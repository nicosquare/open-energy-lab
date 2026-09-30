"""Feature 012-only accepted-plan and segmented rolling evaluation contracts."""

from __future__ import annotations

from datetime import timedelta
from types import MappingProxyType

import pytest

from open_energy_lab.market import CanonicalInterval
from open_energy_lab.simulator.fcr_bid_evaluation import FCRBidEvaluationValidationError
from tests.fcr_rolling_case_utils import fingerprint
from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
    build_test_evaluation_case,
    build_test_time_contract,
)


def _policy(kind: str = "assumed_accepted") -> MappingProxyType[str, object]:
    payload: dict[str, object] = {
        "policy_id": f"feature-015-{kind}-v1",
        "kind": kind,
        "reject_system_volume_as_individual_evidence": True,
    }
    if kind == "assumed_accepted":
        payload["assumption_statement"] = (
            "optimizer-selected bids are assumed accepted for authored evaluation"
        )
        payload["evidence_descriptor"] = None
    else:
        payload["assumption_statement"] = None
        payload["evidence_descriptor"] = {
            "descriptor_id": "authored-individual-award-v1",
            "kind": "individual_bid_award",
            "content_fingerprint": "3" * 64,
        }
    payload["policy_fingerprint"] = fingerprint(payload)
    return MappingProxyType(payload)


def _eight_hour_case():
    default_contract = build_test_time_contract()
    contract = build_test_time_contract(
        end_utc=default_contract.start_utc + timedelta(hours=8)
    )
    return build_test_evaluation_case(
        time_contract=contract,
        powers_kw=(2.0, 2.0, 0.0, 0.0, -1.0, -1.0, 0.0, 0.0),
        capacities_kw=(1.0, 1.0),
        activation_values=(0.0, 0.5, -0.5, 0.0) * 4,
        day_ahead_prices_eur_per_mwh=(50.0,) * 8,
        fcr_capacity_prices_eur_per_kw_block=(0.08, 0.09),
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
    )


def _binding(case) -> MappingProxyType[str, object]:
    battery = case.battery
    return MappingProxyType(
        {
            "binding_fingerprint": fingerprint(
                {
                    "capacity_kwh": battery.capacity_kwh,
                    "max_charge_kw": battery.max_charge_kw,
                    "max_discharge_kw": battery.max_discharge_kw,
                }
            ),
            "capacity_kwh": battery.capacity_kwh,
            "maximum_charge_power_kw": battery.max_charge_kw,
            "maximum_discharge_power_kw": battery.max_discharge_kw,
            "minimum_stored_energy_kwh": battery.min_soc * battery.capacity_kwh,
            "maximum_stored_energy_kwh": battery.max_soc * battery.capacity_kwh,
            "charge_efficiency": battery.charge_efficiency,
            "discharge_efficiency": battery.discharge_efficiency,
            "component_name": "feature-015-segment-test-battery",
        }
    )


def test_accepted_context_converts_energy_prices_and_records_assumption() -> None:
    from open_energy_lab.simulator.fcr_bid_evaluation import build_accepted_plan_market_context

    case = _eight_hour_case()
    context = build_accepted_plan_market_context(
        plan=case.plan,
        period=case.plan.energy_schedule.covered_period,
        day_ahead_prices_eur_per_kwh=(0.05,) * 8,
        fcr_capacity_prices_eur_per_kw_block=(0.08, 0.09),
        acceptance_policy=_policy(),
        source_fingerprints={"authored_prices": "2" * 64},
    )

    assert context.context_kind == "accepted_plan"
    assert [item.source_value for item in context.day_ahead_prices] == [0.05] * 8
    assert [item.canonical_value for item in context.day_ahead_prices] == [50.0] * 8
    assert {item.canonical_unit for item in context.day_ahead_prices} == {"EUR/MWh"}
    assert {
        value["evidence_kind"] for value in context.accepted_bid_evidence.values()
    } == {"assumed_accepted"}
    assert {
        value["plan_fingerprint"] for value in context.accepted_bid_evidence.values()
    } == {case.plan.plan_fingerprint}


def test_evidence_backed_context_rejects_system_volume_as_individual_award() -> None:
    from open_energy_lab.simulator.fcr_bid_evaluation import build_accepted_plan_market_context

    case = _eight_hour_case()
    evidence_policy = dict(_policy("evidence_backed_accepted"))
    context = build_accepted_plan_market_context(
        plan=case.plan,
        period=case.plan.energy_schedule.covered_period,
        day_ahead_prices_eur_per_kwh=(0.05,) * 8,
        fcr_capacity_prices_eur_per_kw_block=(0.08, 0.09),
        acceptance_policy=evidence_policy,
        source_fingerprints={"individual_award": "4" * 64},
    )
    assert {
        value["evidence_kind"] for value in context.accepted_bid_evidence.values()
    } == {"evidence_backed_accepted"}

    evidence_policy["evidence_descriptor"] = {
        "descriptor_id": "system-volume-v1",
        "kind": "system_wide_contracted_reserve_volume",
        "content_fingerprint": "5" * 64,
    }
    evidence_policy["policy_fingerprint"] = fingerprint(
        {
            key: value
            for key, value in evidence_policy.items()
            if key != "policy_fingerprint"
        }
    )
    with pytest.raises(
        FCRBidEvaluationValidationError,
        match="system-wide|individual acceptance",
    ):
        build_accepted_plan_market_context(
            plan=case.plan,
            period=case.plan.energy_schedule.covered_period,
            day_ahead_prices_eur_per_kwh=(0.05,) * 8,
            fcr_capacity_prices_eur_per_kw_block=(0.08, 0.09),
            acceptance_policy=evidence_policy,
            source_fingerprints={"system_volume": "6" * 64},
        )


def test_segmented_evaluation_delegates_and_reconciles_state_and_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import open_energy_lab.simulator.fcr_rolling_evaluation as rolling
    from open_energy_lab.simulator import evaluate_fixed_fcr_bid_segments
    from open_energy_lab.simulator.fcr_bid_evaluation import build_accepted_plan_market_context

    case = _eight_hour_case()
    start = case.time_contract.start_utc
    periods = (
        CanonicalInterval.from_utc(start, start + timedelta(hours=4)),
        CanonicalInterval.from_utc(
            start + timedelta(hours=4), start + timedelta(hours=8)
        ),
    )
    contexts = tuple(
        build_accepted_plan_market_context(
            plan=case.plan,
            period=period,
            day_ahead_prices_eur_per_kwh=(0.05,) * 4,
            fcr_capacity_prices_eur_per_kw_block=(0.08 + 0.01 * index,),
            acceptance_policy=_policy(),
            source_fingerprints={f"segment_{index}": str(index + 7) * 64},
        )
        for index, period in enumerate(periods)
    )
    delegated = rolling.evaluate_fixed_fcr_bid
    calls = []

    def recording_evaluator(request):
        calls.append(request)
        return delegated(request)

    monkeypatch.setattr(rolling, "evaluate_fixed_fcr_bid", recording_evaluator)
    report = evaluate_fixed_fcr_bid_segments(
        evaluation_id="feature-015-segmented-authored-v1",
        plan=case.plan,
        periods=periods,
        market_contexts=contexts,
        activation_trace=case.activation_trace,
        battery_binding=_binding(case),
        initial_stored_energy_kwh=50.0,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        numeric_tolerance=1e-6,
    )

    assert len(calls) == 2
    assert len(report.segments) == 2
    assert len(report.reports) == 2
    assert all(item.status == "settled" for item in report.reports)
    assert {item.parent_plan_fingerprint for item in report.segments} == {
        case.plan.plan_fingerprint
    }
    first_terminal = report.reports[0].physical_metrics["stored_energy_kwh"][
        "terminal"
    ]
    second_initial = report.reports[1].physical_metrics["stored_energy_kwh"][
        "initial"
    ]
    assert first_terminal == pytest.approx(second_initial)
    assert report.initial_stored_energy_kwh == 50.0
    assert report.terminal_stored_energy_kwh == pytest.approx(
        report.reports[-1].physical_metrics["stored_energy_kwh"]["terminal"]
    )
    assert report.additive_metrics["throughput_kwh"] == pytest.approx(
        sum(item.physical_metrics["throughput_kwh"] for item in report.reports)
    )
    assert report.additive_metrics["total_profit_eur"] == pytest.approx(
        sum(item.total_profit_eur for item in report.reports)
    )
    assert report.maximum_state_reconciliation_residual_kwh <= 1e-6
    assert len(report.semantic_fingerprint) == 64


def test_segmented_evaluation_rejects_non_partition_and_context_mismatch() -> None:
    from open_energy_lab.simulator import evaluate_fixed_fcr_bid_segments
    from open_energy_lab.simulator.fcr_bid_evaluation import build_accepted_plan_market_context

    case = _eight_hour_case()
    start = case.time_contract.start_utc
    first = CanonicalInterval.from_utc(start, start + timedelta(hours=4))
    second = CanonicalInterval.from_utc(
        start + timedelta(hours=5), start + timedelta(hours=8)
    )
    context = build_accepted_plan_market_context(
        plan=case.plan,
        period=first,
        day_ahead_prices_eur_per_kwh=(0.05,) * 4,
        fcr_capacity_prices_eur_per_kw_block=(0.08,),
        acceptance_policy=_policy(),
        source_fingerprints={"segment": "9" * 64},
    )
    with pytest.raises(FCRBidEvaluationValidationError, match="partition|contiguous"):
        evaluate_fixed_fcr_bid_segments(
            evaluation_id="feature-015-invalid-segments-v1",
            plan=case.plan,
            periods=(first, second),
            market_contexts=(context, context),
            activation_trace=case.activation_trace,
            battery_binding=_binding(case),
            initial_stored_energy_kwh=50.0,
            settlement_profile="robust-storage-bidding-reference-settlement-v1",
            numeric_tolerance=1e-6,
        )
