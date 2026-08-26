"""Contracts for the bidder-neutral fixed FCR plan envelope."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import importlib

import pytest

from tests.unit.market.test_artifact import PERIOD_START
from tests.unit.simulator.test_stacked_service import _energy_schedule, _fcr_schedule


def _module():
    try:
        return importlib.import_module("open_energy_lab.control.fcr_bid_plan")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.control.fcr_bid_plan is not implemented",
            pytrace=False,
        )
        raise AssertionError from exc


def _producer(*, kind: str = "manual"):
    return _module().BidPlanProducer(
        producer_id="manual-oracle",
        producer_kind=kind,
        producer_version="fixture-v1",
        configuration_fingerprint="a" * 64,
        configuration_unavailable_reason=None,
    )


def _available(*, meaning: str, value: float = 11.028):
    return _module().OptimizationMetric(
        availability="available",
        value=value,
        unit="EUR",
        unavailable_reason=None,
        meaning=meaning,
    )


def _unavailable(*, meaning: str, reason: str = "producer has no optimizer"):
    return _module().OptimizationMetric(
        availability="unavailable",
        value=None,
        unit=None,
        unavailable_reason=reason,
        meaning=meaning,
    )


def _plan(**overrides: object):
    values = {
        "plan_id": "manual-plan-v1",
        "producer": _producer(),
        "information_cutoff_utc": PERIOD_START - timedelta(hours=1),
        "energy_schedule": _energy_schedule(),
        "fcr_schedule": _fcr_schedule(),
        "producer_input_fingerprints": {
            "forecast": "b" * 64,
            "market_snapshot": "c" * 64,
        },
        "solve_status": "not_applicable",
        "objective": _unavailable(meaning="optimization_objective"),
        "objective_bound": _unavailable(meaning="optimization_bound"),
        "diagnostics": (),
        "semantics_version": "oel.fixed-fcr-bid-plan.v1",
    }
    values.update(overrides)
    return _module().build_fixed_fcr_bid_plan(**values)


def test_metrics_require_exact_available_or_unavailable_shapes() -> None:
    module = _module()

    assert _available(meaning="optimization_objective").to_dict() == {
        "availability": "available",
        "value": 11.028,
        "unit": "EUR",
        "unavailable_reason": None,
        "meaning": "optimization_objective",
    }
    assert _unavailable(meaning="optimization_bound").to_dict() == {
        "availability": "unavailable",
        "value": None,
        "unit": None,
        "unavailable_reason": "producer has no optimizer",
        "meaning": "optimization_bound",
    }
    with pytest.raises(module.FCRBidPlanValidationError, match="unavailable reason"):
        module.OptimizationMetric(
            availability="unavailable",
            value=None,
            unit=None,
            unavailable_reason=None,
            meaning="optimization_objective",
        )
    with pytest.raises(module.FCRBidPlanValidationError, match="value.*unit"):
        module.OptimizationMetric(
            availability="available",
            value=1.0,
            unit=None,
            unavailable_reason=None,
            meaning="optimization_objective",
        )


def test_producer_configuration_identity_is_explicit() -> None:
    module = _module()

    unavailable = module.BidPlanProducer(
        producer_id="hand-authored",
        producer_kind="manual",
        producer_version="v1",
        configuration_fingerprint=None,
        configuration_unavailable_reason="no separate configuration artifact",
    )
    assert unavailable.configuration_fingerprint is None
    with pytest.raises(module.FCRBidPlanValidationError, match="configuration"):
        replace(unavailable, configuration_unavailable_reason=None)
    with pytest.raises(module.FCRBidPlanValidationError, match="producer kind"):
        replace(unavailable, producer_kind="optimizer")


def test_plan_retains_exact_schedule_objects_and_serializes_references_only() -> None:
    energy = _energy_schedule()
    fcr = _fcr_schedule()

    plan = _plan(energy_schedule=energy, fcr_schedule=fcr)
    payload = plan.to_dict()

    assert plan.energy_schedule is energy
    assert plan.fcr_schedule is fcr
    assert payload["energy_schedule_ref"] == {
        "schedule_id": energy.schedule_id,
        "semantics_version": energy.semantics_version,
        "schedule_fingerprint": energy.schedule_fingerprint,
    }
    assert payload["fcr_schedule_ref"] == {
        "schedule_id": fcr.schedule_id,
        "semantics_version": fcr.semantics_version,
        "schedule_fingerprint": fcr.schedule_fingerprint,
    }
    assert "energy_schedule" not in payload
    assert "fcr_schedule" not in payload
    assert "intervals" not in repr(payload)


def test_plan_fingerprint_is_canonical_and_excludes_evaluation_activation() -> None:
    diagnostic_type = _module().PlanDiagnostic
    later = diagnostic_type(
        code="z-code",
        severity="warning",
        field_path="producer.z",
        message="later",
        evidence_refs=("z",),
    )
    earlier = diagnostic_type(
        code="a-code",
        severity="info",
        field_path="producer.a",
        message="earlier",
        evidence_refs=("a",),
    )
    first = _plan(
        producer_input_fingerprints={
            "market_snapshot": "c" * 64,
            "forecast": "b" * 64,
        },
        diagnostics=(later, earlier),
    )
    repeated = _plan(
        producer_input_fingerprints={
            "forecast": "b" * 64,
            "market_snapshot": "c" * 64,
        },
        diagnostics=(earlier, later),
    )

    assert first.diagnostics == (earlier, later)
    assert first.producer_input_fingerprints == repeated.producer_input_fingerprints
    assert first.plan_fingerprint == repeated.plan_fingerprint
    assert len(first.plan_fingerprint) == 64
    assert "activation" not in repr(first.to_dict()).lower()


@pytest.mark.parametrize(
    "key",
    (
        "activation_trace",
        "realized_activation_fingerprint",
        "reference_expected_outputs",
        "parity_comparison_fixture",
    ),
)
def test_plan_rejects_evaluation_only_or_lookahead_lineage(key: str) -> None:
    module = _module()

    with pytest.raises(module.FCRBidPlanValidationError, match="evaluation-only|look-ahead"):
        _plan(producer_input_fingerprints={key: "d" * 64})


def test_information_cutoff_must_be_utc_and_before_delivery() -> None:
    module = _module()

    with pytest.raises(module.FCRBidPlanValidationError, match="aware UTC"):
        _plan(information_cutoff_utc=datetime(2022, 8, 18, 21, 0))
    with pytest.raises(module.FCRBidPlanValidationError, match="delivery|cutoff"):
        _plan(information_cutoff_utc=PERIOD_START + timedelta(seconds=1))
    plan = _plan(information_cutoff_utc=PERIOD_START.astimezone(UTC))
    assert plan.information_cutoff_utc == PERIOD_START


def test_plan_rejects_incompatible_schedules_metrics_and_fingerprints() -> None:
    module = _module()

    with pytest.raises(module.FCRBidPlanValidationError, match="same period"):
        _plan(fcr_schedule=_fcr_schedule(start=PERIOD_START, end=PERIOD_START + timedelta(hours=4)))
    with pytest.raises(module.FCRBidPlanValidationError, match="objective meaning"):
        _plan(objective=_available(meaning="optimization_bound"))
    with pytest.raises(module.FCRBidPlanValidationError, match="SHA-256"):
        _plan(producer_input_fingerprints={"forecast": "not-a-digest"})
