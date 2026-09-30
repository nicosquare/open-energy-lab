"""Deterministic replay of fixed energy and symmetric-FCR schedules.

This module owns schedule eligibility and physical battery replay.  It consumes
already-normalized market and activation artifacts and never owns transport or
bid optimization.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import Any

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import canonical_json_bytes, fingerprint, freeze, thaw
from open_energy_lab.core.time import utc_datetime
from open_energy_lab.core.validation import finite, mapping, non_empty_str, sequence
from open_energy_lab.market.activation import RegulationActivationTrace
from open_energy_lab.market.artifact import MarketDataArtifact
from open_energy_lab.market.time import (
    CanonicalInterval,
    HALF_OPEN_INTERVAL_CONVENTION,
    MultiRateTimeIndex,
    build_multi_rate_index,
)

from .battery import apply_power_request, build_initial_state
from .scenario import BatteryComponent


class StackedServiceValidationError(ValidationError):
    """Raised when fixed schedules or replay inputs violate their contract."""


_finite = partial(finite, error=StackedServiceValidationError)
_non_empty = partial(non_empty_str, error=StackedServiceValidationError, strip=True)
_utc = partial(utc_datetime, error=StackedServiceValidationError)
_mapping = partial(mapping, error=StackedServiceValidationError)
_sequence = partial(sequence, error=StackedServiceValidationError)
_freeze = freeze
_thaw = thaw
_canonical_json = partial(canonical_json_bytes, error=StackedServiceValidationError)
_fingerprint = partial(fingerprint, error=StackedServiceValidationError)


@dataclass(frozen=True, slots=True)
class EnergyBaselineInterval:
    interval: CanonicalInterval
    power_kw: float
    schedule_source: str

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "power_kw": self.power_kw,
            "schedule_source": self.schedule_source,
        }


@dataclass(frozen=True, slots=True)
class EnergyBaselineSchedule:
    schedule_id: str
    semantics_version: str
    covered_period: CanonicalInterval
    intervals: tuple[EnergyBaselineInterval, ...]
    schedule_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "semantics_version": self.semantics_version,
            "covered_period": self.covered_period.to_dict(),
            "intervals": [item.to_dict() for item in self.intervals],
            "schedule_fingerprint": self.schedule_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class FCRCommitmentInterval:
    interval: CanonicalInterval
    capacity_kw: float
    volume_observation_ref: str
    price_observation_ref: str

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "capacity_kw": self.capacity_kw,
            "volume_observation_ref": self.volume_observation_ref,
            "price_observation_ref": self.price_observation_ref,
        }


@dataclass(frozen=True, slots=True)
class FCRCapacitySchedule:
    schedule_id: str
    semantics_version: str
    product_identity: Mapping[str, object]
    covered_period: CanonicalInterval
    intervals: tuple[FCRCommitmentInterval, ...]
    schedule_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "semantics_version": self.semantics_version,
            "product_identity": _thaw(self.product_identity),
            "covered_period": self.covered_period.to_dict(),
            "intervals": [item.to_dict() for item in self.intervals],
            "schedule_fingerprint": self.schedule_fingerprint,
        }


def _schedule_grid(
    *,
    start: datetime,
    end: datetime,
    energy_resolution: str = "PT1H",
    fcr_resolution: str = "PT4H",
) -> MultiRateTimeIndex:
    try:
        return build_multi_rate_index(
            start,
            end,
            activation_resolution=energy_resolution,
            checkpoint_resolution=energy_resolution,
            energy_resolution=energy_resolution,
            fcr_resolution=fcr_resolution,
        )
    except ValueError as exc:
        raise StackedServiceValidationError(
            f"schedule coverage must contain complete aligned product blocks: {exc}"
        ) from exc


def build_energy_baseline_schedule(
    *,
    schedule_id: str,
    semantics_version: str,
    covered_start_utc: datetime,
    covered_end_utc: datetime,
    intervals: Sequence[Mapping[str, object]],
) -> EnergyBaselineSchedule:
    """Build an immutable, complete hourly charge-positive baseline schedule."""

    schedule_id = _non_empty(schedule_id, field_name="schedule_id")
    semantics_version = _non_empty(semantics_version, field_name="semantics_version")
    start = _utc(covered_start_utc, field_name="covered_start_utc")
    end = _utc(covered_end_utc, field_name="covered_end_utc")
    grid = _schedule_grid(start=start, end=end)
    raw_intervals = _sequence(intervals, field_name="intervals")
    if len(raw_intervals) != len(grid.energy_intervals):
        raise StackedServiceValidationError(
            "energy schedule must provide complete hourly coverage without gaps"
        )
    built: list[EnergyBaselineInterval] = []
    allowed_sources = {"fixed", "arbitrage_only", "stacked_heuristic"}
    for index, (raw, expected) in enumerate(zip(raw_intervals, grid.energy_intervals, strict=True)):
        item = _mapping(raw, field_name=f"intervals[{index}]")
        item_start = _utc(item.get("start_utc"), field_name=f"intervals[{index}].start_utc")
        item_end = _utc(item.get("end_utc"), field_name=f"intervals[{index}].end_utc")
        if item_start != expected.start_utc or item_end != expected.end_utc:
            raise StackedServiceValidationError(
                f"energy schedule interval {index} breaks complete hourly coverage"
            )
        source = _non_empty(item.get("schedule_source"), field_name=f"intervals[{index}].schedule_source")
        if source not in allowed_sources:
            raise StackedServiceValidationError(
                f"intervals[{index}].schedule_source is not supported"
            )
        built.append(
            EnergyBaselineInterval(
                interval=expected,
                power_kw=_finite(item.get("power_kw"), field_name=f"intervals[{index}].power_kw"),
                schedule_source=source,
            )
        )
    covered = CanonicalInterval.from_utc(start, end)
    payload = {
        "schedule_id": schedule_id,
        "semantics_version": semantics_version,
        "covered_period": covered.to_dict(),
        "intervals": [item.to_dict() for item in built],
    }
    return EnergyBaselineSchedule(
        schedule_id=schedule_id,
        semantics_version=semantics_version,
        covered_period=covered,
        intervals=tuple(built),
        schedule_fingerprint=_fingerprint(payload),
    )


def build_fcr_capacity_schedule(
    *,
    schedule_id: str,
    semantics_version: str,
    product_identity: Mapping[str, object],
    covered_start_utc: datetime,
    covered_end_utc: datetime,
    intervals: Sequence[Mapping[str, object]],
) -> FCRCapacitySchedule:
    """Build an immutable, complete four-hour symmetric-FCR schedule."""

    schedule_id = _non_empty(schedule_id, field_name="schedule_id")
    semantics_version = _non_empty(semantics_version, field_name="semantics_version")
    identity = _mapping(product_identity, field_name="product_identity")
    required_identity = {
        "product": "symmetric-fcr",
        "tender": "daily",
        "block_duration": "PT4H",
    }
    if identity != required_identity:
        raise StackedServiceValidationError(
            "FCR product identity must declare symmetric-fcr daily PT4H blocks"
        )
    start = _utc(covered_start_utc, field_name="covered_start_utc")
    end = _utc(covered_end_utc, field_name="covered_end_utc")
    grid = _schedule_grid(start=start, end=end)
    raw_intervals = _sequence(intervals, field_name="intervals")
    if len(raw_intervals) != len(grid.fcr_intervals):
        raise StackedServiceValidationError(
            "FCR schedule must provide complete four-hour coverage without gaps"
        )
    built: list[FCRCommitmentInterval] = []
    for index, (raw, expected) in enumerate(zip(raw_intervals, grid.fcr_intervals, strict=True)):
        item = _mapping(raw, field_name=f"intervals[{index}]")
        item_start = _utc(item.get("start_utc"), field_name=f"intervals[{index}].start_utc")
        item_end = _utc(item.get("end_utc"), field_name=f"intervals[{index}].end_utc")
        if item_start != expected.start_utc or item_end != expected.end_utc:
            raise StackedServiceValidationError(
                f"FCR schedule interval {index} breaks complete four-hour coverage"
            )
        capacity = _finite(item.get("capacity_kw"), field_name=f"intervals[{index}].capacity_kw")
        if capacity < 0.0:
            raise StackedServiceValidationError("FCR capacity must be non-negative")
        built.append(
            FCRCommitmentInterval(
                interval=expected,
                capacity_kw=capacity,
                volume_observation_ref=_non_empty(
                    item.get("volume_observation_ref"),
                    field_name=f"intervals[{index}].volume_observation_ref",
                ),
                price_observation_ref=_non_empty(
                    item.get("price_observation_ref"),
                    field_name=f"intervals[{index}].price_observation_ref",
                ),
            )
        )
    covered = CanonicalInterval.from_utc(start, end)
    frozen_identity = _freeze(identity)
    payload = {
        "schedule_id": schedule_id,
        "semantics_version": semantics_version,
        "product_identity": identity,
        "covered_period": covered.to_dict(),
        "intervals": [item.to_dict() for item in built],
    }
    return FCRCapacitySchedule(
        schedule_id=schedule_id,
        semantics_version=semantics_version,
        product_identity=frozen_identity,
        covered_period=covered,
        intervals=tuple(built),
        schedule_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class MultiRateTimeContract:
    start_utc: datetime
    end_utc: datetime
    activation_resolution: str
    state_checkpoint_resolution: str
    energy_resolution: str
    fcr_resolution: str
    market_timezone: str
    interval_convention: str
    index: MultiRateTimeIndex = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.interval_convention != HALF_OPEN_INTERVAL_CONVENTION:
            raise StackedServiceValidationError(
                "time grid interval convention must be start-inclusive/end-exclusive"
            )
        try:
            index = build_multi_rate_index(
                self.start_utc,
                self.end_utc,
                activation_resolution=self.activation_resolution,
                checkpoint_resolution=self.state_checkpoint_resolution,
                energy_resolution=self.energy_resolution,
                fcr_resolution=self.fcr_resolution,
                market_timezone=self.market_timezone,
            )
        except ValueError as exc:
            raise StackedServiceValidationError(f"invalid multi-rate time grid: {exc}") from exc
        object.__setattr__(self, "start_utc", index.activation_intervals[0].start_utc)
        object.__setattr__(self, "end_utc", index.activation_intervals[-1].end_utc)
        object.__setattr__(self, "index", index)

    def to_dict(self) -> dict[str, object]:
        return {
            "start_utc": self.start_utc.isoformat().replace("+00:00", "Z"),
            "end_utc": self.end_utc.isoformat().replace("+00:00", "Z"),
            "activation_resolution": self.activation_resolution,
            "state_checkpoint_resolution": self.state_checkpoint_resolution,
            "energy_resolution": self.energy_resolution,
            "fcr_resolution": self.fcr_resolution,
            "market_timezone": self.market_timezone,
            "interval_convention": self.interval_convention,
        }


def _same_bounds(interval: CanonicalInterval, expected: CanonicalInterval) -> bool:
    return (
        interval.start_utc == expected.start_utc
        and interval.end_utc == expected.end_utc
    )


def _require_schedule_alignment(
    schedule_intervals: Sequence[EnergyBaselineInterval | FCRCommitmentInterval],
    grid_intervals: Sequence[CanonicalInterval],
    *,
    label: str,
) -> None:
    if len(schedule_intervals) != len(grid_intervals) or any(
        not _same_bounds(actual.interval, expected)
        for actual, expected in zip(schedule_intervals, grid_intervals, strict=False)
    ):
        raise StackedServiceValidationError(
            f"{label} schedule coverage must exactly match the replay horizon"
        )


def _observation_from_ref(
    artifact: MarketDataArtifact,
    reference: str,
    *,
    expected_series: str,
) -> Any:
    prefix, separator, raw_index = reference.partition(":")
    if prefix != expected_series or separator != ":":
        raise StackedServiceValidationError(
            f"{expected_series} observation reference is not aligned"
        )
    try:
        index = int(raw_index)
        observation = artifact.series[expected_series].observations[index]
    except (ValueError, IndexError, KeyError) as exc:
        raise StackedServiceValidationError(
            f"{expected_series} observation reference is not aligned"
        ) from exc
    return observation


def _validate_commitments(
    *,
    artifact: MarketDataArtifact,
    battery: BatteryComponent,
    energy_schedule: EnergyBaselineSchedule,
    fcr_schedule: FCRCapacitySchedule,
    time_contract: MultiRateTimeContract,
) -> tuple[str, ...]:
    failures: list[str] = []
    index = time_contract.index
    for fcr_index, commitment in enumerate(fcr_schedule.intervals):
        try:
            volume = _observation_from_ref(
                artifact,
                commitment.volume_observation_ref,
                expected_series="fcr_contracted_volume",
            )
            price = _observation_from_ref(
                artifact,
                commitment.price_observation_ref,
                expected_series="fcr_capacity_price",
            )
            if not _same_bounds(volume.interval, commitment.interval):
                raise StackedServiceValidationError(
                    "FCR volume observation reference is not aligned"
                )
            if not _same_bounds(price.interval, commitment.interval):
                raise StackedServiceValidationError(
                    "FCR price observation reference is not aligned"
                )
            if commitment.capacity_kw / 1000.0 > volume.value:
                raise StackedServiceValidationError(
                    "FCR capacity exceeds aligned contracted market volume in MW"
                )
        except StackedServiceValidationError as exc:
            failures.append(str(exc))

        energy_indices = {
            index.activation_to_energy[activation_index]
            for activation_index, mapped_fcr in enumerate(index.activation_to_fcr)
            if mapped_fcr == fcr_index
        }
        for energy_index in sorted(energy_indices):
            baseline = energy_schedule.intervals[energy_index].power_kw
            if baseline + commitment.capacity_kw > battery.max_charge_kw:
                failures.append(
                    f"energy interval {energy_index} lacks charge power headroom"
                )
            if baseline - commitment.capacity_kw < -battery.max_discharge_kw:
                failures.append(
                    f"energy interval {energy_index} lacks discharge power headroom"
                )
    return tuple(failures)


@dataclass(frozen=True, slots=True)
class TerminalSOCTarget:
    """A report-only terminal stored-energy or SOC-fraction target."""

    target_kind: str
    target_value: float
    tolerance: float

    def __post_init__(self) -> None:
        if self.target_kind not in {"stored_energy_kwh", "soc_fraction"}:
            raise StackedServiceValidationError(
                "terminal target kind must be stored_energy_kwh or soc_fraction"
            )
        value = _finite(self.target_value, field_name="terminal target value")
        tolerance = _finite(self.tolerance, field_name="terminal target tolerance")
        if tolerance < 0.0:
            raise StackedServiceValidationError(
                "terminal target tolerance must be non-negative"
            )
        if self.target_kind == "soc_fraction" and not 0.0 <= value <= 1.0:
            raise StackedServiceValidationError(
                "terminal SOC-fraction target must be in [0, 1]"
            )
        if self.target_kind == "stored_energy_kwh" and value < 0.0:
            raise StackedServiceValidationError(
                "terminal stored-energy target must be non-negative"
            )
        object.__setattr__(self, "target_value", value)
        object.__setattr__(self, "tolerance", tolerance)

    def to_dict(self) -> dict[str, object]:
        return {
            "target_kind": self.target_kind,
            "target_value": self.target_value,
            "tolerance": self.tolerance,
        }


@dataclass(frozen=True, slots=True)
class StackedServiceReplayRequest:
    market_artifact: MarketDataArtifact
    activation_trace: RegulationActivationTrace
    battery: BatteryComponent
    energy_schedule: EnergyBaselineSchedule
    fcr_schedule: FCRCapacitySchedule
    time_contract: MultiRateTimeContract
    penalty_rule: object | None
    terminal_soc_target: object | None
    numeric_tolerance: float
    simulation_semantics_version: str
    commitment_validation_mode: str = "strict"
    commitment_validation_errors: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.market_artifact, MarketDataArtifact):
            raise StackedServiceValidationError(
                "market_artifact must be one validated MarketDataArtifact"
            )
        if not isinstance(self.activation_trace, RegulationActivationTrace):
            raise StackedServiceValidationError(
                "activation_trace must be one validated RegulationActivationTrace"
            )
        if not isinstance(self.battery, BatteryComponent):
            raise StackedServiceValidationError(
                "replay requires exactly one BatteryComponent battery"
            )
        if not isinstance(self.energy_schedule, EnergyBaselineSchedule):
            raise StackedServiceValidationError("energy_schedule has the wrong type")
        if not isinstance(self.fcr_schedule, FCRCapacitySchedule):
            raise StackedServiceValidationError("fcr_schedule has the wrong type")
        if not isinstance(self.time_contract, MultiRateTimeContract):
            raise StackedServiceValidationError("time_contract has the wrong type")
        tolerance = _finite(self.numeric_tolerance, field_name="numeric_tolerance")
        if tolerance <= 0.0:
            raise StackedServiceValidationError("numeric_tolerance must be positive")
        semantics = _non_empty(
            self.simulation_semantics_version,
            field_name="simulation_semantics_version",
        )
        if self.commitment_validation_mode not in {"strict", "diagnostic"}:
            raise StackedServiceValidationError(
                "commitment_validation_mode must be strict or diagnostic"
            )
        if self.terminal_soc_target is not None and not isinstance(
            self.terminal_soc_target, TerminalSOCTarget
        ):
            raise StackedServiceValidationError(
                "terminal_soc_target must be a TerminalSOCTarget or None"
            )
        if (
            isinstance(self.terminal_soc_target, TerminalSOCTarget)
            and self.terminal_soc_target.target_kind == "stored_energy_kwh"
            and self.terminal_soc_target.target_value > self.battery.capacity_kwh
        ):
            raise StackedServiceValidationError(
                "terminal stored-energy target exceeds battery capacity"
            )
        index = self.time_contract.index
        artifact_period = self.market_artifact.actual_covered_period
        if (
            artifact_period.start_utc > self.time_contract.start_utc
            or artifact_period.end_utc < self.time_contract.end_utc
        ):
            raise StackedServiceValidationError(
                "market artifact coverage does not contain the exact replay horizon"
            )
        activation_period = self.activation_trace.covered_period
        if (
            activation_period.start_utc != self.time_contract.start_utc
            or activation_period.end_utc != self.time_contract.end_utc
            or self.activation_trace.resolution != self.time_contract.activation_resolution
            or len(self.activation_trace.samples) != len(index.activation_intervals)
            or any(
                not _same_bounds(sample.interval, expected)
                for sample, expected in zip(
                    self.activation_trace.samples,
                    index.activation_intervals,
                    strict=False,
                )
            )
        ):
            raise StackedServiceValidationError(
                "activation coverage and resolution must exactly match the replay horizon"
            )
        _require_schedule_alignment(
            self.energy_schedule.intervals,
            index.energy_intervals,
            label="energy",
        )
        _require_schedule_alignment(
            self.fcr_schedule.intervals,
            index.fcr_intervals,
            label="FCR",
        )
        failures = _validate_commitments(
            artifact=self.market_artifact,
            battery=self.battery,
            energy_schedule=self.energy_schedule,
            fcr_schedule=self.fcr_schedule,
            time_contract=self.time_contract,
        )
        if failures and self.commitment_validation_mode == "strict":
            raise StackedServiceValidationError("; ".join(failures))
        object.__setattr__(self, "numeric_tolerance", tolerance)
        object.__setattr__(self, "simulation_semantics_version", semantics)
        object.__setattr__(self, "commitment_validation_errors", failures)


@dataclass(frozen=True, slots=True)
class ReplaySample:
    """One activation-resolution physical and regulation audit record."""

    interval: CanonicalInterval
    energy_interval_ref: str
    fcr_interval_ref: str
    baseline_power_kw: float
    fcr_capacity_kw: float
    activation: float
    requested_fcr_power_kw: float
    requested_combined_power_kw: float
    delivered_combined_power_kw: float
    delivered_fcr_power_kw: float
    baseline_delivery_error_kw: float
    signed_tracking_error_kw: float
    absolute_tracking_error_kw: float
    non_delivery_energy_kwh: float
    charge_energy_kwh: float
    discharge_energy_kwh: float
    stored_energy_before_kwh: float
    stored_energy_after_kwh: float
    soc_before: float
    soc_after: float
    saturation_causes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "energy_interval_ref": self.energy_interval_ref,
            "fcr_interval_ref": self.fcr_interval_ref,
            "baseline_power_kw": self.baseline_power_kw,
            "fcr_capacity_kw": self.fcr_capacity_kw,
            "activation": self.activation,
            "requested_fcr_power_kw": self.requested_fcr_power_kw,
            "requested_combined_power_kw": self.requested_combined_power_kw,
            "delivered_combined_power_kw": self.delivered_combined_power_kw,
            "delivered_fcr_power_kw": self.delivered_fcr_power_kw,
            "baseline_delivery_error_kw": self.baseline_delivery_error_kw,
            "signed_tracking_error_kw": self.signed_tracking_error_kw,
            "absolute_tracking_error_kw": self.absolute_tracking_error_kw,
            "non_delivery_energy_kwh": self.non_delivery_energy_kwh,
            "charge_energy_kwh": self.charge_energy_kwh,
            "discharge_energy_kwh": self.discharge_energy_kwh,
            "stored_energy_before_kwh": self.stored_energy_before_kwh,
            "stored_energy_after_kwh": self.stored_energy_after_kwh,
            "soc_before": self.soc_before,
            "soc_after": self.soc_after,
            "saturation_causes": list(self.saturation_causes),
        }


@dataclass(frozen=True, slots=True)
class StateCheckpoint:
    timestamp_utc: datetime
    sample_index: int
    soc: float
    stored_energy_kwh: float

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat().replace("+00:00", "Z"),
            "sample_index": self.sample_index,
            "soc": self.soc,
            "stored_energy_kwh": self.stored_energy_kwh,
        }


@dataclass(frozen=True, slots=True)
class ReplayIntervalSummary:
    interval: CanonicalInterval
    charge_energy_kwh: float
    discharge_energy_kwh: float
    net_terminal_energy_kwh: float
    non_delivery_energy_kwh: float

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "charge_energy_kwh": self.charge_energy_kwh,
            "discharge_energy_kwh": self.discharge_energy_kwh,
            "net_terminal_energy_kwh": self.net_terminal_energy_kwh,
            "non_delivery_energy_kwh": self.non_delivery_energy_kwh,
        }


@dataclass(frozen=True, slots=True)
class SaturationEvent:
    event_id: str
    cause: str
    start_utc: datetime
    end_utc: datetime
    sample_count: int
    duration_hours: float
    maximum_power_error_kw: float
    undelivered_energy_kwh: float

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "cause": self.cause,
            "start_utc": self.start_utc.isoformat().replace("+00:00", "Z"),
            "end_utc": self.end_utc.isoformat().replace("+00:00", "Z"),
            "sample_count": self.sample_count,
            "duration_hours": self.duration_hours,
            "maximum_power_error_kw": self.maximum_power_error_kw,
            "undelivered_energy_kwh": self.undelivered_energy_kwh,
        }


@dataclass(frozen=True, slots=True)
class TerminalSOCReport:
    target_kind: str
    target_value: float
    realized_value: float
    signed_deviation: float
    absolute_deviation: float
    tolerance: float
    compliant: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "target_kind": self.target_kind,
            "target_value": self.target_value,
            "realized_value": self.realized_value,
            "signed_deviation": self.signed_deviation,
            "absolute_deviation": self.absolute_deviation,
            "tolerance": self.tolerance,
            "compliant": self.compliant,
        }


@dataclass(frozen=True, slots=True)
class StackedServiceReplayResult:
    simulation_semantics_version: str
    validation_status: str
    input_fingerprints: Mapping[str, object]
    samples: tuple[ReplaySample, ...]
    state_checkpoints: tuple[StateCheckpoint, ...]
    checkpoint_summaries: tuple[ReplayIntervalSummary, ...]
    energy_summaries: tuple[ReplayIntervalSummary, ...]
    fcr_summaries: tuple[ReplayIntervalSummary, ...]
    saturation_events: tuple[SaturationEvent, ...]
    tracking_summary: Mapping[str, object]
    throughput_kwh: float
    settlement: object
    terminal_soc_report: TerminalSOCReport | None
    trace_fingerprint: str
    result_fingerprint: str


@dataclass(frozen=True, slots=True)
class _PhysicalReplayInputs:
    """Source-independent inputs to the one shared fixed-schedule replay kernel."""

    activation_trace: RegulationActivationTrace
    battery: BatteryComponent
    energy_schedule: EnergyBaselineSchedule
    fcr_schedule: FCRCapacitySchedule
    time_contract: MultiRateTimeContract
    numeric_tolerance: float
    terminal_soc_target: TerminalSOCTarget | None


@dataclass(frozen=True, slots=True)
class _PhysicalReplayKernelResult:
    samples: tuple[ReplaySample, ...]
    state_checkpoints: tuple[StateCheckpoint, ...]
    checkpoint_summaries: tuple[ReplayIntervalSummary, ...]
    energy_summaries: tuple[ReplayIntervalSummary, ...]
    fcr_summaries: tuple[ReplayIntervalSummary, ...]
    saturation_events: tuple[SaturationEvent, ...]
    tracking_summary: Mapping[str, object]
    throughput_kwh: float
    terminal_soc_report: TerminalSOCReport | None


def _input_fingerprints(request: StackedServiceReplayRequest) -> Mapping[str, object]:
    penalty_payload = (
        None
        if request.penalty_rule is None
        else request.penalty_rule.to_dict()
        if hasattr(request.penalty_rule, "to_dict")
        else repr(request.penalty_rule)
    )
    terminal_payload = (
        None
        if request.terminal_soc_target is None
        else request.terminal_soc_target.to_dict()
    )
    payload = {
        "market_artifact": request.market_artifact.artifact_fingerprint,
        "activation_trace": request.activation_trace.artifact_fingerprint,
        "energy_schedule": request.energy_schedule.schedule_fingerprint,
        "fcr_schedule": request.fcr_schedule.schedule_fingerprint,
        "battery": _fingerprint(request.battery.to_dict()),
        "time_contract": _fingerprint(request.time_contract.to_dict()),
        "penalty_rule": None if penalty_payload is None else _fingerprint(penalty_payload),
        "terminal_soc_target": (
            None if terminal_payload is None else _fingerprint(terminal_payload)
        ),
        "numeric_tolerance": request.numeric_tolerance,
        "simulation_semantics_version": request.simulation_semantics_version,
    }
    return _freeze(payload)


def _saturation_causes(
    *,
    inputs: _PhysicalReplayInputs,
    requested_power_kw: float,
    delivered_power_kw: float,
    stored_before_kwh: float,
    stored_after_kwh: float,
) -> tuple[str, ...]:
    battery = inputs.battery
    tolerance = inputs.numeric_tolerance
    causes: list[str] = []
    if requested_power_kw > battery.max_charge_kw + tolerance:
        causes.append("charge_power_limit")
    if requested_power_kw < -battery.max_discharge_kw - tolerance:
        causes.append("discharge_power_limit")
    power_clamped = max(
        -battery.max_discharge_kw,
        min(battery.max_charge_kw, requested_power_kw),
    )
    if power_clamped < 0.0 and delivered_power_kw > power_clamped + tolerance:
        minimum_kwh = battery.min_soc * battery.capacity_kwh
        if stored_before_kwh <= minimum_kwh + tolerance or stored_after_kwh <= minimum_kwh + tolerance:
            causes.append("minimum_soc_limit")
    if power_clamped > 0.0 and delivered_power_kw < power_clamped - tolerance:
        maximum_kwh = battery.max_soc * battery.capacity_kwh
        if stored_before_kwh >= maximum_kwh - tolerance or stored_after_kwh >= maximum_kwh - tolerance:
            causes.append("maximum_soc_limit")
    order = {
        "charge_power_limit": 0,
        "discharge_power_limit": 1,
        "minimum_soc_limit": 2,
        "maximum_soc_limit": 3,
    }
    return tuple(sorted(causes, key=order.__getitem__))


def _physical_samples(inputs: _PhysicalReplayInputs) -> tuple[ReplaySample, ...]:
    index = inputs.time_contract.index
    duration_hours = (
        index.activation_intervals[0].end_utc
        - index.activation_intervals[0].start_utc
    ).total_seconds() / 3600.0
    state = build_initial_state(inputs.battery)
    samples: list[ReplaySample] = []
    for sample_index, (activation_sample, interval) in enumerate(
        zip(inputs.activation_trace.samples, index.activation_intervals, strict=True)
    ):
        energy_index = index.activation_to_energy[sample_index]
        fcr_index = index.activation_to_fcr[sample_index]
        baseline = inputs.energy_schedule.intervals[energy_index].power_kw
        capacity = inputs.fcr_schedule.intervals[fcr_index].capacity_kw
        requested_fcr = -activation_sample.activation * capacity
        requested_combined = baseline + requested_fcr
        stored_before = state.stored_energy_kwh
        soc_before = state.soc
        transition = apply_power_request(
            component=inputs.battery,
            state=state,
            requested_power_kw=requested_combined,
            time_step_hours=duration_hours,
            step_index=sample_index,
        )
        delivered_combined = transition.realized_power_kw
        state = transition.state
        if capacity == 0.0:
            delivered_fcr = 0.0
            signed_tracking = 0.0
            baseline_error = baseline - delivered_combined
        else:
            delivered_fcr = delivered_combined - baseline
            signed_tracking = requested_fcr - delivered_fcr
            baseline_error = 0.0
        absolute_tracking = abs(signed_tracking)
        causes = _saturation_causes(
            inputs=inputs,
            requested_power_kw=requested_combined,
            delivered_power_kw=delivered_combined,
            stored_before_kwh=stored_before,
            stored_after_kwh=state.stored_energy_kwh,
        )
        samples.append(
            ReplaySample(
                interval=interval,
                energy_interval_ref=f"energy:{energy_index}",
                fcr_interval_ref=f"fcr:{fcr_index}",
                baseline_power_kw=baseline,
                fcr_capacity_kw=capacity,
                activation=activation_sample.activation,
                requested_fcr_power_kw=requested_fcr,
                requested_combined_power_kw=requested_combined,
                delivered_combined_power_kw=delivered_combined,
                delivered_fcr_power_kw=delivered_fcr,
                baseline_delivery_error_kw=baseline_error,
                signed_tracking_error_kw=signed_tracking,
                absolute_tracking_error_kw=absolute_tracking,
                non_delivery_energy_kwh=absolute_tracking * duration_hours,
                charge_energy_kwh=max(delivered_combined, 0.0) * duration_hours,
                discharge_energy_kwh=max(-delivered_combined, 0.0) * duration_hours,
                stored_energy_before_kwh=stored_before,
                stored_energy_after_kwh=state.stored_energy_kwh,
                soc_before=soc_before,
                soc_after=state.soc,
                saturation_causes=causes,
            )
        )
    return tuple(samples)


def _terminal_report(
    inputs: _PhysicalReplayInputs,
    samples: Sequence[ReplaySample],
) -> TerminalSOCReport | None:
    target = inputs.terminal_soc_target
    if target is None:
        return None
    if target.target_kind == "stored_energy_kwh":
        realized = samples[-1].stored_energy_after_kwh
    else:
        realized = samples[-1].soc_after
    signed = realized - target.target_value
    return TerminalSOCReport(
        target_kind=target.target_kind,
        target_value=target.target_value,
        realized_value=realized,
        signed_deviation=signed,
        absolute_deviation=abs(signed),
        tolerance=target.tolerance,
        compliant=abs(signed) <= target.tolerance,
    )


def _summary_row(
    interval: CanonicalInterval,
    values: tuple[list[float], list[float], list[float]],
) -> ReplayIntervalSummary:
    """Finalize one group with plain ``sum`` so persisted replay payloads keep their JSON types."""

    charge = sum(values[0])
    discharge = sum(values[1])
    return ReplayIntervalSummary(
        interval=interval,
        charge_energy_kwh=charge,
        discharge_energy_kwh=discharge,
        net_terminal_energy_kwh=charge - discharge,
        non_delivery_energy_kwh=sum(values[2]),
    )


def _aggregate_physical_samples(
    inputs: _PhysicalReplayInputs,
    samples: Sequence[ReplaySample],
) -> _PhysicalReplayKernelResult:
    """Aggregate replay output in one pass over activation samples."""

    index = inputs.time_contract.index
    grouped_values: dict[str, tuple[list[float], list[float], list[float]]] = {
        "checkpoint": ([], [], []),
        "energy": ([], [], []),
        "fcr": ([], [], []),
    }
    grouped_summaries: dict[str, list[ReplayIntervalSummary]] = {
        "checkpoint": [],
        "energy": [],
        "fcr": [],
    }
    checkpoints = [
        StateCheckpoint(
            timestamp_utc=inputs.time_contract.start_utc,
            sample_index=0,
            soc=inputs.battery.initial_soc,
            stored_energy_kwh=(
                inputs.battery.initial_soc * inputs.battery.capacity_kwh
            ),
        )
    ]
    aggregate_values: list[tuple[float, float, float, float, float, bool]] = []
    saturation_sample_count = 0
    # Keep the canonical JSON type stable for fingerprints: ``sum(...)`` returns
    # the integer zero when no sample saturated and a float otherwise.
    saturation_duration_hours: int | float = 0
    active_events: dict[str, dict[str, object]] = {}
    closed_events: list[dict[str, object]] = []

    for sample_index, sample in enumerate(samples):
        checkpoint_index = index.activation_to_checkpoint[sample_index]
        energy_index = index.activation_to_energy[sample_index]
        fcr_index = index.activation_to_fcr[sample_index]
        for values in grouped_values.values():
            values[0].append(sample.charge_energy_kwh)
            values[1].append(sample.discharge_energy_kwh)
            values[2].append(sample.non_delivery_energy_kwh)
        aggregate_values.append(
            (
                sample.charge_energy_kwh,
                sample.discharge_energy_kwh,
                sample.signed_tracking_error_kw,
                sample.absolute_tracking_error_kw,
                sample.non_delivery_energy_kwh,
                bool(sample.saturation_causes),
            )
        )

        duration_hours = (
            sample.interval.end_utc - sample.interval.start_utc
        ).total_seconds() / 3600.0
        current_causes = set(sample.saturation_causes)
        if current_causes:
            saturation_sample_count += 1
            saturation_duration_hours += duration_hours
        for cause in tuple(active_events):
            if cause not in current_causes:
                closed_events.append(active_events.pop(cause))
        power_error = abs(
            sample.requested_combined_power_kw - sample.delivered_combined_power_kw
        )
        for cause in sample.saturation_causes:
            event = active_events.setdefault(
                cause,
                {
                    "cause": cause,
                    "start_index": sample_index,
                    "end_index": sample_index,
                    "start_utc": sample.interval.start_utc,
                    "end_utc": sample.interval.end_utc,
                    "sample_count": 0,
                    "maximum_power_error_kw": 0.0,
                    "undelivered_energy_kwh": 0.0,
                },
            )
            event["end_index"] = sample_index
            event["end_utc"] = sample.interval.end_utc
            event["sample_count"] = int(event["sample_count"]) + 1
            event["maximum_power_error_kw"] = max(
                float(event["maximum_power_error_kw"]),
                power_error,
            )
            event["undelivered_energy_kwh"] = (
                float(event["undelivered_energy_kwh"])
                + sample.non_delivery_energy_kwh
            )

        next_checkpoint = (
            None
            if sample_index + 1 == len(samples)
            else index.activation_to_checkpoint[sample_index + 1]
        )
        next_energy = (
            None
            if sample_index + 1 == len(samples)
            else index.activation_to_energy[sample_index + 1]
        )
        next_fcr = (
            None
            if sample_index + 1 == len(samples)
            else index.activation_to_fcr[sample_index + 1]
        )
        for label, current_index, next_index, intervals in (
            (
                "checkpoint",
                checkpoint_index,
                next_checkpoint,
                index.checkpoint_intervals,
            ),
            ("energy", energy_index, next_energy, index.energy_intervals),
            ("fcr", fcr_index, next_fcr, index.fcr_intervals),
        ):
            if next_index != current_index:
                grouped_summaries[label].append(
                    _summary_row(intervals[current_index], grouped_values[label])
                )
                grouped_values[label] = ([], [], [])
        if next_checkpoint != checkpoint_index:
            checkpoints.append(
                StateCheckpoint(
                    timestamp_utc=index.checkpoint_intervals[
                        checkpoint_index
                    ].end_utc,
                    sample_index=sample_index + 1,
                    soc=sample.soc_after,
                    stored_energy_kwh=sample.stored_energy_after_kwh,
                )
            )

    closed_events.extend(active_events.values())
    cause_order = {
        "charge_power_limit": 0,
        "discharge_power_limit": 1,
        "minimum_soc_limit": 2,
        "maximum_soc_limit": 3,
    }
    closed_events.sort(
        key=lambda event: (
            int(event["start_index"]),
            cause_order[str(event["cause"])],
            int(event["end_index"]),
        )
    )
    events = tuple(
        SaturationEvent(
            event_id=f"saturation-{event_index:04d}",
            cause=str(event["cause"]),
            start_utc=event["start_utc"],
            end_utc=event["end_utc"],
            sample_count=int(event["sample_count"]),
            duration_hours=(
                event["end_utc"] - event["start_utc"]
            ).total_seconds()
            / 3600.0,
            maximum_power_error_kw=float(event["maximum_power_error_kw"]),
            undelivered_energy_kwh=float(event["undelivered_energy_kwh"]),
        )
        for event_index, event in enumerate(closed_events)
    )
    checkpoint_summaries = tuple(grouped_summaries["checkpoint"])
    energy_summaries = tuple(grouped_summaries["energy"])
    fcr_summaries = tuple(grouped_summaries["fcr"])
    charge_energy = sum(item[0] for item in aggregate_values)
    discharge_energy = sum(item[1] for item in aggregate_values)
    for label, summaries in (
        ("checkpoint", checkpoint_summaries),
        ("energy", energy_summaries),
        ("FCR", fcr_summaries),
    ):
        grouped_charge = sum(item.charge_energy_kwh for item in summaries)
        grouped_discharge = sum(item.discharge_energy_kwh for item in summaries)
        if (
            abs(grouped_charge - charge_energy) > inputs.numeric_tolerance
            or abs(grouped_discharge - discharge_energy) > inputs.numeric_tolerance
        ):
            raise StackedServiceValidationError(
                f"{label} aggregation does not conserve terminal energy"
            )
    return _PhysicalReplayKernelResult(
        samples=samples if isinstance(samples, tuple) else tuple(samples),
        state_checkpoints=tuple(checkpoints),
        checkpoint_summaries=checkpoint_summaries,
        energy_summaries=energy_summaries,
        fcr_summaries=fcr_summaries,
        saturation_events=events,
        tracking_summary=_freeze(
            {
                "signed_tracking_error_kw_sum": sum(
                    item[2] for item in aggregate_values
                ),
                "absolute_tracking_error_kw_sum": sum(
                    item[3] for item in aggregate_values
                ),
                "non_delivery_energy_kwh": sum(
                    item[4] for item in aggregate_values
                ),
                "saturation_sample_count": saturation_sample_count,
                "saturation_duration_hours": saturation_duration_hours,
                "saturation_event_count": len(events),
            }
        ),
        throughput_kwh=charge_energy + discharge_energy,
        terminal_soc_report=_terminal_report(inputs, samples),
    )


def _replay_physical_kernel(
    inputs: _PhysicalReplayInputs,
) -> _PhysicalReplayKernelResult:
    """Run the shared battery/replay path without market or settlement semantics."""

    samples = _physical_samples(inputs)
    return _aggregate_physical_samples(inputs, samples)


def _run_replay(
    request: StackedServiceReplayRequest,
    *,
    diagnostic: bool,
) -> StackedServiceReplayResult:
    if not isinstance(request, StackedServiceReplayRequest):
        raise StackedServiceValidationError(
            "request must be a StackedServiceReplayRequest"
        )
    if request.commitment_validation_errors and not diagnostic:
        raise StackedServiceValidationError(
            "; ".join(request.commitment_validation_errors)
        )
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
    from .fcr_settlement import settle_stacked_services

    settlement = settle_stacked_services(request, physical.samples)
    inputs = _input_fingerprints(request)
    trace_payload = {
        "samples": [sample.to_dict() for sample in physical.samples],
        "state_checkpoints": [
            item.to_dict() for item in physical.state_checkpoints
        ],
        "saturation_events": [
            item.to_dict() for item in physical.saturation_events
        ],
    }
    trace_fingerprint = _fingerprint(trace_payload)
    result_payload = {
        "simulation_semantics_version": request.simulation_semantics_version,
        "validation_status": (
            "commitment_validation_failed"
            if request.commitment_validation_errors
            else "validated"
        ),
        "input_fingerprints": _thaw(inputs),
        "trace_fingerprint": trace_fingerprint,
        "checkpoint_summaries": [
            item.to_dict() for item in physical.checkpoint_summaries
        ],
        "energy_summaries": [
            item.to_dict() for item in physical.energy_summaries
        ],
        "fcr_summaries": [item.to_dict() for item in physical.fcr_summaries],
        "tracking_summary": _thaw(physical.tracking_summary),
        "throughput_kwh": physical.throughput_kwh,
        "settlement": settlement.to_dict(),
        "terminal_soc_report": (
            None
            if physical.terminal_soc_report is None
            else physical.terminal_soc_report.to_dict()
        ),
    }
    return StackedServiceReplayResult(
        simulation_semantics_version=request.simulation_semantics_version,
        validation_status=result_payload["validation_status"],
        input_fingerprints=inputs,
        samples=physical.samples,
        state_checkpoints=physical.state_checkpoints,
        checkpoint_summaries=physical.checkpoint_summaries,
        energy_summaries=physical.energy_summaries,
        fcr_summaries=physical.fcr_summaries,
        saturation_events=physical.saturation_events,
        tracking_summary=physical.tracking_summary,
        throughput_kwh=physical.throughput_kwh,
        settlement=settlement,
        terminal_soc_report=physical.terminal_soc_report,
        trace_fingerprint=trace_fingerprint,
        result_fingerprint=_fingerprint(result_payload),
    )


def replay_stacked_services(
    request: StackedServiceReplayRequest,
) -> StackedServiceReplayResult:
    """Replay a commitment-valid fixed schedule without network or optimization."""

    return _run_replay(request, diagnostic=False)


def replay_stacked_services_diagnostic(
    request: StackedServiceReplayRequest,
) -> StackedServiceReplayResult:
    """Replay an explicitly diagnostic request even when headroom validation failed."""

    return _run_replay(request, diagnostic=True)


__all__ = [
    "EnergyBaselineInterval",
    "EnergyBaselineSchedule",
    "FCRCapacitySchedule",
    "FCRCommitmentInterval",
    "MultiRateTimeContract",
    "ReplayIntervalSummary",
    "ReplaySample",
    "SaturationEvent",
    "StackedServiceReplayRequest",
    "StackedServiceReplayResult",
    "StackedServiceValidationError",
    "StateCheckpoint",
    "TerminalSOCTarget",
    "TerminalSOCReport",
    "build_energy_baseline_schedule",
    "build_fcr_capacity_schedule",
    "replay_stacked_services",
    "replay_stacked_services_diagnostic",
]
