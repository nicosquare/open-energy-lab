"""Normalize the explicit Feature 015 Julia/Gurobi evidence manifest.

This maintainer command is the only Feature 015 path allowed to read the raw
reference rerun.  It accepts caller-selected roots, resolves only manifest
entries, verifies every byte digest before parsing any evidence, and writes a
candidate plus semantic diff beneath the ignored artifact tree.  Promotion to
``tests/fixtures`` is deliberately a separate review action.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from open_energy_lab.control.fcr_rolling_reference import (
    ROLLING_FCR_REFERENCE_DATES,
    ROLLING_FCR_REFERENCE_FIXTURE_ID,
    ROLLING_FCR_REFERENCE_FIXTURE_SCHEMA_VERSION,
    ROLLING_FCR_REFERENCE_NORMALIZER_VERSION,
    ROLLING_FCR_REFERENCE_PROFILE_IDS,
    ROLLING_FCR_REFERENCE_REVISION,
    RollingFCRFeature013CrossCheck,
    RollingFCRReferenceAcceptedOverlap,
    RollingFCRReferenceDeliveryEvidence,
    RollingFCRReferenceDiscrepancy,
    RollingFCRReferenceFixture,
    RollingFCRReferencePrecisionPolicy,
    RollingFCRReferenceProblemInput,
    RollingFCRReferenceProfileCrosswalk,
    RollingFCRReferenceProvenance,
    RollingFCRReferenceRawArtifact,
    RollingFCRReferenceRedistributionStatus,
    RollingFCRReferenceSolveRecord,
    RollingFCRReferenceUnavailableField,
    RollingFCRSourceSolverEvidence,
    load_rolling_fcr_reference_fixture,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_ROOT = _REPOSITORY_ROOT / "artifacts"
_COMMITTED_FIXTURE = (
    _REPOSITORY_ROOT
    / "tests/fixtures/fcr_rolling_backtest/"
    "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json"
)

_INPUT_SCHEMA_VERSION = "fcr-rolling-reference-input-manifest-v1"
_CANDIDATE_NAME = (
    "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json"
)
_DIFF_NAME = (
    "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.semantic-diff.json"
)
_SOURCE_FILES = (
    "code/01_datastruct.jl",
    "code/02_model.jl",
    "code/03_backtest_save.jl",
    "code/04_parse_results.jl",
    "code/05_dates.txt",
    "code/11.jl",
    "code/12.jl",
    "code/13.jl",
    "code/14.jl",
    "code/15.jl",
)
_INPUT_DATA_FILES = (
    "data/day_ahead_FR.csv",
    "data/FCR_RTE.csv",
    "data/regulation_signal.csv",
)
_PROFILE_DATA = (
    (
        "script-11-relaxation-reset-midnight-v1",
        1,
        11,
        "relax",
        24.0,
        "relaxation with independent midnight reset days",
        1,
        "11",
    ),
    (
        "script-12-restriction-reset-midnight-v1",
        2,
        12,
        "restrict",
        24.0,
        "restriction with independent midnight reset days",
        2,
        "12",
    ),
    (
        "script-13-arbitrage-only-midnight-v1",
        3,
        13,
        "no_reg",
        24.0,
        "day-ahead arbitrage with FCR fixed exactly to zero",
        4,
        "14",
    ),
    (
        "script-14-restriction-rolling-0800-v1",
        4,
        14,
        "restrict",
        8.0,
        "restriction with rolling 08:00 overlapping predecessor decisions",
        5,
        "15",
    ),
    (
        "script-15-restriction-rolling-midnight-v1",
        5,
        15,
        "restrict",
        24.0,
        "restriction with rolling midnight state carry-over",
        3,
        "13",
    ),
)
_EXPECTED_JSON_PATHS = tuple(
    f"results/{profile:02d}/{delivery_date.isoformat()}.json"
    for _profile_id, profile, _script, _model, _time, _behavior, _paper, _workbook
    in _PROFILE_DATA
    for delivery_date in ROLLING_FCR_REFERENCE_DATES
)
_EXPECTED_LOG_PATHS = tuple(
    [
        f"code/{script}-{delivery_date.isoformat()}.log"
        for script in (11, 12)
        for delivery_date in ROLLING_FCR_REFERENCE_DATES
    ]
    + ["code/13.log", "code/14.log", "code/15.log"]
)
_REQUIRED_TOP_KEYS = frozenset(
    {
        "schema_version",
        "fixture_id",
        "reference_revision",
        "runtime_evidence",
        "committed_environment",
        "readme_claims",
        "artifacts",
    }
)
_REQUIRED_ARTIFACT_KEYS = frozenset(
    {
        "artifact_id",
        "artifact_kind",
        "root_kind",
        "relative_path",
        "sha256",
        "used_fields",
        "redistributed",
    }
)
_SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RUN_MARKER = re.compile(r"(?m)^Test run:\s*(\d{4}-\d{2}-\d{2})\s*$")
_FLOAT_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


class RollingFCRReferenceNormalizationError(ValueError):
    """Raised before an invalid or ungoverned candidate can be written."""


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceNormalizationResult:
    candidate_path: Path
    semantic_diff_path: Path
    input_manifest_sha256: str
    raw_artifact_fingerprints: Mapping[str, str]
    semantic_differences: tuple[Mapping[str, object], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "raw_artifact_fingerprints",
            MappingProxyType(dict(self.raw_artifact_fingerprints)),
        )
        object.__setattr__(
            self,
            "semantic_differences",
            tuple(MappingProxyType(dict(item)) for item in self.semantic_differences),
        )


@dataclass(frozen=True, slots=True)
class _InputArtifact:
    artifact_id: str
    artifact_kind: str
    root_kind: str
    relative_path: str
    sha256: str
    used_fields: tuple[str, ...]
    redistributed: bool
    resolved_path: Path


@dataclass(frozen=True, slots=True)
class _LogEvidence:
    termination_condition: str
    primal_status: str
    dual_status: str
    objective: float
    bound: float
    displayed_objective: float
    displayed_bound: float
    relative_gap: float
    runtime_seconds: float


def _canonical_bytes(value: object, *, pretty: bool = False) -> bytes:
    if pretty:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        return f"{text}\n".encode("utf-8")
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _strict_mapping(
    value: object,
    *,
    field_name: str,
    keys: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} must be a JSON object"
        )
    result = {str(key): inner for key, inner in value.items()}
    if set(result) != set(keys):
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} must use the exact field set; "
            f"missing={sorted(set(keys) - set(result))}, "
            f"unexpected={sorted(set(result) - set(keys))}"
        )
    return result


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} must be a finite number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} must be a finite number"
        )
    return 0.0 if result == 0.0 else result


def _sequence(value: object, *, field_name: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RollingFCRReferenceNormalizationError(f"{field_name} must be an array")
    return tuple(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise RollingFCRReferenceNormalizationError(
            f"unable to read explicitly listed artifact {path}: {exc}"
        ) from exc
    return digest.hexdigest()


def _resolve_beneath(root: Path, relative_path: str, *, field_name: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} must be a relative path without parent traversal"
        )
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} escapes its declared root"
        )
    return resolved


def _read_input_manifest(
    *, source_root: Path, input_manifest: Path
) -> tuple[dict[str, Any], tuple[_InputArtifact, ...], str]:
    try:
        manifest_bytes = input_manifest.read_bytes()
    except OSError as exc:
        raise RollingFCRReferenceNormalizationError(
            f"input manifest is unavailable at explicit path {input_manifest}: {exc}"
        ) from exc
    try:
        manifest_raw = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RollingFCRReferenceNormalizationError(
            f"input manifest must be UTF-8 JSON: {exc}"
        ) from exc
    manifest = _strict_mapping(
        manifest_raw,
        field_name="input manifest",
        keys=_REQUIRED_TOP_KEYS,
    )
    if manifest["schema_version"] != _INPUT_SCHEMA_VERSION:
        raise RollingFCRReferenceNormalizationError(
            "unsupported normalization input manifest schema"
        )
    if manifest["fixture_id"] != ROLLING_FCR_REFERENCE_FIXTURE_ID:
        raise RollingFCRReferenceNormalizationError("input fixture_id is not governed")
    if manifest["reference_revision"] != ROLLING_FCR_REFERENCE_REVISION:
        raise RollingFCRReferenceNormalizationError(
            "input reference revision is not pinned"
        )
    artifact_items = _sequence(manifest["artifacts"], field_name="artifacts")
    artifacts: list[_InputArtifact] = []
    for index, value in enumerate(artifact_items):
        raw = _strict_mapping(
            value,
            field_name=f"artifacts[{index}]",
            keys=_REQUIRED_ARTIFACT_KEYS,
        )
        artifact_id = _text(raw["artifact_id"], field_name="artifact_id")
        artifact_kind = _text(raw["artifact_kind"], field_name="artifact_kind")
        if artifact_kind not in {
            "source",
            "generated_json",
            "generated_log",
            "input_data",
            "project",
            "manifest",
            "workbook",
        }:
            raise RollingFCRReferenceNormalizationError(
                f"unsupported artifact kind {artifact_kind!r}"
            )
        root_kind = _text(raw["root_kind"], field_name="root_kind")
        if root_kind not in {"source", "repository"}:
            raise RollingFCRReferenceNormalizationError(
                "artifact root_kind must be source or repository"
            )
        relative_path = _text(raw["relative_path"], field_name="relative_path")
        expected_sha = _text(raw["sha256"], field_name="sha256")
        if not _SHA_PATTERN.fullmatch(expected_sha):
            raise RollingFCRReferenceNormalizationError(
                "artifact SHA-256 must be 64 lowercase hexadecimal characters"
            )
        used_fields = tuple(
            _text(item, field_name="used_fields")
            for item in _sequence(raw["used_fields"], field_name="used_fields")
        )
        if not used_fields or len(set(used_fields)) != len(used_fields):
            raise RollingFCRReferenceNormalizationError(
                "artifact used_fields must be non-empty and unique"
            )
        if raw["redistributed"] is not False:
            raise RollingFCRReferenceNormalizationError(
                "raw input artifacts must not be redistributed"
            )
        root = source_root if root_kind == "source" else _REPOSITORY_ROOT
        artifacts.append(
            _InputArtifact(
                artifact_id=artifact_id,
                artifact_kind=artifact_kind,
                root_kind=root_kind,
                relative_path=relative_path,
                sha256=expected_sha,
                used_fields=used_fields,
                redistributed=False,
                resolved_path=_resolve_beneath(
                    root,
                    relative_path,
                    field_name=f"artifacts[{index}].relative_path",
                ),
            )
        )
    if len({item.artifact_id for item in artifacts}) != len(artifacts):
        raise RollingFCRReferenceNormalizationError("artifact IDs must be unique")
    rooted_paths = {(item.root_kind, item.relative_path) for item in artifacts}
    if len(rooted_paths) != len(artifacts):
        raise RollingFCRReferenceNormalizationError(
            "artifact root/path identities must be unique"
        )
    _validate_inventory(tuple(artifacts))
    return manifest, tuple(artifacts), hashlib.sha256(manifest_bytes).hexdigest()


def _paths_for_kind(
    artifacts: Sequence[_InputArtifact], artifact_kind: str
) -> tuple[str, ...]:
    return tuple(
        item.relative_path for item in artifacts if item.artifact_kind == artifact_kind
    )


def _validate_inventory(artifacts: tuple[_InputArtifact, ...]) -> None:
    counts = Counter(item.artifact_kind for item in artifacts)
    if counts["generated_json"] != 20 or set(
        _paths_for_kind(artifacts, "generated_json")
    ) != set(_EXPECTED_JSON_PATHS):
        raise RollingFCRReferenceNormalizationError(
            "input manifest must list the exact 20 generated JSON files"
        )
    if counts["generated_log"] != 11 or set(
        _paths_for_kind(artifacts, "generated_log")
    ) != set(_EXPECTED_LOG_PATHS):
        raise RollingFCRReferenceNormalizationError(
            "input manifest must list the exact 11 generated logs"
        )
    paths = {(item.root_kind, item.relative_path): item for item in artifacts}
    required_source = {
        *(('source', path) for path in _SOURCE_FILES),
        *(('source', path) for path in _INPUT_DATA_FILES),
        ("source", "code/Project.toml"),
        ("source", "code/Manifest.toml"),
        ("source", "README.md"),
        ("source", "results/result_overview.xlsx"),
        (
            "repository",
            "tests/fixtures/fcr_bidding/"
            "robust_storage_bidding_2023-06-18_restriction_v1.json",
        ),
    }
    missing = sorted(required_source - set(paths))
    if missing:
        raise RollingFCRReferenceNormalizationError(
            f"input manifest omits required governed artifacts: {missing}"
        )
    governed = paths[
        (
            "repository",
            "tests/fixtures/fcr_bidding/"
            "robust_storage_bidding_2023-06-18_restriction_v1.json",
        )
    ]
    if governed.artifact_kind != "input_data":
        raise RollingFCRReferenceNormalizationError(
            "Feature 013 governed fixture must be an input_data artifact"
        )


def _verify_all_digests(
    artifacts: Sequence[_InputArtifact],
) -> Mapping[str, str]:
    observed: dict[str, str] = {}
    mismatches: list[str] = []
    for artifact in artifacts:
        digest = _sha256_file(artifact.resolved_path)
        observed[artifact.artifact_id] = digest
        if digest != artifact.sha256:
            mismatches.append(
                f"{artifact.artifact_id}: expected {artifact.sha256}, observed {digest}"
            )
    if mismatches:
        raise RollingFCRReferenceNormalizationError(
            "SHA-256 verification failed before evidence parsing: "
            + "; ".join(mismatches)
        )
    return MappingProxyType(observed)


def _artifact_by_path(
    artifacts: Sequence[_InputArtifact], relative_path: str, *, root_kind: str = "source"
) -> _InputArtifact:
    try:
        return next(
            item
            for item in artifacts
            if item.root_kind == root_kind and item.relative_path == relative_path
        )
    except StopIteration as exc:  # pragma: no cover - inventory check owns this
        raise RollingFCRReferenceNormalizationError(
            f"required artifact {root_kind}:{relative_path} is unavailable"
        ) from exc


def _parse_json_artifact(artifact: _InputArtifact) -> dict[str, Any]:
    try:
        raw = json.loads(artifact.resolved_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RollingFCRReferenceNormalizationError(
            f"generated JSON {artifact.relative_path} is invalid: {exc}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise RollingFCRReferenceNormalizationError(
            f"generated JSON {artifact.relative_path} must contain an object"
        )
    return {str(key): value for key, value in raw.items()}


def _extract_one(pattern: str, text: str, *, field_name: str) -> str:
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    if len(matches) != 1:
        raise RollingFCRReferenceNormalizationError(
            f"log segment must contain exactly one {field_name}; found {len(matches)}"
        )
    value = matches[0]
    if isinstance(value, tuple):
        raise AssertionError("scalar log expression expected")
    return value.strip()


def _parse_log_segment(segment: str, *, identity: str) -> _LogEvidence:
    termination = _extract_one(
        r"^\s*Termination status\s*:\s*(\S+)\s*$",
        segment,
        field_name=f"{identity} termination status",
    )
    primal = _extract_one(
        r"^\s*Primal status\s*:\s*(\S+)\s*$",
        segment,
        field_name=f"{identity} primal status",
    )
    dual = _extract_one(
        r"^\s*Dual status\s*:\s*(\S+)\s*$",
        segment,
        field_name=f"{identity} dual status",
    )
    best = re.findall(
        rf"^Best objective\s+({_FLOAT_PATTERN}),\s+best bound\s+({_FLOAT_PATTERN}),\s+gap\s+({_FLOAT_PATTERN})%\s*$",
        segment,
        flags=re.MULTILINE,
    )
    if len(best) != 1:
        raise RollingFCRReferenceNormalizationError(
            f"log segment {identity} must contain exactly one Best objective record"
        )
    objective, bound, _percent_gap = (_finite(float(item), field_name=identity) for item in best[0])
    displayed_objective = _finite(
        float(
            _extract_one(
                rf"^\s*Objective value\s*:\s*({_FLOAT_PATTERN})\s*$",
                segment,
                field_name=f"{identity} objective value",
            )
        ),
        field_name=f"{identity} objective value",
    )
    displayed_bound = _finite(
        float(
            _extract_one(
                rf"^\s*Objective bound\s*:\s*({_FLOAT_PATTERN})\s*$",
                segment,
                field_name=f"{identity} objective bound",
            )
        ),
        field_name=f"{identity} objective bound",
    )
    relative_gap = _finite(
        float(
            _extract_one(
                rf"^\s*Relative gap\s*:\s*({_FLOAT_PATTERN})\s*$",
                segment,
                field_name=f"{identity} relative gap",
            )
        ),
        field_name=f"{identity} relative gap",
    )
    runtime = _finite(
        float(
            _extract_one(
                rf"^\s*Solve time \(sec\)\s*:\s*({_FLOAT_PATTERN})\s*$",
                segment,
                field_name=f"{identity} solve time",
            )
        ),
        field_name=f"{identity} solve time",
    )
    if termination not in {"OPTIMAL", "TIME_LIMIT"}:
        raise RollingFCRReferenceNormalizationError(
            f"unsupported source termination {termination!r} in {identity}"
        )
    if primal != "FEASIBLE_POINT" or dual not in {"FEASIBLE_POINT", "NO_SOLUTION"}:
        raise RollingFCRReferenceNormalizationError(
            f"source log {identity} does not retain a supported incumbent status"
        )
    return _LogEvidence(
        termination_condition=termination,
        primal_status=primal,
        dual_status=dual,
        objective=objective,
        bound=bound,
        displayed_objective=displayed_objective,
        displayed_bound=displayed_bound,
        relative_gap=relative_gap,
        runtime_seconds=runtime,
    )


def _parse_logs(
    artifacts: Sequence[_InputArtifact],
) -> Mapping[tuple[int, date], tuple[_InputArtifact, _LogEvidence]]:
    result: dict[tuple[int, date], tuple[_InputArtifact, _LogEvidence]] = {}
    expected_dates = tuple(item.isoformat() for item in ROLLING_FCR_REFERENCE_DATES)
    for _profile_id, profile, script, _model, _time, _behavior, _paper, _workbook in _PROFILE_DATA:
        if profile <= 2:
            artifact_group = tuple(
                _artifact_by_path(
                    artifacts, f"code/{script}-{delivery_date}.log"
                )
                for delivery_date in expected_dates
            )
        else:
            artifact_group = (_artifact_by_path(artifacts, f"code/{script}.log"),)
        for artifact in artifact_group:
            try:
                text = artifact.resolved_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise RollingFCRReferenceNormalizationError(
                    f"generated log {artifact.relative_path} is invalid UTF-8: {exc}"
                ) from exc
            markers = tuple(match.group(1) for match in _RUN_MARKER.finditer(text))
            expected_markers = (
                expected_dates
                if profile >= 3
                else (artifact.relative_path.removeprefix(f"code/{script}-").removesuffix(".log"),)
            )
            if markers != expected_markers:
                raise RollingFCRReferenceNormalizationError(
                    f"log run marker/segment order mismatch for {artifact.relative_path}: "
                    f"expected {expected_markers}, observed {markers}"
                )
            marker_matches = tuple(_RUN_MARKER.finditer(text))
            for index, match in enumerate(marker_matches):
                end = (
                    marker_matches[index + 1].start()
                    if index + 1 < len(marker_matches)
                    else len(text)
                )
                delivery_date = date.fromisoformat(match.group(1))
                identity = f"script-{script}:{delivery_date.isoformat()}"
                result[(profile, delivery_date)] = (
                    artifact,
                    _parse_log_segment(text[match.start():end], identity=identity),
                )
    expected_keys = {
        (profile, delivery_date)
        for _profile_id, profile, _script, _model, _time, _behavior, _paper, _workbook
        in _PROFILE_DATA
        for delivery_date in ROLLING_FCR_REFERENCE_DATES
    }
    if set(result) != expected_keys:
        raise RollingFCRReferenceNormalizationError(
            "log segmentation did not yield exact five-by-four coverage"
        )
    return MappingProxyType(result)


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RollingFCRReferenceNormalizationError(f"{field_name} must be an object")
    return {str(key): inner for key, inner in value.items()}


def _finite_vector(value: object, *, field_name: str, count: int) -> tuple[float, ...]:
    values = tuple(
        _finite(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(_sequence(value, field_name=field_name))
    )
    if len(values) != count:
        raise RollingFCRReferenceNormalizationError(
            f"{field_name} must contain exactly {count} values"
        )
    return values


def _reconcile_source_and_log(
    source: Mapping[str, Any], log: _LogEvidence, *, identity: str
) -> tuple[float, float, float]:
    objective = _finite(source.get("objective value"), field_name=f"{identity} objective")
    bound = _finite(source.get("objective bound"), field_name=f"{identity} bound")
    runtime = _finite(source.get("solve_time"), field_name=f"{identity} solve_time")
    runtime_tolerance = max(0.000500001, abs(log.runtime_seconds) * 5e-6)
    for field_name, source_value, precise_value, displayed_value, tolerance in (
        ("objective", objective, log.objective, log.displayed_objective, 0.000500001),
        ("bound", bound, log.bound, log.displayed_bound, 0.000500001),
        ("solve_time", runtime, log.runtime_seconds, log.runtime_seconds, runtime_tolerance),
    ):
        if abs(source_value - precise_value) > tolerance:
            raise RollingFCRReferenceNormalizationError(
                f"{identity} {field_name} does not reconcile JSON and log evidence"
            )
        display_tolerance = max(tolerance, 1e-5 * max(abs(source_value), 1.0))
        if abs(source_value - displayed_value) > display_tolerance:
            raise RollingFCRReferenceNormalizationError(
                f"{identity} displayed {field_name} does not reconcile JSON and log"
            )
    if bound + 1e-12 < objective:
        raise RollingFCRReferenceNormalizationError(
            f"{identity} maximization bound is below its incumbent"
        )
    return objective, bound, runtime


def _select_current(
    source: Mapping[str, Any], *, profile: int, delivery_date: date
) -> dict[str, Any]:
    backtest = _require_mapping(source.get("bt"), field_name="bt")
    key = (
        "curr_org"
        if profile == 4
        and delivery_date != ROLLING_FCR_REFERENCE_DATES[-1]
        and "curr_org" in backtest
        else "curr"
    )
    return _require_mapping(backtest.get(key), field_name=f"bt.{key}")


def _build_problem_input(
    *,
    profile_id: str,
    delivery_date: date,
    source: Mapping[str, Any],
) -> RollingFCRReferenceProblemInput:
    case = _require_mapping(source.get("case_data"), field_name="case_data")
    prices = _finite_vector(
        case.get("p0"),
        field_name="case_data.p0",
        count=len(_sequence(case.get("p0"), field_name="case_data.p0")),
    )
    fcr_prices = _finite_vector(
        case.get("pr"),
        field_name="case_data.pr",
        count=len(_sequence(case.get("pr"), field_name="case_data.pr")),
    )
    if len(prices) not in {24, 40} or len(fcr_prices) not in {6, 10}:
        raise RollingFCRReferenceNormalizationError(
            "source prices must use ordinary 24/6 or rolling 40/10 coverage"
        )
    energy_current = prices[-24:]
    fcr_current = fcr_prices[-6:]
    battery = {
        "maximum_charge_power_kw": _finite(case.get("x̅"), field_name="case_data.x̅"),
        "maximum_discharge_power_kw": abs(
            _finite(case.get("x̲"), field_name="case_data.x̲")
        ),
        "minimum_stored_energy_kwh": _finite(case.get("y̲"), field_name="case_data.y̲"),
        "maximum_stored_energy_kwh": _finite(case.get("y̅"), field_name="case_data.y̅"),
        "initial_stored_energy_kwh": _finite(case.get("y0"), field_name="case_data.y0"),
        "charge_efficiency": _finite(case.get("ηc"), field_name="case_data.ηc"),
        "discharge_efficiency": _finite(case.get("ηd"), field_name="case_data.ηd"),
        "source_power_sign": "positive_is_discharge",
    }
    uncertainty = {
        "recovery_activation_budget_hours": _finite(
            case.get("γ"), field_name="case_data.γ"
        ),
        "recovery_window_hours": _finite(case.get("Γ"), field_name="case_data.Γ"),
        "horizon_activation_budget_hours": 2.75,
        "derivation_rule": "covering-window-budget-v1",
        "pointwise_activation_bounds": [-1.0, 1.0],
    }
    terminal = {
        "minimum_terminal_stored_energy_kwh": _finite(
            case.get("ylK"), field_name="case_data.ylK"
        ),
        "shortfall_penalty_eur_per_kwh": _finite(
            case.get("psoc"), field_name="case_data.psoc"
        ),
        "allow_penalized_shortfall": True,
        "source_formula": "y0 - delta_t * sum(alpha[k]) >= ylK - syK[2]",
    }
    return RollingFCRReferenceProblemInput(
        profile_id=profile_id,
        delivery_date=delivery_date,
        battery=battery,
        day_ahead_prices_eur_per_kwh=energy_current,
        fcr_prices_eur_per_kw_block=fcr_current,
        uncertainty=uncertainty,
        terminal_rule=terminal,
    )


def _build_accepted_overlap(
    *, source: Mapping[str, Any], delivery_date: date
) -> RollingFCRReferenceAcceptedOverlap:
    case = _require_mapping(source.get("case_data"), field_name="case_data")
    backtest = _require_mapping(source.get("bt"), field_name="bt")
    previous = _require_mapping(backtest.get("prev"), field_name="bt.prev")
    energy = _finite_vector(previous.get("x0"), field_name="bt.prev.x0", count=16)
    fcr = _finite_vector(previous.get("xr"), field_name="bt.prev.xr", count=4)
    prices = _finite_vector(case.get("p0"), field_name="case_data.p0", count=40)
    fcr_prices = _finite_vector(case.get("pr"), field_name="case_data.pr", count=10)
    fixed_tail = sum(price * decision for price, decision in zip(prices[:16], energy))
    fixed_tail += sum(
        price * decision for price, decision in zip(fcr_prices[:4], fcr)
    )
    return RollingFCRReferenceAcceptedOverlap(
        predecessor_delivery_date=delivery_date.fromordinal(delivery_date.toordinal() - 1),
        hourly_energy_source_positive_discharge_kw=energy,
        fcr_capacity_kw=fcr,
        fixed_tail_objective_eur=fixed_tail,
    )


def _validate_case_profile(
    *,
    source: Mapping[str, Any],
    profile: int,
    model_type: str,
    bidding_time: float,
    delivery_date: date,
) -> None:
    if source.get("test_date") != delivery_date.isoformat():
        raise RollingFCRReferenceNormalizationError(
            "source JSON test_date does not match its explicit manifest identity"
        )
    case = _require_mapping(source.get("case_data"), field_name="case_data")
    expected_limit = 900.0 if profile in {4, 5} else 3600.0
    exact = {
        "K": 96,
        "model_type": model_type,
        "intraday_trading": False,
        "cst_reg_periods": 16,
        "solver": "Gurobi",
    }
    for name, expected in exact.items():
        if case.get(name) != expected:
            raise RollingFCRReferenceNormalizationError(
                f"case_data.{name} does not match profile {profile}"
            )
    expected_bidding_time = (
        24.0
        if profile == 4 and delivery_date == ROLLING_FCR_REFERENCE_DATES[0]
        else bidding_time
    )
    if abs(
        _finite(case.get("bidding_time"), field_name="bidding_time")
        - expected_bidding_time
    ) > 1e-12:
        raise RollingFCRReferenceNormalizationError(
            f"case_data.bidding_time does not match profile {profile}"
        )
    if abs(_finite(case.get("timelimit"), field_name="timelimit") - expected_limit) > 1e-12:
        raise RollingFCRReferenceNormalizationError(
            f"case_data.timelimit does not match profile {profile}"
        )


def _build_fixture(
    *,
    manifest: Mapping[str, Any],
    artifacts: tuple[_InputArtifact, ...],
) -> RollingFCRReferenceFixture:
    logs = _parse_logs(artifacts)
    problem_inputs: list[RollingFCRReferenceProblemInput] = []
    solve_records: list[RollingFCRReferenceSolveRecord] = []
    delivery_records: list[RollingFCRReferenceDeliveryEvidence] = []
    parsed_sources: dict[tuple[int, date], tuple[_InputArtifact, dict[str, Any]]] = {}

    for (
        profile_id,
        profile,
        script,
        model_type,
        bidding_time,
        _behavior,
        _paper,
        _workbook,
    ) in _PROFILE_DATA:
        for delivery_date in ROLLING_FCR_REFERENCE_DATES:
            json_artifact = _artifact_by_path(
                artifacts,
                f"results/{profile:02d}/{delivery_date.isoformat()}.json",
            )
            source = _parse_json_artifact(json_artifact)
            parsed_sources[(profile, delivery_date)] = (json_artifact, source)
            _validate_case_profile(
                source=source,
                profile=profile,
                model_type=model_type,
                bidding_time=bidding_time,
                delivery_date=delivery_date,
            )
            log_artifact, log = logs[(profile, delivery_date)]
            identity = f"profile {profile} {delivery_date.isoformat()}"
            objective, bound, _source_runtime = _reconcile_source_and_log(
                source, log, identity=identity
            )
            current = _select_current(
                source, profile=profile, delivery_date=delivery_date
            )
            energy = _finite_vector(current.get("x0"), field_name="current.x0", count=24)
            fcr = _finite_vector(current.get("xr"), field_name="current.xr", count=6)
            if profile == 3 and any(value != 0.0 for value in fcr):
                raise RollingFCRReferenceNormalizationError(
                    "script 13 must retain six exact zero FCR decisions"
                )
            overlap = (
                _build_accepted_overlap(source=source, delivery_date=delivery_date)
                if profile == 4 and delivery_date != ROLLING_FCR_REFERENCE_DATES[0]
                else None
            )
            absolute_gap = max(0.0, bound - objective)
            relative_gap = absolute_gap / max(abs(objective), abs(bound), 1.0)
            solve_records.append(
                RollingFCRReferenceSolveRecord(
                    profile_id=profile_id,
                    delivery_date=delivery_date,
                    source_json_artifact_id=json_artifact.artifact_id,
                    source_log_artifact_id=log_artifact.artifact_id,
                    solver_evidence=RollingFCRSourceSolverEvidence(
                        termination_condition=log.termination_condition,
                        primal_status=log.primal_status,
                        dual_status=log.dual_status,
                        incumbent_available=True,
                        source_evidence="combined",
                    ),
                    objective_eur=objective,
                    best_upper_bound_eur=bound,
                    absolute_gap_eur=absolute_gap,
                    relative_gap=relative_gap,
                    runtime_seconds=log.runtime_seconds,
                    hourly_energy_source_positive_discharge_kw=energy,
                    fcr_capacity_kw=fcr,
                    initial_stored_energy_kwh=_finite(
                        current.get("soc_initial"), field_name="current.soc_initial"
                    ),
                    cutoff_stored_energy_kwh=(
                        _finite(current.get("soc_bid"), field_name="current.soc_bid")
                        if profile == 4
                        else None
                    ),
                    terminal_stored_energy_kwh=_finite(
                        current.get("soc_terminal"), field_name="current.soc_terminal"
                    ),
                    accepted_overlap=overlap,
                    modeled_feasibility_claim="unavailable_pending_independent_audit",
                )
            )
            problem_inputs.append(
                _build_problem_input(
                    profile_id=profile_id,
                    delivery_date=delivery_date,
                    source=source,
                )
            )
            predecessor = (
                date.fromordinal(delivery_date.toordinal() - 1)
                if profile in {3, 4, 5}
                and delivery_date != ROLLING_FCR_REFERENCE_DATES[0]
                else None
            )
            if profile == 4:
                lifecycle = (
                    "initialization_only"
                    if delivery_date == ROLLING_FCR_REFERENCE_DATES[0]
                    else "unfinalized"
                    if delivery_date == ROLLING_FCR_REFERENCE_DATES[-1]
                    else "finalized"
                )
            elif profile in {3, 5}:
                lifecycle = "finalized"
            else:
                lifecycle = "independent_complete"
            delivery_records.append(
                RollingFCRReferenceDeliveryEvidence(
                    profile_id=profile_id,
                    delivery_date=delivery_date,
                    source_lifecycle_status=lifecycle,
                    predecessor_delivery_date=predecessor,
                    original_evidence_available=True,
                    finalized_evidence_available=lifecycle
                    in {"independent_complete", "finalized"},
                    activation_samples_redistributed=False,
                )
            )

    governed_artifact = _artifact_by_path(
        artifacts,
        "tests/fixtures/fcr_bidding/"
        "robust_storage_bidding_2023-06-18_restriction_v1.json",
        root_kind="repository",
    )
    governed = _parse_json_artifact(governed_artifact)
    provenance = _require_mapping(
        governed.get("reference_provenance"),
        field_name="Feature 013 reference_provenance",
    )
    recorded = _require_mapping(
        governed.get("recorded_result"), field_name="Feature 013 recorded_result"
    )
    rerun_artifact, rerun = parsed_sources[(2, date(2023, 6, 18))]
    rerun_current = _select_current(rerun, profile=2, delivery_date=date(2023, 6, 18))
    semantic_pairs = (
        ("objective_value_eur", recorded.get("objective_value_eur"), rerun.get("objective value")),
        ("objective_bound_eur", recorded.get("objective_bound_eur"), rerun.get("objective bound")),
        ("rounded_x0_kw", recorded.get("rounded_x0_kw"), rerun_current.get("x0")),
        ("rounded_xr_kw", recorded.get("rounded_xr_kw"), rerun_current.get("xr")),
    )
    if any(left != right for _name, left, right in semantic_pairs):
        mismatches = [name for name, left, right in semantic_pairs if left != right]
        raise RollingFCRReferenceNormalizationError(
            "Feature 013 governed result and Experiment 2 rerun do not reconcile "
            f"semantic fields: {mismatches}"
        )

    raw_manifest = tuple(
        RollingFCRReferenceRawArtifact(
            artifact_id=item.artifact_id,
            artifact_kind=item.artifact_kind,
            logical_source_path=item.relative_path,
            sha256=item.sha256,
            used_fields=item.used_fields,
            redistributed=False,
        )
        for item in artifacts
    )
    crosswalk = tuple(
        RollingFCRReferenceProfileCrosswalk(
            profile_id=profile_id,
            script=f"code/{script}.jl",
            result_directory=f"results/{profile:02d}",
            executable_behavior=behavior,
            paper_experiment=paper,
            workbook_column=workbook,
            mapping_status="reconciled_by_behavior",
            table_a1_claim="not_claimed_by_bounded_fixture",
        )
        for profile_id, profile, script, _model, _time, behavior, paper, workbook
        in _PROFILE_DATA
    )
    return RollingFCRReferenceFixture(
        schema_version=ROLLING_FCR_REFERENCE_FIXTURE_SCHEMA_VERSION,
        fixture_id=ROLLING_FCR_REFERENCE_FIXTURE_ID,
        reference_provenance=RollingFCRReferenceProvenance(
            reference_repository="robust_storage_bidding",
            reference_revision=manifest["reference_revision"],
            source_kind="generated-untracked-bounded-rerun-evidence",
            runtime_evidence=manifest["runtime_evidence"],
            committed_environment=manifest["committed_environment"],
            readme_claims=manifest["readme_claims"],
            normalizer_version=ROLLING_FCR_REFERENCE_NORMALIZER_VERSION,
        ),
        raw_input_manifest=raw_manifest,
        profile_crosswalk=crosswalk,
        study_window={
            "ordered_dates": [item.isoformat() for item in ROLLING_FCR_REFERENCE_DATES],
            "primary_comparison_dates": [
                item.isoformat() for item in ROLLING_FCR_REFERENCE_DATES[1:3]
            ],
            "edge_policy": {
                "rolling_0800_first_date": "initialization_only",
                "rolling_0800_last_date": "unfinalized",
            },
        },
        problem_inputs=tuple(problem_inputs),
        solve_records=tuple(solve_records),
        delivery_evidence=tuple(delivery_records),
        precision_policy=RollingFCRReferencePrecisionPolicy(
            source_decimal_places=3,
            decision_interval_rule=(
                "closed-half-displayed-unit-with-recorded-julia-endpoint-policy-v1"
            ),
            objective_interval_rule=(
                "closed-half-displayed-unit-plus-native-tolerance-v1"
            ),
            state_rounding_rule=(
                "decimal-string-three-place-half-even-normalized-zero-v1"
            ),
            joint_certificate_required=True,
            restriction_bilinear_violations_is_feasibility_evidence=False,
        ),
        feature_013_cross_check=RollingFCRFeature013CrossCheck(
            governed_fixture_preserved=True,
            governed_raw_sha256=_text(
                provenance.get("original_result_sha256"),
                field_name="Feature 013 governed raw SHA-256",
            ),
            rerun_raw_sha256=rerun_artifact.sha256,
            semantic_fields_compared=tuple(name for name, _left, _right in semantic_pairs),
            semantic_outcome="displayed_objective_bound_and_30_decisions_match",
        ),
        discrepancies=(
            RollingFCRReferenceDiscrepancy(
                code="script-13-time-limit-vs-paper-profile",
                scope="script-13-versus-paper-experiment-4",
                description=(
                    "Script 13 inherits the 3,600-second default while the compared "
                    "rolling source profiles set 900 seconds explicitly."
                ),
                effect_on_claims=(
                    "Termination and runtime evidence are interpreted by executable "
                    "script rather than inferred from the paper label."
                ),
            ),
            RollingFCRReferenceDiscrepancy(
                code="workbook-energy-metric-vs-paper-output",
                scope="results/result_overview.xlsx",
                description=(
                    "The workbook energy column applies charging input times charging "
                    "efficiency and is not the paper's discharge-energy output metric."
                ),
                effect_on_claims=(
                    "The bounded fixture does not compare or claim the paper energy metric."
                ),
            ),
            RollingFCRReferenceDiscrepancy(
                code="bounded-fixture-not-table-a1",
                scope="2023-06-17-through-2023-06-20",
                description=(
                    "The bounded four-day rerun cannot establish full-history Table A1 aggregates."
                ),
                effect_on_claims="No Table A1 parity claim is permitted.",
            ),
        ),
        unavailable_fields=(
            RollingFCRReferenceUnavailableField(
                field_path="source.unrounded_decisions",
                reason="Source JSON persists market decisions only to three decimals.",
                required_for=("exact_decision_parity", "exact_rolling_restart"),
            ),
            RollingFCRReferenceUnavailableField(
                field_path="source.restriction_independent_residual_audit",
                reason=(
                    "Restriction JSON has no independent equation-family residual audit; "
                    "bilinear_violations=0 is not feasibility evidence."
                ),
                required_for=("source_feasibility_proof",),
            ),
            RollingFCRReferenceUnavailableField(
                field_path="profiles.script-14.exact_full_precision_restart",
                reason=(
                    "The source did not persist the full-precision predecessor decisions "
                    "fixed in the next 08:00 solve."
                ),
                required_for=("exact_cross_day_restart_parity",),
            ),
            RollingFCRReferenceUnavailableField(
                field_path="source.feature_012_schedule_fingerprints",
                reason="The Julia source predates Feature 012 schedule identities.",
                required_for=("exact_schedule_fingerprint_parity",),
            ),
            RollingFCRReferenceUnavailableField(
                field_path="source.activation_samples",
                reason="The complete external activation trace is not redistributed.",
                required_for=("realized_replay", "realized_settlement"),
            ),
        ),
        redistribution_status=RollingFCRReferenceRedistributionStatus(
            fixture_contains_raw_logs=False,
            fixture_contains_raw_json=False,
            fixture_contains_workbook=False,
            fixture_contains_activation_samples=False,
            fixture_contains_machine_or_license_data=False,
            normalized_fields_only=True,
        ),
    )


def _semantic_differences(
    committed: object, candidate: object, *, path: str = "$"
) -> tuple[dict[str, object], ...]:
    differences: list[dict[str, object]] = []
    if isinstance(committed, Mapping) and isinstance(candidate, Mapping):
        for key in sorted(set(committed) | set(candidate), key=str):
            child = f"{path}.{key}"
            if key not in committed:
                differences.append(
                    {"field_path": child, "status": "added", "committed": None, "candidate": candidate[key]}
                )
            elif key not in candidate:
                differences.append(
                    {"field_path": child, "status": "removed", "committed": committed[key], "candidate": None}
                )
            else:
                differences.extend(
                    _semantic_differences(committed[key], candidate[key], path=child)
                )
    elif isinstance(committed, list) and isinstance(candidate, list):
        maximum = max(len(committed), len(candidate))
        for index in range(maximum):
            child = f"{path}[{index}]"
            if index >= len(committed):
                differences.append(
                    {"field_path": child, "status": "added", "committed": None, "candidate": candidate[index]}
                )
            elif index >= len(candidate):
                differences.append(
                    {"field_path": child, "status": "removed", "committed": committed[index], "candidate": None}
                )
            else:
                differences.extend(
                    _semantic_differences(committed[index], candidate[index], path=child)
                )
    elif committed != candidate:
        differences.append(
            {"field_path": path, "status": "changed", "committed": committed, "candidate": candidate}
        )
    return tuple(differences)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def normalize_rolling_fcr_reference_fixture(
    *,
    source_root: str | Path,
    input_manifest: str | Path,
    destination_dir: str | Path,
    committed_fixture: str | Path = _COMMITTED_FIXTURE,
) -> RollingFCRReferenceNormalizationResult:
    """Verify, normalize, validate, and atomically write one candidate fixture."""

    selected_source = Path(source_root)
    selected_manifest = Path(input_manifest)
    selected_destination = Path(destination_dir)
    artifact_root = _ARTIFACT_ROOT.resolve()
    destination = selected_destination.resolve()
    if destination == artifact_root or not destination.is_relative_to(artifact_root):
        raise RollingFCRReferenceNormalizationError(
            "normalizer destination must be a child directory beneath artifacts"
        )
    manifest, artifacts, manifest_sha = _read_input_manifest(
        source_root=selected_source,
        input_manifest=selected_manifest,
    )
    raw_digests = _verify_all_digests(artifacts)
    fixture = _build_fixture(manifest=manifest, artifacts=artifacts)
    candidate_payload = fixture.to_dict()
    candidate_bytes = _canonical_bytes(candidate_payload, pretty=True)

    committed_path = Path(committed_fixture)
    if committed_path.is_file():
        try:
            committed_payload = json.loads(committed_path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RollingFCRReferenceNormalizationError(
                f"committed comparison fixture is invalid: {exc}"
            ) from exc
        differences = _semantic_differences(committed_payload, candidate_payload)
    else:
        differences = (
            {
                "field_path": "$",
                "status": "candidate_only",
                "committed": None,
                "candidate": {
                    "fixture_id": fixture.fixture_id,
                    "fixture_fingerprint": fixture.fixture_fingerprint,
                },
            },
        )
    ordered_differences = tuple(
        sorted(differences, key=lambda item: str(item["field_path"]))
    )
    diff_payload = {
        "schema_version": "fcr-rolling-reference-semantic-diff-v1",
        "fixture_id": fixture.fixture_id,
        "candidate_fingerprint": fixture.fixture_fingerprint,
        "committed_fingerprint": (
            committed_payload.get("fixture_fingerprint")
            if committed_path.is_file() and isinstance(committed_payload, Mapping)
            else None
        ),
        "semantic_differences": list(ordered_differences),
    }
    destination.mkdir(parents=True, exist_ok=True)
    candidate_path = destination / _CANDIDATE_NAME
    diff_path = destination / _DIFF_NAME

    validation_temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination,
            prefix=f".{_CANDIDATE_NAME}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            validation_temp = Path(handle.name)
            handle.write(candidate_bytes)
        load_rolling_fcr_reference_fixture(validation_temp)
    finally:
        if validation_temp is not None:
            validation_temp.unlink(missing_ok=True)
    _atomic_write(candidate_path, candidate_bytes)
    _atomic_write(diff_path, _canonical_bytes(diff_payload, pretty=True))
    return RollingFCRReferenceNormalizationResult(
        candidate_path=candidate_path,
        semantic_diff_path=diff_path,
        input_manifest_sha256=manifest_sha,
        raw_artifact_fingerprints=raw_digests,
        semantic_differences=ordered_differences,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize explicit Feature 015 Julia/Gurobi evidence."
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--destination-dir", type=Path, required=True)
    parser.add_argument("--committed-fixture", type=Path, default=_COMMITTED_FIXTURE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = normalize_rolling_fcr_reference_fixture(
        source_root=args.source_root,
        input_manifest=args.input_manifest,
        destination_dir=args.destination_dir,
        committed_fixture=args.committed_fixture,
    )
    print(f"candidate: {result.candidate_path}")
    print(f"semantic diff: {result.semantic_diff_path}")
    print(f"input manifest SHA-256: {result.input_manifest_sha256}")
    print(f"semantic differences: {len(result.semantic_differences)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a maintainer command
    raise SystemExit(main())


__all__ = [
    "RollingFCRReferenceNormalizationError",
    "RollingFCRReferenceNormalizationResult",
    "normalize_rolling_fcr_reference_fixture",
]
