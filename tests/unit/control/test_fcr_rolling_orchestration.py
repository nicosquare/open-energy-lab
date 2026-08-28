"""Hand-calculable rolling indices, fixed tails, and formulation assembly."""

from __future__ import annotations

from dataclasses import replace
import math

import pytest

from open_energy_lab.control import (
    RobustFCRAcceptedDecisionFixings,
    RollingFCRValidationError,
    extract_accepted_predecessor_fixings,
)
from open_energy_lab.control._robust_fcr_formulation import (
    assemble_arbitrage_only_model,
    assemble_rolling_0800_model,
    derive_rolling_source_indices,
    propagate_fixed_tail_robust_bounds,
)
from tests.fcr_rolling_case_utils import (
    AUTHORED_DELIVERY_DATES,
    build_authored_accepted_fixings,
    build_authored_day_input,
    build_authored_fixed_plan,
    build_authored_manifest,
    build_authored_rolling_problem,
)


def test_0800_lower_index_and_signed_dimensions_match_the_source() -> None:
    indices = derive_rolling_source_indices(8)

    assert indices["K_lower"] == -63
    assert indices["planning_indices"] == tuple(range(-63, 97))
    assert indices["energy_indices"] == tuple(range(-15, 25))
    assert indices["fcr_indices"] == tuple(range(-3, 7))
    assert indices["fixed_energy_indices"] == tuple(range(-15, 1))
    assert indices["fixed_fcr_indices"] == tuple(range(-3, 1))
    assert len(indices["planning_indices"]) == 160
    assert len(indices["energy_indices"]) == 40
    assert len(indices["fcr_indices"]) == 10


def test_zero_fixed_tail_preserves_the_cutoff_state_for_both_robust_bounds() -> None:
    lower, upper = propagate_fixed_tail_robust_bounds(
        initial_stored_energy_kwh=10.0,
        source_energy_positive_discharge_kw=(0.0,) * 16,
        fcr_capacity_kw=(0.0,) * 4,
        charge_efficiency=0.92,
        discharge_efficiency=0.92,
        activation_budget_hours=2.0,
    )

    assert lower == 10.0
    assert upper == 10.0


def test_fixed_tail_efficiency_and_activation_budget_are_hand_calculable() -> None:
    lower, upper = propagate_fixed_tail_robust_bounds(
        initial_stored_energy_kwh=10.0,
        source_energy_positive_discharge_kw=(1.0,) * 16,
        fcr_capacity_kw=(1.0,) * 4,
        charge_efficiency=0.8,
        discharge_efficiency=0.5,
        activation_budget_hours=2.0,
    )

    # Sixteen hours at +1 kW discharge consume 32 kWh. Two activation-hours
    # add another 4 kWh upward, while two downward hours recover 4 kWh.
    assert lower == pytest.approx(-26.0)
    assert upper == pytest.approx(-18.0)


def test_accepted_fixings_enforce_explicit_public_to_source_sign_mapping() -> None:
    fixings = build_authored_accepted_fixings(
        public_energy_charge_positive_kw=tuple(float(index) for index in range(16))
    )

    assert fixings.energy_source_indices == tuple(range(-15, 1))
    assert fixings.source_energy_positive_discharge_kw == tuple(
        -float(index) for index in range(16)
    )
    with pytest.raises(RollingFCRValidationError, match="explicit negation"):
        replace(
            fixings,
            source_energy_positive_discharge_kw=(0.0,) * 16,
        )


def test_exact_fixings_are_extracted_from_the_unchanged_full_precision_plan() -> None:
    energy = tuple(index / 13.0 + 1e-10 for index in range(24))
    fcr = tuple(index / 7.0 + 2e-10 for index in range(6))
    plan = build_authored_fixed_plan(
        energy_charge_positive_kw=energy,
        fcr_capacity_kw=fcr,
    )

    fixings = extract_accepted_predecessor_fixings(
        plan=plan,
        predecessor_problem_fingerprint="8" * 64,
        predecessor_result_fingerprint="9" * 64,
    )

    assert fixings.predecessor_plan_fingerprint == plan.plan_fingerprint
    assert fixings.energy_source_indices == tuple(range(-15, 1))
    assert fixings.energy_public_charge_positive_kw == energy[8:]
    assert fixings.source_energy_positive_discharge_kw == tuple(
        -value for value in energy[8:]
    )
    assert fixings.fcr_source_indices == tuple(range(-3, 1))
    assert fixings.fcr_capacity_kw == fcr[2:]
    assert all("T" in value and "/" in value for value in fixings.energy_interval_refs)
    assert all("T" in value and "/" in value for value in fixings.fcr_interval_refs)


def test_0800_bootstrap_has_no_fixings_and_predecessors_follow_manifest_order() -> None:
    original = build_authored_manifest(
        "script-14-restriction-rolling-0800-v1"
    )
    warmup = original.dates[0]
    non_adjacent_closeout = replace(
        original.dates[-1],
        execution_role="close-out",
        comparison_eligible=False,
        reason_codes=("closes_non_adjacent_listed_predecessor",),
    )
    manifest = replace(original, dates=(warmup, non_adjacent_closeout))
    bootstrap = build_authored_day_input(manifest, warmup.delivery_date)

    assert bootstrap.accepted_fixings is None
    assert bootstrap.predecessor_prices is None
    assert manifest.listed_predecessor_date(warmup.delivery_date) is None
    assert manifest.listed_predecessor_date(
        non_adjacent_closeout.delivery_date
    ) == warmup.delivery_date


def test_0800_problem_keeps_16_and_4_fixings_and_separates_fixed_tail_objective() -> None:
    fixings = build_authored_accepted_fixings(
        public_energy_charge_positive_kw=(-1.0,) * 16,
        fcr_capacity_kw=(2.0,) * 4,
    )
    problem = build_authored_rolling_problem(
        "script-14-restriction-rolling-0800-v1",
        accepted_fixings=fixings,
    )
    predecessor_prices = problem.predecessor_prices
    assert predecessor_prices is not None
    expected = sum(predecessor_prices.day_ahead_energy_prices_eur_per_kwh[8:])
    expected += 2.0 * sum(
        predecessor_prices.fcr_capacity_prices_eur_per_kw_block[2:]
    )

    assert problem.K_lower == -63
    assert len(problem.source_planning_indices) == 160
    assert len(problem.source_energy_indices) == 40
    assert len(problem.source_fcr_indices) == 10
    assert problem.accepted_fixings is fixings
    assert problem.fixed_tail_objective_eur == pytest.approx(expected)
    assert problem.to_dict()["sign_mapping"].startswith("source-positive-discharge")


def test_0800_problem_rejects_missing_predecessor_prices_or_fixings() -> None:
    problem = build_authored_rolling_problem(
        "script-14-restriction-rolling-0800-v1"
    )

    with pytest.raises(RollingFCRValidationError, match="predecessor prices"):
        replace(problem, predecessor_prices=None)
    with pytest.raises(RollingFCRValidationError, match="accepted fixings"):
        replace(problem, accepted_fixings=None)


def test_no_fcr_assembly_has_24_hourly_decisions_and_six_model_fixed_zeros() -> None:
    pyo = pytest.importorskip("pyomo.environ")
    problem = build_authored_rolling_problem(
        "script-13-arbitrage-only-midnight-v1"
    )
    assembled = assemble_arbitrage_only_model(problem, pyomo_environ=pyo)

    assert assembled.handoff.formulation_kind == "arbitrage_only"
    assert assembled.handoff.cardinality["planning_intervals"] == 24
    assert assembled.handoff.cardinality["energy_intervals"] == 24
    assert assembled.handoff.cardinality["fcr_intervals"] == 6
    assert assembled.handoff.cardinality["fixed_zero_fcr_decisions"] == 6
    assert tuple(assembled.model.x0) == tuple(range(1, 25))
    assert all(assembled.model.xr[index].fixed for index in range(1, 7))
    assert all(assembled.model.xr[index].value == 0.0 for index in range(1, 7))


def test_rolling_0800_assembly_has_exact_source_frame_and_fixed_values() -> None:
    pyo = pytest.importorskip("pyomo.environ")
    public = tuple(0.25 * index for index in range(16))
    fcr = (1.0, 2.0, 3.0, 4.0)
    fixings = build_authored_accepted_fixings(
        public_energy_charge_positive_kw=public,
        fcr_capacity_kw=fcr,
    )
    problem = build_authored_rolling_problem(
        "script-14-restriction-rolling-0800-v1",
        accepted_fixings=fixings,
    )
    assembled = assemble_rolling_0800_model(problem, pyomo_environ=pyo)

    cardinality = assembled.handoff.cardinality
    assert cardinality["planning_intervals"] == 160
    assert cardinality["energy_intervals"] == 40
    assert cardinality["fcr_intervals"] == 10
    assert cardinality["fixed_predecessor_energy_decisions"] == 16
    assert cardinality["fixed_predecessor_fcr_decisions"] == 4
    assert tuple(assembled.model.x0) == tuple(range(-15, 25))
    assert tuple(assembled.model.xr) == tuple(range(-3, 7))
    for index, expected in zip(range(-15, 1), (-value for value in public), strict=True):
        assert assembled.model.x0[index].fixed
        assert assembled.model.x0[index].value == expected
    for index, expected in zip(range(-3, 1), fcr, strict=True):
        assert assembled.model.xr[index].fixed
        assert assembled.model.xr[index].value == expected


def test_terminal_constraint_uses_current_day_end_for_no_fcr_and_full_frame_for_0800() -> None:
    pyo = pytest.importorskip("pyomo.environ")
    no_fcr = assemble_arbitrage_only_model(
        build_authored_rolling_problem("script-13-arbitrage-only-midnight-v1"),
        pyomo_environ=pyo,
    )
    overlap = assemble_rolling_0800_model(
        build_authored_rolling_problem(
            "script-14-restriction-rolling-0800-v1"
        ),
        pyomo_environ=pyo,
    )

    no_fcr_terminal = next(iter(no_fcr.constraint_handles["terminal_stored_energy"].values()))
    overlap_terminal = next(iter(overlap.constraint_handles["terminal_stored_energy"].values()))
    assert len(tuple(no_fcr.model.alpha)) == 24
    assert len(tuple(overlap.model.alpha)) == 160
    assert no_fcr_terminal.upper is not None
    assert overlap_terminal.upper is not None
    assert math.isfinite(float(pyo.value(overlap_terminal.upper)))
