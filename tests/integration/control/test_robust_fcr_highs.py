"""Real Pyomo/HiGHS integration checks for Feature 013."""

from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.control.robust_fcr_bidding import (
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    TerminalStoredEnergyRule,
    compare_robust_fcr_bounds,
    solve_robust_fcr_bid,
)
from tests.robust_fcr_case_utils import build_authored_problem


pytestmark = pytest.mark.slow


def _presolve_zero_problem(*, problem_id: str = "feature-013-presolve-zero"):
    base = build_authored_problem(time_limit_seconds=30.0)
    battery = RobustFCRBatteryParameters(
        maximum_charge_power_kw=10.0,
        maximum_discharge_power_kw=10.0,
        minimum_stored_energy_kwh=0.0,
        maximum_stored_energy_kwh=20.0,
        initial_stored_energy_kwh=0.0,
        charge_efficiency=0.92,
        discharge_efficiency=0.92,
    )
    prices = RobustFCRPriceInputs(
        day_ahead_energy_prices_eur_per_kwh=(1.0,) * 24,
        fcr_capacity_prices_eur_per_kw_block=(-1.0,) * 6,
        energy_interval_refs=base.prices.energy_interval_refs,
        fcr_interval_refs=base.prices.fcr_interval_refs,
    )
    terminal = TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=0.0,
        allow_penalized_shortfall=False,
        shortfall_penalty_eur_per_kwh=100.0,
        rule_id="presolve-zero-terminal-v1",
    )
    return replace(
        base,
        problem_id=problem_id,
        battery=battery,
        prices=prices,
        terminal_rule=terminal,
    )


def _terminal_shortfall_problem(*, allow_shortfall: bool):
    base = _presolve_zero_problem(
        problem_id=(
            "feature-013-terminal-slack"
            if allow_shortfall
            else "feature-013-infeasible-terminal"
        )
    )
    battery = RobustFCRBatteryParameters(
        maximum_charge_power_kw=0.1,
        maximum_discharge_power_kw=0.1,
        minimum_stored_energy_kwh=0.0,
        maximum_stored_energy_kwh=20.0,
        initial_stored_energy_kwh=0.0,
        charge_efficiency=0.92,
        discharge_efficiency=0.92,
    )
    terminal = TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=20.0,
        allow_penalized_shortfall=allow_shortfall,
        shortfall_penalty_eur_per_kwh=100.0,
        rule_id="shortfall-terminal-v1",
    )
    return replace(base, battery=battery, terminal_rule=terminal)


def test_real_highs_public_restriction_emits_presolve_simple_plan() -> None:
    result = solve_robust_fcr_bid(_presolve_zero_problem())

    assert result.formulation.kind == "restriction"
    assert result.solver.solve_status == "optimal"
    assert result.solver.solver_name == "highs"
    assert result.solver.pyomo_version == "6.10.1"
    assert result.solver.highspy_version == "1.15.1"
    assert result.solver.objective_value_eur == 0.0
    assert result.solver.best_upper_bound_eur == 0.0
    assert result.solver.absolute_gap_eur == 0.0
    assert result.solver.relative_gap == 0.0
    assert result.feasibility_audit.passes_deployability_audit is True
    assert result.deployable_plan is not None
    assert result.decisions.energy_baseline_charge_positive_kw == (0.0,) * 24
    assert result.decisions.fcr_capacity_kw == (0.0,) * 6


def test_real_highs_reports_infeasible_restriction_without_incumbent() -> None:
    result = solve_robust_fcr_bid(
        _terminal_shortfall_problem(allow_shortfall=False)
    )
    assert result.solver.solve_status == "infeasible"
    assert result.solver.has_incumbent is False
    assert result.decisions is None
    assert result.feasibility_audit is None
    assert result.deployable_plan is None


def test_real_highs_reports_terminal_slack_but_does_not_deploy() -> None:
    result = solve_robust_fcr_bid(
        _terminal_shortfall_problem(allow_shortfall=True)
    )
    assert result.solver.solve_status == "optimal"
    assert result.feasibility_audit.modeled_slacks["terminal_end_kwh"] > 1e-6
    assert result.feasibility_audit.passes_deployability_audit is False
    assert result.deployable_plan is None
    assert "feasibility_audit_failed" in result.deployability_reasons


def test_real_highs_repeated_semantic_evidence_is_exactly_identical() -> None:
    problem = _presolve_zero_problem(problem_id="feature-013-repeatability")
    first = solve_robust_fcr_bid(problem)
    second = solve_robust_fcr_bid(problem)

    assert first.solver.objective_value_eur == second.solver.objective_value_eur
    assert first.solver.best_upper_bound_eur == second.solver.best_upper_bound_eur
    assert first.solver.absolute_gap_eur == second.solver.absolute_gap_eur
    assert first.solver.relative_gap == second.solver.relative_gap
    assert first.decisions == second.decisions
    assert first.feasibility_audit == second.feasibility_audit
    assert first.diagnostics == second.diagnostics
    assert first.deployable_plan.plan_fingerprint == second.deployable_plan.plan_fingerprint
    assert first.semantic_result_fingerprint == second.semantic_result_fingerprint


def test_real_highs_restriction_and_relaxation_have_ordered_roles() -> None:
    problem = _presolve_zero_problem(problem_id="feature-013-bound-order")
    restriction = solve_robust_fcr_bid(problem, formulation="restriction")
    relaxation = solve_robust_fcr_bid(problem, formulation="relaxation")
    comparison = compare_robust_fcr_bounds(restriction, relaxation)

    assert restriction.formulation.deployability_role == "candidate_plan"
    assert restriction.deployable_plan is not None
    assert relaxation.formulation.deployability_role == "upper_bound_only"
    assert relaxation.deployability_status == "not_applicable"
    assert relaxation.deployable_plan is None
    assert restriction.problem_fingerprint == relaxation.problem_fingerprint
    assert comparison.restriction_le_relaxation.satisfied is True
    assert comparison.overall_status == "satisfied"


def test_real_highs_paired_results_repeat_exact_numeric_payloads() -> None:
    problem = _presolve_zero_problem(problem_id="feature-013-paired-repeatability")
    first = tuple(
        solve_robust_fcr_bid(problem, formulation=kind)
        for kind in ("restriction", "relaxation")
    )
    second = tuple(
        solve_robust_fcr_bid(problem, formulation=kind)
        for kind in ("restriction", "relaxation")
    )
    for left, right in zip(first, second, strict=True):
        assert left.solver.objective_value_eur == right.solver.objective_value_eur
        assert left.solver.best_upper_bound_eur == right.solver.best_upper_bound_eur
        assert left.solver.absolute_gap_eur == right.solver.absolute_gap_eur
        assert left.solver.relative_gap == right.solver.relative_gap
        assert left.semantic_result_fingerprint == right.semantic_result_fingerprint


def test_feature_015_refactor_guard_preserves_real_highs_golden_evidence() -> None:
    problem = _presolve_zero_problem(
        problem_id="feature-013-golden-regression-v1"
    )
    result = solve_robust_fcr_bid(problem)
    plan = result.deployable_plan

    assert result.solver.solve_status == "optimal"
    assert result.deployability_status == "eligible"
    assert plan is not None
    assert (
        problem.problem_fingerprint
        == "b251d095e552d904644d0757a2b77508615aa6e327fd7a584f4fabfc6000379e"
    )
    assert (
        result.semantic_result_fingerprint
        == "fcae3de50a4d901f3c878bebe82aef4f1116361a7abb4088a1e32a865a6a1491"
    )
    assert (
        plan.energy_schedule.schedule_fingerprint
        == "55e8ed6ae3f6eaf49ecdcd80d9688504a070c326d6c17a60c32fa1bcfcb67bba"
    )
    assert (
        plan.fcr_schedule.schedule_fingerprint
        == "e48a5eb3158743f84b1e24756f15c03f7ec1c7397a6c3d7448df2f0ab6707bc2"
    )
    assert (
        plan.plan_fingerprint
        == "7efedcd0e075ba9363cc8e3973f69f6e74fb5f6d241d4c370dab70af11420a42"
    )
