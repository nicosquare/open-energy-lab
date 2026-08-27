"""Fixture-independent authored inputs shared by Feature 013 tests.

The module intentionally has no import-time dependency on ``open_energy_lab``
or a mathematical-programming backend.  Builders import public contracts only
when a test explicitly asks for a complete problem.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import json
from typing import Any


AUTHORED_DELIVERY_DATE = date(2023, 6, 18)
AUTHORED_MARKET_TIMEZONE = "Europe/Paris"
AUTHORED_INFORMATION_CUTOFF_UTC = datetime(2023, 6, 17, 12, tzinfo=UTC)
DECISION_CANONICALIZATION_ID = "solver-output-kw-1e-9-half-even-v1"
NATIVE_REFERENCE_BENCHMARK_PROFILE_ID = "native-reference-benchmark-highs-v1"


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def authored_battery_mapping() -> dict[str, object]:
    return {
        "maximum_charge_power_kw": 10.0,
        "maximum_discharge_power_kw": 10.0,
        "minimum_stored_energy_kwh": 0.0,
        "maximum_stored_energy_kwh": 20.0,
        "initial_stored_energy_kwh": 10.0,
        "charge_efficiency": 0.92,
        "discharge_efficiency": 0.92,
    }


def authored_time_mapping() -> dict[str, object]:
    return {
        "delivery_date": AUTHORED_DELIVERY_DATE,
        "market_timezone": AUTHORED_MARKET_TIMEZONE,
        "planning_interval_count": 96,
        "planning_resolution_hours": 0.25,
        "energy_interval_count": 24,
        "energy_resolution_hours": 1.0,
        "fcr_interval_count": 6,
        "fcr_block_hours": 4.0,
        "planning_to_energy": tuple(index // 4 for index in range(96)),
        "planning_to_fcr": tuple(index // 16 for index in range(96)),
    }


def authored_price_mapping() -> dict[str, object]:
    return {
        "day_ahead_energy_prices_eur_per_kwh": (
            0.050,
            0.045,
            0.040,
            0.035,
            0.030,
            0.025,
            0.040,
            0.055,
            0.070,
            0.085,
            0.100,
            0.090,
            0.075,
            0.060,
            0.050,
            0.045,
            0.055,
            0.070,
            0.095,
            0.120,
            0.110,
            0.090,
            0.070,
            0.055,
        ),
        "fcr_capacity_prices_eur_per_kw_block": (
            0.060,
            0.055,
            0.050,
            0.052,
            0.058,
            0.065,
        ),
    }


def authored_uncertainty_mapping() -> dict[str, float]:
    return {
        "recovery_activation_budget_hours": 0.25,
        "recovery_window_hours": 2.25,
        "pointwise_activation_lower": -1.0,
        "pointwise_activation_upper": 1.0,
        "horizon_hours": 24.0,
        "expected_horizon_activation_budget_hours": 2.75,
    }


def authored_terminal_mapping() -> dict[str, object]:
    return {
        "minimum_terminal_stored_energy_kwh": 10.0,
        "allow_penalized_shortfall": True,
        "shortfall_penalty_eur_per_kwh": 100.0,
        "rule_id": "authored-terminal-minimum-v1",
    }


def authored_solve_policy_mapping(
    *,
    objective_comparison_absolute_tolerance_eur: float = 1e-6,
    objective_comparison_relative_tolerance: float = 1e-9,
    allow_feasible_incumbent_plan: bool = False,
    time_limit_seconds: float = 30.0,
) -> dict[str, object]:
    return {
        "solver_name": "highs",
        "time_limit_seconds": float(time_limit_seconds),
        "threads": 1,
        "random_seed": 13,
        "primal_feasibility_tolerance": 1e-7,
        "dual_feasibility_tolerance": 1e-7,
        "mip_feasibility_tolerance": 1e-6,
        "relative_mip_gap": 1e-6,
        "objective_comparison_absolute_tolerance_eur": float(
            objective_comparison_absolute_tolerance_eur
        ),
        "objective_comparison_relative_tolerance": float(
            objective_comparison_relative_tolerance
        ),
        "allow_feasible_incumbent_plan": allow_feasible_incumbent_plan,
        "decision_canonicalization_id": DECISION_CANONICALIZATION_ID,
    }


def native_reference_benchmark_policy_mapping(
    *, time_limit_seconds: float = 3600.0
) -> dict[str, object]:
    """Return the complete caller-owned benchmark profile from the quickstart."""

    mapping = authored_solve_policy_mapping(
        time_limit_seconds=time_limit_seconds,
        objective_comparison_absolute_tolerance_eur=1e-6,
        objective_comparison_relative_tolerance=1e-9,
        allow_feasible_incumbent_plan=False,
    )
    return {"profile_id": NATIVE_REFERENCE_BENCHMARK_PROFILE_ID, **mapping}


def build_authored_problem(
    *,
    objective_comparison_absolute_tolerance_eur: float = 1e-6,
    objective_comparison_relative_tolerance: float = 1e-9,
    allow_feasible_incumbent_plan: bool = False,
    time_limit_seconds: float = 30.0,
) -> Any:
    """Construct the authored public problem with deliberately deferred imports."""

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
    )

    battery = RobustFCRBatteryParameters(**authored_battery_mapping())
    time_contract = build_robust_fcr_time_contract(
        delivery_date=AUTHORED_DELIVERY_DATE,
        market_timezone=AUTHORED_MARKET_TIMEZONE,
    )
    price_values = authored_price_mapping()
    prices = RobustFCRPriceInputs(
        **price_values,
        energy_interval_refs=tuple(
            f"authored_day_ahead_price:{index}" for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"authored_fcr_capacity_price:{index}" for index in range(6)
        ),
    )
    uncertainty_values = authored_uncertainty_mapping()
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=uncertainty_values[
            "recovery_activation_budget_hours"
        ],
        recovery_window_hours=uncertainty_values["recovery_window_hours"],
        pointwise_activation_lower=uncertainty_values[
            "pointwise_activation_lower"
        ],
        pointwise_activation_upper=uncertainty_values[
            "pointwise_activation_upper"
        ],
    )
    horizon = derive_non_intraday_horizon_budget(
        recovery,
        horizon_hours=uncertainty_values["horizon_hours"],
    )
    uncertainty = RobustFCRUncertaintyProfile(
        recovery_window=recovery,
        horizon_wide=horizon,
    )
    terminal_rule = TerminalStoredEnergyRule(**authored_terminal_mapping())
    policy = RobustFCRSolvePolicy(
        **authored_solve_policy_mapping(
            objective_comparison_absolute_tolerance_eur=(
                objective_comparison_absolute_tolerance_eur
            ),
            objective_comparison_relative_tolerance=(
                objective_comparison_relative_tolerance
            ),
            allow_feasible_incumbent_plan=allow_feasible_incumbent_plan,
            time_limit_seconds=time_limit_seconds,
        )
    )
    producer_inputs = {
        "authored_prices": _fingerprint(price_values),
        "authored_case": _fingerprint(
            {
                "battery": authored_battery_mapping(),
                "uncertainty": authored_uncertainty_mapping(),
                "terminal": authored_terminal_mapping(),
            }
        ),
    }
    return build_robust_fcr_bidding_problem(
        problem_id="feature-013-authored-ordinary-day-v1",
        battery=battery,
        time_contract=time_contract,
        prices=prices,
        uncertainty=uncertainty,
        terminal_rule=terminal_rule,
        solve_policy=policy,
        information_cutoff_utc=AUTHORED_INFORMATION_CUTOFF_UTC,
        producer_input_fingerprints=producer_inputs,
        provenance={
            "source": "tests/robust_fcr_case_utils.py",
            "case_kind": "project-authored",
            "profile_version": "feature-013-authored-v1",
        },
    )
