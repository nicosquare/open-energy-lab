"""Final additive public-contract snapshots for Features 010 and 012."""

from __future__ import annotations

from dataclasses import fields
import inspect

import open_energy_lab.control as control
import open_energy_lab.market as market
import open_energy_lab.simulator as simulator
from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
    build_test_evaluation_case,
)
from tests.unit.simulator.test_stacked_service import _replay_request


def test_feature_010_and_additive_feature_012_symbols_have_exact_owners() -> None:
    owners = {
        market.MarketDataArtifact: "open_energy_lab.market.artifact",
        market.RegulationActivationTrace: "open_energy_lab.market.activation",
        control.ArbitrageOnlyBaselineConfig: "open_energy_lab.control.stacked_service",
        control.RegulationOnlyBaselineConfig: "open_energy_lab.control.stacked_service",
        control.StackedHeuristicConfig: "open_energy_lab.control.stacked_service",
        control.build_stacked_heuristic_baseline: "open_energy_lab.control.stacked_service",
        simulator.EnergyBaselineSchedule: "open_energy_lab.simulator.stacked_service",
        simulator.FCRCapacitySchedule: "open_energy_lab.simulator.stacked_service",
        simulator.StackedServiceReplayRequest: "open_energy_lab.simulator.stacked_service",
        simulator.StackedServiceReplayResult: "open_energy_lab.simulator.stacked_service",
        simulator.SettlementBreakdown: "open_energy_lab.simulator.fcr_settlement",
        simulator.replay_stacked_services: "open_energy_lab.simulator.stacked_service",
        simulator.settle_stacked_services: "open_energy_lab.simulator.fcr_settlement",
        control.FixedFCRBidPlan: "open_energy_lab.control.fcr_bid_plan",
        control.build_fixed_fcr_bid_plan: "open_energy_lab.control.fcr_bid_plan",
        simulator.FCRBidEvaluationRequest: "open_energy_lab.simulator.fcr_bid_evaluation",
        simulator.DailyFCRBidEvaluationReport: "open_energy_lab.simulator.fcr_bid_evaluation",
        simulator.InvalidCommitmentDiagnosticReport: "open_energy_lab.simulator.fcr_bid_evaluation",
        simulator.DirectionalFCREnergy: "open_energy_lab.simulator.fcr_settlement",
        simulator.ReferenceSettlementBreakdown: "open_energy_lab.simulator.fcr_settlement",
        simulator.evaluate_fixed_fcr_bid: "open_energy_lab.simulator.fcr_bid_evaluation",
    }

    assert {symbol: symbol.__module__ for symbol in owners} == owners


def test_feature_010_constructor_signatures_remain_exact_and_feature_012_is_additive() -> None:
    signatures = {
        "build_arbitrage_only_baseline": str(
            inspect.signature(control.build_arbitrage_only_baseline)
        ),
        "build_regulation_only_baseline": str(
            inspect.signature(control.build_regulation_only_baseline)
        ),
        "build_stacked_heuristic_baseline": str(
            inspect.signature(control.build_stacked_heuristic_baseline)
        ),
        "build_energy_baseline_schedule": str(
            inspect.signature(simulator.build_energy_baseline_schedule)
        ),
        "build_fcr_capacity_schedule": str(
            inspect.signature(simulator.build_fcr_capacity_schedule)
        ),
        "replay_stacked_services": str(
            inspect.signature(simulator.replay_stacked_services)
        ),
        "settle_stacked_services": str(
            inspect.signature(simulator.settle_stacked_services)
        ),
    }
    assert signatures == {
        "build_arbitrage_only_baseline": "(config: 'ArbitrageOnlyBaselineConfig', *, market_artifact: 'MarketDataArtifact', battery: 'BatteryComponent') -> 'BaselineScheduleBundle'",
        "build_regulation_only_baseline": "(config: 'RegulationOnlyBaselineConfig', *, battery: 'BatteryComponent') -> 'BaselineScheduleBundle'",
        "build_stacked_heuristic_baseline": "(config: 'StackedHeuristicConfig', *, market_artifact: 'MarketDataArtifact', battery: 'BatteryComponent') -> 'BaselineScheduleBundle'",
        "build_energy_baseline_schedule": "(*, schedule_id: 'str', semantics_version: 'str', covered_start_utc: 'datetime', covered_end_utc: 'datetime', intervals: 'Sequence[Mapping[str, object]]') -> 'EnergyBaselineSchedule'",
        "build_fcr_capacity_schedule": "(*, schedule_id: 'str', semantics_version: 'str', product_identity: 'Mapping[str, object]', covered_start_utc: 'datetime', covered_end_utc: 'datetime', intervals: 'Sequence[Mapping[str, object]]') -> 'FCRCapacitySchedule'",
        "replay_stacked_services": "(request: 'StackedServiceReplayRequest') -> 'StackedServiceReplayResult'",
        "settle_stacked_services": "(request: 'StackedServiceReplayRequest', samples: 'Sequence[ReplaySample]') -> 'SettlementBreakdown'",
    }
    assert "energy_schedule: 'EnergyBaselineSchedule'" in str(
        inspect.signature(control.build_fixed_fcr_bid_plan)
    )
    assert "fcr_schedule: 'FCRCapacitySchedule'" in str(
        inspect.signature(control.build_fixed_fcr_bid_plan)
    )
    assert str(inspect.signature(simulator.evaluate_fixed_fcr_bid)) == (
        "(request: 'FCRBidEvaluationRequest') -> 'DailyFCRBidEvaluationReport'"
    )


def test_feature_010_exact_types_serialization_and_default_settlement_are_closed() -> None:
    request = _replay_request()
    result = simulator.replay_stacked_services(request)

    assert type(request.energy_schedule) is simulator.EnergyBaselineSchedule
    assert type(request.fcr_schedule) is simulator.FCRCapacitySchedule
    assert type(request) is simulator.StackedServiceReplayRequest
    assert type(result) is simulator.StackedServiceReplayResult
    assert type(result.settlement) is simulator.SettlementBreakdown
    assert tuple(request.energy_schedule.to_dict()) == (
        "schedule_id",
        "semantics_version",
        "covered_period",
        "intervals",
        "schedule_fingerprint",
    )
    assert tuple(request.fcr_schedule.to_dict()) == (
        "schedule_id",
        "semantics_version",
        "product_identity",
        "covered_period",
        "intervals",
        "schedule_fingerprint",
    )
    assert tuple(item.name for item in fields(type(result))) == (
        "simulation_semantics_version",
        "validation_status",
        "input_fingerprints",
        "samples",
        "state_checkpoints",
        "checkpoint_summaries",
        "energy_summaries",
        "fcr_summaries",
        "saturation_events",
        "tracking_summary",
        "throughput_kwh",
        "settlement",
        "terminal_soc_report",
        "trace_fingerprint",
        "result_fingerprint",
    )
    assert result.settlement.activation_energy_settlement_status == "not_modeled"
    assert result.settlement.imbalance_settlement_status == "not_modeled"
    assert result.settlement.degradation_cost_status == "not_modeled"
    assert result.trace_fingerprint == (
        "07c7c079e17b42fedbe544539384cac73cb85aee9ef206b9b13ac9a15a9adaab"
    )
    assert result.result_fingerprint == (
        "7bd2549dedd1c77ae826c94fb23778a1b8dab2339da81cad4e6c846c1f2d90a9"
    )


def test_feature_012_serialization_references_feature_010_schedules_without_copying() -> None:
    case = build_test_evaluation_case(
        settlement_profile="robust-storage-bidding-reference-settlement-v1"
    )
    report = simulator.evaluate_fixed_fcr_bid(case.request)
    plan_payload = case.plan.to_dict()

    assert type(case.plan.energy_schedule) is simulator.EnergyBaselineSchedule
    assert type(case.plan.fcr_schedule) is simulator.FCRCapacitySchedule
    assert case.plan.energy_schedule is case.request.energy_schedule
    assert case.plan.fcr_schedule is case.request.fcr_schedule
    assert tuple(plan_payload["energy_schedule_ref"]) == (
        "schedule_id",
        "semantics_version",
        "schedule_fingerprint",
    )
    assert tuple(plan_payload["fcr_schedule_ref"]) == (
        "schedule_id",
        "semantics_version",
        "schedule_fingerprint",
    )
    assert "intervals" not in plan_payload["energy_schedule_ref"]
    assert "intervals" not in plan_payload["fcr_schedule_ref"]
    assert report.status == "settled"
    assert report.settlement["profile_id"] == (
        "robust-storage-bidding-reference-settlement-v1"
    )
