"""Shared deterministic primitives for aFRR and mFRR battery replay."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import partial
import math
from types import MappingProxyType

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import fingerprint, thaw
from open_energy_lab.core.validation import (
    enum_member,
    finite,
    mapping,
    non_empty_str,
    non_negative,
    positive,
    sha256_digest,
)
from open_energy_lab.market.restoration_activation import (
    AFRRActivationTrajectory,
    MFRRActivationEvent,
    MFRRActivationKind,
    MFRRActivationSequence,
    RestorationDirection,
    RestorationProduct,
)
from open_energy_lab.market.time import (
    CanonicalInterval,
    MarketTimeValidationError,
    parse_iso8601_duration,
)

from .battery import BatteryState, apply_power_request
from .restoration_contracts import (
    DirectionalCapacitySchedule,
    RestorationCapability,
    RestorationEnergyBaselineSchedule,
)
from .scenario import BatteryComponent


RESTORATION_REPLAY_CORE_SCHEMA_VERSION = "oel.restoration.replay-core.v1"
RESTORATION_REPLAY_SAMPLE_SCHEMA_VERSION = "oel.restoration.replay-sample.v1"
AFRR_REPLAY_REQUEST_SCHEMA_VERSION = "oel.restoration.afrr-replay-request.v1"
AFRR_REPLAY_RESULT_SCHEMA_VERSION = "oel.restoration.afrr-replay-result.v1"
AFRR_DIRECTIONAL_PERFORMANCE_SCHEMA_VERSION = (
    "oel.restoration.afrr-directional-performance.v1"
)
MFRR_REPLAY_REQUEST_SCHEMA_VERSION = "oel.restoration.mfrr-replay-request.v1"
MFRR_REPLAY_RESULT_SCHEMA_VERSION = "oel.restoration.mfrr-replay-result.v1"
MFRR_EVENT_PERFORMANCE_SCHEMA_VERSION = (
    "oel.restoration.mfrr-event-performance.v1"
)
MFRR_AGGREGATE_PERFORMANCE_SCHEMA_VERSION = (
    "oel.restoration.mfrr-aggregate-performance.v1"
)
DEFAULT_RESTORATION_REPLAY_TOLERANCE = 1e-6

RESTORATION_CAUSE_ORDER = (
    "commitment_limit",
    "upward_headroom",
    "downward_headroom",
    "ramp_limit",
    "activation_time_limit",
    "duration_limit",
    "charge_power_limit",
    "discharge_power_limit",
    "minimum_soc",
    "maximum_soc",
    "energy_headroom",
)
_CAUSE_INDEX = {cause: index for index, cause in enumerate(RESTORATION_CAUSE_ORDER)}


class RestorationReplayInputKind(str, Enum):
    """Exact activation input discriminator; FCR has no member."""

    AFRR_TRAJECTORY = "AFRR_TRAJECTORY"
    MFRR_EVENT_SEQUENCE = "MFRR_EVENT_SEQUENCE"


class RestorationReplayValidationError(ValidationError):
    """Raised before replay when shared product or physics inputs are invalid."""


_non_empty = partial(non_empty_str, error=RestorationReplayValidationError)
_finite = partial(finite, error=RestorationReplayValidationError)
_positive = partial(positive, error=RestorationReplayValidationError)
_non_negative = partial(non_negative, error=RestorationReplayValidationError)
_product = partial(
    enum_member, RestorationProduct, field_name="product", error=RestorationReplayValidationError
)


def _input_kind(value: object) -> RestorationReplayInputKind:
    try:
        return RestorationReplayInputKind(value)
    except (TypeError, ValueError) as exc:
        raise RestorationReplayValidationError(
            "activation input kind must be AFRR_TRAJECTORY or MFRR_EVENT_SEQUENCE"
        ) from exc


_sha256 = partial(sha256_digest, error=RestorationReplayValidationError)
_mapping = partial(mapping, error=RestorationReplayValidationError)
_plain = thaw
_fingerprint = partial(fingerprint, error=RestorationReplayValidationError)


def _ordered_causes(causes: Sequence[str]) -> tuple[str, ...]:
    unknown = [cause for cause in causes if cause not in _CAUSE_INDEX]
    if unknown:
        raise RestorationReplayValidationError(
            f"unknown restoration cause: {unknown[0]}"
        )
    return tuple(sorted(set(causes), key=_CAUSE_INDEX.__getitem__))


def _state_payload(state: BatteryState) -> dict[str, object]:
    return {
        "step_index": state.step_index,
        "soc": state.soc,
        "stored_energy_kwh": state.stored_energy_kwh,
        "available_charge_kwh": state.available_charge_kwh,
        "available_discharge_kwh": state.available_discharge_kwh,
    }


@dataclass(frozen=True, slots=True)
class RestorationIntegrationGrid:
    period: CanonicalInterval
    resolution: str
    intervals: tuple[CanonicalInterval, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "period": self.period.to_dict(),
            "resolution": self.resolution,
            "intervals": [item.to_dict() for item in self.intervals],
        }


def build_restoration_integration_grid(
    *,
    period: CanonicalInterval,
    resolution: str,
    intervals: Sequence[CanonicalInterval],
) -> RestorationIntegrationGrid:
    """Validate a native, gap-free integration grid without resampling."""

    if not isinstance(period, CanonicalInterval):
        raise RestorationReplayValidationError("period must be a CanonicalInterval")
    normalized_resolution = _non_empty(resolution, field_name="resolution")
    try:
        duration = parse_iso8601_duration(normalized_resolution)
    except MarketTimeValidationError as exc:
        raise RestorationReplayValidationError(str(exc)) from exc
    normalized = tuple(intervals)
    if not normalized or any(
        not isinstance(item, CanonicalInterval) for item in normalized
    ):
        raise RestorationReplayValidationError(
            "integration intervals must be non-empty CanonicalInterval values"
        )
    cursor = period.start_utc
    for index, item in enumerate(normalized):
        if item.start_utc != cursor:
            raise RestorationReplayValidationError(
                f"integration grid has a gap or overlap at interval {index}"
            )
        if item.end_utc - item.start_utc != duration:
            raise RestorationReplayValidationError(
                f"integration interval {index} does not match resolution duration"
            )
        cursor = item.end_utc
    if cursor != period.end_utc:
        raise RestorationReplayValidationError(
            "integration grid coverage is incomplete"
        )
    return RestorationIntegrationGrid(
        period=period,
        resolution=normalized_resolution,
        intervals=normalized,
    )


@dataclass(frozen=True, slots=True)
class RestorationReplayRequestCore:
    schema_version: str
    request_id: str
    semantics_version: str
    product: RestorationProduct
    activation_input_kind: RestorationReplayInputKind
    battery: BatteryComponent
    initial_state: BatteryState
    capability: RestorationCapability
    commitments: DirectionalCapacitySchedule
    baseline: RestorationEnergyBaselineSchedule
    integration_grid: RestorationIntegrationGrid
    tolerance: float
    input_fingerprints: Mapping[str, str]
    request_fingerprint: str


def build_restoration_replay_request_core(
    *,
    request_id: str,
    semantics_version: str,
    product: RestorationProduct | str,
    activation_input_kind: RestorationReplayInputKind | str,
    battery: BatteryComponent,
    initial_state: BatteryState,
    capability: RestorationCapability,
    commitments: DirectionalCapacitySchedule,
    baseline: RestorationEnergyBaselineSchedule,
    integration_grid: RestorationIntegrationGrid,
    tolerance: float,
    input_fingerprints: Mapping[str, str],
) -> RestorationReplayRequestCore:
    """Bind shared replay inputs with an exact product/input discriminator."""

    normalized_product = _product(product)
    kind = _input_kind(activation_input_kind)
    expected_kind = {
        RestorationProduct.AFRR: RestorationReplayInputKind.AFRR_TRAJECTORY,
        RestorationProduct.MFRR: RestorationReplayInputKind.MFRR_EVENT_SEQUENCE,
    }[normalized_product]
    if kind is not expected_kind:
        raise RestorationReplayValidationError(
            f"{normalized_product.value} replay requires {expected_kind.value}; "
            f"received incompatible {kind.value}"
        )
    if not isinstance(battery, BatteryComponent):
        raise RestorationReplayValidationError("battery must be a BatteryComponent")
    if not isinstance(initial_state, BatteryState):
        raise RestorationReplayValidationError("initial_state must be a BatteryState")
    if not isinstance(capability, RestorationCapability):
        raise RestorationReplayValidationError(
            "capability must be a RestorationCapability"
        )
    if not isinstance(commitments, DirectionalCapacitySchedule):
        raise RestorationReplayValidationError(
            "commitments must be a DirectionalCapacitySchedule"
        )
    if not isinstance(baseline, RestorationEnergyBaselineSchedule):
        raise RestorationReplayValidationError(
            "baseline must be a RestorationEnergyBaselineSchedule"
        )
    if not isinstance(integration_grid, RestorationIntegrationGrid):
        raise RestorationReplayValidationError(
            "integration_grid must be a RestorationIntegrationGrid"
        )
    if (
        commitments.product is not normalized_product
        or baseline.product is not normalized_product
    ):
        raise RestorationReplayValidationError(
            "commitments and baseline must match the exact replay product"
        )
    if (
        commitments.period != integration_grid.period
        or baseline.period != integration_grid.period
    ):
        raise RestorationReplayValidationError(
            "commitments, baseline, and integration grid periods must match"
        )
    if len(baseline.intervals) != len(integration_grid.intervals) or any(
        baseline_item.interval != grid_item
        for baseline_item, grid_item in zip(
            baseline.intervals, integration_grid.intervals, strict=True
        )
    ):
        raise RestorationReplayValidationError(
            "baseline intervals must align exactly with the integration grid"
        )
    normalized_tolerance = _positive(tolerance, field_name="tolerance")
    if not (
        battery.min_soc - normalized_tolerance
        <= initial_state.soc
        <= battery.max_soc + normalized_tolerance
    ):
        raise RestorationReplayValidationError(
            "initial_state SOC is incompatible with the battery"
        )
    raw_fingerprints = _mapping(input_fingerprints, field_name="input_fingerprints")
    required_fingerprints = {"activation", "commitments", "baseline", "capability"}
    if set(raw_fingerprints) != required_fingerprints:
        raise RestorationReplayValidationError(
            "input_fingerprints must contain activation, commitments, baseline, and capability"
        )
    fingerprints = MappingProxyType(
        {
            key: _sha256(value, field_name=f"input_fingerprints.{key}")
            for key, value in sorted(raw_fingerprints.items())
        }
    )
    expected = {
        "commitments": commitments.schedule_fingerprint,
        "baseline": baseline.schedule_fingerprint,
        "capability": capability.capability_fingerprint,
    }
    for key, value in expected.items():
        if fingerprints[key] != value:
            raise RestorationReplayValidationError(
                f"input_fingerprints.{key} does not match the validated input"
            )
    payload = {
        "schema_version": RESTORATION_REPLAY_CORE_SCHEMA_VERSION,
        "request_id": _non_empty(request_id, field_name="request_id"),
        "semantics_version": _non_empty(
            semantics_version, field_name="semantics_version"
        ),
        "product": normalized_product.value,
        "activation_input_kind": kind.value,
        "battery": battery.to_dict(),
        "initial_state": _state_payload(initial_state),
        "capability_fingerprint": capability.capability_fingerprint,
        "commitments_fingerprint": commitments.schedule_fingerprint,
        "baseline_fingerprint": baseline.schedule_fingerprint,
        "integration_grid_fingerprint": _fingerprint(integration_grid.to_dict()),
        "tolerance": normalized_tolerance,
        "input_fingerprints": dict(fingerprints),
    }
    return RestorationReplayRequestCore(
        schema_version=RESTORATION_REPLAY_CORE_SCHEMA_VERSION,
        request_id=str(payload["request_id"]),
        semantics_version=str(payload["semantics_version"]),
        product=normalized_product,
        activation_input_kind=kind,
        battery=battery,
        initial_state=initial_state,
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        integration_grid=integration_grid,
        tolerance=normalized_tolerance,
        input_fingerprints=fingerprints,
        request_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class RestorationCapabilityDecision:
    product: RestorationProduct
    accepted_baseline_power_kw: float
    requested_balancing_power_kw: float
    requested_combined_power_kw: float
    capability_accepted_balancing_power_kw: float
    capability_accepted_combined_power_kw: float
    achieved_ramp_kw_per_second: float
    response_delay_seconds: float
    causes: tuple[str, ...]


def enforce_restoration_capability(
    *,
    product: RestorationProduct | str,
    accepted_baseline_power_kw: float,
    requested_balancing_power_kw: float,
    upward_commitment_kw: float,
    downward_commitment_kw: float,
    upward_headroom_kw: float,
    downward_headroom_kw: float,
    previous_capability_combined_power_kw: float,
    interval_seconds: float,
    capability: RestorationCapability,
    actual_activation_delay_seconds: float = 0.0,
    requested_duration_seconds: float | None = None,
) -> RestorationCapabilityDecision:
    """Apply commitment, headroom, ramp, response, and duration gates in order."""

    normalized_product = _product(product)
    if not isinstance(capability, RestorationCapability):
        raise RestorationReplayValidationError(
            "capability must be a RestorationCapability"
        )
    baseline = _finite(
        accepted_baseline_power_kw, field_name="accepted_baseline_power_kw"
    )
    requested = _finite(
        requested_balancing_power_kw, field_name="requested_balancing_power_kw"
    )
    upward_commitment = _non_negative(
        upward_commitment_kw, field_name="upward_commitment_kw"
    )
    downward_commitment = _non_negative(
        downward_commitment_kw, field_name="downward_commitment_kw"
    )
    upward_headroom = _non_negative(
        upward_headroom_kw, field_name="upward_headroom_kw"
    )
    downward_headroom = _non_negative(
        downward_headroom_kw, field_name="downward_headroom_kw"
    )
    previous = _finite(
        previous_capability_combined_power_kw,
        field_name="previous_capability_combined_power_kw",
    )
    duration = _positive(interval_seconds, field_name="interval_seconds")
    response_delay = _non_negative(
        actual_activation_delay_seconds,
        field_name="actual_activation_delay_seconds",
    )
    causes: list[str] = []
    accepted_balancing = requested
    if requested < 0:
        if abs(accepted_balancing) > upward_commitment:
            accepted_balancing = -upward_commitment
            causes.append("commitment_limit")
        if abs(accepted_balancing) > upward_headroom:
            accepted_balancing = -upward_headroom
            causes.append("upward_headroom")
    elif requested > 0:
        if accepted_balancing > downward_commitment:
            accepted_balancing = downward_commitment
            causes.append("commitment_limit")
        if accepted_balancing > downward_headroom:
            accepted_balancing = downward_headroom
            causes.append("downward_headroom")
    target_combined = baseline + accepted_balancing
    delta = target_combined - previous
    maximum_delta = (
        capability.max_ramp_up_kw_per_second * duration
        if delta >= 0
        else capability.max_ramp_down_kw_per_second * duration
    )
    if abs(delta) > maximum_delta:
        target_combined = previous + math.copysign(maximum_delta, delta)
        accepted_balancing = target_combined - baseline
        causes.append("ramp_limit")
    if response_delay > capability.max_activation_delay_seconds[normalized_product]:
        causes.append("activation_time_limit")
        target_combined = baseline
        accepted_balancing = 0.0
    if requested_duration_seconds is not None:
        requested_duration = _non_negative(
            requested_duration_seconds, field_name="requested_duration_seconds"
        )
        if not (
            capability.min_supported_duration_seconds[normalized_product]
            <= requested_duration
            <= capability.max_supported_duration_seconds[normalized_product]
        ):
            causes.append("duration_limit")
            target_combined = baseline
            accepted_balancing = 0.0
    achieved_ramp = abs(target_combined - previous) / duration
    return RestorationCapabilityDecision(
        product=normalized_product,
        accepted_baseline_power_kw=baseline,
        requested_balancing_power_kw=requested,
        requested_combined_power_kw=baseline + requested,
        capability_accepted_balancing_power_kw=accepted_balancing,
        capability_accepted_combined_power_kw=target_combined,
        achieved_ramp_kw_per_second=achieved_ramp,
        response_delay_seconds=response_delay,
        causes=_ordered_causes(causes),
    )


@dataclass(frozen=True, slots=True)
class RestorationReplaySample:
    schema_version: str
    sample_index: int
    interval: CanonicalInterval
    product: RestorationProduct
    event_id: str | None
    mfrr_kind: MFRRActivationKind | None
    accepted_baseline_power_kw: float
    requested_balancing_power_kw: float
    requested_combined_power_kw: float
    capability_accepted_balancing_power_kw: float
    capability_accepted_combined_power_kw: float
    achieved_ramp_kw_per_second: float
    response_delay_seconds: float
    delivered_combined_power_kw: float
    delivered_balancing_power_kw: float
    charge_energy_kwh: float
    discharge_energy_kwh: float
    net_terminal_energy_kwh: float
    tracking_error_kw: float
    absolute_tracking_error_kw: float
    requested_activation_energy_kwh: float
    delivered_activation_energy_kwh: float
    undelivered_activation_energy_kwh: float
    state: BatteryState
    upward_power_headroom_kw: float
    downward_power_headroom_kw: float
    upward_energy_headroom_kwh: float
    downward_energy_headroom_kwh: float
    capability_causes: tuple[str, ...]
    physical_causes: tuple[str, ...]
    causes: tuple[str, ...]
    non_performance_duration_seconds: float
    sample_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sample_index": self.sample_index,
            "interval": self.interval.to_dict(),
            "product": self.product.value,
            "event_id": self.event_id,
            "mfrr_kind": None if self.mfrr_kind is None else self.mfrr_kind.value,
            "accepted_baseline_power_kw": self.accepted_baseline_power_kw,
            "requested_balancing_power_kw": self.requested_balancing_power_kw,
            "requested_combined_power_kw": self.requested_combined_power_kw,
            "capability_accepted_balancing_power_kw": self.capability_accepted_balancing_power_kw,
            "capability_accepted_combined_power_kw": self.capability_accepted_combined_power_kw,
            "achieved_ramp_kw_per_second": self.achieved_ramp_kw_per_second,
            "response_delay_seconds": self.response_delay_seconds,
            "delivered_combined_power_kw": self.delivered_combined_power_kw,
            "delivered_balancing_power_kw": self.delivered_balancing_power_kw,
            "charge_energy_kwh": self.charge_energy_kwh,
            "discharge_energy_kwh": self.discharge_energy_kwh,
            "net_terminal_energy_kwh": self.net_terminal_energy_kwh,
            "tracking_error_kw": self.tracking_error_kw,
            "absolute_tracking_error_kw": self.absolute_tracking_error_kw,
            "requested_activation_energy_kwh": self.requested_activation_energy_kwh,
            "delivered_activation_energy_kwh": self.delivered_activation_energy_kwh,
            "undelivered_activation_energy_kwh": self.undelivered_activation_energy_kwh,
            "state": _state_payload(self.state),
            "upward_power_headroom_kw": self.upward_power_headroom_kw,
            "downward_power_headroom_kw": self.downward_power_headroom_kw,
            "upward_energy_headroom_kwh": self.upward_energy_headroom_kwh,
            "downward_energy_headroom_kwh": self.downward_energy_headroom_kwh,
            "capability_causes": list(self.capability_causes),
            "physical_causes": list(self.physical_causes),
            "causes": list(self.causes),
            "non_performance_duration_seconds": self.non_performance_duration_seconds,
            "sample_fingerprint": self.sample_fingerprint,
        }


def _delivered_activation_magnitude(
    requested_balancing_kw: float, delivered_balancing_kw: float
) -> float:
    if requested_balancing_kw > 0:
        return max(0.0, min(requested_balancing_kw, delivered_balancing_kw))
    if requested_balancing_kw < 0:
        return max(0.0, min(abs(requested_balancing_kw), -delivered_balancing_kw))
    return 0.0


def apply_restoration_battery_transition(
    *,
    sample_index: int,
    interval: CanonicalInterval,
    product: RestorationProduct | str,
    decision: RestorationCapabilityDecision,
    battery: BatteryComponent,
    state: BatteryState,
    tolerance: float,
    event_id: str | None = None,
    mfrr_kind: MFRRActivationKind | str | None = None,
) -> RestorationReplaySample:
    """Pass one capability-accepted request through unchanged battery physics."""

    normalized_product = _product(product)
    if decision.product is not normalized_product:
        raise RestorationReplayValidationError(
            "capability decision product does not match the replay sample"
        )
    if not isinstance(interval, CanonicalInterval):
        raise RestorationReplayValidationError("interval must be a CanonicalInterval")
    if not isinstance(battery, BatteryComponent) or not isinstance(state, BatteryState):
        raise RestorationReplayValidationError(
            "battery and state must be validated simulator types"
        )
    normalized_tolerance = _positive(tolerance, field_name="tolerance")
    if isinstance(sample_index, bool) or not isinstance(sample_index, int) or sample_index < 0:
        raise RestorationReplayValidationError(
            "sample_index must be a non-negative integer"
        )
    normalized_event_id = None
    normalized_kind = None
    if normalized_product is RestorationProduct.AFRR:
        if event_id is not None or mfrr_kind is not None:
            raise RestorationReplayValidationError(
                "AFRR samples cannot contain mFRR event identity"
            )
    else:
        if event_id is not None:
            normalized_event_id = _non_empty(event_id, field_name="event_id")
        if mfrr_kind is not None:
            try:
                normalized_kind = MFRRActivationKind(mfrr_kind)
            except (TypeError, ValueError) as exc:
                raise RestorationReplayValidationError(
                    "mfrr_kind must be SCHEDULED or DIRECT"
                ) from exc
    interval_hours = (interval.end_utc - interval.start_utc).total_seconds() / 3600.0
    interval_seconds = interval_hours * 3600.0
    transition = apply_power_request(
        component=battery,
        state=state,
        requested_power_kw=decision.capability_accepted_combined_power_kw,
        time_step_hours=interval_hours,
        step_index=sample_index,
    )
    physical_causes: list[str] = []
    requested_combined = decision.capability_accepted_combined_power_kw
    if requested_combined > battery.max_charge_kw + normalized_tolerance:
        physical_causes.append("charge_power_limit")
    if requested_combined < -battery.max_discharge_kw - normalized_tolerance:
        physical_causes.append("discharge_power_limit")
    power_limited_target = min(
        max(requested_combined, -battery.max_discharge_kw), battery.max_charge_kw
    )
    if abs(transition.realized_power_kw - power_limited_target) > normalized_tolerance:
        if power_limited_target > 0:
            physical_causes.append("maximum_soc")
        elif power_limited_target < 0:
            physical_causes.append("minimum_soc")
        physical_causes.append("energy_headroom")
    physical = _ordered_causes(physical_causes)
    all_causes = _ordered_causes((*decision.causes, *physical))
    delivered_combined = transition.realized_power_kw
    delivered_balancing = delivered_combined - decision.accepted_baseline_power_kw
    tracking_error = decision.requested_balancing_power_kw - delivered_balancing
    charge_energy = max(delivered_combined, 0.0) * interval_hours
    discharge_energy = max(-delivered_combined, 0.0) * interval_hours
    requested_activation = abs(decision.requested_balancing_power_kw) * interval_hours
    delivered_activation = _delivered_activation_magnitude(
        decision.requested_balancing_power_kw, delivered_balancing
    ) * interval_hours
    undelivered_activation = max(0.0, requested_activation - delivered_activation)
    next_state = transition.state
    provisional = RestorationReplaySample(
        schema_version=RESTORATION_REPLAY_SAMPLE_SCHEMA_VERSION,
        sample_index=sample_index,
        interval=interval,
        product=normalized_product,
        event_id=normalized_event_id,
        mfrr_kind=normalized_kind,
        accepted_baseline_power_kw=decision.accepted_baseline_power_kw,
        requested_balancing_power_kw=decision.requested_balancing_power_kw,
        requested_combined_power_kw=decision.requested_combined_power_kw,
        capability_accepted_balancing_power_kw=(
            decision.capability_accepted_balancing_power_kw
        ),
        capability_accepted_combined_power_kw=requested_combined,
        achieved_ramp_kw_per_second=decision.achieved_ramp_kw_per_second,
        response_delay_seconds=decision.response_delay_seconds,
        delivered_combined_power_kw=delivered_combined,
        delivered_balancing_power_kw=delivered_balancing,
        charge_energy_kwh=charge_energy,
        discharge_energy_kwh=discharge_energy,
        net_terminal_energy_kwh=charge_energy - discharge_energy,
        tracking_error_kw=tracking_error,
        absolute_tracking_error_kw=abs(tracking_error),
        requested_activation_energy_kwh=requested_activation,
        delivered_activation_energy_kwh=delivered_activation,
        undelivered_activation_energy_kwh=undelivered_activation,
        state=next_state,
        upward_power_headroom_kw=max(
            0.0, battery.max_discharge_kw + delivered_combined
        ),
        downward_power_headroom_kw=max(
            0.0, battery.max_charge_kw - delivered_combined
        ),
        upward_energy_headroom_kwh=(
            next_state.available_discharge_kwh * battery.discharge_efficiency
        ),
        downward_energy_headroom_kwh=(
            next_state.available_charge_kwh / battery.charge_efficiency
        ),
        capability_causes=decision.causes,
        physical_causes=physical,
        causes=all_causes,
        non_performance_duration_seconds=(
            interval_seconds if abs(tracking_error) > normalized_tolerance else 0.0
        ),
        sample_fingerprint="0" * 64,
    )
    payload = provisional.to_dict()
    payload.pop("sample_fingerprint")
    return RestorationReplaySample(
        **{
            **{
                field: getattr(provisional, field)
                for field in provisional.__dataclass_fields__
                if field != "sample_fingerprint"
            },
            "sample_fingerprint": _fingerprint(payload),
        }
    )


@dataclass(frozen=True, slots=True)
class RestorationEnergyTotals:
    charge_energy_kwh: float
    discharge_energy_kwh: float
    net_terminal_energy_kwh: float
    throughput_kwh: float
    requested_activation_energy_kwh: float
    delivered_activation_energy_kwh: float
    undelivered_activation_energy_kwh: float
    non_performance_duration_seconds: float
    totals_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "charge_energy_kwh": self.charge_energy_kwh,
            "discharge_energy_kwh": self.discharge_energy_kwh,
            "net_terminal_energy_kwh": self.net_terminal_energy_kwh,
            "throughput_kwh": self.throughput_kwh,
            "requested_activation_energy_kwh": self.requested_activation_energy_kwh,
            "delivered_activation_energy_kwh": self.delivered_activation_energy_kwh,
            "undelivered_activation_energy_kwh": self.undelivered_activation_energy_kwh,
            "non_performance_duration_seconds": self.non_performance_duration_seconds,
            "totals_fingerprint": self.totals_fingerprint,
        }


def aggregate_restoration_samples(
    samples: Sequence[RestorationReplaySample], *, tolerance: float
) -> RestorationEnergyTotals:
    """Aggregate terminal and activation energy with explicit conservation checks."""

    normalized_tolerance = _positive(tolerance, field_name="tolerance")
    normalized = tuple(samples)
    if not normalized or any(
        not isinstance(item, RestorationReplaySample) for item in normalized
    ):
        raise RestorationReplayValidationError(
            "samples must be non-empty RestorationReplaySample values"
        )
    for previous, current in zip(normalized, normalized[1:]):
        if (
            current.sample_index <= previous.sample_index
            or current.interval.start_utc < previous.interval.end_utc
        ):
            raise RestorationReplayValidationError(
                "replay samples must be chronological and non-overlapping"
            )
    charge = sum(item.charge_energy_kwh for item in normalized)
    discharge = sum(item.discharge_energy_kwh for item in normalized)
    net = sum(item.net_terminal_energy_kwh for item in normalized)
    requested = sum(item.requested_activation_energy_kwh for item in normalized)
    delivered = sum(item.delivered_activation_energy_kwh for item in normalized)
    undelivered = sum(item.undelivered_activation_energy_kwh for item in normalized)
    if abs(net - (charge - discharge)) > normalized_tolerance:
        raise RestorationReplayValidationError(
            "terminal charge/discharge/net energy does not conserve"
        )
    if abs(requested - (delivered + undelivered)) > normalized_tolerance:
        raise RestorationReplayValidationError(
            "requested/delivered/undelivered activation energy does not conserve"
        )
    payload = {
        "charge_energy_kwh": charge,
        "discharge_energy_kwh": discharge,
        "net_terminal_energy_kwh": net,
        "throughput_kwh": charge + discharge,
        "requested_activation_energy_kwh": requested,
        "delivered_activation_energy_kwh": delivered,
        "undelivered_activation_energy_kwh": undelivered,
        "non_performance_duration_seconds": sum(
            item.non_performance_duration_seconds for item in normalized
        ),
    }
    return RestorationEnergyTotals(
        **payload,
        totals_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class RestorationReplayResultCore:
    schema_version: str
    product: RestorationProduct
    request_fingerprint: str
    samples: tuple[RestorationReplaySample, ...]
    totals: RestorationEnergyTotals
    causes: tuple[str, ...]
    result_fingerprint: str


def build_restoration_replay_result_core(
    *,
    request: RestorationReplayRequestCore,
    samples: Sequence[RestorationReplaySample],
) -> RestorationReplayResultCore:
    """Build a deterministic shared result core for a product-specific wrapper."""

    if not isinstance(request, RestorationReplayRequestCore):
        raise RestorationReplayValidationError(
            "request must be a RestorationReplayRequestCore"
        )
    normalized = tuple(samples)
    if any(item.product is not request.product for item in normalized):
        raise RestorationReplayValidationError(
            "every replay sample must match the exact request product"
        )
    totals = aggregate_restoration_samples(normalized, tolerance=request.tolerance)
    causes = _ordered_causes(
        tuple(cause for item in normalized for cause in item.causes)
    )
    payload = {
        "schema_version": RESTORATION_REPLAY_CORE_SCHEMA_VERSION,
        "product": request.product.value,
        "request_fingerprint": request.request_fingerprint,
        "sample_fingerprints": [item.sample_fingerprint for item in normalized],
        "totals_fingerprint": totals.totals_fingerprint,
        "causes": list(causes),
    }
    return RestorationReplayResultCore(
        schema_version=RESTORATION_REPLAY_CORE_SCHEMA_VERSION,
        product=request.product,
        request_fingerprint=request.request_fingerprint,
        samples=normalized,
        totals=totals,
        causes=causes,
        result_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class AFRRReplayRequest:
    """Exact aFRR replay inputs bound to a validated shared request core."""

    schema_version: str
    request_id: str
    semantics_version: str
    battery: BatteryComponent
    initial_state: BatteryState
    capability: RestorationCapability
    commitments: DirectionalCapacitySchedule
    baseline: RestorationEnergyBaselineSchedule
    activation_trajectory: AFRRActivationTrajectory
    integration_grid: RestorationIntegrationGrid
    tolerance: float
    input_fingerprints: Mapping[str, str]
    core: RestorationReplayRequestCore
    request_fingerprint: str


def build_afrr_replay_request(
    *,
    request_id: str,
    semantics_version: str,
    battery: BatteryComponent,
    initial_state: BatteryState,
    capability: RestorationCapability,
    commitments: DirectionalCapacitySchedule,
    baseline: RestorationEnergyBaselineSchedule,
    activation_trajectory: AFRRActivationTrajectory,
    integration_grid: RestorationIntegrationGrid,
    tolerance: float = DEFAULT_RESTORATION_REPLAY_TOLERANCE,
) -> AFRRReplayRequest:
    """Validate exact product types, alignment, and fingerprints before replay."""

    if type(activation_trajectory) is not AFRRActivationTrajectory:
        raise RestorationReplayValidationError(
            "activation_trajectory must be exactly an AFRRActivationTrajectory"
        )
    if not isinstance(integration_grid, RestorationIntegrationGrid):
        raise RestorationReplayValidationError(
            "integration_grid must be a RestorationIntegrationGrid"
        )
    if activation_trajectory.period != integration_grid.period:
        raise RestorationReplayValidationError(
            "aFRR trajectory period must align exactly with the integration grid"
        )
    if activation_trajectory.resolution != integration_grid.resolution:
        raise RestorationReplayValidationError(
            "aFRR trajectory resolution must align exactly with the integration grid"
        )
    if len(activation_trajectory.samples) != len(integration_grid.intervals) or any(
        sample.interval != interval
        for sample, interval in zip(
            activation_trajectory.samples,
            integration_grid.intervals,
            strict=True,
        )
    ):
        raise RestorationReplayValidationError(
            "aFRR trajectory samples must align exactly with the native integration grid"
        )
    fingerprints = MappingProxyType(
        {
            "activation": activation_trajectory.trajectory_fingerprint,
            "baseline": getattr(baseline, "schedule_fingerprint", ""),
            "capability": getattr(capability, "capability_fingerprint", ""),
            "commitments": getattr(commitments, "schedule_fingerprint", ""),
        }
    )
    core = build_restoration_replay_request_core(
        request_id=request_id,
        semantics_version=semantics_version,
        product=RestorationProduct.AFRR,
        activation_input_kind=RestorationReplayInputKind.AFRR_TRAJECTORY,
        battery=battery,
        initial_state=initial_state,
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        integration_grid=integration_grid,
        tolerance=tolerance,
        input_fingerprints=fingerprints,
    )
    payload = {
        "schema_version": AFRR_REPLAY_REQUEST_SCHEMA_VERSION,
        "core_request_fingerprint": core.request_fingerprint,
        "activation_trajectory_fingerprint": (
            activation_trajectory.trajectory_fingerprint
        ),
    }
    return AFRRReplayRequest(
        schema_version=AFRR_REPLAY_REQUEST_SCHEMA_VERSION,
        request_id=core.request_id,
        semantics_version=core.semantics_version,
        battery=core.battery,
        initial_state=core.initial_state,
        capability=core.capability,
        commitments=core.commitments,
        baseline=core.baseline,
        activation_trajectory=activation_trajectory,
        integration_grid=core.integration_grid,
        tolerance=core.tolerance,
        input_fingerprints=core.input_fingerprints,
        core=core,
        request_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class AFRRDirectionalPerformance:
    """One direction's conserved tracking and non-performance aggregates."""

    schema_version: str
    direction: RestorationDirection
    sample_count: int
    requested_energy_kwh: float
    delivered_energy_kwh: float
    undelivered_energy_kwh: float
    absolute_tracking_error_energy_kwh: float
    peak_requested_power_kw: float
    peak_delivered_power_kw: float
    maximum_response_delay_seconds: float
    maximum_achieved_ramp_kw_per_second: float
    non_performance_duration_seconds: float
    causes: tuple[str, ...]
    performance_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "direction": self.direction.value,
            "sample_count": self.sample_count,
            "requested_energy_kwh": self.requested_energy_kwh,
            "delivered_energy_kwh": self.delivered_energy_kwh,
            "undelivered_energy_kwh": self.undelivered_energy_kwh,
            "absolute_tracking_error_energy_kwh": (
                self.absolute_tracking_error_energy_kwh
            ),
            "peak_requested_power_kw": self.peak_requested_power_kw,
            "peak_delivered_power_kw": self.peak_delivered_power_kw,
            "maximum_response_delay_seconds": self.maximum_response_delay_seconds,
            "maximum_achieved_ramp_kw_per_second": (
                self.maximum_achieved_ramp_kw_per_second
            ),
            "non_performance_duration_seconds": (
                self.non_performance_duration_seconds
            ),
            "causes": list(self.causes),
            "performance_fingerprint": self.performance_fingerprint,
        }


def _afrr_directional_performance(
    *,
    direction: RestorationDirection,
    activation: AFRRActivationTrajectory,
    samples: tuple[RestorationReplaySample, ...],
) -> AFRRDirectionalPerformance:
    selected = [
        (activation_sample, replay_sample)
        for activation_sample, replay_sample in zip(
            activation.samples, samples, strict=True
        )
        if activation_sample.direction is direction
    ]
    requested = sum(
        replay_sample.requested_activation_energy_kwh
        for _, replay_sample in selected
    )
    delivered = sum(
        replay_sample.delivered_activation_energy_kwh
        for _, replay_sample in selected
    )
    undelivered = sum(
        replay_sample.undelivered_activation_energy_kwh
        for _, replay_sample in selected
    )
    tracking_error_energy = sum(
        replay_sample.absolute_tracking_error_kw
        * (
            replay_sample.interval.end_utc - replay_sample.interval.start_utc
        ).total_seconds()
        / 3600.0
        for _, replay_sample in selected
    )
    requested_powers = [
        abs(replay_sample.requested_balancing_power_kw)
        for _, replay_sample in selected
    ]
    delivered_powers = [
        direction.magnitude_of(replay_sample.delivered_balancing_power_kw)
        for _, replay_sample in selected
    ]
    causes = _ordered_causes(
        tuple(
            cause
            for _, replay_sample in selected
            for cause in replay_sample.causes
        )
    )
    payload = {
        "schema_version": AFRR_DIRECTIONAL_PERFORMANCE_SCHEMA_VERSION,
        "direction": direction.value,
        "sample_count": len(selected),
        "requested_energy_kwh": requested,
        "delivered_energy_kwh": delivered,
        "undelivered_energy_kwh": undelivered,
        "absolute_tracking_error_energy_kwh": tracking_error_energy,
        "peak_requested_power_kw": max(requested_powers, default=0.0),
        "peak_delivered_power_kw": max(delivered_powers, default=0.0),
        "maximum_response_delay_seconds": max(
            (sample.response_delay_seconds for _, sample in selected), default=0.0
        ),
        "maximum_achieved_ramp_kw_per_second": max(
            (sample.achieved_ramp_kw_per_second for _, sample in selected),
            default=0.0,
        ),
        "non_performance_duration_seconds": sum(
            sample.non_performance_duration_seconds for _, sample in selected
        ),
        "causes": list(causes),
    }
    return AFRRDirectionalPerformance(
        schema_version=AFRR_DIRECTIONAL_PERFORMANCE_SCHEMA_VERSION,
        direction=direction,
        sample_count=int(payload["sample_count"]),
        requested_energy_kwh=requested,
        delivered_energy_kwh=delivered,
        undelivered_energy_kwh=undelivered,
        absolute_tracking_error_energy_kwh=tracking_error_energy,
        peak_requested_power_kw=float(payload["peak_requested_power_kw"]),
        peak_delivered_power_kw=float(payload["peak_delivered_power_kw"]),
        maximum_response_delay_seconds=float(
            payload["maximum_response_delay_seconds"]
        ),
        maximum_achieved_ramp_kw_per_second=float(
            payload["maximum_achieved_ramp_kw_per_second"]
        ),
        non_performance_duration_seconds=float(
            payload["non_performance_duration_seconds"]
        ),
        causes=causes,
        performance_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class AFRRReplayResult:
    """Immutable aFRR trace, directional performance, and physical totals."""

    schema_version: str
    request: AFRRReplayRequest
    request_fingerprint: str
    activation_trajectory_fingerprint: str
    samples: tuple[RestorationReplaySample, ...]
    directional_performance: Mapping[
        RestorationDirection, AFRRDirectionalPerformance
    ]
    totals: RestorationEnergyTotals
    causes: tuple[str, ...]
    input_fingerprints: Mapping[str, str]
    core_result_fingerprint: str
    result_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        serialized_samples = []
        for sample in self.samples:
            payload = sample.to_dict()
            payload.pop("event_id")
            payload.pop("mfrr_kind")
            serialized_samples.append(payload)
        return {
            "schema_version": self.schema_version,
            "request_fingerprint": self.request_fingerprint,
            "activation_trajectory_fingerprint": (
                self.activation_trajectory_fingerprint
            ),
            "samples": serialized_samples,
            "directional_performance": {
                direction.value: self.directional_performance[direction].to_dict()
                for direction in RestorationDirection
            },
            "totals": self.totals.to_dict(),
            "causes": list(self.causes),
            "input_fingerprints": dict(self.input_fingerprints),
            "core_result_fingerprint": self.core_result_fingerprint,
            "result_fingerprint": self.result_fingerprint,
        }


def replay_afrr(request: AFRRReplayRequest) -> AFRRReplayResult:
    """Replay native interval-average aFRR requests without resampling."""

    if type(request) is not AFRRReplayRequest:
        raise RestorationReplayValidationError(
            "request must be exactly an AFRRReplayRequest"
        )
    state = request.initial_state
    previous_combined_power_kw = (
        request.baseline.intervals[0].accepted_baseline_power_kw
    )
    samples: list[RestorationReplaySample] = []
    commitment_pairs = request.commitments.commitment_pairs_covering(
        request.integration_grid.intervals
    )
    for index, (
        activation_sample,
        baseline_interval,
        grid_interval,
        commitment_pair,
    ) in enumerate(
        zip(
            request.activation_trajectory.samples,
            request.baseline.intervals,
            request.integration_grid.intervals,
            commitment_pairs,
            strict=True,
        )
    ):
        if (
            activation_sample.interval != grid_interval
            or baseline_interval.interval != grid_interval
        ):
            raise RestorationReplayValidationError(
                f"aFRR replay inputs do not align at interval {index}"
            )
        baseline_power = baseline_interval.accepted_baseline_power_kw
        upward, downward = commitment_pair
        interval_seconds = (
            grid_interval.end_utc - grid_interval.start_utc
        ).total_seconds()
        decision = enforce_restoration_capability(
            product=RestorationProduct.AFRR,
            accepted_baseline_power_kw=baseline_power,
            requested_balancing_power_kw=(
                activation_sample.requested_balancing_power_kw
            ),
            upward_commitment_kw=upward.committed_capacity_kw,
            downward_commitment_kw=downward.committed_capacity_kw,
            upward_headroom_kw=max(
                0.0, request.battery.max_discharge_kw + baseline_power
            ),
            downward_headroom_kw=max(
                0.0, request.battery.max_charge_kw - baseline_power
            ),
            previous_capability_combined_power_kw=previous_combined_power_kw,
            interval_seconds=interval_seconds,
            capability=request.capability,
            actual_activation_delay_seconds=0.0,
            requested_duration_seconds=interval_seconds,
        )
        sample = apply_restoration_battery_transition(
            sample_index=index,
            interval=grid_interval,
            product=RestorationProduct.AFRR,
            decision=decision,
            battery=request.battery,
            state=state,
            tolerance=request.tolerance,
        )
        samples.append(sample)
        state = sample.state
        previous_combined_power_kw = sample.delivered_combined_power_kw
    normalized_samples = tuple(samples)
    core_result = build_restoration_replay_result_core(
        request=request.core,
        samples=normalized_samples,
    )
    directional = MappingProxyType(
        {
            direction: _afrr_directional_performance(
                direction=direction,
                activation=request.activation_trajectory,
                samples=normalized_samples,
            )
            for direction in RestorationDirection
        }
    )
    directional_requested = sum(
        performance.requested_energy_kwh for performance in directional.values()
    )
    directional_delivered = sum(
        performance.delivered_energy_kwh for performance in directional.values()
    )
    directional_undelivered = sum(
        performance.undelivered_energy_kwh for performance in directional.values()
    )
    if (
        abs(
            directional_requested
            - core_result.totals.requested_activation_energy_kwh
        )
        > request.tolerance
        or abs(
            directional_delivered
            - core_result.totals.delivered_activation_energy_kwh
        )
        > request.tolerance
        or abs(
            directional_undelivered
            - core_result.totals.undelivered_activation_energy_kwh
        )
        > request.tolerance
    ):
        raise RestorationReplayValidationError(
            "aFRR directional and horizon activation energy do not conserve"
        )
    payload = {
        "schema_version": AFRR_REPLAY_RESULT_SCHEMA_VERSION,
        "request_fingerprint": request.request_fingerprint,
        "activation_trajectory_fingerprint": (
            request.activation_trajectory.trajectory_fingerprint
        ),
        "sample_fingerprints": [
            sample.sample_fingerprint for sample in normalized_samples
        ],
        "directional_performance_fingerprints": {
            direction.value: directional[direction].performance_fingerprint
            for direction in RestorationDirection
        },
        "totals_fingerprint": core_result.totals.totals_fingerprint,
        "causes": list(core_result.causes),
        "input_fingerprints": dict(request.input_fingerprints),
        "core_result_fingerprint": core_result.result_fingerprint,
    }
    return AFRRReplayResult(
        schema_version=AFRR_REPLAY_RESULT_SCHEMA_VERSION,
        request=request,
        request_fingerprint=request.request_fingerprint,
        activation_trajectory_fingerprint=(
            request.activation_trajectory.trajectory_fingerprint
        ),
        samples=normalized_samples,
        directional_performance=directional,
        totals=core_result.totals,
        causes=core_result.causes,
        input_fingerprints=request.input_fingerprints,
        core_result_fingerprint=core_result.result_fingerprint,
        result_fingerprint=_fingerprint(payload),
    )


def _validate_mfrr_event_grid(
    sequence: MFRRActivationSequence,
    grid: RestorationIntegrationGrid,
) -> None:
    boundaries = {grid.period.start_utc, grid.period.end_utc}
    boundaries.update(interval.start_utc for interval in grid.intervals)
    boundaries.update(interval.end_utc for interval in grid.intervals)
    segment_names = ("delay", "ramp_up", "hold", "ramp_down")
    for event in sequence.events:
        cursor = event.complete_interval.start_utc
        if cursor not in boundaries:
            raise RestorationReplayValidationError(
                f"mFRR event {event.event_id} start is not a conserving grid boundary"
            )
        durations = (
            event.activation_delay_seconds,
            event.ramp_up_seconds,
            event.hold_seconds,
            event.ramp_down_seconds,
        )
        for segment_name, duration_seconds in zip(
            segment_names,
            durations,
            strict=True,
        ):
            cursor += timedelta(seconds=duration_seconds)
            if cursor not in boundaries:
                raise RestorationReplayValidationError(
                    f"mFRR event {event.event_id} {segment_name} segment boundary "
                    "is not represented by the integration grid; expansion would "
                    "not be boundary-conserving"
                )
        if cursor != event.complete_interval.end_utc:
            raise RestorationReplayValidationError(
                f"mFRR event {event.event_id} segment boundaries do not conserve "
                "its complete interval"
            )


def _mfrr_events_by_interval(
    *,
    events: Sequence[MFRRActivationEvent],
    intervals: Sequence[CanonicalInterval],
) -> tuple[MFRRActivationEvent | None, ...]:
    """Expand ordered, non-overlapping events with one forward cursor."""

    normalized_events = tuple(events)
    event_index = 0
    expanded: list[MFRRActivationEvent | None] = []
    for interval in intervals:
        while (
            event_index < len(normalized_events)
            and normalized_events[event_index].complete_interval.end_utc
            <= interval.start_utc
        ):
            event_index += 1
        if event_index >= len(normalized_events):
            expanded.append(None)
            continue
        candidate = normalized_events[event_index]
        if candidate.complete_interval.start_utc >= interval.end_utc:
            expanded.append(None)
            continue
        if not (
            candidate.complete_interval.start_utc <= interval.start_utc
            and candidate.complete_interval.end_utc >= interval.end_utc
        ):
            raise RestorationReplayValidationError(
                f"mFRR event {candidate.event_id} only partially covers a replay "
                "interval; expansion is not boundary-conserving"
            )
        expanded.append(candidate)
    return tuple(expanded)


@dataclass(frozen=True, slots=True)
class MFRRReplayRequest:
    """Exact mFRR replay inputs bound to a validated shared request core."""

    schema_version: str
    request_id: str
    semantics_version: str
    battery: BatteryComponent
    initial_state: BatteryState
    capability: RestorationCapability
    commitments: DirectionalCapacitySchedule
    baseline: RestorationEnergyBaselineSchedule
    activation_sequence: MFRRActivationSequence
    integration_grid: RestorationIntegrationGrid
    tolerance: float
    input_fingerprints: Mapping[str, str]
    core: RestorationReplayRequestCore
    request_fingerprint: str


def build_mfrr_replay_request(
    *,
    request_id: str,
    semantics_version: str,
    battery: BatteryComponent,
    initial_state: BatteryState,
    capability: RestorationCapability,
    commitments: DirectionalCapacitySchedule,
    baseline: RestorationEnergyBaselineSchedule,
    activation_sequence: MFRRActivationSequence,
    integration_grid: RestorationIntegrationGrid,
    tolerance: float = DEFAULT_RESTORATION_REPLAY_TOLERANCE,
) -> MFRRReplayRequest:
    """Validate exact mFRR types, horizon, grid boundaries, and fingerprints."""

    if type(activation_sequence) is not MFRRActivationSequence:
        raise RestorationReplayValidationError(
            "activation_sequence must be exactly an MFRRActivationSequence"
        )
    if not isinstance(integration_grid, RestorationIntegrationGrid):
        raise RestorationReplayValidationError(
            "integration_grid must be a RestorationIntegrationGrid"
        )
    if activation_sequence.period != integration_grid.period:
        raise RestorationReplayValidationError(
            "mFRR event-sequence period must align exactly with the integration grid"
        )
    _validate_mfrr_event_grid(activation_sequence, integration_grid)
    fingerprints = MappingProxyType(
        {
            "activation": activation_sequence.sequence_fingerprint,
            "baseline": getattr(baseline, "schedule_fingerprint", ""),
            "capability": getattr(capability, "capability_fingerprint", ""),
            "commitments": getattr(commitments, "schedule_fingerprint", ""),
        }
    )
    core = build_restoration_replay_request_core(
        request_id=request_id,
        semantics_version=semantics_version,
        product=RestorationProduct.MFRR,
        activation_input_kind=RestorationReplayInputKind.MFRR_EVENT_SEQUENCE,
        battery=battery,
        initial_state=initial_state,
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        integration_grid=integration_grid,
        tolerance=tolerance,
        input_fingerprints=fingerprints,
    )
    payload = {
        "schema_version": MFRR_REPLAY_REQUEST_SCHEMA_VERSION,
        "core_request_fingerprint": core.request_fingerprint,
        "activation_sequence_fingerprint": activation_sequence.sequence_fingerprint,
    }
    return MFRRReplayRequest(
        schema_version=MFRR_REPLAY_REQUEST_SCHEMA_VERSION,
        request_id=core.request_id,
        semantics_version=core.semantics_version,
        battery=core.battery,
        initial_state=core.initial_state,
        capability=core.capability,
        commitments=core.commitments,
        baseline=core.baseline,
        activation_sequence=activation_sequence,
        integration_grid=core.integration_grid,
        tolerance=core.tolerance,
        input_fingerprints=core.input_fingerprints,
        core=core,
        request_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class MFRREventPerformance:
    """Timing, energy, delivery, and non-performance for one exact mFRR event."""

    schema_version: str
    event_id: str
    event_fingerprint: str
    kind: MFRRActivationKind
    direction: RestorationDirection
    sample_count: int
    requested_start_utc: str
    requested_activation_start_utc: str
    requested_completion_utc: str
    actual_start_utc: str | None
    actual_completion_utc: str | None
    actual_response_delay_seconds: float | None
    requested_duration_seconds: float
    delivered_duration_seconds: float
    requested_energy_kwh: float
    delivered_energy_kwh: float
    undelivered_energy_kwh: float
    peak_requested_power_kw: float
    peak_delivered_power_kw: float
    maximum_achieved_ramp_kw_per_second: float
    non_performance_duration_seconds: float
    causes: tuple[str, ...]
    performance_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_fingerprint": self.event_fingerprint,
            "kind": self.kind.value,
            "direction": self.direction.value,
            "sample_count": self.sample_count,
            "requested_start_utc": self.requested_start_utc,
            "requested_activation_start_utc": self.requested_activation_start_utc,
            "requested_completion_utc": self.requested_completion_utc,
            "actual_start_utc": self.actual_start_utc,
            "actual_completion_utc": self.actual_completion_utc,
            "actual_response_delay_seconds": self.actual_response_delay_seconds,
            "requested_duration_seconds": self.requested_duration_seconds,
            "delivered_duration_seconds": self.delivered_duration_seconds,
            "requested_energy_kwh": self.requested_energy_kwh,
            "delivered_energy_kwh": self.delivered_energy_kwh,
            "undelivered_energy_kwh": self.undelivered_energy_kwh,
            "peak_requested_power_kw": self.peak_requested_power_kw,
            "peak_delivered_power_kw": self.peak_delivered_power_kw,
            "maximum_achieved_ramp_kw_per_second": (
                self.maximum_achieved_ramp_kw_per_second
            ),
            "non_performance_duration_seconds": (
                self.non_performance_duration_seconds
            ),
            "causes": list(self.causes),
            "performance_fingerprint": self.performance_fingerprint,
        }


def _utc_boundary(value: object) -> str:
    if not isinstance(value, datetime):
        raise RestorationReplayValidationError("event boundary must be a datetime")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _mfrr_event_performance(
    *,
    event: MFRRActivationEvent,
    indexed_samples: Sequence[tuple[int, RestorationReplaySample]],
    next_zero_at_or_after: Sequence[RestorationReplaySample | None],
    tolerance: float,
) -> MFRREventPerformance:
    selected = tuple(sample for _, sample in indexed_samples)
    if not selected:
        raise RestorationReplayValidationError(
            f"mFRR event {event.event_id} has no expanded replay samples"
        )
    event_samples = tuple(
        item
        for item in selected
        if item.interval.start_utc >= event.complete_interval.start_utc
        and item.interval.end_utc <= event.complete_interval.end_utc
    )
    if (
        not event_samples
        or event_samples[0].interval.start_utc
        != event.complete_interval.start_utc
        or event_samples[-1].interval.end_utc
        != event.complete_interval.end_utc
    ):
        raise RestorationReplayValidationError(
            f"mFRR event {event.event_id} sample coverage is incomplete"
        )
    for previous, current in zip(selected, selected[1:]):
        if current.interval.start_utc != previous.interval.end_utc:
            raise RestorationReplayValidationError(
                f"mFRR event {event.event_id} sample coverage has a gap"
            )
    requested = sum(item.requested_activation_energy_kwh for item in selected)
    if abs(requested - event.requested_energy_kwh) > tolerance:
        raise RestorationReplayValidationError(
            f"mFRR event {event.event_id} expansion does not conserve requested energy"
        )
    delivered = sum(item.delivered_activation_energy_kwh for item in selected)
    undelivered = sum(item.undelivered_activation_energy_kwh for item in selected)
    if abs(requested - (delivered + undelivered)) > tolerance:
        raise RestorationReplayValidationError(
            f"mFRR event {event.event_id} delivery energy does not conserve"
        )
    active_samples = tuple(
        item
        for item in selected
        if item.delivered_activation_energy_kwh > tolerance
    )
    actual_start = (
        None if not active_samples else _utc_boundary(active_samples[0].interval.start_utc)
    )
    tail_samples = tuple(
        (sample_index, item)
        for sample_index, item in indexed_samples
        if item.interval.start_utc >= event.complete_interval.end_utc
    )
    if not active_samples:
        actual_completion = None
    elif not tail_samples:
        actual_completion = event.requested_completion_utc
    else:
        next_index = tail_samples[-1][0] + 1
        completion_candidate = (
            None
            if next_index >= len(next_zero_at_or_after)
            else next_zero_at_or_after[next_index]
        )
        actual_completion = (
            None
            if completion_candidate is None
            else _utc_boundary(completion_candidate.interval.start_utc)
        )
    actual_delay = None
    if active_samples:
        activation_start = event.complete_interval.start_utc
        activation_start += timedelta(seconds=event.activation_delay_seconds)
        actual_delay = max(
            0.0,
            (active_samples[0].interval.start_utc - activation_start).total_seconds(),
        )
    delivered_duration = sum(
        (item.interval.end_utc - item.interval.start_utc).total_seconds()
        for item in active_samples
    )
    delivered_powers = [
        event.direction.magnitude_of(item.delivered_balancing_power_kw)
        for item in selected
    ]
    causes = _ordered_causes(
        tuple(cause for item in selected for cause in item.causes)
    )
    payload = {
        "schema_version": MFRR_EVENT_PERFORMANCE_SCHEMA_VERSION,
        "event_id": event.event_id,
        "event_fingerprint": event.event_fingerprint,
        "kind": event.kind.value,
        "direction": event.direction.value,
        "sample_count": len(selected),
        "requested_start_utc": event.requested_start_utc,
        "requested_activation_start_utc": event.activation_start_utc,
        "requested_completion_utc": event.requested_completion_utc,
        "actual_start_utc": actual_start,
        "actual_completion_utc": actual_completion,
        "actual_response_delay_seconds": actual_delay,
        "requested_duration_seconds": event.total_duration_seconds,
        "delivered_duration_seconds": delivered_duration,
        "requested_energy_kwh": requested,
        "delivered_energy_kwh": delivered,
        "undelivered_energy_kwh": undelivered,
        "peak_requested_power_kw": event.requested_power_kw,
        "peak_delivered_power_kw": max(delivered_powers, default=0.0),
        "maximum_achieved_ramp_kw_per_second": max(
            (item.achieved_ramp_kw_per_second for item in selected),
            default=0.0,
        ),
        "non_performance_duration_seconds": sum(
            item.non_performance_duration_seconds for item in selected
        ),
        "causes": list(causes),
    }
    return MFRREventPerformance(
        schema_version=MFRR_EVENT_PERFORMANCE_SCHEMA_VERSION,
        event_id=event.event_id,
        event_fingerprint=event.event_fingerprint,
        kind=event.kind,
        direction=event.direction,
        sample_count=len(selected),
        requested_start_utc=event.requested_start_utc,
        requested_activation_start_utc=event.activation_start_utc,
        requested_completion_utc=event.requested_completion_utc,
        actual_start_utc=actual_start,
        actual_completion_utc=actual_completion,
        actual_response_delay_seconds=actual_delay,
        requested_duration_seconds=event.total_duration_seconds,
        delivered_duration_seconds=delivered_duration,
        requested_energy_kwh=requested,
        delivered_energy_kwh=delivered,
        undelivered_energy_kwh=undelivered,
        peak_requested_power_kw=event.requested_power_kw,
        peak_delivered_power_kw=max(delivered_powers, default=0.0),
        maximum_achieved_ramp_kw_per_second=float(
            payload["maximum_achieved_ramp_kw_per_second"]
        ),
        non_performance_duration_seconds=float(
            payload["non_performance_duration_seconds"]
        ),
        causes=causes,
        performance_fingerprint=_fingerprint(payload),
    )


def _index_mfrr_replay_samples(
    samples: Sequence[RestorationReplaySample],
    *,
    tolerance: float,
) -> tuple[
    dict[str, tuple[tuple[int, RestorationReplaySample], ...]],
    tuple[RestorationReplaySample | None, ...],
]:
    """Index event-owned samples and later zero-delivery boundaries linearly."""

    grouped: dict[str, list[tuple[int, RestorationReplaySample]]] = {}
    for index, sample in enumerate(samples):
        if sample.event_id is not None:
            grouped.setdefault(sample.event_id, []).append((index, sample))

    next_zero: list[RestorationReplaySample | None] = [None] * (len(samples) + 1)
    candidate: RestorationReplaySample | None = None
    for index in range(len(samples) - 1, -1, -1):
        sample = samples[index]
        if abs(sample.delivered_balancing_power_kw) <= tolerance:
            candidate = sample
        next_zero[index] = candidate
    return (
        {event_id: tuple(values) for event_id, values in grouped.items()},
        tuple(next_zero),
    )


@dataclass(frozen=True, slots=True)
class MFRRPerformanceAggregate:
    """One independently inspectable mFRR kind or direction aggregate."""

    schema_version: str
    aggregate_dimension: str
    aggregate_value: str
    event_count: int
    sample_count: int
    requested_energy_kwh: float
    delivered_energy_kwh: float
    undelivered_energy_kwh: float
    non_performance_duration_seconds: float
    causes: tuple[str, ...]
    aggregate_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "aggregate_dimension": self.aggregate_dimension,
            "aggregate_value": self.aggregate_value,
            "event_count": self.event_count,
            "sample_count": self.sample_count,
            "requested_energy_kwh": self.requested_energy_kwh,
            "delivered_energy_kwh": self.delivered_energy_kwh,
            "undelivered_energy_kwh": self.undelivered_energy_kwh,
            "non_performance_duration_seconds": (
                self.non_performance_duration_seconds
            ),
            "causes": list(self.causes),
            "aggregate_fingerprint": self.aggregate_fingerprint,
        }


def _mfrr_performance_aggregate(
    *,
    aggregate_dimension: str,
    aggregate_value: str,
    performances: Sequence[MFRREventPerformance],
) -> MFRRPerformanceAggregate:
    selected = tuple(performances)
    causes = _ordered_causes(
        tuple(cause for item in selected for cause in item.causes)
    )
    payload = {
        "schema_version": MFRR_AGGREGATE_PERFORMANCE_SCHEMA_VERSION,
        "aggregate_dimension": aggregate_dimension,
        "aggregate_value": aggregate_value,
        "event_count": len(selected),
        "sample_count": sum(item.sample_count for item in selected),
        "requested_energy_kwh": sum(
            item.requested_energy_kwh for item in selected
        ),
        "delivered_energy_kwh": sum(
            item.delivered_energy_kwh for item in selected
        ),
        "undelivered_energy_kwh": sum(
            item.undelivered_energy_kwh for item in selected
        ),
        "non_performance_duration_seconds": sum(
            item.non_performance_duration_seconds for item in selected
        ),
        "causes": list(causes),
    }
    return MFRRPerformanceAggregate(
        schema_version=MFRR_AGGREGATE_PERFORMANCE_SCHEMA_VERSION,
        aggregate_dimension=aggregate_dimension,
        aggregate_value=aggregate_value,
        event_count=int(payload["event_count"]),
        sample_count=int(payload["sample_count"]),
        requested_energy_kwh=float(payload["requested_energy_kwh"]),
        delivered_energy_kwh=float(payload["delivered_energy_kwh"]),
        undelivered_energy_kwh=float(payload["undelivered_energy_kwh"]),
        non_performance_duration_seconds=float(
            payload["non_performance_duration_seconds"]
        ),
        causes=causes,
        aggregate_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class MFRRReplayResult:
    """Immutable event trace with SA/DA, direction, and physical totals."""

    schema_version: str
    request: MFRRReplayRequest
    request_fingerprint: str
    activation_sequence_fingerprint: str
    samples: tuple[RestorationReplaySample, ...]
    event_performance: tuple[MFRREventPerformance, ...]
    kind_performance: Mapping[MFRRActivationKind, MFRRPerformanceAggregate]
    directional_performance: Mapping[
        RestorationDirection, MFRRPerformanceAggregate
    ]
    totals: RestorationEnergyTotals
    causes: tuple[str, ...]
    input_fingerprints: Mapping[str, str]
    core_result_fingerprint: str
    result_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_fingerprint": self.request_fingerprint,
            "activation_sequence_fingerprint": (
                self.activation_sequence_fingerprint
            ),
            "samples": [sample.to_dict() for sample in self.samples],
            "event_performance": [
                item.to_dict() for item in self.event_performance
            ],
            "kind_performance": {
                kind.value: self.kind_performance[kind].to_dict()
                for kind in MFRRActivationKind
            },
            "directional_performance": {
                direction.value: self.directional_performance[direction].to_dict()
                for direction in RestorationDirection
            },
            "totals": self.totals.to_dict(),
            "causes": list(self.causes),
            "input_fingerprints": dict(self.input_fingerprints),
            "core_result_fingerprint": self.core_result_fingerprint,
            "result_fingerprint": self.result_fingerprint,
        }


def replay_mfrr(request: MFRRReplayRequest) -> MFRRReplayResult:
    """Expand and replay boundary-conserving mFRR events deterministically."""

    if type(request) is not MFRRReplayRequest:
        raise RestorationReplayValidationError(
            "request must be exactly an MFRRReplayRequest"
        )
    state = request.initial_state
    previous_combined_power_kw = (
        request.baseline.intervals[0].accepted_baseline_power_kw
    )
    samples: list[RestorationReplaySample] = []
    tail_event: MFRRActivationEvent | None = None
    events = tuple(request.activation_sequence.events)
    expanded_events = _mfrr_events_by_interval(
        events=events,
        intervals=request.integration_grid.intervals,
    )
    commitment_pairs = request.commitments.commitment_pairs_covering(
        request.integration_grid.intervals
    )
    for index, (
        baseline_interval,
        grid_interval,
        event,
        commitment_pair,
    ) in enumerate(
        zip(
            request.baseline.intervals,
            request.integration_grid.intervals,
            expanded_events,
            commitment_pairs,
            strict=True,
        )
    ):
        if baseline_interval.interval != grid_interval:
            raise RestorationReplayValidationError(
                f"mFRR replay inputs do not align at interval {index}"
            )
        requested_power = (
            0.0 if event is None else event.signed_average_power_kw(grid_interval)
        )
        baseline_power = baseline_interval.accepted_baseline_power_kw
        upward, downward = commitment_pair
        interval_seconds = (
            grid_interval.end_utc - grid_interval.start_utc
        ).total_seconds()
        decision = enforce_restoration_capability(
            product=RestorationProduct.MFRR,
            accepted_baseline_power_kw=baseline_power,
            requested_balancing_power_kw=requested_power,
            upward_commitment_kw=upward.committed_capacity_kw,
            downward_commitment_kw=downward.committed_capacity_kw,
            upward_headroom_kw=max(
                0.0, request.battery.max_discharge_kw + baseline_power
            ),
            downward_headroom_kw=max(
                0.0, request.battery.max_charge_kw - baseline_power
            ),
            previous_capability_combined_power_kw=previous_combined_power_kw,
            interval_seconds=interval_seconds,
            capability=request.capability,
            actual_activation_delay_seconds=(
                0.0 if event is None else event.activation_delay_seconds
            ),
            requested_duration_seconds=(
                None if event is None else event.total_duration_seconds
            ),
        )
        identity_event = event
        if (
            identity_event is None
            and tail_event is not None
            and abs(decision.capability_accepted_balancing_power_kw)
            > request.tolerance
        ):
            identity_event = tail_event
        sample = apply_restoration_battery_transition(
            sample_index=index,
            interval=grid_interval,
            product=RestorationProduct.MFRR,
            decision=decision,
            battery=request.battery,
            state=state,
            tolerance=request.tolerance,
            event_id=None if identity_event is None else identity_event.event_id,
            mfrr_kind=None if identity_event is None else identity_event.kind,
        )
        samples.append(sample)
        state = sample.state
        previous_combined_power_kw = sample.delivered_combined_power_kw
        if event is not None:
            tail_event = event
        elif identity_event is None:
            tail_event = None
    normalized_samples = tuple(samples)
    core_result = build_restoration_replay_result_core(
        request=request.core,
        samples=normalized_samples,
    )
    indexed_event_samples, next_zero_at_or_after = _index_mfrr_replay_samples(
        normalized_samples,
        tolerance=request.tolerance,
    )
    event_performance = tuple(
        _mfrr_event_performance(
            event=event,
            indexed_samples=indexed_event_samples.get(event.event_id, ()),
            next_zero_at_or_after=next_zero_at_or_after,
            tolerance=request.tolerance,
        )
        for event in events
    )
    kind_performance = MappingProxyType(
        {
            kind: _mfrr_performance_aggregate(
                aggregate_dimension="kind",
                aggregate_value=kind.value,
                performances=tuple(
                    item for item in event_performance if item.kind is kind
                ),
            )
            for kind in MFRRActivationKind
        }
    )
    directional_performance = MappingProxyType(
        {
            direction: _mfrr_performance_aggregate(
                aggregate_dimension="direction",
                aggregate_value=direction.value,
                performances=tuple(
                    item
                    for item in event_performance
                    if item.direction is direction
                ),
            )
            for direction in RestorationDirection
        }
    )
    event_requested = sum(
        item.requested_energy_kwh for item in event_performance
    )
    event_delivered = sum(
        item.delivered_energy_kwh for item in event_performance
    )
    event_undelivered = sum(
        item.undelivered_energy_kwh for item in event_performance
    )
    if (
        abs(event_requested - core_result.totals.requested_activation_energy_kwh)
        > request.tolerance
        or abs(
            event_delivered - core_result.totals.delivered_activation_energy_kwh
        )
        > request.tolerance
        or abs(
            event_undelivered
            - core_result.totals.undelivered_activation_energy_kwh
        )
        > request.tolerance
    ):
        raise RestorationReplayValidationError(
            "mFRR event and horizon activation energy do not conserve"
        )
    kind_requested = sum(
        item.requested_energy_kwh for item in kind_performance.values()
    )
    direction_requested = sum(
        item.requested_energy_kwh for item in directional_performance.values()
    )
    if (
        abs(kind_requested - event_requested) > request.tolerance
        or abs(direction_requested - event_requested) > request.tolerance
    ):
        raise RestorationReplayValidationError(
            "mFRR kind/direction requested energy does not conserve"
        )
    payload = {
        "schema_version": MFRR_REPLAY_RESULT_SCHEMA_VERSION,
        "request_fingerprint": request.request_fingerprint,
        "activation_sequence_fingerprint": (
            request.activation_sequence.sequence_fingerprint
        ),
        "sample_fingerprints": [
            sample.sample_fingerprint for sample in normalized_samples
        ],
        "event_performance_fingerprints": [
            item.performance_fingerprint for item in event_performance
        ],
        "kind_performance_fingerprints": {
            kind.value: kind_performance[kind].aggregate_fingerprint
            for kind in MFRRActivationKind
        },
        "directional_performance_fingerprints": {
            direction.value: directional_performance[
                direction
            ].aggregate_fingerprint
            for direction in RestorationDirection
        },
        "totals_fingerprint": core_result.totals.totals_fingerprint,
        "causes": list(core_result.causes),
        "input_fingerprints": dict(request.input_fingerprints),
        "core_result_fingerprint": core_result.result_fingerprint,
    }
    return MFRRReplayResult(
        schema_version=MFRR_REPLAY_RESULT_SCHEMA_VERSION,
        request=request,
        request_fingerprint=request.request_fingerprint,
        activation_sequence_fingerprint=(
            request.activation_sequence.sequence_fingerprint
        ),
        samples=normalized_samples,
        event_performance=event_performance,
        kind_performance=kind_performance,
        directional_performance=directional_performance,
        totals=core_result.totals,
        causes=core_result.causes,
        input_fingerprints=request.input_fingerprints,
        core_result_fingerprint=core_result.result_fingerprint,
        result_fingerprint=_fingerprint(payload),
    )


__all__ = [
    "RESTORATION_REPLAY_CORE_SCHEMA_VERSION",
    "RESTORATION_REPLAY_SAMPLE_SCHEMA_VERSION",
    "AFRR_REPLAY_REQUEST_SCHEMA_VERSION",
    "AFRR_REPLAY_RESULT_SCHEMA_VERSION",
    "AFRR_DIRECTIONAL_PERFORMANCE_SCHEMA_VERSION",
    "MFRR_REPLAY_REQUEST_SCHEMA_VERSION",
    "MFRR_REPLAY_RESULT_SCHEMA_VERSION",
    "MFRR_EVENT_PERFORMANCE_SCHEMA_VERSION",
    "MFRR_AGGREGATE_PERFORMANCE_SCHEMA_VERSION",
    "DEFAULT_RESTORATION_REPLAY_TOLERANCE",
    "RESTORATION_CAUSE_ORDER",
    "RestorationReplayInputKind",
    "RestorationReplayValidationError",
    "RestorationIntegrationGrid",
    "RestorationReplayRequestCore",
    "RestorationCapabilityDecision",
    "RestorationReplaySample",
    "RestorationEnergyTotals",
    "RestorationReplayResultCore",
    "AFRRReplayRequest",
    "AFRRDirectionalPerformance",
    "AFRRReplayResult",
    "MFRRReplayRequest",
    "MFRREventPerformance",
    "MFRRPerformanceAggregate",
    "MFRRReplayResult",
    "build_restoration_integration_grid",
    "build_restoration_replay_request_core",
    "enforce_restoration_capability",
    "apply_restoration_battery_transition",
    "aggregate_restoration_samples",
    "build_restoration_replay_result_core",
    "build_afrr_replay_request",
    "replay_afrr",
    "build_mfrr_replay_request",
    "replay_mfrr",
]
