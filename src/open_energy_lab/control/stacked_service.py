"""Deterministic fixed-schedule baselines for stacked-service replay."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from types import MappingProxyType

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import canonical_json_bytes, fingerprint
from open_energy_lab.core.validation import finite, non_empty_str
from open_energy_lab.core import ControllerContext, DispatchProposal
from open_energy_lab.core.controller import BatteryStateSnapshot, PriceInput
from open_energy_lab.market.artifact import MarketDataArtifact
from open_energy_lab.simulator.scenario import BatteryComponent
from open_energy_lab.simulator.stacked_service import (
    EnergyBaselineSchedule,
    FCRCapacitySchedule,
    build_energy_baseline_schedule,
    build_fcr_capacity_schedule,
)

from ._config import PriceThresholdConfig
from .price_threshold import PriceThresholdController


class StackedBaselineValidationError(ValidationError):
    """Raised when a deterministic baseline configuration is incompatible."""


_non_empty = partial(non_empty_str, error=StackedBaselineValidationError, strip=True)
_finite = partial(finite, error=StackedBaselineValidationError)


def _validate_threshold_config(config: object) -> PriceThresholdConfig:
    if (
        config.__class__.__module__ != "open_energy_lab.control._config"
        or config.__class__.__name__ != "PriceThresholdConfig"
    ):
        raise StackedBaselineValidationError(
            "price_threshold_config must be a PriceThresholdConfig"
        )
    for name in (
        "charge_below_import_price",
        "discharge_above_import_price",
        "charge_request_kw",
        "discharge_request_kw",
    ):
        _finite(getattr(config, name), field_name=f"price threshold {name}")
    return config  # type: ignore[return-value]


_canonical_json = partial(canonical_json_bytes, error=StackedBaselineValidationError)
_fingerprint = partial(fingerprint, error=StackedBaselineValidationError)


def _threshold_payload(config: PriceThresholdConfig) -> dict[str, object]:
    return {
        "charge_below_import_price": config.charge_below_import_price,
        "discharge_above_import_price": config.discharge_above_import_price,
        "charge_request_kw": config.charge_request_kw,
        "discharge_request_kw": config.discharge_request_kw,
        "controller_name": config.controller_name,
    }


@dataclass(frozen=True, slots=True)
class ArbitrageOnlyBaselineConfig:
    schedule_id: str
    semantics_version: str
    price_threshold_config: PriceThresholdConfig

    def __post_init__(self) -> None:
        object.__setattr__(self, "schedule_id", _non_empty(self.schedule_id, field_name="schedule_id"))
        object.__setattr__(
            self,
            "semantics_version",
            _non_empty(self.semantics_version, field_name="semantics_version"),
        )
        _validate_threshold_config(self.price_threshold_config)


@dataclass(frozen=True, slots=True)
class RegulationOnlyBaselineConfig:
    schedule_id: str
    semantics_version: str
    fcr_schedule: FCRCapacitySchedule

    def __post_init__(self) -> None:
        object.__setattr__(self, "schedule_id", _non_empty(self.schedule_id, field_name="schedule_id"))
        object.__setattr__(
            self,
            "semantics_version",
            _non_empty(self.semantics_version, field_name="semantics_version"),
        )
        if not isinstance(self.fcr_schedule, FCRCapacitySchedule):
            raise StackedBaselineValidationError(
                "regulation-only config requires one fixed FCRCapacitySchedule"
            )


@dataclass(frozen=True, slots=True)
class StackedHeuristicConfig:
    schedule_id: str
    semantics_version: str
    price_threshold_config: PriceThresholdConfig
    fcr_schedule: FCRCapacitySchedule

    def __post_init__(self) -> None:
        object.__setattr__(self, "schedule_id", _non_empty(self.schedule_id, field_name="schedule_id"))
        object.__setattr__(
            self,
            "semantics_version",
            _non_empty(self.semantics_version, field_name="semantics_version"),
        )
        _validate_threshold_config(self.price_threshold_config)
        if not isinstance(self.fcr_schedule, FCRCapacitySchedule):
            raise StackedBaselineValidationError(
                "stacked config requires one fixed FCRCapacitySchedule"
            )


@dataclass(frozen=True, slots=True)
class BaselineScheduleBundle:
    """Fixed schedules and the battery state from which they should be replayed."""

    builder_kind: str
    battery: BatteryComponent
    energy_schedule: EnergyBaselineSchedule
    fcr_schedule: FCRCapacitySchedule
    initial_stored_energy_kwh: float
    recovery_dispatch_kw: tuple[float, ...]
    configuration_fingerprint: str


def _require_inputs(
    *,
    market_artifact: object,
    battery: object,
) -> tuple[MarketDataArtifact, BatteryComponent]:
    if not isinstance(market_artifact, MarketDataArtifact):
        raise StackedBaselineValidationError(
            "market_artifact must be a validated MarketDataArtifact"
        )
    if not isinstance(battery, BatteryComponent):
        raise StackedBaselineValidationError("battery must be one BatteryComponent")
    return market_artifact, battery


def _controller_proposals(
    config: PriceThresholdConfig,
    *,
    market_artifact: MarketDataArtifact,
    battery: BatteryComponent,
) -> tuple[DispatchProposal, ...]:
    controller = PriceThresholdController(config)
    observations = market_artifact.series["day_ahead_price"].observations
    proposals: list[DispatchProposal] = []
    for index, observation in enumerate(observations):
        duration_hours = (
            observation.interval.end_utc - observation.interval.start_utc
        ).total_seconds() / 3600.0
        context = ControllerContext(
            scenario_id="stacked-service-fixed-schedule",
            scenario_kind="ArbitrageScenario",
            step_index=index,
            time_step_hours=duration_hours,
            battery_state=BatteryStateSnapshot(
                soc_fraction=battery.initial_soc,
                min_soc=battery.min_soc,
                max_soc=battery.max_soc,
                max_charge_kw=battery.max_charge_kw,
                max_discharge_kw=battery.max_discharge_kw,
            ),
            price_input=PriceInput(
                import_price=observation.value,
                export_price=observation.value,
                currency="EUR",
                time_alignment="step-start",
            ),
            step_inputs=MappingProxyType({}),
        )
        proposals.append(controller.propose_dispatch(context))
    return tuple(proposals)


def _energy_schedule(
    *,
    schedule_id: str,
    semantics_version: str,
    market_artifact: MarketDataArtifact,
    powers: tuple[float, ...],
    schedule_source: str,
) -> EnergyBaselineSchedule:
    observations = market_artifact.series["day_ahead_price"].observations
    if len(observations) != len(powers):
        raise StackedBaselineValidationError(
            "price observations and energy requests must align exactly"
        )
    return build_energy_baseline_schedule(
        schedule_id=schedule_id,
        semantics_version=semantics_version,
        covered_start_utc=market_artifact.actual_covered_period.start_utc,
        covered_end_utc=market_artifact.actual_covered_period.end_utc,
        intervals=[
            {
                "start_utc": observation.interval.start_utc,
                "end_utc": observation.interval.end_utc,
                "power_kw": power,
                "schedule_source": schedule_source,
            }
            for observation, power in zip(observations, powers, strict=True)
        ],
    )


def _zero_fcr_schedule(market_artifact: MarketDataArtifact) -> FCRCapacitySchedule:
    volumes = market_artifact.series["fcr_contracted_volume"].observations
    prices = market_artifact.series["fcr_capacity_price"].observations
    if len(volumes) != len(prices):
        raise StackedBaselineValidationError(
            "FCR volume and price observations must align exactly"
        )
    return build_fcr_capacity_schedule(
        schedule_id="arbitrage-only-zero-fcr-v1",
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=market_artifact.actual_covered_period.start_utc,
        covered_end_utc=market_artifact.actual_covered_period.end_utc,
        intervals=[
            {
                "start_utc": volume.interval.start_utc,
                "end_utc": volume.interval.end_utc,
                "capacity_kw": 0.0,
                "volume_observation_ref": f"fcr_contracted_volume:{index}",
                "price_observation_ref": f"fcr_capacity_price:{index}",
            }
            for index, (volume, price) in enumerate(zip(volumes, prices, strict=True))
            if volume.interval.start_utc == price.interval.start_utc
            and volume.interval.end_utc == price.interval.end_utc
        ],
    )


def _bundle(
    *,
    builder_kind: str,
    battery: BatteryComponent,
    energy_schedule: EnergyBaselineSchedule,
    fcr_schedule: FCRCapacitySchedule,
    recovery_dispatch_kw: tuple[float, ...] = (),
    config_payload: dict[str, object],
) -> BaselineScheduleBundle:
    initial_energy = battery.initial_soc * battery.capacity_kwh
    fingerprint = _fingerprint(
        {
            "builder_kind": builder_kind,
            "battery": battery.to_dict(),
            "energy_schedule": energy_schedule.schedule_fingerprint,
            "fcr_schedule": fcr_schedule.schedule_fingerprint,
            "recovery_dispatch_kw": list(recovery_dispatch_kw),
            "config": config_payload,
        }
    )
    return BaselineScheduleBundle(
        builder_kind=builder_kind,
        battery=battery,
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        initial_stored_energy_kwh=initial_energy,
        recovery_dispatch_kw=recovery_dispatch_kw,
        configuration_fingerprint=fingerprint,
    )


def build_arbitrage_only_baseline(
    config: ArbitrageOnlyBaselineConfig,
    *,
    market_artifact: MarketDataArtifact,
    battery: BatteryComponent,
) -> BaselineScheduleBundle:
    """Build the current-step threshold baseline with zero FCR commitment."""

    if not isinstance(config, ArbitrageOnlyBaselineConfig):
        raise StackedBaselineValidationError(
            "config must be an ArbitrageOnlyBaselineConfig"
        )
    market, component = _require_inputs(
        market_artifact=market_artifact,
        battery=battery,
    )
    powers = tuple(
        proposal.requested_power_kw
        for proposal in _controller_proposals(
            config.price_threshold_config,
            market_artifact=market,
            battery=component,
        )
    )
    energy = _energy_schedule(
        schedule_id=config.schedule_id,
        semantics_version=config.semantics_version,
        market_artifact=market,
        powers=powers,
        schedule_source="arbitrage_only",
    )
    fcr = _zero_fcr_schedule(market)
    return _bundle(
        builder_kind="arbitrage_only",
        battery=component,
        energy_schedule=energy,
        fcr_schedule=fcr,
        config_payload={
            "schedule_id": config.schedule_id,
            "semantics_version": config.semantics_version,
            "price_threshold": _threshold_payload(config.price_threshold_config),
        },
    )


def build_regulation_only_baseline(
    config: RegulationOnlyBaselineConfig,
    *,
    battery: BatteryComponent,
) -> BaselineScheduleBundle:
    """Build a zero-energy, no-recovery baseline at efficiency-centered SOC."""

    if not isinstance(config, RegulationOnlyBaselineConfig):
        raise StackedBaselineValidationError(
            "config must be a RegulationOnlyBaselineConfig"
        )
    if not isinstance(battery, BatteryComponent):
        raise StackedBaselineValidationError("battery must be one BatteryComponent")
    minimum_kwh = battery.min_soc * battery.capacity_kwh
    maximum_kwh = battery.max_soc * battery.capacity_kwh
    efficiency_product = battery.charge_efficiency * battery.discharge_efficiency
    centered_kwh = (
        maximum_kwh + efficiency_product * minimum_kwh
    ) / (1.0 + efficiency_product)
    centered_battery = BatteryComponent(
        **{
            **battery.to_dict(),
            "initial_soc": centered_kwh / battery.capacity_kwh,
        }
    )
    covered = config.fcr_schedule.covered_period
    hours = int((covered.end_utc - covered.start_utc).total_seconds() // 3600)
    energy = build_energy_baseline_schedule(
        schedule_id=config.schedule_id,
        semantics_version=config.semantics_version,
        covered_start_utc=covered.start_utc,
        covered_end_utc=covered.end_utc,
        intervals=[
            {
                "start_utc": covered.start_utc + index * (covered.end_utc - covered.start_utc) / hours,
                "end_utc": covered.start_utc + (index + 1) * (covered.end_utc - covered.start_utc) / hours,
                "power_kw": 0.0,
                "schedule_source": "fixed",
            }
            for index in range(hours)
        ],
    )
    return _bundle(
        builder_kind="regulation_only",
        battery=centered_battery,
        energy_schedule=energy,
        fcr_schedule=config.fcr_schedule,
        recovery_dispatch_kw=(),
        config_payload={
            "schedule_id": config.schedule_id,
            "semantics_version": config.semantics_version,
            "centered_initial_stored_energy_kwh": centered_kwh,
            "recovery": "none",
        },
    )


def build_stacked_heuristic_baseline(
    config: StackedHeuristicConfig,
    *,
    market_artifact: MarketDataArtifact,
    battery: BatteryComponent,
) -> BaselineScheduleBundle:
    """Build current-step threshold requests clipped after symmetric reservation."""

    if not isinstance(config, StackedHeuristicConfig):
        raise StackedBaselineValidationError("config must be a StackedHeuristicConfig")
    market, component = _require_inputs(
        market_artifact=market_artifact,
        battery=battery,
    )
    if (
        config.fcr_schedule.covered_period.start_utc
        != market.actual_covered_period.start_utc
        or config.fcr_schedule.covered_period.end_utc
        != market.actual_covered_period.end_utc
    ):
        raise StackedBaselineValidationError(
            "FCR schedule coverage must match market price coverage"
        )
    proposals = _controller_proposals(
        config.price_threshold_config,
        market_artifact=market,
        battery=component,
    )
    powers: list[float] = []
    price_observations = market.series["day_ahead_price"].observations
    for index, (proposal, observation) in enumerate(
        zip(proposals, price_observations, strict=True)
    ):
        matches = [
            commitment
            for commitment in config.fcr_schedule.intervals
            if commitment.interval.start_utc <= observation.interval.start_utc
            and observation.interval.end_utc <= commitment.interval.end_utc
        ]
        if len(matches) != 1:
            raise StackedBaselineValidationError(
                f"energy interval {index} does not map to exactly one FCR commitment"
            )
        reserve = matches[0].capacity_kw
        lower = -component.max_discharge_kw + reserve
        upper = component.max_charge_kw - reserve
        if lower > upper:
            raise StackedBaselineValidationError(
                f"energy interval {index} has an empty admissible power interval after reserve headroom"
            )
        powers.append(max(lower, min(upper, proposal.requested_power_kw)))
    energy = _energy_schedule(
        schedule_id=config.schedule_id,
        semantics_version=config.semantics_version,
        market_artifact=market,
        powers=tuple(powers),
        schedule_source="stacked_heuristic",
    )
    return _bundle(
        builder_kind="stacked_heuristic",
        battery=component,
        energy_schedule=energy,
        fcr_schedule=config.fcr_schedule,
        config_payload={
            "schedule_id": config.schedule_id,
            "semantics_version": config.semantics_version,
            "price_threshold": _threshold_payload(config.price_threshold_config),
            "fcr_schedule": config.fcr_schedule.schedule_fingerprint,
            "headroom_rule": (
                "[-max_discharge_kw + reserve_kw, max_charge_kw - reserve_kw]"
            ),
        },
    )


__all__ = [
    "ArbitrageOnlyBaselineConfig",
    "BaselineScheduleBundle",
    "RegulationOnlyBaselineConfig",
    "StackedBaselineValidationError",
    "StackedHeuristicConfig",
    "build_arbitrage_only_baseline",
    "build_regulation_only_baseline",
    "build_stacked_heuristic_baseline",
]
