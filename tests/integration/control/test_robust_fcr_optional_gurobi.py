"""Explicitly selected optional exact-bilinear Gurobi evidence."""

from __future__ import annotations

from dataclasses import replace
import importlib.util

import pytest

from open_energy_lab.control.robust_fcr_bidding import (
    compare_robust_fcr_bounds,
    solve_robust_fcr_bid,
)
from tests.robust_fcr_case_utils import build_authored_problem


def _skip_after_unavailable(result) -> None:
    assert result.solver.solve_status == "unavailable"
    assert result.solver.has_incumbent is False
    assert result.deployable_plan is None
    assert result.formulation.deployability_role == "exact_evidence_only"
    messages = " ".join(value.message for value in result.diagnostics)
    assert "Gurobi" in messages or "gurobi" in messages
    pytest.skip(messages)


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


def test_optional_exact_bilinear_obeys_three_way_bound_order() -> None:
    common = build_authored_problem(time_limit_seconds=30.0)
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
