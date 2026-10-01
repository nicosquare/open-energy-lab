"""Source-independent inputs and immutable reports for fixed FCR bid evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Protocol
import math

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import (
    canonical_json_bytes as _canonical_json_bytes,
    fingerprint,
    freeze,
    thaw,
)
from open_energy_lab.core.validation import finite, non_empty_str, sha256_digest
from .fcr_bid_plan import FixedFCRBidPlan
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
STACKED_SERVICE_SETTLEMENT_PROFILE = "stacked-service-default-v1"
REFERENCE_SETTLEMENT_PROFILE = "robust-storage-bidding-reference-settlement-v1"

_CONTEXT_KINDS = {
    "accepted_plan",
    "market_artifact",
    "reference_result",
}
_SETTLEMENT_PROFILES = {
    STACKED_SERVICE_SETTLEMENT_PROFILE,
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


class FCRBidEvaluationValidationError(ValidationError):
    """Raised when evaluation inputs or immutable report shapes are invalid."""


class EvaluationComparison(Protocol):
    """Result of comparing one evaluation with an external reference."""

    overall_status: str
    comparison_fingerprint: str

    def to_dict(self) -> dict[str, object]: ...


class EvaluationComparisonFixture(Protocol):
    """Optional request extension: compare the settled evaluation with a reference.

    The library ships no implementation. ``oel_validation.reference_fcr``
    provides one for the pinned robust-storage-bidding case.
    """

    fixture_fingerprint: str

    def compare(
        self,
        *,
        actual_values: Mapping[str, float],
        activation_trace: RegulationActivationTrace,
    ) -> EvaluationComparison: ...

    def domain_unavailable(self, *, reason: str) -> EvaluationComparison: ...


_non_empty = partial(non_empty_str, error=FCRBidEvaluationValidationError, strip=True)
_finite = partial(finite, error=FCRBidEvaluationValidationError)
_sha256 = partial(sha256_digest, error=FCRBidEvaluationValidationError)
_freeze = partial(freeze, sort_keys=True)
_thaw = thaw


def canonical_json_bytes(value: object) -> bytes:
    """Return the compact, sorted, finite JSON representation used by fingerprints."""

    return _canonical_json_bytes(value, error=FCRBidEvaluationValidationError)


_fingerprint = partial(fingerprint, error=FCRBidEvaluationValidationError)


def _same_interval(left: CanonicalInterval, right: CanonicalInterval) -> bool:
    return (
        left.start_utc == right.start_utc
        and left.end_utc == right.end_utc
    )


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

    def __post_init__(self) -> None:
        if self.context_kind not in _CONTEXT_KINDS:
            raise FCRBidEvaluationValidationError(
                "context kind must be accepted_plan, market_artifact, "
                "or reference_result"
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

    def to_dict(self) -> dict[str, object]:
        return {
            "context_kind": self.context_kind,
            "semantics_version": self.semantics_version,
            "period": self.period.to_dict(),
            "day_ahead_prices": [item.to_dict() for item in self.day_ahead_prices],
            "fcr_capacity_prices": [item.to_dict() for item in self.fcr_capacity_prices],
            "accepted_bid_evidence": _thaw(self.accepted_bid_evidence),
            "source_fingerprints": _thaw(self.source_fingerprints),
        }


def _observations_within_period(series: object, period: CanonicalInterval) -> tuple[object, ...]:
    return tuple(
        observation
        for observation in series.observations
        if observation.interval.start_utc >= period.start_utc
        and observation.interval.end_utc <= period.end_utc
    )


def build_market_data_context(
    *,
    market_artifact: MarketDataArtifact,
    period: CanonicalInterval,
) -> EvaluationMarketContext:
    """Copy validated market-data artifact observations into a source-independent view."""

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
            "market-data artifact does not contain the market-context period"
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
            conversion_id="market-artifact-canonical-identity-v1",
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
            conversion_id="market-artifact-canonical-identity-v1",
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
        context_kind="market_artifact",
        semantics_version="market-artifact-context-v1",
        period=period,
        day_ahead_prices=day_prices,
        fcr_capacity_prices=fcr_prices,
        accepted_bid_evidence=accepted,
        source_fingerprints={"market_artifact": market_artifact.artifact_fingerprint},
    )


def _accepted_policy_payload(acceptance_policy: object) -> dict[str, object]:
    if isinstance(acceptance_policy, Mapping):
        payload = {str(key): value for key, value in acceptance_policy.items()}
    elif hasattr(acceptance_policy, "to_dict"):
        raw = acceptance_policy.to_dict()
        if not isinstance(raw, Mapping):
            raise FCRBidEvaluationValidationError(
                "acceptance policy to_dict() must return a mapping"
            )
        payload = {str(key): value for key, value in raw.items()}
    else:
        raise FCRBidEvaluationValidationError(
            "acceptance_policy must be a validated accepted-bid policy"
        )
    expected_fingerprint = _sha256(
        payload.get("policy_fingerprint"),
        field_name="acceptance policy fingerprint",
    )
    semantic_payload = {
        key: value for key, value in payload.items() if key != "policy_fingerprint"
    }
    if _fingerprint(semantic_payload) != expected_fingerprint:
        raise FCRBidEvaluationValidationError(
            "acceptance policy fingerprint does not match its semantic content"
        )
    policy_id = _non_empty(payload.get("policy_id"), field_name="acceptance policy_id")
    kind = payload.get("kind")
    if kind not in {"assumed_accepted", "evidence_backed_accepted"}:
        raise FCRBidEvaluationValidationError(
            "acceptance policy kind must be assumed_accepted or evidence_backed_accepted"
        )
    if payload.get("reject_system_volume_as_individual_evidence") is not True:
        raise FCRBidEvaluationValidationError(
            "acceptance policy must reject system-wide volume as individual acceptance"
        )
    normalized = {
        **semantic_payload,
        "policy_id": policy_id,
        "kind": kind,
        "policy_fingerprint": expected_fingerprint,
    }
    if kind == "assumed_accepted":
        normalized["assumption_statement"] = _non_empty(
            payload.get("assumption_statement"),
            field_name="accepted-bid assumption statement",
        )
        if payload.get("evidence_descriptor") is not None:
            raise FCRBidEvaluationValidationError(
                "assumed acceptance must not claim observed award evidence"
            )
    else:
        descriptor = payload.get("evidence_descriptor")
        if not isinstance(descriptor, Mapping):
            raise FCRBidEvaluationValidationError(
                "evidence-backed acceptance requires an individual award descriptor"
            )
        descriptor_kind = descriptor.get("kind")
        if descriptor_kind == "system_wide_contracted_reserve_volume":
            raise FCRBidEvaluationValidationError(
                "system-wide contracted reserve volume is not individual acceptance evidence"
            )
        if descriptor_kind != "individual_bid_award":
            raise FCRBidEvaluationValidationError(
                "evidence-backed acceptance requires individual acceptance evidence"
            )
        _sha256(
            descriptor.get("content_fingerprint"),
            field_name="individual award descriptor content_fingerprint",
        )
        normalized["evidence_descriptor"] = dict(descriptor)
    return normalized


def build_accepted_plan_market_context(
    *,
    plan: FixedFCRBidPlan,
    period: CanonicalInterval,
    day_ahead_prices_eur_per_kwh: Sequence[float],
    fcr_capacity_prices_eur_per_kw_block: Sequence[float],
    acceptance_policy: object,
    source_fingerprints: Mapping[str, str],
) -> EvaluationMarketContext:
    """Bind explicit individual-plan acceptance and converted settlement prices."""

    if not isinstance(plan, FixedFCRBidPlan):
        raise FCRBidEvaluationValidationError("plan must be one FixedFCRBidPlan")
    if not isinstance(period, CanonicalInterval):
        raise FCRBidEvaluationValidationError("period must be a CanonicalInterval")
    plan_period = plan.energy_schedule.covered_period
    if (
        period.start_utc < plan_period.start_utc
        or period.end_utc > plan_period.end_utc
    ):
        raise FCRBidEvaluationValidationError(
            "accepted-plan market period must remain inside the plan period"
        )
    energy_intervals = tuple(
        item
        for item in plan.energy_schedule.intervals
        if item.interval.start_utc >= period.start_utc
        and item.interval.end_utc <= period.end_utc
    )
    fcr_intervals = tuple(
        item
        for item in plan.fcr_schedule.intervals
        if item.interval.start_utc >= period.start_utc
        and item.interval.end_utc <= period.end_utc
    )
    if (
        not energy_intervals
        or energy_intervals[0].interval.start_utc != period.start_utc
        or energy_intervals[-1].interval.end_utc != period.end_utc
    ):
        raise FCRBidEvaluationValidationError(
            "accepted-plan period must have exact hourly schedule coverage"
        )
    if (
        not fcr_intervals
        or fcr_intervals[0].interval.start_utc != period.start_utc
        or fcr_intervals[-1].interval.end_utc != period.end_utc
    ):
        raise FCRBidEvaluationValidationError(
            "accepted-plan period must have exact four-hour FCR coverage"
        )
    day_values = tuple(day_ahead_prices_eur_per_kwh)
    fcr_values = tuple(fcr_capacity_prices_eur_per_kw_block)
    if len(day_values) != len(energy_intervals):
        raise FCRBidEvaluationValidationError(
            "day-ahead prices must match accepted hourly plan coverage"
        )
    if len(fcr_values) != len(fcr_intervals):
        raise FCRBidEvaluationValidationError(
            "FCR prices must match accepted four-hour plan coverage"
        )
    policy = _accepted_policy_payload(acceptance_policy)
    day_prices = tuple(
        EvaluationPriceObservation(
            interval=item.interval,
            price_kind="day_ahead_energy",
            source_value=_finite(value, field_name=f"day-ahead price {index}"),
            source_unit="EUR/kWh",
            canonical_value=(
                1000.0 * _finite(value, field_name=f"day-ahead price {index}")
            ),
            canonical_unit="EUR/MWh",
            conversion_id="eur-per-kwh-to-eur-per-mwh-times-1000-v1",
            source_ref=f"accepted_plan_day_ahead_price:{index}",
        )
        for index, (item, value) in enumerate(
            zip(energy_intervals, day_values, strict=True)
        )
    )
    fcr_prices = tuple(
        EvaluationPriceObservation(
            interval=item.interval,
            price_kind="fcr_capacity",
            source_value=_finite(value, field_name=f"FCR capacity price {index}"),
            source_unit="EUR/kW/block",
            canonical_value=_finite(value, field_name=f"FCR capacity price {index}"),
            canonical_unit="EUR/kW/block",
            conversion_id="accepted-plan-fcr-block-price-identity-v1",
            source_ref=item.price_observation_ref,
        )
        for index, (item, value) in enumerate(
            zip(fcr_intervals, fcr_values, strict=True)
        )
    )
    evidence_kind = str(policy["kind"])
    accepted = {
        item.volume_observation_ref: {
            "capacity_kw": item.capacity_kw,
            "unit": "kW",
            "evidence_kind": evidence_kind,
            "plan_fingerprint": plan.plan_fingerprint,
            "acceptance_policy_id": policy["policy_id"],
            "acceptance_policy_fingerprint": policy["policy_fingerprint"],
            "evidence_descriptor": policy.get("evidence_descriptor"),
            "assumption_statement": policy.get("assumption_statement"),
        }
        for item in fcr_intervals
    }
    if not isinstance(source_fingerprints, Mapping):
        raise FCRBidEvaluationValidationError(
            "source_fingerprints must be a mapping"
        )
    combined_sources = {
        **{str(key): value for key, value in source_fingerprints.items()},
        "accepted_plan": plan.plan_fingerprint,
        "acceptance_policy": str(policy["policy_fingerprint"]),
    }
    return EvaluationMarketContext(
        context_kind="accepted_plan",
        semantics_version="accepted-plan-market-context-v1",
        period=period,
        day_ahead_prices=day_prices,
        fcr_capacity_prices=fcr_prices,
        accepted_bid_evidence=accepted,
        source_fingerprints=combined_sources,
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
    comparison_fixture: EvaluationComparisonFixture | None
    numeric_tolerance: float
    semantics_version: str = FCR_BID_EVALUATION_SEMANTICS_VERSION
    _battery_at_binding: Mapping[str, object] = field(init=False, repr=False, compare=False)

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
        object.__setattr__(self, "numeric_tolerance", tolerance)
        object.__setattr__(self, "_battery_at_binding", self.battery.to_dict())

    @property
    def energy_schedule(self) -> EnergyBaselineSchedule:
        return self.plan.energy_schedule

    @property
    def fcr_schedule(self) -> FCRCapacitySchedule:
        return self.plan.fcr_schedule

    def assert_battery_unchanged(self) -> None:
        if self.battery.to_dict() != self._battery_at_binding:
            raise FCRBidEvaluationValidationError(
                "battery mutated after evaluation request binding"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "semantics_version": self.semantics_version,
            "plan_fingerprint": self.plan.plan_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class DailyFCRBidEvaluationReport:
    evaluation_id: str
    status: str
    plan_id: str
    producer: Mapping[str, object]
    information_cutoff_utc: str
    schedule_identity: Mapping[str, object]
    optimization_metadata: Mapping[str, object]
    diagnostics: tuple[EvaluationDiagnostic, ...]
    plan_fingerprint: str
    physical_trace: Mapping[str, object] | None
    physical_metrics: Mapping[str, object] | None
    settlement: Mapping[str, object] | None
    total_profit_eur: float | None
    comparison: Mapping[str, object] | None
    schema_version: str = FCR_BID_EVALUATION_REPORT_SCHEMA_VERSION

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
        object.__setattr__(self, "schedule_identity", _freeze(self.schedule_identity))
        object.__setattr__(
            self,
            "optimization_metadata",
            _freeze(self.optimization_metadata),
        )
        object.__setattr__(
            self,
            "plan_fingerprint",
            _sha256(self.plan_fingerprint, field_name="plan_fingerprint"),
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
            if self.comparison is not None:
                object.__setattr__(self, "comparison", _freeze(self.comparison))
            object.__setattr__(
                self,
                "total_profit_eur",
                _finite(self.total_profit_eur, field_name="total_profit_eur"),
            )
        else:
            if any(
                item is not None
                for item in (
                    self.physical_metrics,
                    self.physical_trace,
                    self.settlement,
                    self.total_profit_eur,
                    self.comparison,
                )
            ):
                raise FCRBidEvaluationValidationError(
                    "validation-failed report must omit trace, settlement, profit, and comparison"
                )
        object.__setattr__(self, "producer", _freeze(self.producer))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evaluation_id": self.evaluation_id,
            "status": self.status,
            "plan_id": self.plan_id,
            "producer": _thaw(self.producer),
            "information_cutoff_utc": self.information_cutoff_utc,
            "schedule_identity": _thaw(self.schedule_identity),
            "optimization_metadata": _thaw(self.optimization_metadata),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "plan_fingerprint": self.plan_fingerprint,
            "physical_trace": _thaw(self.physical_trace),
            "physical_metrics": _thaw(self.physical_metrics),
            "settlement": _thaw(self.settlement),
            "total_profit_eur": self.total_profit_eur,
            "comparison": _thaw(self.comparison),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True, slots=True)
class InvalidCommitmentDiagnosticReport:
    """Explicitly non-economic replay of a statically invalid commitment."""

    evaluation_id: str
    plan_id: str
    producer: Mapping[str, object]
    information_cutoff_utc: str
    schedule_identity: Mapping[str, object]
    optimization_metadata: Mapping[str, object]
    diagnostics: tuple[EvaluationDiagnostic, ...]
    physical_trace: Mapping[str, object]
    physical_metrics: Mapping[str, object]
    status: str = "invalid_commitment_diagnostic"
    settlement: None = field(default=None, init=False)
    total_profit_eur: None = field(default=None, init=False)
    comparison: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.status != "invalid_commitment_diagnostic":
            raise FCRBidEvaluationValidationError(
                "diagnostic report status must be invalid_commitment_diagnostic"
            )
        diagnostics = tuple(sorted(self.diagnostics, key=_diagnostic_sort_key))
        if not diagnostics or any(item.severity != "error" for item in diagnostics):
            raise FCRBidEvaluationValidationError(
                "invalid commitment diagnostic requires preflight errors"
            )
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "producer", _freeze(self.producer))
        object.__setattr__(self, "schedule_identity", _freeze(self.schedule_identity))
        object.__setattr__(
            self,
            "optimization_metadata",
            _freeze(self.optimization_metadata),
        )
        object.__setattr__(self, "physical_trace", _freeze(self.physical_trace))
        object.__setattr__(self, "physical_metrics", _freeze(self.physical_metrics))

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "status": self.status,
            "plan_id": self.plan_id,
            "producer": _thaw(self.producer),
            "information_cutoff_utc": self.information_cutoff_utc,
            "schedule_identity": _thaw(self.schedule_identity),
            "optimization_metadata": _thaw(self.optimization_metadata),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "physical_trace": _thaw(self.physical_trace),
            "physical_metrics": _thaw(self.physical_metrics),
            "settlement": None,
            "total_profit_eur": None,
            "comparison": None,
        }


def _report_identity(request: FCRBidEvaluationRequest) -> dict[str, object]:
    return {
        "evaluation_id": request.evaluation_id,
        "plan_id": request.plan.plan_id,
        "producer": request.plan.producer.to_dict(),
        "information_cutoff_utc": request.plan.information_cutoff_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "schedule_identity": {
            "energy": request.plan.energy_schedule_ref.to_dict(),
            "fcr": request.plan.fcr_schedule_ref.to_dict(),
        },
        "optimization_metadata": {
            "solve_status": request.plan.solve_status,
            "objective": request.plan.objective.to_dict(),
            "objective_bound": request.plan.objective_bound.to_dict(),
        },
        "plan_fingerprint": request.plan.plan_fingerprint,
    }


def build_settled_evaluation_report(
    *,
    request: FCRBidEvaluationRequest,
    diagnostics: Sequence[EvaluationDiagnostic],
    physical_trace: Mapping[str, object],
    physical_metrics: Mapping[str, object],
    settlement: Mapping[str, object],
    total_profit_eur: float,
    comparison: Mapping[str, object] | None,
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
        comparison=comparison,
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
        comparison=None,
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

    # Both schedules are already validated as ordered, complete, and aligned.
    # Combine hourly price and headroom checks so fingerprint verification plus
    # this loop are the only two complete energy-schedule passes.
    fcr_index = 0
    commitments = request.fcr_schedule.intervals
    for energy_index, baseline in enumerate(request.energy_schedule.intervals):
        if len(day_prices) == len(request.energy_schedule.intervals):
            price = day_prices[energy_index]
            if not _same_interval(baseline.interval, price.interval):
                reject(
                    "day_ahead_price_alignment_mismatch",
                    f"market_context.day_ahead_prices[{energy_index}]",
                    "day-ahead price interval does not match the energy schedule",
                    (price.source_ref,),
                )
            if price.canonical_unit != "EUR/MWh":
                reject(
                    "day_ahead_price_unit_mismatch",
                    f"market_context.day_ahead_prices[{energy_index}].canonical_unit",
                    "day-ahead price canonical unit must be EUR/MWh",
                    (price.source_ref,),
                )
        while (
            fcr_index + 1 < len(commitments)
            and baseline.interval.start_utc >= commitments[fcr_index].interval.end_utc
        ):
            fcr_index += 1
        commitment = commitments[fcr_index]
        if (
            baseline.power_kw + commitment.capacity_kw
            > request.battery.max_charge_kw + request.numeric_tolerance
        ):
            reject(
                "charge_power_headroom_insufficient",
                f"plan.energy_schedule.intervals[{energy_index}].power_kw",
                "accepted commitment lacks charge power headroom",
                (f"fcr:{fcr_index}",),
            )
        if (
            baseline.power_kw - commitment.capacity_kw
            < -request.battery.max_discharge_kw - request.numeric_tolerance
        ):
            reject(
                "discharge_power_headroom_insufficient",
                f"plan.energy_schedule.intervals[{energy_index}].power_kw",
                "accepted commitment lacks discharge power headroom",
                (f"fcr:{fcr_index}",),
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
            evidence_refs=(request.plan.plan_fingerprint,),
        ),
    )


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
    initial_stored = physical.state_checkpoints[0].stored_energy_kwh
    minimum_stored = initial_stored
    maximum_stored = initial_stored
    terminal_stored = initial_stored
    minimum_requested = math.inf
    maximum_requested = -math.inf
    minimum_delivered = math.inf
    maximum_delivered = -math.inf
    requested_upward = 0.0
    requested_downward = 0.0
    delivered_upward = 0.0
    delivered_downward = 0.0
    energy_values: list[tuple[float, float]] = []
    for sample in samples:
        terminal_stored = sample.stored_energy_after_kwh
        minimum_stored = min(minimum_stored, terminal_stored)
        maximum_stored = max(maximum_stored, terminal_stored)
        minimum_requested = min(
            minimum_requested,
            sample.requested_combined_power_kw,
        )
        maximum_requested = max(
            maximum_requested,
            sample.requested_combined_power_kw,
        )
        minimum_delivered = min(
            minimum_delivered,
            sample.delivered_combined_power_kw,
        )
        maximum_delivered = max(
            maximum_delivered,
            sample.delivered_combined_power_kw,
        )
        duration = (
            sample.interval.end_utc - sample.interval.start_utc
        ).total_seconds() / 3600.0
        requested_upward += max(-sample.requested_fcr_power_kw, 0.0) * duration
        requested_downward += max(sample.requested_fcr_power_kw, 0.0) * duration
        delivered_upward += max(-sample.delivered_fcr_power_kw, 0.0) * duration
        delivered_downward += max(sample.delivered_fcr_power_kw, 0.0) * duration
        energy_values.append(
            (sample.charge_energy_kwh, sample.discharge_energy_kwh)
        )
    charge_energy = sum(item[0] for item in energy_values)
    discharge_energy = sum(item[1] for item in energy_values)
    capacity = request.battery.capacity_kwh
    return {
        "interval_counts": {
            "activation": len(samples),
            "checkpoint": len(request.time_contract.index.checkpoint_intervals),
            "energy": len(request.energy_schedule.intervals),
            "fcr": len(request.fcr_schedule.intervals),
        },
        "stored_energy_kwh": {
            "initial": initial_stored,
            "minimum": minimum_stored,
            "maximum": maximum_stored,
            "terminal": terminal_stored,
        },
        "soc_fraction": {
            "initial": initial_stored / capacity,
            "minimum": minimum_stored / capacity,
            "maximum": maximum_stored / capacity,
            "terminal": terminal_stored / capacity,
        },
        "requested_power_kw": {
            "minimum": minimum_requested,
            "maximum": maximum_requested,
        },
        "delivered_power_kw": {
            "minimum": minimum_delivered,
            "maximum": maximum_delivered,
        },
        "requested_fcr_energy_kwh": {
            "upward_discharge": requested_upward,
            "downward_charge": requested_downward,
            "signed_net_charge_positive": requested_downward - requested_upward,
        },
        "delivered_fcr_energy_kwh": {
            "upward_discharge": delivered_upward,
            "downward_charge": delivered_downward,
            "signed_net_charge_positive": delivered_downward - delivered_upward,
        },
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


def _reference_actual_values(
    request: FCRBidEvaluationRequest,
    physical_metrics: Mapping[str, object],
    settlement: object,
) -> dict[str, float]:
    stored = physical_metrics["stored_energy_kwh"]
    delivered_power = physical_metrics["delivered_power_kw"]
    values = {
        "settlement.total_profit_eur": settlement.total_profit_eur,
        "settlement.day_ahead_revenue_eur": settlement.day_ahead_revenue.value_eur,
        "settlement.combined_fcr_revenue_eur": (
            settlement.fcr_capacity_revenue.value_eur
            + settlement.activation_energy_revenue.value_eur
        ),
        "physical.initial_stored_energy_kwh": stored["initial"],
        "physical.minimum_stored_energy_kwh": stored["minimum"],
        "physical.maximum_stored_energy_kwh": stored["maximum"],
        "physical.terminal_stored_energy_kwh": stored["terminal"],
        "physical.charge_energy_kwh": physical_metrics["charge_energy_kwh"],
        "physical.discharge_energy_kwh": physical_metrics["discharge_energy_kwh"],
        "physical.maximum_delivered_power_kw": delivered_power["maximum"],
        "physical.minimum_delivered_power_kw": delivered_power["minimum"],
    }
    if request.plan.objective.availability == "available":
        values["plan.objective"] = request.plan.objective.value
    if request.plan.objective_bound.availability == "available":
        values["plan.objective_bound"] = request.plan.objective_bound.value
    return values


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

    from .fcr_settlement import settle_fixed_fcr_bid
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
    settlement = settle_fixed_fcr_bid(request, physical.samples)
    physical_metrics = _daily_physical_metrics(request, physical)
    comparison = None
    if request.comparison_fixture is not None:
        if (
            physical_metrics["saturation_event_count"] > 0
            or physical_metrics["non_delivery_energy_kwh"]
            > request.numeric_tolerance
        ):
            comparison = request.comparison_fixture.domain_unavailable(
                reason=(
                    "dynamic saturation or non-delivery is outside the declared "
                    "no-curtailment reference parity domain"
                ),
            )
        else:
            comparison = request.comparison_fixture.compare(
                actual_values=_reference_actual_values(
                    request,
                    physical_metrics,
                    settlement,
                ),
                activation_trace=request.activation_trace,
            )
        diagnostics = (
            *diagnostics,
            EvaluationDiagnostic(
                phase="comparison",
                code=f"reference_comparison_{comparison.overall_status}",
                severity=(
                    "error" if comparison.overall_status == "mismatch" else "info"
                ),
                field_path="comparison",
                message=(
                    "reference aggregate comparison completed under the declared "
                    "field-specific precision policy"
                ),
                evidence_refs=(
                    request.comparison_fixture.fixture_fingerprint,
                    comparison.comparison_fingerprint,
                ),
            ),
        )
    return build_settled_evaluation_report(
        request=request,
        diagnostics=diagnostics,
        physical_trace=physical_trace,
        physical_metrics=physical_metrics,
        settlement=settlement.to_dict(),
        total_profit_eur=settlement.total_profit_eur,
        comparison=None if comparison is None else comparison.to_dict(),
    )


def replay_invalid_fcr_bid_diagnostic(
    request: FCRBidEvaluationRequest,
) -> InvalidCommitmentDiagnosticReport:
    """Replay only static headroom failures without settlement or comparison."""

    if not isinstance(request, FCRBidEvaluationRequest):
        raise FCRBidEvaluationValidationError(
            "request must be one FCRBidEvaluationRequest"
        )
    diagnostics = _preflight_diagnostics(request)
    errors = tuple(item for item in diagnostics if item.severity == "error")
    if not errors:
        raise FCRBidEvaluationValidationError(
            "diagnostic replay requires a statically invalid accepted commitment"
        )
    diagnostic_codes = {
        "charge_power_headroom_insufficient",
        "discharge_power_headroom_insufficient",
    }
    unsupported = [item.code for item in errors if item.code not in diagnostic_codes]
    if unsupported:
        raise FCRBidEvaluationValidationError(
            "diagnostic replay refuses integrity or input failures: "
            + ", ".join(sorted(unsupported))
        )

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
    identity = _report_identity(request)
    return InvalidCommitmentDiagnosticReport(
        evaluation_id=request.evaluation_id,
        plan_id=request.plan.plan_id,
        producer=identity["producer"],
        information_cutoff_utc=identity["information_cutoff_utc"],
        schedule_identity=identity["schedule_identity"],
        optimization_metadata=identity["optimization_metadata"],
        diagnostics=errors,
        physical_trace=physical_trace,
        physical_metrics=_daily_physical_metrics(request, physical),
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
    "STACKED_SERVICE_SETTLEMENT_PROFILE",
    "REFERENCE_SETTLEMENT_PROFILE",
    "InvalidCommitmentDiagnosticReport",
    "build_accepted_plan_market_context",
    "build_market_data_context",
    "build_settled_evaluation_report",
    "build_validation_failed_evaluation_report",
    "canonical_json_bytes",
    "evaluate_fixed_fcr_bid",
    "replay_invalid_fcr_bid_diagnostic",
]
