"""Controlled solver-evidence and deployability tests for Feature 013."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from open_energy_lab.control._robust_fcr_solver import (
    RawRobustFCRSolveResult,
    normalize_backend_termination_status,
    require_highs_backend,
    unavailable_exact_raw_result,
    unavailable_gurobi_raw_result,
)
from open_energy_lab.control.robust_fcr_bidding import (
    DEPLOYABILITY_THRESHOLD,
    RobustFCRBoundComparison,
    RobustFCRFormulationProfile,
    RobustFCRSolverDependencyUnavailableError,
    _canonicalize_kw,
    _canonicalize_witness_decisions,
    _finalize_solve_result,
    _normalize_maximization_gap,
    compare_robust_fcr_bounds,
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

    assert blocked.solver.incumbent_accepted is True
    assert blocked.deployable_plan is None
    assert "feasible_incumbent_not_opted_in" in blocked.deployability_reasons
    assert allowed.solver.incumbent_accepted is True
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


@pytest.mark.parametrize(
    ("termination", "has_incumbent", "expected"),
    (
        ("optimal", True, "optimal"),
        ("optimal", False, "failed"),
        ("maxTimeLimit", True, "feasible"),
        ("time_limit", False, "no_solution"),
        ("userInterrupt", True, "feasible"),
        ("resource_interrupted", False, "no_solution"),
        ("infeasible", False, "infeasible"),
        ("unbounded", False, "unbounded"),
        ("solverFailure", False, "failed"),
        ("unknown_but_incumbent", True, "feasible"),
    ),
)
def test_backend_termination_matrix_is_solver_neutral(
    termination: str,
    has_incumbent: bool,
    expected: str,
) -> None:
    assert normalize_backend_termination_status(
        termination,
        has_incumbent=has_incumbent,
    ) == expected


def test_incompatible_required_backend_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pyomo = SimpleNamespace(__version__="0.0-incompatible")

    def fake_import(name: str):
        if name == "pyomo":
            return fake_pyomo
        if name == "pyomo.environ":
            return SimpleNamespace()
        raise AssertionError(f"unexpected backend import: {name}")

    monkeypatch.setattr(
        "open_energy_lab.control._robust_fcr_solver.import_module",
        fake_import,
    )
    with pytest.raises(
        RobustFCRSolverDependencyUnavailableError,
        match=r"requires Pyomo 6\.10\.1.*0\.0-incompatible",
    ):
        require_highs_backend()


def test_unavailable_optional_exact_is_structured_not_a_required_failure() -> None:
    problem = build_authored_problem()
    raw = unavailable_exact_raw_result(
        "licensed Gurobi evidence was not selected",
        problem.solve_policy,
    )
    result = _finalize_solve_result(
        problem,
        RobustFCRFormulationProfile.for_kind("exact"),
        raw,
    )

    assert result.solver.solve_status == "unavailable"
    assert result.solver.termination_status == "optional_backend_unavailable"
    assert result.decisions is None
    assert result.deployability_status == "not_applicable"
    assert result.deployable_plan is None
    assert [value.code for value in result.diagnostics] == [
        "optional_exact_unavailable"
    ]
    assert result.solver.configured_options["NonConvex"] == 2


def test_unavailable_optional_linear_gurobi_does_not_claim_nonconvex_mode() -> None:
    problem = build_authored_problem()
    gurobi_problem = replace(
        problem,
        solve_policy=replace(problem.solve_policy, solver_name="gurobi"),
    )
    raw = unavailable_gurobi_raw_result(
        "licensed Gurobi evidence was not selected",
        gurobi_problem.solve_policy,
    )
    result = _finalize_solve_result(
        gurobi_problem,
        RobustFCRFormulationProfile.for_kind("restriction"),
        raw,
    )

    assert result.solver.solve_status == "unavailable"
    assert result.deployability_status == "blocked"
    assert result.deployable_plan is None
    assert "NonConvex" not in result.solver.configured_options
    assert [value.code for value in result.diagnostics] == [
        "optional_gurobi_unavailable"
    ]


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
    assert first.solver.semantic_dict() == second.solver.semantic_dict()
    assert first.decisions == second.decisions
    assert first.feasibility_audit == second.feasibility_audit
    assert first.to_dict()["value_semantics"] == second.to_dict()["value_semantics"]


def test_decision_canonicalization_uses_half_even_and_normalizes_signed_zero() -> None:
    assert _canonicalize_kw(1.0000000005) == 1.0
    assert _canonicalize_kw(1.0000000015) == 1.000000002
    assert _canonicalize_kw(-1.0000000005) == -1.0
    normalized_zero = _canonicalize_kw(-0.0000000005)
    assert normalized_zero == 0.0
    assert str(normalized_zero) == "0.0"


def test_canonical_decisions_reaudit_the_unchanged_auxiliary_witness() -> None:
    witness = _zero_witness()
    witness["x0"] = (4e-10,) + (0.0,) * 23
    decisions, canonical = _canonicalize_witness_decisions(witness)

    assert decisions.energy_baseline_charge_positive_kw[0] == 0.0
    assert canonical["x0"][0] == 0.0
    for key in set(witness) - {"x0", "xr"}:
        assert canonical[key] is witness[key]

    objective = 0.05 * 4e-10
    result = _finalize(
        _raw_result(
            witness=witness,
            objective=objective,
            bound=objective,
        )
    )
    assert result.feasibility_audit.raw_witness_fingerprint != (
        result.feasibility_audit.canonical_witness_fingerprint
    )
    assert result.feasibility_audit.passes_deployability_audit is True
    assert result.deployable_plan is not None


def test_diagnostics_are_canonically_ordered_not_backend_ordered() -> None:
    raw = replace(
        _raw_result(witness=_zero_witness()),
        diagnostics=(
            {
                "code": "zeta",
                "severity": "warning",
                "field_path": "solver.z",
                "message": "second by field path",
            },
            {
                "code": "beta",
                "severity": "info",
                "field_path": "solver.a",
                "message": "second by code",
            },
            {
                "code": "alpha",
                "severity": "info",
                "field_path": "solver.a",
                "message": "first by code",
            },
        ),
    )
    result = _finalize(raw)

    assert [value.code for value in result.diagnostics] == [
        "alpha",
        "beta",
        "zeta",
    ]


def test_serialized_bid_values_are_distinct_from_feature_012_realized_values() -> None:
    result = _finalize(
        _raw_result(witness=_zero_witness(), objective=0.0, bound=0.25)
    )
    semantics = result.to_dict()["value_semantics"]

    assert semantics["optimization_objective_eur"] == {
        "value": 0.0,
        "availability": "available",
        "meaning": "ex_ante_bid_selection_objective",
    }
    assert semantics["best_upper_bound_eur"] == {
        "value": 0.25,
        "availability": "available",
        "meaning": "ex_ante_solver_bound_for_maximization",
    }
    assert semantics["feature_012_realized_settlement_eur"]["value"] is None
    assert semantics["feature_012_realized_profit_eur"]["value"] is None
    assert {
        semantics["feature_012_realized_settlement_eur"]["availability"],
        semantics["feature_012_realized_profit_eur"]["availability"],
    } == {"evaluation_only_not_in_bid_result"}


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


def _comparison_result(
    kind: str,
    objective: float,
    *,
    absolute_tolerance: float = 1e-6,
    relative_tolerance: float = 1e-9,
):
    problem = build_authored_problem(
        objective_comparison_absolute_tolerance_eur=absolute_tolerance,
        objective_comparison_relative_tolerance=relative_tolerance,
    )
    profile = RobustFCRFormulationProfile.for_kind(kind)
    raw = _raw_result(
        witness=_zero_witness(),
        objective=0.0,
        bound=0.0,
    )
    base = _finalize_solve_result(problem, profile, raw)
    solver = replace(
        base.solver,
        objective_value_eur=objective,
        best_upper_bound_eur=objective,
        absolute_gap_eur=0.0,
        relative_gap=0.0,
    )
    return replace(
        base,
        solver=solver,
        deployability_status=("blocked" if kind == "restriction" else "not_applicable"),
        deployability_reasons=("comparison_test_result",),
        deployable_plan=None,
    )


def test_formulation_profiles_pin_distinct_operational_roles() -> None:
    restriction = RobustFCRFormulationProfile.for_kind("restriction")
    relaxation = RobustFCRFormulationProfile.for_kind("relaxation")
    exact = RobustFCRFormulationProfile.for_kind("exact")
    assert restriction.deployability_role == "candidate_plan"
    assert relaxation.deployability_role == "upper_bound_only"
    assert exact.deployability_role == "exact_evidence_only"
    assert len({value.formulation_fingerprint for value in (restriction, relaxation, exact)}) == 3


@pytest.mark.parametrize(
    ("restriction_objective", "relaxation_objective", "expected_satisfied"),
    (
        (10.0, 10.0, True),
        (10.000001, 10.0, True),
        (10.0000011, 10.0, False),
        (-9.999999, -10.0, True),
        (-9.9999989, -10.0, False),
    ),
)
def test_pairwise_bound_order_uses_default_absolute_boundary(
    restriction_objective: float,
    relaxation_objective: float,
    expected_satisfied: bool,
) -> None:
    comparison = compare_robust_fcr_bounds(
        _comparison_result("restriction", restriction_objective),
        _comparison_result("relaxation", relaxation_objective),
    )
    assert isinstance(comparison, RobustFCRBoundComparison)
    assert comparison.restriction_le_relaxation.satisfied is expected_satisfied
    assert comparison.restriction_le_relaxation.allowance_eur == pytest.approx(1e-6)
    assert comparison.overall_status == (
        "satisfied" if expected_satisfied else "violated"
    )


def test_pairwise_bound_order_uses_configured_relative_scale() -> None:
    comparison = compare_robust_fcr_bounds(
        _comparison_result(
            "restriction",
            1000.5,
            absolute_tolerance=0.01,
            relative_tolerance=0.001,
        ),
        _comparison_result(
            "relaxation",
            1000.0,
            absolute_tolerance=0.01,
            relative_tolerance=0.001,
        ),
    )
    assert comparison.restriction_le_relaxation.allowance_eur == 1.0005
    assert comparison.restriction_le_relaxation.satisfied is True


def test_bound_comparison_rejects_wrong_roles_and_mismatched_policy() -> None:
    restriction = _comparison_result("restriction", 1.0)
    relaxation = _comparison_result("relaxation", 2.0)
    with pytest.raises(ValueError, match="restriction formulation"):
        compare_robust_fcr_bounds(relaxation, relaxation)
    with pytest.raises(ValueError, match="relaxation formulation"):
        compare_robust_fcr_bounds(restriction, restriction)
    with pytest.raises(ValueError, match="comparison policy"):
        compare_robust_fcr_bounds(
            restriction,
            _comparison_result(
                "relaxation",
                2.0,
                absolute_tolerance=0.1,
            ),
        )


def test_exact_evidence_is_unavailable_or_checked_between_bounds() -> None:
    restriction = _comparison_result("restriction", 1.0)
    relaxation = _comparison_result("relaxation", 3.0)
    unavailable = compare_robust_fcr_bounds(restriction, relaxation)
    assert unavailable.restriction_le_exact is None
    assert unavailable.exact_le_relaxation is None
    assert unavailable.exact_status == "unavailable"

    checked = compare_robust_fcr_bounds(
        restriction,
        relaxation,
        exact=_comparison_result("exact", 2.0),
    )
    assert checked.restriction_le_exact.satisfied is True
    assert checked.exact_le_relaxation.satisfied is True
    assert checked.exact_status == "satisfied"


def test_relaxation_and_exact_results_never_expose_deployable_plans() -> None:
    for kind in ("relaxation", "exact"):
        problem = build_authored_problem()
        result = _finalize_solve_result(
            problem,
            RobustFCRFormulationProfile.for_kind(kind),
            _raw_result(witness=_zero_witness()),
        )
        assert result.deployability_status == "not_applicable"
        assert result.deployable_plan is None
        assert result.formulation.deployability_role.endswith("only")


def test_result_contract_enforces_formulation_deployability_roles() -> None:
    restriction = _comparison_result("restriction", 1.0)
    relaxation = _comparison_result("relaxation", 2.0)
    eligible = _finalize(_raw_result(witness=_zero_witness()))
    assert eligible.deployable_plan is not None

    with pytest.raises(ValueError, match="must be eligible or blocked"):
        replace(restriction, deployability_status="not_applicable")
    with pytest.raises(ValueError, match="must contain a deployable plan"):
        replace(eligible, deployable_plan=None)
    with pytest.raises(ValueError, match="not deployable"):
        replace(relaxation, deployability_status="eligible")
    with pytest.raises(ValueError, match="only an eligible restriction"):
        replace(relaxation, deployable_plan=eligible.deployable_plan)


def test_feature_015_refactor_guard_preserves_controlled_result_and_plan() -> None:
    """Freeze canonical decisions, schedules, result identity, and eligibility."""

    result = _finalize(_raw_result(witness=_zero_witness()))
    plan = result.deployable_plan

    assert result.deployability_status == "eligible"
    assert result.deployability_reasons == ()
    assert plan is not None
    assert result.decisions.energy_baseline_charge_positive_kw == (0.0,) * 24
    assert result.decisions.fcr_capacity_kw == (0.0,) * 6
    assert (
        result.decisions.decision_vector_fingerprint
        == "a00a601eb3cdd1acabf87e3c58c75233b9af3c109675c5d41af0a797bc5a180c"
    )
    assert (
        result.semantic_result_fingerprint
        == "15f1f5077033ecd7b7c2261bed82706ad26b56ead7c4f6889ab87e2f74ea2cae"
    )
    assert (
        plan.energy_schedule.schedule_fingerprint
        == "1e83cf52c59b1b85d6796bc063ef1d9f90b94d22fe076d58b30ca190debb73b2"
    )
    assert (
        plan.fcr_schedule.schedule_fingerprint
        == "1d1f4651e2bf2a691d227cdf3c7c315d558e798d7f24e510dc470d4a9f9a110a"
    )
    assert (
        plan.plan_fingerprint
        == "e81de0cad18c716aa8476883e90477e5a7dd056678bfe8391b9446be031d06e7"
    )
