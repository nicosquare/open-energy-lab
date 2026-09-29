"""Product-neutral restoration commitments, baselines, and capabilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any

from open_energy_lab.core.serialization import fingerprint, freeze
from open_energy_lab.core.validation import (
    finite,
    mapping,
    non_empty_str,
    positive,
    sequence,
)
from open_energy_lab.market.restoration_activation import (
    RestorationDirection,
    RestorationProduct,
)
from open_energy_lab.market.time import (
    CanonicalInterval,
    MarketTimeValidationError,
    parse_iso8601_duration,
)
from open_energy_lab.simulator.battery import apply_power_request, build_initial_state
from open_energy_lab.simulator.restoration_contracts import (
    DirectionalCapacityCommitmentInterval,
    DirectionalCapacitySchedule,
    RESTORATION_CAPABILITY_SCHEMA_VERSION,
    RestorationCapability,
    RestorationControlValidationError,
    RestorationEnergyBaselineInterval,
    RestorationEnergyBaselineSchedule,
    _interval,
    _product,
    build_directional_capacity_schedule,
    build_restoration_capability,
    build_restoration_energy_baseline_schedule,
)
from open_energy_lab.simulator.scenario import BatteryComponent


DIRECTIONAL_CAPACITY_SEMANTICS_VERSION = "directional-restoration-capacity-v1"
RESTORATION_BASELINE_SEMANTICS_VERSION = "restoration-energy-baseline-v1"
RESTORATION_BASELINE_CONFIG_SCHEMA_VERSION = "oel.restoration.baseline-config.v1"
AFRR_BASELINE_CONFIG_SCHEMA_VERSION = "oel.restoration.afrr-baseline-config.v1"
MFRR_BASELINE_CONFIG_SCHEMA_VERSION = "oel.restoration.mfrr-baseline-config.v1"
RESTORATION_BASELINE_BUNDLE_SCHEMA_VERSION = "oel.restoration.baseline-bundle.v1"
DEFAULT_RESTORATION_TOLERANCE = 1e-6


class AFRRBaselineMode(str, Enum):
    """Explicit no-lookahead aFRR energy-baseline construction mode."""

    ZERO = "ZERO"
    FIXED = "FIXED"
    DETERMINISTIC_HEADROOM = "DETERMINISTIC_HEADROOM"


class MFRRBaselineMode(str, Enum):
    """Explicit no-lookahead mFRR energy-baseline construction mode."""

    ZERO = "ZERO"
    FIXED = "FIXED"
    DETERMINISTIC_HEADROOM = "DETERMINISTIC_HEADROOM"


_non_empty = partial(non_empty_str, error=RestorationControlValidationError)
_finite = partial(finite, error=RestorationControlValidationError)
_positive = partial(positive, error=RestorationControlValidationError)
_mapping = partial(mapping, error=RestorationControlValidationError)
_sequence = partial(sequence, error=RestorationControlValidationError)
_freeze = freeze
_fingerprint = partial(fingerprint, error=RestorationControlValidationError)


def _plain(value: Any) -> Any:
    if isinstance(value, RestorationProduct | RestorationDirection):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(inner) for key, inner in value.items()}
    if isinstance(value, tuple):
        return [_plain(inner) for inner in value]
    return value


@dataclass(frozen=True, slots=True)
class RestorationBaselineConfig:
    schema_version: str
    config_id: str
    semantics_version: str
    product: RestorationProduct
    period: CanonicalInterval
    resolution: str
    commitments: DirectionalCapacitySchedule
    baseline: RestorationEnergyBaselineSchedule
    battery: BatteryComponent
    capability: RestorationCapability
    parameters: Mapping[str, object]
    tolerance: float
    configuration_fingerprint: str


def _validate_headroom_and_energy(
    *,
    commitments: DirectionalCapacitySchedule,
    baseline: RestorationEnergyBaselineSchedule,
    battery: BatteryComponent,
    capability: RestorationCapability,
    tolerance: float,
    required_duration_seconds: float | None = None,
) -> None:
    state = build_initial_state(battery)
    duration_seconds = (
        capability.max_supported_duration_seconds[commitments.product]
        if required_duration_seconds is None
        else required_duration_seconds
    )
    commitment_pairs = commitments.commitment_pairs_covering(
        tuple(item.interval for item in baseline.intervals)
    )
    for index, (baseline_interval, commitment_pair) in enumerate(
        zip(baseline.intervals, commitment_pairs, strict=True)
    ):
        upward, downward = commitment_pair
        power = baseline_interval.accepted_baseline_power_kw
        maximum_charge_baseline = (
            battery.max_charge_kw - downward.committed_capacity_kw
        )
        minimum_discharge_baseline = (
            -battery.max_discharge_kw + upward.committed_capacity_kw
        )
        if power > maximum_charge_baseline + tolerance:
            raise RestorationControlValidationError(
                f"baseline charge power at interval {index} consumes DOWNWARD "
                "reserved headroom"
            )
        if power < minimum_discharge_baseline - tolerance:
            raise RestorationControlValidationError(
                f"baseline discharge power at interval {index} consumes UPWARD "
                "reserved headroom"
            )
        step_hours = (
            baseline_interval.interval.end_utc
            - baseline_interval.interval.start_utc
        ).total_seconds() / 3600.0
        transition = apply_power_request(
            component=battery,
            state=state,
            requested_power_kw=power,
            time_step_hours=step_hours,
            step_index=index,
        )
        if abs(transition.realized_power_kw - power) > tolerance:
            raise RestorationControlValidationError(
                f"baseline interval {index} is outside usable battery SOC/efficiency energy"
            )
        usable_discharge_output_kwh = min(
            state.available_discharge_kwh,
            transition.state.available_discharge_kwh,
        ) * battery.discharge_efficiency
        usable_charge_input_kwh = min(
            state.available_charge_kwh,
            transition.state.available_charge_kwh,
        ) / battery.charge_efficiency
        upward_required_kwh = (
            upward.committed_capacity_kw * duration_seconds / 3600.0
        )
        downward_required_kwh = (
            downward.committed_capacity_kw * duration_seconds / 3600.0
        )
        if upward_required_kwh > usable_discharge_output_kwh + tolerance:
            raise RestorationControlValidationError(
                f"UPWARD commitment at interval {index} exceeds usable SOC energy "
                "after discharge efficiency"
            )
        if downward_required_kwh > usable_charge_input_kwh + tolerance:
            raise RestorationControlValidationError(
                f"DOWNWARD commitment at interval {index} exceeds usable SOC energy "
                "after charge efficiency"
            )
        state = transition.state


def build_restoration_baseline_config(
    *,
    config_id: str,
    semantics_version: str,
    product: RestorationProduct | str,
    period: CanonicalInterval,
    resolution: str,
    commitments: DirectionalCapacitySchedule,
    baseline: RestorationEnergyBaselineSchedule,
    battery: BatteryComponent,
    capability: RestorationCapability,
    parameters: Mapping[str, object],
    tolerance: float = DEFAULT_RESTORATION_TOLERANCE,
    required_duration_seconds: float | None = None,
) -> RestorationBaselineConfig:
    """Bind fixed control inputs and prove power/SOC headroom without lookahead."""

    normalized_product = _product(product)
    normalized_period = _interval(period, field_name="period")
    if not isinstance(commitments, DirectionalCapacitySchedule):
        raise RestorationControlValidationError(
            "commitments must be a DirectionalCapacitySchedule"
        )
    if not isinstance(baseline, RestorationEnergyBaselineSchedule):
        raise RestorationControlValidationError(
            "baseline must be a RestorationEnergyBaselineSchedule"
        )
    if not isinstance(battery, BatteryComponent):
        raise RestorationControlValidationError("battery must be a BatteryComponent")
    if not isinstance(capability, RestorationCapability):
        raise RestorationControlValidationError(
            "capability must be a RestorationCapability"
        )
    if (
        commitments.product is not normalized_product
        or baseline.product is not normalized_product
    ):
        raise RestorationControlValidationError(
            "commitment and baseline products must match the configuration"
        )
    if commitments.period != normalized_period or baseline.period != normalized_period:
        raise RestorationControlValidationError(
            "commitment and baseline periods must match the configuration"
        )
    normalized_resolution = _non_empty(resolution, field_name="resolution")
    try:
        duration = parse_iso8601_duration(normalized_resolution)
    except MarketTimeValidationError as exc:
        raise RestorationControlValidationError(str(exc)) from exc
    for item in baseline.intervals:
        if item.interval.end_utc - item.interval.start_utc != duration:
            raise RestorationControlValidationError(
                "baseline intervals must match the configuration resolution"
            )
    normalized_tolerance = _positive(tolerance, field_name="tolerance")
    frozen_parameters = _freeze(_mapping(parameters, field_name="parameters"))
    normalized_required_duration = None
    if required_duration_seconds is not None:
        normalized_required_duration = _positive(
            required_duration_seconds,
            field_name="required_duration_seconds",
        )
        minimum_duration = capability.min_supported_duration_seconds[
            normalized_product
        ]
        maximum_duration = capability.max_supported_duration_seconds[
            normalized_product
        ]
        if not minimum_duration <= normalized_required_duration <= maximum_duration:
            raise RestorationControlValidationError(
                f"{normalized_product.value} required duration "
                f"{normalized_required_duration} seconds is outside supported "
                f"duration [{minimum_duration}, {maximum_duration}]"
            )
    _validate_headroom_and_energy(
        commitments=commitments,
        baseline=baseline,
        battery=battery,
        capability=capability,
        tolerance=normalized_tolerance,
        required_duration_seconds=normalized_required_duration,
    )
    payload = {
        "schema_version": RESTORATION_BASELINE_CONFIG_SCHEMA_VERSION,
        "config_id": _non_empty(config_id, field_name="config_id"),
        "semantics_version": _non_empty(
            semantics_version, field_name="semantics_version"
        ),
        "product": normalized_product.value,
        "period": normalized_period.to_dict(),
        "resolution": normalized_resolution,
        "commitments_fingerprint": commitments.schedule_fingerprint,
        "baseline_fingerprint": baseline.schedule_fingerprint,
        "battery": battery.to_dict(),
        "capability_fingerprint": capability.capability_fingerprint,
        "parameters": _plain(frozen_parameters),
        "tolerance": normalized_tolerance,
    }
    if normalized_required_duration is not None:
        payload["required_duration_seconds"] = normalized_required_duration
    return RestorationBaselineConfig(
        schema_version=RESTORATION_BASELINE_CONFIG_SCHEMA_VERSION,
        config_id=str(payload["config_id"]),
        semantics_version=str(payload["semantics_version"]),
        product=normalized_product,
        period=normalized_period,
        resolution=normalized_resolution,
        commitments=commitments,
        baseline=baseline,
        battery=battery,
        capability=capability,
        parameters=frozen_parameters,
        tolerance=normalized_tolerance,
        configuration_fingerprint=_fingerprint(payload),
    )


def build_afrr_directional_capacity_schedule(
    *,
    schedule_id: str,
    semantics_version: str,
    period: CanonicalInterval,
    intervals: Sequence[Mapping[str, object]],
) -> DirectionalCapacitySchedule:
    """Build one exact aFRR upward/downward fixed-capacity schedule."""

    return build_directional_capacity_schedule(
        schedule_id=schedule_id,
        semantics_version=semantics_version,
        product=RestorationProduct.AFRR,
        period=period,
        intervals=intervals,
    )


@dataclass(frozen=True, slots=True)
class AFRRBaselineConfig:
    """Validated aFRR baseline construction inputs with no activation field."""

    schema_version: str
    config_id: str
    semantics_version: str
    period: CanonicalInterval
    resolution: str
    grid_intervals: tuple[CanonicalInterval, ...]
    commitments: DirectionalCapacitySchedule
    battery: BatteryComponent
    capability: RestorationCapability
    mode: AFRRBaselineMode
    fixed_power_kw: tuple[float, ...] | None
    headroom_bias: float
    tolerance: float
    configuration_fingerprint: str


@dataclass(frozen=True, slots=True)
class RestorationBaselineBundle:
    """Accepted product baseline plus validation evidence and identity."""

    schema_version: str
    product: RestorationProduct
    source_configuration_fingerprint: str
    commitments: DirectionalCapacitySchedule
    baseline: RestorationEnergyBaselineSchedule
    validation: RestorationBaselineConfig
    bundle_fingerprint: str


def _afrr_grid(
    period: CanonicalInterval, resolution: str
) -> tuple[CanonicalInterval, ...]:
    try:
        duration = parse_iso8601_duration(resolution)
    except MarketTimeValidationError as exc:
        raise RestorationControlValidationError(str(exc)) from exc
    intervals: list[CanonicalInterval] = []
    cursor = period.start_utc
    while cursor < period.end_utc:
        end = cursor + duration
        if end > period.end_utc:
            raise RestorationControlValidationError(
                "aFRR period must be exactly divisible by resolution"
            )
        intervals.append(
            CanonicalInterval.from_utc(
                cursor,
                end,
                market_timezone=period.market_timezone,
            )
        )
        cursor = end
    if not intervals:
        raise RestorationControlValidationError(
            "aFRR baseline grid must be non-empty"
        )
    return tuple(intervals)


def _afrr_fixed_values(
    value: float | Sequence[float] | None,
    *,
    count: int,
    mode: AFRRBaselineMode,
) -> tuple[float, ...] | None:
    if mode is AFRRBaselineMode.FIXED:
        if value is None:
            raise RestorationControlValidationError(
                "FIXED aFRR baseline requires fixed_power_kw"
            )
        if isinstance(value, bool):
            raise RestorationControlValidationError(
                "fixed_power_kw must be finite fixed values"
            )
        if isinstance(value, (int, float)):
            normalized = (_finite(value, field_name="fixed_power_kw"),) * count
        else:
            normalized = tuple(
                _finite(item, field_name=f"fixed_power_kw[{index}]")
                for index, item in enumerate(
                    _sequence(value, field_name="fixed_power_kw")
                )
            )
        if len(normalized) != count:
            raise RestorationControlValidationError(
                "fixed_power_kw length must align exactly with the aFRR grid"
            )
        return normalized
    if value is not None:
        raise RestorationControlValidationError(
            f"{mode.value} aFRR baseline cannot declare fixed_power_kw"
        )
    return None


def build_afrr_baseline_config(
    *,
    config_id: str,
    semantics_version: str,
    period: CanonicalInterval,
    resolution: str,
    commitments: DirectionalCapacitySchedule,
    battery: BatteryComponent,
    capability: RestorationCapability,
    mode: AFRRBaselineMode | str,
    fixed_power_kw: float | Sequence[float] | None,
    headroom_bias: float = 0.0,
    tolerance: float = DEFAULT_RESTORATION_TOLERANCE,
) -> AFRRBaselineConfig:
    """Validate product, time, power, ramp, delay, and native-grid inputs."""

    normalized_period = _interval(period, field_name="period")
    normalized_resolution = _non_empty(resolution, field_name="resolution")
    try:
        normalized_mode = AFRRBaselineMode(mode)
    except (TypeError, ValueError) as exc:
        raise RestorationControlValidationError(
            "aFRR baseline mode must be ZERO, FIXED, or DETERMINISTIC_HEADROOM"
        ) from exc
    if type(commitments) is not DirectionalCapacitySchedule:
        raise RestorationControlValidationError(
            "commitments must be exactly a DirectionalCapacitySchedule"
        )
    if commitments.product is not RestorationProduct.AFRR:
        raise RestorationControlValidationError(
            "aFRR baseline commitments must have product AFRR"
        )
    if commitments.period != normalized_period:
        raise RestorationControlValidationError(
            "aFRR commitment period must match the baseline period"
        )
    if not isinstance(battery, BatteryComponent):
        raise RestorationControlValidationError("battery must be a BatteryComponent")
    if not isinstance(capability, RestorationCapability):
        raise RestorationControlValidationError(
            "capability must be a RestorationCapability"
        )
    normalized_tolerance = _positive(tolerance, field_name="tolerance")
    bias = _finite(headroom_bias, field_name="headroom_bias")
    if not -1.0 <= bias <= 1.0:
        raise RestorationControlValidationError(
            "headroom_bias must be finite and in [-1, 1]"
        )
    if normalized_mode is not AFRRBaselineMode.DETERMINISTIC_HEADROOM and bias != 0.0:
        raise RestorationControlValidationError(
            "headroom_bias is valid only for DETERMINISTIC_HEADROOM mode"
        )
    grid = _afrr_grid(normalized_period, normalized_resolution)
    fixed_values = _afrr_fixed_values(
        fixed_power_kw,
        count=len(grid),
        mode=normalized_mode,
    )
    interval_seconds = (
        grid[0].end_utc - grid[0].start_utc
    ).total_seconds()
    minimum_duration = capability.min_supported_duration_seconds[
        RestorationProduct.AFRR
    ]
    maximum_duration = capability.max_supported_duration_seconds[
        RestorationProduct.AFRR
    ]
    if not minimum_duration <= interval_seconds <= maximum_duration:
        raise RestorationControlValidationError(
            f"AFRR grid duration {interval_seconds} seconds is outside supported "
            f"duration [{minimum_duration}, {maximum_duration}]"
        )
    activation_delay = capability.max_activation_delay_seconds[
        RestorationProduct.AFRR
    ]
    upward_reachable = capability.max_ramp_down_kw_per_second * activation_delay
    downward_reachable = capability.max_ramp_up_kw_per_second * activation_delay
    commitment_pairs = commitments.commitment_pairs_covering(grid)
    for index, (interval, commitment_pair) in enumerate(
        zip(grid, commitment_pairs, strict=True)
    ):
        upward, downward = commitment_pair
        if upward.committed_capacity_kw > battery.max_discharge_kw + normalized_tolerance:
            raise RestorationControlValidationError(
                f"UPWARD commitment at interval {index} exceeds battery discharge power"
            )
        if downward.committed_capacity_kw > battery.max_charge_kw + normalized_tolerance:
            raise RestorationControlValidationError(
                f"DOWNWARD commitment at interval {index} exceeds battery charge power"
            )
        if upward.committed_capacity_kw > upward_reachable + normalized_tolerance:
            raise RestorationControlValidationError(
                f"UPWARD commitment {upward.committed_capacity_kw} kW at interval "
                f"{index} exceeds ramp/activation-time reach {upward_reachable} kW"
            )
        if downward.committed_capacity_kw > downward_reachable + normalized_tolerance:
            raise RestorationControlValidationError(
                f"DOWNWARD commitment {downward.committed_capacity_kw} kW at interval "
                f"{index} exceeds ramp/activation-time reach {downward_reachable} kW"
            )
    payload = {
        "schema_version": AFRR_BASELINE_CONFIG_SCHEMA_VERSION,
        "config_id": _non_empty(config_id, field_name="config_id"),
        "semantics_version": _non_empty(
            semantics_version, field_name="semantics_version"
        ),
        "product": RestorationProduct.AFRR.value,
        "period": normalized_period.to_dict(),
        "resolution": normalized_resolution,
        "grid": [interval.to_dict() for interval in grid],
        "commitments_fingerprint": commitments.schedule_fingerprint,
        "battery": battery.to_dict(),
        "capability_fingerprint": capability.capability_fingerprint,
        "mode": normalized_mode.value,
        "fixed_power_kw": None if fixed_values is None else list(fixed_values),
        "headroom_bias": bias,
        "tolerance": normalized_tolerance,
    }
    return AFRRBaselineConfig(
        schema_version=AFRR_BASELINE_CONFIG_SCHEMA_VERSION,
        config_id=str(payload["config_id"]),
        semantics_version=str(payload["semantics_version"]),
        period=normalized_period,
        resolution=normalized_resolution,
        grid_intervals=grid,
        commitments=commitments,
        battery=battery,
        capability=capability,
        mode=normalized_mode,
        fixed_power_kw=fixed_values,
        headroom_bias=bias,
        tolerance=normalized_tolerance,
        configuration_fingerprint=_fingerprint(payload),
    )


def build_afrr_baseline(config: AFRRBaselineConfig) -> RestorationBaselineBundle:
    """Construct and validate one aFRR baseline without activation lookahead."""

    if type(config) is not AFRRBaselineConfig:
        raise RestorationControlValidationError(
            "config must be exactly an AFRRBaselineConfig"
        )
    powers: list[float] = []
    commitment_pairs = (
        config.commitments.commitment_pairs_covering(config.grid_intervals)
        if config.mode is AFRRBaselineMode.DETERMINISTIC_HEADROOM
        else ()
    )
    for index, interval in enumerate(config.grid_intervals):
        if config.mode is AFRRBaselineMode.ZERO:
            power = 0.0
        elif config.mode is AFRRBaselineMode.FIXED:
            assert config.fixed_power_kw is not None
            power = config.fixed_power_kw[index]
        else:
            upward, downward = commitment_pairs[index]
            lower = -config.battery.max_discharge_kw + upward.committed_capacity_kw
            upper = config.battery.max_charge_kw - downward.committed_capacity_kw
            if lower > upper + config.tolerance:
                raise RestorationControlValidationError(
                    f"aFRR interval {index} has no baseline power after reserved headroom"
                )
            midpoint = (lower + upper) / 2.0
            power = midpoint + config.headroom_bias * (upper - lower) / 2.0
        powers.append(power)
    baseline = build_restoration_energy_baseline_schedule(
        schedule_id=f"{config.config_id}-accepted",
        semantics_version=RESTORATION_BASELINE_SEMANTICS_VERSION,
        product=RestorationProduct.AFRR,
        period=config.period,
        source=f"afrr_{config.mode.value.lower()}",
        intervals=[
            {
                "interval": interval,
                "accepted_baseline_power_kw": power,
            }
            for interval, power in zip(config.grid_intervals, powers, strict=True)
        ],
    )
    validation = build_restoration_baseline_config(
        config_id=config.config_id,
        semantics_version=config.semantics_version,
        product=RestorationProduct.AFRR,
        period=config.period,
        resolution=config.resolution,
        commitments=config.commitments,
        baseline=baseline,
        battery=config.battery,
        capability=config.capability,
        parameters={
            "mode": config.mode.value,
            "headroom_bias": config.headroom_bias,
        },
        tolerance=config.tolerance,
    )
    payload = {
        "schema_version": RESTORATION_BASELINE_BUNDLE_SCHEMA_VERSION,
        "product": RestorationProduct.AFRR.value,
        "source_configuration_fingerprint": config.configuration_fingerprint,
        "commitments_fingerprint": config.commitments.schedule_fingerprint,
        "baseline_fingerprint": baseline.schedule_fingerprint,
        "validation_fingerprint": validation.configuration_fingerprint,
    }
    return RestorationBaselineBundle(
        schema_version=RESTORATION_BASELINE_BUNDLE_SCHEMA_VERSION,
        product=RestorationProduct.AFRR,
        source_configuration_fingerprint=config.configuration_fingerprint,
        commitments=config.commitments,
        baseline=baseline,
        validation=validation,
        bundle_fingerprint=_fingerprint(payload),
    )


def build_mfrr_directional_capacity_schedule(
    *,
    schedule_id: str,
    semantics_version: str,
    period: CanonicalInterval,
    intervals: Sequence[Mapping[str, object]],
) -> DirectionalCapacitySchedule:
    """Build one exact mFRR upward/downward fixed-capacity schedule."""

    return build_directional_capacity_schedule(
        schedule_id=schedule_id,
        semantics_version=semantics_version,
        product=RestorationProduct.MFRR,
        period=period,
        intervals=intervals,
    )


@dataclass(frozen=True, slots=True)
class MFRRBaselineConfig:
    """Validated mFRR baseline inputs with a declared duration assumption."""

    schema_version: str
    config_id: str
    semantics_version: str
    period: CanonicalInterval
    resolution: str
    grid_intervals: tuple[CanonicalInterval, ...]
    commitments: DirectionalCapacitySchedule
    battery: BatteryComponent
    capability: RestorationCapability
    mode: MFRRBaselineMode
    fixed_power_kw: tuple[float, ...] | None
    declared_service_duration_seconds: float
    headroom_bias: float
    tolerance: float
    configuration_fingerprint: str


def _mfrr_grid(
    period: CanonicalInterval, resolution: str
) -> tuple[CanonicalInterval, ...]:
    try:
        duration = parse_iso8601_duration(resolution)
    except MarketTimeValidationError as exc:
        raise RestorationControlValidationError(str(exc)) from exc
    intervals: list[CanonicalInterval] = []
    cursor = period.start_utc
    while cursor < period.end_utc:
        end = cursor + duration
        if end > period.end_utc:
            raise RestorationControlValidationError(
                "mFRR period must be exactly divisible by resolution"
            )
        intervals.append(
            CanonicalInterval.from_utc(
                cursor,
                end,
                market_timezone=period.market_timezone,
            )
        )
        cursor = end
    if not intervals:
        raise RestorationControlValidationError(
            "mFRR baseline grid must be non-empty"
        )
    return tuple(intervals)


def _mfrr_fixed_values(
    value: float | Sequence[float] | None,
    *,
    count: int,
    mode: MFRRBaselineMode,
) -> tuple[float, ...] | None:
    if mode is MFRRBaselineMode.FIXED:
        if value is None:
            raise RestorationControlValidationError(
                "FIXED mFRR baseline requires fixed_power_kw"
            )
        if isinstance(value, bool):
            raise RestorationControlValidationError(
                "fixed_power_kw must be finite fixed values"
            )
        if isinstance(value, (int, float)):
            normalized = (_finite(value, field_name="fixed_power_kw"),) * count
        else:
            normalized = tuple(
                _finite(item, field_name=f"fixed_power_kw[{index}]")
                for index, item in enumerate(
                    _sequence(value, field_name="fixed_power_kw")
                )
            )
        if len(normalized) != count:
            raise RestorationControlValidationError(
                "fixed_power_kw length must align exactly with the mFRR grid"
            )
        return normalized
    if value is not None:
        raise RestorationControlValidationError(
            f"{mode.value} mFRR baseline cannot declare fixed_power_kw"
        )
    return None


def build_mfrr_baseline_config(
    *,
    config_id: str,
    semantics_version: str,
    period: CanonicalInterval,
    resolution: str,
    commitments: DirectionalCapacitySchedule,
    battery: BatteryComponent,
    capability: RestorationCapability,
    mode: MFRRBaselineMode | str,
    fixed_power_kw: float | Sequence[float] | None,
    declared_service_duration_seconds: float,
    headroom_bias: float = 0.0,
    tolerance: float = DEFAULT_RESTORATION_TOLERANCE,
) -> MFRRBaselineConfig:
    """Validate mFRR product, grid, headroom, timing, and duration inputs."""

    normalized_period = _interval(period, field_name="period")
    normalized_resolution = _non_empty(resolution, field_name="resolution")
    try:
        normalized_mode = MFRRBaselineMode(mode)
    except (TypeError, ValueError) as exc:
        raise RestorationControlValidationError(
            "mFRR baseline mode must be ZERO, FIXED, or DETERMINISTIC_HEADROOM"
        ) from exc
    if type(commitments) is not DirectionalCapacitySchedule:
        raise RestorationControlValidationError(
            "commitments must be exactly a DirectionalCapacitySchedule"
        )
    if commitments.product is not RestorationProduct.MFRR:
        raise RestorationControlValidationError(
            "mFRR baseline commitments must have product MFRR"
        )
    if commitments.period != normalized_period:
        raise RestorationControlValidationError(
            "mFRR commitment period must match the baseline period"
        )
    if not isinstance(battery, BatteryComponent):
        raise RestorationControlValidationError("battery must be a BatteryComponent")
    if not isinstance(capability, RestorationCapability):
        raise RestorationControlValidationError(
            "capability must be a RestorationCapability"
        )
    normalized_tolerance = _positive(tolerance, field_name="tolerance")
    bias = _finite(headroom_bias, field_name="headroom_bias")
    if not -1.0 <= bias <= 1.0:
        raise RestorationControlValidationError(
            "headroom_bias must be finite and in [-1, 1]"
        )
    if normalized_mode is not MFRRBaselineMode.DETERMINISTIC_HEADROOM and bias != 0.0:
        raise RestorationControlValidationError(
            "headroom_bias is valid only for DETERMINISTIC_HEADROOM mode"
        )
    grid = _mfrr_grid(normalized_period, normalized_resolution)
    fixed_values = _mfrr_fixed_values(
        fixed_power_kw,
        count=len(grid),
        mode=normalized_mode,
    )
    declared_duration = _positive(
        declared_service_duration_seconds,
        field_name="declared_service_duration_seconds",
    )
    minimum_duration = capability.min_supported_duration_seconds[
        RestorationProduct.MFRR
    ]
    maximum_duration = capability.max_supported_duration_seconds[
        RestorationProduct.MFRR
    ]
    if not minimum_duration <= declared_duration <= maximum_duration:
        raise RestorationControlValidationError(
            f"MFRR declared duration {declared_duration} seconds is outside "
            f"supported duration [{minimum_duration}, {maximum_duration}]"
        )
    activation_delay = capability.max_activation_delay_seconds[
        RestorationProduct.MFRR
    ]
    upward_reachable = capability.max_ramp_down_kw_per_second * activation_delay
    downward_reachable = capability.max_ramp_up_kw_per_second * activation_delay
    commitment_pairs = commitments.commitment_pairs_covering(grid)
    for index, (interval, commitment_pair) in enumerate(
        zip(grid, commitment_pairs, strict=True)
    ):
        upward, downward = commitment_pair
        if upward.committed_capacity_kw > battery.max_discharge_kw + normalized_tolerance:
            raise RestorationControlValidationError(
                f"UPWARD commitment at interval {index} exceeds battery discharge power"
            )
        if downward.committed_capacity_kw > battery.max_charge_kw + normalized_tolerance:
            raise RestorationControlValidationError(
                f"DOWNWARD commitment at interval {index} exceeds battery charge power"
            )
        if upward.committed_capacity_kw > upward_reachable + normalized_tolerance:
            raise RestorationControlValidationError(
                f"UPWARD commitment {upward.committed_capacity_kw} kW at interval "
                f"{index} exceeds ramp/activation-time reach {upward_reachable} kW"
            )
        if downward.committed_capacity_kw > downward_reachable + normalized_tolerance:
            raise RestorationControlValidationError(
                f"DOWNWARD commitment {downward.committed_capacity_kw} kW at interval "
                f"{index} exceeds ramp/activation-time reach {downward_reachable} kW"
            )
    payload = {
        "schema_version": MFRR_BASELINE_CONFIG_SCHEMA_VERSION,
        "config_id": _non_empty(config_id, field_name="config_id"),
        "semantics_version": _non_empty(
            semantics_version, field_name="semantics_version"
        ),
        "product": RestorationProduct.MFRR.value,
        "period": normalized_period.to_dict(),
        "resolution": normalized_resolution,
        "grid": [interval.to_dict() for interval in grid],
        "commitments_fingerprint": commitments.schedule_fingerprint,
        "battery": battery.to_dict(),
        "capability_fingerprint": capability.capability_fingerprint,
        "mode": normalized_mode.value,
        "fixed_power_kw": None if fixed_values is None else list(fixed_values),
        "declared_service_duration_seconds": declared_duration,
        "headroom_bias": bias,
        "tolerance": normalized_tolerance,
    }
    return MFRRBaselineConfig(
        schema_version=MFRR_BASELINE_CONFIG_SCHEMA_VERSION,
        config_id=str(payload["config_id"]),
        semantics_version=str(payload["semantics_version"]),
        period=normalized_period,
        resolution=normalized_resolution,
        grid_intervals=grid,
        commitments=commitments,
        battery=battery,
        capability=capability,
        mode=normalized_mode,
        fixed_power_kw=fixed_values,
        declared_service_duration_seconds=declared_duration,
        headroom_bias=bias,
        tolerance=normalized_tolerance,
        configuration_fingerprint=_fingerprint(payload),
    )


def build_mfrr_baseline(config: MFRRBaselineConfig) -> RestorationBaselineBundle:
    """Construct and validate one mFRR baseline without event lookahead."""

    if type(config) is not MFRRBaselineConfig:
        raise RestorationControlValidationError(
            "config must be exactly an MFRRBaselineConfig"
        )
    powers: list[float] = []
    commitment_pairs = (
        config.commitments.commitment_pairs_covering(config.grid_intervals)
        if config.mode is MFRRBaselineMode.DETERMINISTIC_HEADROOM
        else ()
    )
    for index, interval in enumerate(config.grid_intervals):
        if config.mode is MFRRBaselineMode.ZERO:
            power = 0.0
        elif config.mode is MFRRBaselineMode.FIXED:
            assert config.fixed_power_kw is not None
            power = config.fixed_power_kw[index]
        else:
            upward, downward = commitment_pairs[index]
            lower = -config.battery.max_discharge_kw + upward.committed_capacity_kw
            upper = config.battery.max_charge_kw - downward.committed_capacity_kw
            if lower > upper + config.tolerance:
                raise RestorationControlValidationError(
                    f"mFRR interval {index} has no baseline power after reserved headroom"
                )
            midpoint = (lower + upper) / 2.0
            power = midpoint + config.headroom_bias * (upper - lower) / 2.0
        powers.append(power)
    baseline = build_restoration_energy_baseline_schedule(
        schedule_id=f"{config.config_id}-accepted",
        semantics_version=RESTORATION_BASELINE_SEMANTICS_VERSION,
        product=RestorationProduct.MFRR,
        period=config.period,
        source=f"mfrr_{config.mode.value.lower()}",
        intervals=[
            {
                "interval": interval,
                "accepted_baseline_power_kw": power,
            }
            for interval, power in zip(config.grid_intervals, powers, strict=True)
        ],
    )
    validation = build_restoration_baseline_config(
        config_id=config.config_id,
        semantics_version=config.semantics_version,
        product=RestorationProduct.MFRR,
        period=config.period,
        resolution=config.resolution,
        commitments=config.commitments,
        baseline=baseline,
        battery=config.battery,
        capability=config.capability,
        parameters={
            "mode": config.mode.value,
            "headroom_bias": config.headroom_bias,
            "declared_service_duration_seconds": (
                config.declared_service_duration_seconds
            ),
        },
        tolerance=config.tolerance,
        required_duration_seconds=config.declared_service_duration_seconds,
    )
    payload = {
        "schema_version": RESTORATION_BASELINE_BUNDLE_SCHEMA_VERSION,
        "product": RestorationProduct.MFRR.value,
        "source_configuration_fingerprint": config.configuration_fingerprint,
        "commitments_fingerprint": config.commitments.schedule_fingerprint,
        "baseline_fingerprint": baseline.schedule_fingerprint,
        "validation_fingerprint": validation.configuration_fingerprint,
    }
    return RestorationBaselineBundle(
        schema_version=RESTORATION_BASELINE_BUNDLE_SCHEMA_VERSION,
        product=RestorationProduct.MFRR,
        source_configuration_fingerprint=config.configuration_fingerprint,
        commitments=config.commitments,
        baseline=baseline,
        validation=validation,
        bundle_fingerprint=_fingerprint(payload),
    )


__all__ = [
    "DIRECTIONAL_CAPACITY_SEMANTICS_VERSION",
    "RESTORATION_BASELINE_SEMANTICS_VERSION",
    "RESTORATION_CAPABILITY_SCHEMA_VERSION",
    "RESTORATION_BASELINE_CONFIG_SCHEMA_VERSION",
    "AFRR_BASELINE_CONFIG_SCHEMA_VERSION",
    "MFRR_BASELINE_CONFIG_SCHEMA_VERSION",
    "RESTORATION_BASELINE_BUNDLE_SCHEMA_VERSION",
    "DEFAULT_RESTORATION_TOLERANCE",
    "RestorationControlValidationError",
    "AFRRBaselineMode",
    "MFRRBaselineMode",
    "DirectionalCapacityCommitmentInterval",
    "DirectionalCapacitySchedule",
    "RestorationEnergyBaselineInterval",
    "RestorationEnergyBaselineSchedule",
    "RestorationCapability",
    "RestorationBaselineConfig",
    "AFRRBaselineConfig",
    "MFRRBaselineConfig",
    "RestorationBaselineBundle",
    "build_directional_capacity_schedule",
    "build_restoration_energy_baseline_schedule",
    "build_restoration_capability",
    "build_restoration_baseline_config",
    "build_afrr_directional_capacity_schedule",
    "build_afrr_baseline_config",
    "build_afrr_baseline",
    "build_mfrr_directional_capacity_schedule",
    "build_mfrr_baseline_config",
    "build_mfrr_baseline",
]
