"""Causal Feature 012 replay and immutable 08:00 finalization coverage."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from open_energy_lab.control import run_rolling_fcr_study
from open_energy_lab.control._fcr_rolling_orchestrator import (
    _SolvedRollingDay,
    _derive_causal_0800_checkpoint,
    _prefix_trace_for_solved_day,
)
from open_energy_lab.simulator import FCRBidEvaluationValidationError
from tests.fcr_rolling_case_utils import (
    AUTHORED_DELIVERY_DATES,
    build_authored_activation_trace,
    build_authored_day_input,
    build_authored_fixed_plan,
    build_authored_manifest,
    build_authored_zero_prices,
)


def _bounded_manifest(date_count: int):
    source = build_authored_manifest(
        "script-14-restriction-rolling-0800-v1"
    )
    dates = list(source.dates[:date_count])
    dates[-1] = replace(
        dates[-1],
        execution_role="close-out",
        comparison_eligible=False,
        reason_codes=("closes_predecessor",),
    )
    return replace(source, dates=tuple(dates))


def _zero_input(manifest, delivery_date):
    source = build_authored_day_input(manifest, delivery_date)
    prices = build_authored_zero_prices(delivery_date)
    return replace(
        source,
        prices=prices,
        producer_input_fingerprints={
            **dict(source.producer_input_fingerprints),
            "market_prices": prices.price_input_fingerprint,
        },
    )


def _manual_solved(manifest, *, fcr_capacity_kw=(0.0,) * 6):
    delivery_date = manifest.dates[0].delivery_date
    plan = build_authored_fixed_plan(
        delivery_date,
        fcr_capacity_kw=fcr_capacity_kw,
    )
    return _SolvedRollingDay(
        day_input=build_authored_day_input(manifest, delivery_date),
        problem=SimpleNamespace(problem_fingerprint="1" * 64),
        result=SimpleNamespace(),
        plan=plan,
        plan_classification="robust_candidate",
        original_revision=None,
    )


def test_two_traces_equal_through_0800_produce_identical_successor_bids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import open_energy_lab.control._fcr_rolling_orchestrator as orchestrator
    import open_energy_lab.control.robust_fcr_rolling as rolling_solver

    events: list[str] = []
    delegated_solve = rolling_solver.solve_robust_fcr_rolling_bid
    delegated_tail = orchestrator._tail_trace_for_solved_day
    delegated_bootstrap = orchestrator._solve_day
    cached_bootstrap = []

    def recording_solve(problem):
        events.append("successor_solve")
        return delegated_solve(problem)

    def guarded_tail(*args, **kwargs):
        if not events or events[-1] != "successor_solve":
            raise AssertionError("post-cutoff tail was accessed before bid selection")
        events.append("post_solve_tail_replay")
        return delegated_tail(*args, **kwargs)

    def cached_bootstrap_solve(*args, **kwargs):
        if kwargs.get("first_executed") and cached_bootstrap:
            return cached_bootstrap[0]
        result = delegated_bootstrap(*args, **kwargs)
        if kwargs.get("first_executed"):
            cached_bootstrap.append(result)
        return result

    monkeypatch.setattr(
        rolling_solver,
        "solve_robust_fcr_rolling_bid",
        recording_solve,
    )
    monkeypatch.setattr(
        orchestrator,
        "_tail_trace_for_solved_day",
        guarded_tail,
    )
    monkeypatch.setattr(
        orchestrator,
        "_solve_day",
        cached_bootstrap_solve,
    )
    manifest = _bounded_manifest(2)
    inputs = tuple(
        _zero_input(manifest, item.delivery_date) for item in manifest.dates
    )
    sample_count = 96
    prefix = (0.0,) * 32
    first_trace = build_authored_activation_trace(
        manifest.dates[0].delivery_date,
        values=prefix + (0.75,) * (sample_count - len(prefix)),
    )
    second_trace = build_authored_activation_trace(
        manifest.dates[0].delivery_date,
        values=prefix + (-0.75,) * (sample_count - len(prefix)),
    )

    first = run_rolling_fcr_study(
        manifest,
        inputs,
        activation_traces={manifest.dates[0].delivery_date: first_trace},
    )
    second = run_rolling_fcr_study(
        manifest,
        inputs,
        activation_traces={manifest.dates[0].delivery_date: second_trace},
    )

    first_successor = first.records[1].revisions[0]
    second_successor = second.records[1].revisions[0]
    assert first.state_links[0].state_link_fingerprint == (
        second.state_links[0].state_link_fingerprint
    )
    assert first.state_links[0].replay_checkpoint_kwh == (
        second.state_links[0].replay_checkpoint_kwh
    )
    assert first.state_links[0].accepted_fixings_fingerprint == (
        second.state_links[0].accepted_fixings_fingerprint
    )
    assert first_successor.input_fingerprint == second_successor.input_fingerprint
    assert first_successor.problem_fingerprint == second_successor.problem_fingerprint
    assert first_successor.energy_decisions_charge_positive_kw == (
        second_successor.energy_decisions_charge_positive_kw
    )
    assert first_successor.fcr_capacity_kw == second_successor.fcr_capacity_kw
    assert first_successor.plan_fingerprint == second_successor.plan_fingerprint
    assert first.records[0].latest_revision.activation_fingerprint != (
        second.records[0].latest_revision.activation_fingerprint
    )
    assert events == [
        "successor_solve",
        "post_solve_tail_replay",
        "successor_solve",
        "post_solve_tail_replay",
    ]


def test_prefix_replay_requires_exact_half_open_coverage_and_excludes_boundary() -> None:
    manifest = _bounded_manifest(2)
    solved = _manual_solved(manifest)
    full = build_authored_activation_trace(manifest.dates[0].delivery_date)
    prefix = _prefix_trace_for_solved_day(solved, full)
    cutoff = solved.plan.energy_schedule.covered_period.start_utc + timedelta(hours=8)

    assert prefix.covered_period.end_utc == cutoff
    assert prefix.samples[-1].interval.end_utc == cutoff
    assert all(item.interval.start_utc < cutoff for item in prefix.samples)
    with pytest.raises(
        (FCRBidEvaluationValidationError, ValueError),
        match="pre-sliced|exact",
    ):
        _derive_causal_0800_checkpoint(
            manifest,
            solved,
            prefix_activation_trace=full,
            initial_stored_energy_kwh=10.0,
        )


def test_prefix_checkpoint_uses_feature_012_saturation_and_rejects_invalid_initial() -> None:
    manifest = _bounded_manifest(2)
    solved = _manual_solved(manifest, fcr_capacity_kw=(10.0,) * 6)
    full = build_authored_activation_trace(
        manifest.dates[0].delivery_date,
        values=(1.0,) * 96,
    )
    prefix = _prefix_trace_for_solved_day(solved, full)
    evidence = _derive_causal_0800_checkpoint(
        manifest,
        solved,
        prefix_activation_trace=prefix,
        initial_stored_energy_kwh=10.0,
    )

    assert evidence.report.additive_metrics["saturation_sample_count"] > 0
    assert evidence.replay_checkpoint_kwh == pytest.approx(0.0)
    assert evidence.handed_off_checkpoint_kwh == 0.0
    with pytest.raises(FCRBidEvaluationValidationError, match="outside"):
        _derive_causal_0800_checkpoint(
            manifest,
            solved,
            prefix_activation_trace=prefix,
            initial_stored_energy_kwh=21.0,
        )


def test_missing_prefix_retains_optimization_and_blocks_successor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import open_energy_lab.control._fcr_rolling_orchestrator as orchestrator

    manifest = _bounded_manifest(2)
    inputs = tuple(
        _zero_input(manifest, item.delivery_date) for item in manifest.dates
    )
    bootstrap_input = inputs[0]
    plan = build_authored_fixed_plan(bootstrap_input.date_classification.delivery_date)
    fake_problem = SimpleNamespace(problem_fingerprint="4" * 64)
    fake_solver = SimpleNamespace(
        solve_status="optimal",
        termination_status="optimal",
        objective_value_eur=0.0,
        best_upper_bound_eur=0.0,
        absolute_gap_eur=0.0,
        relative_gap=0.0,
    )
    fake_decisions = SimpleNamespace(
        energy_baseline_charge_positive_kw=(0.0,) * 24,
        fcr_capacity_kw=(0.0,) * 6,
    )
    fake_audit = SimpleNamespace(
        audit_fingerprint="5" * 64,
        modeled_slacks={},
    )
    fake_result = SimpleNamespace(
        solver=fake_solver,
        decisions=fake_decisions,
        semantic_result_fingerprint="6" * 64,
        feasibility_audit=fake_audit,
        runtime_metadata={},
        diagnostics=(),
    )

    def fake_bootstrap(*args, **kwargs):
        assert kwargs["first_executed"] is True
        return fake_problem, fake_result, plan, "robust_candidate"

    monkeypatch.setattr(orchestrator, "_solve_day", fake_bootstrap)

    result = run_rolling_fcr_study(manifest, inputs, activation_traces={})

    assert result.records[0].latest_revision.lifecycle_status == "optimization_only"
    assert result.records[1].latest_revision.lifecycle_status == (
        "blocked_by_predecessor"
    )
    assert result.state_links == ()


def test_four_date_chain_retains_original_provisional_finalized_and_edges() -> None:
    manifest = _bounded_manifest(4)
    inputs = tuple(
        _zero_input(manifest, item.delivery_date) for item in manifest.dates
    )
    traces = {
        item.delivery_date: build_authored_activation_trace(item.delivery_date)
        for item in manifest.dates
    }

    result = run_rolling_fcr_study(
        manifest,
        inputs,
        activation_traces=traces,
    )

    assert tuple(item.classification.delivery_date for item in result.records) == (
        AUTHORED_DELIVERY_DATES
    )
    assert tuple(item.latest_revision.lifecycle_status for item in result.records) == (
        "initialization_only",
        "finalized",
        "finalized",
        "unfinalized",
    )
    assert tuple(
        tuple(revision.revision_kind for revision in item.revisions)
        for item in result.records
    ) == (
        ("original", "provisional", "finalized"),
        ("original", "provisional", "finalized"),
        ("original", "provisional", "finalized"),
        ("original", "provisional"),
    )
    assert len(result.state_links) == 3
    assert all(item.reconciles for item in result.state_links)
    assert result.records[0].revisions[0].plan_fingerprint == (
        result.records[0].revisions[-1].plan_fingerprint
    )
    assert result.records[-1].classification.comparison_eligible is False
    assert result.records[-1].latest_revision.replay_fingerprint is not None
    assert result.finalized_parity_eligible_dates == AUTHORED_DELIVERY_DATES[1:3]
    assert result.finalized_parity_exclusions["2023-06-17"] == (
        "execution_role:warm-up",
        "initialization_only",
        "lifecycle_status:initialization_only",
    )
    assert "lifecycle_status:unfinalized" in (
        result.finalized_parity_exclusions["2023-06-20"]
    )
    assert result.completeness_status == "partial"


def test_three_day_midnight_chains_separate_source_rounding_and_native_precision() -> None:
    source_manifest_full = build_authored_manifest(
        "script-13-arbitrage-only-midnight-v1",
        state_carry_policy="source_three_decimal",
    )
    native_manifest_full = build_authored_manifest(
        "script-15-restriction-rolling-midnight-v1",
        state_carry_policy="native_full_precision",
    )
    source_manifest = replace(
        source_manifest_full,
        dates=source_manifest_full.dates[:3],
    )
    native_manifest = replace(
        native_manifest_full,
        dates=native_manifest_full.dates[:3],
    )

    def run(manifest):
        inputs = tuple(
            _zero_input(manifest, item.delivery_date) for item in manifest.dates
        )
        traces = {
            item.delivery_date: build_authored_activation_trace(item.delivery_date)
            for item in manifest.dates
        }
        return run_rolling_fcr_study(
            manifest,
            inputs,
            activation_traces=traces,
        )

    source = run(source_manifest)
    native = run(native_manifest)

    assert source.completeness_status == native.completeness_status == "complete"
    assert tuple(item.latest_revision.lifecycle_status for item in source.records) == (
        "finalized",
        "finalized",
        "finalized",
    )
    assert len(source.state_links) == len(native.state_links) == 2
    assert {item.rounding_policy for item in source.state_links} == {
        "source_three_decimal"
    }
    assert {item.rounding_policy for item in native.state_links} == {
        "native_full_precision"
    }
    assert all(
        item.successor_initial_stored_energy_kwh
        == item.carried_stored_energy_kwh
        for item in (*source.state_links, *native.state_links)
    )
    assert all(
        item.source_interval_kwh
        == (item.replay_checkpoint_kwh, item.replay_checkpoint_kwh)
        for item in native.state_links
    )
    assert all(
        revision.latest_revision.realized_terminal_stored_energy_kwh is not None
        and revision.latest_revision.modeled_terminal_stored_energy_kwh is None
        for revision in (*source.records, *native.records)
    )
    assert tuple(item.revisions[0].problem_fingerprint for item in source.records) != (
        tuple(item.revisions[0].problem_fingerprint for item in native.records)
    )
    assert tuple(item.revisions[0].plan_fingerprint for item in source.records) != (
        tuple(item.revisions[0].plan_fingerprint for item in native.records)
    )
    assert tuple(item.state_link_fingerprint for item in source.state_links) != (
        tuple(item.state_link_fingerprint for item in native.state_links)
    )
    assert source.semantic_fingerprint != native.semantic_fingerprint
