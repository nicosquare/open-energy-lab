"""Source-independent inputs and immutable reports for fixed FCR bid evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any

from open_energy_lab.control.fcr_bid_plan import FixedFCRBidPlan
from open_energy_lab.market.activation import RegulationActivationTrace
from open_energy_lab.market.artifact import MarketDataArtifact
from open_energy_lab.market.time import CanonicalInterval

from .scenario import BatteryComponent
from .stacked_service import (
    EnergyBaselineSchedule,
    FCRCapacitySchedule,
    MultiRateTimeContract,
    TerminalSOCTarget,
)


FCR_BID_EVALUATION_SEMANTICS_VERSION = "oel.fcr-bid-evaluation.v1"
FCR_BID_EVALUATION_REPORT_SCHEMA_VERSION = "oel.fcr-bid-evaluation-report.v1"
FEATURE_010_DEFAULT_SETTLEMENT_PROFILE = "feature-010-default-v1"
REFERENCE_SETTLEMENT_PROFILE = "robust-storage-bidding-reference-settlement-v1"

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_CONTEXT_KINDS = {"feature_010_market_artifact", "reference_result"}
_SETTLEMENT_PROFILES = {
    FEATURE_010_DEFAULT_SETTLEMENT_PROFILE,
    REFERENCE_SETTLEMENT_PROFILE,
}
_DIAGNOSTIC_PHASE_ORDER = {
    "input": 0,
    "plan": 1,
    "preflight": 2,
    "replay": 3,
    "settlement": 4,
    "comparison": 5,
    "report": 6,
}


class FCRBidEvaluationValidationError(ValueError):
    """Raised when evaluation inputs or immutable report shapes are invalid."""


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FCRBidEvaluationValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FCRBidEvaluationValidationError(f"{field_name} must be finite")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise FCRBidEvaluationValidationError(f"{field_name} must be finite")
    return normalized


def _sha256(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise FCRBidEvaluationValidationError(
            f"{field_name} must be a lowercase SHA-256 fingerprint"
        )
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(inner) for key, inner in sorted(value.items())}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(inner) for inner in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(inner) for key, inner in value.items()}
    if isinstance(value, tuple):
        return [_thaw(inner) for inner in value]
    return value


def canonical_json_bytes(value: object) -> bytes:
    """Return the compact, sorted, finite JSON representation used by fingerprints."""

    try:
        return json.dumps(
            _thaw(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FCRBidEvaluationValidationError(
            f"evaluation data must be finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _same_interval(left: CanonicalInterval, right: CanonicalInterval) -> bool:
    return (
        left.start_utc == right.start_utc
        and left.end_utc == right.end_utc
    )


def _battery_payload(battery: BatteryComponent) -> dict[str, object]:
    return {
        "name": battery.name,
        "capacity_kwh": battery.capacity_kwh,
        "max_charge_kw": battery.max_charge_kw,
        "max_discharge_kw": battery.max_discharge_kw,
        "charge_efficiency": battery.charge_efficiency,
        "discharge_efficiency": battery.discharge_efficiency,
        "initial_soc": battery.initial_soc,
        "min_soc": battery.min_soc,
        "max_soc": battery.max_soc,
    }


@dataclass(frozen=True, slots=True)
class EvaluationPriceObservation:
    interval: CanonicalInterval
    price_kind: str
    source_value: float
    source_unit: str
    canonical_value: float
    canonical_unit: str
    conversion_id: str
    source_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.interval, CanonicalInterval):
            raise FCRBidEvaluationValidationError(
                "price interval must be a CanonicalInterval"
            )
        if self.price_kind not in {"day_ahead_energy", "fcr_capacity"}:
            raise FCRBidEvaluationValidationError("price kind is not supported")
        object.__setattr__(
            self,
            "source_value",
            _finite(self.source_value, field_name="price source_value"),
        )
        object.__setattr__(
            self,
            "source_unit",
            _non_empty(self.source_unit, field_name="price source_unit"),
        )
        object.__setattr__(
            self,
            "canonical_value",
            _finite(self.canonical_value, field_name="price canonical_value"),
        )
        object.__setattr__(
            self,
            "canonical_unit",
            _non_empty(self.canonical_unit, field_name="price canonical_unit"),
        )
        object.__setattr__(
            self,
            "conversion_id",
            _non_empty(self.conversion_id, field_name="price conversion_id"),
        )
        object.__setattr__(
            self,
            "source_ref",
            _non_empty(self.source_ref, field_name="price source_ref"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "price_kind": self.price_kind,
            "source_value": self.source_value,
            "source_unit": self.source_unit,
            "canonical_value": self.canonical_value,
            "canonical_unit": self.canonical_unit,
            "conversion_id": self.conversion_id,
            "source_ref": self.source_ref,
        }


def _validate_price_coverage(
    observations: tuple[EvaluationPriceObservation, ...],
    *,
    period: CanonicalInterval,
    price_kind: str,
) -> None:
    if not observations:
        raise FCRBidEvaluationValidationError(
            f"{price_kind} prices must cover the evaluation period"
        )
    if any(item.price_kind != price_kind for item in observations):
        raise FCRBidEvaluationValidationError(
            f"{price_kind} prices contain an incompatible price kind"
        )
    if (
        observations[0].interval.start_utc != period.start_utc
        or observations[-1].interval.end_utc != period.end_utc
        or any(
            left.interval.end_utc != right.interval.start_utc
            for left, right in zip(observations, observations[1:], strict=False)
        )
    ):
        raise FCRBidEvaluationValidationError(
            f"{price_kind} prices must provide complete ordered period coverage"
        )


@dataclass(frozen=True, slots=True)
class EvaluationMarketContext:
    context_kind: str
    semantics_version: str
    period: CanonicalInterval
    day_ahead_prices: tuple[EvaluationPriceObservation, ...]
    fcr_capacity_prices: tuple[EvaluationPriceObservation, ...]
    accepted_bid_evidence: Mapping[str, object]
    source_fingerprints: Mapping[str, str]
    context_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.context_kind not in _CONTEXT_KINDS:
            raise FCRBidEvaluationValidationError(
                "context kind must be feature_010_market_artifact or reference_result"
            )
        object.__setattr__(
            self,
            "semantics_version",
            _non_empty(
                self.semantics_version,
                field_name="market context semantics_version",
            ),
        )
        if not isinstance(self.period, CanonicalInterval):
            raise FCRBidEvaluationValidationError(
                "market context period must be a CanonicalInterval"
            )
        day_ahead = tuple(self.day_ahead_prices)
        fcr_capacity = tuple(self.fcr_capacity_prices)
        if any(not isinstance(item, EvaluationPriceObservation) for item in day_ahead):
            raise FCRBidEvaluationValidationError(
                "day-ahead prices must be EvaluationPriceObservation values"
            )
        if any(not isinstance(item, EvaluationPriceObservation) for item in fcr_capacity):
            raise FCRBidEvaluationValidationError(
                "FCR capacity prices must be EvaluationPriceObservation values"
            )
        _validate_price_coverage(
            day_ahead,
            period=self.period,
            price_kind="day_ahead_energy",
        )
        _validate_price_coverage(
            fcr_capacity,
            period=self.period,
            price_kind="fcr_capacity",
        )
        if not isinstance(self.accepted_bid_evidence, Mapping):
            raise FCRBidEvaluationValidationError(
                "accepted_bid_evidence must be a mapping"
            )
        if not isinstance(self.source_fingerprints, Mapping):
            raise FCRBidEvaluationValidationError(
                "source_fingerprints must be a mapping"
            )
        source_fingerprints = {
            _non_empty(key, field_name="market source fingerprint key"): _sha256(
                value,
                field_name=f"market source fingerprint {key!r}",
            )
            for key, value in self.source_fingerprints.items()
        }
        object.__setattr__(self, "day_ahead_prices", day_ahead)
        object.__setattr__(self, "fcr_capacity_prices", fcr_capacity)
        object.__setattr__(self, "accepted_bid_evidence", _freeze(self.accepted_bid_evidence))
        object.__setattr__(
            self,
            "source_fingerprints",
            _freeze(source_fingerprints),
        )
        object.__setattr__(self, "context_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "context_kind": self.context_kind,
            "semantics_version": self.semantics_version,
            "period": self.period.to_dict(),
            "day_ahead_prices": [item.to_dict() for item in self.day_ahead_prices],
            "fcr_capacity_prices": [item.to_dict() for item in self.fcr_capacity_prices],
            "accepted_bid_evidence": _thaw(self.accepted_bid_evidence),
            "source_fingerprints": _thaw(self.source_fingerprints),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "context_fingerprint": self.context_fingerprint}


def _observations_within_period(series: object, period: CanonicalInterval) -> tuple[object, ...]:
    return tuple(
        observation
        for observation in series.observations
        if observation.interval.start_utc >= period.start_utc
        and observation.interval.end_utc <= period.end_utc
    )


def build_feature_010_market_context(
    *,
    market_artifact: MarketDataArtifact,
    period: CanonicalInterval,
) -> EvaluationMarketContext:
    """Copy validated Feature 010 observations into a source-independent view."""

    if not isinstance(market_artifact, MarketDataArtifact):
        raise FCRBidEvaluationValidationError(
            "market_artifact must be one validated MarketDataArtifact"
        )
    if not isinstance(period, CanonicalInterval):
        raise FCRBidEvaluationValidationError("period must be a CanonicalInterval")
    covered = market_artifact.actual_covered_period
    if (
        period.start_utc < covered.start_utc
        or period.end_utc > covered.end_utc
    ):
        raise FCRBidEvaluationValidationError(
            "Feature 010 artifact does not contain the market-context period"
        )
    day_series = market_artifact.series["day_ahead_price"]
    fcr_series = market_artifact.series["fcr_capacity_price"]
    volume_series = market_artifact.series["fcr_contracted_volume"]
    day_observations = _observations_within_period(day_series, period)
    fcr_observations = _observations_within_period(fcr_series, period)
    volume_observations = _observations_within_period(volume_series, period)
    day_prices = tuple(
        EvaluationPriceObservation(
            interval=observation.interval,
            price_kind="day_ahead_energy",
            source_value=observation.value,
            source_unit=day_series.canonical_unit,
            canonical_value=observation.value,
            canonical_unit="EUR/MWh",
            conversion_id="feature-010-canonical-identity-v1",
            source_ref=f"day_ahead_price:{index}",
        )
        for index, observation in enumerate(day_observations)
    )
    fcr_prices = tuple(
        EvaluationPriceObservation(
            interval=observation.interval,
            price_kind="fcr_capacity",
            source_value=observation.value,
            source_unit=fcr_series.canonical_unit,
            canonical_value=observation.value,
            canonical_unit="EUR/MW/h",
            conversion_id="feature-010-canonical-identity-v1",
            source_ref=f"fcr_capacity_price:{index}",
        )
        for index, observation in enumerate(fcr_observations)
    )
    accepted = {
        f"fcr_contracted_volume:{index}": {
            "interval": observation.interval.to_dict(),
            "value": observation.value,
            "unit": volume_series.canonical_unit,
            "evidence_kind": "observed_market_volume",
        }
        for index, observation in enumerate(volume_observations)
    }
    return EvaluationMarketContext(
        context_kind="feature_010_market_artifact",
        semantics_version="feature-010-market-artifact-context-v1",
        period=period,
        day_ahead_prices=day_prices,
        fcr_capacity_prices=fcr_prices,
        accepted_bid_evidence=accepted,
        source_fingerprints={"market_artifact": market_artifact.artifact_fingerprint},
    )


@dataclass(frozen=True, slots=True)
class EvaluationDiagnostic:
    phase: str
    code: str
    severity: str
    field_path: str | None
    message: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.phase not in _DIAGNOSTIC_PHASE_ORDER:
            raise FCRBidEvaluationValidationError("diagnostic phase is not supported")
        object.__setattr__(self, "code", _non_empty(self.code, field_name="diagnostic code"))
        if self.severity not in {"info", "warning", "error"}:
            raise FCRBidEvaluationValidationError(
                "diagnostic severity must be info, warning, or error"
            )
        if self.field_path is not None:
            object.__setattr__(
                self,
                "field_path",
                _non_empty(self.field_path, field_name="diagnostic field_path"),
            )
        object.__setattr__(
            self,
            "message",
            _non_empty(self.message, field_name="diagnostic message"),
        )
        if isinstance(self.evidence_refs, (str, bytes)) or not isinstance(
            self.evidence_refs, Sequence
        ):
            raise FCRBidEvaluationValidationError(
                "diagnostic evidence_refs must be a sequence"
            )
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(
                _non_empty(item, field_name="diagnostic evidence reference")
                for item in self.evidence_refs
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "code": self.code,
            "severity": self.severity,
            "field_path": self.field_path,
            "message": self.message,
            "evidence_refs": list(self.evidence_refs),
        }


def _diagnostic_sort_key(item: EvaluationDiagnostic) -> tuple[object, ...]:
    return (
        _DIAGNOSTIC_PHASE_ORDER[item.phase],
        item.field_path or "",
        item.code,
        item.evidence_refs,
        item.message,
    )


@dataclass(frozen=True, slots=True)
class ComponentAvailability:
    status: str
    value_eur: float | None
    reason: str | None

    def __post_init__(self) -> None:
        if self.status == "available":
            object.__setattr__(
                self,
                "value_eur",
                _finite(self.value_eur, field_name="available component value_eur"),
            )
            if self.reason is not None:
                raise FCRBidEvaluationValidationError(
                    "available component reason must be absent"
                )
        elif self.status == "unavailable":
            if self.value_eur is not None:
                raise FCRBidEvaluationValidationError(
                    "unavailable component value must be absent"
                )
            object.__setattr__(
                self,
                "reason",
                _non_empty(self.reason, field_name="unavailable component reason"),
            )
        else:
            raise FCRBidEvaluationValidationError(
                "component status must be available or unavailable"
            )

    @classmethod
    def available(cls, value_eur: float) -> ComponentAvailability:
        return cls(status="available", value_eur=value_eur, reason=None)

    @classmethod
    def unavailable(cls, reason: str) -> ComponentAvailability:
        return cls(status="unavailable", value_eur=None, reason=reason)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "value_eur": self.value_eur,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class FCRBidEvaluationRequest:
    evaluation_id: str
    plan: FixedFCRBidPlan
    market_context: EvaluationMarketContext
    activation_trace: RegulationActivationTrace
    battery: BatteryComponent
    time_contract: MultiRateTimeContract
    settlement_profile: str
    penalty_rule: object | None
    terminal_soc_target: TerminalSOCTarget | None
    comparison_fixture: object | None
    numeric_tolerance: float
    semantics_version: str = FCR_BID_EVALUATION_SEMANTICS_VERSION
    input_fingerprints: Mapping[str, object] = field(init=False)
    evaluation_input_fingerprint: str = field(init=False)
    _battery_fingerprint_at_binding: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evaluation_id",
            _non_empty(self.evaluation_id, field_name="evaluation_id"),
        )
        if self.semantics_version != FCR_BID_EVALUATION_SEMANTICS_VERSION:
            raise FCRBidEvaluationValidationError(
                "unsupported FCR bid-evaluation semantics version"
            )
        if not isinstance(self.plan, FixedFCRBidPlan):
            raise FCRBidEvaluationValidationError("plan must be one FixedFCRBidPlan")
        if not isinstance(self.market_context, EvaluationMarketContext):
            raise FCRBidEvaluationValidationError(
                "market_context must be one EvaluationMarketContext"
            )
        if not isinstance(self.activation_trace, RegulationActivationTrace):
            raise FCRBidEvaluationValidationError(
                "activation_trace must be one RegulationActivationTrace"
            )
        if not isinstance(self.battery, BatteryComponent):
            raise FCRBidEvaluationValidationError(
                "battery must be one BatteryComponent"
            )
        if not isinstance(self.time_contract, MultiRateTimeContract):
            raise FCRBidEvaluationValidationError(
                "time_contract must be one MultiRateTimeContract"
            )
        if self.plan.energy_schedule.covered_period != self.plan.fcr_schedule.covered_period:
            raise FCRBidEvaluationValidationError(
                "plan schedules no longer cover the same period"
            )
        plan_period = self.plan.energy_schedule.covered_period
        if plan_period != self.market_context.period:
            raise FCRBidEvaluationValidationError(
                "plan schedule period must exactly match market context period"
            )
        if (
            plan_period.start_utc != self.time_contract.start_utc
            or plan_period.end_utc != self.time_contract.end_utc
        ):
            raise FCRBidEvaluationValidationError(
                "plan schedule period must exactly match time contract period"
            )
        activation_period = self.activation_trace.covered_period
        if (
            activation_period.start_utc != self.time_contract.start_utc
            or activation_period.end_utc != self.time_contract.end_utc
            or self.activation_trace.resolution
            != self.time_contract.activation_resolution
        ):
            raise FCRBidEvaluationValidationError(
                "activation coverage and resolution must match the evaluation period"
            )
        accepted_refs = set(self.market_context.accepted_bid_evidence)
        price_refs = {item.source_ref for item in self.market_context.fcr_capacity_prices}
        for index, commitment in enumerate(self.plan.fcr_schedule.intervals):
            if commitment.volume_observation_ref not in accepted_refs:
                raise FCRBidEvaluationValidationError(
                    f"plan FCR interval {index} accepted-bid reference is missing"
                )
            if commitment.price_observation_ref not in price_refs:
                raise FCRBidEvaluationValidationError(
                    f"plan FCR interval {index} price reference is missing"
                )
        if self.settlement_profile not in _SETTLEMENT_PROFILES:
            raise FCRBidEvaluationValidationError(
                "settlement_profile is not supported"
            )
        if self.terminal_soc_target is not None and not isinstance(
            self.terminal_soc_target, TerminalSOCTarget
        ):
            raise FCRBidEvaluationValidationError(
                "terminal_soc_target must be a TerminalSOCTarget or None"
            )
        tolerance = _finite(self.numeric_tolerance, field_name="numeric_tolerance")
        if tolerance <= 0.0:
            raise FCRBidEvaluationValidationError(
                "numeric_tolerance must be positive"
            )
        battery_fingerprint = _fingerprint(_battery_payload(self.battery))
        penalty_payload = (
            None
            if self.penalty_rule is None
            else self.penalty_rule.to_dict()
            if hasattr(self.penalty_rule, "to_dict")
            else repr(self.penalty_rule)
        )
        terminal_payload = (
            None
            if self.terminal_soc_target is None
            else self.terminal_soc_target.to_dict()
        )
        comparison_fingerprint = (
            None
            if self.comparison_fixture is None
            else getattr(self.comparison_fixture, "fixture_fingerprint", None)
        )
        if self.comparison_fixture is not None:
            comparison_fingerprint = _sha256(
                comparison_fingerprint,
                field_name="comparison fixture fingerprint",
            )
        input_fingerprints = _freeze(
            {
                "plan": self.plan.plan_fingerprint,
                "market_context": self.market_context.context_fingerprint,
                "activation_trace": self.activation_trace.artifact_fingerprint,
                "energy_schedule": self.plan.energy_schedule.schedule_fingerprint,
                "fcr_schedule": self.plan.fcr_schedule.schedule_fingerprint,
                "battery": battery_fingerprint,
                "time_contract": _fingerprint(self.time_contract.to_dict()),
                "settlement_profile": self.settlement_profile,
                "penalty_rule": (
                    None if penalty_payload is None else _fingerprint(penalty_payload)
                ),
                "terminal_soc_target": (
                    None if terminal_payload is None else _fingerprint(terminal_payload)
                ),
                "comparison_fixture": comparison_fingerprint,
                "numeric_tolerance": tolerance,
                "semantics_version": self.semantics_version,
            }
        )
        object.__setattr__(self, "numeric_tolerance", tolerance)
        object.__setattr__(self, "input_fingerprints", input_fingerprints)
        object.__setattr__(
            self,
            "evaluation_input_fingerprint",
            _fingerprint(_thaw(input_fingerprints)),
        )
        object.__setattr__(
            self,
            "_battery_fingerprint_at_binding",
            battery_fingerprint,
        )

    @property
    def energy_schedule(self) -> EnergyBaselineSchedule:
        return self.plan.energy_schedule

    @property
    def fcr_schedule(self) -> FCRCapacitySchedule:
        return self.plan.fcr_schedule

    def assert_battery_unchanged(self) -> None:
        if _fingerprint(_battery_payload(self.battery)) != self._battery_fingerprint_at_binding:
            raise FCRBidEvaluationValidationError(
                "battery mutated after evaluation request binding"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "semantics_version": self.semantics_version,
            "plan_fingerprint": self.plan.plan_fingerprint,
            "market_context_fingerprint": self.market_context.context_fingerprint,
            "input_fingerprints": _thaw(self.input_fingerprints),
            "evaluation_input_fingerprint": self.evaluation_input_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class DailyFCRBidEvaluationReport:
    evaluation_id: str
    status: str
    plan_id: str
    producer: Mapping[str, object]
    information_cutoff_utc: str
    diagnostics: tuple[EvaluationDiagnostic, ...]
    plan_fingerprint: str
    evaluation_input_fingerprint: str
    physical_trace: Mapping[str, object] | None
    physical_metrics: Mapping[str, object] | None
    settlement: Mapping[str, object] | None
    total_profit_eur: float | None
    trace_fingerprint: str | None
    settlement_fingerprint: str | None
    comparison_fingerprint: str | None
    schema_version: str = FCR_BID_EVALUATION_REPORT_SCHEMA_VERSION
    result_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != FCR_BID_EVALUATION_REPORT_SCHEMA_VERSION:
            raise FCRBidEvaluationValidationError(
                "unsupported FCR bid-evaluation report schema version"
            )
        if self.status not in {"settled", "validation_failed"}:
            raise FCRBidEvaluationValidationError(
                "report status must be settled or validation_failed"
            )
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, EvaluationDiagnostic) for item in diagnostics):
            raise FCRBidEvaluationValidationError(
                "report diagnostics must contain EvaluationDiagnostic values"
            )
        diagnostics = tuple(sorted(diagnostics, key=_diagnostic_sort_key))
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(
            self,
            "plan_fingerprint",
            _sha256(self.plan_fingerprint, field_name="plan_fingerprint"),
        )
        object.__setattr__(
            self,
            "evaluation_input_fingerprint",
            _sha256(
                self.evaluation_input_fingerprint,
                field_name="evaluation_input_fingerprint",
            ),
        )
        if self.status == "settled":
            if (
                self.physical_trace is None
                or self.physical_metrics is None
                or self.settlement is None
            ):
                raise FCRBidEvaluationValidationError(
                    "settled report requires physical trace, metrics, and settlement"
                )
            object.__setattr__(self, "physical_trace", _freeze(self.physical_trace))
            object.__setattr__(
                self,
                "physical_metrics",
                _freeze(self.physical_metrics),
            )
            object.__setattr__(self, "settlement", _freeze(self.settlement))
            object.__setattr__(
                self,
                "total_profit_eur",
                _finite(self.total_profit_eur, field_name="total_profit_eur"),
            )
            object.__setattr__(
                self,
                "trace_fingerprint",
                _sha256(self.trace_fingerprint, field_name="trace_fingerprint"),
            )
            object.__setattr__(
                self,
                "settlement_fingerprint",
                _sha256(
                    self.settlement_fingerprint,
                    field_name="settlement_fingerprint",
                ),
            )
        else:
            if any(
                item is not None
                for item in (
                    self.physical_metrics,
                    self.physical_trace,
                    self.settlement,
                    self.total_profit_eur,
                    self.trace_fingerprint,
                    self.settlement_fingerprint,
                    self.comparison_fingerprint,
                )
            ):
                raise FCRBidEvaluationValidationError(
                    "validation-failed report must omit trace, settlement, profit, and comparison"
                )
        if self.comparison_fingerprint is not None:
            object.__setattr__(
                self,
                "comparison_fingerprint",
                _sha256(
                    self.comparison_fingerprint,
                    field_name="comparison_fingerprint",
                ),
            )
        object.__setattr__(self, "producer", _freeze(self.producer))
        object.__setattr__(self, "result_fingerprint", _fingerprint(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evaluation_id": self.evaluation_id,
            "status": self.status,
            "plan_id": self.plan_id,
            "producer": _thaw(self.producer),
            "information_cutoff_utc": self.information_cutoff_utc,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "plan_fingerprint": self.plan_fingerprint,
            "evaluation_input_fingerprint": self.evaluation_input_fingerprint,
            "physical_trace": _thaw(self.physical_trace),
            "physical_metrics": _thaw(self.physical_metrics),
            "settlement": _thaw(self.settlement),
            "total_profit_eur": self.total_profit_eur,
            "trace_fingerprint": self.trace_fingerprint,
            "settlement_fingerprint": self.settlement_fingerprint,
            "comparison_fingerprint": self.comparison_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "result_fingerprint": self.result_fingerprint}

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


def _report_identity(request: FCRBidEvaluationRequest) -> dict[str, object]:
    return {
        "evaluation_id": request.evaluation_id,
        "plan_id": request.plan.plan_id,
        "producer": request.plan.producer.to_dict(),
        "information_cutoff_utc": request.plan.information_cutoff_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "plan_fingerprint": request.plan.plan_fingerprint,
        "evaluation_input_fingerprint": request.evaluation_input_fingerprint,
    }


def build_settled_evaluation_report(
    *,
    request: FCRBidEvaluationRequest,
    diagnostics: Sequence[EvaluationDiagnostic],
    physical_trace: Mapping[str, object],
    physical_metrics: Mapping[str, object],
    settlement: Mapping[str, object],
    total_profit_eur: float,
    trace_fingerprint: str,
    settlement_fingerprint: str,
    comparison_fingerprint: str | None,
) -> DailyFCRBidEvaluationReport:
    request.assert_battery_unchanged()
    return DailyFCRBidEvaluationReport(
        **_report_identity(request),
        status="settled",
        diagnostics=tuple(diagnostics),
        physical_trace=physical_trace,
        physical_metrics=physical_metrics,
        settlement=settlement,
        total_profit_eur=total_profit_eur,
        trace_fingerprint=trace_fingerprint,
        settlement_fingerprint=settlement_fingerprint,
        comparison_fingerprint=comparison_fingerprint,
    )


def build_validation_failed_evaluation_report(
    *,
    request: FCRBidEvaluationRequest,
    diagnostics: Sequence[EvaluationDiagnostic],
) -> DailyFCRBidEvaluationReport:
    return DailyFCRBidEvaluationReport(
        **_report_identity(request),
        status="validation_failed",
        diagnostics=tuple(diagnostics),
        physical_trace=None,
        physical_metrics=None,
        settlement=None,
        total_profit_eur=None,
        trace_fingerprint=None,
        settlement_fingerprint=None,
        comparison_fingerprint=None,
    )


def _schedule_fingerprint_matches(
    schedule: EnergyBaselineSchedule | FCRCapacitySchedule,
) -> bool:
    payload = schedule.to_dict()
    recorded = payload.pop("schedule_fingerprint")
    return recorded == _fingerprint(payload)


def _preflight_diagnostics(
    request: FCRBidEvaluationRequest,
) -> tuple[EvaluationDiagnostic, ...]:
    diagnostics: list[EvaluationDiagnostic] = []

    def reject(
        code: str,
        field_path: str,
        message: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> None:
        diagnostics.append(
            EvaluationDiagnostic(
                phase="preflight",
                code=code,
                severity="error",
                field_path=field_path,
                message=message,
                evidence_refs=evidence_refs,
            )
        )

    try:
        request.assert_battery_unchanged()
    except FCRBidEvaluationValidationError as exc:
        reject(
            "battery_mutated",
            "battery",
            str(exc),
            (request.input_fingerprints["battery"],),
        )
    if not _schedule_fingerprint_matches(request.energy_schedule):
        reject(
            "energy_schedule_fingerprint_mismatch",
            "plan.energy_schedule",
            "energy schedule semantic content does not match its fingerprint",
            (request.energy_schedule.schedule_fingerprint,),
        )
    if not _schedule_fingerprint_matches(request.fcr_schedule):
        reject(
            "fcr_schedule_fingerprint_mismatch",
            "plan.fcr_schedule",
            "FCR schedule semantic content does not match its fingerprint",
            (request.fcr_schedule.schedule_fingerprint,),
        )

    day_prices = request.market_context.day_ahead_prices
    if len(day_prices) != len(request.energy_schedule.intervals):
        reject(
            "day_ahead_price_count_mismatch",
            "market_context.day_ahead_prices",
            "day-ahead prices must align one-to-one with hourly schedule intervals",
        )
    else:
        for index, (schedule, price) in enumerate(
            zip(request.energy_schedule.intervals, day_prices, strict=True)
        ):
            if not _same_interval(schedule.interval, price.interval):
                reject(
                    "day_ahead_price_alignment_mismatch",
                    f"market_context.day_ahead_prices[{index}]",
                    "day-ahead price interval does not match the energy schedule",
                    (price.source_ref,),
                )
            if price.canonical_unit != "EUR/MWh":
                reject(
                    "day_ahead_price_unit_mismatch",
                    f"market_context.day_ahead_prices[{index}].canonical_unit",
                    "day-ahead price canonical unit must be EUR/MWh",
                    (price.source_ref,),
                )

    fcr_prices = request.market_context.fcr_capacity_prices
    if len(fcr_prices) != len(request.fcr_schedule.intervals):
        reject(
            "fcr_price_count_mismatch",
            "market_context.fcr_capacity_prices",
            "FCR prices must align one-to-one with four-hour commitments",
        )
    for index, commitment in enumerate(request.fcr_schedule.intervals):
        evidence = request.market_context.accepted_bid_evidence.get(
            commitment.volume_observation_ref
        )
        if not isinstance(evidence, Mapping):
            reject(
                "accepted_bid_evidence_invalid",
                f"market_context.accepted_bid_evidence[{commitment.volume_observation_ref}]",
                "accepted-bid evidence must be an explicit mapping",
                (commitment.volume_observation_ref,),
            )
        else:
            try:
                if "capacity_kw" in evidence:
                    accepted_kw = _finite(
                        evidence["capacity_kw"],
                        field_name="accepted FCR capacity_kw",
                    )
                    if abs(accepted_kw - commitment.capacity_kw) > request.numeric_tolerance:
                        reject(
                            "accepted_bid_capacity_mismatch",
                            f"plan.fcr_schedule.intervals[{index}].capacity_kw",
                            "reference-result accepted capacity must equal the commitment",
                            (commitment.volume_observation_ref,),
                        )
                elif evidence.get("unit") == "MW" and "value" in evidence:
                    limit_kw = _finite(
                        evidence["value"],
                        field_name="accepted market volume",
                    ) * 1000.0
                    if commitment.capacity_kw > limit_kw + request.numeric_tolerance:
                        reject(
                            "accepted_bid_exceeds_market_volume",
                            f"plan.fcr_schedule.intervals[{index}].capacity_kw",
                            "FCR commitment exceeds observed accepted market volume",
                            (commitment.volume_observation_ref,),
                        )
                else:
                    reject(
                        "accepted_bid_evidence_semantics_missing",
                        f"market_context.accepted_bid_evidence[{commitment.volume_observation_ref}]",
                        "accepted-bid evidence must declare capacity_kw or an MW market volume",
                        (commitment.volume_observation_ref,),
                    )
            except FCRBidEvaluationValidationError as exc:
                reject(
                    "accepted_bid_evidence_nonfinite",
                    f"market_context.accepted_bid_evidence[{commitment.volume_observation_ref}]",
                    str(exc),
                    (commitment.volume_observation_ref,),
                )
        if index < len(fcr_prices):
            price = fcr_prices[index]
            if (
                not _same_interval(commitment.interval, price.interval)
                or commitment.price_observation_ref != price.source_ref
            ):
                reject(
                    "fcr_price_alignment_mismatch",
                    f"market_context.fcr_capacity_prices[{index}]",
                    "FCR price interval/reference does not match the commitment",
                    (commitment.price_observation_ref, price.source_ref),
                )
            if price.canonical_unit not in {"EUR/kW/block", "EUR/MW/h"}:
                reject(
                    "fcr_price_unit_mismatch",
                    f"market_context.fcr_capacity_prices[{index}].canonical_unit",
                    "FCR price canonical unit must be EUR/kW/block or EUR/MW/h",
                    (price.source_ref,),
                )

        for energy_index, baseline in enumerate(request.energy_schedule.intervals):
            if (
                baseline.interval.start_utc >= commitment.interval.start_utc
                and baseline.interval.end_utc <= commitment.interval.end_utc
            ):
                if (
                    baseline.power_kw + commitment.capacity_kw
                    > request.battery.max_charge_kw + request.numeric_tolerance
                ):
                    reject(
                        "charge_power_headroom_insufficient",
                        f"plan.energy_schedule.intervals[{energy_index}].power_kw",
                        "accepted commitment lacks charge power headroom",
                        (f"fcr:{index}",),
                    )
                if (
                    baseline.power_kw - commitment.capacity_kw
                    < -request.battery.max_discharge_kw - request.numeric_tolerance
                ):
                    reject(
                        "discharge_power_headroom_insufficient",
                        f"plan.energy_schedule.intervals[{energy_index}].power_kw",
                        "accepted commitment lacks discharge power headroom",
                        (f"fcr:{index}",),
                    )

    if request.settlement_profile != REFERENCE_SETTLEMENT_PROFILE:
        reject(
            "unsupported_common_evaluator_settlement_profile",
            "settlement_profile",
            "the common evaluator currently requires the explicit reference settlement profile",
            (request.settlement_profile,),
        )
    if diagnostics:
        return tuple(sorted(diagnostics, key=_diagnostic_sort_key))
    return (
        EvaluationDiagnostic(
            phase="preflight",
            code="preflight_valid",
            severity="info",
            field_path=None,
            message="fixed plan passed deterministic accepted-commitment preflight",
            evidence_refs=(
                request.plan.plan_fingerprint,
                request.market_context.context_fingerprint,
            ),
        ),
    )


def _directional_fcr_energy(
    samples: Sequence[object],
    *,
    power_field: str,
) -> dict[str, float]:
    upward = 0.0
    downward = 0.0
    for sample in samples:
        power = float(getattr(sample, power_field))
        duration = (
            sample.interval.end_utc - sample.interval.start_utc
        ).total_seconds() / 3600.0
        upward += max(-power, 0.0) * duration
        downward += max(power, 0.0) * duration
    return {
        "upward_discharge": upward,
        "downward_charge": downward,
        "signed_net_charge_positive": downward - upward,
    }


def _physical_trace_payload(physical: object) -> dict[str, object]:
    return {
        "samples": [sample.to_dict() for sample in physical.samples],
        "state_checkpoints": [
            item.to_dict() for item in physical.state_checkpoints
        ],
        "checkpoint_summaries": [
            item.to_dict() for item in physical.checkpoint_summaries
        ],
        "energy_summaries": [item.to_dict() for item in physical.energy_summaries],
        "fcr_summaries": [item.to_dict() for item in physical.fcr_summaries],
        "saturation_events": [
            item.to_dict() for item in physical.saturation_events
        ],
    }


def _daily_physical_metrics(
    request: FCRBidEvaluationRequest,
    physical: object,
) -> dict[str, object]:
    samples = physical.samples
    stored_values = [physical.state_checkpoints[0].stored_energy_kwh] + [
        sample.stored_energy_after_kwh for sample in samples
    ]
    requested_powers = [sample.requested_combined_power_kw for sample in samples]
    delivered_powers = [sample.delivered_combined_power_kw for sample in samples]
    charge_energy = sum(sample.charge_energy_kwh for sample in samples)
    discharge_energy = sum(sample.discharge_energy_kwh for sample in samples)
    capacity = request.battery.capacity_kwh
    return {
        "interval_counts": {
            "activation": len(samples),
            "checkpoint": len(request.time_contract.index.checkpoint_intervals),
            "energy": len(request.energy_schedule.intervals),
            "fcr": len(request.fcr_schedule.intervals),
        },
        "stored_energy_kwh": {
            "initial": stored_values[0],
            "minimum": min(stored_values),
            "maximum": max(stored_values),
            "terminal": stored_values[-1],
        },
        "soc_fraction": {
            "initial": stored_values[0] / capacity,
            "minimum": min(stored_values) / capacity,
            "maximum": max(stored_values) / capacity,
            "terminal": stored_values[-1] / capacity,
        },
        "requested_power_kw": {
            "minimum": min(requested_powers),
            "maximum": max(requested_powers),
        },
        "delivered_power_kw": {
            "minimum": min(delivered_powers),
            "maximum": max(delivered_powers),
        },
        "requested_fcr_energy_kwh": _directional_fcr_energy(
            samples,
            power_field="requested_fcr_power_kw",
        ),
        "delivered_fcr_energy_kwh": _directional_fcr_energy(
            samples,
            power_field="delivered_fcr_power_kw",
        ),
        "charge_energy_kwh": charge_energy,
        "discharge_energy_kwh": discharge_energy,
        "throughput_kwh": charge_energy + discharge_energy,
        "signed_tracking_error_kw_sum": physical.tracking_summary[
            "signed_tracking_error_kw_sum"
        ],
        "absolute_tracking_error_kw_sum": physical.tracking_summary[
            "absolute_tracking_error_kw_sum"
        ],
        "non_delivery_energy_kwh": physical.tracking_summary[
            "non_delivery_energy_kwh"
        ],
        "saturation_sample_count": physical.tracking_summary[
            "saturation_sample_count"
        ],
        "saturation_duration_hours": physical.tracking_summary[
            "saturation_duration_hours"
        ],
        "saturation_event_count": physical.tracking_summary[
            "saturation_event_count"
        ],
        "physical_limit_diagnostics": [
            {
                "event_id": event.event_id,
                "cause": event.cause,
                "sample_count": event.sample_count,
                "undelivered_energy_kwh": event.undelivered_energy_kwh,
            }
            for event in physical.saturation_events
        ],
    }


def evaluate_fixed_fcr_bid(
    request: FCRBidEvaluationRequest,
) -> DailyFCRBidEvaluationReport:
    """Evaluate a frozen bid plan without inspecting how the schedules were made."""

    if not isinstance(request, FCRBidEvaluationRequest):
        raise FCRBidEvaluationValidationError(
            "request must be one FCRBidEvaluationRequest"
        )
    diagnostics = _preflight_diagnostics(request)
    if any(item.severity == "error" for item in diagnostics):
        return build_validation_failed_evaluation_report(
            request=request,
            diagnostics=diagnostics,
        )

    from .fcr_settlement import settle_reference_fcr_bid
    from .stacked_service import _PhysicalReplayInputs, _replay_physical_kernel

    physical = _replay_physical_kernel(
        _PhysicalReplayInputs(
            activation_trace=request.activation_trace,
            battery=request.battery,
            energy_schedule=request.energy_schedule,
            fcr_schedule=request.fcr_schedule,
            time_contract=request.time_contract,
            numeric_tolerance=request.numeric_tolerance,
            terminal_soc_target=request.terminal_soc_target,
        )
    )
    physical_trace = _physical_trace_payload(physical)
    trace_fingerprint = _fingerprint(physical_trace)
    settlement = settle_reference_fcr_bid(request, physical.samples)
    return build_settled_evaluation_report(
        request=request,
        diagnostics=diagnostics,
        physical_trace=physical_trace,
        physical_metrics=_daily_physical_metrics(request, physical),
        settlement=settlement.to_dict(),
        total_profit_eur=settlement.total_profit_eur,
        trace_fingerprint=trace_fingerprint,
        settlement_fingerprint=settlement.settlement_fingerprint,
        comparison_fingerprint=None,
    )


__all__ = [
    "ComponentAvailability",
    "DailyFCRBidEvaluationReport",
    "EvaluationDiagnostic",
    "EvaluationMarketContext",
    "EvaluationPriceObservation",
    "FCRBidEvaluationRequest",
    "FCRBidEvaluationValidationError",
    "FCR_BID_EVALUATION_REPORT_SCHEMA_VERSION",
    "FCR_BID_EVALUATION_SEMANTICS_VERSION",
    "FEATURE_010_DEFAULT_SETTLEMENT_PROFILE",
    "REFERENCE_SETTLEMENT_PROFILE",
    "build_feature_010_market_context",
    "build_settled_evaluation_report",
    "build_validation_failed_evaluation_report",
    "canonical_json_bytes",
    "evaluate_fixed_fcr_bid",
]
