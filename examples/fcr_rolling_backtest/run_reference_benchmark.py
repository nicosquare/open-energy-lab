"""Run explicit Feature 015 bounded and full-history research workflows."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from open_energy_lab.control import (
    RollingFCRStudyResult,
    RollingFCRValidationError,
    compare_rolling_fcr_reference,
    load_rolling_fcr_reference_fixture,
    load_rolling_fcr_study_result,
    run_rolling_fcr_study,
)

try:
    from examples.fcr_rolling_backtest.study_inputs import (
        BOUNDED_DATES,
        PROFILE_IDS,
        build_day_inputs,
        build_explicit_activation_traces,
        build_explicit_day_inputs,
        build_explicit_manifest,
        build_manifest,
        build_solve_policy,
        fingerprint,
    )
except ModuleNotFoundError as exc:  # Direct ``python path/to/script.py`` execution.
    if exc.name != "examples":
        raise
    from study_inputs import (  # type: ignore[no-redef]
        BOUNDED_DATES,
        PROFILE_IDS,
        build_day_inputs,
        build_explicit_activation_traces,
        build_explicit_day_inputs,
        build_explicit_manifest,
        build_manifest,
        build_solve_policy,
        fingerprint,
    )


BENCHMARK_REPORT_SCHEMA_VERSION = "fcr-rolling-reference-benchmark-report-v1"
FULL_HISTORY_REQUEST_SCHEMA_VERSION = "fcr-rolling-full-history-request-v1"
FULL_HISTORY_FIRST_DATE = date(2020, 7, 1)
FULL_HISTORY_LAST_DATE = date(2024, 6, 30)
FULL_HISTORY_DATE_COUNT = 1453
FULL_HISTORY_SOURCE_DATE_LIST_SHA256 = (
    "6b2412144996135507ea85a73f51b7819897a1f98ae767df4396d18a9605ba51"
)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO delivery date: {value}") from exc


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run an explicitly selected bounded normalized-reference benchmark "
            "or a caller-authored full-history research request."
        )
    )
    parser.add_argument("--fixture", type=Path)
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=("all", *PROFILE_IDS),
        default=("all",),
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        type=_parse_date,
        default=BOUNDED_DATES,
    )
    parser.add_argument("--solver", choices=("highs", "gurobi"), default="highs")
    parser.add_argument("--time-limit-seconds", type=float, default=900.0)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--study-manifest",
        type=Path,
        help="Explicit research-only full-history request JSON.",
    )
    parser.add_argument(
        "--resume-output",
        type=Path,
        help="Full-history checkpoint/result path owned by the caller.",
    )
    return parser.parse_args(argv)


def _selected_profiles(values: Sequence[str]) -> tuple[str, ...]:
    selected = tuple(values)
    if "all" in selected:
        if selected != ("all",):
            raise RollingFCRValidationError("profiles all cannot be combined")
        return PROFILE_IDS
    if not selected or len(set(selected)) != len(selected):
        raise RollingFCRValidationError("profiles must be nonempty and unique")
    return selected


def _validate_bounded_dates(values: Sequence[date]) -> tuple[date, ...]:
    dates = tuple(values)
    if not dates or dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
        raise RollingFCRValidationError(
            "benchmark dates must be a nonempty ordered unique sequence"
        )
    if any(item not in BOUNDED_DATES for item in dates):
        raise RollingFCRValidationError(
            "benchmark dates must lie within 2023-06-17 through 2023-06-20"
        )
    return dates


def _gurobi_backend_evidence() -> dict[str, object]:
    from open_energy_lab.control._robust_fcr_solver import (
        load_optional_gurobi_backend,
    )

    backend, reason = load_optional_gurobi_backend()
    if backend is None:
        return {
            "status": "unavailable",
            "reason": reason or "optional Gurobi backend is unavailable",
            "fallback_attempted": False,
        }
    return {
        "status": "available",
        "solver_name": "gurobi",
        "solver_version": backend.gurobi_version,
        "pyomo_version": backend.pyomo_version,
        "fallback_attempted": False,
    }


def _unavailable_profile_report(
    profile_id: str,
    *,
    reason: str,
) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "status": "unavailable",
        "reason_codes": (reason,),
        "manifest": None,
        "result": None,
        "comparison": None,
        "native_record_count": 0,
        "source_comparison_outcome_counts": {},
    }


def _completed_profile_report(
    *,
    manifest: object,
    result: RollingFCRStudyResult,
    comparison: object,
) -> dict[str, object]:
    outcomes = Counter(item.outcome for item in comparison.field_results)
    source_time_limit_dates = tuple(
        item.delivery_date.isoformat()
        for item in comparison.field_results
        if item.category == "termination"
        and item.source_displayed_value == "TIME_LIMIT"
    )
    return {
        "profile_id": manifest.profile.profile_id,
        "status": "completed",
        "manifest": manifest.to_dict(),
        "result": result.to_dict(),
        "comparison": comparison.to_dict(),
        "native_record_count": len(result.records),
        "native_status_counts": dict(result.status_counts),
        "native_semantic_fingerprint": result.semantic_fingerprint,
        "source_comparison_outcome_counts": dict(sorted(outcomes.items())),
        "source_time_limit_dates": sorted(set(source_time_limit_dates)),
        "overall_compatibility": comparison.overall_compatibility,
        "comparison_fingerprint": comparison.comparison_fingerprint,
    }


def run_bounded_reference_benchmark(
    *,
    fixture_path: Path,
    profile_ids: Sequence[str] = PROFILE_IDS,
    dates: Sequence[date] = BOUNDED_DATES,
    solver_name: str = "highs",
    time_limit_seconds: float = 900.0,
) -> dict[str, object]:
    selected_profiles = tuple(profile_ids)
    if not selected_profiles or any(item not in PROFILE_IDS for item in selected_profiles):
        raise RollingFCRValidationError("benchmark profiles must use known identities")
    if len(set(selected_profiles)) != len(selected_profiles):
        raise RollingFCRValidationError("benchmark profiles must be unique")
    selected_dates = _validate_bounded_dates(dates)
    if PROFILE_IDS[3] in selected_profiles and selected_dates != BOUNDED_DATES:
        raise RollingFCRValidationError(
            "the 08:00 reference benchmark requires all four bounded dates so "
            "initialization and close-out roles remain authoritative"
        )
    if solver_name not in {"highs", "gurobi"}:
        raise RollingFCRValidationError("benchmark solver must be highs or gurobi")
    fixture = load_rolling_fcr_reference_fixture(fixture_path)
    backend_evidence: dict[str, object] = {
        "status": "required",
        "solver_name": "highs",
        "fallback_attempted": False,
    }
    if solver_name == "gurobi":
        backend_evidence = _gurobi_backend_evidence()
        if backend_evidence["status"] == "unavailable":
            return {
                "schema_version": BENCHMARK_REPORT_SCHEMA_VERSION,
                "execution_mode": "explicit_bounded_reference_benchmark",
                "fixture_fingerprint": fixture.fixture_fingerprint,
                "reference_revision": (
                    fixture.reference_provenance.reference_revision
                ),
                "solver_request": solver_name,
                "backend_evidence": backend_evidence,
                "profile_order": list(selected_profiles),
                "ordered_dates": [item.isoformat() for item in selected_dates],
                "profiles": [
                    _unavailable_profile_report(
                        profile_id,
                        reason="optional_gurobi_backend_unavailable",
                    )
                    for profile_id in selected_profiles
                ],
                "evidence_limits": _benchmark_evidence_limits(),
            }
    policy = build_solve_policy(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds,
        allow_feasible_incumbent_plan=True,
    )
    reports = []
    for profile_id in selected_profiles:
        if solver_name == "gurobi" and profile_id in {
            PROFILE_IDS[2],
            PROFILE_IDS[3],
        }:
            reports.append(
                _unavailable_profile_report(
                    profile_id,
                    reason="optional_gurobi_rolling_adapter_not_implemented",
                )
            )
            continue
        manifest = build_manifest(
            profile_id,
            dates=selected_dates,
            state_carry_policy="source_three_decimal",
            solve_policy=policy,
            reference_fixture=fixture,
        )
        inputs = build_day_inputs(manifest, reference_fixture=fixture)
        result = run_rolling_fcr_study(manifest, inputs)
        comparison = compare_rolling_fcr_reference(
            manifest=manifest,
            result=result,
            fixture=fixture,
        )
        reports.append(
            _completed_profile_report(
                manifest=manifest,
                result=result,
                comparison=comparison,
            )
        )
    return {
        "schema_version": BENCHMARK_REPORT_SCHEMA_VERSION,
        "execution_mode": "explicit_bounded_reference_benchmark",
        "fixture_fingerprint": fixture.fixture_fingerprint,
        "reference_revision": fixture.reference_provenance.reference_revision,
        "solver_request": solver_name,
        "backend_evidence": backend_evidence,
        "profile_order": list(selected_profiles),
        "ordered_dates": [item.isoformat() for item in selected_dates],
        "profiles": reports,
        "evidence_limits": _benchmark_evidence_limits(),
    }


def _benchmark_evidence_limits() -> list[str]:
    return [
        "bounded generated rerun evidence does not establish Table A1 parity",
        "source time-limit records are feasible incumbents with bounds, not proven optima",
        "three-decimal source decisions require closed precision intervals and joint audits",
        "exact 08:00 restart parity is unavailable without hidden full-precision fixings",
        "activation-dependent replay remains unavailable unless supplied explicitly",
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RollingFCRValidationError(
            f"unable to read explicit full-history data bundle: {type(exc).__name__}"
        ) from exc
    return digest.hexdigest()


def _load_full_history_request(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RollingFCRValidationError(
            f"unable to load full-history request: {type(exc).__name__}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise RollingFCRValidationError("full-history request must be a mapping")
    required = {
        "schema_version",
        "research_only",
        "release_gate",
        "profile_id",
        "state_carry_policy",
        "ordered_dates",
        "excluded_dates",
        "source_date_list_sha256",
        "acceptance_policy",
        "data_bundle",
        "request_fingerprint",
    }
    if set(payload) != required:
        raise RollingFCRValidationError(
            "full-history request keys differ from the v1 research contract"
        )
    if payload["schema_version"] != FULL_HISTORY_REQUEST_SCHEMA_VERSION:
        raise RollingFCRValidationError("unsupported full-history request schema")
    if payload["research_only"] is not True or payload["release_gate"] is not False:
        raise RollingFCRValidationError(
            "full-history execution must be research-only and non-release-gating"
        )
    if payload["profile_id"] not in PROFILE_IDS:
        raise RollingFCRValidationError("full-history profile is unsupported")
    if payload["state_carry_policy"] not in {
        "source_three_decimal",
        "native_full_precision",
    }:
        raise RollingFCRValidationError("full-history carry policy is unsupported")
    if payload["source_date_list_sha256"] != FULL_HISTORY_SOURCE_DATE_LIST_SHA256:
        raise RollingFCRValidationError(
            "full-history request does not pin the authoritative source date list"
        )
    ordered_raw = payload["ordered_dates"]
    excluded_raw = payload["excluded_dates"]
    if not isinstance(ordered_raw, list) or not isinstance(excluded_raw, list):
        raise RollingFCRValidationError("full-history date fields must be lists")
    try:
        ordered = tuple(date.fromisoformat(str(item)) for item in ordered_raw)
        excluded = tuple(date.fromisoformat(str(item)) for item in excluded_raw)
    except ValueError as exc:
        raise RollingFCRValidationError("full-history date text is invalid") from exc
    if (
        len(ordered) != FULL_HISTORY_DATE_COUNT
        or ordered[0] != FULL_HISTORY_FIRST_DATE
        or ordered[-1] != FULL_HISTORY_LAST_DATE
        or ordered != tuple(sorted(ordered))
        or len(set(ordered)) != len(ordered)
    ):
        raise RollingFCRValidationError(
            "full-history dates must be the immutable 1,453-date ordered source list"
        )
    if (
        excluded != tuple(sorted(excluded))
        or len(excluded) != 8
        or any(item in ordered for item in excluded)
        or len(set(excluded)) != len(excluded)
    ):
        raise RollingFCRValidationError(
            "the eight excluded DST dates must be ordered, unique, and absent"
        )
    calendar_dates = tuple(
        FULL_HISTORY_FIRST_DATE.fromordinal(ordinal)
        for ordinal in range(
            FULL_HISTORY_FIRST_DATE.toordinal(),
            FULL_HISTORY_LAST_DATE.toordinal() + 1,
        )
    )
    if tuple(item for item in calendar_dates if item not in set(excluded)) != ordered:
        raise RollingFCRValidationError(
            "full-history ordering must equal the complete range minus declared DST dates"
        )
    acceptance = payload["acceptance_policy"]
    if not isinstance(acceptance, Mapping) or acceptance.get("kind") not in {
        "assumed_accepted",
        "evidence_backed_accepted",
    }:
        raise RollingFCRValidationError(
            "full-history request requires an explicit accepted-bid policy"
        )
    bundle = payload["data_bundle"]
    if not isinstance(bundle, Mapping) or set(bundle) != {"path", "sha256"}:
        raise RollingFCRValidationError(
            "full-history data_bundle requires explicit path and SHA-256"
        )
    bundle_path = Path(str(bundle["path"]))
    declared_digest = str(bundle["sha256"])
    if len(declared_digest) != 64 or any(
        value not in "0123456789abcdef" for value in declared_digest
    ):
        raise RollingFCRValidationError("full-history bundle SHA-256 is invalid")
    if _sha256_file(bundle_path) != declared_digest:
        raise RollingFCRValidationError("full-history data bundle digest differs")
    semantic = {
        key: value for key, value in payload.items() if key != "request_fingerprint"
    }
    semantic["data_bundle"] = {"sha256": declared_digest}
    if payload["request_fingerprint"] != fingerprint(semantic):
        raise RollingFCRValidationError("full-history request fingerprint differs")
    return {
        **payload,
        "ordered_dates_parsed": ordered,
        "excluded_dates_parsed": excluded,
        "data_bundle_path": bundle_path,
    }


def run_full_history_request(
    request_path: Path,
    *,
    resume_output: Path | None,
    solver_name: str = "highs",
    time_limit_seconds: float = 900.0,
) -> dict[str, object]:
    request = _load_full_history_request(request_path)
    bundle_path = request["data_bundle_path"]
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RollingFCRValidationError(
            f"unable to parse full-history data bundle: {type(exc).__name__}"
        ) from exc
    if not isinstance(bundle, Mapping):
        raise RollingFCRValidationError("full-history data bundle must be a mapping")
    if bundle.get("schema_version") != "fcr-rolling-full-history-data-v1":
        raise RollingFCRValidationError("unsupported full-history data bundle schema")
    required_bundle_keys = {
        "schema_version",
        "battery",
        "capacity_kwh",
        "terminal_rule",
        "data_fingerprints",
        "day_inputs",
        "activation_traces",
        "bundle_fingerprint",
    }
    if set(bundle) != required_bundle_keys:
        raise RollingFCRValidationError(
            "full-history data bundle keys differ from the v1 execution contract"
        )
    bundle_semantic = {
        key: value for key, value in bundle.items() if key != "bundle_fingerprint"
    }
    if bundle["bundle_fingerprint"] != fingerprint(bundle_semantic):
        raise RollingFCRValidationError("full-history data bundle fingerprint differs")
    day_rows = bundle["day_inputs"]
    activation_rows = bundle["activation_traces"]
    if not isinstance(day_rows, list) or not isinstance(activation_rows, list):
        raise RollingFCRValidationError(
            "full-history day inputs and activation traces must be ordered lists"
        )
    ordered_dates = request["ordered_dates_parsed"]
    if any(not isinstance(item, Mapping) for item in day_rows):
        raise RollingFCRValidationError(
            "full-history day input entries must be mappings"
        )
    if tuple(str(item.get("delivery_date")) for item in day_rows) != tuple(
        item.isoformat() for item in ordered_dates
    ):
        raise RollingFCRValidationError(
            "full-history day inputs must exactly match immutable date ordering"
        )
    if solver_name == "gurobi":
        backend = _gurobi_backend_evidence()
        if backend["status"] != "available":
            return {
                "schema_version": "fcr-rolling-full-history-report-v1",
                "execution_mode": "research_only_full_history",
                "release_gate": False,
                "status": "unavailable",
                "backend_evidence": backend,
                "evidence_limits": [
                    "optional Gurobi unavailability never triggers HiGHS fallback"
                ],
            }
        if request["profile_id"] in {PROFILE_IDS[2], PROFILE_IDS[3]}:
            return {
                "schema_version": "fcr-rolling-full-history-report-v1",
                "execution_mode": "research_only_full_history",
                "release_gate": False,
                "status": "unavailable",
                "backend_evidence": backend,
                "reason": "optional_gurobi_rolling_adapter_not_implemented",
                "evidence_limits": [
                    "explicit Gurobi selection never falls back to HiGHS"
                ],
            }
    solve_policy = build_solve_policy(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds,
        allow_feasible_incumbent_plan=True,
    )
    manifest = build_explicit_manifest(
        request["profile_id"],
        study_id=(
            "feature-015-full-history-"
            + str(request["request_fingerprint"])[:16]
        ),
        dates=ordered_dates,
        state_carry_policy=request["state_carry_policy"],
        solve_policy=solve_policy,
        battery_values=bundle["battery"],
        capacity_kwh=float(bundle["capacity_kwh"]),
        terminal_values=bundle["terminal_rule"],
        data_fingerprints=bundle["data_fingerprints"],
        acceptance_policy=request["acceptance_policy"],
        bundle_fingerprint=bundle["bundle_fingerprint"],
    )
    day_inputs = build_explicit_day_inputs(manifest, day_rows)
    activation_traces = build_explicit_activation_traces(
        manifest,
        activation_rows,
    )
    prior = None
    if resume_output is not None and resume_output.exists():
        prior = load_rolling_fcr_study_result(resume_output)
    result = run_rolling_fcr_study(
        manifest,
        day_inputs,
        activation_traces=activation_traces,
        resume_from=prior,
    )
    if resume_output is not None:
        _atomic_write_json(resume_output, result.to_dict())
    return {
        "schema_version": "fcr-rolling-full-history-report-v1",
        "execution_mode": "research_only_full_history",
        "release_gate": False,
        "status": "completed" if result.completeness_status == "complete" else "partial",
        "profile_id": result.profile_id,
        "requested_source_date_count": FULL_HISTORY_DATE_COUNT,
        "retained_date_count": len(result.records),
        "status_counts": dict(result.status_counts),
        "completeness_status": result.completeness_status,
        "semantic_fingerprint": result.semantic_fingerprint,
        "resume_reused": result.resume_lineage is not None,
        "resume_output_written": resume_output is not None,
        "evidence_limits": [
            "full-history completion is optional and never a release gate",
            "failed and blocked dates remain retained by the canonical result",
            "Table A1 parity is not claimed by this research workflow",
        ],
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_benchmark_reports(output_dir: Path, payload: Mapping[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = payload["profiles"]
    for item in profiles:
        _atomic_write_json(
            output_dir / f"{item['profile_id']}.json",
            item,
        )
    summary = {
        key: value for key, value in payload.items() if key != "profiles"
    }
    summary["profile_reports"] = [
        {
            "profile_id": item["profile_id"],
            "status": item["status"],
            "native_semantic_fingerprint": item.get(
                "native_semantic_fingerprint"
            ),
            "comparison_fingerprint": item.get("comparison_fingerprint"),
        }
        for item in profiles
    ]
    _atomic_write_json(output_dir / "summary.json", summary)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.study_manifest is not None:
            if args.fixture is not None or args.output_dir is not None:
                raise RollingFCRValidationError(
                    "full-history mode cannot be combined with bounded fixture/output options"
                )
            payload = run_full_history_request(
                args.study_manifest,
                resume_output=args.resume_output,
                solver_name=args.solver,
                time_limit_seconds=args.time_limit_seconds,
            )
            print(json.dumps(payload, allow_nan=False, indent=2, sort_keys=True))
            return 0
        if args.fixture is None:
            raise RollingFCRValidationError(
                "bounded benchmark mode requires the explicit --fixture path"
            )
        if args.resume_output is not None:
            raise RollingFCRValidationError(
                "--resume-output applies only to --study-manifest mode"
            )
        payload = run_bounded_reference_benchmark(
            fixture_path=args.fixture,
            profile_ids=_selected_profiles(args.profiles),
            dates=args.dates,
            solver_name=args.solver,
            time_limit_seconds=args.time_limit_seconds,
        )
        if args.output_dir is None:
            print(json.dumps(payload, allow_nan=False, indent=2, sort_keys=True))
        else:
            _write_benchmark_reports(args.output_dir, payload)
            print(
                json.dumps(
                    {
                        "output_dir": str(args.output_dir),
                        "profile_order": payload["profile_order"],
                        "statuses": {
                            item["profile_id"]: item["status"]
                            for item in payload["profiles"]
                        },
                    },
                    sort_keys=True,
                )
            )
    except (RollingFCRValidationError, ValueError) as exc:
        print(f"rolling reference benchmark failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
