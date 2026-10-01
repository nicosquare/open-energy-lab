"""Foundational contracts for fixed-plan FCR evaluation inputs and reports."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import importlib
from pathlib import Path
from types import MappingProxyType

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


def _validation():
    return importlib.import_module("oel_validation.fcr_bid_evaluation")


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
    return _module().build_market_data_context(
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
        "settlement_profile": "stacked-service-default-v1",
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

    assert feature_010.context_kind == "market_artifact"
    assert reference.context_kind == "reference_result"
    assert feature_010.day_ahead_prices == reference.day_ahead_prices
    assert feature_010.fcr_capacity_prices == reference.fcr_capacity_prices
    assert feature_010 != reference
    with pytest.raises(module.FCRBidEvaluationValidationError, match="context kind"):
        replace(feature_010, context_kind="synthetic_market")


def test_evaluation_request_binds_plan_schedules_exactly() -> None:
    request = _request()

    assert request.plan.energy_schedule is request.energy_schedule
    assert request.plan.fcr_schedule is request.fcr_schedule


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
        comparison=None,
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


def test_request_and_report_canonical_bytes_are_stable() -> None:
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

    assert first_request.to_dict() == repeated_request.to_dict()
    assert first.to_dict() == repeated.to_dict()
    assert first.canonical_bytes() == repeated.canonical_bytes()


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
    assert report.evaluation_id == case.request.evaluation_id


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
    assert len({report.canonical_bytes() for report in reports}) == 4


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


def test_repeated_evaluation_has_identical_trace_settlement_and_result() -> None:
    module = _module()
    case = _us1_case()

    first = module.evaluate_fixed_fcr_bid(case.request)
    repeated = module.evaluate_fixed_fcr_bid(case.request)

    assert first.physical_trace == repeated.physical_trace
    assert first.settlement == repeated.settlement
    assert first.canonical_bytes() == repeated.canonical_bytes()


def _audit_battery(**overrides: object):
    from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
        build_test_battery,
    )

    values = {
        "capacity_kwh": 2.0,
        "max_charge_kw": 2.0,
        "max_discharge_kw": 2.0,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
        "initial_soc": 0.25,
        "min_soc": 0.0,
        "max_soc": 1.0,
    }
    values.update(overrides)
    return build_test_battery(**values)


def test_valid_static_commitment_remains_settled_after_dynamic_soc_saturation() -> None:
    case = _us1_case(
        powers_kw=(0.0, 0.0, 0.0, 0.0),
        activation_values=(1.0,) * 8,
        day_ahead_prices_eur_per_mwh=(100.0,) * 4,
        battery=_audit_battery(),
    )

    report = _module().evaluate_fixed_fcr_bid(case.request)

    assert report.status == "settled"
    assert [item.code for item in report.diagnostics] == ["preflight_valid"]
    assert report.physical_metrics["saturation_sample_count"] == 7
    assert report.physical_metrics["non_delivery_energy_kwh"] == pytest.approx(3.5)
    assert report.settlement is not None
    assert report.total_profit_eur is not None


def test_static_headroom_failure_has_ordered_diagnostics_and_no_economic_output() -> None:
    case = _us1_case(
        capacities_kw=(2.0,),
        battery=_audit_battery(capacity_kwh=5.0, initial_soc=0.5),
    )

    report = _module().evaluate_fixed_fcr_bid(case.request)

    assert report.status == "validation_failed"
    assert [item.code for item in report.diagnostics] == [
        "charge_power_headroom_insufficient",
        "discharge_power_headroom_insufficient",
    ]
    assert report.physical_trace is None
    assert report.physical_metrics is None
    assert report.settlement is None
    assert report.total_profit_eur is None
    assert report.comparison is None


def test_invalid_commitment_diagnostic_is_explicitly_non_economic() -> None:
    module = _module()
    case = _us1_case(
        capacities_kw=(2.0,),
        battery=_audit_battery(capacity_kwh=5.0, initial_soc=0.5),
    )

    diagnostic = module.replay_invalid_fcr_bid_diagnostic(case.request)
    repeated = module.replay_invalid_fcr_bid_diagnostic(case.request)

    assert diagnostic.status == "invalid_commitment_diagnostic"
    assert diagnostic.settlement is None
    assert diagnostic.total_profit_eur is None
    assert diagnostic.comparison is None
    assert diagnostic.physical_trace["samples"][6]["saturation_causes"] == (
        "discharge_power_limit",
    )
    assert diagnostic.to_dict() == repeated.to_dict()


def test_diagnostic_replay_refuses_valid_or_integrity_failed_requests() -> None:
    module = _module()
    valid = _us1_case()

    with pytest.raises(module.FCRBidEvaluationValidationError, match="statically invalid"):
        module.replay_invalid_fcr_bid_diagnostic(valid.request)

    corrupted = _us1_case()
    object.__setattr__(
        corrupted.plan.energy_schedule,
        "schedule_fingerprint",
        "0" * 64,
    )
    failed = module.evaluate_fixed_fcr_bid(corrupted.request)
    assert failed.status == "validation_failed"
    assert failed.diagnostics[0].code == "energy_schedule_fingerprint_mismatch"
    with pytest.raises(module.FCRBidEvaluationValidationError, match="integrity"):
        module.replay_invalid_fcr_bid_diagnostic(corrupted.request)


def test_battery_mutation_produces_failed_report_without_replay_or_settlement() -> None:
    case = _us1_case()
    case.battery.initial_soc = 0.6

    report = _module().evaluate_fixed_fcr_bid(case.request)

    assert report.status == "validation_failed"
    assert [item.code for item in report.diagnostics] == ["battery_mutated"]
    assert report.physical_trace is None
    assert report.settlement is None


def test_diagnostic_result_cannot_enter_settlement_or_reference_comparison() -> None:
    module = _module()
    settlement = importlib.import_module("open_energy_lab.simulator.fcr_settlement")
    reference = importlib.import_module("oel_validation.reference_fcr")
    fixture = reference.load_golden_reference_fixture(REFERENCE_FIXTURE_PATH)
    case = _us1_case(
        capacities_kw=(2.0,),
        battery=_audit_battery(capacity_kwh=5.0, initial_soc=0.5),
        comparison_fixture=fixture,
    )
    diagnostic = module.replay_invalid_fcr_bid_diagnostic(case.request)

    with pytest.raises(settlement.FCRSettlementValidationError, match="ReplaySample"):
        settlement.settle_fixed_fcr_bid(
            case.request,
            diagnostic.physical_trace["samples"],
        )
    with pytest.raises(module.FCRBidEvaluationValidationError, match="settled"):
        _validation().compare_reference_evaluation(case.request, diagnostic)


def test_daily_report_exposes_schedule_optimization_and_input_lineage() -> None:
    case = _us1_case()
    report = _module().evaluate_fixed_fcr_bid(case.request)

    assert report.schedule_identity == {
        "energy": case.plan.energy_schedule_ref.to_dict(),
        "fcr": case.plan.fcr_schedule_ref.to_dict(),
    }
    assert report.optimization_metadata == {
        "solve_status": "not_applicable",
        "objective": case.plan.objective.to_dict(),
        "objective_bound": case.plan.objective_bound.to_dict(),
    }
    assert report.plan_fingerprint == case.plan.plan_fingerprint
    assert report.to_dict()["comparison"] is None


REFERENCE_FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)


@pytest.fixture(scope="module")
def zero_activation_reference_case():
    reference = importlib.import_module("oel_validation.reference_fcr")
    activation = importlib.import_module("open_energy_lab.market.activation")
    fixture = reference.load_golden_reference_fixture(REFERENCE_FIXTURE_PATH)
    period = fixture.mapping.target_period
    step = timedelta(seconds=10)
    request = activation.ActivationImportRequest(
        source_name="unit-test zero activation",
        source_locator="authored in test_fcr_bid_evaluation.py",
        source_revision="v1",
        source_timezone="Europe/Paris",
        requested_start_utc=period.start_utc,
        requested_end_utc=period.end_utc,
        source_resolution="PT10S",
        source_value_kind="interval_average",
        source_sign_meaning="positive is upward/discharge",
        normalization_rule={
            "conversion": "identity",
            "formula": "activation",
            "point_to_interval": "already_interval_average",
            "clip_min": -1.0,
            "clip_max": 1.0,
            "target_sign": "positive is upward/discharge",
        },
        redistribution_basis={"source": "project-authored unit test"},
    )
    trace = activation.import_regulation_activation_trace(
        request,
        [
            {
                "start_utc": period.start_utc + index * step,
                "end_utc": period.start_utc + (index + 1) * step,
                "value": 0.0,
                "source_value": 0.0,
                "source_unit": "dimensionless",
            }
            for index in range(8640)
        ],
        trace_id="unit-test-zero-reference-activation-v1",
        created_at_utc=datetime(2026, 8, 26, tzinfo=UTC),
    )
    computed_bounds = {
        "charge_energy_kwh": 0.012,
        "discharge_energy_kwh": 0.012,
        "stored_energy_kwh": 0.012 / 0.92,
        "power_extrema_kw": 0.0005,
        "day_ahead_revenue_eur": 0.001073575,
        "fcr_capacity_revenue_eur": 0.00037976,
        "activation_revenue_eur": 0.0,
        "combined_fcr_revenue_eur": 0.00037976,
        "total_revenue_eur": 0.001453335,
    }
    field_bounds = {
        key: replace(value, decision_bound=computed_bounds[key])
        for key, value in fixture.precision_policy.field_bounds.items()
    }
    policy = replace(
        fixture.precision_policy,
        field_bounds=MappingProxyType(field_bounds),
    )
    synthetic_fixture = replace(fixture, precision_policy=policy)
    return synthetic_fixture, trace, computed_bounds


def test_precision_bounds_are_recomputed_from_decisions_prices_and_activation(
    zero_activation_reference_case,
) -> None:
    fixture, trace, expected_bounds = zero_activation_reference_case

    actual = _validation().recompute_reference_precision_bounds(fixture, trace)

    assert actual == pytest.approx(expected_bounds, abs=1e-12)


def test_reference_comparison_records_exact_rounded_match(
    zero_activation_reference_case,
) -> None:
    fixture, trace, _ = zero_activation_reference_case
    comparison = _validation().compare_reference_values(
        fixture=fixture,
        actual_values={"settlement.day_ahead_revenue_eur": 0.1684},
        activation_trace=trace,
        requested_field_ids=("settlement.day_ahead_revenue_eur",),
    )

    assert comparison.overall_status == "exact"
    assert comparison.fields[0].status == "exact"
    assert comparison.fields[0].exact_rounded_match is True


def test_reference_comparison_uses_analytic_interval_overlap(
    zero_activation_reference_case,
) -> None:
    fixture, trace, bounds = zero_activation_reference_case
    field_id = "settlement.day_ahead_revenue_eur"
    comparison = _validation().compare_reference_values(
        fixture=fixture,
        actual_values={field_id: 0.169},
        activation_trace=trace,
        requested_field_ids=(field_id,),
    )

    field = comparison.fields[0]
    assert comparison.overall_status == "source_precision_compatible"
    assert field.status == "source_precision_compatible"
    assert field.decision_bound == pytest.approx(bounds["day_ahead_revenue_eur"])
    assert field.actual_interval == pytest.approx(
        (0.169 - bounds["day_ahead_revenue_eur"], 0.169 + bounds["day_ahead_revenue_eur"])
    )
    assert field.expected_interval == pytest.approx((0.1675, 0.1685))
    assert field.exact_rounded_match is False


def test_reference_comparison_accepts_closed_interval_endpoint_overlap(
    zero_activation_reference_case,
) -> None:
    fixture, trace, bounds = zero_activation_reference_case
    field_id = "settlement.day_ahead_revenue_eur"
    actual = 0.168 + 0.0005 + bounds["day_ahead_revenue_eur"]
    comparison = _validation().compare_reference_values(
        fixture=fixture,
        actual_values={field_id: actual},
        activation_trace=trace,
        requested_field_ids=(field_id,),
    )

    assert comparison.fields[0].actual_interval[0] == pytest.approx(0.1685)
    assert comparison.fields[0].expected_interval[1] == pytest.approx(0.1685)
    assert comparison.overall_status == "source_precision_compatible"


def test_reference_comparison_reports_mismatch_outside_field_bound(
    zero_activation_reference_case,
) -> None:
    fixture, trace, _ = zero_activation_reference_case
    comparison = _validation().compare_reference_values(
        fixture=fixture,
        actual_values={"settlement.day_ahead_revenue_eur": 0.2},
        activation_trace=trace,
        requested_field_ids=("settlement.day_ahead_revenue_eur",),
    )

    assert comparison.overall_status == "mismatch"
    assert comparison.fields[0].status == "mismatch"


def test_reference_comparison_returns_unavailable_for_unsupported_evidence(
    zero_activation_reference_case,
) -> None:
    fixture, trace, _ = zero_activation_reference_case
    comparison = _validation().compare_reference_values(
        fixture=fixture,
        actual_values={"physical.throughput_kwh": 83.0},
        activation_trace=trace,
        requested_field_ids=("physical.throughput_kwh",),
    )

    assert comparison.overall_status == "unavailable"
    assert comparison.fields[0].status == "unavailable"
    assert "not reported" in comparison.fields[0].reason


def test_reference_objective_metadata_is_compared_separately_from_profit(
    zero_activation_reference_case,
) -> None:
    fixture, trace, _ = zero_activation_reference_case
    comparison = _validation().compare_reference_values(
        fixture=fixture,
        actual_values={
            "plan.objective": 11.028,
            "settlement.total_profit_eur": 10.749,
        },
        activation_trace=trace,
        requested_field_ids=("plan.objective", "settlement.total_profit_eur"),
    )

    assert [item.status for item in comparison.fields] == ["exact", "exact"]
    assert comparison.fields[0].actual_value != comparison.fields[1].actual_value


def test_reference_comparison_api_rejects_a_blanket_tolerance_argument(
    zero_activation_reference_case,
) -> None:
    fixture, trace, _ = zero_activation_reference_case

    with pytest.raises(TypeError, match="tolerance"):
        _validation().compare_reference_values(
            fixture=fixture,
            actual_values={"settlement.total_profit_eur": 10.749},
            activation_trace=trace,
            requested_field_ids=("settlement.total_profit_eur",),
            tolerance=0.01,
        )
