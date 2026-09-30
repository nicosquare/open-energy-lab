"""Hand-calculable equation, mapping, and cardinality evidence for Feature 013."""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module

import pytest

from open_energy_lab.control import (
    RecoveryWindowActivationBudget,
    RobustFCRUncertaintyProfile,
    derive_non_intraday_horizon_budget,
)
from open_energy_lab.control.robust_fcr_bidding import RobustFCRFormulationProfile
from open_energy_lab.control._robust_fcr_formulation import (
    assemble_robust_fcr_model,
    build_normalized_index_sets,
    model_cardinality_metadata,
)
from open_energy_lab.control.robust_fcr_bidding import _audit_witness
from tests.robust_fcr_case_utils import build_authored_problem


def _zero_witness() -> dict[str, object]:
    count = 96
    return {
        "x0": (0.0,) * 24,
        "xr": (0.0,) * 6,
        "xa": (0.0,) * count,
        "symin": (0.0,) * count,
        "symax": (0.0,) * count,
        "syK": (0.0, 0.0),
        "alpha": (0.0,) * count,
        "beta": (0.0,) * count,
        "lambda_l": (0.0,) * count,
        "lambda_h": (0.0,) * count,
        "Lambda_l": tuple((0.0,) * (outer + 1) for outer in range(count)),
        "Lambda_h": tuple((0.0,) * (outer + 1) for outer in range(count)),
        "u1": (0.0,) * (count - 1),
        "u2": (0.0,) * (count - 1),
        "v_res": (0.0,) * (count - 1),
    }


def _with_vector_value(
    witness: dict[str, object],
    name: str,
    index: int,
    value: float,
) -> dict[str, object]:
    updated = dict(witness)
    vector = list(updated[name])
    vector[index] = value
    updated[name] = tuple(vector)
    return updated


def _with_triangle_value(
    witness: dict[str, object],
    name: str,
    outer: int,
    inner: int,
    value: float,
) -> dict[str, object]:
    updated = dict(witness)
    triangle = [list(row) for row in updated[name]]
    triangle[outer][inner] = value
    updated[name] = tuple(tuple(row) for row in triangle)
    return updated


def _audit(witness: dict[str, object], *, reported_objective_eur: float = 0.0):
    return _audit_witness(
        build_authored_problem(),
        RobustFCRFormulationProfile.for_kind("restriction"),
        witness,
        reported_objective_eur=reported_objective_eur,
    )


def _family(audit, family_id: str):
    return next(
        family
        for family in audit.constraint_families
        if family.family_id == family_id
    )


def test_window_budget_derives_2_75_hours_with_complete_lineage() -> None:
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=0.25,
        recovery_window_hours=2.25,
    )
    horizon = derive_non_intraday_horizon_budget(recovery)

    assert horizon.horizon_activation_budget_hours == 2.75
    assert horizon.to_dict()["derivation_inputs"] == {
        "full_window_count": 10,
        "horizon_hours": 24.0,
        "recovery_activation_budget_hours": 0.25,
        "recovery_window_hours": 2.25,
        "remainder_hours": 1.5,
    }
    assert horizon.to_dict()["source_refs"] == [
        "baselines/robust_storage_bidding/code/02_model.jl:293-305"
    ]
    assert recovery.to_dict()["source_refs"] == [
        "baselines/robust_storage_bidding/code/01_datastruct.jl:8-9",
        "baselines/robust_storage_bidding/code/12.jl:30-33",
    ]


@pytest.mark.parametrize(
    ("budget", "window", "message"),
    (
        (0.0, 2.25, "greater than zero"),
        (2.5, 2.25, "cannot exceed"),
        (0.25, 2.2, "PT15M"),
    ),
)
def test_invalid_recovery_budget_combinations_are_rejected(
    budget: float,
    window: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RecoveryWindowActivationBudget(
            recovery_activation_budget_hours=budget,
            recovery_window_hours=window,
        )


def test_horizon_budget_rejects_tampered_value_and_derivation_inputs() -> None:
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=0.25,
        recovery_window_hours=2.25,
    )
    horizon = derive_non_intraday_horizon_budget(recovery)
    with pytest.raises(ValueError, match="derived horizon activation budget"):
        replace(horizon, horizon_activation_budget_hours=2.5)

    tampered_inputs = dict(horizon.derivation_inputs)
    tampered_inputs["full_window_count"] = 9
    with pytest.raises(ValueError, match="derivation_inputs"):
        replace(horizon, derivation_inputs=tampered_inputs)

    with pytest.raises(ValueError, match="lineage"):
        RobustFCRUncertaintyProfile(
            recovery_window=recovery,
            horizon_wide=replace(
                horizon,
                recovery_window_fingerprint="0" * 64,
            ),
        )


def test_public_time_mapping_repeats_hourly_and_fcr_blocks_exactly() -> None:
    payload = build_authored_problem().time_contract.to_dict()
    energy_map = payload["mapping"]["planning_to_energy"]
    fcr_map = payload["mapping"]["planning_to_fcr"]

    assert len(energy_map) == len(fcr_map) == 96
    assert energy_map == [index // 4 for index in range(96)]
    assert fcr_map == [index // 16 for index in range(96)]
    assert all(energy_map.count(index) == 4 for index in range(24))
    assert all(fcr_map.count(index) == 16 for index in range(6))
    assert payload["mapping"]["source_one_based_formulas"] == {
        "energy": "ceil(k / 4)",
        "fcr": "ceil(k / 16)",
    }
    assert payload["source_refs"] == [
        "baselines/robust_storage_bidding/code/02_model.jl:170-174,252-253",
        "baselines/robust_storage_bidding/code/12.jl:27-47",
    ]


def test_pointwise_headroom_oracle_reports_one_kw_discharge_violation() -> None:
    witness = _with_vector_value(_zero_witness(), "x0", 0, 8.0)
    witness = _with_vector_value(witness, "xr", 0, 3.0)
    audit = _audit(witness, reported_objective_eur=0.58)

    assert _family(audit, "pointwise_charge_headroom").maximum_positive_violation == 0.0
    discharge = _family(audit, "pointwise_discharge_headroom")
    assert discharge.maximum_positive_violation == 1.0
    assert discharge.witness_indices == ((0,), (1,), (2,), (3,))


def test_efficiency_epigraph_oracles_distinguish_charge_and_discharge() -> None:
    charge = _with_vector_value(_zero_witness(), "x0", 0, -2.0)
    for index in range(4):
        charge = _with_vector_value(charge, "alpha", index, -2.0)
    charge_audit = _audit(charge, reported_objective_eur=-0.1)
    assert _family(
        charge_audit, "alpha_charge_epigraph"
    ).maximum_positive_violation == pytest.approx(0.16)
    assert _family(
        charge_audit, "alpha_discharge_epigraph"
    ).maximum_positive_violation == 0.0

    discharge = _with_vector_value(_zero_witness(), "x0", 0, 2.0)
    discharge = _with_vector_value(discharge, "xr", 0, 1.0)
    for index in range(4):
        discharge = _with_vector_value(discharge, "alpha", index, 2.0)
    for index in range(16):
        discharge = _with_vector_value(discharge, "beta", index, 3.0)
    discharge_audit = _audit(discharge, reported_objective_eur=0.16)
    assert _family(
        discharge_audit, "alpha_charge_epigraph"
    ).maximum_positive_violation == 0.0
    assert _family(
        discharge_audit, "alpha_discharge_epigraph"
    ).maximum_positive_violation == pytest.approx(2.0 / 0.92 - 2.0)
    assert _family(
        discharge_audit, "beta_charge_epigraph"
    ).maximum_positive_violation == 0.0
    assert _family(
        discharge_audit, "beta_discharge_epigraph"
    ).maximum_positive_violation == pytest.approx(3.0 / 0.92 - 3.0)


def test_lower_and_upper_robust_stored_energy_oracles_are_prefix_based() -> None:
    lower = _with_vector_value(_zero_witness(), "lambda_l", 0, 4.0)
    lower_audit = _audit(lower)
    assert _family(lower_audit, "lower_stored_energy").maximum_positive_violation == 1.0
    assert _family(lower_audit, "lower_stored_energy").witness_indices == ((0,),)

    upper = _with_vector_value(_zero_witness(), "lambda_h", 0, 2.0)
    upper = _with_triangle_value(upper, "Lambda_h", 0, 0, 20.0)
    upper_audit = _audit(upper)
    assert _family(upper_audit, "upper_stored_energy").maximum_positive_violation == 0.5
    assert _family(upper_audit, "upper_stored_energy").witness_indices == ((0,),)


def test_terminal_shortfall_and_inert_slacks_remain_visible_and_penalized() -> None:
    witness = _with_vector_value(_zero_witness(), "alpha", 0, 4.0)
    without_shortfall = _audit(witness)
    assert _family(
        without_shortfall, "terminal_stored_energy"
    ).maximum_positive_violation == 1.0

    witness["syK"] = (2.0, 1.0)
    witness = _with_vector_value(witness, "symin", 0, 0.25)
    witness = _with_vector_value(witness, "symax", 0, 0.5)
    with_shortfall = _audit(witness, reported_objective_eur=-375.0)
    assert _family(
        with_shortfall, "terminal_stored_energy"
    ).maximum_positive_violation == 0.0
    assert with_shortfall.modeled_slacks["terminal_start_kwh"] == 2.0
    assert with_shortfall.modeled_slacks["terminal_end_kwh"] == 1.0
    assert with_shortfall.modeled_slacks["stored_energy_lower_0_kwh"] == 0.25
    assert with_shortfall.modeled_slacks["stored_energy_upper_0_kwh"] == 0.5
    assert with_shortfall.objective.feasibility_slack_penalty_eur == 375.0


def test_ex_ante_objective_assembly_has_no_realized_settlement_component() -> None:
    witness = _with_vector_value(_zero_witness(), "x0", 0, 2.0)
    witness = _with_vector_value(witness, "xr", 0, 3.0)
    witness["syK"] = (0.25, 0.5)
    witness = _with_vector_value(witness, "symin", 0, 0.125)
    witness = _with_vector_value(witness, "symax", 0, 0.125)
    audit = _audit(witness, reported_objective_eur=-99.72)
    objective = audit.objective

    assert objective.day_ahead_energy_value_eur == pytest.approx(0.1)
    assert objective.fcr_capacity_value_eur == pytest.approx(0.18)
    assert objective.feasibility_slack_penalty_eur == 100.0
    assert objective.total_objective_eur == pytest.approx(-99.72)
    assert objective.reconciliation_residual_eur == pytest.approx(0.0)
    payload = objective.to_dict()
    assert payload["source_refs"] == [
        "baselines/robust_storage_bidding/code/02_model.jl:252-263"
    ]
    assert payload["excluded_realized_fields"] == [
        "activation_energy_revenue_eur",
        "realized_settlement_eur",
        "realized_profit_eur",
    ]


def test_every_audit_family_has_complete_independent_equation_evidence() -> None:
    audit = _audit(_zero_witness())
    expected_counts = {
        "pointwise_charge_headroom": 96,
        "pointwise_discharge_headroom": 96,
        "lower_coupling": 4656,
        "lambda_h_offdiag_charge_activation": 4560,
        "restriction_classification_lower": 95,
        "restriction_tightening_discharge": 4560,
        "terminal_stored_energy": 1,
    }
    for family in audit.constraint_families:
        payload = family.to_dict()
        assert payload.keys() == {
            "family_id",
            "relation",
            "canonical_unit",
            "checked_count",
            "maximum_positive_violation",
            "witness_indices",
            "source_refs",
        }
        assert family.checked_count > 0
        assert family.source_refs
        assert all(
            reference.startswith(
                "baselines/robust_storage_bidding/code/02_model.jl:"
            )
            for reference in family.source_refs
        )
    for family_id, count in expected_counts.items():
        assert _family(audit, family_id).checked_count == count


@pytest.mark.parametrize("count", (8, 16, 32))
def test_private_cardinality_metadata_has_exact_quadratic_growth(count: int) -> None:
    indices = build_normalized_index_sets(count)
    triangular = count * (count + 1) // 2
    strict = count * (count - 1) // 2
    relaxation = model_cardinality_metadata(indices, "relaxation")
    restriction = model_cardinality_metadata(indices, "restriction")
    exact = model_cardinality_metadata(indices, "exact")

    assert relaxation["triangular_pairs"] == triangular
    assert relaxation["strict_triangular_pairs"] == strict
    assert relaxation["lambda_triangular_variable_entries"] == 2 * triangular
    assert relaxation["common_strict_triangular_constraint_entries"] == 4 * strict
    assert relaxation["formulation_specific_strict_triangular_constraint_entries"] == 0
    assert restriction[
        "formulation_specific_strict_triangular_constraint_entries"
    ] == 2 * strict
    assert exact[
        "formulation_specific_strict_triangular_constraint_entries"
    ] == strict
    assert restriction["variables"] - relaxation["variables"] == count - 1
    assert restriction["binaries"] - relaxation["binaries"] == count - 1
    assert exact["variables"] == relaxation["variables"]
    assert exact["binaries"] == relaxation["binaries"]
    assert relaxation["quadratic_index_power"] == 2
    assert restriction["quadratic_structure_entries"] < 10 * count**2


@pytest.mark.parametrize(
    ("kind", "expected_variables", "expected_binaries", "expected_constraints"),
    (
        ("restriction", 10_301, 285, 33_643),
        ("relaxation", 10_206, 190, 24_333),
        ("exact", 10_206, 190, 28_893),
    ),
)
def test_public_k96_assembly_records_exact_cardinality_without_solving(
    kind: str,
    expected_variables: int,
    expected_binaries: int,
    expected_constraints: int,
) -> None:
    pyo = import_module("pyomo.environ")
    profile = RobustFCRFormulationProfile.for_kind(kind)
    assembled = assemble_robust_fcr_model(
        build_authored_problem(),
        profile,
        pyomo_environ=pyo,
    )

    assert assembled.handoff.cardinality == model_cardinality_metadata(
        build_normalized_index_sets(96),
        kind,
    )
    assert assembled.handoff.cardinality["variables"] == expected_variables
    assert assembled.handoff.cardinality["binaries"] == expected_binaries
    assert assembled.handoff.cardinality["active_constraints"] == expected_constraints
    assert len(assembled.constraint_handles["lower_coupling"]) == 4656
    assert len(
        assembled.constraint_handles["lambda_h_offdiag_charge_activation"]
    ) == 4560
    assert all(
        variable.value is None
        for variable in assembled.variable_handles["x0"].values()
    )
