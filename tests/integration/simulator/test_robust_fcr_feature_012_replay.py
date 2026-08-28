"""A deployable Feature 013 plan enters Feature 012 unchanged after acceptance."""

from __future__ import annotations

from dataclasses import replace

from open_energy_lab.control import (
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    TerminalStoredEnergyRule,
    solve_robust_fcr_bid,
)
from open_energy_lab.simulator import evaluate_fixed_fcr_bid
from tests.integration.simulator.robust_fcr_replay_utils import (
    build_post_acceptance_battery,
    build_post_acceptance_request,
)
from tests.robust_fcr_case_utils import build_authored_problem


def _presolve_zero_problem():
    base = build_authored_problem(time_limit_seconds=30.0)
    return replace(
        base,
        problem_id="feature-013-feature-012-replay-v1",
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
            rule_id="feature-013-replay-terminal-v1",
        ),
    )


def test_feasible_restriction_plan_replays_only_through_feature_012() -> None:
    solve_result = solve_robust_fcr_bid(
        _presolve_zero_problem(),
        formulation="restriction",
    )
    plan = solve_result.deployable_plan
    assert plan is not None
    assert solve_result.solver.solve_status == "optimal"
    assert solve_result.feasibility_audit.passes_deployability_audit is True

    battery = build_post_acceptance_battery(
        capacity_kwh=20.0,
        maximum_charge_power_kw=10.0,
        maximum_discharge_power_kw=10.0,
        minimum_stored_energy_kwh=0.0,
        maximum_stored_energy_kwh=20.0,
        initial_stored_energy_kwh=0.0,
        charge_efficiency=0.92,
        discharge_efficiency=0.92,
    )
    request = build_post_acceptance_request(plan, battery=battery)
    report = evaluate_fixed_fcr_bid(request)

    assert request.plan is plan
    assert request.energy_schedule is plan.energy_schedule
    assert request.fcr_schedule is plan.fcr_schedule
    assert request.input_fingerprints["plan"] == plan.plan_fingerprint
    assert report.status == "settled"
    assert report.plan_fingerprint == plan.plan_fingerprint
    assert report.schedule_identity["energy"]["schedule_fingerprint"] == (
        plan.energy_schedule.schedule_fingerprint
    )
    assert report.schedule_identity["fcr"]["schedule_fingerprint"] == (
        plan.fcr_schedule.schedule_fingerprint
    )
    assert report.physical_metrics["interval_counts"] == {
        "activation": 96,
        "checkpoint": 96,
        "energy": 24,
        "fcr": 6,
    }
    assert report.physical_metrics["saturation_event_count"] == 0
    assert report.optimization_metadata["objective"] == plan.objective.to_dict()
    assert report.optimization_metadata["objective_bound"] == (
        plan.objective_bound.to_dict()
    )
    assert report.optimization_metadata["objective"]["meaning"] == (
        "optimization_objective"
    )
    assert report.settlement["total_profit_eur"] == 0.0
    assert report.total_profit_eur == 0.0
    assert report.trace_fingerprint is not None
    assert report.settlement_fingerprint is not None
    assert report.result_fingerprint is not None
