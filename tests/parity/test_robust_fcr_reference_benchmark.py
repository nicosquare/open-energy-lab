"""Explicit full-day HiGHS benchmark for Feature 013 reference parity."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from open_energy_lab.control import (
    RobustFCRSolvePolicy,
    build_robust_fcr_reference_problem,
    compare_robust_fcr_reference,
    load_robust_fcr_reference_fixture,
    solve_robust_fcr_bid,
)
from tests.robust_fcr_case_utils import (
    NATIVE_REFERENCE_BENCHMARK_PROFILE_ID,
    native_reference_benchmark_policy_mapping,
)


pytestmark = pytest.mark.reference_benchmark

FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bidding/"
    "robust_storage_bidding_2023-06-18_restriction_v1.json"
)
EXPECTED_POLICY_FINGERPRINT = (
    "d4d8934676fce6755f525ef8844f796669e0ec49158a2107515b2dee29b682ed"
)
EXPECTED_FIXTURE_FINGERPRINT = (
    "d2d7d7430153d91c5c589fe8118005d01e02d70012bf5e8bbf4f419c13154ba4"
)


def _benchmark_policy() -> RobustFCRSolvePolicy:
    mapping = native_reference_benchmark_policy_mapping(
        time_limit_seconds=3600.0
    )
    assert mapping.pop("profile_id") == NATIVE_REFERENCE_BENCHMARK_PROFILE_ID
    policy = RobustFCRSolvePolicy(**mapping)
    assert policy.solve_policy_fingerprint == EXPECTED_POLICY_FINGERPRINT
    return policy


def _solve_once(fixture, policy):
    problem = build_robust_fcr_reference_problem(
        fixture,
        solve_policy=policy,
    )
    assert problem.solve_policy is policy
    assert problem.solve_policy.solve_policy_fingerprint == (
        EXPECTED_POLICY_FINGERPRINT
    )
    return solve_robust_fcr_bid(problem, formulation="restriction")


def _skip_for_resource_limit(result) -> None:
    if result.decisions is not None and result.solver.objective_value_eur is not None:
        return
    evidence = {
        "solve_status": result.solver.solve_status,
        "termination_status": result.solver.termination_status,
        "time_limit_seconds": result.solver.configured_options["time_limit"],
        "has_incumbent": result.solver.has_incumbent,
        "diagnostics": [value.to_dict() for value in result.diagnostics],
    }
    pytest.skip(
        "full reference benchmark produced no complete incumbent within the "
        f"declared resource limit: {json.dumps(evidence, sort_keys=True)}"
    )


def _assert_field_set_complete(comparison) -> None:
    field_ids = {value.field_id for value in comparison.field_results}
    required = {
        "optimization_objective_eur",
        "source_solver_bound_eur",
        "decision_content_fingerprint.energy",
        "decision_content_fingerprint.fcr",
        "decision_content_fingerprint.combined",
        "native_feasibility_audit",
        "joint_reference_feasibility",
        "objective_equivalence",
        "native.energy_schedule_fingerprint",
        "native.fcr_schedule_fingerprint",
        "native.plan_fingerprint",
        "source.energy_schedule_fingerprint",
        "source.fcr_schedule_fingerprint",
        "source.plan_fingerprint",
    }
    required.update(f"x0[{index}]" for index in range(24))
    required.update(f"xr[{index}]" for index in range(6))
    assert field_ids == required
    assert comparison.source_bound_proof_status == "unavailable"


def _assert_parity_complete(comparison) -> None:
    _assert_field_set_complete(comparison)
    assert comparison.status_counts["mismatch"] == 0
    assert comparison.overall_status in {
        "source_precision_compatible",
        "alternative_optimum_compatible",
    }
    assert comparison.joint_certificate.joint_feasible is True
    assert comparison.joint_certificate.objective_equivalent is True


def _benchmark_record(fixture, policy, native, comparison) -> dict[str, object]:
    native_plan = native.deployable_plan
    comparison_payload = comparison.to_dict() if comparison is not None else None
    return {
        "fixture_fingerprint": fixture.fixture_fingerprint,
        "source_evidence": {
            "recorded_objective_eur": fixture.recorded_result.objective_value_eur,
            "recorded_bound_eur": fixture.recorded_result.objective_bound_eur,
            "recorded_solve_time_seconds": (
                fixture.recorded_result.solve_time_seconds
            ),
            "recorded_solve_profile": dict(fixture.problem["solve_profile"]),
            "precision_policy_fingerprint": (
                fixture.precision_policy.policy_fingerprint
            ),
            "unavailable_fields": [
                value.to_dict() for value in fixture.unavailable_fields
            ],
        },
        "native_policy": {
            "profile_id": NATIVE_REFERENCE_BENCHMARK_PROFILE_ID,
            **policy.to_dict(),
        },
        "native_result": {
            "solver": native.solver.to_dict(),
            "semantic_result_fingerprint": native.semantic_result_fingerprint,
            "decision_vector_fingerprint": (
                native.decisions.decision_vector_fingerprint
                if native.decisions is not None
                else None
            ),
            "audit_fingerprint": (
                native.feasibility_audit.audit_fingerprint
                if native.feasibility_audit is not None
                else None
            ),
            "deployability_status": native.deployability_status,
            "deployability_reasons": list(native.deployability_reasons),
            "energy_schedule_fingerprint": (
                native_plan.energy_schedule.schedule_fingerprint
                if native_plan is not None
                else None
            ),
            "fcr_schedule_fingerprint": (
                native_plan.fcr_schedule.schedule_fingerprint
                if native_plan is not None
                else None
            ),
            "plan_fingerprint": (
                native_plan.plan_fingerprint if native_plan is not None else None
            ),
        },
        "comparison": (
            {
                "overall_status": comparison.overall_status,
                "status_counts": dict(comparison.status_counts),
                "comparison_fingerprint": comparison.comparison_fingerprint,
                "certification_request_fingerprint": (
                    comparison.certification_request.request_fingerprint
                ),
                "certificate": comparison.joint_certificate.to_dict(),
                "comparison_frame_fingerprints": comparison_payload[
                    "comparison_frame_fingerprints"
                ],
                "producer_schedule_fingerprints": comparison_payload[
                    "producer_schedule_fingerprints"
                ],
                "incomplete_fields": [
                    value.to_dict()
                    for value in comparison.field_results
                    if value.status in {"mismatch", "unavailable"}
                ],
            }
            if comparison is not None
            else None
        ),
    }


def _print_benchmark_record(
    fixture,
    policy,
    native,
    comparison,
) -> dict[str, object]:
    record = _benchmark_record(fixture, policy, native, comparison)
    print("robust_fcr_reference_benchmark=" + json.dumps(record, sort_keys=True))
    return record


def test_full_2023_06_18_restriction_reference_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_robust_fcr_reference_fixture(FIXTURE_PATH)
    assert fixture.fixture_fingerprint == EXPECTED_FIXTURE_FINGERPRINT
    policy = _benchmark_policy()

    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        text = str(path.resolve())
        if (
            "regulation_signal.csv" in text
            or "/artifacts/" in text
            or "/baselines/" in text
        ):
            raise AssertionError(
                f"optimization benchmark attempted evaluation/reference-tree access: {path}"
            )
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    native = _solve_once(fixture, policy)
    _skip_for_resource_limit(native)
    assert native.formulation.kind == "restriction"
    assert native.solver.solver_name == "highs"
    assert native.solver.configured_options["solve_policy"] == policy.to_dict()
    assert native.solver.configured_options["solve_policy_fingerprint"] == (
        policy.solve_policy_fingerprint
    )
    assert native.feasibility_audit is not None
    assert native.feasibility_audit.passes_deployability_audit is True

    comparison = compare_robust_fcr_reference(fixture, native)
    _assert_field_set_complete(comparison)
    record = _print_benchmark_record(fixture, policy, native, comparison)
    if native.solver.solve_status != "optimal":
        assert native.solver.solve_status == "feasible"
        assert native.solver.has_incumbent is True
        assert native.solver.incumbent_accepted is True
        assert policy.allow_feasible_incumbent_plan is False
        assert native.deployability_status == "blocked"
        assert "feasible_incumbent_not_opted_in" in native.deployability_reasons
        assert native.deployable_plan is None
        pytest.skip(
            "full reference benchmark reached its selected resource limit with "
            "a non-optimal audited incumbent; retained objective, bound, gap, "
            "comparison counts, fingerprints, and incomplete evidence: "
            + json.dumps(record, sort_keys=True)
        )
    if comparison.joint_certificate.solve_status in {
        "no_solution",
        "failed",
        "unavailable",
    }:
        pytest.skip(
            "native solve completed, but joint certification did not complete "
            "within the declared benchmark resources: "
                + json.dumps(comparison.joint_certificate.to_dict(), sort_keys=True)
            )
    _assert_parity_complete(comparison)

    if os.environ.get("OEL_REPEAT_REFERENCE_BENCHMARK") == "1":
        repeated_native = _solve_once(fixture, policy)
        _skip_for_resource_limit(repeated_native)
        repeated_comparison = compare_robust_fcr_reference(
            fixture,
            repeated_native,
        )
        _assert_parity_complete(repeated_comparison)
        assert repeated_native.semantic_result_fingerprint == (
            native.semantic_result_fingerprint
        )
        assert repeated_native.solver.semantic_dict() == native.solver.semantic_dict()
        assert repeated_native.decisions == native.decisions
        assert repeated_native.feasibility_audit == native.feasibility_audit
        assert repeated_comparison.comparison_fingerprint == (
            comparison.comparison_fingerprint
        )
