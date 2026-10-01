"""Strict offline evidence and comparison for Feature 015 rolling studies.

The module reads only the normalized fixture path explicitly selected by the
caller.  It never resolves the raw Julia rerun, imports an optimization
backend, invokes a process, or inspects environment state.  Source rounding,
source termination, native feasibility, and lifecycle completeness remain
separate evidence dimensions throughout comparison.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import partial
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any

from open_energy_lab.core.validation import finite, integer, non_negative
from open_energy_lab.control.fcr_rolling_backtest import (
    DeliveryDateRecordEnvelope,
    RollingFCRDayRevision,
    RollingFCRStudyManifest,
    RollingFCRStudyResult,
    RollingFCRValidationError,
    _stable_runtime,
)
from open_energy_lab.control.robust_fcr_bidding import _deep_freeze, _fingerprint, _sha256, _thaw


ROLLING_FCR_REFERENCE_FIXTURE_SCHEMA_VERSION = "fcr-rolling-reference-fixture-v1"
ROLLING_FCR_REFERENCE_FIXTURE_ID = (
    "robust-storage-bidding-experiments-01-05-2023-06-17-20-v1"
)
ROLLING_FCR_REFERENCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
ROLLING_FCR_REFERENCE_NORMALIZER_VERSION = "oel-fcr-rolling-normalizer-v1"
ROLLING_FCR_REFERENCE_OUTCOMES = (
    "exact_displayed_decision_parity",
    "source_precision_compatible",
    "alternative_optimum_compatible",
    "source_incumbent_equivalent",
    "improved_feasible_incumbent_compatible_with_source_bound",
    "bound_incompatible",
    "mismatch",
    "unavailable",
    "incomplete_or_unfinalized",
)
ROLLING_FCR_REFERENCE_COMPATIBLE_OUTCOMES = frozenset(
    ROLLING_FCR_REFERENCE_OUTCOMES[:5]
)
ROLLING_FCR_REFERENCE_PROFILE_IDS = (
    "script-11-relaxation-reset-midnight-v1",
    "script-12-restriction-reset-midnight-v1",
    "script-13-arbitrage-only-midnight-v1",
    "script-14-restriction-rolling-0800-v1",
    "script-15-restriction-rolling-midnight-v1",
)
ROLLING_FCR_REFERENCE_DATES = tuple(date(2023, 6, day) for day in range(17, 21))

_FIXTURE_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "fixture_id",
        "reference_provenance",
        "raw_input_manifest",
        "profile_crosswalk",
        "study_window",
        "problem_inputs",
        "solve_records",
        "delivery_evidence",
        "precision_policy",
        "feature_013_cross_check",
        "discrepancies",
        "unavailable_fields",
        "redistribution_status",
        "fixture_fingerprint",
    }
)


def _strict_mapping(
    value: object,
    *,
    field_name: str,
    required_keys: frozenset[str] | set[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RollingFCRValidationError(f"{field_name} must be a JSON object")
    result = {str(key): inner for key, inner in value.items()}
    expected = set(required_keys)
    if set(result) != expected:
        raise RollingFCRValidationError(
            f"{field_name} must use the exact field set; "
            f"missing={sorted(expected - set(result))}, "
            f"unexpected={sorted(set(result) - expected)}"
        )
    return result


def _sequence(
    value: object,
    *,
    field_name: str,
    count: int | None = None,
) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RollingFCRValidationError(f"{field_name} must be a JSON array")
    result = tuple(value)
    if count is not None and len(result) != count:
        raise RollingFCRValidationError(
            f"{field_name} must contain exactly {count} entries"
        )
    return result


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RollingFCRValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _enum(value: object, allowed: set[str] | frozenset[str], *, field_name: str) -> str:
    result = _text(value, field_name=field_name)
    if result not in allowed:
        raise RollingFCRValidationError(
            f"{field_name} must be one of {sorted(allowed)}, found {result!r}"
        )
    return result


_finite = partial(finite, error=RollingFCRValidationError, normalize_zero=True)


def _optional_finite(value: object, *, field_name: str) -> float | None:
    return None if value is None else _finite(value, field_name=field_name)


_non_negative = partial(non_negative, error=RollingFCRValidationError, normalize_zero=True)
_integer = partial(integer, error=RollingFCRValidationError, minimum=0)


def _date(value: object, *, field_name: str) -> date:
    if not isinstance(value, str):
        raise RollingFCRValidationError(f"{field_name} must be an ISO date")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise RollingFCRValidationError(f"{field_name} must be an ISO date") from exc
    return result


_sha = _sha256


def _finite_tuple(
    value: object,
    *,
    field_name: str,
    count: int,
    non_negative: bool = False,
) -> tuple[float, ...]:
    result = tuple(
        _finite(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(_sequence(value, field_name=field_name, count=count))
    )
    if non_negative and any(item < 0.0 for item in result):
        raise RollingFCRValidationError(f"{field_name} must be non-negative")
    return result


def _verify_fingerprint(
    provided: object,
    recomputed: str,
    *,
    field_name: str,
) -> None:
    normalized = _sha(provided, field_name=field_name)
    if normalized != recomputed:
        raise RollingFCRValidationError(
            f"{field_name} fingerprint mismatch: provided={normalized}, "
            f"recomputed={recomputed}"
        )


def _frozen_string_mapping(
    value: object,
    *,
    field_name: str,
    required_keys: set[str] | frozenset[str] | None = None,
) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise RollingFCRValidationError(f"{field_name} must be a mapping")
    result = {
        _text(key, field_name=f"{field_name} key"): _text(
            inner, field_name=f"{field_name}.{key}"
        )
        for key, inner in value.items()
    }
    if required_keys is not None and set(result) != set(required_keys):
        raise RollingFCRValidationError(
            f"{field_name} must contain exactly {sorted(required_keys)}"
        )
    return MappingProxyType(dict(sorted(result.items())))


def source_precision_interval(
    displayed_value: float,
    half_unit: float,
) -> tuple[float, float]:
    """Return exact decimal closed endpoints without binary widening."""

    center = Decimal(str(_finite(displayed_value, field_name="displayed_value")))
    half = Decimal(str(_non_negative(half_unit, field_name="half_unit")))
    return float(center - half), float(center + half)


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceProvenance:
    reference_repository: str
    reference_revision: str
    source_kind: str
    runtime_evidence: Mapping[str, str]
    committed_environment: Mapping[str, str]
    readme_claims: Mapping[str, str]
    normalizer_version: str
    provenance_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.reference_repository != "robust_storage_bidding":
            raise RollingFCRValidationError("unsupported reference_repository")
        if self.reference_revision != ROLLING_FCR_REFERENCE_REVISION:
            raise RollingFCRValidationError("reference revision is not pinned")
        if self.source_kind != "generated-untracked-bounded-rerun-evidence":
            raise RollingFCRValidationError("unsupported reference source_kind")
        runtime = _frozen_string_mapping(
            self.runtime_evidence,
            field_name="runtime_evidence",
            required_keys={"julia_version", "gurobi_runtime_version"},
        )
        if dict(runtime) != {
            "gurobi_runtime_version": "11.0.3",
            "julia_version": "1.10.1",
        }:
            raise RollingFCRValidationError("runtime evidence does not match rerun")
        committed = _frozen_string_mapping(
            self.committed_environment,
            field_name="committed_environment",
            required_keys={"julia", "jump", "gurobi_jl", "gurobi_runtime"},
        )
        readme = _frozen_string_mapping(
            self.readme_claims,
            field_name="readme_claims",
            required_keys={"julia", "jump", "gurobi"},
        )
        object.__setattr__(self, "runtime_evidence", runtime)
        object.__setattr__(self, "committed_environment", committed)
        object.__setattr__(self, "readme_claims", readme)
        object.__setattr__(
            self,
            "normalizer_version",
            _text(self.normalizer_version, field_name="normalizer_version"),
        )
        object.__setattr__(self, "provenance_fingerprint", _fingerprint(self.to_dict()))

    def to_dict(self) -> dict[str, object]:
        return {
            "reference_repository": self.reference_repository,
            "reference_revision": self.reference_revision,
            "source_kind": self.source_kind,
            "runtime_evidence": dict(self.runtime_evidence),
            "committed_environment": dict(self.committed_environment),
            "readme_claims": dict(self.readme_claims),
            "normalizer_version": self.normalizer_version,
        }

    @classmethod
    def from_dict(cls, payload: object) -> RollingFCRReferenceProvenance:
        data = _strict_mapping(
            payload,
            field_name="reference_provenance",
            required_keys={
                "reference_repository",
                "reference_revision",
                "source_kind",
                "runtime_evidence",
                "committed_environment",
                "readme_claims",
                "normalizer_version",
            },
        )
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceRawArtifact:
    artifact_id: str
    artifact_kind: str
    logical_source_path: str
    sha256: str
    used_fields: tuple[str, ...]
    redistributed: bool
    artifact_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _text(self.artifact_id, field_name="artifact_id"))
        object.__setattr__(
            self,
            "artifact_kind",
            _enum(
                self.artifact_kind,
                {
                    "source",
                    "generated_json",
                    "generated_log",
                    "input_data",
                    "project",
                    "manifest",
                    "workbook",
                },
                field_name="artifact_kind",
            ),
        )
        logical_path = _text(self.logical_source_path, field_name="logical_source_path")
        if logical_path.startswith(("/", "~")) or ".." in Path(logical_path).parts:
            raise RollingFCRValidationError(
                "raw artifact paths must be logical relative identities"
            )
        object.__setattr__(self, "logical_source_path", logical_path)
        object.__setattr__(self, "sha256", _sha(self.sha256, field_name="artifact sha256"))
        fields = tuple(
            _text(item, field_name="used_fields") for item in self.used_fields
        )
        if not fields or len(set(fields)) != len(fields):
            raise RollingFCRValidationError("used_fields must be non-empty and unique")
        if self.redistributed is not False:
            raise RollingFCRValidationError("raw artifacts may not be redistributed")
        object.__setattr__(self, "used_fields", fields)
        object.__setattr__(self, "artifact_fingerprint", _fingerprint(self.to_dict()))

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "logical_source_path": self.logical_source_path,
            "sha256": self.sha256,
            "used_fields": list(self.used_fields),
            "redistributed": self.redistributed,
        }

    @classmethod
    def from_dict(cls, payload: object, *, index: int) -> RollingFCRReferenceRawArtifact:
        data = _strict_mapping(
            payload,
            field_name=f"raw_input_manifest[{index}]",
            required_keys={
                "artifact_id",
                "artifact_kind",
                "logical_source_path",
                "sha256",
                "used_fields",
                "redistributed",
            },
        )
        return cls(
            artifact_id=data["artifact_id"],  # type: ignore[arg-type]
            artifact_kind=data["artifact_kind"],  # type: ignore[arg-type]
            logical_source_path=data["logical_source_path"],  # type: ignore[arg-type]
            sha256=data["sha256"],  # type: ignore[arg-type]
            used_fields=tuple(
                _sequence(data["used_fields"], field_name="used_fields")
            ),  # type: ignore[arg-type]
            redistributed=data["redistributed"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceProfileCrosswalk:
    profile_id: str
    script: str
    result_directory: str
    executable_behavior: str
    paper_experiment: int
    workbook_column: str
    mapping_status: str
    table_a1_claim: str

    def __post_init__(self) -> None:
        if self.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
            raise RollingFCRValidationError("unsupported crosswalk profile_id")
        object.__setattr__(self, "script", _text(self.script, field_name="script"))
        object.__setattr__(
            self,
            "result_directory",
            _text(self.result_directory, field_name="result_directory"),
        )
        object.__setattr__(
            self,
            "executable_behavior",
            _text(self.executable_behavior, field_name="executable_behavior"),
        )
        _integer(self.paper_experiment, field_name="paper_experiment", minimum=1)
        object.__setattr__(
            self,
            "workbook_column",
            _text(self.workbook_column, field_name="workbook_column"),
        )
        if self.mapping_status not in {"reconciled_by_behavior", "unresolved"}:
            raise RollingFCRValidationError("unsupported crosswalk mapping_status")
        if self.table_a1_claim != "not_claimed_by_bounded_fixture":
            raise RollingFCRValidationError("bounded fixture cannot claim Table A1 parity")

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "script": self.script,
            "result_directory": self.result_directory,
            "executable_behavior": self.executable_behavior,
            "paper_experiment": self.paper_experiment,
            "workbook_column": self.workbook_column,
            "mapping_status": self.mapping_status,
            "table_a1_claim": self.table_a1_claim,
        }

    @classmethod
    def from_dict(cls, payload: object, *, index: int) -> RollingFCRReferenceProfileCrosswalk:
        data = _strict_mapping(
            payload,
            field_name=f"profile_crosswalk[{index}]",
            required_keys={
                "profile_id",
                "script",
                "result_directory",
                "executable_behavior",
                "paper_experiment",
                "workbook_column",
                "mapping_status",
                "table_a1_claim",
            },
        )
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceProblemInput:
    profile_id: str
    delivery_date: date
    battery: Mapping[str, object]
    day_ahead_prices_eur_per_kwh: tuple[float, ...]
    fcr_prices_eur_per_kw_block: tuple[float, ...]
    uncertainty: Mapping[str, object]
    terminal_rule: Mapping[str, object]
    input_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
            raise RollingFCRValidationError("unsupported problem-input profile_id")
        if self.delivery_date not in ROLLING_FCR_REFERENCE_DATES:
            raise RollingFCRValidationError("problem input date is outside bounded window")
        battery = _deep_freeze(self.battery, field_name="problem input battery")
        uncertainty = _deep_freeze(
            self.uncertainty, field_name="problem input uncertainty"
        )
        terminal = _deep_freeze(
            self.terminal_rule, field_name="problem input terminal_rule"
        )
        energy = _finite_tuple(
            self.day_ahead_prices_eur_per_kwh,
            field_name="day_ahead_prices_eur_per_kwh",
            count=24,
        )
        fcr = _finite_tuple(
            self.fcr_prices_eur_per_kw_block,
            field_name="fcr_prices_eur_per_kw_block",
            count=6,
        )
        object.__setattr__(self, "battery", battery)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "terminal_rule", terminal)
        object.__setattr__(self, "day_ahead_prices_eur_per_kwh", energy)
        object.__setattr__(self, "fcr_prices_eur_per_kw_block", fcr)
        object.__setattr__(self, "input_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "delivery_date": self.delivery_date.isoformat(),
            "battery": _thaw(self.battery),
            "day_ahead_prices_eur_per_kwh": list(
                self.day_ahead_prices_eur_per_kwh
            ),
            "fcr_prices_eur_per_kw_block": list(self.fcr_prices_eur_per_kw_block),
            "uncertainty": _thaw(self.uncertainty),
            "terminal_rule": _thaw(self.terminal_rule),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "input_fingerprint": self.input_fingerprint}

    @classmethod
    def from_dict(cls, payload: object, *, index: int) -> RollingFCRReferenceProblemInput:
        data = _strict_mapping(
            payload,
            field_name=f"problem_inputs[{index}]",
            required_keys={
                "profile_id",
                "delivery_date",
                "battery",
                "day_ahead_prices_eur_per_kwh",
                "fcr_prices_eur_per_kw_block",
                "uncertainty",
                "terminal_rule",
                "input_fingerprint",
            },
        )
        result = cls(
            profile_id=data["profile_id"],  # type: ignore[arg-type]
            delivery_date=_date(
                data["delivery_date"], field_name="problem input delivery_date"
            ),
            battery=data["battery"],  # type: ignore[arg-type]
            day_ahead_prices_eur_per_kwh=tuple(
                _sequence(
                    data["day_ahead_prices_eur_per_kwh"],
                    field_name="day_ahead_prices_eur_per_kwh",
                )
            ),  # type: ignore[arg-type]
            fcr_prices_eur_per_kw_block=tuple(
                _sequence(
                    data["fcr_prices_eur_per_kw_block"],
                    field_name="fcr_prices_eur_per_kw_block",
                )
            ),  # type: ignore[arg-type]
            uncertainty=data["uncertainty"],  # type: ignore[arg-type]
            terminal_rule=data["terminal_rule"],  # type: ignore[arg-type]
        )
        _verify_fingerprint(
            data["input_fingerprint"],
            result.input_fingerprint,
            field_name="problem input fingerprint",
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRSourceSolverEvidence:
    termination_condition: str
    primal_status: str
    dual_status: str
    incumbent_available: bool
    source_evidence: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "termination_condition",
            _enum(
                self.termination_condition,
                {"OPTIMAL", "TIME_LIMIT", "unavailable"},
                field_name="termination_condition",
            ),
        )
        object.__setattr__(
            self,
            "primal_status",
            _enum(
                self.primal_status,
                {"FEASIBLE_POINT", "unavailable"},
                field_name="primal_status",
            ),
        )
        object.__setattr__(
            self,
            "dual_status",
            _enum(
                self.dual_status,
                {"FEASIBLE_POINT", "NO_SOLUTION", "unavailable"},
                field_name="dual_status",
            ),
        )
        if not isinstance(self.incumbent_available, bool):
            raise RollingFCRValidationError("incumbent_available must be boolean")
        if self.incumbent_available and self.primal_status != "FEASIBLE_POINT":
            raise RollingFCRValidationError(
                "a source incumbent requires FEASIBLE_POINT primal status"
            )
        object.__setattr__(
            self,
            "source_evidence",
            _enum(
                self.source_evidence,
                {"generated_log", "generated_json", "combined"},
                field_name="source_evidence",
            ),
        )

    @property
    def is_optimal(self) -> bool:
        return self.termination_condition == "OPTIMAL"

    @property
    def is_time_limited_incumbent(self) -> bool:
        return (
            self.termination_condition == "TIME_LIMIT"
            and self.incumbent_available
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "termination_condition": self.termination_condition,
            "primal_status": self.primal_status,
            "dual_status": self.dual_status,
            "incumbent_available": self.incumbent_available,
            "source_evidence": self.source_evidence,
        }

    @classmethod
    def from_dict(cls, payload: object, *, field_name: str) -> RollingFCRSourceSolverEvidence:
        data = _strict_mapping(
            payload,
            field_name=field_name,
            required_keys={
                "termination_condition",
                "primal_status",
                "dual_status",
                "incumbent_available",
                "source_evidence",
            },
        )
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceAcceptedOverlap:
    predecessor_delivery_date: date
    hourly_energy_source_positive_discharge_kw: tuple[float, ...]
    fcr_capacity_kw: tuple[float, ...]
    fixed_tail_objective_eur: float
    overlap_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.predecessor_delivery_date not in ROLLING_FCR_REFERENCE_DATES:
            raise RollingFCRValidationError("overlap predecessor date is outside window")
        energy = _finite_tuple(
            self.hourly_energy_source_positive_discharge_kw,
            field_name="accepted overlap energy",
            count=16,
        )
        fcr = _finite_tuple(
            self.fcr_capacity_kw,
            field_name="accepted overlap FCR",
            count=4,
            non_negative=True,
        )
        object.__setattr__(self, "hourly_energy_source_positive_discharge_kw", energy)
        object.__setattr__(self, "fcr_capacity_kw", fcr)
        object.__setattr__(
            self,
            "fixed_tail_objective_eur",
            _finite(
                self.fixed_tail_objective_eur,
                field_name="fixed_tail_objective_eur",
            ),
        )
        object.__setattr__(self, "overlap_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "predecessor_delivery_date": self.predecessor_delivery_date.isoformat(),
            "hourly_energy_source_positive_discharge_kw": list(
                self.hourly_energy_source_positive_discharge_kw
            ),
            "fcr_capacity_kw": list(self.fcr_capacity_kw),
            "fixed_tail_objective_eur": self.fixed_tail_objective_eur,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "overlap_fingerprint": self.overlap_fingerprint}

    @classmethod
    def from_dict(cls, payload: object, *, field_name: str) -> RollingFCRReferenceAcceptedOverlap:
        data = _strict_mapping(
            payload,
            field_name=field_name,
            required_keys={
                "predecessor_delivery_date",
                "hourly_energy_source_positive_discharge_kw",
                "fcr_capacity_kw",
                "fixed_tail_objective_eur",
                "overlap_fingerprint",
            },
        )
        result = cls(
            predecessor_delivery_date=_date(
                data["predecessor_delivery_date"],
                field_name=f"{field_name}.predecessor_delivery_date",
            ),
            hourly_energy_source_positive_discharge_kw=tuple(
                _sequence(
                    data["hourly_energy_source_positive_discharge_kw"],
                    field_name=f"{field_name}.hourly_energy",
                )
            ),  # type: ignore[arg-type]
            fcr_capacity_kw=tuple(
                _sequence(
                    data["fcr_capacity_kw"], field_name=f"{field_name}.fcr_capacity"
                )
            ),  # type: ignore[arg-type]
            fixed_tail_objective_eur=data["fixed_tail_objective_eur"],  # type: ignore[arg-type]
        )
        _verify_fingerprint(
            data["overlap_fingerprint"],
            result.overlap_fingerprint,
            field_name=f"{field_name}.overlap_fingerprint",
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceSolveRecord:
    profile_id: str
    delivery_date: date
    source_json_artifact_id: str
    source_log_artifact_id: str
    solver_evidence: RollingFCRSourceSolverEvidence
    objective_eur: float
    best_upper_bound_eur: float
    absolute_gap_eur: float
    relative_gap: float
    runtime_seconds: float
    hourly_energy_source_positive_discharge_kw: tuple[float, ...]
    fcr_capacity_kw: tuple[float, ...]
    initial_stored_energy_kwh: float
    cutoff_stored_energy_kwh: float | None
    terminal_stored_energy_kwh: float
    accepted_overlap: RollingFCRReferenceAcceptedOverlap | None
    modeled_feasibility_claim: str
    record_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
            raise RollingFCRValidationError("unsupported solve-record profile_id")
        if self.delivery_date not in ROLLING_FCR_REFERENCE_DATES:
            raise RollingFCRValidationError("solve record date is outside bounded window")
        object.__setattr__(
            self,
            "source_json_artifact_id",
            _text(self.source_json_artifact_id, field_name="source_json_artifact_id"),
        )
        object.__setattr__(
            self,
            "source_log_artifact_id",
            _text(self.source_log_artifact_id, field_name="source_log_artifact_id"),
        )
        if not isinstance(self.solver_evidence, RollingFCRSourceSolverEvidence):
            raise RollingFCRValidationError("solver_evidence has the wrong type")
        objective = _finite(self.objective_eur, field_name="objective_eur")
        bound = _finite(self.best_upper_bound_eur, field_name="best_upper_bound_eur")
        if bound + 1e-12 < objective:
            raise RollingFCRValidationError(
                "source upper bound cannot be below its maximization incumbent"
            )
        absolute = _non_negative(self.absolute_gap_eur, field_name="absolute_gap_eur")
        relative = _non_negative(self.relative_gap, field_name="relative_gap")
        expected_absolute = max(0.0, bound - objective)
        if abs(absolute - expected_absolute) > 1e-9:
            raise RollingFCRValidationError("source absolute gap does not reconcile")
        expected_relative = expected_absolute / max(abs(objective), abs(bound), 1.0)
        if abs(relative - expected_relative) > 1e-9:
            raise RollingFCRValidationError("source relative gap does not reconcile")
        runtime = _non_negative(self.runtime_seconds, field_name="runtime_seconds")
        energy = _finite_tuple(
            self.hourly_energy_source_positive_discharge_kw,
            field_name="hourly_energy_source_positive_discharge_kw",
            count=24,
        )
        fcr = _finite_tuple(
            self.fcr_capacity_kw,
            field_name="fcr_capacity_kw",
            count=6,
            non_negative=True,
        )
        initial = _finite(
            self.initial_stored_energy_kwh,
            field_name="initial_stored_energy_kwh",
        )
        cutoff = _optional_finite(
            self.cutoff_stored_energy_kwh,
            field_name="cutoff_stored_energy_kwh",
        )
        terminal = _finite(
            self.terminal_stored_energy_kwh,
            field_name="terminal_stored_energy_kwh",
        )
        if self.accepted_overlap is not None and not isinstance(
            self.accepted_overlap, RollingFCRReferenceAcceptedOverlap
        ):
            raise RollingFCRValidationError("accepted_overlap has the wrong type")
        if self.profile_id == ROLLING_FCR_REFERENCE_PROFILE_IDS[3]:
            expected_overlap = self.delivery_date != ROLLING_FCR_REFERENCE_DATES[0]
            if (self.accepted_overlap is not None) != expected_overlap:
                raise RollingFCRValidationError(
                    "08:00 source records require overlap after initialization"
                )
        elif self.accepted_overlap is not None:
            raise RollingFCRValidationError(
                "accepted overlap applies only to the 08:00 source profile"
            )
        if self.modeled_feasibility_claim != "unavailable_pending_independent_audit":
            raise RollingFCRValidationError(
                "source JSON cannot claim independently audited feasibility"
            )
        object.__setattr__(self, "objective_eur", objective)
        object.__setattr__(self, "best_upper_bound_eur", bound)
        object.__setattr__(self, "absolute_gap_eur", absolute)
        object.__setattr__(self, "relative_gap", relative)
        object.__setattr__(self, "runtime_seconds", runtime)
        object.__setattr__(self, "hourly_energy_source_positive_discharge_kw", energy)
        object.__setattr__(self, "fcr_capacity_kw", fcr)
        object.__setattr__(self, "initial_stored_energy_kwh", initial)
        object.__setattr__(self, "cutoff_stored_energy_kwh", cutoff)
        object.__setattr__(self, "terminal_stored_energy_kwh", terminal)
        object.__setattr__(self, "record_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "delivery_date": self.delivery_date.isoformat(),
            "source_json_artifact_id": self.source_json_artifact_id,
            "source_log_artifact_id": self.source_log_artifact_id,
            "solver_evidence": self.solver_evidence.to_dict(),
            "objective_eur": self.objective_eur,
            "best_upper_bound_eur": self.best_upper_bound_eur,
            "absolute_gap_eur": self.absolute_gap_eur,
            "relative_gap": self.relative_gap,
            "runtime_seconds": self.runtime_seconds,
            "hourly_energy_source_positive_discharge_kw": list(
                self.hourly_energy_source_positive_discharge_kw
            ),
            "fcr_capacity_kw": list(self.fcr_capacity_kw),
            "initial_stored_energy_kwh": self.initial_stored_energy_kwh,
            "cutoff_stored_energy_kwh": self.cutoff_stored_energy_kwh,
            "terminal_stored_energy_kwh": self.terminal_stored_energy_kwh,
            "accepted_overlap": (
                None if self.accepted_overlap is None else self.accepted_overlap.to_dict()
            ),
            "modeled_feasibility_claim": self.modeled_feasibility_claim,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "record_fingerprint": self.record_fingerprint}

    @classmethod
    def from_dict(cls, payload: object, *, index: int) -> RollingFCRReferenceSolveRecord:
        field_name = f"solve_records[{index}]"
        data = _strict_mapping(
            payload,
            field_name=field_name,
            required_keys={
                "profile_id",
                "delivery_date",
                "source_json_artifact_id",
                "source_log_artifact_id",
                "solver_evidence",
                "objective_eur",
                "best_upper_bound_eur",
                "absolute_gap_eur",
                "relative_gap",
                "runtime_seconds",
                "hourly_energy_source_positive_discharge_kw",
                "fcr_capacity_kw",
                "initial_stored_energy_kwh",
                "cutoff_stored_energy_kwh",
                "terminal_stored_energy_kwh",
                "accepted_overlap",
                "modeled_feasibility_claim",
                "record_fingerprint",
            },
        )
        overlap = data["accepted_overlap"]
        result = cls(
            profile_id=data["profile_id"],  # type: ignore[arg-type]
            delivery_date=_date(
                data["delivery_date"], field_name=f"{field_name}.delivery_date"
            ),
            source_json_artifact_id=data["source_json_artifact_id"],  # type: ignore[arg-type]
            source_log_artifact_id=data["source_log_artifact_id"],  # type: ignore[arg-type]
            solver_evidence=RollingFCRSourceSolverEvidence.from_dict(
                data["solver_evidence"], field_name=f"{field_name}.solver_evidence"
            ),
            objective_eur=data["objective_eur"],  # type: ignore[arg-type]
            best_upper_bound_eur=data["best_upper_bound_eur"],  # type: ignore[arg-type]
            absolute_gap_eur=data["absolute_gap_eur"],  # type: ignore[arg-type]
            relative_gap=data["relative_gap"],  # type: ignore[arg-type]
            runtime_seconds=data["runtime_seconds"],  # type: ignore[arg-type]
            hourly_energy_source_positive_discharge_kw=tuple(
                _sequence(
                    data["hourly_energy_source_positive_discharge_kw"],
                    field_name=f"{field_name}.hourly_energy",
                )
            ),  # type: ignore[arg-type]
            fcr_capacity_kw=tuple(
                _sequence(
                    data["fcr_capacity_kw"], field_name=f"{field_name}.fcr_capacity"
                )
            ),  # type: ignore[arg-type]
            initial_stored_energy_kwh=data["initial_stored_energy_kwh"],  # type: ignore[arg-type]
            cutoff_stored_energy_kwh=data["cutoff_stored_energy_kwh"],  # type: ignore[arg-type]
            terminal_stored_energy_kwh=data["terminal_stored_energy_kwh"],  # type: ignore[arg-type]
            accepted_overlap=(
                None
                if overlap is None
                else RollingFCRReferenceAcceptedOverlap.from_dict(
                    overlap, field_name=f"{field_name}.accepted_overlap"
                )
            ),
            modeled_feasibility_claim=data["modeled_feasibility_claim"],  # type: ignore[arg-type]
        )
        _verify_fingerprint(
            data["record_fingerprint"],
            result.record_fingerprint,
            field_name=f"{field_name}.record_fingerprint",
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceDeliveryEvidence:
    profile_id: str
    delivery_date: date
    source_lifecycle_status: str
    predecessor_delivery_date: date | None
    original_evidence_available: bool
    finalized_evidence_available: bool
    activation_samples_redistributed: bool
    evidence_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
            raise RollingFCRValidationError("unsupported delivery-evidence profile_id")
        if self.delivery_date not in ROLLING_FCR_REFERENCE_DATES:
            raise RollingFCRValidationError("delivery evidence date is outside window")
        object.__setattr__(
            self,
            "source_lifecycle_status",
            _enum(
                self.source_lifecycle_status,
                {
                    "independent_complete",
                    "initialization_only",
                    "finalized",
                    "unfinalized",
                },
                field_name="source_lifecycle_status",
            ),
        )
        if self.predecessor_delivery_date is not None:
            if self.predecessor_delivery_date not in ROLLING_FCR_REFERENCE_DATES:
                raise RollingFCRValidationError(
                    "delivery predecessor date is outside bounded window"
                )
            if self.predecessor_delivery_date >= self.delivery_date:
                raise RollingFCRValidationError(
                    "delivery predecessor must precede its successor"
                )
        for name in (
            "original_evidence_available",
            "finalized_evidence_available",
            "activation_samples_redistributed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise RollingFCRValidationError(f"{name} must be boolean")
        if not self.original_evidence_available:
            raise RollingFCRValidationError(
                "every bounded source solve must retain original evidence"
            )
        expected_finalized = self.source_lifecycle_status in {
            "independent_complete",
            "finalized",
        }
        if self.finalized_evidence_available != expected_finalized:
            raise RollingFCRValidationError(
                "finalized source evidence does not reconcile lifecycle"
            )
        if self.activation_samples_redistributed:
            raise RollingFCRValidationError(
                "normalized fixture cannot redistribute activation samples"
            )
        object.__setattr__(self, "evidence_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "delivery_date": self.delivery_date.isoformat(),
            "source_lifecycle_status": self.source_lifecycle_status,
            "predecessor_delivery_date": (
                None
                if self.predecessor_delivery_date is None
                else self.predecessor_delivery_date.isoformat()
            ),
            "original_evidence_available": self.original_evidence_available,
            "finalized_evidence_available": self.finalized_evidence_available,
            "activation_samples_redistributed": self.activation_samples_redistributed,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "evidence_fingerprint": self.evidence_fingerprint}

    @classmethod
    def from_dict(cls, payload: object, *, index: int) -> RollingFCRReferenceDeliveryEvidence:
        field_name = f"delivery_evidence[{index}]"
        data = _strict_mapping(
            payload,
            field_name=field_name,
            required_keys={
                "profile_id",
                "delivery_date",
                "source_lifecycle_status",
                "predecessor_delivery_date",
                "original_evidence_available",
                "finalized_evidence_available",
                "activation_samples_redistributed",
                "evidence_fingerprint",
            },
        )
        predecessor = data["predecessor_delivery_date"]
        result = cls(
            profile_id=data["profile_id"],  # type: ignore[arg-type]
            delivery_date=_date(
                data["delivery_date"], field_name=f"{field_name}.delivery_date"
            ),
            source_lifecycle_status=data["source_lifecycle_status"],  # type: ignore[arg-type]
            predecessor_delivery_date=(
                None
                if predecessor is None
                else _date(predecessor, field_name=f"{field_name}.predecessor_date")
            ),
            original_evidence_available=data["original_evidence_available"],  # type: ignore[arg-type]
            finalized_evidence_available=data["finalized_evidence_available"],  # type: ignore[arg-type]
            activation_samples_redistributed=data[
                "activation_samples_redistributed"
            ],  # type: ignore[arg-type]
        )
        _verify_fingerprint(
            data["evidence_fingerprint"],
            result.evidence_fingerprint,
            field_name=f"{field_name}.evidence_fingerprint",
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRReferencePrecisionPolicy:
    source_decimal_places: int
    decision_interval_rule: str
    objective_interval_rule: str
    state_rounding_rule: str
    joint_certificate_required: bool
    restriction_bilinear_violations_is_feasibility_evidence: bool
    policy_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.source_decimal_places != 3:
            raise RollingFCRValidationError("source precision must be three decimals")
        expected = {
            "decision_interval_rule": (
                "closed-half-displayed-unit-with-recorded-julia-endpoint-policy-v1"
            ),
            "objective_interval_rule": (
                "closed-half-displayed-unit-plus-native-tolerance-v1"
            ),
            "state_rounding_rule": (
                "decimal-string-three-place-half-even-normalized-zero-v1"
            ),
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise RollingFCRValidationError(f"unsupported {name}")
        if self.joint_certificate_required is not True:
            raise RollingFCRValidationError("joint source certification is required")
        if self.restriction_bilinear_violations_is_feasibility_evidence is not False:
            raise RollingFCRValidationError(
                "bilinear_violations cannot be feasibility evidence"
            )
        object.__setattr__(self, "policy_fingerprint", _fingerprint(self.to_dict()))

    @property
    def half_unit(self) -> float:
        return 0.5 * (10.0 ** -self.source_decimal_places)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_decimal_places": self.source_decimal_places,
            "decision_interval_rule": self.decision_interval_rule,
            "objective_interval_rule": self.objective_interval_rule,
            "state_rounding_rule": self.state_rounding_rule,
            "joint_certificate_required": self.joint_certificate_required,
            "restriction_bilinear_violations_is_feasibility_evidence": (
                self.restriction_bilinear_violations_is_feasibility_evidence
            ),
        }

    @classmethod
    def from_dict(cls, payload: object) -> RollingFCRReferencePrecisionPolicy:
        data = _strict_mapping(
            payload,
            field_name="precision_policy",
            required_keys={
                "source_decimal_places",
                "decision_interval_rule",
                "objective_interval_rule",
                "state_rounding_rule",
                "joint_certificate_required",
                "restriction_bilinear_violations_is_feasibility_evidence",
            },
        )
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RollingFCRFeature013CrossCheck:
    governed_fixture_preserved: bool
    governed_raw_sha256: str
    rerun_raw_sha256: str
    semantic_fields_compared: tuple[str, ...]
    semantic_outcome: str
    cross_check_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.governed_fixture_preserved is not True:
            raise RollingFCRValidationError("Feature 013 fixture must be preserved")
        object.__setattr__(
            self,
            "governed_raw_sha256",
            _sha(self.governed_raw_sha256, field_name="governed_raw_sha256"),
        )
        object.__setattr__(
            self,
            "rerun_raw_sha256",
            _sha(self.rerun_raw_sha256, field_name="rerun_raw_sha256"),
        )
        if self.governed_raw_sha256 == self.rerun_raw_sha256:
            raise RollingFCRValidationError(
                "Feature 013 governed source and rerun must retain distinct bytes"
            )
        fields = tuple(
            _text(item, field_name="semantic_fields_compared")
            for item in self.semantic_fields_compared
        )
        if not fields or len(set(fields)) != len(fields):
            raise RollingFCRValidationError(
                "Feature 013 semantic fields must be non-empty and unique"
            )
        if self.semantic_outcome != "displayed_objective_bound_and_30_decisions_match":
            raise RollingFCRValidationError("unsupported Feature 013 semantic outcome")
        object.__setattr__(self, "semantic_fields_compared", fields)
        object.__setattr__(self, "cross_check_fingerprint", _fingerprint(self.to_dict()))

    def to_dict(self) -> dict[str, object]:
        return {
            "governed_fixture_preserved": self.governed_fixture_preserved,
            "governed_raw_sha256": self.governed_raw_sha256,
            "rerun_raw_sha256": self.rerun_raw_sha256,
            "semantic_fields_compared": list(self.semantic_fields_compared),
            "semantic_outcome": self.semantic_outcome,
        }

    @classmethod
    def from_dict(cls, payload: object) -> RollingFCRFeature013CrossCheck:
        data = _strict_mapping(
            payload,
            field_name="feature_013_cross_check",
            required_keys={
                "governed_fixture_preserved",
                "governed_raw_sha256",
                "rerun_raw_sha256",
                "semantic_fields_compared",
                "semantic_outcome",
            },
        )
        return cls(
            governed_fixture_preserved=data["governed_fixture_preserved"],  # type: ignore[arg-type]
            governed_raw_sha256=data["governed_raw_sha256"],  # type: ignore[arg-type]
            rerun_raw_sha256=data["rerun_raw_sha256"],  # type: ignore[arg-type]
            semantic_fields_compared=tuple(
                _sequence(
                    data["semantic_fields_compared"],
                    field_name="semantic_fields_compared",
                )
            ),  # type: ignore[arg-type]
            semantic_outcome=data["semantic_outcome"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceDiscrepancy:
    code: str
    scope: str
    description: str
    effect_on_claims: str

    def __post_init__(self) -> None:
        for name in ("code", "scope", "description", "effect_on_claims"):
            object.__setattr__(
                self, name, _text(getattr(self, name), field_name=name)
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "scope": self.scope,
            "description": self.description,
            "effect_on_claims": self.effect_on_claims,
        }

    @classmethod
    def from_dict(cls, payload: object, *, index: int) -> RollingFCRReferenceDiscrepancy:
        data = _strict_mapping(
            payload,
            field_name=f"discrepancies[{index}]",
            required_keys={"code", "scope", "description", "effect_on_claims"},
        )
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceUnavailableField:
    field_path: str
    reason: str
    required_for: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "field_path", _text(self.field_path, field_name="field_path")
        )
        object.__setattr__(self, "reason", _text(self.reason, field_name="reason"))
        required = tuple(
            _text(item, field_name="required_for") for item in self.required_for
        )
        if not required or len(set(required)) != len(required):
            raise RollingFCRValidationError(
                "unavailable field required_for must be non-empty and unique"
            )
        object.__setattr__(self, "required_for", required)

    def to_dict(self) -> dict[str, object]:
        return {
            "field_path": self.field_path,
            "reason": self.reason,
            "required_for": list(self.required_for),
        }

    @classmethod
    def from_dict(cls, payload: object, *, index: int) -> RollingFCRReferenceUnavailableField:
        data = _strict_mapping(
            payload,
            field_name=f"unavailable_fields[{index}]",
            required_keys={"field_path", "reason", "required_for"},
        )
        return cls(
            field_path=data["field_path"],  # type: ignore[arg-type]
            reason=data["reason"],  # type: ignore[arg-type]
            required_for=tuple(
                _sequence(data["required_for"], field_name="required_for")
            ),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceRedistributionStatus:
    fixture_contains_raw_logs: bool
    fixture_contains_raw_json: bool
    fixture_contains_workbook: bool
    fixture_contains_activation_samples: bool
    fixture_contains_machine_or_license_data: bool
    normalized_fields_only: bool

    def __post_init__(self) -> None:
        forbidden = (
            self.fixture_contains_raw_logs,
            self.fixture_contains_raw_json,
            self.fixture_contains_workbook,
            self.fixture_contains_activation_samples,
            self.fixture_contains_machine_or_license_data,
        )
        if any(value is not False for value in forbidden):
            raise RollingFCRValidationError(
                "normalized fixture cannot redistribute raw or sensitive payloads"
            )
        if self.normalized_fields_only is not True:
            raise RollingFCRValidationError("fixture must contain normalized fields only")

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_contains_raw_logs": self.fixture_contains_raw_logs,
            "fixture_contains_raw_json": self.fixture_contains_raw_json,
            "fixture_contains_workbook": self.fixture_contains_workbook,
            "fixture_contains_activation_samples": self.fixture_contains_activation_samples,
            "fixture_contains_machine_or_license_data": (
                self.fixture_contains_machine_or_license_data
            ),
            "normalized_fields_only": self.normalized_fields_only,
        }

    @classmethod
    def from_dict(cls, payload: object) -> RollingFCRReferenceRedistributionStatus:
        data = _strict_mapping(
            payload,
            field_name="redistribution_status",
            required_keys={
                "fixture_contains_raw_logs",
                "fixture_contains_raw_json",
                "fixture_contains_workbook",
                "fixture_contains_activation_samples",
                "fixture_contains_machine_or_license_data",
                "normalized_fields_only",
            },
        )
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceFixture:
    schema_version: str
    fixture_id: str
    reference_provenance: RollingFCRReferenceProvenance
    raw_input_manifest: tuple[RollingFCRReferenceRawArtifact, ...]
    profile_crosswalk: tuple[RollingFCRReferenceProfileCrosswalk, ...]
    study_window: Mapping[str, object]
    problem_inputs: tuple[RollingFCRReferenceProblemInput, ...]
    solve_records: tuple[RollingFCRReferenceSolveRecord, ...]
    delivery_evidence: tuple[RollingFCRReferenceDeliveryEvidence, ...]
    precision_policy: RollingFCRReferencePrecisionPolicy
    feature_013_cross_check: RollingFCRFeature013CrossCheck
    discrepancies: tuple[RollingFCRReferenceDiscrepancy, ...]
    unavailable_fields: tuple[RollingFCRReferenceUnavailableField, ...]
    redistribution_status: RollingFCRReferenceRedistributionStatus
    fixture_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != ROLLING_FCR_REFERENCE_FIXTURE_SCHEMA_VERSION:
            raise RollingFCRValidationError(
                "unsupported rolling reference fixture schema_version"
            )
        if self.fixture_id != ROLLING_FCR_REFERENCE_FIXTURE_ID:
            raise RollingFCRValidationError(
                "unsupported rolling reference fixture_id"
            )
        expected_contracts = (
            (
                "reference_provenance",
                self.reference_provenance,
                RollingFCRReferenceProvenance,
            ),
            (
                "precision_policy",
                self.precision_policy,
                RollingFCRReferencePrecisionPolicy,
            ),
            (
                "feature_013_cross_check",
                self.feature_013_cross_check,
                RollingFCRFeature013CrossCheck,
            ),
            (
                "redistribution_status",
                self.redistribution_status,
                RollingFCRReferenceRedistributionStatus,
            ),
        )
        for name, value, contract in expected_contracts:
            if not isinstance(value, contract):
                raise RollingFCRValidationError(f"{name} has the wrong contract type")
        raw = tuple(self.raw_input_manifest)
        if not raw or any(
            not isinstance(item, RollingFCRReferenceRawArtifact) for item in raw
        ):
            raise RollingFCRValidationError("raw input manifest must be non-empty")
        if len({item.artifact_id for item in raw}) != len(raw):
            raise RollingFCRValidationError("raw artifact IDs must be unique")
        if len({item.logical_source_path for item in raw}) != len(raw):
            raise RollingFCRValidationError("raw artifact logical paths must be unique")
        kind_counts = Counter(item.artifact_kind for item in raw)
        if kind_counts["generated_json"] != 20:
            raise RollingFCRValidationError(
                "raw input manifest must pin exactly 20 generated JSON files"
            )
        if kind_counts["generated_log"] != 11:
            raise RollingFCRValidationError(
                "raw input manifest must pin exactly 11 generated logs"
            )
        crosswalk = tuple(self.profile_crosswalk)
        if (
            len(crosswalk) != 5
            or any(
                not isinstance(item, RollingFCRReferenceProfileCrosswalk)
                for item in crosswalk
            )
            or tuple(item.profile_id for item in crosswalk)
            != ROLLING_FCR_REFERENCE_PROFILE_IDS
        ):
            raise RollingFCRValidationError(
                "profile crosswalk must use the canonical five-profile order"
            )
        study_window = _deep_freeze(self.study_window, field_name="study_window")
        expected_window = {
            "ordered_dates": [item.isoformat() for item in ROLLING_FCR_REFERENCE_DATES],
            "primary_comparison_dates": [
                item.isoformat() for item in ROLLING_FCR_REFERENCE_DATES[1:3]
            ],
            "edge_policy": {
                "rolling_0800_first_date": "initialization_only",
                "rolling_0800_last_date": "unfinalized",
            },
        }
        if _thaw(study_window) != expected_window:
            raise RollingFCRValidationError("study window is not the bounded oracle")
        expected_coverage = tuple(
            (profile, delivery_date)
            for profile in ROLLING_FCR_REFERENCE_PROFILE_IDS
            for delivery_date in ROLLING_FCR_REFERENCE_DATES
        )
        problem_inputs = tuple(self.problem_inputs)
        solve_records = tuple(self.solve_records)
        delivery_evidence = tuple(self.delivery_evidence)
        for name, values, contract in (
            ("problem_inputs", problem_inputs, RollingFCRReferenceProblemInput),
            ("solve_records", solve_records, RollingFCRReferenceSolveRecord),
            (
                "delivery_evidence",
                delivery_evidence,
                RollingFCRReferenceDeliveryEvidence,
            ),
        ):
            if len(values) != 20 or any(not isinstance(item, contract) for item in values):
                raise RollingFCRValidationError(f"{name} must contain exactly 20 records")
            observed = tuple((item.profile_id, item.delivery_date) for item in values)
            if observed != expected_coverage:
                raise RollingFCRValidationError(
                    f"{name} must use canonical five-by-four coverage"
                )
        raw_ids = {item.artifact_id for item in raw}
        if any(
            item.source_json_artifact_id not in raw_ids
            or item.source_log_artifact_id not in raw_ids
            for item in solve_records
        ):
            raise RollingFCRValidationError(
                "solve records must reference retained raw artifact identities"
            )
        discrepancies = tuple(self.discrepancies)
        if not discrepancies or any(
            not isinstance(item, RollingFCRReferenceDiscrepancy)
            for item in discrepancies
        ):
            raise RollingFCRValidationError("fixture discrepancies must be explicit")
        discrepancy_codes = {item.code for item in discrepancies}
        required_discrepancies = {
            "script-13-time-limit-vs-paper-profile",
            "workbook-energy-metric-vs-paper-output",
            "bounded-fixture-not-table-a1",
        }
        if not required_discrepancies.issubset(discrepancy_codes):
            raise RollingFCRValidationError(
                "fixture omits required source documentation discrepancies"
            )
        unavailable = tuple(self.unavailable_fields)
        if not unavailable or any(
            not isinstance(item, RollingFCRReferenceUnavailableField)
            for item in unavailable
        ):
            raise RollingFCRValidationError("fixture unavailable fields must be explicit")
        unavailable_paths = {item.field_path for item in unavailable}
        required_unavailable = {
            "source.unrounded_decisions",
            "source.restriction_independent_residual_audit",
            "profiles.script-14.exact_full_precision_restart",
            "source.feature_012_schedule_fingerprints",
            "source.activation_samples",
        }
        if not required_unavailable.issubset(unavailable_paths):
            raise RollingFCRValidationError(
                "fixture omits required unavailable source evidence"
            )
        object.__setattr__(self, "raw_input_manifest", raw)
        object.__setattr__(self, "profile_crosswalk", crosswalk)
        object.__setattr__(self, "study_window", study_window)
        object.__setattr__(self, "problem_inputs", problem_inputs)
        object.__setattr__(self, "solve_records", solve_records)
        object.__setattr__(self, "delivery_evidence", delivery_evidence)
        object.__setattr__(self, "discrepancies", discrepancies)
        object.__setattr__(self, "unavailable_fields", unavailable)
        object.__setattr__(self, "fixture_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "fixture_id": self.fixture_id,
            "reference_provenance": self.reference_provenance.to_dict(),
            "raw_input_manifest": [item.to_dict() for item in self.raw_input_manifest],
            "profile_crosswalk": [item.to_dict() for item in self.profile_crosswalk],
            "study_window": _thaw(self.study_window),
            "problem_inputs": [item.to_dict() for item in self.problem_inputs],
            "solve_records": [item.to_dict() for item in self.solve_records],
            "delivery_evidence": [item.to_dict() for item in self.delivery_evidence],
            "precision_policy": self.precision_policy.to_dict(),
            "feature_013_cross_check": self.feature_013_cross_check.to_dict(),
            "discrepancies": [item.to_dict() for item in self.discrepancies],
            "unavailable_fields": [item.to_dict() for item in self.unavailable_fields],
            "redistribution_status": self.redistribution_status.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "fixture_fingerprint": self.fixture_fingerprint}

    def solve_record(
        self, profile_id: str, delivery_date: date
    ) -> RollingFCRReferenceSolveRecord:
        try:
            return next(
                item
                for item in self.solve_records
                if item.profile_id == profile_id and item.delivery_date == delivery_date
            )
        except StopIteration as exc:  # pragma: no cover - construction guarantees coverage
            raise RollingFCRValidationError("reference solve record is unavailable") from exc

    def delivery_record(
        self, profile_id: str, delivery_date: date
    ) -> RollingFCRReferenceDeliveryEvidence:
        try:
            return next(
                item
                for item in self.delivery_evidence
                if item.profile_id == profile_id and item.delivery_date == delivery_date
            )
        except StopIteration as exc:  # pragma: no cover - construction guarantees coverage
            raise RollingFCRValidationError("reference delivery evidence is unavailable") from exc


def load_rolling_fcr_reference_fixture(
    path: str | Path,
) -> RollingFCRReferenceFixture:
    """Load one explicit normalized fixture without resolving any raw source path."""

    selected = Path(path)
    try:
        raw_bytes = selected.read_bytes()
    except OSError as exc:
        raise RollingFCRValidationError(
            f"rolling reference fixture is unavailable at explicit path {selected}: {exc}"
        ) from exc
    try:
        raw = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RollingFCRValidationError(
            f"rolling reference fixture must be UTF-8 JSON: {exc}"
        ) from exc
    top = _strict_mapping(
        raw,
        field_name="rolling reference fixture",
        required_keys=_FIXTURE_TOP_LEVEL_KEYS,
    )
    raw_manifest = _sequence(
        top["raw_input_manifest"], field_name="raw_input_manifest"
    )
    crosswalk = _sequence(top["profile_crosswalk"], field_name="profile_crosswalk")
    problem_inputs = _sequence(top["problem_inputs"], field_name="problem_inputs")
    solve_records = _sequence(top["solve_records"], field_name="solve_records")
    delivery_evidence = _sequence(
        top["delivery_evidence"], field_name="delivery_evidence"
    )
    discrepancies = _sequence(top["discrepancies"], field_name="discrepancies")
    unavailable = _sequence(
        top["unavailable_fields"], field_name="unavailable_fields"
    )
    fixture = RollingFCRReferenceFixture(
        schema_version=top["schema_version"],  # type: ignore[arg-type]
        fixture_id=top["fixture_id"],  # type: ignore[arg-type]
        reference_provenance=RollingFCRReferenceProvenance.from_dict(
            top["reference_provenance"]
        ),
        raw_input_manifest=tuple(
            RollingFCRReferenceRawArtifact.from_dict(item, index=index)
            for index, item in enumerate(raw_manifest)
        ),
        profile_crosswalk=tuple(
            RollingFCRReferenceProfileCrosswalk.from_dict(item, index=index)
            for index, item in enumerate(crosswalk)
        ),
        study_window=top["study_window"],  # type: ignore[arg-type]
        problem_inputs=tuple(
            RollingFCRReferenceProblemInput.from_dict(item, index=index)
            for index, item in enumerate(problem_inputs)
        ),
        solve_records=tuple(
            RollingFCRReferenceSolveRecord.from_dict(item, index=index)
            for index, item in enumerate(solve_records)
        ),
        delivery_evidence=tuple(
            RollingFCRReferenceDeliveryEvidence.from_dict(item, index=index)
            for index, item in enumerate(delivery_evidence)
        ),
        precision_policy=RollingFCRReferencePrecisionPolicy.from_dict(
            top["precision_policy"]
        ),
        feature_013_cross_check=RollingFCRFeature013CrossCheck.from_dict(
            top["feature_013_cross_check"]
        ),
        discrepancies=tuple(
            RollingFCRReferenceDiscrepancy.from_dict(item, index=index)
            for index, item in enumerate(discrepancies)
        ),
        unavailable_fields=tuple(
            RollingFCRReferenceUnavailableField.from_dict(item, index=index)
            for index, item in enumerate(unavailable)
        ),
        redistribution_status=RollingFCRReferenceRedistributionStatus.from_dict(
            top["redistribution_status"]
        ),
    )
    _verify_fingerprint(
        top["fixture_fingerprint"],
        fixture.fixture_fingerprint,
        field_name="fixture_fingerprint",
    )
    return fixture


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceFieldResult:
    """One authoritative native/source evidence outcome."""

    profile_id: str
    delivery_date: date | str
    category: str
    field_path: str
    unit: str
    mandatory: bool
    native_value: object | None
    source_displayed_value: object | None
    source_interval: tuple[float, float] | None
    delta: float | None
    allowed_envelope: tuple[float, float] | None
    outcome: str
    reason_codes: tuple[str, ...]
    native_evidence_fingerprint: str | None
    source_evidence_fingerprint: str | None
    joint_certificate_fingerprint: str | None = None
    field_result_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
            raise RollingFCRValidationError("unsupported field-result profile_id")
        delivery_date = (
            _date(self.delivery_date, field_name="field-result delivery_date")
            if isinstance(self.delivery_date, str)
            else self.delivery_date
        )
        if delivery_date not in ROLLING_FCR_REFERENCE_DATES:
            raise RollingFCRValidationError("field-result date is outside bounded window")
        object.__setattr__(self, "delivery_date", delivery_date)
        object.__setattr__(self, "category", _text(self.category, field_name="category"))
        object.__setattr__(
            self, "field_path", _text(self.field_path, field_name="field_path")
        )
        object.__setattr__(self, "unit", _text(self.unit, field_name="unit"))
        if not isinstance(self.mandatory, bool):
            raise RollingFCRValidationError("mandatory must be boolean")
        if self.outcome not in ROLLING_FCR_REFERENCE_OUTCOMES:
            raise RollingFCRValidationError("unsupported rolling reference outcome")
        source_interval = None
        if self.source_interval is not None:
            source_interval = tuple(
                _finite(value, field_name="source_interval")
                for value in self.source_interval
            )
            if len(source_interval) != 2 or source_interval[0] > source_interval[1]:
                raise RollingFCRValidationError(
                    "source interval must contain ordered endpoints"
                )
        allowed = None
        if self.allowed_envelope is not None:
            allowed = tuple(
                _finite(value, field_name="allowed_envelope")
                for value in self.allowed_envelope
            )
            if len(allowed) != 2 or allowed[0] > allowed[1]:
                raise RollingFCRValidationError(
                    "allowed envelope must contain ordered endpoints"
                )
            if source_interval is not None and (
                allowed[0] > source_interval[0] or allowed[1] < source_interval[1]
            ):
                raise RollingFCRValidationError(
                    "allowed envelope cannot be narrower than source precision"
                )
        delta = None if self.delta is None else _finite(self.delta, field_name="delta")
        reasons = tuple(
            _text(item, field_name="reason_codes") for item in self.reason_codes
        )
        if not reasons or len(set(reasons)) != len(reasons):
            raise RollingFCRValidationError(
                "field results require unique ordered reason codes"
            )
        for name in (
            "native_evidence_fingerprint",
            "source_evidence_fingerprint",
            "joint_certificate_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _sha(value, field_name=name))
        if self.outcome == "unavailable" and (
            self.native_value is not None and self.source_displayed_value is not None
        ) and "unavailable" not in " ".join(reasons):
            raise RollingFCRValidationError(
                "unavailable field results require an explicit unavailable reason"
            )
        object.__setattr__(self, "source_interval", source_interval)
        object.__setattr__(self, "allowed_envelope", allowed)
        object.__setattr__(self, "delta", delta)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(
            self, "native_value", _deep_freeze(self.native_value, field_name="native_value")
        )
        object.__setattr__(
            self,
            "source_displayed_value",
            _deep_freeze(
                self.source_displayed_value, field_name="source_displayed_value"
            ),
        )
        object.__setattr__(
            self, "field_result_fingerprint", _fingerprint(self._payload())
        )

    def _payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "delivery_date": self.delivery_date.isoformat(),  # type: ignore[union-attr]
            "category": self.category,
            "field_path": self.field_path,
            "unit": self.unit,
            "mandatory": self.mandatory,
            "native_value": _thaw(self.native_value),
            "source_displayed_value": _thaw(self.source_displayed_value),
            "source_interval": (
                None if self.source_interval is None else list(self.source_interval)
            ),
            "delta": self.delta,
            "allowed_envelope": (
                None if self.allowed_envelope is None else list(self.allowed_envelope)
            ),
            "outcome": self.outcome,
            "reason_codes": list(self.reason_codes),
            "native_evidence_fingerprint": self.native_evidence_fingerprint,
            "source_evidence_fingerprint": self.source_evidence_fingerprint,
            "joint_certificate_fingerprint": self.joint_certificate_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "field_result_fingerprint": self.field_result_fingerprint,
        }


def classify_rolling_fcr_numeric_evidence(
    *,
    native_value: float | None,
    source_value: float | None,
    source_half_unit: float,
    native_tolerance: float,
    source_termination: str,
    native_termination: str,
    native_feasible: bool,
    source_joint_feasible: bool,
    both_optimal: bool,
    objective_equivalent: bool,
    source_objective_eur: float | None,
    source_bound_eur: float | None,
    native_objective_eur: float | None,
    lifecycle_complete: bool,
) -> str:
    """Classify one scalar without collapsing precision, incumbent, and bound evidence."""

    if not lifecycle_complete:
        return "incomplete_or_unfinalized"
    if native_value is None or source_value is None:
        return "unavailable"
    native = _finite(native_value, field_name="native_value")
    source = _finite(source_value, field_name="source_value")
    half = _non_negative(source_half_unit, field_name="source_half_unit")
    tolerance = _non_negative(native_tolerance, field_name="native_tolerance")
    if native == source:
        return "exact_displayed_decision_parity"
    lower, upper = source_precision_interval(source, half)
    if lower - tolerance <= native <= upper + tolerance:
        return "source_precision_compatible"
    sufficient_common_feasibility = bool(native_feasible and source_joint_feasible)
    if (
        both_optimal
        and source_termination == "OPTIMAL"
        and native_termination.casefold() in {"optimal", "locallyoptimal", "globallyoptimal"}
        and sufficient_common_feasibility
        and objective_equivalent
    ):
        return "alternative_optimum_compatible"
    if source_termination == "TIME_LIMIT" and sufficient_common_feasibility:
        if objective_equivalent:
            return "source_incumbent_equivalent"
        if (
            source_objective_eur is not None
            and source_bound_eur is not None
            and native_objective_eur is not None
        ):
            source_objective = _finite(
                source_objective_eur, field_name="source_objective_eur"
            )
            source_bound = _finite(source_bound_eur, field_name="source_bound_eur")
            native_objective = _finite(
                native_objective_eur, field_name="native_objective_eur"
            )
            if source_bound + tolerance < source_objective:
                raise RollingFCRValidationError(
                    "source maximization bound cannot be below its incumbent"
                )
            if native_objective > source_bound + tolerance:
                return "bound_incompatible"
            if native_objective > source_objective + max(half, tolerance):
                return "improved_feasible_incumbent_compatible_with_source_bound"
    return "mismatch"


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceCompatibilitySummary:
    scope_id: str
    overall_compatibility: str
    evidence_bases: tuple[str, ...]
    field_result_fingerprints: tuple[str, ...]
    summary_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope_id", _text(self.scope_id, field_name="scope_id"))
        if self.overall_compatibility not in {
            "compatible",
            "incompatible",
            "incomplete",
        }:
            raise RollingFCRValidationError("unsupported overall compatibility")
        bases = tuple(self.evidence_bases)
        if bases != tuple(
            item for item in ROLLING_FCR_REFERENCE_OUTCOMES if item in set(bases)
        ):
            raise RollingFCRValidationError(
                "reference evidence bases must be distinct and canonically ordered"
            )
        fingerprints = tuple(
            _sha(value, field_name="field_result_fingerprints")
            for value in self.field_result_fingerprints
        )
        if not fingerprints:
            raise RollingFCRValidationError("compatibility summary requires field evidence")
        object.__setattr__(self, "evidence_bases", bases)
        object.__setattr__(self, "field_result_fingerprints", fingerprints)
        object.__setattr__(self, "summary_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "scope_id": self.scope_id,
            "overall_compatibility": self.overall_compatibility,
            "evidence_bases": list(self.evidence_bases),
            "field_result_fingerprints": list(self.field_result_fingerprints),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "summary_fingerprint": self.summary_fingerprint}


def derive_rolling_fcr_reference_summary(
    *,
    scope_id: str,
    field_results: Sequence[RollingFCRReferenceFieldResult],
) -> RollingFCRReferenceCompatibilitySummary:
    """Derive a deterministic summary while retaining authoritative field results."""

    fields = tuple(field_results)
    if not fields or any(
        not isinstance(item, RollingFCRReferenceFieldResult) for item in fields
    ):
        raise RollingFCRValidationError("summary requires reference field results")
    mandatory_outcomes = tuple(item.outcome for item in fields if item.mandatory)
    if not mandatory_outcomes:
        overall = "incomplete"
    elif any(
        item in {"bound_incompatible", "mismatch"}
        for item in mandatory_outcomes
    ):
        overall = "incompatible"
    elif any(
        item in {"unavailable", "incomplete_or_unfinalized"}
        for item in mandatory_outcomes
    ):
        overall = "incomplete"
    elif all(item in ROLLING_FCR_REFERENCE_COMPATIBLE_OUTCOMES for item in mandatory_outcomes):
        overall = "compatible"
    else:  # pragma: no cover - outcome contract makes this defensive only
        overall = "incomplete"
    observed = {item.outcome for item in fields}
    bases = tuple(
        item for item in ROLLING_FCR_REFERENCE_OUTCOMES if item in observed
    )
    return RollingFCRReferenceCompatibilitySummary(
        scope_id=scope_id,
        overall_compatibility=overall,
        evidence_bases=bases,
        field_result_fingerprints=tuple(
            item.field_result_fingerprint for item in fields
        ),
    )


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceLatentCertificate:
    """Joint source-interval certificate backed by Feature 013 residual evidence."""

    profile_id: str
    delivery_date: date
    status: str
    interval_audit_fingerprint: str | None
    native_feasibility_audit_fingerprint: str | None
    maximum_decision_residual: float | None
    maximum_objective_residual: float | None
    maximum_state_residual: float | None
    maximum_overlap_residual: float | None
    exact_restart_available: bool
    reason_codes: tuple[str, ...]
    certificate_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
            raise RollingFCRValidationError("unsupported certificate profile_id")
        if self.delivery_date not in ROLLING_FCR_REFERENCE_DATES:
            raise RollingFCRValidationError("certificate date is outside window")
        if self.status not in {"compatible", "incompatible", "unavailable"}:
            raise RollingFCRValidationError("unsupported latent certificate status")
        for name in (
            "interval_audit_fingerprint",
            "native_feasibility_audit_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _sha(value, field_name=name))
        for name in (
            "maximum_decision_residual",
            "maximum_objective_residual",
            "maximum_state_residual",
            "maximum_overlap_residual",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _non_negative(value, field_name=name))
        if not isinstance(self.exact_restart_available, bool):
            raise RollingFCRValidationError("exact_restart_available must be boolean")
        reasons = tuple(
            _text(item, field_name="certificate reason") for item in self.reason_codes
        )
        if not reasons or len(set(reasons)) != len(reasons):
            raise RollingFCRValidationError(
                "latent certificate requires unique ordered reasons"
            )
        if self.status == "compatible" and self.interval_audit_fingerprint is None:
            raise RollingFCRValidationError(
                "compatible latent certificate requires interval audit evidence"
            )
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "certificate_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "delivery_date": self.delivery_date.isoformat(),
            "status": self.status,
            "interval_audit_fingerprint": self.interval_audit_fingerprint,
            "native_feasibility_audit_fingerprint": (
                self.native_feasibility_audit_fingerprint
            ),
            "maximum_decision_residual": self.maximum_decision_residual,
            "maximum_objective_residual": self.maximum_objective_residual,
            "maximum_state_residual": self.maximum_state_residual,
            "maximum_overlap_residual": self.maximum_overlap_residual,
            "exact_restart_available": self.exact_restart_available,
            "reason_codes": list(self.reason_codes),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "certificate_fingerprint": self.certificate_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RollingFCRReferenceComparison:
    fixture_fingerprint: str
    manifest_fingerprint: str
    result_fingerprint: str
    profile_id: str
    field_results: tuple[RollingFCRReferenceFieldResult, ...]
    latent_certificates: tuple[RollingFCRReferenceLatentCertificate, ...]
    date_summaries: tuple[RollingFCRReferenceCompatibilitySummary, ...]
    profile_summary: RollingFCRReferenceCompatibilitySummary
    overall_summary: RollingFCRReferenceCompatibilitySummary
    diagnostics: tuple[str, ...]
    comparison_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "fixture_fingerprint",
            "manifest_fingerprint",
            "result_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), field_name=name))
        if self.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
            raise RollingFCRValidationError("unsupported comparison profile_id")
        fields = tuple(self.field_results)
        if not fields or any(
            not isinstance(item, RollingFCRReferenceFieldResult) for item in fields
        ):
            raise RollingFCRValidationError("comparison field results are required")
        field_keys = tuple(
            (item.profile_id, item.delivery_date, item.category, item.field_path)
            for item in fields
        )
        if len(set(field_keys)) != len(field_keys):
            raise RollingFCRValidationError("comparison field identities must be unique")
        if any(item.profile_id != self.profile_id for item in fields):
            raise RollingFCRValidationError("comparison fields use a different profile")
        certificates = tuple(self.latent_certificates)
        if any(
            not isinstance(item, RollingFCRReferenceLatentCertificate)
            for item in certificates
        ):
            raise RollingFCRValidationError("comparison latent certificate is invalid")
        summaries = tuple(self.date_summaries)
        if len(summaries) != len({item.delivery_date for item in fields}):
            raise RollingFCRValidationError("comparison requires one summary per date")
        if any(
            not isinstance(item, RollingFCRReferenceCompatibilitySummary)
            for item in summaries
        ):
            raise RollingFCRValidationError("comparison date summary is invalid")
        if not isinstance(
            self.profile_summary, RollingFCRReferenceCompatibilitySummary
        ) or not isinstance(
            self.overall_summary, RollingFCRReferenceCompatibilitySummary
        ):
            raise RollingFCRValidationError("comparison summaries have the wrong type")
        diagnostics = tuple(
            _text(item, field_name="comparison diagnostic")
            for item in self.diagnostics
        )
        object.__setattr__(self, "field_results", fields)
        object.__setattr__(self, "latent_certificates", certificates)
        object.__setattr__(self, "date_summaries", summaries)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "comparison_fingerprint", _fingerprint(self._payload()))

    @property
    def overall_compatibility(self) -> str:
        return self.overall_summary.overall_compatibility

    @property
    def evidence_bases(self) -> tuple[str, ...]:
        return self.overall_summary.evidence_bases

    def _payload(self) -> dict[str, object]:
        return {
            "fixture_fingerprint": self.fixture_fingerprint,
            "manifest_fingerprint": self.manifest_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "profile_id": self.profile_id,
            "field_results": [item.to_dict() for item in self.field_results],
            "latent_certificates": [
                item.to_dict() for item in self.latent_certificates
            ],
            "date_summaries": [item.to_dict() for item in self.date_summaries],
            "profile_summary": self.profile_summary.to_dict(),
            "overall_summary": self.overall_summary.to_dict(),
            "diagnostics": list(self.diagnostics),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "comparison_fingerprint": self.comparison_fingerprint,
        }


def _native_tolerance(manifest: RollingFCRStudyManifest) -> float:
    policy = manifest.solve_policy
    return max(
        float(policy.objective_comparison_absolute_tolerance_eur),
        float(policy.primal_feasibility_tolerance),
        float(policy.mip_feasibility_tolerance),
    )


def _revision_evidence_fingerprint(revision: RollingFCRDayRevision) -> str:
    """Content hash of one native revision, ignoring volatile runtime fields."""

    return _fingerprint(_stable_runtime(revision.to_dict()))


def _audit_evidence_fingerprint(revision: RollingFCRDayRevision) -> str | None:
    """The revision's evidence hash when it carries an independent audit."""

    return _revision_evidence_fingerprint(revision) if revision.independent_residuals else None


def _revision_is_independently_feasible(
    revision: RollingFCRDayRevision,
    *,
    tolerance: float,
) -> bool:
    if not revision.independent_residuals:
        return False
    maximum_slack = max(revision.feasibility_slacks.values(), default=math.inf)
    maximum_residual = max(
        revision.independent_residuals.values(), default=math.inf
    )
    return (
        revision.solve_status in {"optimal", "feasible"}
        and maximum_slack <= tolerance
        and maximum_residual <= tolerance
    )


def _objective_equivalent(
    native: float | None,
    source: float,
    *,
    source_half_unit: float,
    manifest: RollingFCRStudyManifest,
) -> bool:
    if native is None:
        return False
    absolute = float(manifest.solve_policy.objective_comparison_absolute_tolerance_eur)
    relative = float(manifest.solve_policy.objective_comparison_relative_tolerance)
    allowance = max(absolute, relative * max(abs(native), abs(source), 1.0))
    lower, upper = source_precision_interval(source, source_half_unit)
    return lower - allowance <= native <= upper + allowance


def _maximum_overlap_residual(
    fixture: RollingFCRReferenceFixture,
    source: RollingFCRReferenceSolveRecord,
) -> float | None:
    overlap = source.accepted_overlap
    if overlap is None:
        return None
    predecessor = fixture.solve_record(source.profile_id, overlap.predecessor_delivery_date)
    half = fixture.precision_policy.half_unit
    residual = 0.0
    predecessor_energy = predecessor.hourly_energy_source_positive_discharge_kw[8:24]
    predecessor_fcr = predecessor.fcr_capacity_kw[2:6]
    for left, right in zip(
        (*predecessor_energy, *predecessor_fcr),
        (*overlap.hourly_energy_source_positive_discharge_kw, *overlap.fcr_capacity_kw),
    ):
        left_interval = source_precision_interval(left, half)
        right_interval = source_precision_interval(right, half)
        residual = max(
            residual,
            left_interval[0] - right_interval[1],
            right_interval[0] - left_interval[1],
            0.0,
        )
    return residual


def _build_latent_certificate(
    *,
    manifest: RollingFCRStudyManifest,
    fixture: RollingFCRReferenceFixture,
    source: RollingFCRReferenceSolveRecord,
    revision: RollingFCRDayRevision,
) -> RollingFCRReferenceLatentCertificate:
    half = fixture.precision_policy.half_unit
    tolerance = _native_tolerance(manifest)
    if (
        revision.energy_decisions_charge_positive_kw is None
        or revision.fcr_capacity_kw is None
        or revision.objective_value_eur is None
        or not revision.independent_residuals
    ):
        return RollingFCRReferenceLatentCertificate(
            profile_id=source.profile_id,
            delivery_date=source.delivery_date,
            status="unavailable",
            interval_audit_fingerprint=None,
            native_feasibility_audit_fingerprint=_audit_evidence_fingerprint(revision),
            maximum_decision_residual=None,
            maximum_objective_residual=None,
            maximum_state_residual=None,
            maximum_overlap_residual=_maximum_overlap_residual(fixture, source),
            exact_restart_available=False,
            reason_codes=("native_joint_witness_evidence_unavailable",),
        )
    native_source_x0 = tuple(
        -value for value in revision.energy_decisions_charge_positive_kw
    )
    field_values: dict[str, float] = {}
    intervals: dict[str, tuple[float, float]] = {}
    categories: dict[str, str] = {}
    for index, (native, displayed) in enumerate(
        zip(native_source_x0, source.hourly_energy_source_positive_discharge_kw)
    ):
        name = f"decision.x0[{index}]"
        field_values[name] = native
        intervals[name] = source_precision_interval(displayed, half)
        categories[name] = "decision"
    for index, (native, displayed) in enumerate(
        zip(revision.fcr_capacity_kw, source.fcr_capacity_kw)
    ):
        name = f"decision.xr[{index}]"
        field_values[name] = native
        intervals[name] = source_precision_interval(displayed, half)
        categories[name] = "decision"
    field_values["objective"] = revision.objective_value_eur
    intervals["objective"] = source_precision_interval(source.objective_eur, half)
    categories["objective"] = "objective"
    if revision.initial_stored_energy_kwh is not None:
        field_values["state.initial"] = revision.initial_stored_energy_kwh
        intervals["state.initial"] = source_precision_interval(
            source.initial_stored_energy_kwh, half
        )
        categories["state.initial"] = "state"
    if (
        source.cutoff_stored_energy_kwh is not None
        and revision.realized_cutoff_stored_energy_kwh is not None
    ):
        field_values["state.cutoff"] = revision.realized_cutoff_stored_energy_kwh
        intervals["state.cutoff"] = source_precision_interval(
            source.cutoff_stored_energy_kwh, half
        )
        categories["state.cutoff"] = "state"
    from open_energy_lab.control._robust_fcr_formulation import audit_closed_reference_witness

    interval_audit = audit_closed_reference_witness(
        field_values=field_values,
        closed_intervals=intervals,
        maximum_modeled_slack=max(revision.feasibility_slacks.values(), default=math.inf),
        maximum_independent_residual=max(
            revision.independent_residuals.values(), default=math.inf
        ),
        tolerance=tolerance,
    )
    by_category = {
        category: max(
            (
                residual
                for name, residual in interval_audit.field_residuals.items()
                if categories[name] == category
            ),
            default=0.0,
        )
        for category in {"decision", "objective", "state"}
    }
    overlap_residual = _maximum_overlap_residual(fixture, source)
    exact_restart_available = source.profile_id != ROLLING_FCR_REFERENCE_PROFILE_IDS[3]
    overlap_passes = overlap_residual is None or overlap_residual <= tolerance
    status = "compatible" if interval_audit.passes and overlap_passes else "incompatible"
    reasons = [
        "native_witness_reused_as_joint_source_interval_certificate"
        if interval_audit.passes
        else "native_witness_outside_joint_source_interval_or_audit_tolerance"
    ]
    if source.profile_id == ROLLING_FCR_REFERENCE_PROFILE_IDS[3]:
        reasons.append("exact_restart_unavailable_hidden_full_precision_fixings")
        if overlap_residual is not None:
            reasons.append("displayed_cross_day_overlap_intervals_certified")
    return RollingFCRReferenceLatentCertificate(
        profile_id=source.profile_id,
        delivery_date=source.delivery_date,
        status=status,
        interval_audit_fingerprint=interval_audit.audit_fingerprint,
        native_feasibility_audit_fingerprint=_audit_evidence_fingerprint(revision),
        maximum_decision_residual=by_category["decision"],
        maximum_objective_residual=by_category["objective"],
        maximum_state_residual=by_category["state"],
        maximum_overlap_residual=overlap_residual,
        exact_restart_available=exact_restart_available,
        reason_codes=tuple(reasons),
    )


def _numeric_field_result(
    *,
    manifest: RollingFCRStudyManifest,
    source: RollingFCRReferenceSolveRecord,
    revision: RollingFCRDayRevision,
    certificate: RollingFCRReferenceLatentCertificate,
    category: str,
    field_path: str,
    unit: str,
    mandatory: bool,
    native_value: float | None,
    source_value: float | None,
    native_feasible: bool,
    lifecycle_complete: bool,
) -> RollingFCRReferenceFieldResult:
    half = 0.0005
    tolerance = _native_tolerance(manifest)
    objective_equivalent = _objective_equivalent(
        revision.objective_value_eur,
        source.objective_eur,
        source_half_unit=half,
        manifest=manifest,
    )
    source_joint_feasible = certificate.status == "compatible"
    both_optimal = bool(
        source.solver_evidence.is_optimal
        and revision.solve_status == "optimal"
        and revision.termination_status is not None
        and "optimal" in revision.termination_status.casefold()
    )
    outcome = classify_rolling_fcr_numeric_evidence(
        native_value=native_value,
        source_value=source_value,
        source_half_unit=half,
        native_tolerance=tolerance,
        source_termination=source.solver_evidence.termination_condition,
        native_termination=revision.termination_status or "unavailable",
        native_feasible=native_feasible,
        source_joint_feasible=source_joint_feasible,
        both_optimal=both_optimal,
        objective_equivalent=objective_equivalent,
        source_objective_eur=source.objective_eur,
        source_bound_eur=source.best_upper_bound_eur,
        native_objective_eur=revision.objective_value_eur,
        lifecycle_complete=lifecycle_complete,
    )
    interval = (
        None if source_value is None else source_precision_interval(source_value, half)
    )
    envelope = (
        None
        if interval is None
        else (interval[0] - tolerance, interval[1] + tolerance)
    )
    delta = (
        None
        if native_value is None or source_value is None
        else float(native_value) - float(source_value)
    )
    reasons = {
        "exact_displayed_decision_parity": ("native_equals_displayed_source_value",),
        "source_precision_compatible": (
            "native_value_inside_closed_source_precision_and_native_tolerance",
        ),
        "alternative_optimum_compatible": (
            "both_optimal_common_feasibility_and_objective_equivalence",
        ),
        "source_incumbent_equivalent": (
            "time_limited_source_incumbent_objective_equivalent",
        ),
        "improved_feasible_incumbent_compatible_with_source_bound": (
            "native_feasible_incumbent_improves_source_within_upper_bound",
        ),
        "bound_incompatible": (
            "native_objective_exceeds_source_upper_bound_envelope",
        ),
        "mismatch": ("numeric_evidence_outside_compatible_regions",),
        "unavailable": ("native_or_source_numeric_evidence_unavailable",),
        "incomplete_or_unfinalized": (
            "required_delivery_lifecycle_is_incomplete_or_unfinalized",
        ),
    }[outcome]
    return RollingFCRReferenceFieldResult(
        profile_id=source.profile_id,
        delivery_date=source.delivery_date,
        category=category,
        field_path=field_path,
        unit=unit,
        mandatory=mandatory,
        native_value=native_value,
        source_displayed_value=source_value,
        source_interval=interval,
        delta=delta,
        allowed_envelope=envelope,
        outcome=outcome,
        reason_codes=reasons,
        native_evidence_fingerprint=_revision_evidence_fingerprint(revision),
        source_evidence_fingerprint=source.record_fingerprint,
        joint_certificate_fingerprint=certificate.certificate_fingerprint,
    )


def _categorical_field_result(
    *,
    source: RollingFCRReferenceSolveRecord,
    revision: RollingFCRDayRevision,
    category: str,
    field_path: str,
    mandatory: bool,
    native_value: object | None,
    source_value: object | None,
    outcome: str,
    reason_codes: tuple[str, ...],
    certificate: RollingFCRReferenceLatentCertificate | None = None,
) -> RollingFCRReferenceFieldResult:
    return RollingFCRReferenceFieldResult(
        profile_id=source.profile_id,
        delivery_date=source.delivery_date,
        category=category,
        field_path=field_path,
        unit="status",
        mandatory=mandatory,
        native_value=native_value,
        source_displayed_value=source_value,
        source_interval=None,
        delta=None,
        allowed_envelope=None,
        outcome=outcome,
        reason_codes=reason_codes,
        native_evidence_fingerprint=_revision_evidence_fingerprint(revision),
        source_evidence_fingerprint=source.record_fingerprint,
        joint_certificate_fingerprint=(
            None if certificate is None else certificate.certificate_fingerprint
        ),
    )


def _delivery_lifecycle_outcome(
    source: RollingFCRReferenceDeliveryEvidence,
    envelope: DeliveryDateRecordEnvelope,
) -> tuple[str, tuple[str, ...]]:
    native = envelope.latest_revision.lifecycle_status
    if source.source_lifecycle_status in {"initialization_only", "unfinalized"}:
        expected = source.source_lifecycle_status
        if native == expected:
            return (
                "incomplete_or_unfinalized",
                (f"source_and_native_{expected}_edge_retained",),
            )
        return "mismatch", ("native_lifecycle_differs_from_source_edge",)
    if source.source_lifecycle_status == "finalized":
        if native == "finalized":
            return "exact_displayed_decision_parity", ("finalized_lifecycle_matches",)
        return "incomplete_or_unfinalized", ("native_finalization_evidence_incomplete",)
    if native in {"finalized", "optimization_only"}:
        # Source independent completion contains solve/replay output.  Native
        # optimization-only evidence remains usable for ex-ante fields, while
        # its lifecycle comparison itself stays incomplete.
        if native == "optimization_only":
            return "incomplete_or_unfinalized", ("native_replay_evidence_unavailable",)
        return "exact_displayed_decision_parity", ("independent_completion_matches",)
    return "incomplete_or_unfinalized", ("native_independent_lifecycle_incomplete",)


def compare_rolling_fcr_reference(
    *,
    manifest: RollingFCRStudyManifest,
    result: RollingFCRStudyResult,
    fixture: RollingFCRReferenceFixture,
) -> RollingFCRReferenceComparison:
    """Compare one native rolling study with the bounded normalized source oracle."""

    if not isinstance(manifest, RollingFCRStudyManifest):
        raise RollingFCRValidationError("manifest has the wrong contract type")
    if not isinstance(result, RollingFCRStudyResult):
        raise RollingFCRValidationError("result has the wrong contract type")
    if not isinstance(fixture, RollingFCRReferenceFixture):
        raise RollingFCRValidationError("fixture has the wrong contract type")
    if result.manifest_fingerprint != manifest.manifest_fingerprint:
        raise RollingFCRValidationError("comparison result and manifest differ")
    if result.profile_id != manifest.profile.profile_id:
        raise RollingFCRValidationError("comparison result and profile differ")
    if manifest.profile.profile_id not in ROLLING_FCR_REFERENCE_PROFILE_IDS:
        raise RollingFCRValidationError("manifest profile is outside the source fixture")
    if tuple(result.requested_dates) != tuple(
        item.delivery_date for item in manifest.dates
    ):
        raise RollingFCRValidationError("comparison date order differs from manifest")
    if any(item not in ROLLING_FCR_REFERENCE_DATES for item in result.requested_dates):
        raise RollingFCRValidationError("comparison requires the bounded source dates")
    lineage = dict(manifest.reference_lineage)
    if lineage.get("reference_revision") != fixture.reference_provenance.reference_revision:
        raise RollingFCRValidationError("manifest reference revision differs from fixture")
    declared_fixture = lineage.get("fixture_fingerprint")
    if declared_fixture is not None and declared_fixture != fixture.fixture_fingerprint:
        raise RollingFCRValidationError("manifest fixture fingerprint differs")

    profile_id = manifest.profile.profile_id
    fields: list[RollingFCRReferenceFieldResult] = []
    certificates: list[RollingFCRReferenceLatentCertificate] = []
    date_summaries: list[RollingFCRReferenceCompatibilitySummary] = []
    diagnostics: list[str] = []
    tolerance = _native_tolerance(manifest)
    for envelope in result.records:
        delivery_date = envelope.classification.delivery_date
        source = fixture.solve_record(profile_id, delivery_date)
        source_delivery = fixture.delivery_record(profile_id, delivery_date)
        revision = envelope.latest_revision
        certificate = _build_latent_certificate(
            manifest=manifest,
            fixture=fixture,
            source=source,
            revision=revision,
        )
        certificates.append(certificate)
        comparison_eligible = envelope.classification.comparison_eligible
        lifecycle_outcome, lifecycle_reasons = _delivery_lifecycle_outcome(
            source_delivery, envelope
        )
        date_fields: list[RollingFCRReferenceFieldResult] = [
            _categorical_field_result(
                source=source,
                revision=revision,
                category="lifecycle",
                field_path="source_lifecycle_status",
                mandatory=True,
                native_value=revision.lifecycle_status,
                source_value=source_delivery.source_lifecycle_status,
                outcome=lifecycle_outcome,
                reason_codes=lifecycle_reasons,
                certificate=certificate,
            )
        ]
        lifecycle_complete = source_delivery.finalized_evidence_available and (
            revision.lifecycle_status in {"finalized", "optimization_only"}
        )
        native_feasible = _revision_is_independently_feasible(
            revision, tolerance=tolerance
        )
        date_fields.append(
            _numeric_field_result(
                manifest=manifest,
                source=source,
                revision=revision,
                certificate=certificate,
                category="objective",
                field_path="optimization_objective_eur",
                unit="EUR",
                mandatory=comparison_eligible,
                native_value=revision.objective_value_eur,
                source_value=source.objective_eur,
                native_feasible=native_feasible,
                lifecycle_complete=(
                    lifecycle_complete or source_delivery.source_lifecycle_status == "unfinalized"
                ),
            )
        )
        date_fields.append(
            _numeric_field_result(
                manifest=manifest,
                source=source,
                revision=revision,
                certificate=certificate,
                category="bound",
                field_path="best_upper_bound_eur",
                unit="EUR",
                mandatory=comparison_eligible,
                native_value=revision.best_upper_bound_eur,
                source_value=source.best_upper_bound_eur,
                native_feasible=native_feasible,
                lifecycle_complete=(
                    lifecycle_complete or source_delivery.source_lifecycle_status == "unfinalized"
                ),
            )
        )
        source_x0 = source.hourly_energy_source_positive_discharge_kw
        native_x0 = (
            None
            if revision.energy_decisions_charge_positive_kw is None
            else tuple(-value for value in revision.energy_decisions_charge_positive_kw)
        )
        for index in range(24):
            date_fields.append(
                _numeric_field_result(
                    manifest=manifest,
                    source=source,
                    revision=revision,
                    certificate=certificate,
                    category="decision",
                    field_path=f"hourly_energy_source_positive_discharge_kw[{index}]",
                    unit="kW",
                    mandatory=comparison_eligible,
                    native_value=None if native_x0 is None else native_x0[index],
                    source_value=source_x0[index],
                    native_feasible=native_feasible,
                    lifecycle_complete=True,
                )
            )
        for index in range(6):
            date_fields.append(
                _numeric_field_result(
                    manifest=manifest,
                    source=source,
                    revision=revision,
                    certificate=certificate,
                    category="decision",
                    field_path=f"fcr_capacity_kw[{index}]",
                    unit="kW",
                    mandatory=comparison_eligible,
                    native_value=(
                        None
                        if revision.fcr_capacity_kw is None
                        else revision.fcr_capacity_kw[index]
                    ),
                    source_value=source.fcr_capacity_kw[index],
                    native_feasible=native_feasible,
                    lifecycle_complete=True,
                )
            )
        feasibility_outcome = (
            "source_precision_compatible"
            if certificate.status == "compatible"
            else "mismatch"
            if certificate.status == "incompatible"
            else "unavailable"
        )
        date_fields.append(
            _categorical_field_result(
                source=source,
                revision=revision,
                category="feasibility",
                field_path="joint_formulation_audit",
                mandatory=comparison_eligible,
                native_value=native_feasible,
                source_value="closed_source_interval_certificate_required",
                outcome=feasibility_outcome,
                reason_codes=(
                    "joint_source_interval_and_native_residual_audit_compatible"
                    if feasibility_outcome == "source_precision_compatible"
                    else "joint_source_interval_audit_incompatible"
                    if feasibility_outcome == "mismatch"
                    else "joint_source_interval_audit_unavailable",
                ),
                certificate=certificate,
            )
        )
        termination_outcome = (
            "exact_displayed_decision_parity"
            if (
                source.solver_evidence.termination_condition == "OPTIMAL"
                and revision.termination_status is not None
                and "optimal" in revision.termination_status.casefold()
            )
            else "source_incumbent_equivalent"
            if source.solver_evidence.is_time_limited_incumbent and native_feasible
            else "unavailable"
            if revision.termination_status is None
            else "mismatch"
        )
        date_fields.append(
            _categorical_field_result(
                source=source,
                revision=revision,
                category="termination",
                field_path="termination_condition",
                mandatory=comparison_eligible,
                native_value=revision.termination_status,
                source_value=source.solver_evidence.termination_condition,
                outcome=termination_outcome,
                reason_codes=(
                    "source_and_native_optimal_termination"
                    if termination_outcome == "exact_displayed_decision_parity"
                    else "source_time_limit_retained_as_incumbent_evidence"
                    if termination_outcome == "source_incumbent_equivalent"
                    else "termination_evidence_unavailable"
                    if termination_outcome == "unavailable"
                    else "termination_evidence_mismatch",
                ),
                certificate=certificate,
            )
        )
        date_fields.append(
            _categorical_field_result(
                source=source,
                revision=revision,
                category="schedule_fingerprint",
                field_path="feature_012_schedule_fingerprint",
                mandatory=False,
                native_value=revision.plan_fingerprint,
                source_value=None,
                outcome="unavailable",
                reason_codes=("source_feature_012_schedule_fingerprint_unavailable",),
                certificate=certificate,
            )
        )
        if source.accepted_overlap is not None:
            native_fixed_tail = revision.runtime_metadata.get(
                "fixed_tail_objective_eur"
            )
            date_fields.append(
                _numeric_field_result(
                    manifest=manifest,
                    source=source,
                    revision=revision,
                    certificate=certificate,
                    category="fixed_tail_objective",
                    field_path="fixed_tail_objective_eur",
                    unit="EUR",
                    mandatory=comparison_eligible,
                    native_value=(
                        None
                        if native_fixed_tail is None
                        else _finite(
                            native_fixed_tail,
                            field_name="native fixed_tail_objective_eur",
                        )
                    ),
                    source_value=source.accepted_overlap.fixed_tail_objective_eur,
                    native_feasible=native_feasible,
                    lifecycle_complete=True,
                )
            )
            date_fields.append(
                _categorical_field_result(
                    source=source,
                    revision=revision,
                    category="overlap",
                    field_path="exact_full_precision_restart",
                    mandatory=comparison_eligible,
                    native_value="native_full_precision_fixings_retained",
                    source_value=None,
                    outcome="unavailable",
                    reason_codes=(
                        "source_json_did_not_persist_unrounded_predecessor_fixings",
                    ),
                    certificate=certificate,
                )
            )
        fields.extend(date_fields)
        date_summaries.append(
            derive_rolling_fcr_reference_summary(
                scope_id=f"{profile_id}:{delivery_date.isoformat()}",
                field_results=date_fields,
            )
        )
        if certificate.status != "compatible":
            diagnostics.append(
                f"{delivery_date.isoformat()}:joint_latent_certificate_{certificate.status}"
            )
    profile_summary = derive_rolling_fcr_reference_summary(
        scope_id=profile_id,
        field_results=fields,
    )
    overall_summary = derive_rolling_fcr_reference_summary(
        scope_id=f"{result.study_id}:bounded-reference",
        field_results=fields,
    )
    if profile_id == ROLLING_FCR_REFERENCE_PROFILE_IDS[3]:
        diagnostics.append("exact_0800_restart_parity_unavailable_hidden_fixings")
    diagnostics.extend(
        (
            "bounded_fixture_does_not_claim_table_a1_parity",
            "source_bilinear_violations_field_not_used_as_feasibility_evidence",
        )
    )
    return RollingFCRReferenceComparison(
        fixture_fingerprint=fixture.fixture_fingerprint,
        manifest_fingerprint=manifest.manifest_fingerprint,
        result_fingerprint=result.semantic_fingerprint,
        profile_id=profile_id,
        field_results=tuple(fields),
        latent_certificates=tuple(certificates),
        date_summaries=tuple(date_summaries),
        profile_summary=profile_summary,
        overall_summary=overall_summary,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "ROLLING_FCR_REFERENCE_COMPATIBLE_OUTCOMES",
    "ROLLING_FCR_REFERENCE_DATES",
    "ROLLING_FCR_REFERENCE_FIXTURE_ID",
    "ROLLING_FCR_REFERENCE_FIXTURE_SCHEMA_VERSION",
    "ROLLING_FCR_REFERENCE_NORMALIZER_VERSION",
    "ROLLING_FCR_REFERENCE_OUTCOMES",
    "ROLLING_FCR_REFERENCE_PROFILE_IDS",
    "ROLLING_FCR_REFERENCE_REVISION",
    "RollingFCRFeature013CrossCheck",
    "RollingFCRReferenceAcceptedOverlap",
    "RollingFCRReferenceComparison",
    "RollingFCRReferenceCompatibilitySummary",
    "RollingFCRReferenceDeliveryEvidence",
    "RollingFCRReferenceDiscrepancy",
    "RollingFCRReferenceFieldResult",
    "RollingFCRReferenceFixture",
    "RollingFCRReferenceLatentCertificate",
    "RollingFCRReferencePrecisionPolicy",
    "RollingFCRReferenceProblemInput",
    "RollingFCRReferenceProfileCrosswalk",
    "RollingFCRReferenceProvenance",
    "RollingFCRReferenceRawArtifact",
    "RollingFCRReferenceRedistributionStatus",
    "RollingFCRReferenceSolveRecord",
    "RollingFCRReferenceUnavailableField",
    "RollingFCRSourceSolverEvidence",
    "classify_rolling_fcr_numeric_evidence",
    "compare_rolling_fcr_reference",
    "derive_rolling_fcr_reference_summary",
    "load_rolling_fcr_reference_fixture",
    "source_precision_interval",
]
