"""Governed reference evidence for the pinned robust-storage-bidding case.

This focused module loads a small committed aggregate fixture or a caller-selected
external activation CSV.  It never searches the repository, downloads data, or
imports the reference implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
import csv
from dataclasses import dataclass, field
from functools import partial
from datetime import UTC, date, datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Any

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import canonical_json_bytes, fingerprint, thaw
from open_energy_lab.core.validation import finite, mapping, non_empty_str, sequence, sha256_digest
from open_energy_lab.market.activation import (
    ActivationImportRequest,
    RegulationActivationTrace,
    import_regulation_activation_trace,
)
from open_energy_lab.market.time import (
    CanonicalInterval,
    build_local_delivery_day,
    parse_iso8601_duration,
)


REFERENCE_FIXTURE_SCHEMA_VERSION = "oel.fcr-reference-aggregate.v1"
REFERENCE_MAPPING_ID = "robust-storage-bidding-to-oel-v1"
REFERENCE_PRECISION_POLICY_ID = "rounded-decisions-interval-v1"
REFERENCE_COMMIT = "7e44738bb30e5c8204efe40103b9be4c2203685c"
REFERENCE_RESULT_SHA256 = (
    "8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6"
)
REFERENCE_ACTIVATION_ARTIFACT_CREATED_AT_UTC = datetime(2026, 8, 26, tzinfo=UTC)

_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}")
_REQUIRED_FIXTURE_SECTIONS = {
    "schema_version",
    "fixture_id",
    "reference_provenance",
    "runtime_provenance",
    "reference_configuration",
    "fixed_decisions",
    "price_inputs",
    "mapping",
    "external_activation",
    "precision_policy",
    "expected_fields",
    "unsupported_fields",
    "redistribution_status",
    "fixture_fingerprint",
}


class ReferenceFCRValidationError(ValidationError):
    """Raised when reference declarations are incomplete or inconsistent."""


class ReferenceFCRIntegrityError(ReferenceFCRValidationError):
    """Raised when committed or external evidence fails an integrity check."""


class ExternalReferenceDataError(ReferenceFCRValidationError):
    """Raised with installation guidance for absent or invalid external bytes."""


_non_empty = partial(non_empty_str, error=ReferenceFCRValidationError, strip=True)
_finite = partial(finite, error=ReferenceFCRValidationError)


def _integer(value: object, *, field_name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ReferenceFCRValidationError(
            f"{field_name} must be an integer greater than or equal to {minimum}"
        )
    return value


_mapping = partial(mapping, error=ReferenceFCRValidationError)
_sequence = partial(sequence, error=ReferenceFCRValidationError)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(inner) for key, inner in sorted(value.items())}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(inner) for inner in value)
    return value


_thaw = thaw


def canonical_reference_json_bytes(value: object) -> bytes:
    """Serialize finite reference evidence for stable digests."""

    return canonical_json_bytes(value, error=ReferenceFCRValidationError)


_fingerprint = partial(fingerprint, error=ReferenceFCRValidationError)
_sha256 = partial(sha256_digest, error=ReferenceFCRValidationError)


def _json_pointer(value: object, *, field_name: str) -> str:
    pointer = _non_empty(value, field_name=field_name)
    if not pointer.startswith("/"):
        raise ReferenceFCRValidationError(f"{field_name} must be a JSON pointer")
    return pointer


def _date(value: object, *, field_name: str) -> date:
    if not isinstance(value, str):
        raise ReferenceFCRValidationError(f"{field_name} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReferenceFCRValidationError(f"{field_name} must be an ISO date") from exc


@dataclass(frozen=True, slots=True)
class ReferenceDecisionMappingDeclaration:
    mapping_id: str
    reference_commit: str
    source_fields: Mapping[str, str]
    source_sign_convention: str
    target_sign_convention: str
    x0_formula: str
    xr_formula: str
    activation_formula: str
    unit_conversions: tuple[str, ...]
    index_conversions: tuple[str, ...]
    source_timezone_interpretation: str
    target_period: CanonicalInterval
    mapping_fingerprint: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReferenceDecisionMappingDeclaration:
        raw = _mapping(payload, field_name="mapping")
        expected_fingerprint = _sha256(
            raw.get("mapping_fingerprint"), field_name="mapping.mapping_fingerprint"
        )
        fingerprint_payload = dict(raw)
        fingerprint_payload.pop("mapping_fingerprint", None)
        if _fingerprint(fingerprint_payload) != expected_fingerprint:
            raise ReferenceFCRIntegrityError("mapping fingerprint mismatch")
        source_fields_raw = _mapping(
            raw.get("source_fields"), field_name="mapping.source_fields"
        )
        source_fields = {
            _non_empty(key, field_name="mapping source field key"): _json_pointer(
                value, field_name=f"mapping.source_fields.{key}"
            )
            for key, value in source_fields_raw.items()
        }
        required_source_fields = {
            "battery",
            "day_ahead_prices",
            "expected_outputs",
            "fcr_prices",
            "x0",
            "xr",
        }
        if set(source_fields) != required_source_fields:
            raise ReferenceFCRValidationError(
                "mapping.source_fields must declare every required reference field"
            )
        target = _mapping(raw.get("target_period"), field_name="mapping.target_period")
        if target.get("market_timezone") != "Europe/Paris":
            raise ReferenceFCRValidationError(
                "mapping target period must use Europe/Paris"
            )
        if target.get("interval_convention") != "start-inclusive/end-exclusive":
            raise ReferenceFCRValidationError(
                "mapping target period must use the half-open interval convention"
            )
        try:
            start = datetime.fromisoformat(str(target.get("start_utc")).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(target.get("end_utc")).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReferenceFCRValidationError(
                "mapping target UTC period is invalid"
            ) from exc
        period = CanonicalInterval.from_utc(start, end, market_timezone="Europe/Paris")
        if (
            period.local_start.isoformat() != target.get("start_local")
            or period.local_end.isoformat() != target.get("end_local")
        ):
            raise ReferenceFCRValidationError(
                "mapping UTC and local delivery periods are inconsistent"
            )
        mapping_id = _non_empty(raw.get("mapping_id"), field_name="mapping.mapping_id")
        if mapping_id != REFERENCE_MAPPING_ID:
            raise ReferenceFCRValidationError("reference mapping ID is unsupported")
        reference_commit = _non_empty(
            raw.get("reference_commit"), field_name="mapping.reference_commit"
        )
        if _SHA1_PATTERN.fullmatch(reference_commit) is None:
            raise ReferenceFCRValidationError("mapping reference commit is invalid")
        source_sign = _non_empty(
            raw.get("source_sign_convention"),
            field_name="mapping.source_sign_convention",
        )
        target_sign = _non_empty(
            raw.get("target_sign_convention"),
            field_name="mapping.target_sign_convention",
        )
        if source_sign != "positive power is discharge":
            raise ReferenceFCRValidationError(
                "mapping source sign must explicitly declare discharge-positive power"
            )
        if target_sign != "positive power is charge":
            raise ReferenceFCRValidationError(
                "mapping target sign must explicitly declare charge-positive power"
            )
        unit_conversions = tuple(
            _non_empty(item, field_name="mapping unit conversion")
            for item in _sequence(
                raw.get("unit_conversions"), field_name="mapping.unit_conversions"
            )
        )
        index_conversions = tuple(
            _non_empty(item, field_name="mapping index conversion")
            for item in _sequence(
                raw.get("index_conversions"), field_name="mapping.index_conversions"
            )
        )
        return cls(
            mapping_id=mapping_id,
            reference_commit=reference_commit,
            source_fields=MappingProxyType(dict(sorted(source_fields.items()))),
            source_sign_convention=source_sign,
            target_sign_convention=target_sign,
            x0_formula=_non_empty(raw.get("x0_formula"), field_name="mapping.x0_formula"),
            xr_formula=_non_empty(raw.get("xr_formula"), field_name="mapping.xr_formula"),
            activation_formula=_non_empty(
                raw.get("activation_formula"), field_name="mapping.activation_formula"
            ),
            unit_conversions=unit_conversions,
            index_conversions=index_conversions,
            source_timezone_interpretation=_non_empty(
                raw.get("source_timezone_interpretation"),
                field_name="mapping.source_timezone_interpretation",
            ),
            target_period=period,
            mapping_fingerprint=expected_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class ExternalActivationDescriptor:
    input_id: str
    download_url: str
    superseded_locator: str | None
    local_relative_path: str
    byte_count: int
    sha256: str
    header: tuple[str, ...]
    selected_date: date
    selected_column: str
    selected_resolution: str
    selected_row_count: int
    retention_status: str
    redistribution_policy: Mapping[str, bool]

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_id", _non_empty(self.input_id, field_name="input_id"))
        download = _non_empty(self.download_url, field_name="download_url")
        if not download.startswith("https://"):
            raise ReferenceFCRValidationError("download_url must use HTTPS")
        object.__setattr__(self, "download_url", download)
        if self.superseded_locator is not None:
            object.__setattr__(
                self,
                "superseded_locator",
                _non_empty(self.superseded_locator, field_name="superseded_locator"),
            )
        relative = _non_empty(self.local_relative_path, field_name="local_relative_path")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise ReferenceFCRValidationError(
                "local_relative_path must be a safe repository-relative POSIX path"
            )
        object.__setattr__(self, "local_relative_path", relative)
        object.__setattr__(
            self, "byte_count", _integer(self.byte_count, field_name="byte_count", minimum=1)
        )
        object.__setattr__(self, "sha256", _sha256(self.sha256, field_name="sha256"))
        if len(self.header) < 2 or any(
            not isinstance(item, str) or not item for item in self.header
        ):
            raise ReferenceFCRValidationError("header must contain exact non-empty columns")
        if not isinstance(self.selected_date, date) or isinstance(
            self.selected_date, datetime
        ):
            raise ReferenceFCRValidationError("selected_date must be a date")
        object.__setattr__(
            self,
            "selected_column",
            _non_empty(self.selected_column, field_name="selected_column"),
        )
        parse_iso8601_duration(self.selected_resolution)
        object.__setattr__(
            self,
            "selected_row_count",
            _integer(self.selected_row_count, field_name="selected_row_count", minimum=1),
        )
        if self.retention_status != "external_only":
            raise ReferenceFCRValidationError(
                "external activation retention_status must be external_only"
            )
        policy = _mapping(
            self.redistribution_policy, field_name="redistribution_policy"
        )
        required = {"git", "package", "release", "mirror", "ci_artifact"}
        if set(policy) != required or any(value is not False for value in policy.values()):
            raise ReferenceFCRValidationError(
                "external activation redistribution policy must prohibit every channel"
            )
        object.__setattr__(self, "redistribution_policy", _freeze(policy))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ExternalActivationDescriptor:
        raw = _mapping(payload, field_name="external_activation")
        return cls(
            input_id=raw.get("input_id"),
            download_url=raw.get("download_url"),
            superseded_locator=raw.get("superseded_locator"),
            local_relative_path=raw.get("local_relative_path"),
            byte_count=raw.get("byte_count"),
            sha256=raw.get("sha256"),
            header=tuple(
                _sequence(raw.get("header"), field_name="external_activation.header")
            ),
            selected_date=_date(
                raw.get("selected_date"), field_name="external_activation.selected_date"
            ),
            selected_column=raw.get("selected_column"),
            selected_resolution=raw.get("selected_resolution"),
            selected_row_count=raw.get("selected_row_count"),
            retention_status=raw.get("retention_status"),
            redistribution_policy=raw.get("redistribution_policy"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "input_id": self.input_id,
            "download_url": self.download_url,
            "superseded_locator": self.superseded_locator,
            "local_relative_path": self.local_relative_path,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "header": list(self.header),
            "selected_date": self.selected_date.isoformat(),
            "selected_column": self.selected_column,
            "selected_resolution": self.selected_resolution,
            "selected_row_count": self.selected_row_count,
            "retention_status": self.retention_status,
            "redistribution_policy": _thaw(self.redistribution_policy),
        }


@dataclass(frozen=True, slots=True)
class ReferenceFieldBound:
    bound_id: str
    formula_id: str
    decision_bound: float
    unit: str
    dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bound_id", _non_empty(self.bound_id, field_name="bound_id"))
        object.__setattr__(
            self, "formula_id", _non_empty(self.formula_id, field_name="formula_id")
        )
        bound = _finite(self.decision_bound, field_name="decision_bound")
        if bound < 0.0:
            raise ReferenceFCRValidationError("decision_bound must be non-negative")
        object.__setattr__(self, "decision_bound", bound)
        object.__setattr__(self, "unit", _non_empty(self.unit, field_name="bound unit"))
        if not self.dependencies:
            raise ReferenceFCRValidationError("field bound dependencies cannot be empty")


@dataclass(frozen=True, slots=True)
class ReferencePrecisionPolicy:
    policy_id: str
    decision_decimal_places: int
    aggregate_decimal_places: int
    decision_half_unit_kw: float
    aggregate_half_unit: float
    propagation_method: str
    exact_rounding_mode: str
    field_bounds: Mapping[str, ReferenceFieldBound]
    policy_fingerprint: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReferencePrecisionPolicy:
        raw = _mapping(payload, field_name="precision_policy")
        expected_fingerprint = _sha256(
            raw.get("policy_fingerprint"),
            field_name="precision_policy.policy_fingerprint",
        )
        fingerprint_payload = dict(raw)
        fingerprint_payload.pop("policy_fingerprint", None)
        if _fingerprint(fingerprint_payload) != expected_fingerprint:
            raise ReferenceFCRIntegrityError("precision policy fingerprint mismatch")
        raw_bounds = _mapping(
            raw.get("field_bounds"), field_name="precision_policy.field_bounds"
        )
        bounds: dict[str, ReferenceFieldBound] = {}
        for bound_id, value in raw_bounds.items():
            item = _mapping(value, field_name=f"precision field bound {bound_id}")
            bounds[bound_id] = ReferenceFieldBound(
                bound_id=bound_id,
                formula_id=item.get("formula_id"),
                decision_bound=item.get("decision_bound"),
                unit=item.get("unit"),
                dependencies=tuple(
                    _non_empty(dep, field_name="precision dependency")
                    for dep in _sequence(
                        item.get("dependencies"),
                        field_name=f"precision field bound {bound_id} dependencies",
                    )
                ),
            )
        policy_id = _non_empty(
            raw.get("policy_id"), field_name="precision_policy.policy_id"
        )
        if policy_id != REFERENCE_PRECISION_POLICY_ID:
            raise ReferenceFCRValidationError("reference precision policy is unsupported")
        decision_places = _integer(
            raw.get("decision_decimal_places"),
            field_name="precision_policy.decision_decimal_places",
        )
        aggregate_places = _integer(
            raw.get("aggregate_decimal_places"),
            field_name="precision_policy.aggregate_decimal_places",
        )
        decision_half = _finite(
            raw.get("decision_half_unit_kw"),
            field_name="precision_policy.decision_half_unit_kw",
        )
        aggregate_half = _finite(
            raw.get("aggregate_half_unit"),
            field_name="precision_policy.aggregate_half_unit",
        )
        if decision_places != 3 or aggregate_places != 3:
            raise ReferenceFCRValidationError(
                "initial reference fixture must declare three-decimal precision"
            )
        if decision_half != 0.0005 or aggregate_half != 0.0005:
            raise ReferenceFCRValidationError(
                "reference half-unit declarations do not match three-decimal precision"
            )
        if raw.get("exact_rounding_mode") != "record_only":
            raise ReferenceFCRValidationError(
                "initial exact rounding mode must be record_only"
            )
        return cls(
            policy_id=policy_id,
            decision_decimal_places=decision_places,
            aggregate_decimal_places=aggregate_places,
            decision_half_unit_kw=decision_half,
            aggregate_half_unit=aggregate_half,
            propagation_method=_non_empty(
                raw.get("propagation_method"),
                field_name="precision_policy.propagation_method",
            ),
            exact_rounding_mode="record_only",
            field_bounds=MappingProxyType(dict(sorted(bounds.items()))),
            policy_fingerprint=expected_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class ReferenceExpectedField:
    field_id: str
    reference_field_path: str
    expected_value: object
    unit: str | None
    evidence_kind: str
    comparison_rule: str
    precision_bound_id: str | None
    reference_transform: str | None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReferenceExpectedField:
        raw = _mapping(payload, field_name="expected field")
        evidence = raw.get("evidence_kind")
        if evidence not in {"parity", "metadata", "unavailable"}:
            raise ReferenceFCRValidationError("expected field evidence_kind is invalid")
        rule = raw.get("comparison_rule")
        if rule not in {"exact", "source-precision", "metadata-only", "unavailable"}:
            raise ReferenceFCRValidationError("expected field comparison_rule is invalid")
        if evidence == "parity" and rule not in {"exact", "source-precision"}:
            raise ReferenceFCRValidationError("parity evidence needs a parity comparison rule")
        if evidence == "metadata" and rule != "metadata-only":
            raise ReferenceFCRValidationError("metadata evidence must be metadata-only")
        if isinstance(raw.get("expected_value"), (int, float)):
            expected: object = _finite(
                raw.get("expected_value"), field_name="expected field value"
            )
        else:
            expected = raw.get("expected_value")
        unit_raw = raw.get("unit")
        unit = None if unit_raw is None else _non_empty(unit_raw, field_name="expected unit")
        precision_id_raw = raw.get("precision_bound_id")
        precision_id = (
            None
            if precision_id_raw is None
            else _non_empty(precision_id_raw, field_name="precision_bound_id")
        )
        if rule == "source-precision" and precision_id is None:
            raise ReferenceFCRValidationError(
                "source-precision field must name a field-specific precision bound"
            )
        transform_raw = raw.get("reference_transform")
        transform = (
            None
            if transform_raw is None
            else _non_empty(transform_raw, field_name="reference_transform")
        )
        if transform not in {None, "negate"}:
            raise ReferenceFCRValidationError("reference_transform is unsupported")
        return cls(
            field_id=_non_empty(raw.get("field_id"), field_name="expected field_id"),
            reference_field_path=_json_pointer(
                raw.get("reference_field_path"), field_name="reference_field_path"
            ),
            expected_value=expected,
            unit=unit,
            evidence_kind=evidence,
            comparison_rule=rule,
            precision_bound_id=precision_id,
            reference_transform=transform,
        )


@dataclass(frozen=True, slots=True)
class UnsupportedReferenceField:
    field_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class GoldenReferenceFixture:
    schema_version: str
    fixture_id: str
    reference_provenance: Mapping[str, object]
    runtime_provenance: Mapping[str, object]
    reference_configuration: Mapping[str, object]
    rounded_x0_kw: tuple[float, ...]
    rounded_xr_kw: tuple[float, ...]
    p0_eur_per_kwh: tuple[float, ...]
    pr_eur_per_kw_block: tuple[float, ...]
    mapping: ReferenceDecisionMappingDeclaration
    external_activation: ExternalActivationDescriptor
    precision_policy: ReferencePrecisionPolicy
    expected_fields: tuple[ReferenceExpectedField, ...]
    unsupported_fields: tuple[UnsupportedReferenceField, ...]
    redistribution_status: Mapping[str, str]
    fixture_fingerprint: str
    _payload: Mapping[str, object] = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, object]:
        return _thaw(self._payload)


def _validate_reference_provenance(payload: Mapping[str, Any]) -> Mapping[str, object]:
    raw = _mapping(payload, field_name="reference_provenance")
    commit = _non_empty(raw.get("reference_commit"), field_name="reference_commit")
    if commit != REFERENCE_COMMIT:
        raise ReferenceFCRValidationError("reference commit does not match the pinned case")
    digest = _sha256(
        raw.get("original_result_sha256"), field_name="original_result_sha256"
    )
    if digest != REFERENCE_RESULT_SHA256:
        raise ReferenceFCRIntegrityError("original result digest does not match the pinned case")
    for name in (
        "generation_working_directory",
        "generation_command",
        "original_result_path",
    ):
        _non_empty(raw.get(name), field_name=name)
    paths = tuple(
        _non_empty(item, field_name="reference source path")
        for item in _sequence(
            raw.get("reference_source_paths"), field_name="reference_source_paths"
        )
    )
    required_paths = {
        "baselines/robust_storage_bidding/code/01_datastruct.jl",
        "baselines/robust_storage_bidding/code/02_model.jl",
        "baselines/robust_storage_bidding/code/03_backtest_save.jl",
        "baselines/robust_storage_bidding/code/04_parse_results.jl",
        "baselines/robust_storage_bidding/results/02/2023-06-18.json",
    }
    if set(paths) != required_paths:
        raise ReferenceFCRValidationError("reference source path provenance is incomplete")
    return _freeze(raw)


def _validate_runtime_provenance(payload: Mapping[str, Any]) -> Mapping[str, object]:
    raw = _mapping(payload, field_name="runtime_provenance")
    generation = _mapping(
        raw.get("generation_runtime"),
        field_name="runtime_provenance.generation_runtime",
    )
    if generation.get("status") not in {"recorded", "partially_recorded", "not_recorded"}:
        raise ReferenceFCRValidationError("generation runtime status is invalid")
    if generation.get("status") != "recorded":
        _non_empty(generation.get("reason"), field_name="generation runtime reason")
    locked = _mapping(
        raw.get("locked_manifest"), field_name="runtime_provenance.locked_manifest"
    )
    for name in ("julia_version", "manifest_format", "project_hash"):
        _non_empty(locked.get(name), field_name=f"locked manifest {name}")
    packages = _mapping(locked.get("packages"), field_name="locked manifest packages")
    required = {"CSV", "DataFrames", "Gurobi", "Gurobi_jll", "JSON", "JuMP"}
    if set(packages) != required:
        raise ReferenceFCRValidationError("locked manifest package provenance is incomplete")
    for name, version in packages.items():
        _non_empty(version, field_name=f"locked package {name}")
    return _freeze(raw)


def _validate_configuration(payload: Mapping[str, Any]) -> Mapping[str, object]:
    raw = _mapping(payload, field_name="reference_configuration")
    required_exact = {
        "test_date": "2023-06-18",
        "experiment": 2,
        "model_type": "restrict",
        "activation_series": "xi_EU",
        "energy_payment": True,
        "intraday_trading": False,
        "day_ahead": True,
        "day_ahead_limited": False,
        "reference_power_sign": "positive_is_discharge",
        "planning_interval_count": 96,
        "fcr_commitment_planning_intervals": 16,
        "saved_decimal_places": 3,
        "intraday_adjustment_kw": 0.0,
    }
    for key, expected in required_exact.items():
        if raw.get(key) != expected:
            raise ReferenceFCRValidationError(
                f"reference configuration {key} does not match the pinned case"
            )
    for key in (
        "max_discharge_kw",
        "max_charge_kw",
        "capacity_kwh",
        "minimum_stored_energy_kwh",
        "maximum_stored_energy_kwh",
        "initial_stored_energy_kwh",
        "charge_efficiency",
        "discharge_efficiency",
        "planning_resolution_hours",
        "activation_resolution_hours",
    ):
        _finite(raw.get(key), field_name=f"reference configuration {key}")
    if raw.get("charge_efficiency") != 0.92 or raw.get("discharge_efficiency") != 0.92:
        raise ReferenceFCRValidationError("reference efficiencies must both be 0.92")
    return _freeze(raw)


def _finite_vector(
    value: object,
    *,
    field_name: str,
    count: int,
    non_negative: bool = False,
) -> tuple[float, ...]:
    raw = _sequence(value, field_name=field_name)
    if len(raw) != count:
        raise ReferenceFCRValidationError(f"{field_name} must contain exactly {count} values")
    values = tuple(
        _finite(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(raw)
    )
    if non_negative and any(item < 0.0 for item in values):
        index = next(index for index, item in enumerate(values) if item < 0.0)
        raise ReferenceFCRValidationError(
            f"{field_name}[{index}] must be non-negative"
        )
    return values


def golden_reference_fixture_from_dict(
    payload: Mapping[str, Any],
) -> GoldenReferenceFixture:
    """Validate one normalized aggregate fixture without resolving provenance paths."""

    raw = _mapping(payload, field_name="golden reference fixture")
    missing = sorted(_REQUIRED_FIXTURE_SECTIONS - set(raw))
    unknown = sorted(set(raw) - _REQUIRED_FIXTURE_SECTIONS)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise ReferenceFCRValidationError(
            "golden reference fixture sections are invalid (" + "; ".join(details) + ")"
        )
    if raw.get("schema_version") != REFERENCE_FIXTURE_SCHEMA_VERSION:
        raise ReferenceFCRValidationError("golden reference fixture schema is unsupported")
    expected_fingerprint = _sha256(
        raw.get("fixture_fingerprint"), field_name="fixture_fingerprint"
    )
    fingerprint_payload = dict(raw)
    fingerprint_payload.pop("fixture_fingerprint", None)
    if _fingerprint(fingerprint_payload) != expected_fingerprint:
        raise ReferenceFCRIntegrityError("golden reference fixture fingerprint mismatch")
    reference_provenance = _validate_reference_provenance(
        _mapping(raw.get("reference_provenance"), field_name="reference_provenance")
    )
    runtime_provenance = _validate_runtime_provenance(
        _mapping(raw.get("runtime_provenance"), field_name="runtime_provenance")
    )
    configuration = _validate_configuration(
        _mapping(raw.get("reference_configuration"), field_name="reference_configuration")
    )
    decisions = _mapping(raw.get("fixed_decisions"), field_name="fixed_decisions")
    if decisions.get("x0_source_sign") != "positive_is_discharge":
        raise ReferenceFCRValidationError("x0 source sign is not declared")
    if decisions.get("xr_source_sign") != "non_negative_symmetric_capacity":
        raise ReferenceFCRValidationError("xr source capacity meaning is not declared")
    if decisions.get("x0_source_unit") != "kW" or decisions.get("xr_source_unit") != "kW":
        raise ReferenceFCRValidationError("fixed decision power units must be kW")
    _json_pointer(decisions.get("x0_source_path"), field_name="x0 source path")
    _json_pointer(decisions.get("xr_source_path"), field_name="xr source path")
    x0 = _finite_vector(
        decisions.get("rounded_x0_kw"), field_name="rounded_x0_kw", count=24
    )
    xr = _finite_vector(
        decisions.get("rounded_xr_kw"),
        field_name="rounded_xr_kw",
        count=6,
        non_negative=True,
    )
    prices = _mapping(raw.get("price_inputs"), field_name="price_inputs")
    if prices.get("p0_source_unit") != "EUR/kWh":
        raise ReferenceFCRValidationError("p0 source unit must be EUR/kWh")
    if prices.get("pr_source_unit") != "EUR/kW/4h-block":
        raise ReferenceFCRValidationError("pr source unit must be EUR/kW/4h-block")
    _json_pointer(prices.get("p0_source_path"), field_name="p0 source path")
    _json_pointer(prices.get("pr_source_path"), field_name="pr source path")
    p0 = _finite_vector(prices.get("p0"), field_name="p0", count=24)
    pr = _finite_vector(prices.get("pr"), field_name="pr", count=6)
    mapping = ReferenceDecisionMappingDeclaration.from_dict(
        _mapping(raw.get("mapping"), field_name="mapping")
    )
    if mapping.reference_commit != REFERENCE_COMMIT:
        raise ReferenceFCRValidationError("mapping commit differs from fixture provenance")
    descriptor = ExternalActivationDescriptor.from_dict(
        _mapping(raw.get("external_activation"), field_name="external_activation")
    )
    if (
        descriptor.byte_count != 528805941
        or descriptor.sha256
        != "0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13"
        or descriptor.header != ("DateTime", "Frequency (Hz)", "xi", "xi_EU")
        or descriptor.selected_date != date(2023, 6, 18)
        or descriptor.selected_column != "xi_EU"
        or descriptor.selected_resolution != "PT10S"
        or descriptor.selected_row_count != 8640
    ):
        raise ReferenceFCRValidationError(
            "external activation descriptor does not match the pinned v0.1 bytes"
        )
    precision = ReferencePrecisionPolicy.from_dict(
        _mapping(raw.get("precision_policy"), field_name="precision_policy")
    )
    expected = tuple(
        ReferenceExpectedField.from_dict(
            _mapping(value, field_name=f"expected_fields[{index}]")
        )
        for index, value in enumerate(
            _sequence(raw.get("expected_fields"), field_name="expected_fields")
        )
    )
    expected_ids = [item.field_id for item in expected]
    if len(set(expected_ids)) != len(expected_ids):
        raise ReferenceFCRValidationError("expected field IDs must be unique")
    for item in expected:
        if (
            item.precision_bound_id is not None
            and item.precision_bound_id not in precision.field_bounds
        ):
            raise ReferenceFCRValidationError(
                f"expected field {item.field_id} references an unknown precision bound"
            )
    unsupported = tuple(
        UnsupportedReferenceField(
            field_id=_non_empty(item.get("field_id"), field_name="unsupported field_id"),
            reason=_non_empty(item.get("reason"), field_name="unsupported field reason"),
        )
        for item in (
            _mapping(value, field_name=f"unsupported_fields[{index}]")
            for index, value in enumerate(
                _sequence(raw.get("unsupported_fields"), field_name="unsupported_fields")
            )
        )
    )
    unsupported_ids = [item.field_id for item in unsupported]
    if len(set(unsupported_ids)) != len(unsupported_ids):
        raise ReferenceFCRValidationError("unsupported field IDs must be unique")
    if set(expected_ids) & set(unsupported_ids):
        raise ReferenceFCRValidationError(
            "a reference field cannot be both expected and unsupported"
        )
    redistribution_raw = _mapping(
        raw.get("redistribution_status"), field_name="redistribution_status"
    )
    required_redistribution = {
        "original_result",
        "fixed_decisions",
        "price_inputs",
        "expected_aggregates",
        "mapping",
        "precision_policy",
        "activation_csv",
    }
    if set(redistribution_raw) != required_redistribution:
        raise ReferenceFCRValidationError("redistribution status is incomplete")
    redistribution = MappingProxyType(
        {
            key: _non_empty(value, field_name=f"redistribution status {key}")
            for key, value in sorted(redistribution_raw.items())
        }
    )
    if redistribution["activation_csv"] != "external_only":
        raise ReferenceFCRValidationError("activation CSV must remain external_only")
    frozen_payload = _freeze(raw)
    return GoldenReferenceFixture(
        schema_version=REFERENCE_FIXTURE_SCHEMA_VERSION,
        fixture_id=_non_empty(raw.get("fixture_id"), field_name="fixture_id"),
        reference_provenance=reference_provenance,
        runtime_provenance=runtime_provenance,
        reference_configuration=configuration,
        rounded_x0_kw=x0,
        rounded_xr_kw=xr,
        p0_eur_per_kwh=p0,
        pr_eur_per_kw_block=pr,
        mapping=mapping,
        external_activation=descriptor,
        precision_policy=precision,
        expected_fields=expected,
        unsupported_fields=unsupported,
        redistribution_status=redistribution,
        fixture_fingerprint=expected_fingerprint,
        _payload=frozen_payload,
    )


def load_golden_reference_fixture(path: str | Path) -> GoldenReferenceFixture:
    """Load only caller-selected committed bytes; provenance paths remain inert."""

    selected = Path(path)
    try:
        raw_bytes = selected.read_bytes()
    except OSError as exc:
        raise ReferenceFCRValidationError(
            f"cannot read golden reference fixture {selected}: {exc}"
        ) from exc
    try:
        payload = json.loads(
            raw_bytes.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ReferenceFCRValidationError(
            f"golden reference fixture is not finite UTF-8 JSON: {exc}"
        ) from exc
    return golden_reference_fixture_from_dict(
        _mapping(payload, field_name="golden reference fixture")
    )


def _external_error(
    descriptor: ExternalActivationDescriptor,
    path: Path,
    reason: str,
) -> ExternalReferenceDataError:
    return ExternalReferenceDataError(
        f"external reference activation is unavailable or invalid at {path}: {reason}. "
        f"Download {descriptor.download_url} and pass its path explicitly; the expected "
        f"project location is {descriptor.local_relative_path}."
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_reference_activation_trace(
    path: str | Path,
    *,
    descriptor: ExternalActivationDescriptor,
) -> RegulationActivationTrace:
    """Validate explicit external bytes and build the existing activation trace."""

    if not isinstance(descriptor, ExternalActivationDescriptor):
        raise ReferenceFCRValidationError(
            "descriptor must be an ExternalActivationDescriptor"
        )
    selected_path = Path(path)
    if selected_path.is_symlink():
        raise _external_error(descriptor, selected_path, "symbolic links are not accepted")
    if not selected_path.is_file():
        raise _external_error(descriptor, selected_path, "the path is not a regular file")
    size = selected_path.stat().st_size
    if size != descriptor.byte_count:
        raise _external_error(
            descriptor,
            selected_path,
            f"byte count {size} does not match {descriptor.byte_count}",
        )
    try:
        digest = _file_sha256(selected_path)
    except OSError as exc:
        raise _external_error(descriptor, selected_path, f"cannot hash the file: {exc}") from exc
    if digest != descriptor.sha256:
        raise _external_error(
            descriptor,
            selected_path,
            f"SHA-256 {digest} does not match {descriptor.sha256}",
        )

    try:
        expected_intervals = build_local_delivery_day(
            descriptor.selected_date,
            resolution=descriptor.selected_resolution,
            market_timezone="Europe/Paris",
        )
    except ValueError as exc:
        raise _external_error(
            descriptor, selected_path, f"selected delivery day is unsupported: {exc}"
        ) from exc
    if len(expected_intervals) != descriptor.selected_row_count:
        raise _external_error(
            descriptor,
            selected_path,
            "selected day is a daylight-saving transition or has an incompatible row count",
        )

    selected_rows: list[tuple[datetime, float]] = []
    try:
        with selected_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or tuple(reader.fieldnames) != descriptor.header:
                raise _external_error(
                    descriptor,
                    selected_path,
                    f"header {reader.fieldnames!r} does not match {descriptor.header!r}",
                )
            if descriptor.selected_column not in reader.fieldnames:
                raise _external_error(
                    descriptor,
                    selected_path,
                    f"selected column {descriptor.selected_column!r} is absent",
                )
            date_prefix = descriptor.selected_date.isoformat()
            for row_number, row in enumerate(reader, start=2):
                timestamp_text = row.get("DateTime")
                if not isinstance(timestamp_text, str):
                    continue
                if not timestamp_text.startswith(date_prefix):
                    continue
                try:
                    timestamp = datetime.strptime(
                        timestamp_text, "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError as exc:
                    raise _external_error(
                        descriptor,
                        selected_path,
                        f"row {row_number} has an invalid selected timestamp",
                    ) from exc
                raw_value = row.get(descriptor.selected_column)
                try:
                    value = float(raw_value) if raw_value is not None else math.nan
                except ValueError as exc:
                    raise _external_error(
                        descriptor,
                        selected_path,
                        f"row {row_number} has a nonnumeric activation value",
                    ) from exc
                if not math.isfinite(value):
                    raise _external_error(
                        descriptor,
                        selected_path,
                        f"row {row_number} has a nonfinite activation value",
                    )
                if value < -1.0 or value > 1.0:
                    raise _external_error(
                        descriptor,
                        selected_path,
                        f"row {row_number} activation is outside [-1, 1]",
                    )
                selected_rows.append((timestamp, value))
    except UnicodeDecodeError as exc:
        raise _external_error(descriptor, selected_path, "file is not UTF-8 CSV") from exc
    except OSError as exc:
        raise _external_error(descriptor, selected_path, f"cannot parse the CSV: {exc}") from exc

    if len(selected_rows) != descriptor.selected_row_count:
        raise _external_error(
            descriptor,
            selected_path,
            f"selected row count {len(selected_rows)} does not match {descriptor.selected_row_count}",
        )
    source_samples: list[dict[str, object]] = []
    for index, ((timestamp, value), interval) in enumerate(
        zip(selected_rows, expected_intervals, strict=True)
    ):
        expected_label = interval.local_start.replace(tzinfo=None)
        if timestamp != expected_label:
            relation = "duplicate, gap, overlap, or out-of-order timestamp"
            raise _external_error(
                descriptor,
                selected_path,
                f"selected row {index} has a {relation}: {timestamp} != {expected_label}",
            )
        source_samples.append(
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "value": value,
                "source_value": value,
                "source_unit": "dimensionless",
            }
        )

    covered = CanonicalInterval.from_utc(
        expected_intervals[0].start_utc,
        expected_intervals[-1].end_utc,
        market_timezone="Europe/Paris",
    )
    request = ActivationImportRequest(
        source_name="robust-storage-bidding regulation signal",
        source_locator=str(selected_path),
        source_revision=descriptor.sha256,
        source_timezone="Europe/Paris",
        requested_start_utc=covered.start_utc,
        requested_end_utc=covered.end_utc,
        source_resolution=descriptor.selected_resolution,
        source_value_kind="interval_average",
        source_sign_meaning="positive xi_EU means upward/discharge activation",
        normalization_rule={
            "conversion": "identity",
            "formula": "activation = xi_EU",
            "point_to_interval": "already_interval_average",
            "clip_min": -1.0,
            "clip_max": 1.0,
            "target_sign": "positive is upward/discharge",
        },
        redistribution_basis={
            "retention_status": descriptor.retention_status,
            "redistribution_policy": _thaw(descriptor.redistribution_policy),
        },
        source_sha256=descriptor.sha256,
        source_document_type="reference-regulation-csv",
    )
    return import_regulation_activation_trace(
        request,
        source_samples,
        trace_id=f"{descriptor.input_id}-{descriptor.selected_date.isoformat()}",
        created_at_utc=REFERENCE_ACTIVATION_ARTIFACT_CREATED_AT_UTC,
    )


def build_reference_market_context(
    fixture: GoldenReferenceFixture,
    *,
    energy_schedule: object,
    fcr_schedule: object,
) -> object:
    """Assemble source-independent price and accepted-bid evidence.

    Imports stay local so ordinary market-package imports do not acquire simulator
    ownership or eager dependencies.
    """

    from open_energy_lab.simulator.fcr_bid_evaluation import (
        EvaluationMarketContext,
        EvaluationPriceObservation,
    )
    from open_energy_lab.simulator.stacked_service import (
        EnergyBaselineSchedule,
        FCRCapacitySchedule,
    )

    if not isinstance(fixture, GoldenReferenceFixture):
        raise ReferenceFCRValidationError("fixture must be a GoldenReferenceFixture")
    if not isinstance(energy_schedule, EnergyBaselineSchedule):
        raise ReferenceFCRValidationError("energy_schedule has the wrong product type")
    if not isinstance(fcr_schedule, FCRCapacitySchedule):
        raise ReferenceFCRValidationError("fcr_schedule has the wrong product type")
    if (
        energy_schedule.covered_period != fixture.mapping.target_period
        or fcr_schedule.covered_period != fixture.mapping.target_period
    ):
        raise ReferenceFCRValidationError(
            "reference schedules do not match the declared fixture period"
        )
    if len(energy_schedule.intervals) != 24 or len(fcr_schedule.intervals) != 6:
        raise ReferenceFCRValidationError("reference schedules must contain 24/6 intervals")
    day_prices = tuple(
        EvaluationPriceObservation(
            interval=schedule.interval,
            price_kind="day_ahead_energy",
            source_value=source_value,
            source_unit="EUR/kWh",
            canonical_value=source_value * 1000.0,
            canonical_unit="EUR/MWh",
            conversion_id="reference-p0-eur-per-kwh-to-eur-per-mwh-v1",
            source_ref=f"/price_inputs/p0/{index}",
        )
        for index, (schedule, source_value) in enumerate(
            zip(energy_schedule.intervals, fixture.p0_eur_per_kwh, strict=True)
        )
    )
    capacity_prices = tuple(
        EvaluationPriceObservation(
            interval=commitment.interval,
            price_kind="fcr_capacity",
            source_value=source_value,
            source_unit="EUR/kW/4h-block",
            canonical_value=source_value,
            canonical_unit="EUR/kW/block",
            conversion_id="reference-pr-eur-per-kw-block-identity-v1",
            source_ref=f"reference_fcr_capacity_price:{index}",
        )
        for index, (commitment, source_value) in enumerate(
            zip(fcr_schedule.intervals, fixture.pr_eur_per_kw_block, strict=True)
        )
    )
    accepted = {
        f"reference_accepted_fcr_bid:{index}": {
            "capacity_kw": commitment.capacity_kw,
            "unit": "kW",
            "evidence_kind": "reference_fixed_decision",
            "source_ref": f"/fixed_decisions/rounded_xr_kw/{index}",
        }
        for index, commitment in enumerate(fcr_schedule.intervals)
    }
    return EvaluationMarketContext(
        context_kind="reference_result",
        semantics_version="robust-storage-bidding-reference-context-v1",
        period=fixture.mapping.target_period,
        day_ahead_prices=day_prices,
        fcr_capacity_prices=capacity_prices,
        accepted_bid_evidence=accepted,
        source_fingerprints={
            "golden_reference_fixture": fixture.fixture_fingerprint,
            "reference_mapping": fixture.mapping.mapping_fingerprint,
        },
    )


__all__ = [
    "ExternalActivationDescriptor",
    "ExternalReferenceDataError",
    "GoldenReferenceFixture",
    "REFERENCE_FIXTURE_SCHEMA_VERSION",
    "REFERENCE_MAPPING_ID",
    "REFERENCE_PRECISION_POLICY_ID",
    "ReferenceDecisionMappingDeclaration",
    "ReferenceExpectedField",
    "ReferenceFCRIntegrityError",
    "ReferenceFCRValidationError",
    "ReferenceFieldBound",
    "ReferencePrecisionPolicy",
    "UnsupportedReferenceField",
    "build_reference_market_context",
    "canonical_reference_json_bytes",
    "golden_reference_fixture_from_dict",
    "load_golden_reference_fixture",
    "load_reference_activation_trace",
]
