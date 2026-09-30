"""Explicitly selected optional exact-bilinear Gurobi evidence."""

from __future__ import annotations

from dataclasses import replace
import importlib.util

import pytest

from open_energy_lab.control.robust_fcr_bidding import (
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    TerminalStoredEnergyRule,
    compare_robust_fcr_bounds,
    solve_robust_fcr_bid,
)
from tests.robust_fcr_case_utils import build_authored_problem


pytestmark = pytest.mark.licensed_gurobi


def _skip_after_unavailable(result) -> None:
    assert result.solver.solve_status == "unavailable"
    assert result.solver.has_incumbent is False
    assert result.deployable_plan is None
    messages = " ".join(value.message for value in result.diagnostics)
    assert "Gurobi" in messages or "gurobi" in messages
    pytest.skip(messages)


def _presolve_zero_problem():
    base = build_authored_problem(time_limit_seconds=30.0)
    return replace(
        base,
        problem_id="feature-013-gurobi-presolve-zero",
        battery=RobustFCRBatteryParameters(
            maximum_charge_power_kw=10.0,
            maximum_discharge_power_kw=10.0,
            minimum_stored_energy_kwh=0.0,
            maximum_stored_energy_kwh=20.0,
            initial_stored_energy_kwh=0.0,
            charge_efficiency=0.92,
            discharge_efficiency=0.92,
        ),
        prices=RobustFCRPriceInputs(
            day_ahead_energy_prices_eur_per_kwh=(1.0,) * 24,
            fcr_capacity_prices_eur_per_kw_block=(-1.0,) * 6,
            energy_interval_refs=base.prices.energy_interval_refs,
            fcr_interval_refs=base.prices.fcr_interval_refs,
        ),
        terminal_rule=TerminalStoredEnergyRule(
            minimum_terminal_stored_energy_kwh=0.0,
            allow_penalized_shortfall=False,
            shortfall_penalty_eur_per_kwh=100.0,
            rule_id="gurobi-presolve-zero-terminal-v1",
        ),
    )


def test_exact_requires_explicit_gurobi_and_never_falls_back_to_highs() -> None:
    highs_problem = build_authored_problem(time_limit_seconds=30.0)
    result = solve_robust_fcr_bid(highs_problem, formulation="exact")
    assert result.solver.solve_status == "unavailable"
    assert result.solver.solver_name == "gurobi"
    assert result.deployable_plan is None
    assert any(
        value.code == "exact_requires_explicit_gurobi"
        for value in result.diagnostics
    )


def test_optional_gurobi_solves_linear_restriction_and_relaxation() -> None:
    common = _presolve_zero_problem()
    gurobi_problem = replace(
        common,
        solve_policy=replace(common.solve_policy, solver_name="gurobi"),
    )

    restriction = solve_robust_fcr_bid(
        gurobi_problem,
        formulation="restriction",
    )
    if restriction.solver.solve_status == "unavailable":
        _skip_after_unavailable(restriction)
    relaxation = solve_robust_fcr_bid(
        gurobi_problem,
        formulation="relaxation",
    )

    assert restriction.solver.solve_status == "optimal"
    assert relaxation.solver.solve_status == "optimal"
    assert restriction.solver.solver_name == "gurobi"
    assert relaxation.solver.solver_name == "gurobi"
    assert restriction.solver.highspy_version is None
    assert relaxation.solver.highspy_version is None
    assert restriction.deployable_plan is not None
    assert relaxation.deployable_plan is None
    comparison = compare_robust_fcr_bounds(restriction, relaxation)
    assert comparison.restriction_le_relaxation.satisfied is True


def test_optional_exact_bilinear_obeys_three_way_bound_order() -> None:
    common = _presolve_zero_problem()
    gurobi_policy = replace(common.solve_policy, solver_name="gurobi")
    exact_problem = replace(common, solve_policy=gurobi_policy)
    exact = solve_robust_fcr_bid(exact_problem, formulation="exact")

    if importlib.util.find_spec("gurobipy") is None or exact.solver.solve_status == "unavailable":
        _skip_after_unavailable(exact)

    restriction = solve_robust_fcr_bid(common, formulation="restriction")
    relaxation = solve_robust_fcr_bid(common, formulation="relaxation")
    assert exact.solver.solve_status in {"optimal", "feasible"}
    assert exact.solver.solver_name == "gurobi"
    assert exact.deployable_plan is None
    comparison = compare_robust_fcr_bounds(
        restriction,
        relaxation,
        exact=exact,
    )
    assert comparison.restriction_le_relaxation.satisfied is True
    assert comparison.restriction_le_exact.satisfied is True
    assert comparison.exact_le_relaxation.satisfied is True
    assert comparison.overall_status == "satisfied"
