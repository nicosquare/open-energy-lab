"""Private deterministic state machine for Feature 015 rolling studies."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from .fcr_rolling_backtest import (
    ContinuitySegment,
    DeliveryDateRecordEnvelope,
    RollingFCRDayInput,
    RollingFCRDayRevision,
    RollingFCRStudyManifest,
    RollingFCRStudyResult,
    RollingFCRValidationError,
)
from .robust_fcr_bidding import (
    RobustFCRSolveResult,
    _build_fixed_fcr_plan_from_decisions,
    build_robust_fcr_bidding_problem,
    solve_robust_fcr_bid,
)


def _diagnostic_relaxation_plan(
    day_input: RollingFCRDayInput,
    result: RobustFCRSolveResult,
) -> Any | None:
    if result.decisions is None or result.solver.objective_value_eur is None:
        return None
    from .fcr_bid_plan import BidPlanProducer, OptimizationMetric, PlanDiagnostic

    return _build_fixed_fcr_plan_from_decisions(
        plan_id=f"{day_input.date_classification.delivery_date}-relaxation-diagnostic-plan-v1",
        energy_schedule_id=f"{day_input.date_classification.delivery_date}-relaxation-energy-v1",
        fcr_schedule_id=f"{day_input.date_classification.delivery_date}-relaxation-fcr-v1",
        producer=BidPlanProducer(
            producer_id="open-energy-lab-fcr-rolling-relaxation",
            producer_kind="other",
            producer_version="feature-015-diagnostic-non-robust-v1",
            configuration_fingerprint=result.problem_fingerprint,
            configuration_unavailable_reason=None,
        ),
        information_cutoff_utc=day_input.information_cutoff_utc,
        time_contract=day_input.time_contract,
        decisions=result.decisions,
        producer_input_fingerprints={
            **dict(day_input.producer_input_fingerprints),
            "daily_problem": result.problem_fingerprint,
        },
        solve_status=result.solver.solve_status,
        objective=OptimizationMetric(
            availability="available",
            value=result.solver.objective_value_eur,
            unit="EUR",
            unavailable_reason=None,
            meaning="optimization_objective",
        ),
        objective_bound=OptimizationMetric(
            availability=(
                "available"
                if result.solver.best_upper_bound_eur is not None
                else "unavailable"
            ),
            value=result.solver.best_upper_bound_eur,
            unit=("EUR" if result.solver.best_upper_bound_eur is not None else None),
            unavailable_reason=(
                None
                if result.solver.best_upper_bound_eur is not None
                else "same-solve upper bound unavailable"
            ),
            meaning="optimization_bound",
        ),
        diagnostics=(
            PlanDiagnostic(
                code="diagnostic_non_robust_relaxation",
                severity="warning",
                field_path="plan_classification",
                message=(
                    "relaxation decisions are upper-bound diagnostics and are not robustly deployable"
                ),
                evidence_refs=(f"sha256:{result.semantic_result_fingerprint}",),
            ),
        ),
    )


def _ordinary_problem(
    manifest: RollingFCRStudyManifest,
    day_input: RollingFCRDayInput,
) -> Any:
    return build_robust_fcr_bidding_problem(
        problem_id=(
            f"{manifest.study_id}-{day_input.date_classification.delivery_date}-daily-v1"
        ),
        battery=day_input.battery,
        time_contract=day_input.time_contract,
        prices=day_input.prices,
        uncertainty=manifest.uncertainty_profile,
        terminal_rule=manifest.terminal_rule,
        solve_policy=manifest.solve_policy,
        information_cutoff_utc=day_input.information_cutoff_utc,
        producer_input_fingerprints=day_input.producer_input_fingerprints,
        provenance=day_input.provenance,
    )


def _solve_day(
    manifest: RollingFCRStudyManifest,
    day_input: RollingFCRDayInput,
    *,
    first_executed: bool,
) -> tuple[object, object, Any | None, str]:
    profile = manifest.profile
    use_ordinary = profile.profile_id in {
        "script-11-relaxation-reset-midnight-v1",
        "script-12-restriction-reset-midnight-v1",
        "script-15-restriction-rolling-midnight-v1",
    } or (
        profile.profile_id == "script-14-restriction-rolling-0800-v1"
        and first_executed
    )
    if use_ordinary:
        problem = _ordinary_problem(manifest, day_input)
        formulation = (
            "relaxation"
            if profile.formulation_kind == "relaxation"
            else "restriction"
        )
        result = solve_robust_fcr_bid(problem, formulation=formulation)
        if formulation == "relaxation":
            plan = _diagnostic_relaxation_plan(day_input, result)
        else:
            plan = result.deployable_plan
        return problem, result, plan, profile.plan_classification

    from .robust_fcr_rolling import (
        build_robust_fcr_rolling_problem,
        solve_robust_fcr_rolling_bid,
    )

    rolling_problem = build_robust_fcr_rolling_problem(
        problem_id=(
            f"{manifest.study_id}-{day_input.date_classification.delivery_date}-rolling-v1"
        ),
        profile=profile,
        current_time_contract=day_input.time_contract,
        battery=day_input.battery,
        current_prices=day_input.prices,
        uncertainty=manifest.uncertainty_profile,
        terminal_rule=manifest.terminal_rule,
        solve_policy=manifest.solve_policy,
        information_cutoff_utc=day_input.information_cutoff_utc,
        producer_input_fingerprints=day_input.producer_input_fingerprints,
        provenance=day_input.provenance,
        predecessor_prices=day_input.predecessor_prices,
        accepted_fixings=day_input.accepted_fixings,
        predecessor_cutoff_utc=day_input.predecessor_cutoff_utc,
    )
    rolling_result = solve_robust_fcr_rolling_bid(rolling_problem)
    return (
        rolling_problem,
        rolling_result,
        rolling_result.plan,
        rolling_result.plan_classification,
    )


def _result_fields(result: object) -> dict[str, object]:
    solver = result.solver
    decisions = result.decisions
    semantic_fingerprint = getattr(
        result,
        "semantic_result_fingerprint",
        getattr(result, "semantic_fingerprint", None),
    )
    audit = getattr(result, "feasibility_audit", None)
    return {
        "solve_result_fingerprint": semantic_fingerprint,
        "solve_status": solver.solve_status,
        "termination_status": solver.termination_status,
        "objective_value_eur": solver.objective_value_eur,
        "best_upper_bound_eur": solver.best_upper_bound_eur,
        "absolute_gap_eur": solver.absolute_gap_eur,
        "relative_gap": solver.relative_gap,
        "feasibility_audit_fingerprint": (
            None if audit is None else audit.audit_fingerprint
        ),
        "feasibility_slacks": (
            {} if audit is None else dict(audit.modeled_slacks)
        ),
        "energy_decisions_charge_positive_kw": (
            None
            if decisions is None
            else decisions.energy_baseline_charge_positive_kw
        ),
        "fcr_capacity_kw": None if decisions is None else decisions.fcr_capacity_kw,
        "runtime_metadata": getattr(result, "runtime_metadata", {}),
    }


def _failure_envelope(
    manifest: RollingFCRStudyManifest,
    classification: object,
    *,
    predecessor_date: date | None,
    lifecycle_status: str,
    reason: str,
) -> DeliveryDateRecordEnvelope:
    revision = RollingFCRDayRevision(
        revision_number=0,
        revision_kind="original",
        lifecycle_status=lifecycle_status,
        creation_cause=reason,
        input_fingerprint=None,
        problem_fingerprint=None,
        solve_result_fingerprint=None,
        plan_fingerprint=None,
        plan_classification=manifest.profile.plan_classification,
        solve_status=None,
        termination_status=None,
        objective_value_eur=None,
        best_upper_bound_eur=None,
        absolute_gap_eur=None,
        relative_gap=None,
        feasibility_audit_fingerprint=None,
        feasibility_slacks={},
        energy_decisions_charge_positive_kw=None,
        fcr_capacity_kw=None,
        diagnostics=(reason,),
    )
    return DeliveryDateRecordEnvelope(
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        classification=classification,
        predecessor_date=predecessor_date,
        continuity_segment_id=f"{manifest.study_id}-segment-0",
        revisions=(revision,),
    )


def run_initial_rolling_fcr_study(
    manifest: RollingFCRStudyManifest,
    day_inputs: tuple[RollingFCRDayInput, ...],
    *,
    activation_traces: Mapping[date, object] | None,
    resume_from: RollingFCRStudyResult | None,
) -> RollingFCRStudyResult:
    """Build ordered optimization evidence; causal replay is added in later phases."""

    if resume_from is not None:
        if resume_from.manifest_fingerprint != manifest.manifest_fingerprint:
            raise RollingFCRValidationError("resume result belongs to another manifest")
        raise RollingFCRValidationError(
            "resume reuse is not available until the Feature 015 resume phase"
        )
    # Activation is deliberately not inspected by this optimization-only phase.
    del activation_traces
    by_date = {item.date_classification.delivery_date: item for item in day_inputs}
    if len(by_date) != len(day_inputs):
        raise RollingFCRValidationError("day_inputs must identify unique dates")
    manifest_dates = {item.delivery_date for item in manifest.dates}
    if any(delivery_date not in manifest_dates for delivery_date in by_date):
        raise RollingFCRValidationError("day input date is outside the manifest")
    records: list[DeliveryDateRecordEnvelope] = []
    first_executed = True
    predecessor_date: date | None = None
    coupled_blocked = False
    for classification in manifest.dates:
        delivery_date = classification.delivery_date
        predecessor = predecessor_date if not manifest.profile.is_independent else None
        if classification.execution_role == "excluded":
            records.append(
                _failure_envelope(
                    manifest,
                    classification,
                    predecessor_date=predecessor,
                    lifecycle_status="excluded",
                    reason="date_excluded_by_manifest",
                )
            )
            continue
        day_input = by_date.get(delivery_date)
        if coupled_blocked or day_input is None:
            lifecycle = (
                "blocked_by_predecessor"
                if not manifest.profile.is_independent
                else "failed"
            )
            reason = (
                "valid_predecessor_state_or_coupling_input_unavailable"
                if lifecycle == "blocked_by_predecessor"
                else "required_day_input_unavailable"
            )
            records.append(
                _failure_envelope(
                    manifest,
                    classification,
                    predecessor_date=predecessor,
                    lifecycle_status=lifecycle,
                    reason=reason,
                )
            )
            if not manifest.profile.is_independent:
                coupled_blocked = True
            predecessor_date = delivery_date
            first_executed = False
            continue
        try:
            problem, result, plan, plan_classification = _solve_day(
                manifest,
                day_input,
                first_executed=first_executed,
            )
            fields = _result_fields(result)
            lifecycle = (
                "unfinalized"
                if manifest.profile.state_mode == "rolling_0800"
                and classification.execution_role == "close-out"
                else "optimization_only"
            )
            revision = RollingFCRDayRevision(
                revision_number=0,
                revision_kind="optimization_only",
                lifecycle_status=lifecycle,
                creation_cause="profile_optimization_completed",
                input_fingerprint=day_input.day_input_fingerprint,
                problem_fingerprint=getattr(
                    problem,
                    "problem_fingerprint",
                    getattr(problem, "rolling_problem_fingerprint", None),
                ),
                plan_fingerprint=(None if plan is None else plan.plan_fingerprint),
                plan_classification=plan_classification,
                diagnostics=tuple(
                    str(value.code)
                    for value in getattr(result, "diagnostics", ())
                    if hasattr(value, "code")
                )
                or tuple(str(value) for value in getattr(result, "diagnostics", ())),
                **fields,
            )
            records.append(
                DeliveryDateRecordEnvelope(
                    manifest_fingerprint=manifest.manifest_fingerprint,
                    profile_fingerprint=manifest.profile.profile_fingerprint,
                    classification=classification,
                    predecessor_date=predecessor,
                    continuity_segment_id=f"{manifest.study_id}-segment-0",
                    revisions=(revision,),
                )
            )
            if result.solver.solve_status not in {"optimal", "feasible"}:
                coupled_blocked = not manifest.profile.is_independent
        except Exception as exc:
            records.append(
                _failure_envelope(
                    manifest,
                    classification,
                    predecessor_date=predecessor,
                    lifecycle_status="failed",
                    reason=f"optimization_failed:{type(exc).__name__}:{exc}",
                )
            )
            coupled_blocked = not manifest.profile.is_independent
        predecessor_date = delivery_date
        first_executed = False
    dates = tuple(item.delivery_date for item in manifest.dates)
    segment = ContinuitySegment(
        segment_id=f"{manifest.study_id}-segment-0",
        start_date=dates[0],
        end_date=dates[-1],
        start_reason="manifest_start",
    )
    latest_statuses = tuple(item.latest_revision.lifecycle_status for item in records)
    if any(status == "failed" for status in latest_statuses):
        completeness = "failed"
    elif any(
        status in {"blocked_by_predecessor", "unfinalized"}
        for status in latest_statuses
    ):
        completeness = "partial"
    else:
        completeness = "complete"
    return RollingFCRStudyResult(
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        records=tuple(records),
        continuity_segments=(segment,),
        state_links=(),
        aggregate_metrics=(),
        completeness_status=completeness,
        runtime_metadata={
            "phase": "initial-profile-optimization-v1",
            "activation_inspected": False,
        },
    )


__all__ = ["run_initial_rolling_fcr_study"]
