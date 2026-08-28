"""Immutable contracts and deterministic orchestration for Feature 015.

The public objects in this module describe rolling studies without importing a
solver, simulator implementation, source runtime, dataframe stack, network
client, or credential provider.  Optimization is delegated lazily to Feature
013 and :mod:`open_energy_lab.control.robust_fcr_rolling`; physical replay and
settlement are delegated to Feature 012 by the private orchestrator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

from .robust_fcr_bidding import (
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRTimeContract,
    RobustFCRUncertaintyProfile,
    TerminalStoredEnergyRule,
    _deep_freeze,
    _fingerprint,
    _sha256,
    _thaw,
)


ROLLING_FCR_STUDY_MANIFEST_VERSION = "oel.fcr-rolling-study-manifest.v1"
ROLLING_FCR_DATA_DESCRIPTOR_VERSION = "oel.fcr-rolling-data-descriptor.v1"
ROLLING_FCR_ACCEPTED_BID_POLICY_VERSION = "oel.fcr-accepted-bid-policy.v1"
ROLLING_FCR_NUMERIC_POLICY_VERSION = "oel.fcr-rolling-numeric-policy.v1"
ROLLING_FCR_BATTERY_BINDING_VERSION = "oel.fcr-rolling-battery-binding.v1"
ROLLING_FCR_DAY_INPUT_VERSION = "oel.fcr-rolling-day-input.v1"
ROLLING_FCR_STUDY_RESULT_VERSION = "oel.fcr-rolling-study-result.v1"
ROLLING_FCR_RESUME_EVIDENCE_VERSION = "oel.fcr-rolling-resume-evidence.v1"
ROLLING_FCR_PROFILE_VERSION = "oel.fcr-rolling-experiment-profile.v1"
ROLLING_FCR_STATE_CARRY_EVIDENCE_VERSION = "oel.fcr-state-carry-evidence.v1"

SOURCE_REFERENCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
FAILURE_POLICY_INDEPENDENT = "independent-days-continue-after-failure-v1"
FAILURE_POLICY_COUPLED = "coupled-days-block-after-failure-v1"
AGGREGATION_POLICY = "coverage-labelled-no-zero-fill-v1"
RESUME_POLICY = "exact-semantic-evidence-v1"

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_PROFILE_IDS = (
    "script-11-relaxation-reset-midnight-v1",
    "script-12-restriction-reset-midnight-v1",
    "script-13-arbitrage-only-midnight-v1",
    "script-14-restriction-rolling-0800-v1",
    "script-15-restriction-rolling-midnight-v1",
)
_DATE_ROLES = {"included", "warm-up", "close-out", "excluded"}
_LIFECYCLE_STATUSES = {
    "original",
    "initialization_only",
    "optimization_only",
    "provisional",
    "finalized",
    "failed",
    "blocked_by_predecessor",
    "excluded",
    "unfinalized",
}
_REVISION_KINDS = {"original", "optimization_only", "provisional", "finalized"}
_TERMINAL_LIFECYCLE_STATUSES = {
    "initialization_only",
    "optimization_only",
    "provisional",
    "finalized",
    "failed",
    "blocked_by_predecessor",
    "excluded",
    "unfinalized",
}
_VOLATILE_RUNTIME_KEY_TERMS = (
    "duration",
    "runtime_seconds",
    "elapsed",
    "started_at",
    "finished_at",
    "wall_clock",
    "cpu_time",
    "host",
    "hostname",
    "process",
    "pid",
    "path",
    "directory",
    "cwd",
    "filename",
    "log_text",
    "temporary",
    "tee",
)
_DESCRIPTOR_RULES = {
    "day_ahead_price": ("EUR/kWh", "PT1H", "hourly-delivery-interval-v1"),
    "fcr_capacity_price": (
        "EUR/kW/4h-block",
        "PT4H",
        "six-four-hour-delivery-blocks-v1",
    ),
    "regulation_activation": (
        "dimensionless",
        "PT10S",
        "ten-second-half-open-activation-v1",
    ),
}
_BIDDER_FORBIDDEN_TERMS = (
    "activation",
    "realized",
    "replay",
    "settlement",
    "comparison",
    "parity",
    "future",
    "credential",
    "password",
    "secret",
    "token",
    "environment",
)
_DESCRIPTOR_PROVENANCE_FORBIDDEN_TERMS = (
    "path",
    "file",
    "locator",
    "url",
    "credential",
    "password",
    "secret",
    "token",
)


class RollingFCRValidationError(ValueError):
    """Raised before a rolling solve or replay when a contract is invalid."""


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RollingFCRValidationError(f"{field_name} must be a non-empty string")
    return value


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RollingFCRValidationError(f"{field_name} must be finite")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise RollingFCRValidationError(f"{field_name} must be finite")
    return 0.0 if normalized == 0.0 else normalized


def _positive(value: object, *, field_name: str) -> float:
    normalized = _finite(value, field_name=field_name)
    if normalized <= 0.0:
        raise RollingFCRValidationError(f"{field_name} must be greater than zero")
    return normalized


def _utc(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RollingFCRValidationError(f"{field_name} must be an aware UTC datetime")
    if value.utcoffset() != timedelta(0):
        raise RollingFCRValidationError(f"{field_name} must be an aware UTC datetime")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha(value: object, *, field_name: str) -> str:
    try:
        return _sha256(value, field_name=field_name)
    except ValueError as exc:
        raise RollingFCRValidationError(str(exc)) from exc


def _string_tuple(value: Sequence[object], *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise RollingFCRValidationError(f"{field_name} must be a sequence")
    return tuple(
        _non_empty(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _freeze_mapping(value: Mapping[str, object], *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RollingFCRValidationError(f"{field_name} must be a mapping")
    try:
        return _deep_freeze(value, field_name=field_name)
    except ValueError as exc:
        raise RollingFCRValidationError(str(exc)) from exc


def _validate_mapping_keys(
    value: Mapping[str, object],
    *,
    field_name: str,
    forbidden_terms: tuple[str, ...],
) -> None:
    for key, inner in value.items():
        normalized = _non_empty(key, field_name=f"{field_name} key")
        lowered = normalized.casefold()
        if any(term in lowered for term in forbidden_terms):
            raise RollingFCRValidationError(
                f"{field_name}.{normalized} contains forbidden evidence"
            )
        if isinstance(inner, Mapping):
            _validate_mapping_keys(
                inner,
                field_name=f"{field_name}.{normalized}",
                forbidden_terms=forbidden_terms,
            )


def _contract_dict(value: object, *, field_name: str) -> Mapping[str, object]:
    method = getattr(value, "to_dict", None)
    if method is None:
        raise RollingFCRValidationError(f"{field_name} must provide to_dict()")
    payload = method()
    if not isinstance(payload, Mapping):
        raise RollingFCRValidationError(f"{field_name}.to_dict() must return a mapping")
    return payload


def _strict_mapping(
    value: object,
    *,
    field_name: str,
    required_keys: frozenset[str],
    optional_keys: frozenset[str] = frozenset(),
) -> Mapping[str, object]:
    """Return one mapping only when its schema keys match exactly."""

    if not isinstance(value, Mapping):
        raise RollingFCRValidationError(f"{field_name} must be a mapping")
    keys = set(value)
    missing = required_keys - keys
    unknown = keys - required_keys - optional_keys
    if missing:
        raise RollingFCRValidationError(
            f"{field_name} is missing required keys: {sorted(missing)}"
        )
    if unknown:
        raise RollingFCRValidationError(
            f"{field_name} contains unknown keys: {sorted(unknown)}"
        )
    if any(not isinstance(key, str) for key in keys):
        raise RollingFCRValidationError(f"{field_name} keys must be strings")
    return value


def _date_from_text(value: object, *, field_name: str) -> date:
    if not isinstance(value, str):
        raise RollingFCRValidationError(f"{field_name} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise RollingFCRValidationError(f"{field_name} must be an ISO date") from exc
    return parsed


def _utc_from_text(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RollingFCRValidationError(f"{field_name} must be an ISO UTC timestamp")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as exc:
        raise RollingFCRValidationError(
            f"{field_name} must be an ISO UTC timestamp"
        ) from exc
    return _utc(parsed, field_name=field_name)


def _semantic_runtime_metadata(value: Mapping[str, object]) -> dict[str, object]:
    """Keep stable backend/version evidence and remove volatile execution facts."""

    def filtered(inner: object) -> object:
        if isinstance(inner, Mapping):
            result: dict[str, object] = {}
            for key, item in sorted(inner.items()):
                normalized = str(key)
                lowered = normalized.casefold()
                if any(term in lowered for term in _VOLATILE_RUNTIME_KEY_TERMS):
                    continue
                result[normalized] = filtered(item)
            return result
        if isinstance(inner, tuple):
            return [filtered(item) for item in inner]
        return inner

    result = filtered(value)
    assert isinstance(result, dict)
    return result


def _verify_persisted_fingerprint(
    *,
    field_name: str,
    provided: object,
    recomputed: str,
) -> None:
    normalized = _sha(provided, field_name=field_name)
    if normalized != recomputed:
        raise RollingFCRValidationError(
            f"{field_name} does not match recomputed semantic evidence"
        )


@dataclass(frozen=True, slots=True)
class RollingFCRDataDescriptor:
    """Fingerprint-only description of one governed input data family."""

    descriptor_id: str
    kind: str
    schema_version: str
    unit: str
    sign_convention: str
    timezone: str
    temporal_resolution: str
    mapping_rule_id: str
    coverage_start_utc: datetime
    coverage_end_utc: datetime
    source_organization: str
    source_document_id: str
    acquisition_cutoff_utc: datetime
    content_sha256: str
    normalized_data_fingerprint: str
    provenance: Mapping[str, object]
    semantics_version: str = ROLLING_FCR_DATA_DESCRIPTOR_VERSION
    descriptor_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "descriptor_id", _non_empty(self.descriptor_id, field_name="descriptor_id"))
        if self.kind not in _DESCRIPTOR_RULES:
            raise RollingFCRValidationError(
                "descriptor kind must be day_ahead_price, fcr_capacity_price, or regulation_activation"
            )
        if self.semantics_version != ROLLING_FCR_DATA_DESCRIPTOR_VERSION:
            raise RollingFCRValidationError("unsupported rolling data descriptor version")
        expected_unit, expected_resolution, expected_mapping = _DESCRIPTOR_RULES[self.kind]
        if self.unit != expected_unit:
            raise RollingFCRValidationError(
                f"{self.kind} descriptor unit must equal {expected_unit}"
            )
        if self.temporal_resolution != expected_resolution:
            raise RollingFCRValidationError(
                f"{self.kind} descriptor resolution must equal {expected_resolution}"
            )
        if self.mapping_rule_id != expected_mapping:
            raise RollingFCRValidationError(
                f"{self.kind} descriptor mapping_rule_id must equal {expected_mapping}"
            )
        start = _utc(self.coverage_start_utc, field_name="coverage_start_utc")
        end = _utc(self.coverage_end_utc, field_name="coverage_end_utc")
        cutoff = _utc(self.acquisition_cutoff_utc, field_name="acquisition_cutoff_utc")
        if end <= start:
            raise RollingFCRValidationError("descriptor coverage must be nonempty")
        provenance = _freeze_mapping(self.provenance, field_name="provenance")
        _validate_mapping_keys(
            provenance,
            field_name="provenance",
            forbidden_terms=_DESCRIPTOR_PROVENANCE_FORBIDDEN_TERMS,
        )
        object.__setattr__(self, "schema_version", _non_empty(self.schema_version, field_name="schema_version"))
        object.__setattr__(self, "sign_convention", _non_empty(self.sign_convention, field_name="sign_convention"))
        object.__setattr__(self, "timezone", _non_empty(self.timezone, field_name="timezone"))
        object.__setattr__(self, "source_organization", _non_empty(self.source_organization, field_name="source_organization"))
        object.__setattr__(self, "source_document_id", _non_empty(self.source_document_id, field_name="source_document_id"))
        object.__setattr__(self, "coverage_start_utc", start)
        object.__setattr__(self, "coverage_end_utc", end)
        object.__setattr__(self, "acquisition_cutoff_utc", cutoff)
        object.__setattr__(self, "content_sha256", _sha(self.content_sha256, field_name="content_sha256"))
        object.__setattr__(self, "normalized_data_fingerprint", _sha(self.normalized_data_fingerprint, field_name="normalized_data_fingerprint"))
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "descriptor_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "descriptor_id": self.descriptor_id,
            "kind": self.kind,
            "schema_version": self.schema_version,
            "unit": self.unit,
            "sign_convention": self.sign_convention,
            "timezone": self.timezone,
            "temporal_resolution": self.temporal_resolution,
            "mapping_rule_id": self.mapping_rule_id,
            "coverage_start_utc": _utc_text(self.coverage_start_utc),
            "coverage_end_utc": _utc_text(self.coverage_end_utc),
            "source_organization": self.source_organization,
            "source_document_id": self.source_document_id,
            "acquisition_cutoff_utc": _utc_text(self.acquisition_cutoff_utc),
            "content_sha256": self.content_sha256,
            "normalized_data_fingerprint": self.normalized_data_fingerprint,
            "provenance": _thaw(self.provenance),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "descriptor_fingerprint": self.descriptor_fingerprint}


@dataclass(frozen=True, slots=True)
class AcceptedBidPolicy:
    """Explicit individual-plan acceptance assumption or evidence contract."""

    policy_id: str
    kind: str
    assumption_statement: str | None = None
    evidence_descriptor: Mapping[str, object] | None = None
    reject_system_volume_as_individual_evidence: bool = True
    semantics_version: str = ROLLING_FCR_ACCEPTED_BID_POLICY_VERSION
    policy_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, field_name="policy_id"))
        if self.kind not in {"assumed_accepted", "evidence_backed_accepted"}:
            raise RollingFCRValidationError(
                "accepted-bid policy kind must be assumed_accepted or evidence_backed_accepted"
            )
        if self.reject_system_volume_as_individual_evidence is not True:
            raise RollingFCRValidationError(
                "accepted-bid policy must reject system-wide volume as individual evidence"
            )
        if self.semantics_version != ROLLING_FCR_ACCEPTED_BID_POLICY_VERSION:
            raise RollingFCRValidationError("unsupported accepted-bid policy version")
        if self.kind == "assumed_accepted":
            statement = _non_empty(self.assumption_statement, field_name="assumption_statement")
            if self.evidence_descriptor is not None:
                raise RollingFCRValidationError(
                    "assumed acceptance must not claim an observed award descriptor"
                )
            object.__setattr__(self, "assumption_statement", statement)
        else:
            if self.assumption_statement is not None:
                raise RollingFCRValidationError(
                    "evidence-backed acceptance must not carry an assumption statement"
                )
            descriptor = _freeze_mapping(
                self.evidence_descriptor or {}, field_name="evidence_descriptor"
            )
            if descriptor.get("kind") == "system_wide_contracted_reserve_volume":
                raise RollingFCRValidationError(
                    "system-wide contracted reserve volume is not individual acceptance evidence"
                )
            if descriptor.get("kind") != "individual_bid_award":
                raise RollingFCRValidationError(
                    "evidence-backed acceptance requires an individual_bid_award descriptor"
                )
            _sha(descriptor.get("content_fingerprint"), field_name="evidence_descriptor.content_fingerprint")
            object.__setattr__(self, "evidence_descriptor", descriptor)
        object.__setattr__(self, "policy_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "policy_id": self.policy_id,
            "kind": self.kind,
            "assumption_statement": self.assumption_statement,
            "evidence_descriptor": (
                None if self.evidence_descriptor is None else _thaw(self.evidence_descriptor)
            ),
            "reject_system_volume_as_individual_evidence": True,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "policy_fingerprint": self.policy_fingerprint}


@dataclass(frozen=True, slots=True)
class DeliveryDateClassification:
    delivery_date: date
    execution_role: str
    comparison_eligible: bool
    reason_codes: tuple[str, ...] = ()
    classification_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.delivery_date, date) or isinstance(self.delivery_date, datetime):
            raise RollingFCRValidationError("delivery_date must be a date")
        if self.execution_role not in _DATE_ROLES:
            raise RollingFCRValidationError("unsupported delivery-date execution role")
        if not isinstance(self.comparison_eligible, bool):
            raise RollingFCRValidationError("comparison_eligible must be boolean")
        if self.comparison_eligible and self.execution_role != "included":
            raise RollingFCRValidationError("only included dates may be comparison eligible")
        reasons = _string_tuple(self.reason_codes, field_name="reason_codes")
        object.__setattr__(self, "reason_codes", tuple(sorted(reasons)))
        object.__setattr__(self, "classification_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "delivery_date": self.delivery_date.isoformat(),
            "execution_role": self.execution_role,
            "comparison_eligible": self.comparison_eligible,
            "reason_codes": list(self.reason_codes),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "classification_fingerprint": self.classification_fingerprint}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DeliveryDateClassification:
        data = _strict_mapping(
            payload,
            field_name="date classification",
            required_keys=frozenset(
                {
                    "delivery_date",
                    "execution_role",
                    "comparison_eligible",
                    "reason_codes",
                    "classification_fingerprint",
                }
            ),
        )
        reasons = data["reason_codes"]
        if not isinstance(reasons, Sequence) or isinstance(reasons, (str, bytes)):
            raise RollingFCRValidationError(
                "date classification reason_codes must be a sequence"
            )
        result = cls(
            delivery_date=_date_from_text(
                data["delivery_date"], field_name="classification.delivery_date"
            ),
            execution_role=data["execution_role"],  # type: ignore[arg-type]
            comparison_eligible=data["comparison_eligible"],  # type: ignore[arg-type]
            reason_codes=tuple(reasons),  # type: ignore[arg-type]
        )
        _verify_persisted_fingerprint(
            field_name="classification_fingerprint",
            provided=data["classification_fingerprint"],
            recomputed=result.classification_fingerprint,
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRNumericPolicy:
    solve_policy_fingerprint: str
    state_carry_policy: str
    decimal_places: int
    rounding_mode: str = "ROUND_HALF_EVEN"
    signed_zero_rule: str = "normalize_to_positive_zero"
    closed_interval_rule: str = "displayed-half-ulp-closed-v1"
    state_link_tolerance_kwh: float = 1e-7
    aggregate_reconciliation_tolerance: float = 1e-7
    semantics_version: str = ROLLING_FCR_NUMERIC_POLICY_VERSION
    numeric_policy_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "solve_policy_fingerprint", _sha(self.solve_policy_fingerprint, field_name="solve_policy_fingerprint"))
        if self.state_carry_policy not in {"source_three_decimal", "native_full_precision"}:
            raise RollingFCRValidationError("unsupported state_carry_policy")
        if isinstance(self.decimal_places, bool) or not isinstance(self.decimal_places, int):
            raise RollingFCRValidationError("decimal_places must be an integer")
        if self.state_carry_policy == "source_three_decimal" and self.decimal_places != 3:
            raise RollingFCRValidationError("source carry must use exactly three decimals")
        if self.state_carry_policy == "native_full_precision" and self.decimal_places != 0:
            raise RollingFCRValidationError("native full precision must not declare display rounding")
        if self.rounding_mode != "ROUND_HALF_EVEN":
            raise RollingFCRValidationError("unsupported rolling rounding mode")
        if self.signed_zero_rule != "normalize_to_positive_zero":
            raise RollingFCRValidationError("unsupported signed-zero rule")
        if self.closed_interval_rule != "displayed-half-ulp-closed-v1":
            raise RollingFCRValidationError("unsupported source precision interval rule")
        if self.semantics_version != ROLLING_FCR_NUMERIC_POLICY_VERSION:
            raise RollingFCRValidationError("unsupported rolling numeric policy version")
        object.__setattr__(self, "state_link_tolerance_kwh", _positive(self.state_link_tolerance_kwh, field_name="state_link_tolerance_kwh"))
        object.__setattr__(self, "aggregate_reconciliation_tolerance", _positive(self.aggregate_reconciliation_tolerance, field_name="aggregate_reconciliation_tolerance"))
        object.__setattr__(self, "numeric_policy_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "solve_policy_fingerprint": self.solve_policy_fingerprint,
            "state_carry_policy": self.state_carry_policy,
            "decimal_places": self.decimal_places,
            "rounding_mode": self.rounding_mode,
            "signed_zero_rule": self.signed_zero_rule,
            "closed_interval_rule": self.closed_interval_rule,
            "state_link_tolerance_kwh": self.state_link_tolerance_kwh,
            "aggregate_reconciliation_tolerance": self.aggregate_reconciliation_tolerance,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "numeric_policy_fingerprint": self.numeric_policy_fingerprint}


@dataclass(frozen=True, slots=True)
class RollingFCRStateCarryEvidence:
    """Deterministic full-precision or source-rounded state handoff."""

    replay_checkpoint_kwh: float
    carried_stored_energy_kwh: float
    state_carry_policy: str
    decimal_input_text: str
    carried_decimal_text: str
    source_interval_kwh: tuple[float, float]
    rounding_applied: bool
    signed_zero_normalized: bool
    semantics_version: str = ROLLING_FCR_STATE_CARRY_EVIDENCE_VERSION
    evidence_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        checkpoint = _finite(
            self.replay_checkpoint_kwh,
            field_name="replay_checkpoint_kwh",
        )
        carried = _finite(
            self.carried_stored_energy_kwh,
            field_name="carried_stored_energy_kwh",
        )
        if self.state_carry_policy not in {
            "source_three_decimal",
            "native_full_precision",
        }:
            raise RollingFCRValidationError("unsupported state-carry evidence policy")
        if self.semantics_version != ROLLING_FCR_STATE_CARRY_EVIDENCE_VERSION:
            raise RollingFCRValidationError("unsupported state-carry evidence version")
        decimal_input = _non_empty(
            self.decimal_input_text,
            field_name="decimal_input_text",
        )
        carried_decimal = _non_empty(
            self.carried_decimal_text,
            field_name="carried_decimal_text",
        )
        try:
            parsed_input = Decimal(decimal_input)
            parsed_carried = Decimal(carried_decimal)
        except Exception as exc:
            raise RollingFCRValidationError(
                "state-carry decimal evidence is malformed"
            ) from exc
        if parsed_input != Decimal(str(checkpoint)):
            raise RollingFCRValidationError(
                "decimal input evidence does not match the replay checkpoint"
            )
        if float(parsed_carried) != carried:
            raise RollingFCRValidationError(
                "carried decimal evidence does not match the carried state"
            )
        interval = tuple(
            _finite(value, field_name="source_interval_kwh")
            for value in self.source_interval_kwh
        )
        if len(interval) != 2 or interval[0] > interval[1]:
            raise RollingFCRValidationError(
                "state-carry source interval must contain two ordered endpoints"
            )
        if not interval[0] <= checkpoint <= interval[1]:
            raise RollingFCRValidationError(
                "closed source interval must contain the replay checkpoint"
            )
        if not interval[0] <= carried <= interval[1]:
            raise RollingFCRValidationError(
                "closed source interval must contain the carried state"
            )
        if self.state_carry_policy == "native_full_precision":
            if carried != checkpoint or interval != (checkpoint, checkpoint):
                raise RollingFCRValidationError(
                    "native full-precision evidence must preserve the checkpoint exactly"
                )
            if self.rounding_applied:
                raise RollingFCRValidationError(
                    "native full-precision evidence cannot report rounding"
                )
        else:
            if not self.rounding_applied:
                raise RollingFCRValidationError(
                    "source-three-decimal evidence must report rounding"
                )
            if parsed_carried.as_tuple().exponent != -3:
                raise RollingFCRValidationError(
                    "source carried decimal evidence must retain three places"
                )
        if not isinstance(self.signed_zero_normalized, bool):
            raise RollingFCRValidationError(
                "signed_zero_normalized must be boolean"
            )
        object.__setattr__(self, "replay_checkpoint_kwh", checkpoint)
        object.__setattr__(self, "carried_stored_energy_kwh", carried)
        object.__setattr__(self, "decimal_input_text", decimal_input)
        object.__setattr__(self, "carried_decimal_text", carried_decimal)
        object.__setattr__(self, "source_interval_kwh", interval)
        object.__setattr__(self, "evidence_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "replay_checkpoint_kwh": self.replay_checkpoint_kwh,
            "carried_stored_energy_kwh": self.carried_stored_energy_kwh,
            "state_carry_policy": self.state_carry_policy,
            "decimal_input_text": self.decimal_input_text,
            "carried_decimal_text": self.carried_decimal_text,
            "source_interval_kwh": list(self.source_interval_kwh),
            "interval_closure": "closed",
            "rounding_mode": "ROUND_HALF_EVEN",
            "rounding_applied": self.rounding_applied,
            "signed_zero_normalized": self.signed_zero_normalized,
            "unit": "kWh",
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "evidence_fingerprint": self.evidence_fingerprint}


def derive_rolling_fcr_state_carry(
    replay_checkpoint_kwh: float,
    *,
    state_carry_policy: str,
) -> RollingFCRStateCarryEvidence:
    """Apply the declared midnight/08:00 carry policy from Decimal(str(x))."""

    checkpoint = _finite(
        replay_checkpoint_kwh,
        field_name="replay_checkpoint_kwh",
    )
    decimal_input = Decimal(str(checkpoint))
    if state_carry_policy == "native_full_precision":
        return RollingFCRStateCarryEvidence(
            replay_checkpoint_kwh=checkpoint,
            carried_stored_energy_kwh=checkpoint,
            state_carry_policy=state_carry_policy,
            decimal_input_text=str(decimal_input),
            carried_decimal_text=str(decimal_input),
            source_interval_kwh=(checkpoint, checkpoint),
            rounding_applied=False,
            signed_zero_normalized=False,
        )
    if state_carry_policy != "source_three_decimal":
        raise RollingFCRValidationError("unsupported state-carry policy")
    quantized = decimal_input.quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_EVEN,
    )
    signed_zero = quantized.is_zero() and quantized.is_signed()
    if quantized.is_zero():
        quantized = Decimal("0.000")
    carried = float(quantized)
    half_unit = Decimal("0.0005")
    lower = float(quantized - half_unit)
    upper = float(quantized + half_unit)
    return RollingFCRStateCarryEvidence(
        replay_checkpoint_kwh=checkpoint,
        carried_stored_energy_kwh=carried,
        state_carry_policy=state_carry_policy,
        decimal_input_text=str(decimal_input),
        carried_decimal_text=format(quantized, ".3f"),
        source_interval_kwh=(lower, upper),
        rounding_applied=True,
        signed_zero_normalized=signed_zero,
    )


@dataclass(frozen=True, slots=True)
class RollingFCRBatteryBinding:
    optimization_battery: RobustFCRBatteryParameters
    capacity_kwh: float
    component_name: str
    replay_timestep_seconds: int
    power_sign_mapping: str = "source-positive-discharge-to-public-charge-positive-negation-v1"
    efficiency_lineage: str = "identical-feature-013-feature-012-efficiencies-v1"
    semantics_version: str = ROLLING_FCR_BATTERY_BINDING_VERSION
    binding_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.optimization_battery, RobustFCRBatteryParameters):
            raise RollingFCRValidationError("optimization_battery has the wrong contract type")
        capacity = _positive(self.capacity_kwh, field_name="capacity_kwh")
        if capacity < self.optimization_battery.maximum_stored_energy_kwh:
            raise RollingFCRValidationError(
                "capacity_kwh must cover Feature 013 maximum stored energy"
            )
        if isinstance(self.replay_timestep_seconds, bool) or not isinstance(self.replay_timestep_seconds, int) or self.replay_timestep_seconds <= 0:
            raise RollingFCRValidationError("replay_timestep_seconds must be positive")
        if self.power_sign_mapping != "source-positive-discharge-to-public-charge-positive-negation-v1":
            raise RollingFCRValidationError("unsupported battery power-sign mapping")
        if self.efficiency_lineage != "identical-feature-013-feature-012-efficiencies-v1":
            raise RollingFCRValidationError("unsupported battery efficiency lineage")
        if self.semantics_version != ROLLING_FCR_BATTERY_BINDING_VERSION:
            raise RollingFCRValidationError("unsupported rolling battery binding version")
        object.__setattr__(self, "capacity_kwh", capacity)
        object.__setattr__(self, "component_name", _non_empty(self.component_name, field_name="component_name"))
        object.__setattr__(self, "binding_fingerprint", _fingerprint(self._payload()))

    @property
    def maximum_charge_power_kw(self) -> float:
        return self.optimization_battery.maximum_charge_power_kw

    @property
    def maximum_discharge_power_kw(self) -> float:
        return self.optimization_battery.maximum_discharge_power_kw

    @property
    def minimum_stored_energy_kwh(self) -> float:
        return self.optimization_battery.minimum_stored_energy_kwh

    @property
    def maximum_stored_energy_kwh(self) -> float:
        return self.optimization_battery.maximum_stored_energy_kwh

    @property
    def charge_efficiency(self) -> float:
        return self.optimization_battery.charge_efficiency

    @property
    def discharge_efficiency(self) -> float:
        return self.optimization_battery.discharge_efficiency

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "optimization_battery": self.optimization_battery.to_dict(),
            "capacity_kwh": self.capacity_kwh,
            "component_name": self.component_name,
            "replay_timestep_seconds": self.replay_timestep_seconds,
            "power_sign_mapping": self.power_sign_mapping,
            "efficiency_lineage": self.efficiency_lineage,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "binding_fingerprint": self.binding_fingerprint}


@dataclass(frozen=True, slots=True)
class RollingFCRExperimentProfile:
    profile_id: str
    source_script: str
    source_result_directory: str
    formulation_kind: str
    bidding_time_local_hour: int
    state_mode: str
    predecessor_fixing_rule: str
    finalization_rule: str
    allowed_state_carry_policies: tuple[str, ...]
    feasible_incumbent_rule: str
    plan_classification: str
    paper_experiment: int
    workbook_column: int
    crosswalk_reconciliation_status: str
    table_a1_parity_claim: bool
    source_refs: tuple[str, ...]
    semantics_version: str = ROLLING_FCR_PROFILE_VERSION
    profile_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.profile_id not in _PROFILE_IDS:
            raise RollingFCRValidationError("unsupported rolling experiment profile")
        if self.formulation_kind not in {"restriction", "relaxation", "arbitrage_only"}:
            raise RollingFCRValidationError("unsupported profile formulation kind")
        if self.state_mode not in {"reset", "midnight_carry", "rolling_0800"}:
            raise RollingFCRValidationError("unsupported profile state mode")
        if self.plan_classification not in {"robust_candidate", "diagnostic_non_robust", "arbitrage_only"}:
            raise RollingFCRValidationError("unsupported profile plan classification")
        if self.table_a1_parity_claim is not False:
            raise RollingFCRValidationError("Feature 015 profiles must not claim Table A1 parity")
        if self.semantics_version != ROLLING_FCR_PROFILE_VERSION:
            raise RollingFCRValidationError("unsupported rolling profile version")
        carry = _string_tuple(self.allowed_state_carry_policies, field_name="allowed_state_carry_policies")
        if not carry or any(item not in {"source_three_decimal", "native_full_precision"} for item in carry):
            raise RollingFCRValidationError("profile carries unsupported state policy")
        object.__setattr__(self, "allowed_state_carry_policies", carry)
        object.__setattr__(self, "source_refs", _string_tuple(self.source_refs, field_name="source_refs"))
        object.__setattr__(self, "profile_fingerprint", _fingerprint(self._payload()))

    @property
    def is_independent(self) -> bool:
        return self.state_mode == "reset"

    @property
    def requires_accepted_fixings(self) -> bool:
        return self.state_mode == "rolling_0800"

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "profile_id": self.profile_id,
            "source_script": self.source_script,
            "source_result_directory": self.source_result_directory,
            "formulation_kind": self.formulation_kind,
            "bidding_time_local_hour": self.bidding_time_local_hour,
            "state_mode": self.state_mode,
            "predecessor_fixing_rule": self.predecessor_fixing_rule,
            "finalization_rule": self.finalization_rule,
            "allowed_state_carry_policies": list(self.allowed_state_carry_policies),
            "feasible_incumbent_rule": self.feasible_incumbent_rule,
            "plan_classification": self.plan_classification,
            "crosswalk": {
                "paper_experiment": self.paper_experiment,
                "workbook_column": self.workbook_column,
                "reconciliation_status": self.crosswalk_reconciliation_status,
                "table_a1_parity_claim": self.table_a1_parity_claim,
            },
            "reference_revision": SOURCE_REFERENCE_REVISION,
            "source_refs": list(self.source_refs),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "profile_fingerprint": self.profile_fingerprint}


_PROFILE_DEFINITIONS: dict[str, dict[str, object]] = {
    "script-11-relaxation-reset-midnight-v1": {
        "source_script": "baselines/robust_storage_bidding/code/11.jl",
        "source_result_directory": "baselines/robust_storage_bidding/results/01",
        "formulation_kind": "relaxation",
        "bidding_time_local_hour": 0,
        "state_mode": "reset",
        "predecessor_fixing_rule": "none-independent-reset-v1",
        "finalization_rule": "same-day-original-v1",
        "allowed_state_carry_policies": ("source_three_decimal",),
        "feasible_incumbent_rule": "diagnostic-only-v1",
        "plan_classification": "diagnostic_non_robust",
        "paper_experiment": 1,
        "workbook_column": 11,
    },
    "script-12-restriction-reset-midnight-v1": {
        "source_script": "baselines/robust_storage_bidding/code/12.jl",
        "source_result_directory": "baselines/robust_storage_bidding/results/02",
        "formulation_kind": "restriction",
        "bidding_time_local_hour": 0,
        "state_mode": "reset",
        "predecessor_fixing_rule": "none-independent-reset-v1",
        "finalization_rule": "same-day-original-v1",
        "allowed_state_carry_policies": ("source_three_decimal",),
        "feasible_incumbent_rule": "feature-013-solve-policy-v1",
        "plan_classification": "robust_candidate",
        "paper_experiment": 2,
        "workbook_column": 12,
    },
    "script-13-arbitrage-only-midnight-v1": {
        "source_script": "baselines/robust_storage_bidding/code/13.jl",
        "source_result_directory": "baselines/robust_storage_bidding/results/03",
        "formulation_kind": "arbitrage_only",
        "bidding_time_local_hour": 0,
        "state_mode": "midnight_carry",
        "predecessor_fixing_rule": "realized-midnight-state-only-v1",
        "finalization_rule": "same-day-after-replay-v1",
        "allowed_state_carry_policies": ("source_three_decimal",),
        "feasible_incumbent_rule": "audited-arbitrage-incumbent-v1",
        "plan_classification": "arbitrage_only",
        "paper_experiment": 4,
        "workbook_column": 14,
    },
    "script-14-restriction-rolling-0800-v1": {
        "source_script": "baselines/robust_storage_bidding/code/14.jl",
        "source_result_directory": "baselines/robust_storage_bidding/results/04",
        "formulation_kind": "restriction",
        "bidding_time_local_hour": 8,
        "state_mode": "rolling_0800",
        "predecessor_fixing_rule": "accepted-hours-09-24-and-blocks-3-6-v1",
        "finalization_rule": "successor-0800-closes-predecessor-v1",
        "allowed_state_carry_policies": ("source_three_decimal",),
        "feasible_incumbent_rule": "feature-013-solve-policy-v1",
        "plan_classification": "robust_candidate",
        "paper_experiment": 5,
        "workbook_column": 15,
    },
    "script-15-restriction-rolling-midnight-v1": {
        "source_script": "baselines/robust_storage_bidding/code/15.jl",
        "source_result_directory": "baselines/robust_storage_bidding/results/05",
        "formulation_kind": "restriction",
        "bidding_time_local_hour": 0,
        "state_mode": "midnight_carry",
        "predecessor_fixing_rule": "realized-midnight-state-only-v1",
        "finalization_rule": "same-day-after-replay-v1",
        "allowed_state_carry_policies": ("source_three_decimal", "native_full_precision"),
        "feasible_incumbent_rule": "feature-013-solve-policy-v1",
        "plan_classification": "robust_candidate",
        "paper_experiment": 3,
        "workbook_column": 13,
    },
}


def build_rolling_fcr_experiment_profile(profile_id: str) -> RollingFCRExperimentProfile:
    """Return one authoritative executable-script profile and explicit crosswalk."""

    try:
        values = _PROFILE_DEFINITIONS[profile_id]
    except KeyError as exc:
        raise RollingFCRValidationError("unsupported rolling experiment profile") from exc
    script = str(values["source_script"])
    return RollingFCRExperimentProfile(
        profile_id=profile_id,
        **values,
        crosswalk_reconciliation_status="executable-crosswalk-known-metric-discrepancies-v1",
        table_a1_parity_claim=False,
        source_refs=(
            f"{script}:23-104",
            "baselines/robust_storage_bidding/code/04_parse_results.jl:4-100",
            "baselines/robust_storage_bidding/results/result_overview.xlsx",
        ),
    )


@dataclass(frozen=True, slots=True)
class CallerSuppliedRollingState:
    delivery_date: date
    stored_energy_kwh: float
    observation_cutoff_utc: datetime
    provenance: Mapping[str, object]
    source_fingerprint: str
    unit: str = "kWh"
    state_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.delivery_date, date) or isinstance(self.delivery_date, datetime):
            raise RollingFCRValidationError("caller state delivery_date must be a date")
        object.__setattr__(self, "stored_energy_kwh", _finite(self.stored_energy_kwh, field_name="stored_energy_kwh"))
        object.__setattr__(self, "observation_cutoff_utc", _utc(self.observation_cutoff_utc, field_name="observation_cutoff_utc"))
        object.__setattr__(self, "source_fingerprint", _sha(self.source_fingerprint, field_name="source_fingerprint"))
        if self.unit != "kWh":
            raise RollingFCRValidationError("caller-supplied state unit must be kWh")
        provenance = _freeze_mapping(self.provenance, field_name="provenance")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "state_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "delivery_date": self.delivery_date.isoformat(),
            "stored_energy_kwh": self.stored_energy_kwh,
            "observation_cutoff_utc": _utc_text(self.observation_cutoff_utc),
            "provenance": _thaw(self.provenance),
            "source_fingerprint": self.source_fingerprint,
            "unit": self.unit,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "state_fingerprint": self.state_fingerprint}


@dataclass(frozen=True, slots=True)
class RollingFCRStudyManifest:
    study_id: str
    profile: RollingFCRExperimentProfile
    dates: tuple[DeliveryDateClassification, ...]
    day_ahead_descriptor: RollingFCRDataDescriptor
    fcr_capacity_descriptor: RollingFCRDataDescriptor
    activation_descriptor: RollingFCRDataDescriptor
    battery_binding: RollingFCRBatteryBinding
    uncertainty_profile: RobustFCRUncertaintyProfile
    terminal_rule: TerminalStoredEnergyRule
    solve_policy: RobustFCRSolvePolicy
    settlement_profile: str
    acceptance_policy: AcceptedBidPolicy
    numeric_policy: RollingFCRNumericPolicy
    failure_policy: str
    aggregation_policy: str
    resume_policy: str
    caller_state_declarations: tuple[CallerSuppliedRollingState, ...] = ()
    reference_lineage: Mapping[str, object] | None = None
    semantics_version: str = ROLLING_FCR_STUDY_MANIFEST_VERSION
    manifest_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "study_id", _non_empty(self.study_id, field_name="study_id"))
        if self.semantics_version != ROLLING_FCR_STUDY_MANIFEST_VERSION:
            raise RollingFCRValidationError("unsupported rolling study manifest version")
        expected = (
            ("profile", self.profile, RollingFCRExperimentProfile),
            ("battery_binding", self.battery_binding, RollingFCRBatteryBinding),
            ("uncertainty_profile", self.uncertainty_profile, RobustFCRUncertaintyProfile),
            ("terminal_rule", self.terminal_rule, TerminalStoredEnergyRule),
            ("solve_policy", self.solve_policy, RobustFCRSolvePolicy),
            ("acceptance_policy", self.acceptance_policy, AcceptedBidPolicy),
            ("numeric_policy", self.numeric_policy, RollingFCRNumericPolicy),
        )
        for name, value, contract in expected:
            if not isinstance(value, contract):
                raise RollingFCRValidationError(f"{name} has the wrong contract type")
        descriptors = (
            (self.day_ahead_descriptor, "day_ahead_price"),
            (self.fcr_capacity_descriptor, "fcr_capacity_price"),
            (self.activation_descriptor, "regulation_activation"),
        )
        for descriptor, kind in descriptors:
            if not isinstance(descriptor, RollingFCRDataDescriptor) or descriptor.kind != kind:
                raise RollingFCRValidationError(f"manifest requires exactly one {kind} descriptor")
        dates = tuple(self.dates)
        if not dates or any(not isinstance(item, DeliveryDateClassification) for item in dates):
            raise RollingFCRValidationError("manifest dates must contain classifications")
        ordered = tuple(item.delivery_date for item in dates)
        if ordered != tuple(sorted(ordered)) or len(set(ordered)) != len(ordered):
            raise RollingFCRValidationError("manifest dates must be strictly ordered and unique")
        executed = tuple(item for item in dates if item.execution_role != "excluded")
        if not executed:
            raise RollingFCRValidationError("manifest must execute at least one date")
        if self.profile.state_mode == "rolling_0800":
            if dates[0].execution_role != "warm-up" or dates[-1].execution_role != "close-out":
                raise RollingFCRValidationError(
                    "08:00 profile requires explicit first warm-up and final close-out dates"
                )
            if self.numeric_policy.state_carry_policy != "source_three_decimal":
                raise RollingFCRValidationError("08:00 source profile requires three-decimal carry")
        if self.numeric_policy.state_carry_policy not in self.profile.allowed_state_carry_policies:
            raise RollingFCRValidationError("numeric state-carry policy is incompatible with profile")
        if self.numeric_policy.solve_policy_fingerprint != self.solve_policy.solve_policy_fingerprint:
            raise RollingFCRValidationError("numeric and solve policies do not reconcile")
        expected_failure = FAILURE_POLICY_INDEPENDENT if self.profile.is_independent else FAILURE_POLICY_COUPLED
        if self.failure_policy != expected_failure:
            raise RollingFCRValidationError("failure policy does not match profile coupling")
        if self.aggregation_policy != AGGREGATION_POLICY:
            raise RollingFCRValidationError("unsupported aggregation policy")
        if self.resume_policy != RESUME_POLICY:
            raise RollingFCRValidationError("unsupported resume policy")
        if self.profile.formulation_kind == "relaxation" and self.profile.plan_classification != "diagnostic_non_robust":
            raise RollingFCRValidationError("relaxation profile cannot be robustly deployable")
        first_start = datetime.combine(ordered[0], time.min, tzinfo=UTC) - timedelta(days=1)
        last_end = datetime.combine(ordered[-1], time.min, tzinfo=UTC) + timedelta(days=2)
        if any(
            item.coverage_start_utc > first_start
            or item.coverage_end_utc < last_end
            for item, _ in descriptors
        ):
            raise RollingFCRValidationError(
                "every data descriptor must cover the declared rolling date window"
            )
        caller_states = tuple(self.caller_state_declarations)
        if any(not isinstance(item, CallerSuppliedRollingState) for item in caller_states):
            raise RollingFCRValidationError("caller_state_declarations contain an invalid contract")
        caller_dates = tuple(item.delivery_date for item in caller_states)
        if len(set(caller_dates)) != len(caller_dates) or any(item not in ordered for item in caller_dates):
            raise RollingFCRValidationError("caller states must identify unique manifest dates")
        for item in caller_states:
            battery = self.battery_binding.optimization_battery
            if not (
                battery.minimum_stored_energy_kwh
                <= item.stored_energy_kwh
                <= battery.maximum_stored_energy_kwh
            ):
                raise RollingFCRValidationError(
                    "caller-supplied state lies outside the battery bounds"
                )
        lineage = _freeze_mapping(self.reference_lineage or {}, field_name="reference_lineage")
        if lineage and lineage.get("reference_revision") != SOURCE_REFERENCE_REVISION:
            raise RollingFCRValidationError("reference lineage revision does not match the pinned source")
        object.__setattr__(self, "dates", dates)
        object.__setattr__(self, "settlement_profile", _non_empty(self.settlement_profile, field_name="settlement_profile"))
        object.__setattr__(self, "caller_state_declarations", caller_states)
        object.__setattr__(self, "reference_lineage", lineage)
        object.__setattr__(self, "manifest_fingerprint", _fingerprint(self._payload()))

    @property
    def decision_cutoff_rule(self) -> str:
        return (
            "previous-delivery-day-0800-local-v1"
            if self.profile.state_mode == "rolling_0800"
            else "pre-delivery-midnight-local-v1"
        )

    @property
    def information_cutoff_rule(self) -> str:
        return self.decision_cutoff_rule

    def listed_predecessor_date(self, delivery_date: date) -> date | None:
        """Return the immediately preceding manifest date, not calendar day."""

        ordered = tuple(item.delivery_date for item in self.dates)
        try:
            index = ordered.index(delivery_date)
        except ValueError as exc:
            raise RollingFCRValidationError(
                "delivery date is outside the rolling-study manifest"
            ) from exc
        return None if index == 0 else ordered[index - 1]

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "study_id": self.study_id,
            "profile": self.profile.to_dict(),
            "dates": [item.to_dict() for item in self.dates],
            "data_descriptors": {
                "day_ahead": self.day_ahead_descriptor.to_dict(),
                "fcr_capacity": self.fcr_capacity_descriptor.to_dict(),
                "activation": self.activation_descriptor.to_dict(),
            },
            "battery_binding": self.battery_binding.to_dict(),
            "uncertainty_profile": self.uncertainty_profile.to_dict(),
            "terminal_rule": self.terminal_rule.to_dict(),
            "solve_policy": self.solve_policy.to_dict(),
            "settlement_profile": self.settlement_profile,
            "acceptance_policy": self.acceptance_policy.to_dict(),
            "numeric_policy": self.numeric_policy.to_dict(),
            "decision_cutoff_rule": self.decision_cutoff_rule,
            "information_cutoff_rule": self.information_cutoff_rule,
            "failure_policy": self.failure_policy,
            "aggregation_policy": self.aggregation_policy,
            "resume_policy": self.resume_policy,
            "caller_state_declarations": [item.to_dict() for item in self.caller_state_declarations],
            "reference_lineage": _thaw(self.reference_lineage),
            "reference_revision": SOURCE_REFERENCE_REVISION,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "manifest_fingerprint": self.manifest_fingerprint}


def build_rolling_fcr_study_manifest(**values: object) -> RollingFCRStudyManifest:
    """Validate and fingerprint one executable profile over ordered dates."""

    return RollingFCRStudyManifest(**values)


@dataclass(frozen=True, slots=True)
class RollingFCRDayInput:
    manifest_fingerprint: str
    profile_fingerprint: str
    date_classification: DeliveryDateClassification
    time_contract: RobustFCRTimeContract
    battery: RobustFCRBatteryParameters
    prices: RobustFCRPriceInputs
    decision_cutoff_utc: datetime
    information_cutoff_utc: datetime
    producer_input_fingerprints: Mapping[str, str]
    provenance: Mapping[str, object]
    predecessor_prices: RobustFCRPriceInputs | None = None
    accepted_fixings: object | None = None
    predecessor_cutoff_utc: datetime | None = None
    semantics_version: str = ROLLING_FCR_DAY_INPUT_VERSION
    day_input_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_fingerprint", _sha(self.manifest_fingerprint, field_name="manifest_fingerprint"))
        object.__setattr__(self, "profile_fingerprint", _sha(self.profile_fingerprint, field_name="profile_fingerprint"))
        expected = (
            ("date_classification", self.date_classification, DeliveryDateClassification),
            ("time_contract", self.time_contract, RobustFCRTimeContract),
            ("battery", self.battery, RobustFCRBatteryParameters),
            ("prices", self.prices, RobustFCRPriceInputs),
        )
        for name, value, contract in expected:
            if not isinstance(value, contract):
                raise RollingFCRValidationError(f"{name} has the wrong contract type")
        if self.time_contract.delivery_period.local_start.date() != self.date_classification.delivery_date:
            raise RollingFCRValidationError("day input time contract and delivery date differ")
        decision_cutoff = _utc(self.decision_cutoff_utc, field_name="decision_cutoff_utc")
        information_cutoff = _utc(self.information_cutoff_utc, field_name="information_cutoff_utc")
        if information_cutoff > decision_cutoff:
            raise RollingFCRValidationError("information cutoff cannot follow decision cutoff")
        if decision_cutoff > self.time_contract.delivery_period.start_utc:
            raise RollingFCRValidationError("decision cutoff cannot follow delivery start")
        if not isinstance(self.producer_input_fingerprints, Mapping):
            raise RollingFCRValidationError("producer_input_fingerprints must be a mapping")
        inputs: dict[str, str] = {}
        for key, value in self.producer_input_fingerprints.items():
            normalized = _non_empty(key, field_name="producer_input_fingerprints key")
            if any(term in normalized.casefold() for term in _BIDDER_FORBIDDEN_TERMS):
                raise RollingFCRValidationError(
                    f"producer_input_fingerprints.{normalized} violates the information cutoff"
                )
            inputs[normalized] = _sha(value, field_name=f"producer_input_fingerprints.{normalized}")
        provenance = _freeze_mapping(self.provenance, field_name="provenance")
        _validate_mapping_keys(
            provenance,
            field_name="provenance",
            forbidden_terms=_BIDDER_FORBIDDEN_TERMS,
        )
        if self.predecessor_prices is not None and not isinstance(self.predecessor_prices, RobustFCRPriceInputs):
            raise RollingFCRValidationError("predecessor_prices has the wrong contract type")
        predecessor_cutoff = None
        if self.predecessor_cutoff_utc is not None:
            predecessor_cutoff = _utc(self.predecessor_cutoff_utc, field_name="predecessor_cutoff_utc")
            if predecessor_cutoff > information_cutoff:
                raise RollingFCRValidationError("predecessor cutoff cannot follow information cutoff")
        object.__setattr__(self, "decision_cutoff_utc", decision_cutoff)
        object.__setattr__(self, "information_cutoff_utc", information_cutoff)
        object.__setattr__(self, "producer_input_fingerprints", MappingProxyType(dict(sorted(inputs.items()))))
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "predecessor_cutoff_utc", predecessor_cutoff)
        object.__setattr__(self, "day_input_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        fixings_payload = None
        if self.accepted_fixings is not None:
            fixings_payload = _contract_dict(self.accepted_fixings, field_name="accepted_fixings")
        return {
            "semantics_version": self.semantics_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "date_classification": self.date_classification.to_dict(),
            "time_contract": self.time_contract.to_dict(),
            "battery": self.battery.to_dict(),
            "prices": self.prices.to_dict(),
            "decision_cutoff_utc": _utc_text(self.decision_cutoff_utc),
            "information_cutoff_utc": _utc_text(self.information_cutoff_utc),
            "producer_input_fingerprints": dict(self.producer_input_fingerprints),
            "provenance": _thaw(self.provenance),
            "predecessor_prices": None if self.predecessor_prices is None else self.predecessor_prices.to_dict(),
            "accepted_fixings": fixings_payload,
            "predecessor_cutoff_utc": None if self.predecessor_cutoff_utc is None else _utc_text(self.predecessor_cutoff_utc),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "day_input_fingerprint": self.day_input_fingerprint}


@dataclass(frozen=True, slots=True)
class ContinuitySegment:
    segment_id: str
    start_date: date
    end_date: date
    start_reason: str
    source_state_fingerprint: str | None = None
    continuity_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "segment_id", _non_empty(self.segment_id, field_name="segment_id"))
        if not isinstance(self.start_date, date) or isinstance(self.start_date, datetime):
            raise RollingFCRValidationError("continuity start_date must be a date")
        if not isinstance(self.end_date, date) or isinstance(self.end_date, datetime):
            raise RollingFCRValidationError("continuity end_date must be a date")
        if self.end_date < self.start_date:
            raise RollingFCRValidationError("continuity segment dates are reversed")
        object.__setattr__(self, "start_reason", _non_empty(self.start_reason, field_name="start_reason"))
        if self.source_state_fingerprint is not None:
            object.__setattr__(self, "source_state_fingerprint", _sha(self.source_state_fingerprint, field_name="source_state_fingerprint"))
        object.__setattr__(self, "continuity_fingerprint", _fingerprint(self.to_dict(include_fingerprint=False)))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        payload = {
            "segment_id": self.segment_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "start_reason": self.start_reason,
            "source_state_fingerprint": self.source_state_fingerprint,
        }
        return {**payload, **({"continuity_fingerprint": self.continuity_fingerprint} if include_fingerprint else {})}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ContinuitySegment:
        data = _strict_mapping(
            payload,
            field_name="continuity segment",
            required_keys=frozenset(
                {
                    "segment_id",
                    "start_date",
                    "end_date",
                    "start_reason",
                    "source_state_fingerprint",
                    "continuity_fingerprint",
                }
            ),
        )
        result = cls(
            segment_id=data["segment_id"],  # type: ignore[arg-type]
            start_date=_date_from_text(data["start_date"], field_name="segment.start_date"),
            end_date=_date_from_text(data["end_date"], field_name="segment.end_date"),
            start_reason=data["start_reason"],  # type: ignore[arg-type]
            source_state_fingerprint=data["source_state_fingerprint"],  # type: ignore[arg-type]
        )
        _verify_persisted_fingerprint(
            field_name="continuity_fingerprint",
            provided=data["continuity_fingerprint"],
            recomputed=result.continuity_fingerprint,
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRStateLink:
    predecessor_date: date
    successor_date: date
    handoff_kind: str
    observation_cutoff_utc: datetime
    replay_checkpoint_kwh: float
    carried_stored_energy_kwh: float
    rounding_policy: str
    source_interval_kwh: tuple[float, float]
    predecessor_plan_fingerprint: str | None
    replay_fingerprint: str | None
    activation_fingerprint: str | None
    continuity_segment_id: str
    reconciles: bool
    accepted_fixings_fingerprint: str | None = None
    successor_problem_fingerprint: str | None = None
    causal_prefix_fingerprint: str | None = None
    rounding_evidence_fingerprint: str | None = None
    successor_initial_stored_energy_kwh: float | None = None
    modeled_terminal_stored_energy_kwh: float | None = None
    reconciliation_tolerance_kwh: float = 1e-7
    unit: str = "kWh"
    state_link_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.predecessor_date, date) or isinstance(
            self.predecessor_date, datetime
        ):
            raise RollingFCRValidationError("state-link predecessor_date must be a date")
        if not isinstance(self.successor_date, date) or isinstance(
            self.successor_date, datetime
        ):
            raise RollingFCRValidationError("state-link successor_date must be a date")
        if self.handoff_kind not in {"midnight", "cutoff_0800", "caller_supplied"}:
            raise RollingFCRValidationError("unsupported state-link handoff kind")
        if self.successor_date <= self.predecessor_date and self.handoff_kind != "caller_supplied":
            raise RollingFCRValidationError("state-link successor must follow predecessor")
        object.__setattr__(self, "observation_cutoff_utc", _utc(self.observation_cutoff_utc, field_name="observation_cutoff_utc"))
        object.__setattr__(self, "replay_checkpoint_kwh", _finite(self.replay_checkpoint_kwh, field_name="replay_checkpoint_kwh"))
        object.__setattr__(self, "carried_stored_energy_kwh", _finite(self.carried_stored_energy_kwh, field_name="carried_stored_energy_kwh"))
        interval = tuple(_finite(value, field_name="source_interval_kwh") for value in self.source_interval_kwh)
        if (
            len(interval) != 2
            or interval[0] > interval[1]
            or interval[0] > self.carried_stored_energy_kwh
            or interval[1] < self.carried_stored_energy_kwh
            or interval[0] > self.replay_checkpoint_kwh
            or interval[1] < self.replay_checkpoint_kwh
        ):
            raise RollingFCRValidationError(
                "closed source interval must contain replay and carried states"
            )
        object.__setattr__(self, "source_interval_kwh", interval)
        for name in (
            "predecessor_plan_fingerprint",
            "replay_fingerprint",
            "activation_fingerprint",
            "accepted_fixings_fingerprint",
            "successor_problem_fingerprint",
            "causal_prefix_fingerprint",
            "rounding_evidence_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _sha(value, field_name=name))
        successor_initial = (
            self.carried_stored_energy_kwh
            if self.successor_initial_stored_energy_kwh is None
            else _finite(
                self.successor_initial_stored_energy_kwh,
                field_name="successor_initial_stored_energy_kwh",
            )
        )
        object.__setattr__(
            self,
            "successor_initial_stored_energy_kwh",
            successor_initial,
        )
        if self.modeled_terminal_stored_energy_kwh is not None:
            object.__setattr__(
                self,
                "modeled_terminal_stored_energy_kwh",
                _finite(
                    self.modeled_terminal_stored_energy_kwh,
                    field_name="modeled_terminal_stored_energy_kwh",
                ),
            )
        tolerance = _positive(
            self.reconciliation_tolerance_kwh,
            field_name="reconciliation_tolerance_kwh",
        )
        object.__setattr__(self, "reconciliation_tolerance_kwh", tolerance)
        if self.unit != "kWh":
            raise RollingFCRValidationError("rolling state links require kWh units")
        if not isinstance(self.reconciles, bool):
            raise RollingFCRValidationError("state-link reconciles must be boolean")
        expected_reconciliation = (
            abs(successor_initial - self.carried_stored_energy_kwh) <= tolerance
        )
        if self.reconciles is not expected_reconciliation:
            raise RollingFCRValidationError(
                "state-link reconciliation flag disagrees with successor initial state"
            )
        object.__setattr__(self, "continuity_segment_id", _non_empty(self.continuity_segment_id, field_name="continuity_segment_id"))
        object.__setattr__(self, "state_link_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "predecessor_date": self.predecessor_date.isoformat(),
            "successor_date": self.successor_date.isoformat(),
            "handoff_kind": self.handoff_kind,
            "observation_cutoff_utc": _utc_text(self.observation_cutoff_utc),
            "replay_checkpoint_kwh": self.replay_checkpoint_kwh,
            "carried_stored_energy_kwh": self.carried_stored_energy_kwh,
            "rounding_policy": self.rounding_policy,
            "source_interval_kwh": list(self.source_interval_kwh),
            "predecessor_plan_fingerprint": self.predecessor_plan_fingerprint,
            "replay_fingerprint": self.replay_fingerprint,
            "activation_fingerprint": self.activation_fingerprint,
            "continuity_segment_id": self.continuity_segment_id,
            "reconciles": self.reconciles,
            "accepted_fixings_fingerprint": self.accepted_fixings_fingerprint,
            "successor_problem_fingerprint": self.successor_problem_fingerprint,
            "causal_prefix_fingerprint": self.causal_prefix_fingerprint,
            "rounding_evidence_fingerprint": self.rounding_evidence_fingerprint,
            "successor_initial_stored_energy_kwh": self.successor_initial_stored_energy_kwh,
            "modeled_terminal_stored_energy_kwh": self.modeled_terminal_stored_energy_kwh,
            "reconciliation_tolerance_kwh": self.reconciliation_tolerance_kwh,
            "unit": self.unit,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "state_link_fingerprint": self.state_link_fingerprint}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RollingFCRStateLink:
        required = frozenset(
            {
                "predecessor_date",
                "successor_date",
                "handoff_kind",
                "observation_cutoff_utc",
                "replay_checkpoint_kwh",
                "carried_stored_energy_kwh",
                "rounding_policy",
                "source_interval_kwh",
                "predecessor_plan_fingerprint",
                "replay_fingerprint",
                "activation_fingerprint",
                "continuity_segment_id",
                "reconciles",
                "accepted_fixings_fingerprint",
                "successor_problem_fingerprint",
                "causal_prefix_fingerprint",
                "rounding_evidence_fingerprint",
                "successor_initial_stored_energy_kwh",
                "modeled_terminal_stored_energy_kwh",
                "reconciliation_tolerance_kwh",
                "unit",
                "state_link_fingerprint",
            }
        )
        data = _strict_mapping(
            payload,
            field_name="state link",
            required_keys=required,
        )
        interval = data["source_interval_kwh"]
        if not isinstance(interval, Sequence) or isinstance(interval, (str, bytes)):
            raise RollingFCRValidationError("source_interval_kwh must be a sequence")
        result = cls(
            predecessor_date=_date_from_text(
                data["predecessor_date"], field_name="state_link.predecessor_date"
            ),
            successor_date=_date_from_text(
                data["successor_date"], field_name="state_link.successor_date"
            ),
            handoff_kind=data["handoff_kind"],  # type: ignore[arg-type]
            observation_cutoff_utc=_utc_from_text(
                data["observation_cutoff_utc"],
                field_name="state_link.observation_cutoff_utc",
            ),
            replay_checkpoint_kwh=data["replay_checkpoint_kwh"],  # type: ignore[arg-type]
            carried_stored_energy_kwh=data["carried_stored_energy_kwh"],  # type: ignore[arg-type]
            rounding_policy=data["rounding_policy"],  # type: ignore[arg-type]
            source_interval_kwh=tuple(interval),  # type: ignore[arg-type]
            predecessor_plan_fingerprint=data["predecessor_plan_fingerprint"],  # type: ignore[arg-type]
            replay_fingerprint=data["replay_fingerprint"],  # type: ignore[arg-type]
            activation_fingerprint=data["activation_fingerprint"],  # type: ignore[arg-type]
            continuity_segment_id=data["continuity_segment_id"],  # type: ignore[arg-type]
            reconciles=data["reconciles"],  # type: ignore[arg-type]
            accepted_fixings_fingerprint=data["accepted_fixings_fingerprint"],  # type: ignore[arg-type]
            successor_problem_fingerprint=data["successor_problem_fingerprint"],  # type: ignore[arg-type]
            causal_prefix_fingerprint=data["causal_prefix_fingerprint"],  # type: ignore[arg-type]
            rounding_evidence_fingerprint=data["rounding_evidence_fingerprint"],  # type: ignore[arg-type]
            successor_initial_stored_energy_kwh=data[
                "successor_initial_stored_energy_kwh"
            ],  # type: ignore[arg-type]
            modeled_terminal_stored_energy_kwh=data[
                "modeled_terminal_stored_energy_kwh"
            ],  # type: ignore[arg-type]
            reconciliation_tolerance_kwh=data["reconciliation_tolerance_kwh"],  # type: ignore[arg-type]
            unit=data["unit"],  # type: ignore[arg-type]
        )
        _verify_persisted_fingerprint(
            field_name="state_link_fingerprint",
            provided=data["state_link_fingerprint"],
            recomputed=result.state_link_fingerprint,
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRDayRevision:
    revision_number: int
    revision_kind: str
    lifecycle_status: str
    creation_cause: str
    input_fingerprint: str | None
    problem_fingerprint: str | None
    solve_result_fingerprint: str | None
    plan_fingerprint: str | None
    plan_classification: str | None
    solve_status: str | None
    termination_status: str | None
    objective_value_eur: float | None
    best_upper_bound_eur: float | None
    absolute_gap_eur: float | None
    relative_gap: float | None
    feasibility_audit_fingerprint: str | None
    feasibility_slacks: Mapping[str, float]
    energy_decisions_charge_positive_kw: tuple[float, ...] | None
    fcr_capacity_kw: tuple[float, ...] | None
    independent_residuals: Mapping[str, float] = field(default_factory=dict)
    activation_fingerprint: str | None = None
    replay_fingerprint: str | None = None
    settlement_fingerprint: str | None = None
    state_link_fingerprint: str | None = None
    predecessor_revision_fingerprint: str | None = None
    finalizer_problem_fingerprint: str | None = None
    finalizer_result_fingerprint: str | None = None
    initial_stored_energy_kwh: float | None = None
    realized_cutoff_stored_energy_kwh: float | None = None
    handed_off_cutoff_stored_energy_kwh: float | None = None
    modeled_terminal_stored_energy_kwh: float | None = None
    realized_terminal_stored_energy_kwh: float | None = None
    carried_stored_energy_kwh: float | None = None
    realized_metrics: Mapping[str, float] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()
    runtime_metadata: Mapping[str, object] = field(default_factory=dict)
    revision_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.revision_number, bool) or not isinstance(self.revision_number, int) or self.revision_number < 0:
            raise RollingFCRValidationError("revision_number must be non-negative")
        if self.revision_kind not in _REVISION_KINDS:
            raise RollingFCRValidationError("unsupported revision kind")
        if self.lifecycle_status not in _LIFECYCLE_STATUSES:
            raise RollingFCRValidationError("unsupported lifecycle status")
        if self.lifecycle_status == "original":
            raise RollingFCRValidationError(
                "original is a revision kind, not a terminal lifecycle status"
            )
        if self.revision_kind == "finalized" and self.lifecycle_status not in {
            "finalized",
            "initialization_only",
        }:
            raise RollingFCRValidationError(
                "a finalized revision requires finalized or initialization_only lifecycle"
            )
        if self.revision_kind == "provisional" and self.lifecycle_status not in {
            "provisional",
            "unfinalized",
        }:
            raise RollingFCRValidationError(
                "a provisional revision requires provisional or unfinalized lifecycle"
            )
        if self.revision_kind == "optimization_only" and self.lifecycle_status not in {
            "optimization_only",
            "unfinalized",
        }:
            raise RollingFCRValidationError(
                "an optimization_only revision has an incompatible lifecycle"
            )
        object.__setattr__(self, "creation_cause", _non_empty(self.creation_cause, field_name="creation_cause"))
        for name in (
            "input_fingerprint",
            "problem_fingerprint",
            "solve_result_fingerprint",
            "plan_fingerprint",
            "feasibility_audit_fingerprint",
            "activation_fingerprint",
            "replay_fingerprint",
            "settlement_fingerprint",
            "state_link_fingerprint",
            "predecessor_revision_fingerprint",
            "finalizer_problem_fingerprint",
            "finalizer_result_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _sha(value, field_name=name))
        if self.termination_status is not None:
            object.__setattr__(
                self,
                "termination_status",
                _non_empty(self.termination_status, field_name="termination_status"),
            )
        if self.solve_status is not None:
            object.__setattr__(
                self,
                "solve_status",
                _non_empty(self.solve_status, field_name="solve_status"),
            )
        if self.plan_classification is not None:
            object.__setattr__(
                self,
                "plan_classification",
                _non_empty(
                    self.plan_classification, field_name="plan_classification"
                ),
            )
        for name in (
            "objective_value_eur",
            "best_upper_bound_eur",
            "absolute_gap_eur",
            "relative_gap",
        ):
            value = getattr(self, name)
            if value is not None:
                normalized = _finite(value, field_name=name)
                if name in {"absolute_gap_eur", "relative_gap"} and normalized < 0.0:
                    raise RollingFCRValidationError(f"{name} must be non-negative")
                object.__setattr__(self, name, normalized)
        if (self.absolute_gap_eur is None) is not (self.relative_gap is None):
            raise RollingFCRValidationError(
                "absolute and relative solve gaps must be available together"
            )
        if self.absolute_gap_eur is not None and (
            self.objective_value_eur is None or self.best_upper_bound_eur is None
        ):
            raise RollingFCRValidationError(
                "solve gaps require both objective and upper-bound evidence"
            )
        if self.objective_value_eur is not None and self.best_upper_bound_eur is not None:
            expected_gap = max(
                0.0,
                self.best_upper_bound_eur - self.objective_value_eur,
            )
            tolerance = max(1e-8, abs(expected_gap) * 1e-9)
            if self.absolute_gap_eur is None or abs(self.absolute_gap_eur - expected_gap) > tolerance:
                raise RollingFCRValidationError(
                    "absolute gap does not reconcile objective and upper bound"
                )
            expected_relative = expected_gap / max(
                abs(self.objective_value_eur),
                abs(self.best_upper_bound_eur),
                1.0,
            )
            if self.relative_gap is None or abs(self.relative_gap - expected_relative) > max(
                1e-8, abs(expected_relative) * 1e-9
            ):
                raise RollingFCRValidationError(
                    "relative gap does not reconcile objective and upper bound"
                )
        slacks: dict[str, float] = {}
        for name, value in self.feasibility_slacks.items():
            normalized_name = _non_empty(name, field_name="feasibility slack name")
            normalized = _finite(value, field_name=f"feasibility_slacks.{name}")
            if normalized < 0.0:
                raise RollingFCRValidationError("feasibility slacks must be non-negative")
            slacks[normalized_name] = normalized
        object.__setattr__(self, "feasibility_slacks", MappingProxyType(dict(sorted(slacks.items()))))
        residuals: dict[str, float] = {}
        for name, value in self.independent_residuals.items():
            normalized_name = _non_empty(
                name, field_name="independent residual name"
            )
            normalized = _finite(
                value, field_name=f"independent_residuals.{name}"
            )
            if normalized < 0.0:
                raise RollingFCRValidationError(
                    "independent residuals must be non-negative"
                )
            residuals[normalized_name] = normalized
        object.__setattr__(
            self,
            "independent_residuals",
            MappingProxyType(dict(sorted(residuals.items()))),
        )
        if self.energy_decisions_charge_positive_kw is not None:
            energy = tuple(_finite(value, field_name="energy decision") for value in self.energy_decisions_charge_positive_kw)
            if len(energy) != 24:
                raise RollingFCRValidationError("an incumbent revision must carry 24 energy decisions")
            object.__setattr__(self, "energy_decisions_charge_positive_kw", energy)
        if self.fcr_capacity_kw is not None:
            fcr = tuple(_finite(value, field_name="FCR decision") for value in self.fcr_capacity_kw)
            if len(fcr) != 6:
                raise RollingFCRValidationError("an incumbent revision must carry six FCR decisions")
            object.__setattr__(self, "fcr_capacity_kw", fcr)
        if (self.energy_decisions_charge_positive_kw is None) is not (
            self.fcr_capacity_kw is None
        ):
            raise RollingFCRValidationError(
                "energy and FCR decisions must be available together"
            )
        if self.solve_status is None and any(
            value is not None
            for value in (
                self.objective_value_eur,
                self.best_upper_bound_eur,
                self.energy_decisions_charge_positive_kw,
            )
        ):
            raise RollingFCRValidationError(
                "solve evidence cannot exist without solve_status"
            )
        for name in (
            "initial_stored_energy_kwh",
            "realized_cutoff_stored_energy_kwh",
            "handed_off_cutoff_stored_energy_kwh",
            "modeled_terminal_stored_energy_kwh",
            "realized_terminal_stored_energy_kwh",
            "carried_stored_energy_kwh",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite(value, field_name=name))
        realized_metrics: dict[str, float] = {}
        for name, value in self.realized_metrics.items():
            normalized_name = _non_empty(name, field_name="realized metric name")
            realized_metrics[normalized_name] = _finite(
                value,
                field_name=f"realized_metrics.{normalized_name}",
            )
        object.__setattr__(
            self,
            "realized_metrics",
            MappingProxyType(dict(sorted(realized_metrics.items()))),
        )
        object.__setattr__(self, "diagnostics", tuple(sorted(_string_tuple(self.diagnostics, field_name="diagnostics"))))
        object.__setattr__(self, "runtime_metadata", _freeze_mapping(self.runtime_metadata, field_name="runtime_metadata"))
        object.__setattr__(self, "revision_fingerprint", _fingerprint(self._semantic_payload()))

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "revision_number": self.revision_number,
            "revision_kind": self.revision_kind,
            "lifecycle_status": self.lifecycle_status,
            "creation_cause": self.creation_cause,
            "input_fingerprint": self.input_fingerprint,
            "problem_fingerprint": self.problem_fingerprint,
            "solve_result_fingerprint": self.solve_result_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
            "plan_classification": self.plan_classification,
            "solve_status": self.solve_status,
            "termination_status": self.termination_status,
            "objective_value_eur": self.objective_value_eur,
            "best_upper_bound_eur": self.best_upper_bound_eur,
            "absolute_gap_eur": self.absolute_gap_eur,
            "relative_gap": self.relative_gap,
            "feasibility_audit_fingerprint": self.feasibility_audit_fingerprint,
            "feasibility_slacks": dict(self.feasibility_slacks),
            "independent_residuals": dict(self.independent_residuals),
            "energy_decisions_charge_positive_kw": None if self.energy_decisions_charge_positive_kw is None else list(self.energy_decisions_charge_positive_kw),
            "fcr_capacity_kw": None if self.fcr_capacity_kw is None else list(self.fcr_capacity_kw),
            "activation_fingerprint": self.activation_fingerprint,
            "replay_fingerprint": self.replay_fingerprint,
            "settlement_fingerprint": self.settlement_fingerprint,
            "state_link_fingerprint": self.state_link_fingerprint,
            "predecessor_revision_fingerprint": self.predecessor_revision_fingerprint,
            "finalizer_problem_fingerprint": self.finalizer_problem_fingerprint,
            "finalizer_result_fingerprint": self.finalizer_result_fingerprint,
            "stored_energy_kwh": {
                "initial": self.initial_stored_energy_kwh,
                "realized_cutoff": self.realized_cutoff_stored_energy_kwh,
                "handed_off_cutoff": self.handed_off_cutoff_stored_energy_kwh,
                "modeled_terminal": self.modeled_terminal_stored_energy_kwh,
                "realized_terminal": self.realized_terminal_stored_energy_kwh,
                "carried": self.carried_stored_energy_kwh,
                "unit": "kWh",
            },
            "realized_metrics": dict(self.realized_metrics),
            "diagnostics": list(self.diagnostics),
            "stable_runtime_evidence": _semantic_runtime_metadata(
                self.runtime_metadata
            ),
        }

    def _fingerprint_evidence(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for name in (
            "input_fingerprint",
            "problem_fingerprint",
            "solve_result_fingerprint",
            "plan_fingerprint",
            "activation_fingerprint",
            "replay_fingerprint",
            "settlement_fingerprint",
            "state_link_fingerprint",
            "predecessor_revision_fingerprint",
            "finalizer_problem_fingerprint",
            "finalizer_result_fingerprint",
            "feasibility_audit_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                values[name] = value
                continue
            evidence_name = name.removesuffix("_fingerprint")
            values[name] = {
                "status": "unavailable",
                "reason_codes": [
                    f"{evidence_name}_unavailable_for_{self.lifecycle_status}"
                ],
            }
        return values

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "fingerprint_evidence": self._fingerprint_evidence(),
            "runtime_metadata": _thaw(self.runtime_metadata),
            "revision_fingerprint": self.revision_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RollingFCRDayRevision:
        semantic_keys = frozenset(
            {
                "revision_number",
                "revision_kind",
                "lifecycle_status",
                "creation_cause",
                "input_fingerprint",
                "problem_fingerprint",
                "solve_result_fingerprint",
                "plan_fingerprint",
                "plan_classification",
                "solve_status",
                "termination_status",
                "objective_value_eur",
                "best_upper_bound_eur",
                "absolute_gap_eur",
                "relative_gap",
                "feasibility_audit_fingerprint",
                "feasibility_slacks",
                "independent_residuals",
                "energy_decisions_charge_positive_kw",
                "fcr_capacity_kw",
                "activation_fingerprint",
                "replay_fingerprint",
                "settlement_fingerprint",
                "state_link_fingerprint",
                "predecessor_revision_fingerprint",
                "finalizer_problem_fingerprint",
                "finalizer_result_fingerprint",
                "stored_energy_kwh",
                "realized_metrics",
                "diagnostics",
                "stable_runtime_evidence",
            }
        )
        data = _strict_mapping(
            payload,
            field_name="day revision",
            required_keys=semantic_keys
            | frozenset(
                {
                    "fingerprint_evidence",
                    "runtime_metadata",
                    "revision_fingerprint",
                }
            ),
        )
        stored = _strict_mapping(
            data["stored_energy_kwh"],
            field_name="stored_energy_kwh",
            required_keys=frozenset(
                {
                    "initial",
                    "realized_cutoff",
                    "handed_off_cutoff",
                    "modeled_terminal",
                    "realized_terminal",
                    "carried",
                    "unit",
                }
            ),
        )
        if stored["unit"] != "kWh":
            raise RollingFCRValidationError("stored energy unit must be kWh")
        diagnostics = data["diagnostics"]
        energy = data["energy_decisions_charge_positive_kw"]
        fcr = data["fcr_capacity_kw"]
        for name, values in (
            ("diagnostics", diagnostics),
            ("energy_decisions_charge_positive_kw", energy),
            ("fcr_capacity_kw", fcr),
        ):
            if values is not None and (
                not isinstance(values, Sequence) or isinstance(values, (str, bytes))
            ):
                raise RollingFCRValidationError(f"{name} must be a sequence or null")
        result = cls(
            revision_number=data["revision_number"],  # type: ignore[arg-type]
            revision_kind=data["revision_kind"],  # type: ignore[arg-type]
            lifecycle_status=data["lifecycle_status"],  # type: ignore[arg-type]
            creation_cause=data["creation_cause"],  # type: ignore[arg-type]
            input_fingerprint=data["input_fingerprint"],  # type: ignore[arg-type]
            problem_fingerprint=data["problem_fingerprint"],  # type: ignore[arg-type]
            solve_result_fingerprint=data["solve_result_fingerprint"],  # type: ignore[arg-type]
            plan_fingerprint=data["plan_fingerprint"],  # type: ignore[arg-type]
            plan_classification=data["plan_classification"],  # type: ignore[arg-type]
            solve_status=data["solve_status"],  # type: ignore[arg-type]
            termination_status=data["termination_status"],  # type: ignore[arg-type]
            objective_value_eur=data["objective_value_eur"],  # type: ignore[arg-type]
            best_upper_bound_eur=data["best_upper_bound_eur"],  # type: ignore[arg-type]
            absolute_gap_eur=data["absolute_gap_eur"],  # type: ignore[arg-type]
            relative_gap=data["relative_gap"],  # type: ignore[arg-type]
            feasibility_audit_fingerprint=data["feasibility_audit_fingerprint"],  # type: ignore[arg-type]
            feasibility_slacks=data["feasibility_slacks"],  # type: ignore[arg-type]
            independent_residuals=data["independent_residuals"],  # type: ignore[arg-type]
            energy_decisions_charge_positive_kw=(
                None if energy is None else tuple(energy)
            ),  # type: ignore[arg-type]
            fcr_capacity_kw=None if fcr is None else tuple(fcr),  # type: ignore[arg-type]
            activation_fingerprint=data["activation_fingerprint"],  # type: ignore[arg-type]
            replay_fingerprint=data["replay_fingerprint"],  # type: ignore[arg-type]
            settlement_fingerprint=data["settlement_fingerprint"],  # type: ignore[arg-type]
            state_link_fingerprint=data["state_link_fingerprint"],  # type: ignore[arg-type]
            predecessor_revision_fingerprint=data[
                "predecessor_revision_fingerprint"
            ],  # type: ignore[arg-type]
            finalizer_problem_fingerprint=data["finalizer_problem_fingerprint"],  # type: ignore[arg-type]
            finalizer_result_fingerprint=data["finalizer_result_fingerprint"],  # type: ignore[arg-type]
            initial_stored_energy_kwh=stored["initial"],  # type: ignore[arg-type]
            realized_cutoff_stored_energy_kwh=stored["realized_cutoff"],  # type: ignore[arg-type]
            handed_off_cutoff_stored_energy_kwh=stored["handed_off_cutoff"],  # type: ignore[arg-type]
            modeled_terminal_stored_energy_kwh=stored["modeled_terminal"],  # type: ignore[arg-type]
            realized_terminal_stored_energy_kwh=stored["realized_terminal"],  # type: ignore[arg-type]
            carried_stored_energy_kwh=stored["carried"],  # type: ignore[arg-type]
            realized_metrics=data["realized_metrics"],  # type: ignore[arg-type]
            diagnostics=tuple(diagnostics),  # type: ignore[arg-type]
            runtime_metadata=data["runtime_metadata"],  # type: ignore[arg-type]
        )
        if data["stable_runtime_evidence"] != _semantic_runtime_metadata(
            result.runtime_metadata
        ):
            raise RollingFCRValidationError(
                "stable_runtime_evidence does not match runtime metadata"
            )
        _verify_persisted_fingerprint(
            field_name="revision_fingerprint",
            provided=data["revision_fingerprint"],
            recomputed=result.revision_fingerprint,
        )
        expected_evidence = result._fingerprint_evidence()
        if data["fingerprint_evidence"] != expected_evidence:
            raise RollingFCRValidationError(
                "fingerprint_evidence does not match revision availability"
            )
        return result


@dataclass(frozen=True, slots=True)
class DeliveryDateRecordEnvelope:
    manifest_fingerprint: str
    profile_fingerprint: str
    profile_id: str
    classification: DeliveryDateClassification
    predecessor_date: date | None
    continuity_segment_id: str
    revisions: tuple[RollingFCRDayRevision, ...]
    decision_cutoff_utc: datetime | None = None
    information_cutoff_utc: datetime | None = None
    envelope_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_fingerprint", _sha(self.manifest_fingerprint, field_name="manifest_fingerprint"))
        object.__setattr__(self, "profile_fingerprint", _sha(self.profile_fingerprint, field_name="profile_fingerprint"))
        if self.profile_id not in _PROFILE_IDS:
            raise RollingFCRValidationError("envelope profile_id is unsupported")
        if not isinstance(self.classification, DeliveryDateClassification):
            raise RollingFCRValidationError("envelope classification has the wrong type")
        if self.predecessor_date is not None and (
            not isinstance(self.predecessor_date, date)
            or isinstance(self.predecessor_date, datetime)
        ):
            raise RollingFCRValidationError("envelope predecessor_date must be a date")
        for name in ("decision_cutoff_utc", "information_cutoff_utc"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _utc(value, field_name=name))
        if (
            self.decision_cutoff_utc is not None
            and self.information_cutoff_utc is not None
            and self.information_cutoff_utc > self.decision_cutoff_utc
        ):
            raise RollingFCRValidationError(
                "envelope information cutoff cannot follow decision cutoff"
            )
        object.__setattr__(self, "continuity_segment_id", _non_empty(self.continuity_segment_id, field_name="continuity_segment_id"))
        revisions = tuple(self.revisions)
        if not revisions or any(not isinstance(item, RollingFCRDayRevision) for item in revisions):
            raise RollingFCRValidationError("envelope must retain immutable revisions")
        if tuple(item.revision_number for item in revisions) != tuple(range(len(revisions))):
            raise RollingFCRValidationError("revision numbers must be contiguous and monotonic")
        for previous, current in zip(revisions, revisions[1:]):
            if current.predecessor_revision_fingerprint != previous.revision_fingerprint:
                raise RollingFCRValidationError(
                    "revision lineage must reference the immediately preceding revision"
                )
        object.__setattr__(self, "revisions", revisions)
        object.__setattr__(
            self,
            "envelope_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    @property
    def latest_revision(self) -> RollingFCRDayRevision:
        return self.revisions[-1]

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "profile_id": self.profile_id,
            "classification": self.classification.to_dict(),
            "predecessor_date": None if self.predecessor_date is None else self.predecessor_date.isoformat(),
            "decision_cutoff_utc": (
                None
                if self.decision_cutoff_utc is None
                else _utc_text(self.decision_cutoff_utc)
            ),
            "information_cutoff_utc": (
                None
                if self.information_cutoff_utc is None
                else _utc_text(self.information_cutoff_utc)
            ),
            "continuity_segment_id": self.continuity_segment_id,
            "revisions": [
                {
                    **item._semantic_payload(),
                    "revision_fingerprint": item.revision_fingerprint,
                }
                for item in self.revisions
            ],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "profile_id": self.profile_id,
            "classification": self.classification.to_dict(),
            "predecessor_date": (
                None
                if self.predecessor_date is None
                else self.predecessor_date.isoformat()
            ),
            "decision_cutoff_utc": (
                None
                if self.decision_cutoff_utc is None
                else _utc_text(self.decision_cutoff_utc)
            ),
            "information_cutoff_utc": (
                None
                if self.information_cutoff_utc is None
                else _utc_text(self.information_cutoff_utc)
            ),
            "continuity_segment_id": self.continuity_segment_id,
            "revisions": [item.to_dict() for item in self.revisions],
            "envelope_fingerprint": self.envelope_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DeliveryDateRecordEnvelope:
        data = _strict_mapping(
            payload,
            field_name="date envelope",
            required_keys=frozenset(
                {
                    "manifest_fingerprint",
                    "profile_fingerprint",
                    "profile_id",
                    "classification",
                    "predecessor_date",
                    "decision_cutoff_utc",
                    "information_cutoff_utc",
                    "continuity_segment_id",
                    "revisions",
                    "envelope_fingerprint",
                }
            ),
        )
        revisions = data["revisions"]
        if not isinstance(revisions, Sequence) or isinstance(revisions, (str, bytes)):
            raise RollingFCRValidationError("date envelope revisions must be a sequence")
        predecessor = data["predecessor_date"]
        decision_cutoff = data["decision_cutoff_utc"]
        information_cutoff = data["information_cutoff_utc"]
        result = cls(
            manifest_fingerprint=data["manifest_fingerprint"],  # type: ignore[arg-type]
            profile_fingerprint=data["profile_fingerprint"],  # type: ignore[arg-type]
            profile_id=data["profile_id"],  # type: ignore[arg-type]
            classification=DeliveryDateClassification.from_dict(
                data["classification"]  # type: ignore[arg-type]
            ),
            predecessor_date=(
                None
                if predecessor is None
                else _date_from_text(predecessor, field_name="envelope.predecessor_date")
            ),
            continuity_segment_id=data["continuity_segment_id"],  # type: ignore[arg-type]
            revisions=tuple(
                RollingFCRDayRevision.from_dict(item)  # type: ignore[arg-type]
                for item in revisions
            ),
            decision_cutoff_utc=(
                None
                if decision_cutoff is None
                else _utc_from_text(
                    decision_cutoff, field_name="envelope.decision_cutoff_utc"
                )
            ),
            information_cutoff_utc=(
                None
                if information_cutoff is None
                else _utc_from_text(
                    information_cutoff,
                    field_name="envelope.information_cutoff_utc",
                )
            ),
        )
        _verify_persisted_fingerprint(
            field_name="envelope_fingerprint",
            provided=data["envelope_fingerprint"],
            recomputed=result.envelope_fingerprint,
        )
        return result


@dataclass(frozen=True, slots=True)
class AggregateMetricEvidence:
    metric_id: str
    unit: str
    value: float | None
    coverage_status: str
    eligible_dates: tuple[date, ...]
    contributing_dates: tuple[date, ...]
    omitted_dates_with_reasons: Mapping[str, tuple[str, ...]]
    aggregation_rule: str = "sum-v1"
    source_fingerprints: tuple[str, ...] = ()
    reconciliation_residual: float | None = None
    aggregate_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _non_empty(self.metric_id, field_name="metric_id"))
        object.__setattr__(self, "unit", _non_empty(self.unit, field_name="unit"))
        if self.coverage_status not in {"complete", "partial", "unavailable"}:
            raise RollingFCRValidationError("unsupported aggregate coverage status")
        if self.value is not None:
            object.__setattr__(self, "value", _finite(self.value, field_name="aggregate value"))
        object.__setattr__(
            self,
            "aggregation_rule",
            _non_empty(self.aggregation_rule, field_name="aggregation_rule"),
        )
        eligible = tuple(self.eligible_dates)
        contributors = tuple(self.contributing_dates)
        for name, values in (("eligible_dates", eligible), ("contributing_dates", contributors)):
            if any(
                not isinstance(item, date) or isinstance(item, datetime)
                for item in values
            ):
                raise RollingFCRValidationError(f"{name} must contain dates")
            if values != tuple(sorted(values)) or len(set(values)) != len(values):
                raise RollingFCRValidationError(f"{name} must be ordered and unique")
        if any(item not in eligible for item in contributors):
            raise RollingFCRValidationError(
                "aggregate contributing dates must be eligible"
            )
        omissions: dict[str, tuple[str, ...]] = {}
        for date_text, reasons in self.omitted_dates_with_reasons.items():
            parsed = _date_from_text(date_text, field_name="omitted date")
            if parsed not in eligible or parsed in contributors:
                raise RollingFCRValidationError(
                    "omitted dates must be eligible non-contributors"
                )
            normalized_reasons = tuple(
                sorted(_string_tuple(reasons, field_name=f"omissions.{date_text}"))
            )
            if not normalized_reasons:
                raise RollingFCRValidationError(
                    "every omitted date requires at least one reason"
                )
            omissions[parsed.isoformat()] = normalized_reasons
        expected_omissions = {
            item.isoformat() for item in eligible if item not in contributors
        }
        if set(omissions) != expected_omissions:
            raise RollingFCRValidationError(
                "aggregate omissions must account for exactly eligible non-contributors"
            )
        expected_status = (
            "unavailable"
            if not contributors
            else "complete"
            if len(contributors) == len(eligible)
            else "partial"
        )
        if self.coverage_status != expected_status:
            raise RollingFCRValidationError(
                "aggregate coverage must reconcile exactly eligible contributors"
            )
        if self.coverage_status == "unavailable" and self.value is not None:
            raise RollingFCRValidationError(
                "unavailable aggregate must not zero-fill a value"
            )
        if contributors and self.value is None:
            raise RollingFCRValidationError(
                "aggregate contributors require an available value"
            )
        source_fingerprints = tuple(
            _sha(value, field_name="source_fingerprints")
            for value in self.source_fingerprints
        )
        if len(source_fingerprints) != len(contributors):
            raise RollingFCRValidationError(
                "aggregate source fingerprints must identify every contributor"
            )
        residual = self.reconciliation_residual
        if residual is not None:
            residual = _finite(residual, field_name="reconciliation_residual")
            if residual < 0.0:
                raise RollingFCRValidationError(
                    "aggregate reconciliation residual must be non-negative"
                )
        if contributors and residual is None:
            raise RollingFCRValidationError(
                "aggregate contributors require reconciliation evidence"
            )
        object.__setattr__(self, "eligible_dates", eligible)
        object.__setattr__(self, "contributing_dates", contributors)
        object.__setattr__(
            self,
            "omitted_dates_with_reasons",
            MappingProxyType(dict(sorted(omissions.items()))),
        )
        object.__setattr__(self, "source_fingerprints", source_fingerprints)
        object.__setattr__(self, "reconciliation_residual", residual)
        object.__setattr__(self, "aggregate_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "unit": self.unit,
            "value": self.value,
            "coverage_status": self.coverage_status,
            "aggregation_rule": self.aggregation_rule,
            "eligible_dates": [item.isoformat() for item in self.eligible_dates],
            "contributing_dates": [item.isoformat() for item in self.contributing_dates],
            "omitted_dates_with_reasons": _thaw(self.omitted_dates_with_reasons),
            "source_fingerprints": list(self.source_fingerprints),
            "reconciliation_residual": self.reconciliation_residual,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "aggregate_fingerprint": self.aggregate_fingerprint}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> AggregateMetricEvidence:
        data = _strict_mapping(
            payload,
            field_name="aggregate metric",
            required_keys=frozenset(
                {
                    "metric_id",
                    "unit",
                    "value",
                    "coverage_status",
                    "aggregation_rule",
                    "eligible_dates",
                    "contributing_dates",
                    "omitted_dates_with_reasons",
                    "source_fingerprints",
                    "reconciliation_residual",
                    "aggregate_fingerprint",
                }
            ),
        )
        eligible = data["eligible_dates"]
        contributors = data["contributing_dates"]
        fingerprints = data["source_fingerprints"]
        for name, values in (
            ("eligible_dates", eligible),
            ("contributing_dates", contributors),
            ("source_fingerprints", fingerprints),
        ):
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                raise RollingFCRValidationError(f"aggregate {name} must be a sequence")
        result = cls(
            metric_id=data["metric_id"],  # type: ignore[arg-type]
            unit=data["unit"],  # type: ignore[arg-type]
            value=data["value"],  # type: ignore[arg-type]
            coverage_status=data["coverage_status"],  # type: ignore[arg-type]
            aggregation_rule=data["aggregation_rule"],  # type: ignore[arg-type]
            eligible_dates=tuple(
                _date_from_text(item, field_name="aggregate eligible date")
                for item in eligible
            ),
            contributing_dates=tuple(
                _date_from_text(item, field_name="aggregate contributing date")
                for item in contributors
            ),
            omitted_dates_with_reasons=data["omitted_dates_with_reasons"],  # type: ignore[arg-type]
            source_fingerprints=tuple(fingerprints),  # type: ignore[arg-type]
            reconciliation_residual=data["reconciliation_residual"],  # type: ignore[arg-type]
        )
        _verify_persisted_fingerprint(
            field_name="aggregate_fingerprint",
            provided=data["aggregate_fingerprint"],
            recomputed=result.aggregate_fingerprint,
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRResumeEvidence:
    """Fail-closed evidence for reusing immutable rolling-study records."""

    prior_result_semantic_fingerprint: str
    manifest_fingerprint: str
    profile_fingerprint: str
    reused_envelope_fingerprints: tuple[str, ...]
    reused_revision_fingerprints: tuple[str, ...]
    last_continuity_fingerprint: str | None
    last_state_link_fingerprint: str | None
    checks: Mapping[str, bool]
    diagnostics: tuple[str, ...]
    status: str
    semantics_version: str = ROLLING_FCR_RESUME_EVIDENCE_VERSION
    resume_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "prior_result_semantic_fingerprint",
            "manifest_fingerprint",
            "profile_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), field_name=name))
        for name in ("last_continuity_fingerprint", "last_state_link_fingerprint"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _sha(value, field_name=name))
        object.__setattr__(
            self,
            "reused_envelope_fingerprints",
            tuple(
                _sha(value, field_name="reused_envelope_fingerprints")
                for value in self.reused_envelope_fingerprints
            ),
        )
        object.__setattr__(
            self,
            "reused_revision_fingerprints",
            tuple(
                _sha(value, field_name="reused_revision_fingerprints")
                for value in self.reused_revision_fingerprints
            ),
        )
        normalized_checks: dict[str, bool] = {}
        for key, value in self.checks.items():
            normalized_key = _non_empty(key, field_name="resume check")
            if not isinstance(value, bool):
                raise RollingFCRValidationError("resume checks must be boolean")
            normalized_checks[normalized_key] = value
        expected_status = (
            "compatible" if normalized_checks and all(normalized_checks.values()) else "incompatible"
        )
        if self.status != expected_status:
            raise RollingFCRValidationError(
                "resume status does not reconcile exact compatibility checks"
            )
        diagnostics = tuple(
            sorted(_string_tuple(self.diagnostics, field_name="resume diagnostics"))
        )
        if self.status == "incompatible" and not diagnostics:
            raise RollingFCRValidationError(
                "incompatible resume evidence requires diagnostics"
            )
        object.__setattr__(
            self, "checks", MappingProxyType(dict(sorted(normalized_checks.items())))
        )
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "resume_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "prior_result_semantic_fingerprint": self.prior_result_semantic_fingerprint,
            "manifest_fingerprint": self.manifest_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "reused_envelope_fingerprints": list(
                self.reused_envelope_fingerprints
            ),
            "reused_revision_fingerprints": list(
                self.reused_revision_fingerprints
            ),
            "last_continuity_fingerprint": self.last_continuity_fingerprint,
            "last_state_link_fingerprint": self.last_state_link_fingerprint,
            "checks": dict(self.checks),
            "diagnostics": list(self.diagnostics),
            "status": self.status,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "resume_fingerprint": self.resume_fingerprint}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RollingFCRResumeEvidence:
        data = _strict_mapping(
            payload,
            field_name="resume evidence",
            required_keys=frozenset(
                {
                    "semantics_version",
                    "prior_result_semantic_fingerprint",
                    "manifest_fingerprint",
                    "profile_fingerprint",
                    "reused_envelope_fingerprints",
                    "reused_revision_fingerprints",
                    "last_continuity_fingerprint",
                    "last_state_link_fingerprint",
                    "checks",
                    "diagnostics",
                    "status",
                    "resume_fingerprint",
                }
            ),
        )
        for name in (
            "reused_envelope_fingerprints",
            "reused_revision_fingerprints",
            "diagnostics",
        ):
            if not isinstance(data[name], Sequence) or isinstance(
                data[name], (str, bytes)
            ):
                raise RollingFCRValidationError(f"resume {name} must be a sequence")
        result = cls(
            semantics_version=data["semantics_version"],  # type: ignore[arg-type]
            prior_result_semantic_fingerprint=data[
                "prior_result_semantic_fingerprint"
            ],  # type: ignore[arg-type]
            manifest_fingerprint=data["manifest_fingerprint"],  # type: ignore[arg-type]
            profile_fingerprint=data["profile_fingerprint"],  # type: ignore[arg-type]
            reused_envelope_fingerprints=tuple(
                data["reused_envelope_fingerprints"]  # type: ignore[arg-type]
            ),
            reused_revision_fingerprints=tuple(
                data["reused_revision_fingerprints"]  # type: ignore[arg-type]
            ),
            last_continuity_fingerprint=data[
                "last_continuity_fingerprint"
            ],  # type: ignore[arg-type]
            last_state_link_fingerprint=data[
                "last_state_link_fingerprint"
            ],  # type: ignore[arg-type]
            checks=data["checks"],  # type: ignore[arg-type]
            diagnostics=tuple(data["diagnostics"]),  # type: ignore[arg-type]
            status=data["status"],  # type: ignore[arg-type]
        )
        _verify_persisted_fingerprint(
            field_name="resume_fingerprint",
            provided=data["resume_fingerprint"],
            recomputed=result.resume_fingerprint,
        )
        return result


@dataclass(frozen=True, slots=True)
class RollingFCRStudyResult:
    study_id: str
    manifest_fingerprint: str
    profile_id: str
    profile_fingerprint: str
    records: tuple[DeliveryDateRecordEnvelope, ...]
    continuity_segments: tuple[ContinuitySegment, ...]
    state_links: tuple[RollingFCRStateLink, ...]
    aggregate_metrics: tuple[AggregateMetricEvidence, ...]
    completeness_status: str
    requested_day_input_fingerprints: Mapping[str, str] = field(
        default_factory=dict
    )
    supplied_activation_fingerprints: Mapping[str, str] = field(
        default_factory=dict
    )
    runtime_metadata: Mapping[str, object] = field(default_factory=dict)
    resume_lineage: RollingFCRResumeEvidence | None = None
    diagnostics: tuple[str, ...] = ()
    comparisons: tuple[Mapping[str, object], ...] = ()
    semantics_version: str = ROLLING_FCR_STUDY_RESULT_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "study_id", _non_empty(self.study_id, field_name="study_id"))
        object.__setattr__(self, "manifest_fingerprint", _sha(self.manifest_fingerprint, field_name="manifest_fingerprint"))
        object.__setattr__(self, "profile_fingerprint", _sha(self.profile_fingerprint, field_name="profile_fingerprint"))
        if self.profile_id not in _PROFILE_IDS:
            raise RollingFCRValidationError("study profile_id is unsupported")
        if self.semantics_version != ROLLING_FCR_STUDY_RESULT_VERSION:
            raise RollingFCRValidationError("unsupported rolling study result version")
        records = tuple(self.records)
        if not records or any(
            not isinstance(item, DeliveryDateRecordEnvelope) for item in records
        ):
            raise RollingFCRValidationError(
                "study records must retain at least one valid envelope"
            )
        dates = tuple(item.classification.delivery_date for item in records)
        if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
            raise RollingFCRValidationError("study records must retain ordered unique dates")
        if any(
            item.manifest_fingerprint != self.manifest_fingerprint
            or item.profile_fingerprint != self.profile_fingerprint
            or item.profile_id != self.profile_id
            for item in records
        ):
            raise RollingFCRValidationError(
                "study envelopes must retain the study manifest and profile identities"
            )
        if self.completeness_status not in {
            "complete",
            "partial",
            "failed",
            "incomplete",
        }:
            raise RollingFCRValidationError("unsupported study completeness status")
        segments = tuple(self.continuity_segments)
        if any(not isinstance(item, ContinuitySegment) for item in segments):
            raise RollingFCRValidationError("study continuity segment has the wrong type")
        segment_ids = tuple(item.segment_id for item in segments)
        if len(set(segment_ids)) != len(segment_ids):
            raise RollingFCRValidationError("continuity segment identities must be unique")
        if any(item.continuity_segment_id not in segment_ids for item in records):
            raise RollingFCRValidationError(
                "every date envelope must belong to a retained continuity segment"
            )
        segment_by_id = {item.segment_id: item for item in segments}
        if any(
            not (
                segment_by_id[item.continuity_segment_id].start_date
                <= item.classification.delivery_date
                <= segment_by_id[item.continuity_segment_id].end_date
            )
            for item in records
        ):
            raise RollingFCRValidationError(
                "date envelope lies outside its continuity segment"
            )
        links = tuple(self.state_links)
        if any(not isinstance(item, RollingFCRStateLink) for item in links):
            raise RollingFCRValidationError("study state link has the wrong type")
        if any(item.continuity_segment_id not in segment_ids for item in links):
            raise RollingFCRValidationError(
                "every state link must belong to a retained continuity segment"
            )
        if tuple(item.successor_date for item in links) != tuple(
            sorted(item.successor_date for item in links)
        ):
            raise RollingFCRValidationError("study state links must be date ordered")
        metrics = tuple(self.aggregate_metrics)
        if any(not isinstance(item, AggregateMetricEvidence) for item in metrics):
            raise RollingFCRValidationError("study aggregate has the wrong type")
        if len({item.metric_id for item in metrics}) != len(metrics):
            raise RollingFCRValidationError("study aggregate metric identities must be unique")
        if tuple(item.metric_id for item in metrics) != tuple(
            sorted(item.metric_id for item in metrics)
        ):
            raise RollingFCRValidationError("study aggregates must be canonically ordered")
        eligible_dates = tuple(
            item.classification.delivery_date
            for item in records
            if item.classification.execution_role == "included"
        )
        if any(item.eligible_dates != eligible_dates for item in metrics):
            raise RollingFCRValidationError(
                "study aggregate eligibility must match included date records"
            )
        if self.resume_lineage is not None and not isinstance(
            self.resume_lineage, RollingFCRResumeEvidence
        ):
            raise RollingFCRValidationError("resume_lineage has the wrong type")
        diagnostics = tuple(
            sorted(_string_tuple(self.diagnostics, field_name="study diagnostics"))
        )
        comparisons = tuple(
            _freeze_mapping(item, field_name="comparison") for item in self.comparisons
        )
        identity_maps: dict[str, MappingProxyType[str, str]] = {}
        record_date_texts = {item.isoformat() for item in dates}
        for field_name in (
            "requested_day_input_fingerprints",
            "supplied_activation_fingerprints",
        ):
            raw = getattr(self, field_name)
            if not isinstance(raw, Mapping):
                raise RollingFCRValidationError(f"{field_name} must be a mapping")
            normalized: dict[str, str] = {}
            for raw_date, fingerprint in raw.items():
                parsed = _date_from_text(raw_date, field_name=f"{field_name} date")
                if parsed.isoformat() not in record_date_texts:
                    raise RollingFCRValidationError(
                        f"{field_name} contains a date outside retained records"
                    )
                normalized[parsed.isoformat()] = _sha(
                    fingerprint, field_name=f"{field_name}.{raw_date}"
                )
            identity_maps[field_name] = MappingProxyType(
                dict(sorted(normalized.items()))
            )
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "continuity_segments", segments)
        object.__setattr__(self, "state_links", links)
        object.__setattr__(self, "aggregate_metrics", metrics)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "comparisons", comparisons)
        object.__setattr__(
            self,
            "requested_day_input_fingerprints",
            identity_maps["requested_day_input_fingerprints"],
        )
        object.__setattr__(
            self,
            "supplied_activation_fingerprints",
            identity_maps["supplied_activation_fingerprints"],
        )
        object.__setattr__(self, "runtime_metadata", _freeze_mapping(self.runtime_metadata, field_name="runtime_metadata"))
        statuses = tuple(item.latest_revision.lifecycle_status for item in records)
        if ("failed" in statuses) != (self.completeness_status == "failed"):
            raise RollingFCRValidationError(
                "study failed completeness must reconcile failed date records"
            )
        if self.completeness_status == "complete" and any(
            item in {"blocked_by_predecessor", "provisional", "unfinalized"}
            for item in statuses
        ):
            raise RollingFCRValidationError(
                "complete study cannot retain blocked, provisional, or unfinalized dates"
            )
        object.__setattr__(self, "semantic_fingerprint", _fingerprint(self._semantic_payload()))

    @property
    def requested_dates(self) -> tuple[date, ...]:
        return tuple(item.classification.delivery_date for item in self.records)

    @property
    def status_counts(self) -> Mapping[str, int]:
        roles = tuple(item.classification.execution_role for item in self.records)
        statuses = tuple(item.latest_revision.lifecycle_status for item in self.records)
        values = {
            "requested": len(self.records),
            "included": roles.count("included"),
            "compared": sum(
                item.classification.comparison_eligible for item in self.records
            ),
            "warm-up": roles.count("warm-up"),
            "close-out": roles.count("close-out"),
            "excluded": statuses.count("excluded"),
            "initialization_only": statuses.count("initialization_only"),
            "optimization_only": statuses.count("optimization_only"),
            "provisional": statuses.count("provisional"),
            "finalized": statuses.count("finalized"),
            "failed": statuses.count("failed"),
            "blocked_by_predecessor": statuses.count("blocked_by_predecessor"),
            "unfinalized": statuses.count("unfinalized"),
        }
        terminal_total = sum(
            values[key]
            for key in _TERMINAL_LIFECYCLE_STATUSES
            if key != "original"
        )
        if terminal_total != values["requested"]:
            raise RollingFCRValidationError(
                "study lifecycle status counts do not reconcile requested dates"
            )
        return MappingProxyType(values)

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "study_id": self.study_id,
            "manifest_fingerprint": self.manifest_fingerprint,
            "profile_id": self.profile_id,
            "profile_fingerprint": self.profile_fingerprint,
            "requested_dates": [item.isoformat() for item in self.requested_dates],
            "records": [
                {
                    **item._semantic_payload(),
                    "envelope_fingerprint": item.envelope_fingerprint,
                }
                for item in self.records
            ],
            "continuity_segments": [item.to_dict() for item in self.continuity_segments],
            "state_links": [item.to_dict() for item in self.state_links],
            "status_counts": dict(self.status_counts),
            "requested_day_input_fingerprints": dict(
                self.requested_day_input_fingerprints
            ),
            "supplied_activation_fingerprints": dict(
                self.supplied_activation_fingerprints
            ),
            "aggregate_metrics": [item.to_dict() for item in self.aggregate_metrics],
            "completeness_status": self.completeness_status,
            "diagnostics": list(self.diagnostics),
            "comparisons": [_thaw(item) for item in self.comparisons],
            "stable_runtime_evidence": _semantic_runtime_metadata(
                self.runtime_metadata
            ),
        }

    @property
    def finalized_parity_eligible_dates(self) -> tuple[date, ...]:
        """Dates explicitly eligible for finalized comparison evidence."""

        return tuple(
            item.classification.delivery_date
            for item in self.records
            if item.classification.comparison_eligible
            and item.latest_revision.lifecycle_status == "finalized"
        )

    @property
    def finalized_parity_exclusions(self) -> Mapping[str, tuple[str, ...]]:
        """Requested dates omitted from finalized parity with explicit reasons."""

        values: dict[str, tuple[str, ...]] = {}
        for item in self.records:
            if (
                item.classification.comparison_eligible
                and item.latest_revision.lifecycle_status == "finalized"
            ):
                continue
            reasons = [
                f"execution_role:{item.classification.execution_role}",
                f"lifecycle_status:{item.latest_revision.lifecycle_status}",
            ]
            reasons.extend(item.classification.reason_codes)
            values[item.classification.delivery_date.isoformat()] = tuple(
                sorted(set(reasons))
            )
        return MappingProxyType(dict(sorted(values.items())))

    def to_dict(self) -> dict[str, object]:
        payload = self._semantic_payload()
        payload["records"] = [item.to_dict() for item in self.records]
        return {
            **payload,
            "resume_lineage": (
                None
                if self.resume_lineage is None
                else self.resume_lineage.to_dict()
            ),
            "runtime_metadata": _thaw(self.runtime_metadata),
            "semantic_fingerprint": self.semantic_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RollingFCRStudyResult:
        data = _strict_mapping(
            payload,
            field_name="rolling study result",
            required_keys=frozenset(
                {
                    "semantics_version",
                    "study_id",
                    "manifest_fingerprint",
                    "profile_id",
                    "profile_fingerprint",
                    "requested_dates",
                    "records",
                    "continuity_segments",
                    "state_links",
                    "status_counts",
                    "requested_day_input_fingerprints",
                    "supplied_activation_fingerprints",
                    "aggregate_metrics",
                    "completeness_status",
                    "diagnostics",
                    "comparisons",
                    "stable_runtime_evidence",
                    "resume_lineage",
                    "runtime_metadata",
                    "semantic_fingerprint",
                }
            ),
        )
        sequence_names = (
            "requested_dates",
            "records",
            "continuity_segments",
            "state_links",
            "aggregate_metrics",
            "diagnostics",
            "comparisons",
        )
        for name in sequence_names:
            if not isinstance(data[name], Sequence) or isinstance(
                data[name], (str, bytes)
            ):
                raise RollingFCRValidationError(f"study {name} must be a sequence")
        result = cls(
            semantics_version=data["semantics_version"],  # type: ignore[arg-type]
            study_id=data["study_id"],  # type: ignore[arg-type]
            manifest_fingerprint=data["manifest_fingerprint"],  # type: ignore[arg-type]
            profile_id=data["profile_id"],  # type: ignore[arg-type]
            profile_fingerprint=data["profile_fingerprint"],  # type: ignore[arg-type]
            records=tuple(
                DeliveryDateRecordEnvelope.from_dict(item)  # type: ignore[arg-type]
                for item in data["records"]  # type: ignore[union-attr]
            ),
            continuity_segments=tuple(
                ContinuitySegment.from_dict(item)  # type: ignore[arg-type]
                for item in data["continuity_segments"]  # type: ignore[union-attr]
            ),
            state_links=tuple(
                RollingFCRStateLink.from_dict(item)  # type: ignore[arg-type]
                for item in data["state_links"]  # type: ignore[union-attr]
            ),
            aggregate_metrics=tuple(
                AggregateMetricEvidence.from_dict(item)  # type: ignore[arg-type]
                for item in data["aggregate_metrics"]  # type: ignore[union-attr]
            ),
            completeness_status=data["completeness_status"],  # type: ignore[arg-type]
            requested_day_input_fingerprints=data[
                "requested_day_input_fingerprints"
            ],  # type: ignore[arg-type]
            supplied_activation_fingerprints=data[
                "supplied_activation_fingerprints"
            ],  # type: ignore[arg-type]
            resume_lineage=(
                None
                if data["resume_lineage"] is None
                else RollingFCRResumeEvidence.from_dict(
                    data["resume_lineage"]  # type: ignore[arg-type]
                )
            ),
            diagnostics=tuple(data["diagnostics"]),  # type: ignore[arg-type]
            comparisons=tuple(data["comparisons"]),  # type: ignore[arg-type]
            runtime_metadata=data["runtime_metadata"],  # type: ignore[arg-type]
        )
        requested_dates = tuple(
            _date_from_text(item, field_name="requested_dates")
            for item in data["requested_dates"]  # type: ignore[union-attr]
        )
        if requested_dates != result.requested_dates:
            raise RollingFCRValidationError(
                "requested_dates do not match retained record order"
            )
        if data["status_counts"] != dict(result.status_counts):
            raise RollingFCRValidationError(
                "status_counts do not reconcile retained records"
            )
        if data["stable_runtime_evidence"] != _semantic_runtime_metadata(
            result.runtime_metadata
        ):
            raise RollingFCRValidationError(
                "stable_runtime_evidence does not match runtime metadata"
            )
        _verify_persisted_fingerprint(
            field_name="semantic_fingerprint",
            provided=data["semantic_fingerprint"],
            recomputed=result.semantic_fingerprint,
        )
        return result


def _aggregate_value_for_revision(
    revision: RollingFCRDayRevision,
    metric_id: str,
) -> float | None:
    if metric_id == "optimization_objective_eur":
        return revision.objective_value_eur
    if metric_id == "best_upper_bound_eur":
        return revision.best_upper_bound_eur
    realized_fields = {
        "realized_settlement_eur": "settlement.total_profit_eur",
        "realized_profit_eur": "total_profit_eur",
        "delivered_fcr_up_energy_kwh": (
            "delivered_fcr_energy_kwh.upward_discharge"
        ),
        "delivered_fcr_down_energy_kwh": (
            "delivered_fcr_energy_kwh.downward_charge"
        ),
        "throughput_kwh": "throughput_kwh",
    }
    field_name = realized_fields[metric_id]
    return revision.realized_metrics.get(field_name)


def aggregate_rolling_fcr_records(
    manifest: RollingFCRStudyManifest,
    records: tuple[DeliveryDateRecordEnvelope, ...],
) -> tuple[AggregateMetricEvidence, ...]:
    """Aggregate eligible evidence without dropping or zero-filling dates."""

    if not isinstance(manifest, RollingFCRStudyManifest):
        raise RollingFCRValidationError("manifest has the wrong contract type")
    ordered = tuple(records)
    expected_prefix = tuple(item.delivery_date for item in manifest.dates[: len(ordered)])
    actual_dates = tuple(item.classification.delivery_date for item in ordered)
    if actual_dates != expected_prefix:
        raise RollingFCRValidationError(
            "aggregate records must be an ordered manifest prefix"
        )
    if any(
        item.manifest_fingerprint != manifest.manifest_fingerprint
        or item.profile_fingerprint != manifest.profile.profile_fingerprint
        for item in ordered
    ):
        raise RollingFCRValidationError(
            "aggregate records belong to another manifest or profile"
        )
    eligible_records = tuple(
        item
        for item in ordered
        if item.classification.execution_role == "included"
    )
    eligible_dates = tuple(
        item.classification.delivery_date for item in eligible_records
    )
    definitions = (
        ("best_upper_bound_eur", "EUR"),
        ("delivered_fcr_down_energy_kwh", "kWh"),
        ("delivered_fcr_up_energy_kwh", "kWh"),
        ("optimization_objective_eur", "EUR"),
        ("realized_profit_eur", "EUR"),
        ("realized_settlement_eur", "EUR"),
        ("throughput_kwh", "kWh"),
    )
    aggregates: list[AggregateMetricEvidence] = []
    for metric_id, unit in definitions:
        contributor_rows: list[tuple[date, float, str]] = []
        omissions: dict[str, tuple[str, ...]] = {}
        for envelope in eligible_records:
            revision = envelope.latest_revision
            value = _aggregate_value_for_revision(revision, metric_id)
            delivery_date = envelope.classification.delivery_date
            if value is None:
                omissions[delivery_date.isoformat()] = (
                    f"metric_unavailable:{metric_id}",
                    f"lifecycle_status:{revision.lifecycle_status}",
                )
            else:
                contributor_rows.append(
                    (delivery_date, float(value), revision.revision_fingerprint)
                )
        contributing_dates = tuple(item[0] for item in contributor_rows)
        values = tuple(item[1] for item in contributor_rows)
        value = None if not values else math.fsum(values)
        coverage = (
            "unavailable"
            if not contributing_dates
            else "complete"
            if len(contributing_dates) == len(eligible_dates)
            else "partial"
        )
        aggregates.append(
            AggregateMetricEvidence(
                metric_id=metric_id,
                unit=unit,
                value=value,
                coverage_status=coverage,
                eligible_dates=eligible_dates,
                contributing_dates=contributing_dates,
                omitted_dates_with_reasons=omissions,
                aggregation_rule="ordered-math-fsum-v1",
                source_fingerprints=tuple(item[2] for item in contributor_rows),
                reconciliation_residual=(None if value is None else 0.0),
            )
        )
    return tuple(aggregates)


def assess_rolling_fcr_resume(
    manifest: RollingFCRStudyManifest,
    prior_result: RollingFCRStudyResult,
) -> RollingFCRResumeEvidence:
    """Assess exact semantic reuse without partly approving any mismatch."""

    if not isinstance(manifest, RollingFCRStudyManifest):
        raise RollingFCRValidationError("manifest has the wrong contract type")
    if not isinstance(prior_result, RollingFCRStudyResult):
        raise RollingFCRValidationError("prior_result has the wrong contract type")
    expected_dates = tuple(
        item.delivery_date for item in manifest.dates[: len(prior_result.records)]
    )
    record_dates = prior_result.requested_dates
    segment_ids = {item.segment_id for item in prior_result.continuity_segments}
    caller_state_fingerprints = {
        item.state_fingerprint for item in manifest.caller_state_declarations
    }
    continuity_origins_match = all(
        (
            index == 0
            and item.start_reason == "manifest_start"
            and item.source_state_fingerprint is None
        )
        or (
            index > 0
            and item.start_reason == "caller_supplied"
            and item.source_state_fingerprint in caller_state_fingerprints
        )
        for index, item in enumerate(prior_result.continuity_segments)
    )
    record_by_date = {
        item.classification.delivery_date: item for item in prior_result.records
    }
    state_link_evidence_matches = True
    for link in prior_result.state_links:
        successor = record_by_date.get(link.successor_date)
        predecessor = record_by_date.get(link.predecessor_date)
        if successor is None:
            state_link_evidence_matches = False
            break
        successor_initial = successor.revisions[0].initial_stored_energy_kwh
        if (
            successor_initial is None
            or abs(successor_initial - link.successor_initial_stored_energy_kwh)
            > link.reconciliation_tolerance_kwh
        ):
            state_link_evidence_matches = False
            break
        linked_revisions = tuple(successor.revisions) + (
            () if predecessor is None else tuple(predecessor.revisions)
        )
        if not any(
            item.state_link_fingerprint == link.state_link_fingerprint
            for item in linked_revisions
        ):
            state_link_evidence_matches = False
            break
    try:
        expected_aggregates = aggregate_rolling_fcr_records(
            manifest, prior_result.records
        )
        aggregate_match = tuple(
            item.aggregate_fingerprint for item in expected_aggregates
        ) == tuple(
            item.aggregate_fingerprint for item in prior_result.aggregate_metrics
        )
    except RollingFCRValidationError:
        aggregate_match = False
    checks = {
        "aggregate_evidence": aggregate_match,
        "continuity_membership": all(
            item.continuity_segment_id in segment_ids
            for item in (*prior_result.records, *prior_result.state_links)
        ),
        "continuity_origins": continuity_origins_match,
        "manifest_fingerprint": (
            prior_result.manifest_fingerprint == manifest.manifest_fingerprint
        ),
        "ordered_dates": bool(prior_result.records) and record_dates == expected_dates,
        "profile_fingerprint": (
            prior_result.profile_fingerprint
            == manifest.profile.profile_fingerprint
            and prior_result.profile_id == manifest.profile.profile_id
        ),
        "record_classifications": all(
            prior.classification.classification_fingerprint
            == expected.classification_fingerprint
            for prior, expected in zip(
                prior_result.records,
                manifest.dates,
                strict=False,
            )
        ),
        "record_manifest_identity": all(
            item.manifest_fingerprint == manifest.manifest_fingerprint
            and item.profile_fingerprint == manifest.profile.profile_fingerprint
            for item in prior_result.records
        ),
        "state_link_reconciliation": all(
            item.reconciles for item in prior_result.state_links
        ),
        "state_link_evidence": state_link_evidence_matches,
        "study_identity": prior_result.study_id == manifest.study_id,
    }
    diagnostics = tuple(
        f"resume_mismatch:{name}"
        for name, compatible in sorted(checks.items())
        if not compatible
    )
    return RollingFCRResumeEvidence(
        prior_result_semantic_fingerprint=prior_result.semantic_fingerprint,
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        reused_envelope_fingerprints=tuple(
            item.envelope_fingerprint for item in prior_result.records
        ),
        reused_revision_fingerprints=tuple(
            revision.revision_fingerprint
            for item in prior_result.records
            for revision in item.revisions
        ),
        last_continuity_fingerprint=(
            None
            if not prior_result.continuity_segments
            else prior_result.continuity_segments[-1].continuity_fingerprint
        ),
        last_state_link_fingerprint=(
            None
            if not prior_result.state_links
            else prior_result.state_links[-1].state_link_fingerprint
        ),
        checks=checks,
        diagnostics=diagnostics,
        status="compatible" if all(checks.values()) else "incompatible",
    )


def load_rolling_fcr_study_result(path: Path) -> RollingFCRStudyResult:
    """Load one strict result without resolving any referenced artifact."""

    if not isinstance(path, Path):
        raise RollingFCRValidationError("rolling study result path must be a Path")
    try:
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise RollingFCRValidationError(
            f"unable to load rolling study result: {type(exc).__name__}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise RollingFCRValidationError("rolling study result root must be a mapping")
    return RollingFCRStudyResult.from_dict(payload)


def run_rolling_fcr_study(
    manifest: RollingFCRStudyManifest,
    day_inputs: tuple[RollingFCRDayInput, ...],
    *,
    activation_traces: Mapping[date, object] | None = None,
    resume_from: RollingFCRStudyResult | None = None,
) -> RollingFCRStudyResult:
    """Run the initial deterministic profile state machine in date order."""

    if not isinstance(manifest, RollingFCRStudyManifest):
        raise RollingFCRValidationError("manifest has the wrong contract type")
    inputs = tuple(day_inputs)
    if any(not isinstance(item, RollingFCRDayInput) for item in inputs):
        raise RollingFCRValidationError("day_inputs contain an invalid contract")
    for item in inputs:
        if item.manifest_fingerprint != manifest.manifest_fingerprint:
            raise RollingFCRValidationError("day input belongs to another manifest")
        if item.profile_fingerprint != manifest.profile.profile_fingerprint:
            raise RollingFCRValidationError("day input belongs to another profile")
    from ._fcr_rolling_orchestrator import run_initial_rolling_fcr_study

    return run_initial_rolling_fcr_study(
        manifest,
        inputs,
        activation_traces=activation_traces,
        resume_from=resume_from,
    )


__all__ = [
    "AGGREGATION_POLICY",
    "AcceptedBidPolicy",
    "AggregateMetricEvidence",
    "CallerSuppliedRollingState",
    "ContinuitySegment",
    "DeliveryDateClassification",
    "DeliveryDateRecordEnvelope",
    "FAILURE_POLICY_COUPLED",
    "FAILURE_POLICY_INDEPENDENT",
    "RESUME_POLICY",
    "RollingFCRBatteryBinding",
    "RollingFCRDataDescriptor",
    "RollingFCRDayInput",
    "RollingFCRDayRevision",
    "RollingFCRExperimentProfile",
    "RollingFCRNumericPolicy",
    "RollingFCRResumeEvidence",
    "RollingFCRStateLink",
    "RollingFCRStateCarryEvidence",
    "RollingFCRStudyManifest",
    "RollingFCRStudyResult",
    "RollingFCRValidationError",
    "SOURCE_REFERENCE_REVISION",
    "build_rolling_fcr_experiment_profile",
    "build_rolling_fcr_study_manifest",
    "aggregate_rolling_fcr_records",
    "assess_rolling_fcr_resume",
    "derive_rolling_fcr_state_carry",
    "load_rolling_fcr_study_result",
    "run_rolling_fcr_study",
]
