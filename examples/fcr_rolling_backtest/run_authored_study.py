"""Run deterministic offline Feature 015 studies from project-authored inputs."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

from open_energy_lab.control import (
    RollingFCRStudyResult,
    RollingFCRValidationError,
    aggregate_rolling_fcr_records,
    run_rolling_fcr_study,
)

try:
    from examples.fcr_rolling_backtest.study_inputs import (
        PROFILE_IDS,
        build_authored_activation_traces,
        build_day_inputs,
        build_manifest,
        build_solve_policy,
    )
except ModuleNotFoundError as exc:  # Direct ``python path/to/script.py`` execution.
    if exc.name != "examples":
        raise
    from study_inputs import (  # type: ignore[no-redef]
        PROFILE_IDS,
        build_authored_activation_traces,
        build_day_inputs,
        build_manifest,
        build_solve_policy,
    )


AUTHORED_BUNDLE_SCHEMA_VERSION = "fcr-rolling-authored-study-bundle-v1"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one or all five deterministic offline Feature 015 profiles "
            "without baseline or external-data access."
        )
    )
    parser.add_argument(
        "--profile",
        choices=("all", *PROFILE_IDS),
        default="all",
        help="Executable profile to run; the default runs five separate studies.",
    )
    parser.add_argument(
        "--state-carry-policy",
        choices=("source_three_decimal", "native_full_precision"),
        default="source_three_decimal",
        help=(
            "State handoff policy. native_full_precision is valid only for "
            "the script-15 profile."
        ),
    )
    parser.add_argument(
        "--time-limit-seconds",
        type=float,
        default=30.0,
        help="Per-solve deterministic resource limit (default: 30).",
    )
    parser.add_argument(
        "--stop-after",
        type=int,
        help=(
            "Persist only this many leading date envelopes. The full manifest "
            "identity is retained so the checkpoint can be resumed."
        ),
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="Explicit authored bundle previously written by this command.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional explicit JSON destination; otherwise JSON is printed.",
    )
    return parser.parse_args(argv)


def _selected_profiles(profile: str) -> tuple[str, ...]:
    return PROFILE_IDS if profile == "all" else (profile,)


def _partial_result(
    manifest: object,
    result: RollingFCRStudyResult,
    stop_after: int | None,
) -> RollingFCRStudyResult:
    if stop_after is None or stop_after == len(result.records):
        return result
    if stop_after <= 0 or stop_after > len(result.records):
        raise RollingFCRValidationError(
            "stop-after must select between one and the declared date count"
        )
    records = result.records[:stop_after]
    retained_dates = {
        item.classification.delivery_date for item in records
    }
    retained_segment_ids = {
        item.continuity_segment_id for item in records
    }
    segments = []
    for segment in result.continuity_segments:
        if segment.segment_id not in retained_segment_ids:
            continue
        member_dates = tuple(
            item.classification.delivery_date
            for item in records
            if item.continuity_segment_id == segment.segment_id
        )
        segments.append(
            replace(
                segment,
                start_date=min(member_dates),
                end_date=max(member_dates),
            )
        )
    links = tuple(
        item
        for item in result.state_links
        if item.successor_date in retained_dates
        and item.continuity_segment_id in retained_segment_ids
    )
    status = (
        "failed"
        if any(item.latest_revision.lifecycle_status == "failed" for item in records)
        else "partial"
    )
    retained_date_text = {item.isoformat() for item in retained_dates}
    return replace(
        result,
        records=records,
        continuity_segments=tuple(segments),
        state_links=links,
        aggregate_metrics=aggregate_rolling_fcr_records(manifest, records),
        completeness_status=status,
        requested_day_input_fingerprints={
            key: value
            for key, value in result.requested_day_input_fingerprints.items()
            if key in retained_date_text
        },
        supplied_activation_fingerprints={
            key: value
            for key, value in result.supplied_activation_fingerprints.items()
            if key in retained_date_text
        },
        resume_lineage=None,
    )


def _load_resume_bundle(path: Path) -> Mapping[str, RollingFCRStudyResult]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RollingFCRValidationError(
            f"unable to load authored resume bundle: {type(exc).__name__}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise RollingFCRValidationError("authored resume bundle must be a mapping")
    if payload.get("schema_version") != AUTHORED_BUNDLE_SCHEMA_VERSION:
        raise RollingFCRValidationError("unsupported authored resume bundle schema")
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list):
        raise RollingFCRValidationError("authored resume bundle profiles must be a list")
    results: dict[str, RollingFCRStudyResult] = {}
    for index, item in enumerate(raw_profiles):
        if not isinstance(item, Mapping):
            raise RollingFCRValidationError(
                f"authored resume profile {index} must be a mapping"
            )
        profile_id = item.get("profile_id")
        result_payload = item.get("result")
        if profile_id not in PROFILE_IDS or not isinstance(result_payload, Mapping):
            raise RollingFCRValidationError(
                f"authored resume profile {index} has invalid identity or result"
            )
        if profile_id in results:
            raise RollingFCRValidationError(
                "authored resume bundle contains a duplicate profile"
            )
        result = RollingFCRStudyResult.from_dict(result_payload)
        if result.profile_id != profile_id:
            raise RollingFCRValidationError(
                "authored resume profile identity differs from its result"
            )
        results[profile_id] = result
    return results


def _profile_report(
    *,
    manifest: object,
    result: RollingFCRStudyResult,
) -> dict[str, object]:
    return {
        "profile_id": manifest.profile.profile_id,
        "manifest": manifest.to_dict(),
        "result": result.to_dict(),
        "summary": {
            "completeness_status": result.completeness_status,
            "status_counts": dict(result.status_counts),
            "semantic_fingerprint": result.semantic_fingerprint,
            "finalized_parity_eligible_dates": [
                item.isoformat() for item in result.finalized_parity_eligible_dates
            ],
            "finalized_parity_exclusions": {
                key: list(value)
                for key, value in result.finalized_parity_exclusions.items()
            },
        },
    }


def run_authored_profiles(
    *,
    profile_ids: Sequence[str],
    state_carry_policy: str,
    time_limit_seconds: float,
    stop_after: int | None = None,
    resume_results: Mapping[str, RollingFCRStudyResult] | None = None,
) -> dict[str, object]:
    selected = tuple(profile_ids)
    if not selected or any(item not in PROFILE_IDS for item in selected):
        raise RollingFCRValidationError("authored profiles must use known identities")
    if len(set(selected)) != len(selected):
        raise RollingFCRValidationError("authored profiles must be unique")
    if state_carry_policy == "native_full_precision" and selected != (PROFILE_IDS[4],):
        raise RollingFCRValidationError(
            "native_full_precision is supported only with "
            "script-15-restriction-rolling-midnight-v1"
        )
    resume = {} if resume_results is None else dict(resume_results)
    if set(resume) - set(selected):
        raise RollingFCRValidationError(
            "resume bundle contains profiles outside the requested selection"
        )
    policy = build_solve_policy(time_limit_seconds=time_limit_seconds)
    reports = []
    for profile_id in selected:
        manifest = build_manifest(
            profile_id,
            state_carry_policy=state_carry_policy,
            solve_policy=policy,
        )
        day_inputs = build_day_inputs(manifest)
        dates = tuple(item.delivery_date for item in manifest.dates)
        traces = build_authored_activation_traces(dates)
        result = run_rolling_fcr_study(
            manifest,
            day_inputs,
            activation_traces=traces,
            resume_from=resume.get(profile_id),
        )
        result = _partial_result(manifest, result, stop_after)
        reports.append(_profile_report(manifest=manifest, result=result))
    return {
        "schema_version": AUTHORED_BUNDLE_SCHEMA_VERSION,
        "execution_mode": "deterministic_offline_project_authored",
        "profile_order": list(selected),
        "state_carry_policy": state_carry_policy,
        "profiles": reports,
        "evidence_limits": [
            "project-authored inputs are not Julia parity evidence",
            "relaxation plans remain diagnostic and non-robust",
            "optimizer-selected bids are governed by an explicit assumed-accepted policy",
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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        selected = _selected_profiles(args.profile)
        resume = (
            None
            if args.resume_from is None
            else _load_resume_bundle(args.resume_from)
        )
        payload = run_authored_profiles(
            profile_ids=selected,
            state_carry_policy=args.state_carry_policy,
            time_limit_seconds=args.time_limit_seconds,
            stop_after=args.stop_after,
            resume_results=resume,
        )
        if args.output is None:
            print(json.dumps(payload, allow_nan=False, indent=2, sort_keys=True))
        else:
            _atomic_write_json(args.output, payload)
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "profile_order": payload["profile_order"],
                        "semantic_fingerprints": {
                            item["profile_id"]: item["summary"][
                                "semantic_fingerprint"
                            ]
                            for item in payload["profiles"]
                        },
                    },
                    sort_keys=True,
                )
            )
    except (RollingFCRValidationError, ValueError) as exc:
        print(f"authored rolling study failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
