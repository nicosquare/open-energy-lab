"""Run the explicit full-day Feature 013 reference benchmark offline."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from pathlib import Path

from open_energy_lab.core.serialization import fingerprint
from open_energy_lab.control import (
    RobustFCRSolvePolicy,
    solve_robust_fcr_bid,
)
from oel_validation.robust_fcr_reference import (
    build_robust_fcr_reference_problem,
    compare_robust_fcr_reference,
    load_robust_fcr_reference_fixture,
)


PROFILE_IDS = {
    "highs": "native-reference-benchmark-highs-v1",
    "gurobi": "native-reference-benchmark-gurobi-v1",
}


def _policy(solver_name: str, time_limit_seconds: float) -> RobustFCRSolvePolicy:
    return RobustFCRSolvePolicy(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds,
        threads=1,
        random_seed=13,
        primal_feasibility_tolerance=1e-7,
        dual_feasibility_tolerance=1e-7,
        mip_feasibility_tolerance=1e-6,
        relative_mip_gap=1e-6,
        objective_comparison_absolute_tolerance_eur=1e-6,
        objective_comparison_relative_tolerance=1e-9,
        allow_feasible_incumbent_plan=False,
        decision_canonicalization_id="solver-output-kw-1e-9-half-even-v1",
    )


def _print_json(label: str, payload: object) -> None:
    print(f"\n{label}")
    print(json.dumps(_json_value(payload), indent=2, sort_keys=True))


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(inner) for key, inner in value.items()}
    if isinstance(value, tuple):
        return [_json_value(inner) for inner in value]
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument(
        "--solver",
        choices=tuple(PROFILE_IDS),
        default="highs",
        help="explicit native backend; Gurobi requires the optional extra and license",
    )
    parser.add_argument(
        "--time-limit-seconds",
        type=float,
        default=3600.0,
        help="explicit native solver limit; the source fixture owns no native policy",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    fixture = load_robust_fcr_reference_fixture(args.fixture)
    policy = _policy(args.solver, args.time_limit_seconds)
    problem = build_robust_fcr_reference_problem(
        fixture,
        solve_policy=policy,
    )

    _print_json(
        "Native benchmark policy (caller-owned, not Julia evidence)",
        {"profile_id": PROFILE_IDS[args.solver], **policy.to_dict()},
    )
    _print_json(
        "Normalized source evidence",
        {
            "fixture_id": fixture.fixture_id,
            "fixture_fingerprint": fixture.fixture_fingerprint,
            "source_revision": fixture.reference_provenance["reference_revision"],
            "source_result_sha256": fixture.reference_provenance[
                "original_result_sha256"
            ],
            "source_solve_profile": fixture.problem["solve_profile"],
            "source_unavailable_fields": [
                value.to_dict() for value in fixture.unavailable_fields
            ],
        },
    )
    _print_json(
        "Native problem identity",
        {
            "problem_fingerprint": problem.problem_fingerprint,
            "comparison_problem_fingerprint": fingerprint(problem.comparison_dict()),
            "solve_policy_fingerprint": fingerprint(policy.to_dict()),
        },
    )

    result = solve_robust_fcr_bid(problem, formulation="restriction")
    _print_json(
        "Native restriction result",
        {
            "solver": result.solver.to_dict(),
            "deployability_status": result.deployability_status,
            "deployability_reasons": list(result.deployability_reasons),
            "objective_breakdown": (
                result.raw_objective.to_dict()
                if result.raw_objective is not None
                else None
            ),
            "decisions": (
                result.decisions.to_dict() if result.decisions is not None else None
            ),
            "feasibility_audit": (
                result.feasibility_audit.to_dict()
                if result.feasibility_audit is not None
                else None
            ),
            "semantic_result_fingerprint": result.semantic_result_fingerprint,
            "runtime_metadata": result.runtime_metadata,
        },
    )
    if result.decisions is None or result.solver.objective_value_eur is None:
        _print_json(
            "Reference comparison unavailable",
            {
                "reason": "native solve produced no complete incumbent",
                "solve_status": result.solver.solve_status,
                "termination_status": result.solver.termination_status,
                "configured_time_limit_seconds": args.time_limit_seconds,
            },
        )
        return 2

    comparison = compare_robust_fcr_reference(fixture, result)
    request = comparison.certification_request
    _print_json(
        "Fixed objective comparison envelope",
        {
            "source_objective_interval_eur": request.source_objective_interval,
            "native_objective_equivalence_band_eur": (
                request.native_objective_equivalence_band
            ),
            "certification_objective_interval_eur": (
                request.certification_objective_interval
            ),
            "native_allowance_eur": request.objective_comparison_allowance_eur,
            "native_policy_fingerprint": request.native_policy_fingerprint,
            "source_precision_policy_fingerprint": (
                fixture.precision_policy.policy_fingerprint
            ),
            "request_fingerprint": request.request_fingerprint,
        },
    )
    print("\nField comparison")
    print("field_id\tstatus\tnative\tsource\tdelta\tsource_interval")
    for field in comparison.field_results:
        print(
            "\t".join(
                (
                    field.field_id,
                    field.status,
                    json.dumps(field.native_value, sort_keys=True),
                    json.dumps(field.source_value, sort_keys=True),
                    json.dumps(field.delta),
                    json.dumps(field.source_interval),
                )
            )
        )
    _print_json(
        "Reference comparison summary",
        {
            "overall_status": comparison.overall_status,
            "status_counts": comparison.status_counts,
            "source_bound_proof_status": comparison.source_bound_proof_status,
            "comparison_frame_fingerprints": (
                comparison.comparison_frame_fingerprints
            ),
            "producer_schedule_fingerprints": (
                comparison.producer_schedule_fingerprints
            ),
            "joint_certificate": comparison.joint_certificate.to_dict(),
            "comparison_fingerprint": comparison.comparison_fingerprint,
        },
    )
    return 0 if comparison.status_counts["mismatch"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
