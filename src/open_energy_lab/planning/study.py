"""Discrete solar-storage planning-study contracts and staged workflows."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from numbers import Real
from typing import Any


SUPPORTED_ADEQUACY_EVENT_KINDS = (
    "shortfall_ratio",
    "unmet_energy_kwh",
    "unmet_timestep_fraction",
)
SUPPORTED_GRID_AVAILABILITY_MODES = (
    "always_available",
    "islanded",
    "supplied",
    "markov",
)
SUPPORTED_STUDY_SHARD_FORMATS = ("jsonl", "parquet")
DEFAULT_STUDY_RANDOM_SEED = 13
DEFAULT_STUDY_BATCH_SIZE = 100
DEFAULT_STUDY_WORKER_COUNT = 1


def _text(value: object, *, field_name: str) -> str:
    normalized = str(value)
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _positive(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be numeric")
    normalized = float(value)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _non_negative(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be numeric")
    normalized = float(value)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return normalized


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return int(value)


def _probability(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be numeric")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be within [0.0, 1.0]")
    return normalized


@dataclass(frozen=True, slots=True)
class BatteryDesignOption:
    option_id: str
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    installed_cost: float
    charge_efficiency: float | None = None
    discharge_efficiency: float | None = None
    initial_soc: float | None = None
    min_soc: float | None = None
    max_soc: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", _text(self.option_id, field_name="option_id"))
        for name in ("capacity_kwh", "max_charge_kw", "max_discharge_kw"):
            object.__setattr__(self, name, _positive(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "installed_cost",
            _non_negative(self.installed_cost, field_name="installed_cost"),
        )
        for name in ("charge_efficiency", "discharge_efficiency"):
            value = getattr(self, name)
            if value is not None:
                normalized = _probability(value, field_name=name)
                if normalized == 0.0:
                    raise ValueError(f"{name} must be greater than zero")
                object.__setattr__(self, name, normalized)
        for name in ("initial_soc", "min_soc", "max_soc"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _probability(value, field_name=name))
        minimum = 0.0 if self.min_soc is None else self.min_soc
        maximum = 1.0 if self.max_soc is None else self.max_soc
        initial = minimum if self.initial_soc is None else self.initial_soc
        if not minimum <= initial <= maximum:
            raise ValueError("battery option must satisfy min_soc <= initial_soc <= max_soc")


@dataclass(frozen=True, slots=True)
class SolarDesignOption:
    option_id: str
    capacity_kw: float
    installed_cost: float
    generation_cap_kw: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", _text(self.option_id, field_name="option_id"))
        object.__setattr__(
            self,
            "capacity_kw",
            _positive(self.capacity_kw, field_name="capacity_kw"),
        )
        object.__setattr__(
            self,
            "installed_cost",
            _non_negative(self.installed_cost, field_name="installed_cost"),
        )
        if self.generation_cap_kw is not None:
            object.__setattr__(
                self,
                "generation_cap_kw",
                _positive(self.generation_cap_kw, field_name="generation_cap_kw"),
            )


@dataclass(frozen=True, slots=True)
class AdequacyMetrics:
    shortfall_ratio: float
    unmet_energy_kwh: float
    unmet_timestep_fraction: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdequacyEventDefinition:
    kind: str
    threshold: float
    comparison: str = ">"

    def __post_init__(self) -> None:
        kind = str(self.kind)
        if kind not in SUPPORTED_ADEQUACY_EVENT_KINDS:
            raise ValueError(
                "kind must be one of " + ", ".join(SUPPORTED_ADEQUACY_EVENT_KINDS)
            )
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "threshold",
            _non_negative(self.threshold, field_name="threshold"),
        )
        if self.comparison != ">":
            raise ValueError("comparison must be '>'")
        if kind in {"shortfall_ratio", "unmet_timestep_fraction"} and self.threshold > 1.0:
            raise ValueError(f"{kind} threshold must be within [0.0, 1.0]")

    @property
    def event_target_name(self) -> str:
        return f"{self.kind}_exceeds_threshold"

    def evaluate(self, metrics: AdequacyMetrics) -> int:
        return int(float(getattr(metrics, self.kind)) > self.threshold)


@dataclass(frozen=True, slots=True)
class GridAvailabilityPolicy:
    mode: str
    initial_grid_available: bool = True
    outage_start_probability: float | None = None
    recovery_probability: float | None = None
    supplied_traces: Mapping[int, Sequence[bool]] = field(default_factory=dict)
    import_limit_kw: float | None = None

    def __post_init__(self) -> None:
        mode = str(self.mode)
        if mode not in SUPPORTED_GRID_AVAILABILITY_MODES:
            raise ValueError(
                "mode must be one of " + ", ".join(SUPPORTED_GRID_AVAILABILITY_MODES)
            )
        object.__setattr__(self, "mode", mode)
        if not isinstance(self.initial_grid_available, bool):
            raise TypeError("initial_grid_available must be boolean")
        if mode == "markov":
            if self.outage_start_probability is None or self.recovery_probability is None:
                raise ValueError(
                    "markov grid availability requires outage_start_probability and recovery_probability"
                )
            object.__setattr__(
                self,
                "outage_start_probability",
                _probability(
                    self.outage_start_probability,
                    field_name="outage_start_probability",
                ),
            )
            recovery = _probability(
                self.recovery_probability,
                field_name="recovery_probability",
            )
            if recovery == 0.0:
                raise ValueError("recovery_probability must be greater than zero")
            object.__setattr__(self, "recovery_probability", recovery)
        elif self.outage_start_probability is not None or self.recovery_probability is not None:
            raise ValueError("outage probabilities are valid only for markov mode")

        traces: dict[int, tuple[bool, ...]] = {}
        for sample_id, trace in self.supplied_traces.items():
            normalized_id = int(sample_id)
            normalized_trace = tuple(trace)
            if any(not isinstance(value, bool) for value in normalized_trace):
                raise TypeError("supplied grid availability traces must contain booleans")
            traces[normalized_id] = normalized_trace
        if mode == "supplied" and not traces:
            raise ValueError("supplied mode requires supplied_traces")
        if mode != "supplied" and traces:
            raise ValueError("supplied_traces are valid only for supplied mode")
        object.__setattr__(self, "supplied_traces", traces)
        if self.import_limit_kw is not None:
            if mode == "islanded":
                raise ValueError("import_limit_kw is not valid for islanded mode")
            object.__setattr__(
                self,
                "import_limit_kw",
                _non_negative(self.import_limit_kw, field_name="import_limit_kw"),
            )


@dataclass(frozen=True, slots=True)
class ControllerStudyConfig:
    controller_name: str = "PVSelfConsumptionController"
    parameters: Mapping[str, object] = field(default_factory=dict)
    resolve_power_from_equipment: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "controller_name",
            _text(self.controller_name, field_name="controller_name"),
        )
        object.__setattr__(
            self,
            "parameters",
            {str(key): value for key, value in self.parameters.items()},
        )
        if not isinstance(self.resolve_power_from_equipment, bool):
            raise TypeError("resolve_power_from_equipment must be boolean")


@dataclass(frozen=True, slots=True)
class PlanningConfiguration:
    configuration_index: int
    configuration_id: str
    battery: BatteryDesignOption
    solar: SolarDesignOption
    installed_cost: float

    def design_metadata(self) -> dict[str, object]:
        return {
            "configuration_index": self.configuration_index,
            "configuration_id": self.configuration_id,
            "battery_option_id": self.battery.option_id,
            "solar_option_id": self.solar.option_id,
            "battery_capacity_kwh": self.battery.capacity_kwh,
            "battery_max_charge_kw": self.battery.max_charge_kw,
            "battery_max_discharge_kw": self.battery.max_discharge_kw,
            "solar_capacity_kw": self.solar.capacity_kw,
            "installed_cost": self.installed_cost,
        }


@dataclass(frozen=True, slots=True)
class PlanningStudyRequest:
    study_id: str
    battery_options: tuple[BatteryDesignOption, ...]
    solar_options: tuple[SolarDesignOption, ...]
    samples_per_configuration: int
    horizon_steps: int
    adequacy_event: AdequacyEventDefinition
    grid_availability: GridAvailabilityPolicy
    controller: ControllerStudyConfig = field(default_factory=ControllerStudyConfig)
    batch_size: int = DEFAULT_STUDY_BATCH_SIZE
    worker_count: int = DEFAULT_STUDY_WORKER_COUNT
    random_seed: int = DEFAULT_STUDY_RANDOM_SEED
    shard_format: str = "parquet"
    fit_feature_names: tuple[str, ...] = field(default_factory=tuple)
    local_start_step: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "study_id", _text(self.study_id, field_name="study_id"))
        batteries = tuple(self.battery_options)
        solar = tuple(self.solar_options)
        if not batteries or not solar:
            raise ValueError("battery_options and solar_options must not be empty")
        if len({item.option_id for item in batteries}) != len(batteries):
            raise ValueError("battery option ids must be unique")
        if len({item.option_id for item in solar}) != len(solar):
            raise ValueError("solar option ids must be unique")
        object.__setattr__(self, "battery_options", batteries)
        object.__setattr__(self, "solar_options", solar)
        for name in ("samples_per_configuration", "horizon_steps", "batch_size", "worker_count"):
            object.__setattr__(self, name, _positive_int(getattr(self, name), field_name=name))
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise TypeError("random_seed must be an integer")
        if self.random_seed < 0 or self.random_seed > 2**32 - 1:
            raise ValueError("random_seed must be between 0 and 2**32 - 1")
        if isinstance(self.local_start_step, bool) or not isinstance(
            self.local_start_step, int
        ):
            raise TypeError("local_start_step must be an integer")
        if not 0 <= self.local_start_step < 24:
            raise ValueError("local_start_step must be within [0, 23]")
        shard_format = str(self.shard_format)
        if shard_format not in SUPPORTED_STUDY_SHARD_FORMATS:
            raise ValueError(
                "shard_format must be one of " + ", ".join(SUPPORTED_STUDY_SHARD_FORMATS)
            )
        object.__setattr__(self, "shard_format", shard_format)
        feature_names = tuple(str(name) for name in self.fit_feature_names)
        if len(set(feature_names)) != len(feature_names):
            raise ValueError("fit_feature_names must be unique")
        object.__setattr__(self, "fit_feature_names", feature_names)

    @property
    def expected_row_count(self) -> int:
        return (
            len(self.battery_options)
            * len(self.solar_options)
            * self.samples_per_configuration
        )

    def sample_batches(self) -> tuple[tuple[int, ...], ...]:
        return tuple(
            tuple(range(start, min(start + self.batch_size, self.samples_per_configuration)))
            for start in range(0, self.samples_per_configuration, self.batch_size)
        )

    def _grid_availability_dict(self) -> dict[str, object]:
        payload = {
            **asdict(self.grid_availability),
            "supplied_traces": {
                str(key): list(value)
                for key, value in self.grid_availability.supplied_traces.items()
            },
        }
        # Omitted when unset so uncapped requests keep their earlier
        # serialization and dataset fingerprints.
        if payload["import_limit_kw"] is None:
            del payload["import_limit_kw"]
        return payload

    def to_dict(self) -> dict[str, object]:
        return {
            "study_id": self.study_id,
            "battery_options": [asdict(item) for item in self.battery_options],
            "solar_options": [asdict(item) for item in self.solar_options],
            "samples_per_configuration": self.samples_per_configuration,
            "horizon_steps": self.horizon_steps,
            "adequacy_event": asdict(self.adequacy_event),
            "grid_availability": self._grid_availability_dict(),
            "controller": {
                **asdict(self.controller),
                "parameters": dict(self.controller.parameters),
            },
            "batch_size": self.batch_size,
            "worker_count": self.worker_count,
            "random_seed": self.random_seed,
            "shard_format": self.shard_format,
            "fit_feature_names": list(self.fit_feature_names),
            "local_start_step": self.local_start_step,
        }

    @property
    def request_fingerprint(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_configuration_grid(
    request: PlanningStudyRequest,
) -> tuple[PlanningConfiguration, ...]:
    configurations: list[PlanningConfiguration] = []
    for battery in request.battery_options:
        for solar in request.solar_options:
            configurations.append(
                PlanningConfiguration(
                    configuration_index=len(configurations),
                    configuration_id=f"{battery.option_id}__{solar.option_id}",
                    battery=battery,
                    solar=solar,
                    installed_cost=battery.installed_cost + solar.installed_cost,
                )
            )
    return tuple(configurations)


def derive_adequacy_metrics(
    *,
    site_electric_load_kw: Sequence[float],
    unmet_load_kw: Sequence[float],
    timestep_hours: float,
    numeric_tolerance: float = 1e-9,
) -> AdequacyMetrics:
    load = tuple(float(value) for value in site_electric_load_kw)
    unmet = tuple(float(value) for value in unmet_load_kw)
    if not load or len(load) != len(unmet):
        raise ValueError("site load and unmet load must be non-empty and aligned")
    duration = _positive(timestep_hours, field_name="timestep_hours")
    tolerance = _positive(numeric_tolerance, field_name="numeric_tolerance")
    if any(value < -tolerance for value in load + unmet):
        raise ValueError("site load and unmet load must be non-negative")
    load_energy = sum(load) * duration
    unmet_energy = sum(max(0.0, value) for value in unmet) * duration
    if load_energy <= tolerance:
        if unmet_energy > tolerance:
            raise ValueError("unmet energy cannot be positive when total load energy is zero")
        ratio = 0.0
    else:
        ratio = unmet_energy / load_energy
    unmet_fraction = sum(value > tolerance for value in unmet) / len(unmet)
    return AdequacyMetrics(
        shortfall_ratio=float(ratio),
        unmet_energy_kwh=float(unmet_energy),
        unmet_timestep_fraction=float(unmet_fraction),
    )


def generate_grid_availability_trace(
    policy: GridAvailabilityPolicy,
    *,
    study_seed: int,
    sample_id: int,
    horizon_steps: int,
) -> tuple[bool, ...]:
    steps = _positive_int(horizon_steps, field_name="horizon_steps")
    if sample_id < 0:
        raise ValueError("sample_id must be non-negative")
    if policy.mode == "always_available":
        return (True,) * steps
    if policy.mode == "islanded":
        return (False,) * steps
    if policy.mode == "supplied":
        try:
            trace = tuple(policy.supplied_traces[sample_id])
        except KeyError as exc:
            raise ValueError(f"supplied grid trace is missing sample_id {sample_id}") from exc
        if len(trace) != steps:
            raise ValueError("supplied grid trace length must match horizon_steps")
        return trace

    seed_payload = f"planning-grid-availability|{study_seed}|{sample_id}".encode()
    seed = int.from_bytes(hashlib.sha256(seed_payload).digest()[:8], "big")
    rng = random.Random(seed)
    available = policy.initial_grid_available
    values: list[bool] = []
    assert policy.outage_start_probability is not None
    assert policy.recovery_probability is not None
    for _ in range(steps):
        values.append(available)
        if available:
            if rng.random() < policy.outage_start_probability:
                available = False
        elif rng.random() < policy.recovery_probability:
            available = True
    return tuple(values)


def default_fit_feature_names(event: AdequacyEventDefinition) -> tuple[str, ...]:
    return (
        "battery_option_id",
        "solar_option_id",
        "shortfall_ratio",
        "unmet_energy_kwh",
        "unmet_timestep_fraction",
        event.event_target_name,
    )


def resolve_study_controller(
    config: ControllerStudyConfig,
    *,
    battery: BatteryDesignOption,
) -> object:
    """Instantiate one supported named controller for a concrete battery option."""

    parameters = dict(config.parameters)
    if config.resolve_power_from_equipment:
        parameters.setdefault("charge_request_kw", battery.max_charge_kw)
        parameters.setdefault("discharge_request_kw", battery.max_discharge_kw)

    if config.controller_name == "PVSelfConsumptionController":
        from open_energy_lab.control import (
            PVSelfConsumptionConfig,
            PVSelfConsumptionController,
        )

        parameters.setdefault("reserve_min_soc", battery.min_soc or 0.0)
        parameters.setdefault("reserve_max_soc", battery.max_soc or 1.0)
        return PVSelfConsumptionController(PVSelfConsumptionConfig(**parameters))
    if config.controller_name == "SocGuardrailController":
        from open_energy_lab.control import SocGuardrailConfig, SocGuardrailController

        parameters.setdefault("target_min_soc", battery.min_soc or 0.0)
        parameters.setdefault("target_max_soc", battery.max_soc or 1.0)
        return SocGuardrailController(SocGuardrailConfig(**parameters))
    raise ValueError(
        f"unsupported planning-study controller {config.controller_name!r}; "
        "supported controllers are PVSelfConsumptionController and SocGuardrailController"
    )


__all__ = [
    "AdequacyEventDefinition",
    "AdequacyMetrics",
    "BatteryDesignOption",
    "ControllerStudyConfig",
    "GridAvailabilityPolicy",
    "PlanningConfiguration",
    "PlanningStudyRequest",
    "SolarDesignOption",
    "build_configuration_grid",
    "default_fit_feature_names",
    "derive_adequacy_metrics",
    "generate_grid_availability_trace",
    "resolve_study_controller",
]
