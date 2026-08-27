"""Solve and inspect one presolve-simple public Feature 013 restriction."""

from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import json

from open_energy_lab.control import (
    RecoveryWindowActivationBudget,
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRUncertaintyProfile,
    TerminalStoredEnergyRule,
    build_robust_fcr_bidding_problem,
    build_robust_fcr_time_contract,
    compare_robust_fcr_bounds,
    derive_non_intraday_horizon_budget,
    solve_robust_fcr_bid,
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _display_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _print_table(
    title: str,
    headers: tuple[str, ...],
    rows: tuple[tuple[object, ...], ...],
) -> None:
    rendered = tuple(
        tuple(_display_value(value) for value in row)
        for row in rows
    )
    widths = tuple(
        max(len(headers[index]), *(len(row[index]) for row in rendered))
        for index in range(len(headers))
    )
    print(title)
    print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(headers)))
    print("-+-".join("-" * value for value in widths))
    for row in rendered:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _print_problem_evidence(problem) -> None:
    time_contract = problem.time_contract
    _print_table(
        "multi-rate mapping table",
        ("mapping", "planning", "market blocks", "repeat", "first", "last"),
        (
            (
                "planning_to_energy",
                len(time_contract.planning_intervals),
                len(time_contract.energy_intervals),
                4,
                "0 -> 0",
                "95 -> 23",
            ),
            (
                "planning_to_fcr",
                len(time_contract.planning_intervals),
                len(time_contract.fcr_intervals),
                16,
                "0 -> 0",
                "95 -> 5",
            ),
        ),
    )
    inputs = problem.uncertainty.horizon_wide.derivation_inputs
    _print_table(
        "uncertainty derivation table",
        ("quantity", "value", "unit"),
        (
            ("horizon", inputs["horizon_hours"], "h"),
            ("recovery window", inputs["recovery_window_hours"], "h"),
            (
                "recovery activation budget",
                inputs["recovery_activation_budget_hours"],
                "h",
            ),
            ("full windows", inputs["full_window_count"], "count"),
            ("remainder", inputs["remainder_hours"], "h"),
            (
                "derived horizon budget",
                problem.uncertainty.horizon_wide.horizon_activation_budget_hours,
                "h",
            ),
        ),
    )


def _print_result_evidence(restriction, relaxation) -> None:
    _print_table(
        "value-semantics table",
        ("field", "value", "unit", "when known", "meaning"),
        tuple(
            (
                field,
                evidence["value"],
                "EUR",
                (
                    "before delivery"
                    if field in {
                        "optimization_objective_eur",
                        "best_upper_bound_eur",
                    }
                    else "after Feature 012 evaluation"
                ),
                evidence["meaning"],
            )
            for field, evidence in restriction.to_dict()["value_semantics"].items()
        ),
    )
    if restriction.raw_objective is not None:
        objective = restriction.raw_objective
        _print_table(
            "ex-ante objective-component table",
            ("component", "value", "unit", "sign"),
            (
                (
                    "day_ahead_energy_value",
                    objective.day_ahead_energy_value_eur,
                    "EUR",
                    "+",
                ),
                (
                    "fcr_capacity_value",
                    objective.fcr_capacity_value_eur,
                    "EUR",
                    "+",
                ),
                (
                    "feasibility_slack_penalty",
                    objective.feasibility_slack_penalty_eur,
                    "EUR",
                    "-",
                ),
                ("total_objective", objective.total_objective_eur, "EUR", "="),
                (
                    "reconciliation_residual",
                    objective.reconciliation_residual_eur,
                    "EUR",
                    "audit",
                ),
            ),
        )
    if restriction.feasibility_audit is not None:
        _print_table(
            "equation-family residual table",
            ("family", "relation", "unit", "checks", "maximum violation"),
            tuple(
                (
                    family.family_id,
                    family.relation,
                    family.canonical_unit,
                    family.checked_count,
                    family.maximum_positive_violation,
                )
                for family in restriction.feasibility_audit.constraint_families
            ),
        )
    cardinality_keys = (
        "planning_intervals",
        "triangular_pairs",
        "strict_triangular_pairs",
        "variables",
        "binaries",
        "active_constraints",
        "quadratic_structure_entries",
    )
    _print_table(
        "model-cardinality table",
        ("formulation", *cardinality_keys),
        tuple(
            (
                result.formulation.kind,
                *(result.solver.model_cardinality[key] for key in cardinality_keys),
            )
            for result in (restriction, relaxation)
        ),
    )


def build_small_problem():
    """Build a unique zero-bid case that still assembles the public 96-step MILP."""

    time_contract = build_robust_fcr_time_contract(
        delivery_date=date(2023, 6, 18),
        market_timezone="Europe/Paris",
    )
    battery = RobustFCRBatteryParameters(
        maximum_charge_power_kw=10.0,
        maximum_discharge_power_kw=10.0,
        minimum_stored_energy_kwh=0.0,
        maximum_stored_energy_kwh=20.0,
        initial_stored_energy_kwh=0.0,
        charge_efficiency=0.92,
        discharge_efficiency=0.92,
    )
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=0.25,
        recovery_window_hours=2.25,
    )
    uncertainty = RobustFCRUncertaintyProfile(
        recovery_window=recovery,
        horizon_wide=derive_non_intraday_horizon_budget(recovery),
    )
    prices = RobustFCRPriceInputs(
        day_ahead_energy_prices_eur_per_kwh=(1.0,) * 24,
        fcr_capacity_prices_eur_per_kw_block=(-1.0,) * 6,
        energy_interval_refs=tuple(
            f"small_day_ahead_price:{index}" for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"small_fcr_capacity_price:{index}" for index in range(6)
        ),
    )
    terminal = TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=0.0,
        allow_penalized_shortfall=False,
        shortfall_penalty_eur_per_kwh=100.0,
        rule_id="small-case-terminal-v1",
    )
    policy = RobustFCRSolvePolicy(
        solver_name="highs",
        time_limit_seconds=30.0,
        threads=1,
        random_seed=13,
        primal_feasibility_tolerance=1e-7,
        dual_feasibility_tolerance=1e-7,
        mip_feasibility_tolerance=1e-6,
        relative_mip_gap=1e-6,
        objective_comparison_absolute_tolerance_eur=1e-6,
        objective_comparison_relative_tolerance=1e-9,
        allow_feasible_incumbent_plan=False,
    )
    return build_robust_fcr_bidding_problem(
        problem_id="feature-013-small-case-v1",
        battery=battery,
        time_contract=time_contract,
        prices=prices,
        uncertainty=uncertainty,
        terminal_rule=terminal,
        solve_policy=policy,
        information_cutoff_utc=datetime(2023, 6, 17, 12, tzinfo=UTC),
        producer_input_fingerprints={
            "authored_case": _digest("feature-013-small-case-v1"),
            "market_prices": prices.price_input_fingerprint,
        },
        provenance={
            "source": "examples/robust_fcr_bidding/run_small_case.py",
            "case_kind": "project-authored",
        },
    )


def main() -> int:
    problem = build_small_problem()
    _print_problem_evidence(problem)
    restriction = solve_robust_fcr_bid(problem, formulation="restriction")
    relaxation = solve_robust_fcr_bid(problem, formulation="relaxation")
    exact = solve_robust_fcr_bid(problem, formulation="exact")
    comparison = compare_robust_fcr_bounds(
        restriction,
        relaxation,
        exact=exact,
    )
    print("restriction ex-ante optimization solver evidence")
    print(json.dumps(restriction.solver.to_dict(), indent=2, sort_keys=True))
    print("relaxation ex-ante upper-bound solver evidence")
    print(json.dumps(relaxation.solver.to_dict(), indent=2, sort_keys=True))
    print("bound comparison")
    print(json.dumps(comparison.to_dict(), indent=2, sort_keys=True))
    _print_result_evidence(restriction, relaxation)
    print(
        "exact evidence interpretation",
        {
            "status": comparison.exact_status,
            "solver_status": exact.solver.solve_status,
            "meaning": (
                "optional exact evidence was not requested; select a Gurobi solve "
                "policy explicitly to check restriction <= exact <= relaxation"
            ),
        },
    )
    if restriction.raw_objective is not None:
        print("ex-ante objective reconciliation")
        print(json.dumps(restriction.raw_objective.to_dict(), indent=2, sort_keys=True))
    if restriction.feasibility_audit is not None:
        print("independent residual and slack maxima")
        print(
            json.dumps(
                {
                    "constraint_families": {
                        item.family_id: item.maximum_positive_violation
                        for item in restriction.feasibility_audit.constraint_families
                    },
                    "maximum_modeled_slack": max(
                        restriction.feasibility_audit.modeled_slacks.values()
                    ),
                    "raw_witness_fingerprint": (
                        restriction.feasibility_audit.raw_witness_fingerprint
                    ),
                    "canonical_witness_fingerprint": (
                        restriction.feasibility_audit.canonical_witness_fingerprint
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
    if restriction.decisions is not None:
        print("charge-positive hourly energy schedule (kW)")
        print(list(restriction.decisions.energy_baseline_charge_positive_kw))
        print("four-hour symmetric FCR capacities (kW)")
        print(list(restriction.decisions.fcr_capacity_kw))
    print(
        "restriction deployability",
        restriction.deployability_status,
        restriction.deployability_reasons,
    )
    print(
        "relaxation deployability",
        relaxation.deployability_status,
        relaxation.deployability_reasons,
    )
    if restriction.deployable_plan is not None:
        print(
            "energy schedule fingerprint",
            restriction.deployable_plan.energy_schedule.schedule_fingerprint,
        )
        print(
            "FCR schedule fingerprint",
            restriction.deployable_plan.fcr_schedule.schedule_fingerprint,
        )
        print("plan fingerprint", restriction.deployable_plan.plan_fingerprint)
    print("restriction result fingerprint", restriction.semantic_result_fingerprint)
    print("relaxation result fingerprint", relaxation.semantic_result_fingerprint)
    return (
        0
        if restriction.deployable_plan is not None
        and relaxation.deployable_plan is None
        and comparison.restriction_le_relaxation.satisfied
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
