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
    result = solve_robust_fcr_bid(problem, formulation="restriction")
    print("restriction solver evidence")
    print(json.dumps(result.solver.to_dict(), indent=2, sort_keys=True))
    if result.raw_objective is not None:
        print("ex-ante objective reconciliation")
        print(json.dumps(result.raw_objective.to_dict(), indent=2, sort_keys=True))
    if result.feasibility_audit is not None:
        print("independent residual and slack maxima")
        print(
            json.dumps(
                {
                    "constraint_families": {
                        item.family_id: item.maximum_positive_violation
                        for item in result.feasibility_audit.constraint_families
                    },
                    "maximum_modeled_slack": max(
                        result.feasibility_audit.modeled_slacks.values()
                    ),
                    "raw_witness_fingerprint": (
                        result.feasibility_audit.raw_witness_fingerprint
                    ),
                    "canonical_witness_fingerprint": (
                        result.feasibility_audit.canonical_witness_fingerprint
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
    if result.decisions is not None:
        print("charge-positive hourly energy schedule (kW)")
        print(list(result.decisions.energy_baseline_charge_positive_kw))
        print("four-hour symmetric FCR capacities (kW)")
        print(list(result.decisions.fcr_capacity_kw))
    print("deployability", result.deployability_status, result.deployability_reasons)
    if result.deployable_plan is not None:
        print("energy schedule fingerprint", result.deployable_plan.energy_schedule.schedule_fingerprint)
        print("FCR schedule fingerprint", result.deployable_plan.fcr_schedule.schedule_fingerprint)
        print("plan fingerprint", result.deployable_plan.plan_fingerprint)
    print("semantic result fingerprint", result.semantic_result_fingerprint)
    return 0 if result.deployable_plan is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
