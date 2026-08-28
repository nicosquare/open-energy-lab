"""Public problem, uncertainty, time, and fingerprint contracts for Feature 013."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
import math

import pytest

from open_energy_lab.control.robust_fcr_bidding import (
    DECISION_CANONICALIZATION_ID,
    HORIZON_BUDGET_DERIVATION_RULE,
    RecoveryWindowActivationBudget,
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRUncertaintyProfile,
    RobustFCRValidationError,
    TerminalStoredEnergyRule,
    build_robust_fcr_bidding_problem,
    build_robust_fcr_time_contract,
    derive_non_intraday_horizon_budget,
)
from tests.robust_fcr_case_utils import (
    AUTHORED_DELIVERY_DATE,
    AUTHORED_INFORMATION_CUTOFF_UTC,
    AUTHORED_MARKET_TIMEZONE,
    authored_battery_mapping,
    authored_price_mapping,
    authored_solve_policy_mapping,
    authored_terminal_mapping,
    build_authored_problem,
)


def test_authored_problem_is_exact_ordinary_day_and_deterministic() -> None:
    first = build_authored_problem()
    second = build_authored_problem()

    assert first == second
    assert first.problem_fingerprint == second.problem_fingerprint
    assert len(first.time_contract.planning_intervals) == 96
    assert len(first.time_contract.energy_intervals) == 24
    assert len(first.time_contract.fcr_intervals) == 6
    assert first.time_contract.planning_to_energy == tuple(
        index // 4 for index in range(96)
    )
    assert first.time_contract.planning_to_fcr == tuple(
        index // 16 for index in range(96)
    )
    assert first.time_contract.to_dict()["mapping"] == {
        "planning_to_energy": [index // 4 for index in range(96)],
        "planning_to_fcr": [index // 16 for index in range(96)],
        "source_one_based_formulas": {
            "energy": "ceil(k / 4)",
            "fcr": "ceil(k / 16)",
        },
    }
    assert first.information_cutoff_utc == AUTHORED_INFORMATION_CUTOFF_UTC
    assert first.to_dict()["problem_fingerprint"] == first.problem_fingerprint


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("maximum_charge_power_kw", 0.0),
        ("maximum_discharge_power_kw", -1.0),
        ("minimum_stored_energy_kwh", -0.1),
        ("maximum_stored_energy_kwh", math.inf),
        ("initial_stored_energy_kwh", 21.0),
        ("charge_efficiency", 0.0),
        ("charge_efficiency", 1.01),
        ("discharge_efficiency", float("nan")),
    ),
)
def test_battery_rejects_invalid_physical_values(
    field_name: str,
    value: float,
) -> None:
    values = authored_battery_mapping()
    values[field_name] = value
    with pytest.raises(RobustFCRValidationError, match=field_name):
        RobustFCRBatteryParameters(**values)


def test_battery_is_frozen_and_has_content_fingerprint() -> None:
    battery = RobustFCRBatteryParameters(**authored_battery_mapping())
    assert len(battery.battery_fingerprint) == 64
    assert battery.to_dict()["units"] == {
        "power": "kW",
        "stored_energy": "kWh",
        "efficiency": "dimensionless",
    }
    with pytest.raises(FrozenInstanceError):
        battery.maximum_charge_power_kw = 99.0  # type: ignore[misc]


def test_time_contract_rejects_spring_and_fall_dst_days() -> None:
    for transition_day in (date(2023, 3, 26), date(2023, 10, 29)):
        with pytest.raises(RobustFCRValidationError, match="ordinary 24-hour"):
            build_robust_fcr_time_contract(
                delivery_date=transition_day,
                market_timezone="Europe/Paris",
            )


def test_time_contract_rejects_datetime_and_unknown_timezone() -> None:
    with pytest.raises(RobustFCRValidationError, match="delivery_date"):
        build_robust_fcr_time_contract(
            delivery_date=datetime(2023, 6, 18, tzinfo=UTC),  # type: ignore[arg-type]
            market_timezone="Europe/Paris",
        )
    with pytest.raises(RobustFCRValidationError, match="timezone"):
        build_robust_fcr_time_contract(
            delivery_date=AUTHORED_DELIVERY_DATE,
            market_timezone="Not/AZone",
        )


def test_prices_accept_negative_zero_and_tied_values_but_require_counts() -> None:
    time_contract = build_robust_fcr_time_contract(
        delivery_date=AUTHORED_DELIVERY_DATE,
        market_timezone=AUTHORED_MARKET_TIMEZONE,
    )
    prices = RobustFCRPriceInputs(
        day_ahead_energy_prices_eur_per_kwh=(-0.01,) + (0.0,) * 23,
        fcr_capacity_prices_eur_per_kw_block=(0.02,) * 6,
        energy_interval_refs=tuple(f"energy:{index}" for index in range(24)),
        fcr_interval_refs=tuple(f"fcr:{index}" for index in range(6)),
    )
    assert prices.day_ahead_energy_prices_eur_per_kwh[0] == -0.01
    assert len(prices.price_input_fingerprint) == 64

    with pytest.raises(RobustFCRValidationError, match="exactly 24"):
        replace(prices, day_ahead_energy_prices_eur_per_kwh=(0.0,) * 23)
    assert len(time_contract.time_contract_fingerprint) == 64


def test_uncertainty_sets_are_distinct_and_derive_reference_budget() -> None:
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=0.25,
        recovery_window_hours=2.25,
        pointwise_activation_lower=-1.0,
        pointwise_activation_upper=1.0,
    )
    horizon = derive_non_intraday_horizon_budget(recovery)
    profile = RobustFCRUncertaintyProfile(
        recovery_window=recovery,
        horizon_wide=horizon,
    )

    assert horizon.horizon_activation_budget_hours == 2.75
    assert horizon.derivation_rule == HORIZON_BUDGET_DERIVATION_RULE
    assert horizon.recovery_window_fingerprint == recovery.recovery_window_fingerprint
    assert profile.recovery_window is recovery
    assert profile.horizon_wide is horizon
    assert profile.to_dict()["semantics_version"].endswith(".v1")


@pytest.mark.parametrize(
    ("budget", "window"),
    ((0.0, 2.25), (-0.25, 2.25), (2.5, 2.25), (0.25, 0.0), (0.25, 2.2)),
)
def test_recovery_window_rejects_invalid_or_unaligned_budgets(
    budget: float,
    window: float,
) -> None:
    with pytest.raises(RobustFCRValidationError):
        RecoveryWindowActivationBudget(
            recovery_activation_budget_hours=budget,
            recovery_window_hours=window,
            pointwise_activation_lower=-1.0,
            pointwise_activation_upper=1.0,
        )


def test_solve_policy_defaults_and_configurable_objective_comparison() -> None:
    default = RobustFCRSolvePolicy(**authored_solve_policy_mapping())
    custom = RobustFCRSolvePolicy(
        **authored_solve_policy_mapping(
            objective_comparison_absolute_tolerance_eur=0.002,
            objective_comparison_relative_tolerance=0.003,
        )
    )
    assert default.objective_comparison_absolute_tolerance_eur == 1e-6
    assert default.objective_comparison_relative_tolerance == 1e-9
    assert default.decision_canonicalization_id == DECISION_CANONICALIZATION_ID
    assert custom.objective_comparison_allowance(10.0, 11.0) == 0.033
    assert custom.solve_policy_fingerprint != default.solve_policy_fingerprint

    for field_name in (
        "objective_comparison_absolute_tolerance_eur",
        "objective_comparison_relative_tolerance",
    ):
        values = authored_solve_policy_mapping()
        values[field_name] = -1.0
        with pytest.raises(RobustFCRValidationError, match=field_name):
            RobustFCRSolvePolicy(**values)


def test_solve_policy_rejects_unsupported_canonicalization_only() -> None:
    values = authored_solve_policy_mapping()
    values["decision_canonicalization_id"] = "caller-rounding"
    with pytest.raises(RobustFCRValidationError, match="canonicalization"):
        RobustFCRSolvePolicy(**values)


def test_problem_rejects_activation_evaluation_and_credential_leakage() -> None:
    base = build_authored_problem()
    common = {
        "problem_id": base.problem_id,
        "battery": base.battery,
        "time_contract": base.time_contract,
        "prices": base.prices,
        "uncertainty": base.uncertainty,
        "terminal_rule": base.terminal_rule,
        "solve_policy": base.solve_policy,
        "information_cutoff_utc": base.information_cutoff_utc,
        "provenance": {"source": "authored"},
    }
    for forbidden_key in (
        "activation_trace",
        "realized_settlement",
        "expected_replay",
        "comparison_result",
        "external_csv",
        "credential_token",
    ):
        with pytest.raises(RobustFCRValidationError, match="decision cutoff"):
            build_robust_fcr_bidding_problem(
                **common,
                producer_input_fingerprints={forbidden_key: "0" * 64},
            )


def test_problem_rejects_late_cutoff_and_terminal_outside_battery() -> None:
    base = build_authored_problem()
    with pytest.raises(RobustFCRValidationError, match="cutoff"):
        replace(
            base,
            information_cutoff_utc=base.time_contract.delivery_period.start_utc
            + timedelta(seconds=1),
        )
    invalid_terminal = TerminalStoredEnergyRule(
        **{
            **authored_terminal_mapping(),
            "minimum_terminal_stored_energy_kwh": 21.0,
        }
    )
    with pytest.raises(RobustFCRValidationError, match="terminal"):
        replace(base, terminal_rule=invalid_terminal)


def test_problem_fingerprint_covers_policy_and_deep_frozen_lineage() -> None:
    default = build_authored_problem()
    custom = build_authored_problem(
        objective_comparison_absolute_tolerance_eur=0.002,
    )
    assert default.problem_fingerprint != custom.problem_fingerprint
    assert tuple(default.provenance) == tuple(sorted(default.provenance))
    with pytest.raises(TypeError):
        default.provenance["new"] = "value"  # type: ignore[index]


def test_problem_fingerprint_is_independent_of_mapping_insertion_order() -> None:
    base = build_authored_problem()
    common = {
        "problem_id": "canonical-input-order-v1",
        "battery": base.battery,
        "time_contract": base.time_contract,
        "prices": base.prices,
        "uncertainty": base.uncertainty,
        "terminal_rule": base.terminal_rule,
        "solve_policy": base.solve_policy,
        "information_cutoff_utc": base.information_cutoff_utc,
    }
    forward = build_robust_fcr_bidding_problem(
        **common,
        producer_input_fingerprints={"alpha": "1" * 64, "omega": "2" * 64},
        provenance={"alpha": 1, "omega": {"left": 2, "right": 3}},
    )
    reversed_order = build_robust_fcr_bidding_problem(
        **common,
        producer_input_fingerprints={"omega": "2" * 64, "alpha": "1" * 64},
        provenance={"omega": {"right": 3, "left": 2}, "alpha": 1},
    )

    assert forward == reversed_order
    assert forward.problem_fingerprint == reversed_order.problem_fingerprint
    assert forward.to_dict() == reversed_order.to_dict()


def test_nondecision_numeric_change_changes_identity_despite_wide_comparison_tolerance() -> None:
    base = build_authored_problem(
        objective_comparison_absolute_tolerance_eur=1.0,
    )
    delta = 5e-7
    changed = replace(
        base,
        battery=replace(
            base.battery,
            maximum_charge_power_kw=(
                base.battery.maximum_charge_power_kw + delta
            ),
        ),
    )

    assert base.solve_policy.objective_comparison_allowance(0.0, delta) == 1.0
    assert base.problem_fingerprint != changed.problem_fingerprint
    assert base.comparison_problem_fingerprint != (
        changed.comparison_problem_fingerprint
    )


def test_price_values_from_shared_mapping_are_not_mutated() -> None:
    values = authored_price_mapping()
    original = dict(values)
    build_authored_problem()
    assert values == original
