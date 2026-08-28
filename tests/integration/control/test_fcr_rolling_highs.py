"""Deterministic bounded HiGHS coverage for the five executable profiles."""

from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.control import (
    RobustFCRBatteryParameters,
    TerminalStoredEnergyRule,
    run_rolling_fcr_study,
    solve_robust_fcr_rolling_bid,
)
from open_energy_lab.control.robust_fcr_rolling import (
    _rolling_incumbent_is_accepted,
)
from tests.fcr_rolling_case_utils import (
    AUTHORED_DELIVERY_DATES,
    build_authored_activation_trace,
    build_authored_day_input,
    build_authored_manifest,
    build_authored_rolling_problem,
    build_authored_zero_prices,
)


def _single_date_manifest(profile_id: str):
    original = build_authored_manifest(profile_id)
    return replace(original, dates=(original.dates[1],))


def _zero_price_day_input(manifest, delivery_date):
    original = build_authored_day_input(manifest, delivery_date)
    prices = build_authored_zero_prices(delivery_date)
    return replace(
        original,
        prices=prices,
        producer_input_fingerprints={
            **original.producer_input_fingerprints,
            "market_prices": prices.price_input_fingerprint,
        },
    )


@pytest.mark.parametrize(
    ("profile_id", "classification"),
    (
        ("script-11-relaxation-reset-midnight-v1", "diagnostic_non_robust"),
        ("script-12-restriction-reset-midnight-v1", "robust_candidate"),
        ("script-13-arbitrage-only-midnight-v1", "arbitrage_only"),
        ("script-15-restriction-rolling-midnight-v1", "robust_candidate"),
    ),
)
def test_bounded_profile_solves_return_ordered_classified_evidence(
    profile_id: str,
    classification: str,
) -> None:
    manifest = _single_date_manifest(profile_id)
    day_input = _zero_price_day_input(manifest, AUTHORED_DELIVERY_DATES[1])

    result = run_rolling_fcr_study(manifest, (day_input,))
    revision = result.records[0].latest_revision

    assert result.completeness_status == "complete"
    assert len(result.records) == 1
    assert revision.solve_status == "optimal"
    assert revision.plan_classification == classification
    assert revision.energy_decisions_charge_positive_kw is not None
    assert len(revision.energy_decisions_charge_positive_kw) == 24
    assert revision.fcr_capacity_kw is not None
    assert len(revision.fcr_capacity_kw) == 6
    assert revision.plan_fingerprint is not None
    if classification == "diagnostic_non_robust":
        assert "relaxation" in revision.plan_fingerprint or len(
            revision.plan_fingerprint
        ) == 64
    if classification == "arbitrage_only":
        assert revision.fcr_capacity_kw == (0.0,) * 6


def test_0800_fixed_overlap_solves_with_40_160_10_frame_and_retains_edges() -> None:
    original = build_authored_manifest(
        "script-14-restriction-rolling-0800-v1"
    )
    manifest = replace(original, dates=(original.dates[0], replace(
        original.dates[1],
        execution_role="close-out",
        comparison_eligible=False,
        reason_codes=("closes_predecessor",),
    )))
    warmup = _zero_price_day_input(manifest, AUTHORED_DELIVERY_DATES[0])
    successor = _zero_price_day_input(manifest, AUTHORED_DELIVERY_DATES[1])
    trace = build_authored_activation_trace(AUTHORED_DELIVERY_DATES[0])

    result = run_rolling_fcr_study(
        manifest,
        (warmup, successor),
        activation_traces={AUTHORED_DELIVERY_DATES[0]: trace},
    )
    warmup_revision = result.records[0].latest_revision
    closeout_revision = result.records[1].latest_revision

    assert result.completeness_status == "partial"
    assert warmup_revision.solve_status == "optimal"
    assert warmup_revision.lifecycle_status == "initialization_only"
    assert closeout_revision.solve_status == "optimal"
    assert closeout_revision.lifecycle_status == "unfinalized"
    assert closeout_revision.plan_classification == "robust_candidate"
    assert closeout_revision.plan_fingerprint is not None
    assert closeout_revision.feasibility_audit_fingerprint is not None
    assert max(closeout_revision.feasibility_slacks.values(), default=0.0) <= 1e-6
    assert tuple(item.revision_kind for item in result.records[0].revisions) == (
        "original",
        "provisional",
        "finalized",
    )
    assert len(result.state_links) == 1


def test_exact_zero_fcr_is_a_model_constraint_not_a_zero_price_inference() -> None:
    problem = build_authored_rolling_problem(
        "script-13-arbitrage-only-midnight-v1"
    )
    result = solve_robust_fcr_rolling_bid(problem)

    assert result.solver.solve_status == "optimal"
    assert result.decisions is not None
    assert result.decisions.fcr_capacity_kw == (0.0,) * 6
    assert result.solver.model_cardinality["fixed_zero_fcr_decisions"] == 6
    assert result.plan_classification == "arbitrage_only"
    assert result.plan is not None
    assert result.feasibility_audit is not None
    assert result.feasibility_audit.passes_deployability_audit is True


def test_arbitrage_only_infeasibility_is_retained_without_plan_or_decisions() -> None:
    base = build_authored_rolling_problem(
        "script-13-arbitrage-only-midnight-v1"
    )
    battery = RobustFCRBatteryParameters(
        maximum_charge_power_kw=0.001,
        maximum_discharge_power_kw=0.001,
        minimum_stored_energy_kwh=0.0,
        maximum_stored_energy_kwh=1.0,
        initial_stored_energy_kwh=0.0,
        charge_efficiency=1.0,
        discharge_efficiency=1.0,
    )
    terminal = TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=1.0,
        allow_penalized_shortfall=False,
        shortfall_penalty_eur_per_kwh=100.0,
        rule_id="feature-015-infeasible-terminal-v1",
    )
    problem = replace(base, battery=battery, terminal_rule=terminal)

    result = solve_robust_fcr_rolling_bid(problem)

    assert result.solver.solve_status == "infeasible"
    assert result.solver.has_incumbent is False
    assert result.decisions is None
    assert result.plan is None


def test_repeated_exact_zero_fcr_solves_have_identical_semantic_evidence() -> None:
    base = build_authored_rolling_problem(
        "script-13-arbitrage-only-midnight-v1"
    )
    zero = build_authored_zero_prices(AUTHORED_DELIVERY_DATES[1])
    problem = replace(base, current_prices=zero)

    first = solve_robust_fcr_rolling_bid(problem)
    second = solve_robust_fcr_rolling_bid(problem)

    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.decisions == second.decisions
    assert first.plan is not None and second.plan is not None
    assert first.plan.plan_fingerprint == second.plan.plan_fingerprint
    assert first.runtime_metadata != {}


def test_midnight_coupled_problem_identity_changes_with_explicit_initial_state() -> None:
    source = build_authored_rolling_problem(
        "script-13-arbitrage-only-midnight-v1",
        initial_stored_energy_kwh=10.0,
    )
    carried = build_authored_rolling_problem(
        "script-13-arbitrage-only-midnight-v1",
        initial_stored_energy_kwh=10.125,
    )

    assert source.rolling_problem_fingerprint != carried.rolling_problem_fingerprint
    assert source.battery.initial_stored_energy_kwh == 10.0
    assert carried.battery.initial_stored_energy_kwh == 10.125


def test_feasible_incumbent_requires_the_fingerprinted_pre_solve_opt_in() -> None:
    blocked = build_authored_rolling_problem(
        "script-13-arbitrage-only-midnight-v1"
    ).solve_policy
    enabled = replace(blocked, allow_feasible_incumbent_plan=True)

    assert _rolling_incumbent_is_accepted(
        solve_status="feasible",
        has_incumbent=True,
        solve_policy=blocked,
    ) is False
    assert _rolling_incumbent_is_accepted(
        solve_status="feasible",
        has_incumbent=True,
        solve_policy=enabled,
    ) is True
    assert blocked.solve_policy_fingerprint != enabled.solve_policy_fingerprint
    assert _rolling_incumbent_is_accepted(
        solve_status="optimal",
        has_incumbent=True,
        solve_policy=blocked,
    ) is True
