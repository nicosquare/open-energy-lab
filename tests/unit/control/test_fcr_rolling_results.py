"""Immutable Feature 015 result, aggregate, and failure contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date
from types import SimpleNamespace

import pytest

from open_energy_lab.control import (
    AggregateMetricEvidence,
    ContinuitySegment,
    DeliveryDateClassification,
    DeliveryDateRecordEnvelope,
    RollingFCRDayRevision,
    RollingFCRStudyResult,
    RollingFCRValidationError,
    aggregate_rolling_fcr_records,
    run_rolling_fcr_study,
)
from tests.fcr_rolling_case_utils import (
    AUTHORED_DELIVERY_DATES,
    build_authored_day_input,
    build_authored_fixed_plan,
    build_authored_manifest,
    fingerprint,
)


def _sha(character: str) -> str:
    return character * 64


def _revision(
    *,
    number: int = 0,
    kind: str = "original",
    status: str = "optimization_only",
    objective: float | None = 10.0,
    bound: float | None = 10.5,
    metrics: dict[str, float] | None = None,
    runtime: dict[str, object] | None = None,
    predecessor_revision_fingerprint: str | None = None,
) -> RollingFCRDayRevision:
    solved = objective is not None
    return RollingFCRDayRevision(
        revision_number=number,
        revision_kind=kind,
        lifecycle_status=status,
        creation_cause=f"authored_{kind}",
        input_fingerprint=_sha("1") if solved else None,
        problem_fingerprint=_sha("2") if solved else None,
        solve_result_fingerprint=_sha("3") if solved else None,
        plan_fingerprint=_sha("4") if solved else None,
        plan_classification="robust_candidate" if solved else None,
        solve_status="optimal" if solved else None,
        termination_status="optimal" if solved else None,
        objective_value_eur=objective,
        best_upper_bound_eur=bound,
        absolute_gap_eur=(None if objective is None or bound is None else bound - objective),
        relative_gap=(
            None
            if objective is None or bound is None
            else (bound - objective) / max(abs(objective), abs(bound), 1.0)
        ),
        feasibility_audit_fingerprint=_sha("5") if solved else None,
        feasibility_slacks={"headroom": 0.0} if solved else {},
        independent_residuals={"headroom": 0.0} if solved else {},
        energy_decisions_charge_positive_kw=(0.0,) * 24 if solved else None,
        fcr_capacity_kw=(1.0,) * 6 if solved else None,
        activation_fingerprint=_sha("6") if metrics else None,
        replay_fingerprint=_sha("7") if metrics else None,
        settlement_fingerprint=_sha("8") if metrics else None,
        predecessor_revision_fingerprint=predecessor_revision_fingerprint,
        initial_stored_energy_kwh=10.0 if solved else None,
        realized_terminal_stored_energy_kwh=10.0 if metrics else None,
        carried_stored_energy_kwh=10.0 if metrics else None,
        realized_metrics={} if metrics is None else metrics,
        diagnostics=(f"authored:{status}",),
        runtime_metadata=(
            {
                "runtime_seconds": 1.0,
                "backend": {"solver_name": "highs", "solver_version": "1.15.1"},
            }
            if runtime is None
            else runtime
        ),
    )


def _envelope(
    manifest: object,
    index: int,
    revision: RollingFCRDayRevision,
    *,
    segment_id: str = "authored-segment-0",
) -> DeliveryDateRecordEnvelope:
    classification = manifest.dates[index]
    return DeliveryDateRecordEnvelope(
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        profile_id=manifest.profile.profile_id,
        classification=classification,
        predecessor_date=(None if index == 0 else manifest.dates[index - 1].delivery_date),
        decision_cutoff_utc=None,
        information_cutoff_utc=None,
        continuity_segment_id=segment_id,
        revisions=(revision,),
    )


def _result(manifest: object, records: tuple[DeliveryDateRecordEnvelope, ...]) -> RollingFCRStudyResult:
    segment = ContinuitySegment(
        segment_id="authored-segment-0",
        start_date=records[0].classification.delivery_date,
        end_date=records[-1].classification.delivery_date,
        start_reason="manifest_start",
    )
    aggregates = aggregate_rolling_fcr_records(manifest, records)
    return RollingFCRStudyResult(
        study_id=manifest.study_id,
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_id=manifest.profile.profile_id,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        records=records,
        continuity_segments=(segment,),
        state_links=(),
        aggregate_metrics=aggregates,
        completeness_status="partial",
    )


def test_result_contract_is_deeply_immutable_and_to_dict_is_detached() -> None:
    manifest = replace(
        build_authored_manifest("script-12-restriction-reset-midnight-v1"),
        dates=build_authored_manifest(
            "script-12-restriction-reset-midnight-v1"
        ).dates[:1],
    )
    revision = _revision()
    result = _result(manifest, (_envelope(manifest, 0, revision),))

    with pytest.raises(FrozenInstanceError):
        result.completeness_status = "complete"  # type: ignore[misc]
    with pytest.raises(TypeError):
        revision.feasibility_slacks["headroom"] = 1.0  # type: ignore[index]
    payload = result.to_dict()
    payload["runtime_metadata"]["host"] = "mutated"
    assert "host" not in result.runtime_metadata


def test_revision_reports_explicit_unavailable_fingerprint_evidence_and_gaps() -> None:
    revision = _revision()
    payload = revision.to_dict()

    assert payload["absolute_gap_eur"] == pytest.approx(0.5)
    assert payload["relative_gap"] == pytest.approx(0.5 / 10.5)
    assert payload["fingerprint_evidence"]["activation_fingerprint"] == {
        "status": "unavailable",
        "reason_codes": ["activation_unavailable_for_optimization_only"],
    }
    assert payload["fingerprint_evidence"]["solve_result_fingerprint"] == _sha("3")


def test_revision_runtime_duration_host_and_path_are_nonsemantic_but_solver_version_is_semantic() -> None:
    original = _revision()
    volatile = replace(
        original,
        runtime_metadata={
            "runtime_seconds": 99.0,
            "started_at_utc": "2026-08-28T01:00:00Z",
            "finished_at_utc": "2026-08-28T01:01:39Z",
            "host": "other-host",
            "pid": 42,
            "output_path": "/private/result.json",
            "backend": {"solver_name": "highs", "solver_version": "1.15.1"},
        },
    )
    changed_solver = replace(
        original,
        runtime_metadata={
            "runtime_seconds": 1.0,
            "backend": {"solver_name": "highs", "solver_version": "9.9.9"},
        },
    )

    assert original.revision_fingerprint == volatile.revision_fingerprint
    assert original.revision_fingerprint != changed_solver.revision_fingerprint


def test_envelope_rejects_noncontiguous_revisions_and_invalid_lifecycle_transition() -> None:
    manifest = build_authored_manifest("script-12-restriction-reset-midnight-v1")
    original = _revision()
    skipped = _revision(number=2, kind="finalized", status="finalized")

    with pytest.raises(RollingFCRValidationError, match="contiguous"):
        replace(
            _envelope(manifest, 0, original),
            revisions=(original, skipped),
        )
    with pytest.raises(RollingFCRValidationError, match="finalized revision"):
        _revision(kind="finalized", status="optimization_only")


def test_status_counts_reconcile_every_requested_role_and_terminal_status() -> None:
    base = build_authored_manifest("script-12-restriction-reset-midnight-v1")
    dates = (
        replace(base.dates[0], execution_role="warm-up", comparison_eligible=False),
        base.dates[1],
        replace(base.dates[2], execution_role="excluded", comparison_eligible=False),
        replace(base.dates[3], execution_role="close-out", comparison_eligible=False),
    )
    manifest = replace(base, dates=dates)
    records = (
        _envelope(manifest, 0, _revision(status="initialization_only")),
        _envelope(manifest, 1, _revision(status="finalized", metrics={"throughput_kwh": 2.0})),
        _envelope(manifest, 2, _revision(status="excluded", objective=None, bound=None)),
        _envelope(manifest, 3, _revision(status="unfinalized")),
    )
    result = _result(manifest, records)

    assert result.status_counts == {
        "requested": 4,
        "included": 1,
        "compared": 1,
        "warm-up": 1,
        "close-out": 1,
        "excluded": 1,
        "initialization_only": 1,
        "optimization_only": 0,
        "provisional": 0,
        "finalized": 1,
        "failed": 0,
        "blocked_by_predecessor": 0,
        "unfinalized": 1,
    }
    assert sum(
        result.status_counts[key]
        for key in (
            "initialization_only",
            "optimization_only",
            "provisional",
            "finalized",
            "failed",
            "blocked_by_predecessor",
            "excluded",
            "unfinalized",
        )
    ) == result.status_counts["requested"]


def test_aggregate_records_never_zero_fill_and_keep_separate_quantities() -> None:
    base = build_authored_manifest("script-12-restriction-reset-midnight-v1")
    manifest = replace(base, dates=base.dates[:3])
    realized = {
        "settlement.total_profit_eur": 4.0,
        "total_profit_eur": 4.0,
        "delivered_fcr_energy_kwh.upward_discharge": 1.25,
        "delivered_fcr_energy_kwh.downward_charge": 0.75,
        "throughput_kwh": 3.0,
    }
    records = (
        _envelope(manifest, 0, _revision(objective=10.0, bound=11.0, status="finalized", metrics=realized)),
        _envelope(manifest, 1, _revision(objective=20.0, bound=22.0, status="failed", metrics=None)),
        _envelope(manifest, 2, _revision(objective=None, bound=None, status="blocked_by_predecessor", metrics=None)),
    )

    metrics = {item.metric_id: item for item in aggregate_rolling_fcr_records(manifest, records)}

    assert metrics["optimization_objective_eur"].value == 30.0
    assert metrics["optimization_objective_eur"].coverage_status == "partial"
    assert metrics["best_upper_bound_eur"].value == 33.0
    assert metrics["realized_settlement_eur"].value == 4.0
    assert metrics["realized_profit_eur"].value == 4.0
    assert metrics["delivered_fcr_up_energy_kwh"].value == 1.25
    assert metrics["delivered_fcr_down_energy_kwh"].value == 0.75
    assert metrics["throughput_kwh"].value == 3.0
    throughput = metrics["throughput_kwh"]
    assert throughput.contributing_dates == (AUTHORED_DELIVERY_DATES[0],)
    assert tuple(throughput.omitted_dates_with_reasons) == tuple(
        item.isoformat() for item in AUTHORED_DELIVERY_DATES[1:3]
    )
    assert throughput.coverage_status == "partial"
    assert throughput.reconciliation_residual == 0.0


def test_aggregate_contract_rejects_inconsistent_coverage_or_omission_lineage() -> None:
    with pytest.raises(RollingFCRValidationError, match="exactly eligible"):
        AggregateMetricEvidence(
            metric_id="throughput_kwh",
            unit="kWh",
            value=1.0,
            coverage_status="complete",
            eligible_dates=(date(2023, 6, 18), date(2023, 6, 19)),
            contributing_dates=(date(2023, 6, 18),),
            omitted_dates_with_reasons={},
            aggregation_rule="sum-v1",
            source_fingerprints=(_sha("a"),),
            reconciliation_residual=0.0,
        )


def test_failures_blocks_and_caller_restart_remain_visible_across_segments() -> None:
    base = build_authored_manifest("script-15-restriction-rolling-midnight-v1")
    manifest = replace(base, dates=base.dates[:4])
    first_segment = "authored-segment-0"
    restarted_segment = "authored-segment-1"
    records = (
        _envelope(manifest, 0, _revision(status="finalized", metrics={"throughput_kwh": 1.0}), segment_id=first_segment),
        _envelope(manifest, 1, _revision(status="failed", objective=None, bound=None), segment_id=first_segment),
        _envelope(manifest, 2, _revision(status="blocked_by_predecessor", objective=None, bound=None), segment_id=first_segment),
        _envelope(manifest, 3, _revision(status="finalized", metrics={"throughput_kwh": 2.0}), segment_id=restarted_segment),
    )
    result = RollingFCRStudyResult(
        study_id=manifest.study_id,
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_id=manifest.profile.profile_id,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        records=records,
        continuity_segments=(
            ContinuitySegment(
                segment_id=first_segment,
                start_date=AUTHORED_DELIVERY_DATES[0],
                end_date=AUTHORED_DELIVERY_DATES[2],
                start_reason="manifest_start",
            ),
            ContinuitySegment(
                segment_id=restarted_segment,
                start_date=AUTHORED_DELIVERY_DATES[3],
                end_date=AUTHORED_DELIVERY_DATES[3],
                start_reason="caller_supplied",
                source_state_fingerprint=_sha("c"),
            ),
        ),
        state_links=(),
        aggregate_metrics=aggregate_rolling_fcr_records(manifest, records),
        completeness_status="failed",
    )

    assert result.requested_dates == AUTHORED_DELIVERY_DATES
    assert tuple(item.latest_revision.lifecycle_status for item in result.records) == (
        "finalized",
        "failed",
        "blocked_by_predecessor",
        "finalized",
    )
    assert result.status_counts["failed"] == 1
    assert result.status_counts["blocked_by_predecessor"] == 1
    assert result.records[-1].continuity_segment_id != result.records[1].continuity_segment_id
    assert result.aggregate_metrics[-1].coverage_status == "partial"


def test_independent_profile_continues_after_missing_date_without_disappearing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_energy_lab.control import _fcr_rolling_orchestrator as orchestrator

    base = build_authored_manifest("script-12-restriction-reset-midnight-v1")
    manifest = replace(base, dates=base.dates[:3])
    inputs = tuple(
        build_authored_day_input(manifest, manifest.dates[index].delivery_date)
        for index in (0, 2)
    )
    called_dates: list[date] = []

    def fake_solve(manifest_value: object, day_input: object, *, first_executed: bool) -> tuple[object, object, object, str]:
        del manifest_value, first_executed
        delivery_date = day_input.date_classification.delivery_date
        called_dates.append(delivery_date)
        plan = build_authored_fixed_plan(delivery_date)
        solver = SimpleNamespace(
            solve_status="optimal",
            termination_status="optimal",
            objective_value_eur=0.0,
            best_upper_bound_eur=0.0,
            absolute_gap_eur=0.0,
            relative_gap=0.0,
        )
        decisions = SimpleNamespace(
            energy_baseline_charge_positive_kw=(0.0,) * 24,
            fcr_capacity_kw=(0.0,) * 6,
        )
        audit = SimpleNamespace(
            audit_fingerprint=fingerprint({"audit": delivery_date.isoformat()}),
            modeled_slacks={},
            constraint_families=(),
        )
        result = SimpleNamespace(
            solver=solver,
            decisions=decisions,
            semantic_result_fingerprint=fingerprint(
                {"result": delivery_date.isoformat()}
            ),
            feasibility_audit=audit,
            runtime_metadata={"backend": {"solver_version": "authored"}},
            diagnostics=(),
        )
        problem = SimpleNamespace(
            problem_fingerprint=fingerprint(
                {"problem": delivery_date.isoformat()}
            )
        )
        return problem, result, plan, "robust_candidate"

    monkeypatch.setattr(orchestrator, "_solve_day", fake_solve)
    result = run_rolling_fcr_study(manifest, inputs)

    assert called_dates == (
        list(AUTHORED_DELIVERY_DATES[:1])
        + list(AUTHORED_DELIVERY_DATES[2:3])
    )
    assert result.requested_dates == AUTHORED_DELIVERY_DATES[:3]
    assert tuple(item.latest_revision.lifecycle_status for item in result.records) == (
        "optimization_only",
        "failed",
        "optimization_only",
    )
    assert result.status_counts["failed"] == 1
    assert result.completeness_status == "failed"
