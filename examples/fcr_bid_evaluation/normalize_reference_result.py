"""Normalize one explicitly generated robust-storage-bidding result for review.

This helper validates an already generated JSON file. It never invokes Julia,
JuMP, Gurobi, a network client, or code below ``baselines/``.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

from oel_validation.reference_fcr import load_golden_reference_fixture


NORMALIZED_SCHEMA_VERSION = "oel.fcr-reference-normalized-result.v1"
DEFAULT_FIXTURE = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)
OUTPUT_NAME = "normalized_reference_result.json"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_ROOT = _REPOSITORY_ROOT / "artifacts"


class ReferenceNormalizationError(ValueError):
    """Raised when generated evidence cannot enter the review workflow."""


@dataclass(frozen=True, slots=True)
class ReferenceNormalizationResult:
    output_path: Path
    source_sha256: str
    semantic_differences: tuple[Mapping[str, object], ...]


def _mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceNormalizationError(f"{field} must be a JSON object")
    return {str(key): inner for key, inner in value.items()}


def _sequence(value: object, *, field: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ReferenceNormalizationError(f"{field} must be a JSON array")
    return list(value)


def _finite(value: object, *, field: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceNormalizationError(f"{field} must be finite numeric evidence")
    if not math.isfinite(float(value)):
        raise ReferenceNormalizationError(f"{field} must be finite numeric evidence")
    return value


def _finite_array(value: object, *, field: str, count: int) -> list[float | int]:
    values = _sequence(value, field=field)
    if len(values) != count:
        raise ReferenceNormalizationError(
            f"{field} must contain exactly {count} values, found {len(values)}"
        )
    return [_finite(item, field=f"{field}[{index}]") for index, item in enumerate(values)]


def _walk_finite_json(value: object, *, field: str = "generated result") -> None:
    if isinstance(value, Mapping):
        for key, inner in value.items():
            _walk_finite_json(inner, field=f"{field}/{key}")
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            _walk_finite_json(inner, field=f"{field}/{index}")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ReferenceNormalizationError(f"{field} must be finite")


def _pointer_get(payload: object, pointer: str) -> object:
    current = payload
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping) and token in current:
            current = current[token]
        else:
            raise ReferenceNormalizationError(
                f"generated result is missing required reference field {pointer}"
            )
    return current


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReferenceNormalizationError(
            f"normalized evidence must be canonical finite JSON: {exc}"
        ) from exc


def _configuration_from_generated(
    payload: Mapping[str, object],
    *,
    committed: Mapping[str, object],
) -> dict[str, object]:
    case = _mapping(payload.get("case_data"), field="case_data")
    curr = _mapping(_mapping(payload.get("bt"), field="bt").get("curr"), field="bt.curr")
    xa = _finite_array(curr.get("xa"), field="bt.curr.xa", count=96)
    xa_dec = _finite_array(curr.get("xa_dec"), field="bt.curr.xa_dec", count=96)
    intraday_adjustment = max(abs(float(item)) for item in xa + xa_dec)
    actual = {
        "test_date": payload.get("test_date"),
        "experiment": committed["experiment"],
        "model_type": case.get("model_type"),
        "activation_series": case.get("xi_signal"),
        "energy_payment": case.get("energy_payment"),
        "intraday_trading": case.get("intraday_trading"),
        "day_ahead": case.get("day_ahead"),
        "day_ahead_limited": case.get("day_ahead_limited"),
        "reference_power_sign": committed["reference_power_sign"],
        "max_discharge_kw": _finite(case.get("x̅"), field="case_data.x̅"),
        "max_charge_kw": -float(_finite(case.get("x̲"), field="case_data.x̲")),
        "capacity_kwh": _finite(case.get("psoc"), field="case_data.psoc"),
        "minimum_stored_energy_kwh": _finite(
            case.get("y̲"), field="case_data.y̲"
        ),
        "maximum_stored_energy_kwh": _finite(
            case.get("y̅"), field="case_data.y̅"
        ),
        "initial_stored_energy_kwh": _finite(case.get("y0"), field="case_data.y0"),
        "charge_efficiency": _finite(case.get("ηc"), field="case_data.ηc"),
        "discharge_efficiency": _finite(case.get("ηd"), field="case_data.ηd"),
        "planning_interval_count": case.get("K"),
        "planning_resolution_hours": _finite(case.get("Δt"), field="case_data.Δt"),
        "activation_resolution_hours": _finite(case.get("dt"), field="case_data.dt"),
        "fcr_commitment_planning_intervals": case.get("cst_reg_periods"),
        "saved_decimal_places": case.get("ndigits_prev"),
        "intraday_adjustment_kw": intraday_adjustment,
    }
    for field, expected in committed.items():
        if actual.get(field) != expected:
            raise ReferenceNormalizationError(
                "reference configuration mismatch for "
                f"{field}: expected {expected!r}, found {actual.get(field)!r}"
            )
    return actual


def _normalized_semantics(
    payload: Mapping[str, object],
    *,
    fixture: object,
) -> dict[str, object]:
    fixture_dict = fixture.to_dict()
    committed_configuration = _mapping(
        fixture_dict["reference_configuration"],
        field="fixture.reference_configuration",
    )
    configuration = _configuration_from_generated(
        payload,
        committed=committed_configuration,
    )
    case = _mapping(payload.get("case_data"), field="case_data")
    bt = _mapping(payload.get("bt"), field="bt")
    curr = _mapping(bt.get("curr"), field="bt.curr")
    curr_bid = _mapping(bt.get("curr_bid"), field="bt.curr_bid")

    relevant_curr_fields = {
        "x0",
        "xr",
        "profit_total",
        "profit_da",
        "profit_fcr",
        "profit_id",
        "soc_initial",
        "soc_min",
        "soc_max",
        "soc_terminal",
        "y_in",
        "y_out",
        "xmin",
        "xmax",
    }
    for field in sorted(relevant_curr_fields):
        if curr.get(field) != curr_bid.get(field):
            raise ReferenceNormalizationError(
                f"bt.curr and bt.curr_bid disagree for required field {field}"
            )

    rounded_x0 = _finite_array(curr.get("x0"), field="bt.curr.x0", count=24)
    rounded_xr = _finite_array(curr.get("xr"), field="bt.curr.xr", count=6)
    if any(float(value) < 0.0 for value in rounded_xr):
        raise ReferenceNormalizationError("bt.curr.xr must be non-negative")
    p0 = _finite_array(case.get("p0"), field="case_data.p0", count=24)
    pr = _finite_array(case.get("pr"), field="case_data.pr", count=6)

    expected_fields: dict[str, object] = {}
    for expected in fixture.expected_fields:
        value = _pointer_get(payload, expected.reference_field_path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = _finite(value, field=expected.reference_field_path)
        if getattr(expected, "reference_transform", None) == "negate":
            value = -float(_finite(value, field=expected.reference_field_path))
        expected_fields[expected.field_id] = value

    return {
        "reference_configuration": configuration,
        "fixed_decisions": {
            "rounded_x0_kw": rounded_x0,
            "rounded_xr_kw": rounded_xr,
        },
        "price_inputs": {"p0": p0, "pr": pr},
        "expected_fields": expected_fields,
    }


def _committed_semantics(fixture: object) -> dict[str, object]:
    payload = fixture.to_dict()
    return {
        "reference_configuration": payload["reference_configuration"],
        "fixed_decisions": {
            "rounded_x0_kw": payload["fixed_decisions"]["rounded_x0_kw"],
            "rounded_xr_kw": payload["fixed_decisions"]["rounded_xr_kw"],
        },
        "price_inputs": {
            "p0": payload["price_inputs"]["p0"],
            "pr": payload["price_inputs"]["pr"],
        },
        "expected_fields": {
            item["field_id"]: item["expected_value"]
            for item in payload["expected_fields"]
        },
    }


def _semantic_diff(
    committed: object,
    candidate: object,
    *,
    path: str = "",
) -> list[dict[str, object]]:
    differences: list[dict[str, object]] = []
    if isinstance(committed, Mapping) and isinstance(candidate, Mapping):
        for key in sorted(set(committed) | set(candidate), key=str):
            differences.extend(
                _semantic_diff(
                    committed.get(key),
                    candidate.get(key),
                    path=f"{path}/{key}",
                )
            )
        return differences
    if isinstance(committed, list) and isinstance(candidate, list):
        for index in range(max(len(committed), len(candidate))):
            before = committed[index] if index < len(committed) else None
            after = candidate[index] if index < len(candidate) else None
            differences.extend(
                _semantic_diff(before, after, path=f"{path}/{index}")
            )
        return differences
    if committed != candidate:
        differences.append(
            {
                "field_path": path or "/",
                "committed_value": committed,
                "candidate_value": candidate,
            }
        )
    return differences


def _validate_output_path(*, input_path: Path, output_dir: Path) -> Path:
    resolved_dir = output_dir.resolve()
    if resolved_dir.is_relative_to(_REPOSITORY_ROOT) and not resolved_dir.is_relative_to(
        _ARTIFACT_ROOT
    ):
        raise ReferenceNormalizationError(
            "normalized output inside the repository must stay below ignored "
            "artifacts/; committed fixture paths require explicit reviewed promotion"
        )
    output_path = resolved_dir / OUTPUT_NAME
    if output_path == input_path.resolve():
        raise ReferenceNormalizationError("normalization output cannot overwrite its input")
    return output_path


def normalize_reference_result(
    *,
    input_path: Path,
    expected_sha256: str,
    output_dir: Path,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> ReferenceNormalizationResult:
    """Validate and normalize one generated result into an ignored review path."""

    if _SHA256.fullmatch(expected_sha256) is None:
        raise ReferenceNormalizationError(
            "expected SHA-256 must be one lowercase 64-character digest"
        )
    input_path = Path(input_path)
    if not input_path.is_file():
        raise ReferenceNormalizationError(
            f"generated reference input is not a regular file: {input_path}"
        )
    output_path = _validate_output_path(
        input_path=input_path,
        output_dir=Path(output_dir),
    )
    source_bytes = input_path.read_bytes()
    actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ReferenceNormalizationError(
            "generated reference SHA-256 mismatch: "
            f"expected {expected_sha256}, found {actual_sha256}"
        )
    try:
        payload = json.loads(source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceNormalizationError(
            f"generated reference input must be UTF-8 JSON: {exc}"
        ) from exc
    payload = _mapping(payload, field="generated result")
    _walk_finite_json(payload)
    fixture = load_golden_reference_fixture(fixture_path)
    candidate = _normalized_semantics(payload, fixture=fixture)
    differences = tuple(
        _semantic_diff(_committed_semantics(fixture), candidate)
    )
    normalized = {
        "schema_version": NORMALIZED_SCHEMA_VERSION,
        "source": {
            "sha256": actual_sha256,
            "test_date": payload["test_date"],
        },
        "committed_fixture": {
            "fixture_id": fixture.fixture_id,
            "fixture_fingerprint": fixture.fixture_fingerprint,
        },
        **candidate,
        "semantic_diff": list(differences),
    }
    output_bytes = _canonical_bytes(normalized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_bytes)
    return ReferenceNormalizationResult(
        output_path=output_path,
        source_sha256=actual_sha256,
        semantic_differences=differences,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a generated robust-storage-bidding JSON and write a "
            "canonical semantic review artifact without executing the baseline"
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fixture-path", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args(argv)
    try:
        result = normalize_reference_result(
            input_path=args.input,
            expected_sha256=args.expected_sha256,
            output_dir=args.output_dir,
            fixture_path=args.fixture_path,
        )
    except ReferenceNormalizationError as exc:
        print(f"reference normalization failed: {exc}", file=sys.stderr)
        return 2
    print(result.output_path)
    print(f"source_sha256={result.source_sha256}")
    print(f"semantic_differences={len(result.semantic_differences)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
