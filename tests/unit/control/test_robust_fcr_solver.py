"""Controlled solver-evidence and deployability tests for Feature 013."""

from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.control._robust_fcr_solver import RawRobustFCRSolveResult
from open_energy_lab.control.robust_fcr_bidding import (
    DEPLOYABILITY_THRESHOLD,
    RobustFCRFormulationProfile,
    _finalize_solve_result,
    _normalize_maximization_gap,
)
from tests.robust_fcr_case_utils import build_authored_problem


def _zero_witness(*, terminal_slack: float = 0.0) -> dict[str, object]:
    planning_count = 96
    return {
        "x0": (0.0,) * 24,
        "xr": (0.0,) * 6,
        "xa": (0.0,) * planning_count,
        "symin": (0.0,) * planning_count,
        "symax": (0.0,) * planning_count,
        "syK": (0.0, terminal_slack),
        "alpha": (0.0,) * planning_count,
        "beta": (0.0,) * planning_count,
        "lambda_l": (0.0,) * planning_count,
        "lambda_h": (0.0,) * planning_count,
        "Lambda_l": tuple((0.0,) * (outer + 1) for outer in range(planning_count)),
        "Lambda_h": tuple((0.0,) * (outer + 1) for outer in range(planning_count)),
        "u1": (0.0,) * (planning_count - 1),
        "u2": (0.0,) * (planning_count - 1),
        "v_res": (0.0,) * (planning_count - 1),
    }


def _raw_result(
    *,
    status: str = "optimal",
    termination: str = "optimal",
    witness: dict[str, object] | None = None,
    objective: float | None = 0.0,
    bound: float | None = 0.0,
    runtime_seconds: float = 0.1,
) -> RawRobustFCRSolveResult:
    return RawRobustFCRSolveResult(
        solve_status=status,
        termination_status=termination,
        has_incumbent=witness is not None,
        objective_value_eur=objective,
        best_upper_bound_eur=bound,
        witness=witness,
        solver_name="controlled-highs",
        solver_version="controlled-1",
        pyomo_version="6.10.1",
        highspy_version="1.15.1",
        configured_options={"threads": 1},
        model_cardinality={"variables": 1, "constraints": 1},
        runtime_seconds=runtime_seconds,
        runtime_metadata={"temporary_log": "/tmp/not-semantic.log"},
    )


def _finalize(
    raw: RawRobustFCRSolveResult,
    *,
    allow_feasible_incumbent_plan: bool = False,
):
    problem = build_authored_problem(
        allow_feasible_incumbent_plan=allow_feasible_incumbent_plan
    )
    profile = RobustFCRFormulationProfile.for_kind("restriction")
    return _finalize_solve_result(problem, profile, raw)


def test_optimal_zero_witness_emits_one_robust_plan() -> None:
    result = _finalize(_raw_result(witness=_zero_witness()))

    assert result.solver.solve_status == "optimal"
    assert result.solver.has_incumbent is True
    assert result.solver.absolute_gap_eur == 0.0
    assert result.solver.relative_gap == 0.0
    assert result.deployability_status == "eligible"
    assert result.deployability_reasons == ()
    assert result.deployable_plan is not None
    assert result.deployable_plan.producer.producer_kind == "robust"
    assert result.deployable_plan.solve_status == "optimal"
    assert len(result.decisions.energy_baseline_charge_positive_kw) == 24
    assert len(result.decisions.fcr_capacity_kw) == 6
    assert max(result.feasibility_audit.modeled_slacks.values()) == 0.0
    assert result.feasibility_audit.passes_deployability_audit is True


def test_feasible_incumbent_is_blocked_by_default_and_allowed_only_by_opt_in() -> None:
    raw = _raw_result(
        status="feasible",
        termination="time_limit",
        witness=_zero_witness(),
        objective=0.0,
        bound=1.0,
    )
    blocked = _finalize(raw)
    allowed = _finalize(raw, allow_feasible_incumbent_plan=True)

    assert blocked.deployable_plan is None
    assert "feasible_incumbent_not_opted_in" in blocked.deployability_reasons
    assert allowed.deployable_plan is not None
    assert allowed.deployable_plan.solve_status == "feasible"
    assert allowed.solver.relative_gap == 1.0


@pytest.mark.parametrize(
    ("status", "termination"),
    (
        ("no_solution", "time_limit"),
        ("infeasible", "infeasible"),
        ("unbounded", "unbounded"),
        ("failed", "solver_error"),
    ),
)
def test_non_solution_statuses_never_expose_decisions_or_plan(
    status: str,
    termination: str,
) -> None:
    raw = _raw_result(
        status=status,
        termination=termination,
        witness=None,
        objective=None,
        bound=None,
    )
    result = _finalize(raw)
    assert result.solver.solve_status == status
    assert result.decisions is None
    assert result.feasibility_audit is None
    assert result.deployable_plan is None
    assert result.deployability_status == "blocked"


def test_positive_terminal_slack_is_audited_and_blocks_plan() -> None:
    slack = DEPLOYABILITY_THRESHOLD * 10.0
    penalty = 100.0 * slack
    result = _finalize(
        _raw_result(
            witness=_zero_witness(terminal_slack=slack),
            objective=-penalty,
            bound=-penalty,
        )
    )
    assert result.feasibility_audit.modeled_slacks["terminal_end_kwh"] == slack
    assert result.feasibility_audit.passes_deployability_audit is False
    assert result.deployable_plan is None
    assert "feasibility_audit_failed" in result.deployability_reasons


def test_constraint_residual_above_threshold_blocks_plan() -> None:
    witness = _zero_witness()
    witness["x0"] = (11.0,) + (0.0,) * 23
    result = _finalize(
        _raw_result(witness=witness, objective=0.55, bound=0.55)
    )
    residuals = {
        item.family_id: item.maximum_positive_violation
        for item in result.feasibility_audit.constraint_families
    }
    assert residuals["pointwise_discharge_headroom"] > DEPLOYABILITY_THRESHOLD
    assert result.deployable_plan is None


@pytest.mark.parametrize(
    ("objective", "bound", "expected_absolute", "expected_relative"),
    (
        (10.0, 11.0, 1.0, 1.0 / 11.0),
        (-10.0, -9.0, 1.0, 0.1),
        (0.0, 0.0, 0.0, 0.0),
        (-0.0, 0.0, 0.0, 0.0),
    ),
)
def test_maximization_gap_uses_stable_absolute_denominator(
    objective: float,
    bound: float,
    expected_absolute: float,
    expected_relative: float,
) -> None:
    policy = build_authored_problem().solve_policy
    evidence = _normalize_maximization_gap(objective, bound, policy)
    assert evidence.absolute_gap_eur == expected_absolute
    assert evidence.relative_gap == pytest.approx(expected_relative)
    assert evidence.inconsistent_bound is False


def test_small_negative_gap_is_normalized_but_inconsistent_bound_is_unavailable() -> None:
    policy = build_authored_problem().solve_policy
    normalized = _normalize_maximization_gap(10.0, 9.9999995, policy)
    inconsistent = _normalize_maximization_gap(10.0, 9.0, policy)

    assert normalized.absolute_gap_eur == 0.0
    assert normalized.relative_gap == 0.0
    assert normalized.normalized_negative_gap is True
    assert inconsistent.absolute_gap_eur is None
    assert inconsistent.relative_gap is None
    assert inconsistent.inconsistent_bound is True


def test_missing_objective_or_bound_produces_unavailable_gaps() -> None:
    policy = build_authored_problem().solve_policy
    for objective, bound in ((None, 1.0), (1.0, None), (None, None)):
        evidence = _normalize_maximization_gap(objective, bound, policy)
        assert evidence.absolute_gap_eur is None
        assert evidence.relative_gap is None


def test_runtime_metadata_does_not_change_semantic_result_identity() -> None:
    first = _finalize(_raw_result(witness=_zero_witness(), runtime_seconds=0.1))
    second = _finalize(_raw_result(witness=_zero_witness(), runtime_seconds=9.9))
    assert first.runtime_metadata != second.runtime_metadata
    assert first.semantic_result_fingerprint == second.semantic_result_fingerprint


def test_raw_objective_mismatch_is_diagnostic_and_blocks_plan() -> None:
    result = _finalize(
        _raw_result(witness=_zero_witness(), objective=1.0, bound=1.0)
    )
    assert result.raw_objective.reconciliation_residual_eur == 1.0
    assert result.deployable_plan is None
    assert any(
        diagnostic.code == "objective_reconciliation_failed"
        for diagnostic in result.diagnostics
    )
