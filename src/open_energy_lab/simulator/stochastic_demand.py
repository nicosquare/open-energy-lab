"""Simulator-owned paired weather-and-demand family evaluation surface."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from .demand import CoolingServiceConfiguration, derive_local_cooling_electric_kw
from .load import CoolingServiceBalance, LoadComponent
from .objective import evaluate_district_cooling_settlement
from .scenario import BatteryLoadPVScenario
from .weather import weather_component_from_sampled_trace


SUPPORTED_SUMMARY_OUTPUT_FIELDS = (
    "site_electric_load_kw",
    "local_cooling_electric_kw",
    "served_cooling_rt",
    "unserved_cooling_rt",
    "net_grid_power_kw",
    "step_settlement",
    "district_cooling_settlement",
)


@dataclass(frozen=True, slots=True)
class DemandFamilyEvaluationRequest:
    """Stable simulator-side request for one paired weather-and-demand family."""

    base_scenario_reference: BatteryLoadPVScenario
    weather_family: object
    demand_family: object
    cooling_service_configuration: CoolingServiceConfiguration
    summary_output_fields: tuple[str, ...] = field(default_factory=tuple)
    numeric_tolerance: float = 1e-6


@dataclass(frozen=True, slots=True)
class DemandScenarioEvaluationResult:
    """Per-scenario simulator result for one aligned weather and demand trace."""

    scenario_index: int
    weather_reference: str
    demand_reference: str
    non_thermal_electric_demand_kw: tuple[float, ...]
    cooling_demand_rt: tuple[float, ...]
    local_cooling_electric_kw: tuple[float, ...]
    served_cooling_rt: tuple[float, ...]
    unserved_cooling_rt: tuple[float, ...]
    district_cooling_settlement: tuple[float, ...]
    site_electric_load_kw: tuple[float, ...]
    net_grid_power_kw: tuple[float, ...]
    unmet_load_kw: tuple[float, ...]
    blackout_active: tuple[bool, ...]
    step_settlement: tuple[float, ...]
    total_settlement: float
    constraint_events: list[str]


@dataclass(frozen=True, slots=True)
class DemandFamilyEvaluationResult:
    """Scenario-indexed demand-aware simulator outputs plus family summaries."""

    family_id: str
    scenario_results: tuple[DemandScenarioEvaluationResult, ...]
    summary_statistics: dict[str, dict[str, tuple[float, ...]]]
    supported_summary_fields: tuple[str, ...] = field(default_factory=tuple)
    paired_family_seed: int = 0
    timestep_hours: float = 0.0
    cooling_service_path: str = ""


def evaluate_demand_family(
    request: DemandFamilyEvaluationRequest,
) -> DemandFamilyEvaluationResult:
    """Evaluate one sampled weather-and-demand family against a deterministic simulator base."""

    summary_fields = _validated_summary_fields(request.summary_output_fields)
    _validate_request(request)

    weather_family = request.weather_family
    demand_family = request.demand_family
    blackout_by_scenario = _blackout_grid_availability(weather_family)

    scenario_results = tuple(
        _evaluate_sampled_trace(
            request=request,
            weather_trace=weather_trace,
            demand_trace=demand_trace,
            blackout_grid_available=blackout_by_scenario.get(demand_trace.scenario_index),
        )
        for weather_trace, demand_trace in zip(
            getattr(weather_family, "sampled_traces"),
            getattr(demand_family, "sampled_traces"),
            strict=True,
        )
    )

    return DemandFamilyEvaluationResult(
        family_id=(
            f"{getattr(weather_family, 'family_id')}|"
            f"{getattr(demand_family, 'family_id')}|"
            f"{request.cooling_service_configuration.service_path}"
        ),
        scenario_results=scenario_results,
        summary_statistics={
            field_name: _summary_bucket(scenario_results, field_name)
            for field_name in summary_fields
        },
        supported_summary_fields=SUPPORTED_SUMMARY_OUTPUT_FIELDS,
        paired_family_seed=int(getattr(demand_family, "paired_family_seed")),
        timestep_hours=float(getattr(demand_family, "timestep_hours")),
        cooling_service_path=request.cooling_service_configuration.service_path,
    )


__all__ = [
    "DemandFamilyEvaluationRequest",
    "DemandFamilyEvaluationResult",
    "DemandScenarioEvaluationResult",
    "SUPPORTED_SUMMARY_OUTPUT_FIELDS",
    "evaluate_demand_family",
]


def _validate_request(request: DemandFamilyEvaluationRequest) -> None:
    if request.numeric_tolerance <= 0:
        raise ValueError("numeric_tolerance must be positive")

    base_scenario = request.base_scenario_reference
    weather_family = request.weather_family
    demand_family = request.demand_family

    weather_num_steps = int(getattr(weather_family, "num_steps"))
    demand_num_steps = int(getattr(demand_family, "num_steps"))
    if weather_num_steps <= 0 or demand_num_steps <= 0:
        raise ValueError("weather and demand families must define positive num_steps")
    if weather_num_steps != demand_num_steps:
        raise ValueError("weather and demand family horizons must align")
    if base_scenario.time_grid.num_steps != demand_num_steps:
        raise ValueError("paired family num_steps must match the base scenario time grid")

    weather_timestep = float(getattr(weather_family, "timestep_hours"))
    demand_timestep = float(getattr(demand_family, "timestep_hours"))
    if abs(weather_timestep - demand_timestep) > request.numeric_tolerance:
        raise ValueError("weather and demand family timestep_hours must align")
    if abs(base_scenario.time_grid.time_step_hours - demand_timestep) > request.numeric_tolerance:
        raise ValueError("paired family timestep_hours must match the base scenario time grid")

    weather_count = int(getattr(weather_family, "scenario_count"))
    demand_count = int(getattr(demand_family, "scenario_count"))
    if weather_count <= 0 or demand_count <= 0:
        raise ValueError("weather and demand families must define positive scenario_count")
    if weather_count != demand_count:
        raise ValueError("weather and demand family scenario counts must align")

    weather_traces = tuple(getattr(weather_family, "sampled_traces"))
    demand_traces = tuple(getattr(demand_family, "sampled_traces"))
    if len(weather_traces) != weather_count:
        raise ValueError("weather family sampled_traces length must match scenario_count")
    if len(demand_traces) != demand_count:
        raise ValueError("demand family sampled_traces length must match scenario_count")

    weather_seed = int(getattr(weather_family, "family_seed"))
    demand_seed = int(getattr(demand_family, "paired_family_seed"))
    if weather_seed != demand_seed:
        raise ValueError("paired weather and demand families must share the same seed")

    weather_indices = [int(getattr(trace, "scenario_index")) for trace in weather_traces]
    demand_indices = [int(getattr(trace, "scenario_index")) for trace in demand_traces]
    if len(set(weather_indices)) != len(weather_indices):
        raise ValueError("weather family scenario_index values must be unique")
    if len(set(demand_indices)) != len(demand_indices):
        raise ValueError("demand family scenario_index values must be unique")
    if weather_indices != demand_indices:
        raise ValueError("paired weather and demand family scenario ordering must align")

    for weather_trace, demand_trace in zip(weather_traces, demand_traces, strict=True):
        if len(getattr(weather_trace, "timestamp_utc")) != demand_num_steps:
            raise ValueError("sampled weather trace length must match the paired family horizon")
        if len(getattr(demand_trace, "non_thermal_electric_demand_kw")) != demand_num_steps:
            raise ValueError(
                "sampled demand trace non_thermal_electric_demand_kw length must match the paired family horizon"
            )
        if len(getattr(demand_trace, "cooling_demand_rt")) != demand_num_steps:
            raise ValueError(
                "sampled demand trace cooling_demand_rt length must match the paired family horizon"
            )
        if (
            str(getattr(demand_trace, "weather_trace_reference"))
            != str(getattr(weather_trace, "derived_identity"))
        ):
            raise ValueError("paired weather and demand trace references must align")

    blackout_traces = getattr(weather_family, "blackout_traces", ())
    if blackout_traces and len(blackout_traces) != weather_count:
        raise ValueError("weather family blackout_traces length must match scenario_count")


def _validated_summary_fields(summary_output_fields: Sequence[str]) -> tuple[str, ...]:
    if not summary_output_fields:
        return SUPPORTED_SUMMARY_OUTPUT_FIELDS
    normalized = tuple(dict.fromkeys(str(field_name) for field_name in summary_output_fields))
    unsupported = [
        field_name for field_name in normalized if field_name not in SUPPORTED_SUMMARY_OUTPUT_FIELDS
    ]
    if unsupported:
        raise ValueError(
            "summary_output_fields must be limited to the supported simulator fields: "
            + ", ".join(unsupported)
        )
    return normalized


def _evaluate_sampled_trace(
    *,
    request: DemandFamilyEvaluationRequest,
    weather_trace: object,
    demand_trace: object,
    blackout_grid_available: tuple[bool, ...] | None,
) -> DemandScenarioEvaluationResult:
    base_scenario = request.base_scenario_reference
    scenario_index = int(getattr(demand_trace, "scenario_index"))
    weather_component = weather_component_from_sampled_trace(
        weather_trace,
        time_grid=base_scenario.time_grid,
        name=f"{base_scenario.weather.name}-scenario-{scenario_index}",
        notes="Adapted from a sampled canonical weather trace for paired simulator evaluation.",
    )
    load_component = LoadComponent(
        name=f"{base_scenario.load.name}-scenario-{scenario_index}",
        demand_kw=[float(value) for value in getattr(demand_trace, "non_thermal_electric_demand_kw")],
        interpretation=base_scenario.load.interpretation,
        time_grid=base_scenario.time_grid,
        source=str(getattr(demand_trace, "derived_identity")),
    )
    cooling_service_balance = _cooling_service_balance(
        config=request.cooling_service_configuration,
        demand_trace=demand_trace,
        scenario_index=scenario_index,
        time_step_hours=base_scenario.time_grid.time_step_hours,
    )
    evaluated_trace = replace(
        base_scenario,
        scenario_id=f"{base_scenario.scenario_id}:scenario-{scenario_index}",
        weather=weather_component,
        load=load_component,
        cooling_service_balance=cooling_service_balance,
        blackout_grid_available=list(blackout_grid_available) if blackout_grid_available is not None else None,
    ).evaluate_trace()
    return DemandScenarioEvaluationResult(
        scenario_index=scenario_index,
        weather_reference=str(getattr(weather_trace, "derived_identity")),
        demand_reference=str(getattr(demand_trace, "derived_identity")),
        non_thermal_electric_demand_kw=tuple(float(value) for value in evaluated_trace.load_kw),
        cooling_demand_rt=tuple(float(value) for value in getattr(demand_trace, "cooling_demand_rt")),
        local_cooling_electric_kw=tuple(
            float(value) for value in evaluated_trace.local_cooling_electric_kw
        ),
        served_cooling_rt=tuple(float(value) for value in evaluated_trace.served_cooling_rt),
        unserved_cooling_rt=tuple(float(value) for value in evaluated_trace.unserved_cooling_rt),
        district_cooling_settlement=tuple(
            float(value) for value in evaluated_trace.district_cooling_settlement
        ),
        site_electric_load_kw=tuple(float(value) for value in evaluated_trace.site_electric_load_kw),
        net_grid_power_kw=tuple(float(value) for value in evaluated_trace.net_grid_power_kw),
        unmet_load_kw=tuple(float(value) for value in evaluated_trace.unmet_load_kw),
        blackout_active=tuple(bool(value) for value in evaluated_trace.blackout_active),
        step_settlement=tuple(float(value) for value in evaluated_trace.step_settlement),
        total_settlement=float(evaluated_trace.total_settlement),
        constraint_events=[str(value) for value in evaluated_trace.constraint_events],
    )


def _cooling_service_balance(
    *,
    config: CoolingServiceConfiguration,
    demand_trace: object,
    scenario_index: int,
    time_step_hours: float,
) -> CoolingServiceBalance:
    from .scenario import TimeGrid

    cooling_demand_rt = [float(value) for value in getattr(demand_trace, "cooling_demand_rt")]
    timestep_hours = float(getattr(demand_trace, "timestep_hours"))
    time_grid = TimeGrid(
        num_steps=len(cooling_demand_rt),
        time_step_hours=timestep_hours,
    )

    if config.service_path == "local-electric":
        assert config.local_electric_cooling is not None
        local_cooling_electric_kw = derive_local_cooling_electric_kw(
            cooling_demand_rt=cooling_demand_rt,
            config=config.local_electric_cooling,
        )
        return CoolingServiceBalance(
            time_grid=time_grid,
            local_cooling_electric_kw=local_cooling_electric_kw,
            served_cooling_rt=list(cooling_demand_rt),
            unserved_cooling_rt=[0.0] * time_grid.num_steps,
            district_cooling_settlement=[0.0] * time_grid.num_steps,
            source=config.source,
        )

    assert config.district_cooling_tariff is not None
    served_cooling_rt = _district_served_cooling_rt(
        config=config,
        scenario_index=scenario_index,
        cooling_demand_rt=cooling_demand_rt,
    )
    district_settlement = evaluate_district_cooling_settlement(
        served_cooling_rt=served_cooling_rt,
        time_step_hours=time_step_hours,
        tariff=config.district_cooling_tariff,
    )
    return CoolingServiceBalance(
        time_grid=time_grid,
        local_cooling_electric_kw=[0.0] * time_grid.num_steps,
        served_cooling_rt=list(district_settlement.served_cooling_rt),
        unserved_cooling_rt=[
            demand_value - served_value
            for demand_value, served_value in zip(cooling_demand_rt, served_cooling_rt, strict=True)
        ],
        district_cooling_settlement=list(district_settlement.step_settlement),
        source=config.source,
    )


def _district_served_cooling_rt(
    *,
    config: CoolingServiceConfiguration,
    scenario_index: int,
    cooling_demand_rt: Sequence[float],
) -> list[float]:
    if config.district_served_cooling_rt is None:
        return list(cooling_demand_rt)

    if scenario_index >= len(config.district_served_cooling_rt):
        raise ValueError("district_served_cooling_rt must provide one per-scenario trace")
    configured_values = [float(value) for value in config.district_served_cooling_rt[scenario_index]]
    if len(configured_values) != len(cooling_demand_rt):
        raise ValueError("district_served_cooling_rt length must match the paired family horizon")

    served: list[float] = []
    for demand_value, configured_value in zip(cooling_demand_rt, configured_values, strict=True):
        if configured_value < 0.0:
            raise ValueError("district_served_cooling_rt values must be non-negative")
        if configured_value > demand_value:
            raise ValueError(
                "district_served_cooling_rt cannot serve more thermal demand than the sampled cooling_demand_rt"
            )
        served.append(configured_value)
    return served


def _blackout_grid_availability(family: object) -> dict[int, tuple[bool, ...]]:
    blackout_traces = getattr(family, "blackout_traces", ())
    if not blackout_traces:
        return {}

    family_num_steps = int(getattr(family, "num_steps"))
    blackout_by_scenario: dict[int, tuple[bool, ...]] = {}
    for blackout_trace in blackout_traces:
        scenario_index = int(_lookup(blackout_trace, "scenario_index"))
        if scenario_index in blackout_by_scenario:
            raise ValueError("weather family blackout trace scenario_index values must be unique")
        blackout_by_scenario[scenario_index] = _bool_series(
            _lookup(blackout_trace, "grid_available"),
            field_name="grid_available",
            expected_length=family_num_steps,
        )
        interval_annotations = _lookup_optional(blackout_trace, "interval_annotations")
        if interval_annotations is not None:
            _string_series(
                interval_annotations,
                field_name="interval_annotations",
                expected_length=family_num_steps,
            )
    return blackout_by_scenario


def _summary_bucket(
    scenario_results: Sequence[DemandScenarioEvaluationResult],
    field_name: str,
) -> dict[str, tuple[float, ...]]:
    series_by_scenario = [getattr(result, field_name) for result in scenario_results]
    if not series_by_scenario:
        raise ValueError("scenario_results must not be empty")

    per_step_values = [
        [float(values[step_index]) for values in series_by_scenario]
        for step_index in range(len(series_by_scenario[0]))
    ]
    return {
        "min": _reduce_per_step(per_step_values, "min"),
        "mean": _reduce_per_step(per_step_values, "mean"),
        "max": _reduce_per_step(per_step_values, "max"),
        "p05": _reduce_per_step(per_step_values, "5"),
        "p50": _reduce_per_step(per_step_values, "50"),
        "p95": _reduce_per_step(per_step_values, "95"),
    }


def _reduce_per_step(
    per_step_values: Sequence[Sequence[float]],
    statistic: str,
) -> tuple[float, ...]:
    reduced: list[float] = []
    for step_values in per_step_values:
        ordered = sorted(float(value) for value in step_values)
        if statistic == "min":
            reduced.append(ordered[0])
        elif statistic == "mean":
            reduced.append(sum(ordered) / len(ordered))
        elif statistic == "max":
            reduced.append(ordered[-1])
        else:
            reduced.append(_percentile(ordered, float(statistic)))
    return tuple(reduced)


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    rank = (len(sorted_values) - 1) * (percentile / 100.0)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - lower_index
    lower_value = float(sorted_values[lower_index])
    upper_value = float(sorted_values[upper_index])
    return lower_value + ((upper_value - lower_value) * fraction)


def _lookup(source: object, field_name: str) -> object:
    if isinstance(source, Mapping):
        if field_name not in source:
            raise ValueError(f"blackout trace is missing {field_name!r}")
        return source[field_name]
    if not hasattr(source, field_name):
        raise ValueError(f"blackout trace is missing {field_name!r}")
    return getattr(source, field_name)


def _lookup_optional(source: object, field_name: str) -> object | None:
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _bool_series(
    value: object,
    *,
    field_name: str,
    expected_length: int,
) -> tuple[bool, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a boolean sequence")
    if any(not isinstance(item, bool) for item in value):
        raise TypeError(f"{field_name} values must be booleans")
    series = tuple(value)
    if len(series) != expected_length:
        raise ValueError(f"{field_name} length must match the weather family horizon")
    return series


def _string_series(
    value: object,
    *,
    field_name: str,
    expected_length: int,
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a string sequence")
    series = tuple(str(item) for item in value)
    if len(series) != expected_length:
        raise ValueError(f"{field_name} length must match the weather family horizon")
    return series
