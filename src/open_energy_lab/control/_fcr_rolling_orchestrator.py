"""Private deterministic state machine for Feature 015 rolling studies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any

from .fcr_rolling_backtest import (
    ContinuitySegment,
    DeliveryDateRecordEnvelope,
    RollingFCRDayInput,
    RollingFCRDayRevision,
    RollingFCRStudyManifest,
    RollingFCRStudyResult,
    RollingFCRValidationError,
    RollingFCRStateLink,
    _fingerprint,
    aggregate_rolling_fcr_records,
    assess_rolling_fcr_resume,
    derive_rolling_fcr_state_carry,
)
from .robust_fcr_bidding import (
    RobustFCRSolveResult,
    _build_fixed_fcr_plan_from_decisions,
    build_robust_fcr_bidding_problem,
    solve_robust_fcr_bid,
)


@dataclass(frozen=True, slots=True)
class _SolvedRollingDay:
    day_input: RollingFCRDayInput
    problem: object
    result: object
    plan: object
    plan_classification: str
    original_revision: RollingFCRDayRevision


@dataclass(frozen=True, slots=True)
class _CausalCutoffEvidence:
    report: object
    prefix_activation_fingerprint: str
    causal_activation_fingerprint: str
    causal_replay_fingerprint: str
    replay_checkpoint_kwh: float
    handed_off_checkpoint_kwh: float
    state_carry_evidence: object


@dataclass(frozen=True, slots=True)
class _MidnightReplayEvidence:
    report: object
    activation_fingerprint: str
    state_carry_evidence: object


_PROCESS_INTEGRITY_ERRORS = (MemoryError, RecursionError)


def _normalized_date_failure(phase: str, exc: Exception) -> str:
    """Return stable per-date failure evidence or preserve process integrity."""

    if isinstance(exc, _PROCESS_INTEGRITY_ERRORS):
        raise exc
    return f"{phase}_failed:{type(exc).__name__}"


def _requested_day_input_fingerprints(
    day_inputs: tuple[RollingFCRDayInput, ...],
) -> dict[str, str]:
    return {
        item.date_classification.delivery_date.isoformat(): (
            item.day_input_fingerprint
        )
        for item in day_inputs
    }


def _supplied_activation_fingerprints(
    activation_traces: Mapping[date, object] | None,
) -> dict[str, str]:
    if activation_traces is None:
        return {}
    values: dict[str, str] = {}
    for delivery_date, trace in activation_traces.items():
        if not isinstance(delivery_date, date):
            raise RollingFCRValidationError(
                "activation trace keys must be delivery dates"
            )
        fingerprint = getattr(trace, "artifact_fingerprint", None)
        if not isinstance(fingerprint, str):
            raise RollingFCRValidationError(
                "activation trace must expose an artifact fingerprint"
            )
        values[delivery_date.isoformat()] = fingerprint
    return dict(sorted(values.items()))


def _causal_activation_fingerprint(trace: object) -> str:
    return _fingerprint(
        {
            "semantics": "feature-015-causal-prefix-activation-v1",
            "covered_period": trace.covered_period.to_dict(),
            "resolution": trace.resolution,
            "value_semantics": trace.value_semantics,
            "sign_semantics": trace.sign_semantics,
            "samples": [
                {
                    "interval": item.interval.to_dict(),
                    "activation": item.activation,
                }
                for item in trace.samples
            ],
        }
    )


def _segment_period(plan: object, *, start_hour: int, end_hour: int) -> object:
    from open_energy_lab.market import CanonicalInterval

    start = plan.energy_schedule.covered_period.start_utc
    return CanonicalInterval.from_utc(
        start + timedelta(hours=start_hour),
        start + timedelta(hours=end_hour),
        market_timezone=plan.energy_schedule.covered_period.market_timezone,
    )


def _accepted_market_context(
    manifest: RollingFCRStudyManifest,
    solved: _SolvedRollingDay,
    *,
    period: object,
    start_hour: int,
    end_hour: int,
) -> object:
    from open_energy_lab.simulator import build_accepted_plan_market_context

    first_fcr = start_hour // 4
    last_fcr = end_hour // 4
    return build_accepted_plan_market_context(
        plan=solved.plan,
        period=period,
        day_ahead_prices_eur_per_kwh=(
            solved.day_input.prices.day_ahead_energy_prices_eur_per_kwh[
                start_hour:end_hour
            ]
        ),
        fcr_capacity_prices_eur_per_kw_block=(
            solved.day_input.prices.fcr_capacity_prices_eur_per_kw_block[
                first_fcr:last_fcr
            ]
        ),
        acceptance_policy=manifest.acceptance_policy,
        source_fingerprints={
            "day_ahead_descriptor": (
                manifest.day_ahead_descriptor.normalized_data_fingerprint
            ),
            "fcr_capacity_descriptor": (
                manifest.fcr_capacity_descriptor.normalized_data_fingerprint
            ),
            "price_input": solved.day_input.prices.price_input_fingerprint,
        },
    )


def _evaluate_exact_plan_period(
    manifest: RollingFCRStudyManifest,
    solved: _SolvedRollingDay,
    *,
    period: object,
    activation_trace: object,
    initial_stored_energy_kwh: float,
    evaluation_suffix: str,
) -> object:
    from open_energy_lab.market import RegulationActivationTrace
    from open_energy_lab.simulator import evaluate_fixed_fcr_bid_segments

    if not isinstance(activation_trace, RegulationActivationTrace):
        raise RollingFCRValidationError(
            "causal replay requires a RegulationActivationTrace"
        )
    if activation_trace.covered_period != period:
        raise RollingFCRValidationError(
            "causal replay accepts only an exact pre-sliced activation period"
        )
    start = solved.plan.energy_schedule.covered_period.start_utc
    start_hour = int((period.start_utc - start) / timedelta(hours=1))
    end_hour = int((period.end_utc - start) / timedelta(hours=1))
    context = _accepted_market_context(
        manifest,
        solved,
        period=period,
        start_hour=start_hour,
        end_hour=end_hour,
    )
    return evaluate_fixed_fcr_bid_segments(
        evaluation_id=(
            f"{manifest.study_id}-"
            f"{solved.day_input.date_classification.delivery_date}-"
            f"{evaluation_suffix}"
        ),
        plan=solved.plan,
        periods=(period,),
        market_contexts=(context,),
        activation_trace=activation_trace,
        battery_binding=manifest.battery_binding,
        initial_stored_energy_kwh=initial_stored_energy_kwh,
        settlement_profile=manifest.settlement_profile,
        numeric_tolerance=manifest.numeric_policy.state_link_tolerance_kwh,
    )


def _derive_causal_0800_checkpoint(
    manifest: RollingFCRStudyManifest,
    solved: _SolvedRollingDay,
    *,
    prefix_activation_trace: object,
    initial_stored_energy_kwh: float,
) -> _CausalCutoffEvidence:
    """Replay only [00:00, 08:00) and return validated cutoff evidence."""

    prefix_period = _segment_period(solved.plan, start_hour=0, end_hour=8)
    report = _evaluate_exact_plan_period(
        manifest,
        solved,
        period=prefix_period,
        activation_trace=prefix_activation_trace,
        initial_stored_energy_kwh=initial_stored_energy_kwh,
        evaluation_suffix="causal-prefix-0000-0800-v1",
    )
    checkpoint = float(report.terminal_stored_energy_kwh)
    battery = manifest.battery_binding.optimization_battery
    tolerance = manifest.numeric_policy.state_link_tolerance_kwh
    if not (
        battery.minimum_stored_energy_kwh - tolerance
        <= checkpoint
        <= battery.maximum_stored_energy_kwh + tolerance
    ):
        raise RollingFCRValidationError(
            "Feature 012 cutoff checkpoint lies outside declared battery bounds"
        )
    carry_evidence = derive_rolling_fcr_state_carry(
        checkpoint,
        state_carry_policy="source_three_decimal",
    )
    handed_off = carry_evidence.carried_stored_energy_kwh
    if not (
        battery.minimum_stored_energy_kwh
        <= handed_off
        <= battery.maximum_stored_energy_kwh
    ):
        raise RollingFCRValidationError(
            "rounded cutoff checkpoint lies outside declared battery bounds"
        )
    causal_activation = _causal_activation_fingerprint(prefix_activation_trace)
    causal_replay = _fingerprint(
        {
            "semantics": "feature-015-causal-prefix-replay-v1",
            "plan_fingerprint": solved.plan.plan_fingerprint,
            "activation_prefix_fingerprint": causal_activation,
            "battery_binding_fingerprint": (
                manifest.battery_binding.binding_fingerprint
            ),
            "initial_stored_energy_kwh": initial_stored_energy_kwh,
            "replay_checkpoint_kwh": checkpoint,
            "handed_off_checkpoint_kwh": handed_off,
            "state_carry_evidence_fingerprint": (
                carry_evidence.evidence_fingerprint
            ),
            "additive_metrics": dict(report.additive_metrics),
            "extrema": dict(report.extrema),
        }
    )
    return _CausalCutoffEvidence(
        report=report,
        prefix_activation_fingerprint=(
            prefix_activation_trace.artifact_fingerprint
        ),
        causal_activation_fingerprint=causal_activation,
        causal_replay_fingerprint=causal_replay,
        replay_checkpoint_kwh=checkpoint,
        handed_off_checkpoint_kwh=handed_off,
        state_carry_evidence=carry_evidence,
    )


def _diagnostic_relaxation_plan(
    day_input: RollingFCRDayInput,
    result: RobustFCRSolveResult,
) -> Any | None:
    if result.decisions is None or result.solver.objective_value_eur is None:
        return None
    from open_energy_lab.simulator.fcr_bid_plan import (
        BidPlanProducer,
        OptimizationMetric,
        PlanDiagnostic,
    )

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
        "independent_residuals": (
            {}
            if audit is None
            else {
                item.family_id: item.maximum_positive_violation
                for item in getattr(audit, "constraint_families", ())
            }
        ),
        "energy_decisions_charge_positive_kw": (
            None
            if decisions is None
            else decisions.energy_baseline_charge_positive_kw
        ),
        "fcr_capacity_kw": None if decisions is None else decisions.fcr_capacity_kw,
        "runtime_metadata": getattr(result, "runtime_metadata", {}),
    }


def _solved_day_from_result(
    day_input: RollingFCRDayInput,
    problem: object,
    result: object,
    plan: object,
    plan_classification: str,
    *,
    lifecycle_status: str = "optimization_only",
) -> _SolvedRollingDay:
    fields = _result_fields(result)
    revision = RollingFCRDayRevision(
        revision_number=0,
        revision_kind="original",
        lifecycle_status=lifecycle_status,
        creation_cause="profile_optimization_completed",
        input_fingerprint=day_input.day_input_fingerprint,
        problem_fingerprint=getattr(
            problem,
            "problem_fingerprint",
            getattr(problem, "rolling_problem_fingerprint", None),
        ),
        plan_fingerprint=None if plan is None else plan.plan_fingerprint,
        plan_classification=plan_classification,
        initial_stored_energy_kwh=day_input.battery.initial_stored_energy_kwh,
        diagnostics=tuple(
            str(value.code)
            for value in getattr(result, "diagnostics", ())
            if hasattr(value, "code")
        )
        or tuple(str(value) for value in getattr(result, "diagnostics", ())),
        **fields,
    )
    return _SolvedRollingDay(
        day_input=day_input,
        problem=problem,
        result=result,
        plan=plan,
        plan_classification=plan_classification,
        original_revision=revision,
    )


def _append_revision(
    envelope: DeliveryDateRecordEnvelope,
    revision: RollingFCRDayRevision,
) -> DeliveryDateRecordEnvelope:
    if revision.revision_number != len(envelope.revisions):
        raise RollingFCRValidationError(
            "appended revision number does not follow immutable history"
        )
    return DeliveryDateRecordEnvelope(
        manifest_fingerprint=envelope.manifest_fingerprint,
        profile_fingerprint=envelope.profile_fingerprint,
        profile_id=envelope.profile_id,
        classification=envelope.classification,
        predecessor_date=envelope.predecessor_date,
        continuity_segment_id=envelope.continuity_segment_id,
        revisions=(*envelope.revisions, revision),
        decision_cutoff_utc=envelope.decision_cutoff_utc,
        information_cutoff_utc=envelope.information_cutoff_utc,
    )


def _envelope_for_solved_day(
    manifest: RollingFCRStudyManifest,
    solved: _SolvedRollingDay,
    *,
    predecessor_date: date | None,
    continuity_segment_id: str | None = None,
) -> DeliveryDateRecordEnvelope:
    return DeliveryDateRecordEnvelope(
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        profile_id=manifest.profile.profile_id,
        classification=solved.day_input.date_classification,
        predecessor_date=predecessor_date,
        continuity_segment_id=(
            continuity_segment_id or f"{manifest.study_id}-segment-0"
        ),
        revisions=(solved.original_revision,),
        decision_cutoff_utc=solved.day_input.decision_cutoff_utc,
        information_cutoff_utc=solved.day_input.information_cutoff_utc,
    )


def _build_0800_successor_problem(
    manifest: RollingFCRStudyManifest,
    base_input: RollingFCRDayInput,
    predecessor: _SolvedRollingDay,
    cutoff: _CausalCutoffEvidence,
) -> tuple[RollingFCRDayInput, object, object]:
    from .robust_fcr_rolling import (
        build_robust_fcr_rolling_problem,
        extract_accepted_predecessor_fixings,
    )

    predecessor_problem_fingerprint = getattr(
        predecessor.problem,
        "problem_fingerprint",
        getattr(predecessor.problem, "rolling_problem_fingerprint", None),
    )
    predecessor_result_fingerprint = _result_fields(predecessor.result)[
        "solve_result_fingerprint"
    ]
    fixings = extract_accepted_predecessor_fixings(
        plan=predecessor.plan,
        predecessor_problem_fingerprint=predecessor_problem_fingerprint,
        predecessor_result_fingerprint=predecessor_result_fingerprint,
    )
    if (
        base_input.accepted_fixings is not None
        and base_input.accepted_fixings.fixings_fingerprint
        != fixings.fixings_fingerprint
    ):
        raise RollingFCRValidationError(
            "caller-provided predecessor fixings differ from the accepted plan"
        )
    if (
        base_input.predecessor_prices is not None
        and base_input.predecessor_prices.price_input_fingerprint
        != predecessor.day_input.prices.price_input_fingerprint
    ):
        raise RollingFCRValidationError(
            "caller-provided predecessor prices differ from the listed predecessor"
        )
    cutoff_utc = predecessor.plan.energy_schedule.covered_period.start_utc + timedelta(
        hours=8
    )
    battery = replace(
        base_input.battery,
        initial_stored_energy_kwh=cutoff.handed_off_checkpoint_kwh,
    )
    successor_input = replace(
        base_input,
        battery=battery,
        decision_cutoff_utc=cutoff_utc,
        information_cutoff_utc=cutoff_utc,
        predecessor_prices=predecessor.day_input.prices,
        accepted_fixings=fixings,
        predecessor_cutoff_utc=cutoff_utc,
        producer_input_fingerprints={
            **dict(base_input.producer_input_fingerprints),
            "accepted_fixings": fixings.fixings_fingerprint,
            "cutoff_checkpoint": cutoff.causal_replay_fingerprint,
        },
        provenance={
            **dict(base_input.provenance),
            "predecessor_delivery_date": (
                predecessor.day_input.date_classification.delivery_date.isoformat()
            ),
            "state_handoff_rule": "source-three-decimal-at-0800-v1",
        },
    )
    problem = build_robust_fcr_rolling_problem(
        problem_id=(
            f"{manifest.study_id}-"
            f"{successor_input.date_classification.delivery_date}-rolling-v1"
        ),
        profile=manifest.profile,
        current_time_contract=successor_input.time_contract,
        battery=successor_input.battery,
        current_prices=successor_input.prices,
        uncertainty=manifest.uncertainty_profile,
        terminal_rule=manifest.terminal_rule,
        solve_policy=manifest.solve_policy,
        information_cutoff_utc=successor_input.information_cutoff_utc,
        producer_input_fingerprints=(
            successor_input.producer_input_fingerprints
        ),
        provenance=successor_input.provenance,
        predecessor_prices=successor_input.predecessor_prices,
        accepted_fixings=successor_input.accepted_fixings,
        predecessor_cutoff_utc=successor_input.predecessor_cutoff_utc,
    )
    return successor_input, fixings, problem


def _cutoff_state_link(
    manifest: RollingFCRStudyManifest,
    predecessor: _SolvedRollingDay,
    successor_input: RollingFCRDayInput,
    fixings: object,
    successor_problem: object,
    cutoff: _CausalCutoffEvidence,
) -> RollingFCRStateLink:
    carried = cutoff.handed_off_checkpoint_kwh
    return RollingFCRStateLink(
        predecessor_date=(
            predecessor.day_input.date_classification.delivery_date
        ),
        successor_date=successor_input.date_classification.delivery_date,
        handoff_kind="cutoff_0800",
        observation_cutoff_utc=successor_input.information_cutoff_utc,
        replay_checkpoint_kwh=cutoff.replay_checkpoint_kwh,
        carried_stored_energy_kwh=carried,
        rounding_policy=manifest.numeric_policy.state_carry_policy,
        source_interval_kwh=cutoff.state_carry_evidence.source_interval_kwh,
        predecessor_plan_fingerprint=predecessor.plan.plan_fingerprint,
        replay_fingerprint=cutoff.causal_replay_fingerprint,
        activation_fingerprint=cutoff.causal_activation_fingerprint,
        continuity_segment_id=f"{manifest.study_id}-segment-0",
        reconciles=(
            abs(successor_input.battery.initial_stored_energy_kwh - carried)
            <= manifest.numeric_policy.state_link_tolerance_kwh
        ),
        accepted_fixings_fingerprint=fixings.fixings_fingerprint,
        successor_problem_fingerprint=(
            successor_problem.rolling_problem_fingerprint
        ),
        causal_prefix_fingerprint=cutoff.causal_replay_fingerprint,
        rounding_evidence_fingerprint=(
            cutoff.state_carry_evidence.evidence_fingerprint
        ),
        successor_initial_stored_energy_kwh=(
            successor_input.battery.initial_stored_energy_kwh
        ),
        reconciliation_tolerance_kwh=(
            manifest.numeric_policy.state_link_tolerance_kwh
        ),
    )


def _flatten_realized_metrics(report: object) -> dict[str, float]:
    values = {
        str(key): float(value) for key, value in report.additive_metrics.items()
    }
    values.update(
        {
            f"settlement.{key}": float(value)
            for key, value in report.settlement_components_eur.items()
        }
    )
    return values


def _combined_realized_metrics(prefix: object, tail: object) -> dict[str, float]:
    keys = set(prefix.additive_metrics) | set(tail.additive_metrics)
    values = {
        str(key): float(prefix.additive_metrics.get(key, 0.0))
        + float(tail.additive_metrics.get(key, 0.0))
        for key in keys
    }
    settlement_keys = set(prefix.settlement_components_eur) | set(
        tail.settlement_components_eur
    )
    values.update(
        {
            f"settlement.{key}": float(
                prefix.settlement_components_eur.get(key, 0.0)
            )
            + float(tail.settlement_components_eur.get(key, 0.0))
            for key in settlement_keys
        }
    )
    return values


def _build_midnight_problem(
    manifest: RollingFCRStudyManifest,
    day_input: RollingFCRDayInput,
) -> object:
    if manifest.profile.profile_id == "script-15-restriction-rolling-midnight-v1":
        return _ordinary_problem(manifest, day_input)
    if manifest.profile.profile_id != "script-13-arbitrage-only-midnight-v1":
        raise RollingFCRValidationError(
            "midnight carry orchestration supports only scripts 13 and 15"
        )
    from .robust_fcr_rolling import build_robust_fcr_rolling_problem

    return build_robust_fcr_rolling_problem(
        problem_id=(
            f"{manifest.study_id}-{day_input.date_classification.delivery_date}-"
            "midnight-v1"
        ),
        profile=manifest.profile,
        current_time_contract=day_input.time_contract,
        battery=day_input.battery,
        current_prices=day_input.prices,
        uncertainty=manifest.uncertainty_profile,
        terminal_rule=manifest.terminal_rule,
        solve_policy=manifest.solve_policy,
        information_cutoff_utc=day_input.information_cutoff_utc,
        producer_input_fingerprints=day_input.producer_input_fingerprints,
        provenance=day_input.provenance,
    )


def _solve_midnight_problem(
    manifest: RollingFCRStudyManifest,
    day_input: RollingFCRDayInput,
    problem: object,
) -> _SolvedRollingDay:
    if manifest.profile.profile_id == "script-15-restriction-rolling-midnight-v1":
        result = solve_robust_fcr_bid(problem, formulation="restriction")
        plan = result.deployable_plan
        classification = manifest.profile.plan_classification
    else:
        from .robust_fcr_rolling import solve_robust_fcr_rolling_bid

        result = solve_robust_fcr_rolling_bid(problem)
        plan = result.plan
        classification = result.plan_classification
    return _solved_day_from_result(
        day_input,
        problem,
        result,
        plan,
        classification,
    )


def _evaluate_midnight_day(
    manifest: RollingFCRStudyManifest,
    solved: _SolvedRollingDay,
    activation_trace: object,
) -> _MidnightReplayEvidence:
    report = _evaluate_full_day(
        manifest,
        solved,
        activation_trace=activation_trace,
        evaluation_suffix="midnight-full-day-v1",
    )
    carry = derive_rolling_fcr_state_carry(
        report.terminal_stored_energy_kwh,
        state_carry_policy=manifest.numeric_policy.state_carry_policy,
    )
    battery = manifest.battery_binding.optimization_battery
    if not (
        battery.minimum_stored_energy_kwh
        <= carry.carried_stored_energy_kwh
        <= battery.maximum_stored_energy_kwh
    ):
        raise RollingFCRValidationError(
            "midnight carried state lies outside declared battery bounds"
        )
    return _MidnightReplayEvidence(
        report=report,
        activation_fingerprint=activation_trace.artifact_fingerprint,
        state_carry_evidence=carry,
    )


def _evaluate_full_day(
    manifest: RollingFCRStudyManifest,
    solved: _SolvedRollingDay,
    *,
    activation_trace: object,
    evaluation_suffix: str,
) -> object:
    """Evaluate one accepted ordinary-day plan only through Feature 012."""

    if solved.plan is None:
        raise RollingFCRValidationError(
            "full-day replay requires an accepted fixed plan"
        )
    return _evaluate_exact_plan_period(
        manifest,
        solved,
        period=solved.plan.energy_schedule.covered_period,
        activation_trace=activation_trace,
        initial_stored_energy_kwh=(
            solved.day_input.battery.initial_stored_energy_kwh
        ),
        evaluation_suffix=evaluation_suffix,
    )


def _build_midnight_successor_input(
    manifest: RollingFCRStudyManifest,
    base_input: RollingFCRDayInput,
    predecessor: _SolvedRollingDay,
    replay: _MidnightReplayEvidence,
) -> RollingFCRDayInput:
    if base_input.accepted_fixings is not None or base_input.predecessor_prices is not None:
        raise RollingFCRValidationError(
            "midnight carry input must not contain 08:00 predecessor fixings"
        )
    carried = replay.state_carry_evidence.carried_stored_energy_kwh
    battery = replace(
        base_input.battery,
        initial_stored_energy_kwh=carried,
    )
    successor = replace(
        base_input,
        battery=battery,
        producer_input_fingerprints={
            **dict(base_input.producer_input_fingerprints),
            "numeric_policy": manifest.numeric_policy.numeric_policy_fingerprint,
            "state_carry_evidence": (
                replay.state_carry_evidence.evidence_fingerprint
            ),
        },
        provenance={
            **dict(base_input.provenance),
            "predecessor_delivery_date": (
                predecessor.day_input.date_classification.delivery_date.isoformat()
            ),
            "state_handoff_rule": manifest.numeric_policy.state_carry_policy,
        },
    )
    if (
        abs(successor.battery.initial_stored_energy_kwh - carried)
        > manifest.numeric_policy.state_link_tolerance_kwh
    ):
        raise RollingFCRValidationError(
            "successor initial state does not reconcile with midnight carry"
        )
    return successor


def _midnight_state_link(
    manifest: RollingFCRStudyManifest,
    predecessor: _SolvedRollingDay,
    successor_input: RollingFCRDayInput,
    successor_problem: object,
    replay: _MidnightReplayEvidence,
    *,
    continuity_segment_id: str,
) -> RollingFCRStateLink:
    carry = replay.state_carry_evidence
    return RollingFCRStateLink(
        predecessor_date=(
            predecessor.day_input.date_classification.delivery_date
        ),
        successor_date=successor_input.date_classification.delivery_date,
        handoff_kind="midnight",
        observation_cutoff_utc=(
            predecessor.plan.energy_schedule.covered_period.end_utc
        ),
        replay_checkpoint_kwh=carry.replay_checkpoint_kwh,
        carried_stored_energy_kwh=carry.carried_stored_energy_kwh,
        rounding_policy=carry.state_carry_policy,
        source_interval_kwh=carry.source_interval_kwh,
        predecessor_plan_fingerprint=predecessor.plan.plan_fingerprint,
        replay_fingerprint=replay.report.semantic_fingerprint,
        activation_fingerprint=replay.activation_fingerprint,
        continuity_segment_id=continuity_segment_id,
        reconciles=True,
        successor_problem_fingerprint=getattr(
            successor_problem,
            "problem_fingerprint",
            getattr(successor_problem, "rolling_problem_fingerprint", None),
        ),
        rounding_evidence_fingerprint=carry.evidence_fingerprint,
        successor_initial_stored_energy_kwh=(
            successor_input.battery.initial_stored_energy_kwh
        ),
        reconciliation_tolerance_kwh=(
            manifest.numeric_policy.state_link_tolerance_kwh
        ),
    )


def _caller_successor_input(
    manifest: RollingFCRStudyManifest,
    base_input: RollingFCRDayInput,
    declaration: object,
) -> RollingFCRDayInput:
    if declaration.observation_cutoff_utc != base_input.time_contract.delivery_period.start_utc:
        raise RollingFCRValidationError(
            "caller-supplied state cutoff must equal the delivery handoff"
        )
    battery = replace(
        base_input.battery,
        initial_stored_energy_kwh=declaration.stored_energy_kwh,
    )
    return replace(
        base_input,
        battery=battery,
        producer_input_fingerprints={
            **dict(base_input.producer_input_fingerprints),
            "caller_state": declaration.state_fingerprint,
            "numeric_policy": manifest.numeric_policy.numeric_policy_fingerprint,
        },
        provenance={
            **dict(base_input.provenance),
            "continuity_origin": "caller_supplied",
        },
    )


def _caller_state_link(
    manifest: RollingFCRStudyManifest,
    declaration: object,
    successor_input: RollingFCRDayInput,
    successor_problem: object,
    *,
    continuity_segment_id: str,
) -> RollingFCRStateLink:
    value = declaration.stored_energy_kwh
    return RollingFCRStateLink(
        predecessor_date=declaration.delivery_date,
        successor_date=declaration.delivery_date,
        handoff_kind="caller_supplied",
        observation_cutoff_utc=declaration.observation_cutoff_utc,
        replay_checkpoint_kwh=value,
        carried_stored_energy_kwh=value,
        rounding_policy="caller_supplied",
        source_interval_kwh=(value, value),
        predecessor_plan_fingerprint=None,
        replay_fingerprint=None,
        activation_fingerprint=None,
        continuity_segment_id=continuity_segment_id,
        reconciles=True,
        successor_problem_fingerprint=getattr(
            successor_problem,
            "problem_fingerprint",
            getattr(successor_problem, "rolling_problem_fingerprint", None),
        ),
        rounding_evidence_fingerprint=declaration.state_fingerprint,
        successor_initial_stored_energy_kwh=(
            successor_input.battery.initial_stored_energy_kwh
        ),
        reconciliation_tolerance_kwh=(
            manifest.numeric_policy.state_link_tolerance_kwh
        ),
    )


def _finalized_midnight_revision(
    solved: _SolvedRollingDay,
    replay: _MidnightReplayEvidence,
    *,
    revision_number: int,
    predecessor_revision_fingerprint: str,
    state_link_fingerprint: str | None,
) -> RollingFCRDayRevision:
    fields = _result_fields(solved.result)
    carry = replay.state_carry_evidence
    return RollingFCRDayRevision(
        revision_number=revision_number,
        revision_kind="finalized",
        lifecycle_status="finalized",
        creation_cause="same_day_feature_012_replay_completed",
        input_fingerprint=solved.day_input.day_input_fingerprint,
        problem_fingerprint=getattr(
            solved.problem,
            "problem_fingerprint",
            getattr(solved.problem, "rolling_problem_fingerprint", None),
        ),
        plan_fingerprint=solved.plan.plan_fingerprint,
        plan_classification=solved.plan_classification,
        activation_fingerprint=replay.activation_fingerprint,
        replay_fingerprint=replay.report.semantic_fingerprint,
        settlement_fingerprint=_fingerprint(
            dict(replay.report.settlement_components_eur)
        ),
        state_link_fingerprint=state_link_fingerprint,
        predecessor_revision_fingerprint=predecessor_revision_fingerprint,
        initial_stored_energy_kwh=replay.report.initial_stored_energy_kwh,
        realized_terminal_stored_energy_kwh=(
            replay.report.terminal_stored_energy_kwh
        ),
        carried_stored_energy_kwh=carry.carried_stored_energy_kwh,
        realized_metrics=_flatten_realized_metrics(replay.report),
        diagnostics=(
            f"state_carry_policy:{carry.state_carry_policy}",
            "successor_state_uses_realized_not_modeled_terminal",
        ),
        **fields,
    )


def _finalized_independent_revision(
    solved: _SolvedRollingDay,
    report: object,
    *,
    activation_fingerprint: str,
) -> RollingFCRDayRevision:
    """Finalize an independent accepted plan without creating carry evidence."""

    fields = _result_fields(solved.result)
    return RollingFCRDayRevision(
        revision_number=1,
        revision_kind="finalized",
        lifecycle_status="finalized",
        creation_cause="same_day_feature_012_replay_completed",
        input_fingerprint=solved.day_input.day_input_fingerprint,
        problem_fingerprint=getattr(
            solved.problem,
            "problem_fingerprint",
            getattr(solved.problem, "rolling_problem_fingerprint", None),
        ),
        plan_fingerprint=solved.plan.plan_fingerprint,
        plan_classification=solved.plan_classification,
        activation_fingerprint=activation_fingerprint,
        replay_fingerprint=report.semantic_fingerprint,
        settlement_fingerprint=_fingerprint(
            dict(report.settlement_components_eur)
        ),
        predecessor_revision_fingerprint=(
            solved.original_revision.revision_fingerprint
        ),
        initial_stored_energy_kwh=report.initial_stored_energy_kwh,
        realized_terminal_stored_energy_kwh=(
            report.terminal_stored_energy_kwh
        ),
        realized_metrics=_flatten_realized_metrics(report),
        diagnostics=(
            "accepted_plan_evaluated_by_feature_012",
            "independent_day_resets_after_delivery",
            f"plan_classification_preserved:{solved.plan_classification}",
        ),
        **fields,
    )


def _failure_envelope(
    manifest: RollingFCRStudyManifest,
    classification: object,
    *,
    predecessor_date: date | None,
    lifecycle_status: str,
    reason: str,
    continuity_segment_id: str | None = None,
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
        profile_id=manifest.profile.profile_id,
        classification=classification,
        predecessor_date=predecessor_date,
        continuity_segment_id=(
            continuity_segment_id or f"{manifest.study_id}-segment-0"
        ),
        revisions=(revision,),
    )


def _prefix_trace_for_solved_day(
    solved: _SolvedRollingDay,
    full_trace: object,
) -> object:
    from open_energy_lab.market import slice_regulation_activation_trace

    period = _segment_period(solved.plan, start_hour=0, end_hour=8)
    return slice_regulation_activation_trace(full_trace, period=period)


def _tail_trace_for_solved_day(
    solved: _SolvedRollingDay,
    full_trace: object,
) -> object:
    from open_energy_lab.market import slice_regulation_activation_trace

    period = _segment_period(solved.plan, start_hour=8, end_hour=24)
    return slice_regulation_activation_trace(full_trace, period=period)


def _provisional_revision(
    solved: _SolvedRollingDay,
    cutoff: _CausalCutoffEvidence,
    state_link: RollingFCRStateLink,
) -> RollingFCRDayRevision:
    fields = _result_fields(solved.result)
    return RollingFCRDayRevision(
        revision_number=1,
        revision_kind="provisional",
        lifecycle_status="provisional",
        creation_cause="causal_0800_prefix_replayed_before_successor_solve",
        input_fingerprint=solved.day_input.day_input_fingerprint,
        problem_fingerprint=getattr(
            solved.problem,
            "problem_fingerprint",
            getattr(solved.problem, "rolling_problem_fingerprint", None),
        ),
        plan_fingerprint=solved.plan.plan_fingerprint,
        plan_classification=solved.plan_classification,
        activation_fingerprint=cutoff.prefix_activation_fingerprint,
        replay_fingerprint=cutoff.report.semantic_fingerprint,
        settlement_fingerprint=_fingerprint(
            dict(cutoff.report.settlement_components_eur)
        ),
        state_link_fingerprint=state_link.state_link_fingerprint,
        predecessor_revision_fingerprint=(
            solved.original_revision.revision_fingerprint
        ),
        initial_stored_energy_kwh=(
            cutoff.report.initial_stored_energy_kwh
        ),
        realized_cutoff_stored_energy_kwh=cutoff.replay_checkpoint_kwh,
        handed_off_cutoff_stored_energy_kwh=(
            cutoff.handed_off_checkpoint_kwh
        ),
        carried_stored_energy_kwh=cutoff.handed_off_checkpoint_kwh,
        realized_metrics=_flatten_realized_metrics(cutoff.report),
        diagnostics=(
            "causal_prefix_contains_no_post_cutoff_samples",
            "accepted_predecessor_plan_unchanged",
        ),
        **fields,
    )


def _finalized_revision(
    solved: _SolvedRollingDay,
    cutoff: _CausalCutoffEvidence,
    tail_report: object,
    state_link: RollingFCRStateLink,
    provisional_revision: RollingFCRDayRevision,
    finalizer: _SolvedRollingDay,
    *,
    initialization_only: bool,
) -> RollingFCRDayRevision:
    fields = _result_fields(solved.result)
    replay_fingerprint = _fingerprint(
        {
            "semantics": "feature-015-immutable-0800-finalization-v1",
            "unchanged_plan_fingerprint": solved.plan.plan_fingerprint,
            "prefix_replay_fingerprint": cutoff.report.semantic_fingerprint,
            "tail_replay_fingerprint": tail_report.semantic_fingerprint,
            "rounded_tail_initial_stored_energy_kwh": (
                cutoff.handed_off_checkpoint_kwh
            ),
        }
    )
    activation_fingerprint = _fingerprint(
        {
            "prefix": cutoff.prefix_activation_fingerprint,
            "tail": tail_report.activation_trace_fingerprint,
        }
    )
    realized_metrics = _combined_realized_metrics(cutoff.report, tail_report)
    settlement_fingerprint = _fingerprint(
        {
            key: value
            for key, value in realized_metrics.items()
            if key.startswith("settlement.")
        }
    )
    finalizer_problem_fingerprint = getattr(
        finalizer.problem,
        "problem_fingerprint",
        getattr(finalizer.problem, "rolling_problem_fingerprint", None),
    )
    return RollingFCRDayRevision(
        revision_number=2,
        revision_kind="finalized",
        lifecycle_status=(
            "initialization_only" if initialization_only else "finalized"
        ),
        creation_cause="successor_solve_triggered_unchanged_plan_tail_replay",
        input_fingerprint=solved.day_input.day_input_fingerprint,
        problem_fingerprint=getattr(
            solved.problem,
            "problem_fingerprint",
            getattr(solved.problem, "rolling_problem_fingerprint", None),
        ),
        plan_fingerprint=solved.plan.plan_fingerprint,
        plan_classification=solved.plan_classification,
        activation_fingerprint=activation_fingerprint,
        replay_fingerprint=replay_fingerprint,
        settlement_fingerprint=settlement_fingerprint,
        state_link_fingerprint=state_link.state_link_fingerprint,
        predecessor_revision_fingerprint=(
            provisional_revision.revision_fingerprint
        ),
        finalizer_problem_fingerprint=finalizer_problem_fingerprint,
        finalizer_result_fingerprint=_result_fields(finalizer.result)[
            "solve_result_fingerprint"
        ],
        initial_stored_energy_kwh=cutoff.report.initial_stored_energy_kwh,
        realized_cutoff_stored_energy_kwh=cutoff.replay_checkpoint_kwh,
        handed_off_cutoff_stored_energy_kwh=(
            cutoff.handed_off_checkpoint_kwh
        ),
        realized_terminal_stored_energy_kwh=(
            tail_report.terminal_stored_energy_kwh
        ),
        carried_stored_energy_kwh=cutoff.handed_off_checkpoint_kwh,
        realized_metrics=realized_metrics,
        diagnostics=(
            "finalized_after_successor_solve",
            "original_full_day_plan_fingerprint_preserved",
        ),
        **fields,
    )


def _unfinalized_revision(
    solved: _SolvedRollingDay,
    cutoff: _CausalCutoffEvidence | None = None,
) -> RollingFCRDayRevision:
    fields = _result_fields(solved.result)
    return RollingFCRDayRevision(
        revision_number=1,
        revision_kind=("provisional" if cutoff is not None else "optimization_only"),
        lifecycle_status="unfinalized",
        creation_cause="following_0800_closeout_solve_unavailable",
        input_fingerprint=solved.day_input.day_input_fingerprint,
        problem_fingerprint=getattr(
            solved.problem,
            "problem_fingerprint",
            getattr(solved.problem, "rolling_problem_fingerprint", None),
        ),
        plan_fingerprint=solved.plan.plan_fingerprint,
        plan_classification=solved.plan_classification,
        predecessor_revision_fingerprint=(
            solved.original_revision.revision_fingerprint
        ),
        activation_fingerprint=(
            None if cutoff is None else cutoff.prefix_activation_fingerprint
        ),
        replay_fingerprint=(
            None if cutoff is None else cutoff.report.semantic_fingerprint
        ),
        settlement_fingerprint=(
            None
            if cutoff is None
            else _fingerprint(dict(cutoff.report.settlement_components_eur))
        ),
        initial_stored_energy_kwh=(
            solved.day_input.battery.initial_stored_energy_kwh
            if cutoff is None
            else cutoff.report.initial_stored_energy_kwh
        ),
        realized_cutoff_stored_energy_kwh=(
            None if cutoff is None else cutoff.replay_checkpoint_kwh
        ),
        handed_off_cutoff_stored_energy_kwh=(
            None if cutoff is None else cutoff.handed_off_checkpoint_kwh
        ),
        carried_stored_energy_kwh=(
            None if cutoff is None else cutoff.handed_off_checkpoint_kwh
        ),
        realized_metrics=(
            {} if cutoff is None else _flatten_realized_metrics(cutoff.report)
        ),
        diagnostics=(
            "delivery_record_awaits_following_0800_solve",
            "excluded_from_finalized_parity_aggregates",
        ),
        **fields,
    )


def _run_causal_0800_study(
    manifest: RollingFCRStudyManifest,
    day_inputs: tuple[RollingFCRDayInput, ...],
    *,
    activation_traces: Mapping[date, object] | None,
) -> RollingFCRStudyResult:
    """Run the source-compatible causal 08:00 state machine."""

    from .robust_fcr_rolling import solve_robust_fcr_rolling_bid

    by_date = {item.date_classification.delivery_date: item for item in day_inputs}
    if len(by_date) != len(day_inputs):
        raise RollingFCRValidationError("day_inputs must identify unique dates")
    traces = {} if activation_traces is None else activation_traces
    if not isinstance(traces, Mapping):
        raise RollingFCRValidationError("activation_traces must be a date mapping")
    records: dict[date, DeliveryDateRecordEnvelope] = {}
    state_links: list[RollingFCRStateLink] = []
    pending_solved: _SolvedRollingDay | None = None
    pending_cutoff: _CausalCutoffEvidence | None = None
    pending_full_trace: object | None = None
    pending_midnight_initial: float | None = None
    blocked = False

    for index, classification in enumerate(manifest.dates):
        delivery_date = classification.delivery_date
        predecessor_date = manifest.listed_predecessor_date(delivery_date)
        if classification.execution_role == "excluded":
            records[delivery_date] = _failure_envelope(
                manifest,
                classification,
                predecessor_date=predecessor_date,
                lifecycle_status="excluded",
                reason="date_excluded_by_manifest",
            )
            blocked = True
            pending_solved = None
            pending_cutoff = None
            pending_full_trace = None
            continue
        base_input = by_date.get(delivery_date)
        if base_input is None or blocked:
            records[delivery_date] = _failure_envelope(
                manifest,
                classification,
                predecessor_date=predecessor_date,
                lifecycle_status="blocked_by_predecessor" if blocked else "failed",
                reason=(
                    "valid_listed_predecessor_cutoff_unavailable"
                    if blocked
                    else "required_day_input_unavailable"
                ),
            )
            blocked = True
            continue
        try:
            if index == 0:
                problem, result, plan, plan_classification = _solve_day(
                    manifest,
                    base_input,
                    first_executed=True,
                )
                solved = _solved_day_from_result(
                    base_input,
                    problem,
                    result,
                    plan,
                    plan_classification,
                )
            else:
                if pending_solved is None or pending_cutoff is None:
                    raise RollingFCRValidationError(
                        "listed predecessor has no eligible causal 08:00 checkpoint"
                    )
                successor_input, fixings, problem = _build_0800_successor_problem(
                    manifest,
                    base_input,
                    pending_solved,
                    pending_cutoff,
                )
                state_link = _cutoff_state_link(
                    manifest,
                    pending_solved,
                    successor_input,
                    fixings,
                    problem,
                    pending_cutoff,
                )
                state_links.append(state_link)
                predecessor_envelope = records[
                    pending_solved.day_input.date_classification.delivery_date
                ]
                provisional_revision = _provisional_revision(
                    pending_solved,
                    pending_cutoff,
                    state_link,
                )
                predecessor_envelope = _append_revision(
                    predecessor_envelope,
                    provisional_revision,
                )
                records[
                    pending_solved.day_input.date_classification.delivery_date
                ] = predecessor_envelope

                result = solve_robust_fcr_rolling_bid(problem)
                plan = result.plan
                solved = _solved_day_from_result(
                    successor_input,
                    problem,
                    result,
                    plan,
                    result.plan_classification,
                    lifecycle_status=(
                        "unfinalized"
                        if classification.execution_role == "close-out"
                        else "optimization_only"
                    ),
                )
                if plan is None or result.solver.solve_status not in {
                    "optimal",
                    "feasible",
                }:
                    raise RollingFCRValidationError(
                        "successor solve produced no accepted audited plan"
                    )

                if pending_full_trace is None:
                    raise RollingFCRValidationError(
                        "listed predecessor activation is unavailable for finalization"
                    )
                tail_period = _segment_period(
                    pending_solved.plan,
                    start_hour=8,
                    end_hour=24,
                )
                tail_trace = _tail_trace_for_solved_day(
                    pending_solved,
                    pending_full_trace,
                )
                tail_report = _evaluate_exact_plan_period(
                    manifest,
                    pending_solved,
                    period=tail_period,
                    activation_trace=tail_trace,
                    initial_stored_energy_kwh=(
                        pending_cutoff.handed_off_checkpoint_kwh
                    ),
                    evaluation_suffix="successor-finalized-tail-0800-2400-v1",
                )
                predecessor_envelope = records[
                    pending_solved.day_input.date_classification.delivery_date
                ]
                predecessor_envelope = _append_revision(
                    predecessor_envelope,
                    _finalized_revision(
                        pending_solved,
                        pending_cutoff,
                        tail_report,
                        state_link,
                        provisional_revision,
                        solved,
                        initialization_only=(
                            pending_solved.day_input.date_classification.execution_role
                            == "warm-up"
                        ),
                    ),
                )
                records[
                    pending_solved.day_input.date_classification.delivery_date
                ] = predecessor_envelope
                pending_midnight_initial = tail_report.terminal_stored_energy_kwh

            if solved.plan is None or solved.result.solver.solve_status not in {
                "optimal",
                "feasible",
            }:
                raise RollingFCRValidationError(
                    "08:00 profile produced no accepted audited plan"
                )
            records[delivery_date] = _envelope_for_solved_day(
                manifest,
                solved,
                predecessor_date=predecessor_date,
            )
            is_last = index == len(manifest.dates) - 1
            if is_last:
                terminal_cutoff = None
                full_trace = traces.get(delivery_date)
                if full_trace is not None:
                    prefix_trace = _prefix_trace_for_solved_day(solved, full_trace)
                    prefix_initial = (
                        solved.day_input.battery.initial_stored_energy_kwh
                        if index == 0
                        else pending_midnight_initial
                    )
                    if prefix_initial is None:
                        raise RollingFCRValidationError(
                            "close-out midnight state is unavailable"
                        )
                    terminal_cutoff = _derive_causal_0800_checkpoint(
                        manifest,
                        solved,
                        prefix_activation_trace=prefix_trace,
                        initial_stored_energy_kwh=prefix_initial,
                    )
                records[delivery_date] = _append_revision(
                    records[delivery_date],
                    _unfinalized_revision(solved, terminal_cutoff),
                )
                pending_solved = None
                pending_cutoff = None
                pending_full_trace = None
                continue
            full_trace = traces.get(delivery_date)
            if full_trace is None:
                blocked = True
                pending_solved = None
                pending_cutoff = None
                pending_full_trace = None
                continue
            prefix_trace = _prefix_trace_for_solved_day(solved, full_trace)
            prefix_initial = (
                solved.day_input.battery.initial_stored_energy_kwh
                if index == 0
                else pending_midnight_initial
            )
            if prefix_initial is None:
                raise RollingFCRValidationError(
                    "current-day midnight state is unavailable after finalization"
                )
            pending_cutoff = _derive_causal_0800_checkpoint(
                manifest,
                solved,
                prefix_activation_trace=prefix_trace,
                initial_stored_energy_kwh=prefix_initial,
            )
            pending_solved = solved
            pending_full_trace = full_trace
        except Exception as exc:
            records[delivery_date] = _failure_envelope(
                manifest,
                classification,
                predecessor_date=predecessor_date,
                lifecycle_status="failed",
                reason=_normalized_date_failure("rolling_0800", exc),
            )
            blocked = True
            pending_solved = None
            pending_cutoff = None
            pending_full_trace = None

    ordered_records = tuple(
        records[item.delivery_date] for item in manifest.dates
    )
    dates = tuple(item.delivery_date for item in manifest.dates)
    segment = ContinuitySegment(
        segment_id=f"{manifest.study_id}-segment-0",
        start_date=dates[0],
        end_date=dates[-1],
        start_reason="manifest_start",
    )
    statuses = tuple(item.latest_revision.lifecycle_status for item in ordered_records)
    completeness = (
        "failed"
        if any(item == "failed" for item in statuses)
        else "partial"
        if any(
            item
            in {
                "initialization_only",
                "blocked_by_predecessor",
                "optimization_only",
                "provisional",
                "unfinalized",
            }
            for item in statuses
        )
        else "complete"
    )
    return RollingFCRStudyResult(
        study_id=manifest.study_id,
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_id=manifest.profile.profile_id,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        records=ordered_records,
        continuity_segments=(segment,),
        state_links=tuple(state_links),
        aggregate_metrics=aggregate_rolling_fcr_records(
            manifest, ordered_records
        ),
        completeness_status=completeness,
        requested_day_input_fingerprints=_requested_day_input_fingerprints(
            day_inputs
        ),
        supplied_activation_fingerprints=_supplied_activation_fingerprints(
            activation_traces
        ),
        runtime_metadata={
            "phase": "causal-0800-rolling-v1",
            "bidder_received_activation": False,
            "tail_replay_order": "strictly_after_successor_solve",
        },
    )


def _run_midnight_carry_study(
    manifest: RollingFCRStudyManifest,
    day_inputs: tuple[RollingFCRDayInput, ...],
    *,
    activation_traces: Mapping[date, object] | None,
) -> RollingFCRStudyResult:
    """Run realized Feature 012 midnight carry with explicit continuity."""

    by_date = {item.date_classification.delivery_date: item for item in day_inputs}
    if len(by_date) != len(day_inputs):
        raise RollingFCRValidationError("day_inputs must identify unique dates")
    traces = {} if activation_traces is None else activation_traces
    if not isinstance(traces, Mapping):
        raise RollingFCRValidationError("activation_traces must be a date mapping")
    declarations = {
        item.delivery_date: item for item in manifest.caller_state_declarations
    }
    records: dict[date, DeliveryDateRecordEnvelope] = {}
    state_links: list[RollingFCRStateLink] = []
    segment_members: dict[str, list[date]] = {
        f"{manifest.study_id}-segment-0": []
    }
    segment_reasons: dict[str, tuple[str, str | None]] = {
        f"{manifest.study_id}-segment-0": ("manifest_start", None)
    }
    active_segment = f"{manifest.study_id}-segment-0"
    pending_solved: _SolvedRollingDay | None = None
    pending_replay: _MidnightReplayEvidence | None = None
    blocked = False

    for index, classification in enumerate(manifest.dates):
        delivery_date = classification.delivery_date
        predecessor_date = manifest.listed_predecessor_date(delivery_date)
        declaration = declarations.get(delivery_date)
        if classification.execution_role == "excluded":
            records[delivery_date] = _failure_envelope(
                manifest,
                classification,
                predecessor_date=predecessor_date,
                lifecycle_status="excluded",
                reason="date_excluded_by_manifest",
                continuity_segment_id=active_segment,
            )
            blocked = True
            pending_solved = None
            pending_replay = None
            continue
        base_input = by_date.get(delivery_date)
        if base_input is None:
            records[delivery_date] = _failure_envelope(
                manifest,
                classification,
                predecessor_date=predecessor_date,
                lifecycle_status="failed" if index == 0 else "blocked_by_predecessor",
                reason="required_day_input_unavailable",
                continuity_segment_id=active_segment,
            )
            blocked = True
            pending_solved = None
            pending_replay = None
            continue
        if blocked and declaration is None:
            records[delivery_date] = _failure_envelope(
                manifest,
                classification,
                predecessor_date=predecessor_date,
                lifecycle_status="blocked_by_predecessor",
                reason="valid_realized_midnight_predecessor_unavailable",
                continuity_segment_id=active_segment,
            )
            continue

        incoming_link: RollingFCRStateLink | None = None
        incoming_predecessor_revision: str | None = None
        try:
            if pending_solved is not None and pending_replay is not None:
                if declaration is not None:
                    raise RollingFCRValidationError(
                        "caller state cannot override a valid physical predecessor"
                    )
                successor_input = _build_midnight_successor_input(
                    manifest,
                    base_input,
                    pending_solved,
                    pending_replay,
                )
                problem = _build_midnight_problem(manifest, successor_input)
                incoming_link = _midnight_state_link(
                    manifest,
                    pending_solved,
                    successor_input,
                    problem,
                    pending_replay,
                    continuity_segment_id=active_segment,
                )
                state_links.append(incoming_link)
                predecessor_delivery_date = (
                    pending_solved.day_input.date_classification.delivery_date
                )
                predecessor_envelope = records[predecessor_delivery_date]
                finalized = _finalized_midnight_revision(
                    pending_solved,
                    pending_replay,
                    revision_number=len(predecessor_envelope.revisions),
                    predecessor_revision_fingerprint=(
                        predecessor_envelope.latest_revision.revision_fingerprint
                    ),
                    state_link_fingerprint=incoming_link.state_link_fingerprint,
                )
                records[predecessor_delivery_date] = _append_revision(
                    predecessor_envelope,
                    finalized,
                )
                incoming_predecessor_revision = finalized.revision_fingerprint
            elif declaration is not None:
                active_segment = f"{manifest.study_id}-segment-{len(segment_members)}"
                segment_members[active_segment] = []
                segment_reasons[active_segment] = (
                    "caller_supplied",
                    declaration.state_fingerprint,
                )
                successor_input = _caller_successor_input(
                    manifest,
                    base_input,
                    declaration,
                )
                problem = _build_midnight_problem(manifest, successor_input)
                incoming_link = _caller_state_link(
                    manifest,
                    declaration,
                    successor_input,
                    problem,
                    continuity_segment_id=active_segment,
                )
                state_links.append(incoming_link)
                blocked = False
            elif index == 0:
                successor_input = replace(
                    base_input,
                    producer_input_fingerprints={
                        **dict(base_input.producer_input_fingerprints),
                        "numeric_policy": (
                            manifest.numeric_policy.numeric_policy_fingerprint
                        ),
                    },
                )
                expected_initial = (
                    manifest.battery_binding.optimization_battery.initial_stored_energy_kwh
                )
                if (
                    abs(
                        successor_input.battery.initial_stored_energy_kwh
                        - expected_initial
                    )
                    > manifest.numeric_policy.state_link_tolerance_kwh
                ):
                    raise RollingFCRValidationError(
                        "first midnight state does not match the manifest battery"
                    )
                problem = _build_midnight_problem(manifest, successor_input)
            else:
                raise RollingFCRValidationError(
                    "coupled midnight successor lacks an eligible state"
                )

            solved = _solve_midnight_problem(
                manifest,
                successor_input,
                problem,
            )
            if incoming_link is not None:
                original = replace(
                    solved.original_revision,
                    state_link_fingerprint=incoming_link.state_link_fingerprint,
                    predecessor_revision_fingerprint=(
                        incoming_predecessor_revision
                    ),
                )
                solved = replace(solved, original_revision=original)
            if solved.plan is None or solved.result.solver.solve_status not in {
                "optimal",
                "feasible",
            }:
                raise RollingFCRValidationError(
                    "midnight solve produced no accepted audited plan"
                )
            records[delivery_date] = _envelope_for_solved_day(
                manifest,
                solved,
                predecessor_date=predecessor_date,
                continuity_segment_id=active_segment,
            )
            segment_members[active_segment].append(delivery_date)
            trace = traces.get(delivery_date)
            if trace is None:
                pending_solved = None
                pending_replay = None
                blocked = True
                continue
            replay = _evaluate_midnight_day(manifest, solved, trace)
            is_last = index == len(manifest.dates) - 1
            if is_last:
                envelope = records[delivery_date]
                records[delivery_date] = _append_revision(
                    envelope,
                    _finalized_midnight_revision(
                        solved,
                        replay,
                        revision_number=len(envelope.revisions),
                        predecessor_revision_fingerprint=(
                            envelope.latest_revision.revision_fingerprint
                        ),
                        state_link_fingerprint=None,
                    ),
                )
                pending_solved = None
                pending_replay = None
            else:
                pending_solved = solved
                pending_replay = replay
            blocked = False
        except Exception as exc:
            records[delivery_date] = _failure_envelope(
                manifest,
                classification,
                predecessor_date=predecessor_date,
                lifecycle_status="failed",
                reason=_normalized_date_failure("midnight_carry", exc),
                continuity_segment_id=active_segment,
            )
            blocked = True
            pending_solved = None
            pending_replay = None

    if pending_solved is not None and pending_replay is not None:
        delivery_date = pending_solved.day_input.date_classification.delivery_date
        envelope = records[delivery_date]
        records[delivery_date] = _append_revision(
            envelope,
            _finalized_midnight_revision(
                pending_solved,
                pending_replay,
                revision_number=len(envelope.revisions),
                predecessor_revision_fingerprint=(
                    envelope.latest_revision.revision_fingerprint
                ),
                state_link_fingerprint=None,
            ),
        )
    ordered_records = tuple(records[item.delivery_date] for item in manifest.dates)
    record_dates_by_segment: dict[str, list[date]] = {}
    for record in ordered_records:
        record_dates_by_segment.setdefault(record.continuity_segment_id, []).append(
            record.classification.delivery_date
        )
    continuity_segments = tuple(
        ContinuitySegment(
            segment_id=segment_id,
            start_date=members[0],
            end_date=members[-1],
            start_reason=segment_reasons[segment_id][0],
            source_state_fingerprint=segment_reasons[segment_id][1],
        )
        for segment_id, members in record_dates_by_segment.items()
    )
    statuses = tuple(item.latest_revision.lifecycle_status for item in ordered_records)
    completeness = (
        "failed"
        if any(item == "failed" for item in statuses)
        else "partial"
        if any(
            item in {"blocked_by_predecessor", "optimization_only"}
            for item in statuses
        )
        else "complete"
    )
    return RollingFCRStudyResult(
        study_id=manifest.study_id,
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_id=manifest.profile.profile_id,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        records=ordered_records,
        continuity_segments=continuity_segments,
        state_links=tuple(state_links),
        aggregate_metrics=aggregate_rolling_fcr_records(
            manifest, ordered_records
        ),
        completeness_status=completeness,
        requested_day_input_fingerprints=_requested_day_input_fingerprints(
            day_inputs
        ),
        supplied_activation_fingerprints=_supplied_activation_fingerprints(
            activation_traces
        ),
        runtime_metadata={
            "phase": "realized-midnight-carry-v1",
            "state_carry_policy": manifest.numeric_policy.state_carry_policy,
            "bidder_received_activation": False,
        },
    )


def _run_independent_study(
    manifest: RollingFCRStudyManifest,
    day_inputs: tuple[RollingFCRDayInput, ...],
    *,
    activation_traces: Mapping[date, object] | None,
) -> RollingFCRStudyResult:
    """Solve reset days independently and optionally replay accepted plans."""

    if not manifest.profile.is_independent:
        raise RollingFCRValidationError(
            "independent study orchestration requires an independent profile"
        )
    by_date = {item.date_classification.delivery_date: item for item in day_inputs}
    if len(by_date) != len(day_inputs):
        raise RollingFCRValidationError("day_inputs must identify unique dates")
    manifest_dates = {item.delivery_date for item in manifest.dates}
    if any(delivery_date not in manifest_dates for delivery_date in by_date):
        raise RollingFCRValidationError("day input date is outside the manifest")
    traces = {} if activation_traces is None else activation_traces
    if not isinstance(traces, Mapping):
        raise RollingFCRValidationError("activation_traces must be a date mapping")
    supplied_activation_fingerprints = _supplied_activation_fingerprints(traces)

    records: list[DeliveryDateRecordEnvelope] = []
    for index, classification in enumerate(manifest.dates):
        delivery_date = classification.delivery_date
        if classification.execution_role == "excluded":
            records.append(
                _failure_envelope(
                    manifest,
                    classification,
                    predecessor_date=None,
                    lifecycle_status="excluded",
                    reason="date_excluded_by_manifest",
                )
            )
            continue
        day_input = by_date.get(delivery_date)
        if day_input is None:
            records.append(
                _failure_envelope(
                    manifest,
                    classification,
                    predecessor_date=None,
                    lifecycle_status="failed",
                    reason="required_day_input_unavailable",
                )
            )
            continue
        try:
            problem, result, plan, plan_classification = _solve_day(
                manifest,
                day_input,
                first_executed=index == 0,
            )
            solved = _solved_day_from_result(
                day_input,
                problem,
                result,
                plan,
                plan_classification,
            )
            if plan is None or result.solver.solve_status not in {
                "optimal",
                "feasible",
            }:
                failed = replace(
                    solved.original_revision,
                    lifecycle_status="failed",
                    creation_cause="optimization_produced_no_replayable_plan",
                    diagnostics=(
                        *solved.original_revision.diagnostics,
                        "accepted_plan_unavailable",
                    ),
                )
                solved = replace(solved, original_revision=failed)
                records.append(
                    _envelope_for_solved_day(
                        manifest,
                        solved,
                        predecessor_date=None,
                    )
                )
                continue

            envelope = _envelope_for_solved_day(
                manifest,
                solved,
                predecessor_date=None,
            )
            trace = traces.get(delivery_date)
            if trace is None:
                records.append(envelope)
                continue
            try:
                report = _evaluate_full_day(
                    manifest,
                    solved,
                    activation_trace=trace,
                    evaluation_suffix="independent-full-day-v1",
                )
            except Exception as exc:
                failed = replace(
                    solved.original_revision,
                    lifecycle_status="failed",
                    creation_cause="same_day_feature_012_replay_failed",
                    diagnostics=(
                        *solved.original_revision.diagnostics,
                        _normalized_date_failure("feature_012_replay", exc),
                    ),
                )
                solved = replace(solved, original_revision=failed)
                records.append(
                    _envelope_for_solved_day(
                        manifest,
                        solved,
                        predecessor_date=None,
                    )
                )
                continue
            records.append(
                _append_revision(
                    envelope,
                    _finalized_independent_revision(
                        solved,
                        report,
                        activation_fingerprint=trace.artifact_fingerprint,
                    ),
                )
            )
        except Exception as exc:
            records.append(
                _failure_envelope(
                    manifest,
                    classification,
                    predecessor_date=None,
                    lifecycle_status="failed",
                    reason=_normalized_date_failure("optimization", exc),
                )
            )

    dates = tuple(item.delivery_date for item in manifest.dates)
    segment = ContinuitySegment(
        segment_id=f"{manifest.study_id}-segment-0",
        start_date=dates[0],
        end_date=dates[-1],
        start_reason="manifest_start",
    )
    statuses = tuple(item.latest_revision.lifecycle_status for item in records)
    completeness = (
        "failed"
        if any(item == "failed" for item in statuses)
        else "partial"
        if any(item == "optimization_only" for item in statuses)
        else "complete"
    )
    ordered_records = tuple(records)
    return RollingFCRStudyResult(
        study_id=manifest.study_id,
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_id=manifest.profile.profile_id,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        records=ordered_records,
        continuity_segments=(segment,),
        state_links=(),
        aggregate_metrics=aggregate_rolling_fcr_records(
            manifest, ordered_records
        ),
        completeness_status=completeness,
        requested_day_input_fingerprints=_requested_day_input_fingerprints(
            day_inputs
        ),
        supplied_activation_fingerprints=supplied_activation_fingerprints,
        runtime_metadata={
            "phase": "independent-feature-012-replay-v1",
            "bidder_received_activation": False,
            "state_semantics": "reset_after_each_delivery_day",
        },
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
        resume_evidence = assess_rolling_fcr_resume(manifest, resume_from)
        if resume_evidence.status != "compatible":
            raise RollingFCRValidationError(
                "resume evidence is incompatible: "
                + ",".join(resume_evidence.diagnostics)
            )
        current_input_fingerprints = _requested_day_input_fingerprints(day_inputs)
        expected_input_fingerprints = dict(
            resume_from.requested_day_input_fingerprints
        )
        if any(
            current_input_fingerprints.get(key) != value
            for key, value in expected_input_fingerprints.items()
        ):
            raise RollingFCRValidationError(
                "resume day input fingerprints changed"
            )
        current_activation_fingerprints = _supplied_activation_fingerprints(
            activation_traces
        )
        expected_activation_fingerprints = dict(
            resume_from.supplied_activation_fingerprints
        )
        if any(
            current_activation_fingerprints.get(key) != value
            for key, value in expected_activation_fingerprints.items()
        ):
            raise RollingFCRValidationError(
                "resume activation fingerprints changed"
            )
        is_complete_record_set = len(resume_from.records) == len(manifest.dates)
        if is_complete_record_set:
            if current_input_fingerprints != expected_input_fingerprints:
                raise RollingFCRValidationError(
                    "resume complete day input set changed"
                )
            if current_activation_fingerprints != expected_activation_fingerprints:
                raise RollingFCRValidationError(
                    "resume complete activation set changed"
                )
            return replace(resume_from, resume_lineage=resume_evidence)
        fresh = run_initial_rolling_fcr_study(
            manifest,
            day_inputs,
            activation_traces=activation_traces,
            resume_from=None,
        )
        if len(resume_from.records) > len(fresh.records):
            raise RollingFCRValidationError(
                "resume contains more dates than the requested study"
            )
        fresh_prefix = fresh.records[: len(resume_from.records)]
        if tuple(item.envelope_fingerprint for item in fresh_prefix) != tuple(
            item.envelope_fingerprint for item in resume_from.records
        ):
            raise RollingFCRValidationError(
                "resume day input, activation, revision, or carried-state evidence changed"
            )
        merged_records = (
            resume_from.records
            if len(resume_from.records) == len(fresh.records)
            else (*resume_from.records, *fresh.records[len(resume_from.records) :])
        )
        return replace(
            fresh,
            records=merged_records,
            aggregate_metrics=aggregate_rolling_fcr_records(
                manifest, merged_records
            ),
            resume_lineage=resume_evidence,
        )
    if manifest.profile.state_mode == "rolling_0800":
        return _run_causal_0800_study(
            manifest,
            day_inputs,
            activation_traces=activation_traces,
        )
    if manifest.profile.state_mode == "midnight_carry":
        return _run_midnight_carry_study(
            manifest,
            day_inputs,
            activation_traces=activation_traces,
        )
    return _run_independent_study(
        manifest,
        day_inputs,
        activation_traces=activation_traces,
    )


__all__ = ["run_initial_rolling_fcr_study"]
