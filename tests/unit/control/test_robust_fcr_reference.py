"""Strict normalized-reference and interval-comparison contracts for Feature 013."""

from __future__ import annotations

from dataclasses import replace
import builtins
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest

from open_energy_lab.control.robust_fcr_bidding import _fingerprint
from open_energy_lab.control._robust_fcr_solver import RawRobustFCRSolveResult
from open_energy_lab.control.robust_fcr_bidding import (
    DEPLOYABILITY_THRESHOLD,
    RobustFCRDecisions,
    RobustFCRFormulationProfile,
    _finalize_solve_result,
)
from oel_validation.robust_fcr_reference import (
    REFERENCE_FIXTURE_SCHEMA_VERSION,
    JointReferenceCertificate,
    RobustFCRReferenceFieldResult,
    _compare_reference_numeric_field,
    _overall_reference_status,
    build_reference_certification_request,
    build_reference_decision_intervals,
    build_robust_fcr_reference_problem,
    compare_robust_fcr_reference,
    load_robust_fcr_reference_fixture,
)
from tests.robust_fcr_case_utils import native_reference_benchmark_policy_mapping


FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bidding/"
    "robust_storage_bidding_2023-06-18_restriction_v1.json"
)
REFERENCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
REFERENCE_RESULT_SHA256 = (
    "8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6"
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _native_policy(*, solver_name: str = "highs"):
    from open_energy_lab.control import RobustFCRSolvePolicy

    mapping = native_reference_benchmark_policy_mapping(time_limit_seconds=30.0)
    mapping.pop("profile_id")
    mapping["solver_name"] = solver_name
    return RobustFCRSolvePolicy(**mapping)


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


def _native_result(
    *,
    objective: float = 11.028,
    match_decisions: bool = True,
    fixture=None,
    solver_name: str = "highs",
):
    fixture = fixture or load_robust_fcr_reference_fixture(FIXTURE_PATH)
    problem = build_robust_fcr_reference_problem(
        fixture,
        solve_policy=_native_policy(solver_name=solver_name),
    )
    raw = RawRobustFCRSolveResult(
        solve_status="optimal",
        termination_status="optimal",
        has_incumbent=True,
        objective_value_eur=0.0,
        best_upper_bound_eur=0.0,
        witness=_zero_witness(),
        solver_name=f"controlled-{solver_name}",
        solver_version="13.0.2" if solver_name == "gurobi" else "1.15.1",
        pyomo_version="6.10.1",
        highspy_version=None if solver_name == "gurobi" else "1.15.1",
        configured_options={"threads": 1},
        model_cardinality={"variables": 10_301, "active_constraints": 33_643},
    )
    base = _finalize_solve_result(
        problem,
        RobustFCRFormulationProfile.for_kind("restriction"),
        raw,
    )
    source_x0 = fixture.recorded_result.rounded_x0_kw
    source_xr = fixture.recorded_result.rounded_xr_kw
    if not match_decisions:
        source_x0 = (source_x0[0] + 1.0, *source_x0[1:])
    decisions = RobustFCRDecisions(
        energy_baseline_charge_positive_kw=tuple(-value for value in source_x0),
        fcr_capacity_kw=source_xr,
    )
    solver = replace(
        base.solver,
        objective_value_eur=objective,
        best_upper_bound_eur=objective,
        absolute_gap_eur=0.0,
        relative_gap=0.0,
    )
    feasibility_audit = replace(
        base.feasibility_audit,
        passes_deployability_audit=True,
    )
    return replace(
        base,
        solver=solver,
        decisions=decisions,
        feasibility_audit=feasibility_audit,
        deployability_status="blocked",
        deployability_reasons=("controlled_reference_test",),
        deployable_plan=None,
    )


def _certificate(
    request,
    *,
    feasible: bool = True,
    objective_equivalent: bool = True,
) -> JointReferenceCertificate:
    return JointReferenceCertificate(
        request_fingerprint=request.request_fingerprint,
        solve_status="optimal" if feasible else "infeasible",
        joint_feasible=feasible,
        objective_equivalent=objective_equivalent if feasible else False,
        maximum_slack=0.0 if feasible else None,
        maximum_residual=0.0 if feasible else None,
        certified_objective_value_eur=(11.028 if feasible else None),
        witness_fingerprint=("1" * 64 if feasible else None),
        unavailable_reason=None,
    )


def test_fixture_loads_with_exact_sections_provenance_and_fingerprint() -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    payload = fixture.to_dict()

    assert fixture.schema_version == REFERENCE_FIXTURE_SCHEMA_VERSION
    assert set(payload) == {
        "schema_version",
        "fixture_id",
        "reference_provenance",
        "evaluation_fixture_reference",
        "problem",
        "reference_formulation",
        "recorded_result",
        "precision_policy",
        "unavailable_fields",
        "redistribution_status",
        "fixture_fingerprint",
    }
    provenance = payload["reference_provenance"]
    assert provenance["reference_revision"] == REFERENCE_REVISION
    assert provenance["original_result_sha256"] == REFERENCE_RESULT_SHA256
    assert provenance["original_result_byte_count"] == 6653
    assert provenance["generated_result_revision_status"] == (
        "digest_pinned_generated_file_not_tracked_at_reference_revision"
    )
    fingerprint_payload = dict(payload)
    fingerprint_payload.pop("fixture_fingerprint")
    assert fixture.fixture_fingerprint == hashlib.sha256(
        _canonical_bytes(fingerprint_payload)
    ).hexdigest()


def test_fixture_retains_exact_problem_units_signs_mappings_and_budgets() -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    problem = fixture.problem
    time = problem["time_contract"]
    battery = problem["battery"]
    uncertainty = problem["uncertainty"]
    terminal = problem["terminal_rule"]
    prices = problem["prices"]

    assert time["planning_interval_count"] == 96
    assert time["energy_interval_count"] == 24
    assert time["fcr_interval_count"] == 6
    assert time["planning_intervals_per_energy_interval"] == 4
    assert time["planning_intervals_per_fcr_block"] == 16
    assert battery["source_power_sign"] == "positive_is_discharge"
    assert battery["initial_stored_energy_kwh"] == 53.328
    assert terminal["minimum_terminal_stored_energy_kwh"] == 53.327556325823224
    assert uncertainty["recovery_activation_budget_hours"] == 0.25
    assert uncertainty["recovery_window_hours"] == 2.25
    assert uncertainty["horizon_activation_budget_hours"] == 2.75
    assert prices["day_ahead_unit"] == "EUR/kWh"
    assert prices["fcr_capacity_unit"] == "EUR/kW/4h-block"
    assert len(prices["day_ahead_energy_prices"]) == 24
    assert len(prices["fcr_capacity_prices"]) == 6


def test_fixture_records_precision_unavailable_fields_and_redistribution() -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    recorded = fixture.recorded_result
    precision = fixture.precision_policy

    assert recorded.objective_value_eur == recorded.objective_bound_eur == 11.028
    assert len(recorded.rounded_x0_kw) == 24
    assert len(recorded.rounded_xr_kw) == 6
    assert recorded.source_x0_sign == "positive_is_discharge"
    assert recorded.saved_decimal_places == 3
    assert precision.decision_half_unit_kw == 0.0005
    assert precision.objective_half_unit_eur == 0.0005
    assert precision.deployability_threshold == DEPLOYABILITY_THRESHOLD
    unavailable = {item.field_id for item in fixture.unavailable_fields}
    assert {
        "source.termination_status",
        "source.primal_status",
        "source.dual_status",
        "source.optimality_proof",
        "source.exact_optimality_gap",
        "source.unrounded_decisions",
        "source.constraint_residuals",
        "source.solver_tolerances",
        "source.actual_solver_versions",
        "source.restriction_bilinear_evidence",
    } <= unavailable
    assert fixture.redistribution_status == {
        "activation_data": "absent_external_evaluation_only",
        "normalized_problem_and_result": "committed_derived_evidence",
        "original_result": "digest_only",
    }


def test_fixture_contains_no_invented_native_or_source_tolerances() -> None:
    payload = _fixture_payload()

    def keys(value: object):
        if isinstance(value, dict):
            for key, inner in value.items():
                yield key
                yield from keys(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from keys(inner)

    all_keys = set(keys(payload))
    assert "native_solve_policy" not in all_keys
    assert "objective_comparison_absolute_tolerance_eur" not in all_keys
    assert "objective_comparison_relative_tolerance" not in all_keys
    assert "primal_feasibility_tolerance" not in all_keys
    assert "dual_feasibility_tolerance" not in all_keys
    assert payload["problem"]["solve_profile"]["explicit_tolerances_status"] == (
        "not_recorded_source_defaults"
    )


def test_fixture_loader_rejects_unknown_fields_tampering_and_native_policy(
    tmp_path: Path,
) -> None:
    payload = _fixture_payload()
    payload["unexpected"] = True
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exact section set|unexpected"):
        load_robust_fcr_reference_fixture(unknown)

    payload = _fixture_payload()
    payload["problem"]["terminal_rule"]["minimum_terminal_stored_energy_kwh"] = 53.328
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="terminal|fingerprint"):
        load_robust_fcr_reference_fixture(tampered)

    payload = _fixture_payload()
    payload["problem"]["solve_profile"]["primal_feasibility_tolerance"] = 1e-6
    invented = tmp_path / "invented.json"
    invented.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="solve_profile|tolerance"):
        load_robust_fcr_reference_fixture(invented)


def test_fixture_loader_reads_only_the_explicit_selected_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "fixture.json"
    selected.write_bytes(FIXTURE_PATH.read_bytes())
    original = Path.read_bytes
    reads: list[Path] = []

    def guarded(path: Path) -> bytes:
        resolved = path.resolve()
        reads.append(resolved)
        assert resolved == selected.resolve()
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    fixture = load_robust_fcr_reference_fixture(selected)
    assert fixture.fixture_id == "robust-storage-bidding-2023-06-18-restriction-v1"
    assert reads == [selected.resolve()]


def test_routine_reference_path_is_guarded_offline_and_local_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "selected-reference-fixture.json"
    selected.write_bytes(FIXTURE_PATH.read_bytes())
    original_read_bytes = Path.read_bytes
    original_open = Path.open
    allowed_path = selected.resolve()
    reads: list[Path] = []

    def guarded_read_bytes(path: Path) -> bytes:
        resolved = path.resolve()
        reads.append(resolved)
        if resolved != allowed_path:
            raise AssertionError(f"unexpected routine reference read: {resolved}")
        return original_read_bytes(path)

    def guarded_open(path: Path, *args, **kwargs):
        resolved = path.resolve()
        if resolved != allowed_path:
            raise AssertionError(f"unexpected routine reference open: {resolved}")
        return original_open(path, *args, **kwargs)

    def forbidden(action: str):
        def fail(*args, **kwargs):
            raise AssertionError(f"routine reference path attempted {action}")

        return fail

    class GuardedEnvironment(dict):
        def __getitem__(self, key):
            raise AssertionError(f"routine reference path read environment key {key}")

        def get(self, key, default=None):
            raise AssertionError(f"routine reference path inspected environment key {key}")

        def __contains__(self, key):
            raise AssertionError(f"routine reference path tested environment key {key}")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "gurobipy" or name.startswith("gurobipy."):
            raise AssertionError("routine reference path attempted Gurobi access")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", forbidden("socket creation"))
    monkeypatch.setattr(
        socket,
        "create_connection",
        forbidden("network connection"),
    )
    monkeypatch.setattr(subprocess, "run", forbidden("subprocess execution"))
    monkeypatch.setattr(subprocess, "Popen", forbidden("subprocess execution"))
    monkeypatch.setattr(os, "getenv", forbidden("environment inspection"))
    monkeypatch.setattr(os, "environ", GuardedEnvironment())
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    fixture = load_robust_fcr_reference_fixture(selected)
    problem = build_robust_fcr_reference_problem(
        fixture,
        solve_policy=_native_policy(),
    )
    native = _native_result(fixture=fixture)
    request = build_reference_certification_request(fixture, native)
    monkeypatch.setattr(
        "oel_validation.robust_fcr_reference._certify_reference_decision_box",
        lambda fixture, native_result, request: _certificate(request),
    )
    comparison = compare_robust_fcr_reference(fixture, native)

    assert problem.producer_input_fingerprints["reference_fixture"] == (
        fixture.fixture_fingerprint
    )
    assert comparison.status_counts["mismatch"] == 0
    assert request.fixture_fingerprint == fixture.fixture_fingerprint
    assert reads == [allowed_path]


def test_reference_problem_requires_a_separate_complete_native_policy() -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    policy = _native_policy()
    problem = build_robust_fcr_reference_problem(fixture, solve_policy=policy)

    assert problem.solve_policy is policy
    assert problem.battery.initial_stored_energy_kwh == 53.328
    assert problem.terminal_rule.minimum_terminal_stored_energy_kwh == (
        53.327556325823224
    )
    assert problem.uncertainty.horizon_wide.horizon_activation_budget_hours == 2.75
    assert problem.producer_input_fingerprints["reference_fixture"] == (
        fixture.fixture_fingerprint
    )
    with pytest.raises((TypeError, ValueError), match="solve_policy"):
        build_robust_fcr_reference_problem(fixture, solve_policy=None)


@pytest.mark.parametrize(
    ("native", "source", "half_unit", "source_exact", "status"),
    (
        (1.0, 1.0, 0.0, True, "exact"),
        (1.0004, 1.0, 0.0005, False, "source_precision_compatible"),
        (1.001, 1.0, 0.0005, False, "mismatch"),
    ),
)
def test_numeric_field_comparison_distinguishes_exact_precision_and_mismatch(
    native: float,
    source: float,
    half_unit: float,
    source_exact: bool,
    status: str,
) -> None:
    result = _compare_reference_numeric_field(
        field_id="test.value",
        native_value=native,
        source_value=source,
        source_half_unit=half_unit,
        source_exact=source_exact,
        alternative_optimum_compatible=False,
        source_evidence_role="recorded_value",
    )
    assert isinstance(result, RobustFCRReferenceFieldResult)
    assert result.status == status
    assert result.delta == pytest.approx(native - source)
    assert result.source_interval == (source - half_unit, source + half_unit)


def test_numeric_field_comparison_reports_alternative_and_unavailable() -> None:
    alternative = _compare_reference_numeric_field(
        field_id="test.value",
        native_value=2.0,
        source_value=1.0,
        source_half_unit=0.0005,
        source_exact=False,
        alternative_optimum_compatible=True,
        source_evidence_role="rounded_decision",
    )
    unavailable = _compare_reference_numeric_field(
        field_id="test.missing",
        native_value=2.0,
        source_value=None,
        source_half_unit=None,
        source_exact=False,
        alternative_optimum_compatible=False,
        source_evidence_role="not_recorded",
        unavailable_reason="source did not record the field",
    )
    assert alternative.status == "alternative_optimum_compatible"
    assert alternative.delta == 1.0
    assert unavailable.status == "unavailable"
    assert unavailable.delta is None
    assert unavailable.reason == "source did not record the field"


def test_reference_status_precedence_is_explicit() -> None:
    assert _overall_reference_status(("exact", "exact")) == "exact"
    assert _overall_reference_status(("exact", "unavailable")) == "unavailable"
    assert _overall_reference_status(
        ("exact", "source_precision_compatible", "unavailable")
    ) == "source_precision_compatible"
    assert _overall_reference_status(
        ("source_precision_compatible", "alternative_optimum_compatible")
    ) == "alternative_optimum_compatible"
    assert _overall_reference_status(("exact", "mismatch")) == "mismatch"


def test_decision_intervals_are_joint_closed_and_reserve_nonnegative() -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    intervals = build_reference_decision_intervals(fixture)

    assert len(intervals) == 30
    assert [item.index for item in intervals[:24]] == list(range(24))
    assert [item.index for item in intervals[24:]] == list(range(6))
    assert all(item.interval_closure == "closed_outer" for item in intervals)
    assert intervals[0].lower == pytest.approx(
        fixture.recorded_result.rounded_x0_kw[0] - 0.0005
    )
    zero_reserve_fixture = replace(
        fixture,
        recorded_result=replace(
            fixture.recorded_result,
            rounded_xr_kw=(0.0, *fixture.recorded_result.rounded_xr_kw[1:]),
        ),
    )
    zero_interval = build_reference_decision_intervals(zero_reserve_fixture)[24]
    assert zero_interval.lower == 0.0
    assert zero_interval.upper == 0.0005


def test_certification_request_uses_fixed_native_band_and_interval_intersection() -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    native = _native_result(objective=11.028)
    request = build_reference_certification_request(fixture, native)

    assert len(request.decision_intervals) == 30
    assert request.source_objective_interval == (11.0275, 11.0285)
    assert request.objective_comparison_allowance_eur == pytest.approx(1e-6)
    assert request.native_objective_equivalence_band == pytest.approx(
        (11.027999, 11.028001)
    )
    assert request.certification_objective_interval == pytest.approx(
        (11.027999, 11.028001)
    )
    assert request.maximum_deployability_slack == DEPLOYABILITY_THRESHOLD


def test_certification_request_scales_relative_allowance_from_both_endpoints() -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    native = _native_result(objective=1_000_000_000.0)
    request = build_reference_certification_request(fixture, native)

    assert request.objective_comparison_allowance_eur == pytest.approx(1.0)
    assert request.native_objective_equivalence_band == pytest.approx(
        (999_999_999.0, 1_000_000_001.0)
    )
    assert request.certification_objective_interval is None
    assert request.objective_equivalence_possible is False


def test_joint_certification_model_adds_one_simultaneous_box_and_slack_caps() -> None:
    import pyomo.environ as pyo

    from open_energy_lab.control._robust_fcr_formulation import (
        assemble_robust_fcr_reference_certificate,
    )

    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    native = _native_result()
    request = build_reference_certification_request(fixture, native)
    problem = build_robust_fcr_reference_problem(
        fixture,
        solve_policy=_native_policy(),
    )
    assembled = assemble_robust_fcr_reference_certificate(
        problem,
        request,
        pyomo_environ=pyo,
    )

    assert assembled.handoff.cardinality["reference_decision_box_constraints"] == 60
    assert assembled.handoff.cardinality["reference_objective_box_constraints"] == 2
    assert assembled.handoff.cardinality["reference_slack_bound_constraints"] == 194
    assert assembled.handoff.cardinality["reference_certification_constraints"] == 256
    assert len(assembled.constraint_handles["reference_decision_box"]) == 60
    assert len(assembled.constraint_handles["reference_objective_box"]) == 2
    assert len(assembled.constraint_handles["reference_slack_bounds"]) == 194
    assert assembled.handoff.cardinality["active_constraints"] == 33_899


def test_joint_certificate_rejects_false_feasibility_evidence() -> None:
    request = build_reference_certification_request(
        load_robust_fcr_reference_fixture(FIXTURE_PATH),
        _native_result(),
    )
    with pytest.raises(ValueError, match="deployability slack"):
        JointReferenceCertificate(
            request_fingerprint=request.request_fingerprint,
            solve_status="optimal",
            joint_feasible=True,
            objective_equivalent=True,
            maximum_slack=DEPLOYABILITY_THRESHOLD * 2,
            maximum_residual=0.0,
            certified_objective_value_eur=11.028,
            witness_fingerprint="1" * 64,
            unavailable_reason=None,
        )
    infeasible = _certificate(request, feasible=False)
    assert infeasible.joint_feasible is False
    assert infeasible.objective_equivalent is False
    assert infeasible.maximum_slack is None


def test_joint_certificate_reuses_audited_native_witness_inside_source_box() -> None:
    from oel_validation.robust_fcr_reference import (
        _certify_reference_decision_box,
    )

    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    native = _native_result(objective=11.028269482283491, solver_name="gurobi")
    clean_audit = replace(
        native.feasibility_audit,
        constraint_families=tuple(
            replace(
                family,
                maximum_positive_violation=0.0,
                witness_indices=(),
            )
            for family in native.feasibility_audit.constraint_families
        ),
        modeled_slacks={
            name: 0.0 for name in native.feasibility_audit.modeled_slacks
        },
        passes_deployability_audit=True,
    )
    native = replace(native, feasibility_audit=clean_audit)
    request = build_reference_certification_request(fixture, native)
    certificate = _certify_reference_decision_box(fixture, native, request)

    assert certificate.solve_status == "optimal"
    assert certificate.joint_feasible is True
    assert certificate.objective_equivalent is True
    assert certificate.certified_objective_value_eur == pytest.approx(
        11.028269482283491
    )
    assert certificate.maximum_slack == 0.0
    assert certificate.maximum_residual == 0.0
    assert certificate.witness_fingerprint == _fingerprint(native.decisions.to_dict())


def test_joint_certificate_keeps_independent_highs_backend_for_gurobi_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_energy_lab.control import _robust_fcr_formulation, _robust_fcr_solver
    from oel_validation.robust_fcr_reference import (
        _certify_reference_decision_box,
    )

    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    native = _native_result(
        objective=11.028269,
        match_decisions=False,
        solver_name="gurobi",
    )
    request = build_reference_certification_request(fixture, native)
    assembled_sentinel = object()
    backend = SimpleNamespace(pyomo_environ=object())

    monkeypatch.setattr(
        _robust_fcr_solver,
        "require_highs_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        _robust_fcr_formulation,
        "assemble_robust_fcr_reference_certificate",
        lambda problem, request, pyomo_environ: assembled_sentinel,
    )

    def observe_dispatch(assembled, policy, *, backend):
        assert assembled is assembled_sentinel
        assert policy.solver_name == "highs"
        raise RuntimeError("certificate HiGHS dispatch observed")

    monkeypatch.setattr(
        _robust_fcr_solver,
        "solve_assembled_model",
        observe_dispatch,
    )
    certificate = _certify_reference_decision_box(fixture, native, request)

    assert certificate.solve_status == "unavailable"
    assert "certificate HiGHS dispatch observed" in certificate.unavailable_reason


def test_public_comparison_reports_precision_alternative_and_source_bound_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    matching = _native_result()
    request = build_reference_certification_request(fixture, matching)
    monkeypatch.setattr(
        "oel_validation.robust_fcr_reference._certify_reference_decision_box",
        lambda fixture, native_result, request: _certificate(request),
    )
    precision = compare_robust_fcr_reference(fixture, matching)
    assert precision.overall_status == "source_precision_compatible"
    assert precision.source_bound_proof_status == "unavailable"
    assert precision.status_counts["mismatch"] == 0
    assert len([item for item in precision.field_results if item.field_id.startswith("x0[")]) == 24
    assert len([item for item in precision.field_results if item.field_id.startswith("xr[")]) == 6

    different = _native_result(match_decisions=False)
    alternative_request = build_reference_certification_request(fixture, different)
    monkeypatch.setattr(
        "oel_validation.robust_fcr_reference._certify_reference_decision_box",
        lambda fixture, native_result, request: _certificate(request),
    )
    alternative = compare_robust_fcr_reference(fixture, different)
    assert alternative.overall_status == "alternative_optimum_compatible"
    changed = next(item for item in alternative.field_results if item.field_id == "x0[0]")
    assert changed.status == "alternative_optimum_compatible"
    assert changed.delta == pytest.approx(1.0)
    assert alternative_request.objective_equivalence_possible is True


def test_public_comparison_reports_mismatch_when_joint_certificate_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    native = _native_result(match_decisions=False)
    monkeypatch.setattr(
        "oel_validation.robust_fcr_reference._certify_reference_decision_box",
        lambda fixture, native_result, request: _certificate(
            request,
            feasible=False,
        ),
    )
    comparison = compare_robust_fcr_reference(fixture, native)
    assert comparison.overall_status == "mismatch"
    assert comparison.status_counts["mismatch"] > 0
    assert comparison.joint_certificate.joint_feasible is False


def test_result_certificate_and_comparison_fingerprints_exclude_runtime_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    first_native = _native_result(fixture=fixture)
    second_native = replace(
        first_native,
        runtime_metadata={
            "runtime_seconds": 999.0,
            "backend": {
                "temporary_log": "/different/machine/highs.log",
                "temporary_path": "/different/machine/tmp",
            },
        },
    )
    assert first_native.semantic_result_fingerprint == (
        second_native.semantic_result_fingerprint
    )

    monkeypatch.setattr(
        "oel_validation.robust_fcr_reference._certify_reference_decision_box",
        lambda fixture, native_result, request: _certificate(request),
    )
    first = compare_robust_fcr_reference(fixture, first_native)
    second = compare_robust_fcr_reference(fixture, second_native)

    assert first.certification_request.request_fingerprint == (
        second.certification_request.request_fingerprint
    )
    assert first.joint_certificate.certificate_fingerprint == (
        second.joint_certificate.certificate_fingerprint
    )
    assert first.field_results == second.field_results
    assert first.comparison_fingerprint == second.comparison_fingerprint
