"""Explicit external-data replay of native and recorded reference schedules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oel_validation.scripts.run_fcr_bid_reference_parity import (
    assemble_reference_request,
)
from open_energy_lab.control.robust_fcr_bidding import _fingerprint
from open_energy_lab.control import (
    RobustFCRSolvePolicy,
    solve_robust_fcr_bid,
)
from oel_validation.robust_fcr_reference import (
    build_robust_fcr_reference_problem,
    load_robust_fcr_reference_fixture,
)
from oel_validation.reference_fcr import (
    load_golden_reference_fixture,
    load_reference_activation_trace,
)
from open_energy_lab.simulator import evaluate_fixed_fcr_bid
from tests.integration.simulator.robust_fcr_replay_utils import (
    build_post_acceptance_battery,
    build_post_acceptance_request,
)
from tests.robust_fcr_case_utils import authored_solve_policy_mapping


pytestmark = pytest.mark.external_reference_data

OPTIMIZATION_FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bidding/"
    "robust_storage_bidding_2023-06-18_restriction_v1.json"
)
EVALUATION_FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)
ACTIVATION_PATH = Path(
    "artifacts/reference/robust_storage_bidding/regulation_signal.csv"
)
EXTERNAL_REPLAY_PROFILE_ID = "native-reference-external-replay-highs-v1"
EXPECTED_EXTERNAL_REPLAY_POLICY_FINGERPRINT = (
    "f99c91a2afff96667c11797c47ea95e04a37756c0cddbcbef19bf7617c5a863c"
)


def _external_activation_path_or_skip() -> Path:
    if not ACTIVATION_PATH.is_file():
        pytest.skip(
            "external Feature 012 activation CSV is absent; install the governed "
            f"file explicitly at {ACTIVATION_PATH} and rerun this selected test"
        )
    return ACTIVATION_PATH


def _external_replay_policy() -> RobustFCRSolvePolicy:
    policy = RobustFCRSolvePolicy(
        **authored_solve_policy_mapping(
            time_limit_seconds=600.0,
            allow_feasible_incumbent_plan=True,
        )
    )
    assert _fingerprint(policy.to_dict()) == EXPECTED_EXTERNAL_REPLAY_POLICY_FINGERPRINT
    return policy


def _skip_without_deployable_native_plan(result) -> None:
    if result.deployable_plan is not None:
        return
    pytest.skip(
        "native restriction did not produce an optimal, audited deployable plan "
        "within the explicit 600-second external-replay resource policy: "
        + json.dumps(
            {
                "solve_status": result.solver.solve_status,
                "termination_status": result.solver.termination_status,
                "has_incumbent": result.solver.has_incumbent,
                "incumbent_accepted": result.solver.incumbent_accepted,
                "deployability_status": result.deployability_status,
                "deployability_reasons": list(result.deployability_reasons),
                "diagnostics": [value.to_dict() for value in result.diagnostics],
            },
            sort_keys=True,
        )
    )


def test_native_and_recorded_schedules_share_feature_012_external_replay() -> None:
    activation_path = _external_activation_path_or_skip()
    optimization_fixture = load_robust_fcr_reference_fixture(
        OPTIMIZATION_FIXTURE_PATH
    )
    evaluation_fixture = load_golden_reference_fixture(EVALUATION_FIXTURE_PATH)
    cross_reference = optimization_fixture.evaluation_fixture_reference
    assert cross_reference["fixture_id"] == evaluation_fixture.fixture_id
    assert cross_reference["fixture_fingerprint"] == (
        evaluation_fixture.fixture_fingerprint
    )

    # Bid selection is complete before the evaluation-only CSV is opened.
    replay_policy = _external_replay_policy()
    problem = build_robust_fcr_reference_problem(
        optimization_fixture,
        solve_policy=replay_policy,
    )
    native = solve_robust_fcr_bid(problem, formulation="restriction")
    _skip_without_deployable_native_plan(native)
    native_plan = native.deployable_plan
    assert native_plan is not None

    activation_trace = load_reference_activation_trace(
        activation_path,
        descriptor=evaluation_fixture.external_activation,
    )
    recorded_request = assemble_reference_request(
        fixture=evaluation_fixture,
        activation_trace=activation_trace,
    )
    battery = problem.battery
    native_request = build_post_acceptance_request(
        native_plan,
        battery=build_post_acceptance_battery(
            capacity_kwh=float(
                evaluation_fixture.reference_configuration["capacity_kwh"]
            ),
            maximum_charge_power_kw=battery.maximum_charge_power_kw,
            maximum_discharge_power_kw=battery.maximum_discharge_power_kw,
            minimum_stored_energy_kwh=battery.minimum_stored_energy_kwh,
            maximum_stored_energy_kwh=battery.maximum_stored_energy_kwh,
            initial_stored_energy_kwh=battery.initial_stored_energy_kwh,
            charge_efficiency=battery.charge_efficiency,
            discharge_efficiency=battery.discharge_efficiency,
        ),
        activation_trace=activation_trace,
        activation_resolution="PT10S",
        day_ahead_prices_eur_per_mwh=tuple(
            value * 1000.0
            for value in problem.prices.day_ahead_energy_prices_eur_per_kwh
        ),
        fcr_capacity_prices_eur_per_kw_block=(
            problem.prices.fcr_capacity_prices_eur_per_kw_block
        ),
    )
    assert native_request.plan is native_plan
    assert native_request.activation_trace is recorded_request.activation_trace
    assert native_request.input_fingerprints["activation_trace"] == (
        recorded_request.input_fingerprints["activation_trace"]
    )

    native_report = evaluate_fixed_fcr_bid(native_request)
    recorded_report = evaluate_fixed_fcr_bid(recorded_request)

    for report in (native_report, recorded_report):
        assert report.status == "settled"
        assert report.physical_metrics["interval_counts"] == {
            "activation": 8_640,
            "checkpoint": 96,
            "energy": 24,
            "fcr": 6,
        }
        assert report.settlement is not None

    assert native_report.plan_fingerprint == native_plan.plan_fingerprint
    assert recorded_report.plan_fingerprint == recorded_request.plan.plan_fingerprint
    print(
        "robust_fcr_external_reference_replay="
        + json.dumps(
            {
                "activation_trace_fingerprint": activation_trace.artifact_fingerprint,
                "external_replay_profile_id": EXTERNAL_REPLAY_PROFILE_ID,
                "external_replay_policy_fingerprint": _fingerprint(replay_policy.to_dict()),
                "native": {
                    "solve_status": native.solver.solve_status,
                    "optimization_objective_eur": native.solver.objective_value_eur,
                    "best_upper_bound_eur": native.solver.best_upper_bound_eur,
                    "plan_fingerprint": native_plan.plan_fingerprint,
                    "trace_fingerprint": _fingerprint(native_report.to_dict()["physical_trace"]),
                    "settlement_fingerprint": _fingerprint(native_report.to_dict()["settlement"]),
                    "result_fingerprint": _fingerprint(native_report.to_dict()),
                    "total_profit_eur": native_report.total_profit_eur,
                },
                "recorded": {
                    "plan_fingerprint": recorded_request.plan.plan_fingerprint,
                    "trace_fingerprint": _fingerprint(recorded_report.to_dict()["physical_trace"]),
                    "settlement_fingerprint": _fingerprint(recorded_report.to_dict()["settlement"]),
                    "result_fingerprint": _fingerprint(recorded_report.to_dict()),
                    "total_profit_eur": recorded_report.total_profit_eur,
                },
            },
            sort_keys=True,
        )
    )
