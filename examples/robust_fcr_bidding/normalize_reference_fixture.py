"""Normalize one explicitly selected robust-storage-bidding result offline.

The normalizer is a maintainer tool, not a runtime discovery mechanism.  It
validates the selected bytes and source configuration, writes only a candidate
and ordered semantic diff, and never invokes Julia or a solver.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from open_energy_lab.control.robust_fcr_bidding import (
    DEPLOYABILITY_THRESHOLD,
    ROBUST_FCR_BIDDING_PROBLEM_VERSION,
    RobustFCRFormulationProfile,
)
from open_energy_lab.control.robust_fcr_reference import (
    REFERENCE_FIXTURE_ID,
    REFERENCE_FIXTURE_SCHEMA_VERSION,
    REFERENCE_PRECISION_POLICY_ID,
    REFERENCE_RESULT_BYTE_COUNT,
    REFERENCE_RESULT_PATH,
    REFERENCE_RESULT_SHA256,
    REFERENCE_REVISION,
    reference_decision_content_fingerprint,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_ROOT = _REPOSITORY_ROOT / "artifacts"
_CANDIDATE_NAME = "robust_storage_bidding_2023-06-18_restriction_v1.json"
_EVALUATION_FIXTURE_FINGERPRINT = (
    "6bce7f00bb38b257a6f5e4186a8b8dab06d7f5f41336238b499b153b3f7a59fd"
)


class ReferenceFixtureNormalizationError(ValueError):
    """Raised before a candidate is written when governance checks fail."""


@dataclass(frozen=True, slots=True)
class ReferenceFixtureNormalizationResult:
    source_json: Path
    source_sha256: str
    candidate_path: Path
    semantic_diff_path: Path
    semantic_differences: tuple[Mapping[str, object], ...]


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReferenceFixtureNormalizationError(
            f"reference evidence must be finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceFixtureNormalizationError(f"{field_name} must be an object")
    return {str(key): inner for key, inner in value.items()}


def _sequence(value: object, *, field_name: str, count: int) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ReferenceFixtureNormalizationError(f"{field_name} must be an array")
    result = list(value)
    if len(result) != count:
        raise ReferenceFixtureNormalizationError(
            f"{field_name} must contain exactly {count} values"
        )
    for index, item in enumerate(result):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ReferenceFixtureNormalizationError(
                f"{field_name}[{index}] must be finite"
            )
        if not math.isfinite(float(item)):
            raise ReferenceFixtureNormalizationError(
                f"{field_name}[{index}] must be finite"
            )
    return [0.0 if float(item) == 0.0 else float(item) for item in result]


def _expect(
    mapping: Mapping[str, object],
    name: str,
    expected: object,
    *,
    field_name: str = "case_data",
) -> None:
    if name not in mapping or mapping[name] != expected:
        raise ReferenceFixtureNormalizationError(
            f"{field_name}.{name} must equal {expected!r}"
        )


def _validated_source(raw: object) -> dict[str, object]:
    top = _mapping(raw, field_name="source result")
    for name in (
        "case_data",
        "objective bound",
        "bt",
        "test_date",
        "objective value",
        "solve_time",
    ):
        if name not in top:
            raise ReferenceFixtureNormalizationError(
                f"source result is missing {name!r}"
            )
    case = _mapping(top["case_data"], field_name="case_data")
    expected = {
        "K": 96,
        "x̅": 50.0,
        "x̲": -50.0,
        "y0": 53.328,
        "γ": 0.25,
        "Γ": 2.25,
        "Δt": 0.25,
        "y̲": 10.0,
        "y̅": 90.0,
        "ηc": 0.92,
        "ηd": 0.92,
        "psoc": 100.0,
        "intraday_trading": False,
        "cst_reg_periods": 16,
        "ylK": 53.327556325823224,
        "model_type": "restrict",
        "u_restrict": 0.0,
        "solver": "Gurobi",
        "timelimit": 3600.0,
    }
    for name, value in expected.items():
        _expect(case, name, value)
    _expect(top, "test_date", "2023-06-18", field_name="source result")
    p0 = _sequence(case.get("p0"), field_name="case_data.p0", count=24)
    pr = _sequence(case.get("pr"), field_name="case_data.pr", count=6)
    bt = _mapping(top["bt"], field_name="bt")
    current = _mapping(bt.get("curr"), field_name="bt.curr")
    x0 = _sequence(current.get("x0"), field_name="bt.curr.x0", count=24)
    xr = _sequence(current.get("xr"), field_name="bt.curr.xr", count=6)
    if any(value < 0.0 for value in xr):
        raise ReferenceFixtureNormalizationError("bt.curr.xr must be non-negative")
    symin = _sequence(current.get("symin"), field_name="bt.curr.symin", count=96)
    symax = _sequence(current.get("symax"), field_name="bt.curr.symax", count=96)
    sy_k = current.get("syK")
    if isinstance(sy_k, bool) or not isinstance(sy_k, (int, float)):
        raise ReferenceFixtureNormalizationError("bt.curr.syK must be finite")
    values = {
        "case": case,
        "p0": p0,
        "pr": pr,
        "x0": x0,
        "xr": xr,
        "symin": symin,
        "symax": symax,
        "syK": float(sy_k),
    }
    for source_name, target_name in (
        ("objective value", "objective_value"),
        ("objective bound", "objective_bound"),
        ("solve_time", "solve_time"),
    ):
        value = top[source_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ReferenceFixtureNormalizationError(
                f"source result {source_name!r} must be finite"
            )
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ReferenceFixtureNormalizationError(
                f"source result {source_name!r} must be finite"
            )
        values[target_name] = normalized
    return values


def _precision_policy() -> dict[str, object]:
    payload = {
        "policy_id": REFERENCE_PRECISION_POLICY_ID,
        "interval_closure": "closed_outer",
        "decision_decimal_places": 3,
        "decision_half_unit_kw": 0.0005,
        "objective_decimal_places": 3,
        "objective_half_unit_eur": 0.0005,
        "deployability_threshold": {
            "value": DEPLOYABILITY_THRESHOLD,
            "rule": "absolute_in_each_canonical_unit",
        },
        "certification_method": (
            "one_joint_restriction_feasibility_and_objective_interval"
        ),
    }
    return {**payload, "policy_fingerprint": _fingerprint(payload)}


def _normalized_payload(source: Mapping[str, object]) -> dict[str, object]:
    problem = {
        "semantics_version": ROBUST_FCR_BIDDING_PROBLEM_VERSION,
        "information_cutoff_utc": "2023-06-17T22:00:00Z",
        "time_contract": {
            "delivery_date": "2023-06-18",
            "market_timezone": "Europe/Paris",
            "start_utc": "2023-06-17T22:00:00Z",
            "end_utc": "2023-06-18T22:00:00Z",
            "planning_interval_count": 96,
            "planning_resolution_hours": 0.25,
            "energy_interval_count": 24,
            "energy_resolution_hours": 1.0,
            "fcr_interval_count": 6,
            "fcr_block_hours": 4.0,
            "planning_intervals_per_energy_interval": 4,
            "planning_intervals_per_fcr_block": 16,
        },
        "battery": {
            "source_power_sign": "positive_is_discharge",
            "maximum_charge_power_kw": 50.0,
            "maximum_discharge_power_kw": 50.0,
            "minimum_stored_energy_kwh": 10.0,
            "maximum_stored_energy_kwh": 90.0,
            "initial_stored_energy_kwh": 53.328,
            "charge_efficiency": 0.92,
            "discharge_efficiency": 0.92,
        },
        "uncertainty": {
            "recovery_activation_budget_hours": 0.25,
            "recovery_window_hours": 2.25,
            "horizon_activation_budget_hours": 2.75,
            "horizon_hours": 24.0,
            "pointwise_activation_bounds": [-1.0, 1.0],
            "derivation_rule": "covering-window-budget-v1",
        },
        "terminal_rule": {
            "minimum_terminal_stored_energy_kwh": 53.327556325823224,
            "allow_penalized_shortfall": True,
            "shortfall_penalty_eur_per_kwh": 100.0,
            "source_formula": (
                "y0 - delta_t * sum(alpha[k]) >= ylK - syK[2]"
            ),
        },
        "prices": {
            "day_ahead_unit": "EUR/kWh",
            "day_ahead_energy_prices": list(source["p0"]),
            "fcr_capacity_unit": "EUR/kW/4h-block",
            "fcr_capacity_prices": list(source["pr"]),
        },
        "solve_profile": {
            "reference_solver": "Gurobi",
            "time_limit_seconds": 3600.0,
            "explicit_tolerances_status": "not_recorded_source_defaults",
            "intraday_trading": False,
            "u_restrict": 0.0,
        },
    }
    problem["problem_fingerprint"] = _fingerprint(problem)
    recorded = {
        "objective_value_eur": source["objective_value"],
        "objective_bound_eur": source["objective_bound"],
        "source_x0_sign": "positive_is_discharge",
        "rounded_x0_kw": list(source["x0"]),
        "rounded_xr_kw": list(source["xr"]),
        "saved_decimal_places": 3,
        "solve_time_seconds": source["solve_time"],
        "recorded_slacks": {
            "symin": list(source["symin"]),
            "symax": list(source["symax"]),
            "terminal_syK": source["syK"],
            "source_declared_inert_syK_status": "not_serialized_separately",
        },
        "decision_content_fingerprint": reference_decision_content_fingerprint(
            source["x0"], source["xr"]
        ),
    }
    unavailable_reasons = {
        "source.actual_solver_versions": "the generated JSON records only the configured solver name",
        "source.constraint_residuals": "the generated JSON contains no equation-family residual audit",
        "source.dual_status": "the generated JSON contains no formal dual status",
        "source.exact_optimality_gap": "displayed objective and bound are rounded and do not establish an exact gap",
        "source.optimality_proof": "the generated JSON contains no solver proof or termination record",
        "source.primal_status": "the generated JSON contains no formal primal status",
        "source.restriction_bilinear_evidence": "bilinear_violations is not evaluated for restriction results",
        "source.solver_tolerances": "the source run records no explicit solver tolerances",
        "source.termination_status": "the generated JSON contains no termination condition",
        "source.unrounded_decisions": "market decisions are serialized to three decimals",
    }
    payload = {
        "schema_version": REFERENCE_FIXTURE_SCHEMA_VERSION,
        "fixture_id": REFERENCE_FIXTURE_ID,
        "reference_provenance": {
            "reference_revision": REFERENCE_REVISION,
            "source_paths": [
                "baselines/robust_storage_bidding/code/01_datastruct.jl",
                "baselines/robust_storage_bidding/code/02_model.jl",
                "baselines/robust_storage_bidding/code/12.jl",
                REFERENCE_RESULT_PATH,
            ],
            "generation_working_directory": "baselines/robust_storage_bidding",
            "generation_command": "julia --project=. code/12.jl",
            "original_result_path": REFERENCE_RESULT_PATH,
            "original_result_byte_count": REFERENCE_RESULT_BYTE_COUNT,
            "original_result_sha256": REFERENCE_RESULT_SHA256,
            "normalization_command": (
                "uv run python examples/robust_fcr_bidding/"
                "normalize_reference_fixture.py --source-json "
                f"{REFERENCE_RESULT_PATH} --destination-dir "
                "artifacts/reference/robust_fcr_bidding"
            ),
            "generated_result_revision_status": (
                "digest_pinned_generated_file_not_tracked_at_reference_revision"
            ),
        },
        "evaluation_fixture_reference": {
            "fixture_id": "robust-storage-bidding-experiment-2-2023-06-18-v1",
            "relative_path": (
                "tests/fixtures/fcr_bid_evaluation/"
                "robust_storage_bidding_2023-06-18_aggregate_v1.json"
            ),
            "fixture_fingerprint": _EVALUATION_FIXTURE_FINGERPRINT,
        },
        "problem": problem,
        "reference_formulation": RobustFCRFormulationProfile.for_kind(
            "restriction"
        ).to_dict(),
        "recorded_result": recorded,
        "precision_policy": _precision_policy(),
        "unavailable_fields": [
            {"field_id": name, "reason": unavailable_reasons[name]}
            for name in sorted(unavailable_reasons)
        ],
        "redistribution_status": {
            "normalized_problem_and_result": "committed_derived_evidence",
            "original_result": "digest_only",
            "activation_data": "absent_external_evaluation_only",
        },
    }
    payload["fixture_fingerprint"] = _fingerprint(payload)
    return payload


def _semantic_differences(
    candidate: object,
    committed: object,
    *,
    path: str = "",
) -> list[dict[str, object]]:
    differences: list[dict[str, object]] = []
    if isinstance(candidate, Mapping) and isinstance(committed, Mapping):
        for key in sorted(set(candidate) | set(committed)):
            child = f"{path}/{key}"
            if key not in candidate:
                differences.append(
                    {"field_path": child, "candidate": None, "committed": committed[key]}
                )
            elif key not in committed:
                differences.append(
                    {"field_path": child, "candidate": candidate[key], "committed": None}
                )
            else:
                differences.extend(
                    _semantic_differences(candidate[key], committed[key], path=child)
                )
    elif isinstance(candidate, list) and isinstance(committed, list):
        for index in range(max(len(candidate), len(committed))):
            child = f"{path}/{index}"
            left = candidate[index] if index < len(candidate) else None
            right = committed[index] if index < len(committed) else None
            differences.extend(_semantic_differences(left, right, path=child))
    elif candidate != committed:
        differences.append(
            {"field_path": path or "/", "candidate": candidate, "committed": committed}
        )
    return differences


def _validate_destination(destination_dir: Path, committed_fixture: Path) -> None:
    destination = destination_dir.resolve()
    committed = committed_fixture.resolve()
    candidate = destination / _CANDIDATE_NAME
    if candidate == committed or destination == committed.parent:
        raise ReferenceFixtureNormalizationError(
            "normalization refuses a committed fixture destination"
        )
    repository = _REPOSITORY_ROOT.resolve()
    if destination.is_relative_to(repository) and not destination.is_relative_to(
        _ARTIFACT_ROOT.resolve()
    ):
        raise ReferenceFixtureNormalizationError(
            "repository-local normalization output must stay below ignored artifacts/"
        )


def normalize_reference_fixture(
    *,
    source_json: str | Path,
    expected_sha256: str,
    destination_dir: str | Path,
    committed_fixture: str | Path,
) -> ReferenceFixtureNormalizationResult:
    """Validate one local source and emit a deterministic candidate and diff."""

    source_path = Path(source_json)
    destination = Path(destination_dir)
    committed_path = Path(committed_fixture)
    _validate_destination(destination, committed_path)
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise ReferenceFixtureNormalizationError(
            f"explicit source JSON is unavailable: {exc}"
        ) from exc
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != expected_sha256:
        raise ReferenceFixtureNormalizationError(
            f"source SHA-256 mismatch: expected {expected_sha256}, found {source_sha256}"
        )
    try:
        source_raw = json.loads(source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceFixtureNormalizationError(
            f"source must be UTF-8 JSON: {exc}"
        ) from exc
    candidate_payload = _normalized_payload(_validated_source(source_raw))
    if committed_path.exists():
        try:
            committed_payload = json.loads(committed_path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReferenceFixtureNormalizationError(
                f"committed fixture cannot be compared: {exc}"
            ) from exc
        differences = _semantic_differences(candidate_payload, committed_payload)
    else:
        differences = [
            {
                "field_path": "/",
                "candidate": candidate_payload,
                "committed": None,
            }
        ]
    ordered = tuple(sorted(differences, key=lambda item: str(item["field_path"])))
    destination.mkdir(parents=True, exist_ok=True)
    candidate_path = destination / _CANDIDATE_NAME
    semantic_diff_path = destination / "semantic_diff.json"
    candidate_path.write_bytes(_canonical_bytes(candidate_payload) + b"\n")
    semantic_diff_path.write_bytes(
        _canonical_bytes(
            {
                "candidate_fixture": _CANDIDATE_NAME,
                "committed_fixture": str(committed_path),
                "source_json": str(source_path),
                "source_sha256": source_sha256,
                "semantic_differences": list(ordered),
            }
        )
        + b"\n"
    )
    return ReferenceFixtureNormalizationResult(
        source_json=source_path,
        source_sha256=source_sha256,
        candidate_path=candidate_path,
        semantic_diff_path=semantic_diff_path,
        semantic_differences=ordered,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-json", type=Path, required=True)
    parser.add_argument(
        "--expected-sha256",
        default=REFERENCE_RESULT_SHA256,
        help="expected SHA-256 for the explicitly selected source bytes",
    )
    parser.add_argument("--destination-dir", type=Path, required=True)
    parser.add_argument(
        "--committed-fixture",
        type=Path,
        default=(
            _REPOSITORY_ROOT
            / "tests/fixtures/fcr_bidding/"
            / _CANDIDATE_NAME
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = normalize_reference_fixture(
        source_json=args.source_json,
        expected_sha256=args.expected_sha256,
        destination_dir=args.destination_dir,
        committed_fixture=args.committed_fixture,
    )
    print(f"source_sha256={result.source_sha256}")
    print(f"candidate={result.candidate_path}")
    print(f"semantic_diff={result.semantic_diff_path}")
    print(f"semantic_difference_count={len(result.semantic_differences)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
