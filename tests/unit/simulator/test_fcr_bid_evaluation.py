"""Foundational contracts for fixed-plan FCR evaluation inputs and reports."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import importlib

import pytest

from tests.unit.control.test_fcr_bid_plan import _plan
from tests.unit.market.test_artifact import _build_artifact
from tests.unit.simulator.test_stacked_service import (
    _activation_trace,
    _battery,
    _energy_schedule,
    _fcr_schedule,
    _time_contract,
)
from tests.unit.market.test_artifact import PERIOD_START


def _module():
    try:
        return importlib.import_module("open_energy_lab.simulator.fcr_bid_evaluation")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.simulator.fcr_bid_evaluation is not implemented",
            pytrace=False,
        )
        raise AssertionError from exc


def _market_context():
    plan = _plan()
    return _module().build_feature_010_market_context(
        market_artifact=_build_artifact(),
        period=plan.energy_schedule.covered_period,
    )


def _request(**overrides: object):
    values = {
        "evaluation_id": "manual-plan-evaluation-v1",
        "plan": _plan(),
        "market_context": _market_context(),
        "activation_trace": _activation_trace(),
        "battery": _battery(),
        "time_contract": _time_contract(),
        "settlement_profile": "feature-010-default-v1",
        "penalty_rule": None,
        "terminal_soc_target": None,
        "comparison_fixture": None,
        "numeric_tolerance": 1e-6,
        "semantics_version": "oel.fcr-bid-evaluation.v1",
    }
    values.update(overrides)
    return _module().FCRBidEvaluationRequest(**values)


def test_market_context_is_source_independent_and_discriminated() -> None:
    module = _module()
    feature_010 = _market_context()
    reference = replace(
        feature_010,
        context_kind="reference_result",
        semantics_version="robust-storage-bidding-reference-context-v1",
    )

    assert feature_010.context_kind == "feature_010_market_artifact"
    assert reference.context_kind == "reference_result"
    assert feature_010.day_ahead_prices == reference.day_ahead_prices
    assert feature_010.fcr_capacity_prices == reference.fcr_capacity_prices
    assert feature_010.context_fingerprint != reference.context_fingerprint
    with pytest.raises(module.FCRBidEvaluationValidationError, match="context kind"):
        replace(feature_010, context_kind="synthetic_market")


def test_evaluation_request_binds_plan_schedules_exactly() -> None:
    request = _request()

    assert request.plan.energy_schedule is request.energy_schedule
    assert request.plan.fcr_schedule is request.fcr_schedule
    assert request.input_fingerprints["energy_schedule"] == (
        request.plan.energy_schedule.schedule_fingerprint
    )
    assert request.input_fingerprints["fcr_schedule"] == (
        request.plan.fcr_schedule.schedule_fingerprint
    )


def test_evaluation_request_rejects_plan_context_period_mismatch() -> None:
    module = _module()
    short_end = PERIOD_START + timedelta(hours=4)
    short_plan = _plan(
        energy_schedule=_energy_schedule(start=PERIOD_START, end=short_end),
        fcr_schedule=_fcr_schedule(start=PERIOD_START, end=short_end),
    )

    with pytest.raises(module.FCRBidEvaluationValidationError, match="plan.*period|period.*plan"):
        _request(plan=short_plan)


def test_request_detects_battery_mutation_after_binding() -> None:
    module = _module()
    battery = _battery()
    request = _request(battery=battery)

    battery.initial_soc = 0.6
    with pytest.raises(module.FCRBidEvaluationValidationError, match="battery.*mutat"):
        request.assert_battery_unchanged()


def test_activation_is_evaluation_only_lineage() -> None:
    request = _request()

    assert "activation_trace" in request.input_fingerprints
    assert request.input_fingerprints["activation_trace"] == (
        request.activation_trace.artifact_fingerprint
    )
    assert all(
        "activation" not in key.casefold()
        for key in request.plan.producer_input_fingerprints
    )
    assert request.activation_trace.artifact_fingerprint not in repr(
        request.plan.to_dict()
    )


def test_component_availability_has_no_numeric_unavailable_placeholder() -> None:
    module = _module()
    available = module.ComponentAvailability.available(1.25)
    unavailable = module.ComponentAvailability.unavailable("not selected by profile")

    assert available.to_dict() == {
        "status": "available",
        "value_eur": 1.25,
        "reason": None,
    }
    assert unavailable.to_dict() == {
        "status": "unavailable",
        "value_eur": None,
        "reason": "not selected by profile",
    }
    with pytest.raises(module.FCRBidEvaluationValidationError, match="unavailable.*value"):
        module.ComponentAvailability(
            status="unavailable",
            value_eur=0.0,
            reason="not selected",
        )


def test_successful_and_failed_reports_have_disjoint_shapes() -> None:
    module = _module()
    request = _request()
    diagnostic = module.EvaluationDiagnostic(
        phase="preflight",
        code="accepted",
        severity="info",
        field_path=None,
        message="preflight passed",
        evidence_refs=(),
    )
    settled = module.build_settled_evaluation_report(
        request=request,
        diagnostics=(diagnostic,),
        physical_trace={"samples": []},
        physical_metrics={"throughput_kwh": 2.0},
        settlement={"total_profit_eur": 0.13},
        total_profit_eur=0.13,
        trace_fingerprint="d" * 64,
        settlement_fingerprint="e" * 64,
        comparison_fingerprint=None,
    )
    failed = module.build_validation_failed_evaluation_report(
        request=request,
        diagnostics=(
            replace(
                diagnostic,
                code="invalid_commitment",
                severity="error",
                message="commitment failed",
            ),
        ),
    )

    assert settled.status == "settled"
    assert settled.physical_trace == {"samples": ()}
    assert settled.physical_metrics == {"throughput_kwh": 2.0}
    assert settled.settlement == {"total_profit_eur": 0.13}
    assert settled.total_profit_eur == 0.13
    assert failed.status == "validation_failed"
    assert failed.physical_trace is None
    assert failed.physical_metrics is None
    assert failed.settlement is None
    assert failed.total_profit_eur is None
    assert failed.trace_fingerprint is None
    assert failed.settlement_fingerprint is None


def test_request_and_report_canonical_bytes_and_fingerprints_are_stable() -> None:
    module = _module()
    first_request = _request()
    repeated_request = _request()
    diagnostics = (
        module.EvaluationDiagnostic(
            phase="preflight",
            code="invalid",
            severity="error",
            field_path="plan.fcr_schedule",
            message="invalid commitment",
            evidence_refs=("fcr:0",),
        ),
    )
    first = module.build_validation_failed_evaluation_report(
        request=first_request,
        diagnostics=diagnostics,
    )
    repeated = module.build_validation_failed_evaluation_report(
        request=repeated_request,
        diagnostics=diagnostics,
    )

    assert first_request.evaluation_input_fingerprint == (
        repeated_request.evaluation_input_fingerprint
    )
    assert first.to_dict() == repeated.to_dict()
    assert first.canonical_bytes() == repeated.canonical_bytes()
    assert first.result_fingerprint == repeated.result_fingerprint
    assert len(first.result_fingerprint) == 64


def _us1_case(*, producer_kind: str = "manual", **overrides: object):
    from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
        build_test_evaluation_case,
    )

    values = {
        "powers_kw": (1.0, 0.0, 0.0, -1.0),
        "capacities_kw": (1.0,),
        "activation_values": (1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0, -1.0),
        "day_ahead_prices_eur_per_mwh": (50.0, 60.0, 70.0, 100.0),
        "fcr_capacity_prices_eur_per_kw_block": (0.08,),
        "settlement_profile": "robust-storage-bidding-reference-settlement-v1",
        "producer_kind": producer_kind,
    }
    values.update(overrides)
    return build_test_evaluation_case(**values)


def test_valid_fixed_plan_preflight_returns_a_settled_report() -> None:
    module = _module()
    case = _us1_case()

    report = module.evaluate_fixed_fcr_bid(case.request)

    assert report.status == "settled"
    assert report.diagnostics[0].code == "preflight_valid"
    assert report.plan_fingerprint == case.plan.plan_fingerprint
    assert report.evaluation_input_fingerprint == (
        case.request.evaluation_input_fingerprint
    )


def test_identical_values_are_physically_invariant_across_producer_kinds() -> None:
    module = _module()
    reports = [
        module.evaluate_fixed_fcr_bid(_us1_case(producer_kind=kind).request)
        for kind in ("manual", "heuristic", "robust", "tpm")
    ]

    assert all(report.status == "settled" for report in reports)
    assert all(report.physical_metrics == reports[0].physical_metrics for report in reports)
    assert all(report.physical_trace == reports[0].physical_trace for report in reports)
    assert all(report.settlement == reports[0].settlement for report in reports)
    assert all(report.trace_fingerprint == reports[0].trace_fingerprint for report in reports)
    assert all(
        report.settlement_fingerprint == reports[0].settlement_fingerprint
        for report in reports
    )
    assert len({report.result_fingerprint for report in reports}) == 4


def test_manual_plan_retains_explicit_unavailable_objective_reasons_and_no_activation() -> None:
    case = _us1_case()
    plan = case.plan

    assert plan.objective.availability == "unavailable"
    assert plan.objective.unavailable_reason == (
        "authored plan has no optimization objective"
    )
    assert plan.objective_bound.availability == "unavailable"
    assert plan.objective_bound.unavailable_reason == (
        "authored plan has no optimization bound"
    )
    assert "activation" not in repr(plan.to_dict()).casefold()
    assert case.request.energy_schedule is plan.energy_schedule
    assert case.request.fcr_schedule is plan.fcr_schedule


def test_zero_fcr_and_zero_energy_use_the_same_evaluation_path() -> None:
    module = _module()
    zero_fcr = _us1_case(capacities_kw=(0.0,))
    zero_energy = _us1_case(powers_kw=(0.0, 0.0, 0.0, 0.0))

    fcr_report = module.evaluate_fixed_fcr_bid(zero_fcr.request)
    energy_report = module.evaluate_fixed_fcr_bid(zero_energy.request)

    assert fcr_report.status == "settled"
    assert fcr_report.physical_metrics["requested_fcr_energy_kwh"] == {
        "upward_discharge": 0.0,
        "downward_charge": 0.0,
        "signed_net_charge_positive": 0.0,
    }
    assert fcr_report.settlement["activation_energy_revenue"]["value_eur"] == 0.0
    assert energy_report.status == "settled"
    assert energy_report.settlement["day_ahead_revenue"]["value_eur"] == 0.0


def test_repeated_evaluation_has_identical_trace_settlement_and_result_fingerprints() -> None:
    module = _module()
    case = _us1_case()

    first = module.evaluate_fixed_fcr_bid(case.request)
    repeated = module.evaluate_fixed_fcr_bid(case.request)

    assert first.physical_trace == repeated.physical_trace
    assert first.trace_fingerprint == repeated.trace_fingerprint
    assert first.settlement_fingerprint == repeated.settlement_fingerprint
    assert first.result_fingerprint == repeated.result_fingerprint
