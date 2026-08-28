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
import math
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
ROLLING_FCR_PROFILE_VERSION = "oel.fcr-rolling-experiment-profile.v1"

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
    state_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.delivery_date, date) or isinstance(self.delivery_date, datetime):
            raise RollingFCRValidationError("caller state delivery_date must be a date")
        object.__setattr__(self, "stored_energy_kwh", _finite(self.stored_energy_kwh, field_name="stored_energy_kwh"))
        object.__setattr__(self, "observation_cutoff_utc", _utc(self.observation_cutoff_utc, field_name="observation_cutoff_utc"))
        object.__setattr__(self, "source_fingerprint", _sha(self.source_fingerprint, field_name="source_fingerprint"))
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
    state_link_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.handoff_kind not in {"midnight", "cutoff_0800", "caller_supplied"}:
            raise RollingFCRValidationError("unsupported state-link handoff kind")
        if self.successor_date <= self.predecessor_date and self.handoff_kind != "caller_supplied":
            raise RollingFCRValidationError("state-link successor must follow predecessor")
        object.__setattr__(self, "observation_cutoff_utc", _utc(self.observation_cutoff_utc, field_name="observation_cutoff_utc"))
        object.__setattr__(self, "replay_checkpoint_kwh", _finite(self.replay_checkpoint_kwh, field_name="replay_checkpoint_kwh"))
        object.__setattr__(self, "carried_stored_energy_kwh", _finite(self.carried_stored_energy_kwh, field_name="carried_stored_energy_kwh"))
        interval = tuple(_finite(value, field_name="source_interval_kwh") for value in self.source_interval_kwh)
        if len(interval) != 2 or interval[0] > self.carried_stored_energy_kwh or interval[1] < self.carried_stored_energy_kwh:
            raise RollingFCRValidationError("source interval must contain the carried state")
        object.__setattr__(self, "source_interval_kwh", interval)
        for name in (
            "predecessor_plan_fingerprint",
            "replay_fingerprint",
            "activation_fingerprint",
            "accepted_fixings_fingerprint",
            "successor_problem_fingerprint",
            "causal_prefix_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _sha(value, field_name=name))
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
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "state_link_fingerprint": self.state_link_fingerprint}


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
        slacks: dict[str, float] = {}
        for name, value in self.feasibility_slacks.items():
            normalized_name = _non_empty(name, field_name="feasibility slack name")
            normalized = _finite(value, field_name=f"feasibility_slacks.{name}")
            if normalized < 0.0:
                raise RollingFCRValidationError("feasibility slacks must be non-negative")
            slacks[normalized_name] = normalized
        object.__setattr__(self, "feasibility_slacks", MappingProxyType(dict(sorted(slacks.items()))))
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
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "runtime_metadata": _thaw(self.runtime_metadata),
            "revision_fingerprint": self.revision_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class DeliveryDateRecordEnvelope:
    manifest_fingerprint: str
    profile_fingerprint: str
    classification: DeliveryDateClassification
    predecessor_date: date | None
    continuity_segment_id: str
    revisions: tuple[RollingFCRDayRevision, ...]
    envelope_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_fingerprint", _sha(self.manifest_fingerprint, field_name="manifest_fingerprint"))
        object.__setattr__(self, "profile_fingerprint", _sha(self.profile_fingerprint, field_name="profile_fingerprint"))
        if not isinstance(self.classification, DeliveryDateClassification):
            raise RollingFCRValidationError("envelope classification has the wrong type")
        object.__setattr__(self, "continuity_segment_id", _non_empty(self.continuity_segment_id, field_name="continuity_segment_id"))
        revisions = tuple(self.revisions)
        if not revisions or any(not isinstance(item, RollingFCRDayRevision) for item in revisions):
            raise RollingFCRValidationError("envelope must retain immutable revisions")
        if tuple(item.revision_number for item in revisions) != tuple(range(len(revisions))):
            raise RollingFCRValidationError("revision numbers must be contiguous and monotonic")
        object.__setattr__(self, "revisions", revisions)
        object.__setattr__(self, "envelope_fingerprint", _fingerprint(self._payload()))

    @property
    def latest_revision(self) -> RollingFCRDayRevision:
        return self.revisions[-1]

    def _payload(self) -> dict[str, object]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "classification": self.classification.to_dict(),
            "predecessor_date": None if self.predecessor_date is None else self.predecessor_date.isoformat(),
            "continuity_segment_id": self.continuity_segment_id,
            "revisions": [item.to_dict() for item in self.revisions],
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "envelope_fingerprint": self.envelope_fingerprint}


@dataclass(frozen=True, slots=True)
class AggregateMetricEvidence:
    metric_id: str
    unit: str
    value: float | None
    coverage_status: str
    eligible_dates: tuple[date, ...]
    contributing_dates: tuple[date, ...]
    omitted_dates_with_reasons: Mapping[str, tuple[str, ...]]
    aggregate_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _non_empty(self.metric_id, field_name="metric_id"))
        object.__setattr__(self, "unit", _non_empty(self.unit, field_name="unit"))
        if self.coverage_status not in {"complete", "partial", "unavailable"}:
            raise RollingFCRValidationError("unsupported aggregate coverage status")
        if self.value is not None:
            object.__setattr__(self, "value", _finite(self.value, field_name="aggregate value"))
        object.__setattr__(self, "eligible_dates", tuple(self.eligible_dates))
        object.__setattr__(self, "contributing_dates", tuple(self.contributing_dates))
        object.__setattr__(self, "omitted_dates_with_reasons", _freeze_mapping(self.omitted_dates_with_reasons, field_name="omitted_dates_with_reasons"))
        object.__setattr__(self, "aggregate_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "unit": self.unit,
            "value": self.value,
            "coverage_status": self.coverage_status,
            "eligible_dates": [item.isoformat() for item in self.eligible_dates],
            "contributing_dates": [item.isoformat() for item in self.contributing_dates],
            "omitted_dates_with_reasons": _thaw(self.omitted_dates_with_reasons),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "aggregate_fingerprint": self.aggregate_fingerprint}


@dataclass(frozen=True, slots=True)
class RollingFCRStudyResult:
    manifest_fingerprint: str
    profile_fingerprint: str
    records: tuple[DeliveryDateRecordEnvelope, ...]
    continuity_segments: tuple[ContinuitySegment, ...]
    state_links: tuple[RollingFCRStateLink, ...]
    aggregate_metrics: tuple[AggregateMetricEvidence, ...]
    completeness_status: str
    runtime_metadata: Mapping[str, object] = field(default_factory=dict)
    semantics_version: str = ROLLING_FCR_STUDY_RESULT_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_fingerprint", _sha(self.manifest_fingerprint, field_name="manifest_fingerprint"))
        object.__setattr__(self, "profile_fingerprint", _sha(self.profile_fingerprint, field_name="profile_fingerprint"))
        records = tuple(self.records)
        if any(not isinstance(item, DeliveryDateRecordEnvelope) for item in records):
            raise RollingFCRValidationError("study records contain an invalid envelope")
        dates = tuple(item.classification.delivery_date for item in records)
        if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
            raise RollingFCRValidationError("study records must retain ordered unique dates")
        if self.completeness_status not in {"complete", "partial", "failed"}:
            raise RollingFCRValidationError("unsupported study completeness status")
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "continuity_segments", tuple(self.continuity_segments))
        object.__setattr__(self, "state_links", tuple(self.state_links))
        object.__setattr__(self, "aggregate_metrics", tuple(self.aggregate_metrics))
        object.__setattr__(self, "runtime_metadata", _freeze_mapping(self.runtime_metadata, field_name="runtime_metadata"))
        object.__setattr__(self, "semantic_fingerprint", _fingerprint(self._semantic_payload()))

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "records": [item.to_dict() for item in self.records],
            "continuity_segments": [item.to_dict() for item in self.continuity_segments],
            "state_links": [item.to_dict() for item in self.state_links],
            "aggregate_metrics": [item.to_dict() for item in self.aggregate_metrics],
            "completeness_status": self.completeness_status,
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
        return {
            **self._semantic_payload(),
            "runtime_metadata": _thaw(self.runtime_metadata),
            "semantic_fingerprint": self.semantic_fingerprint,
        }


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
    "RollingFCRStateLink",
    "RollingFCRStudyManifest",
    "RollingFCRStudyResult",
    "RollingFCRValidationError",
    "SOURCE_REFERENCE_REVISION",
    "build_rolling_fcr_experiment_profile",
    "build_rolling_fcr_study_manifest",
    "run_rolling_fcr_study",
]
