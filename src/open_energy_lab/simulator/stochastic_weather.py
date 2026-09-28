"""Simulator-owned stochastic weather family evaluation surface."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from ._family_summary import (
    bool_series,
    lookup,
    lookup_optional,
    string_series,
    summary_bucket,
    validated_summary_fields,
)
from .scenario import BatteryLoadPVScenario
from .weather import weather_component_from_sampled_trace

if TYPE_CHECKING:
    from .scenario import BatteryLoadPVTrace
    from .weather import WeatherComponent
    from open_energy_lab.weather.sampling import WeatherScenarioFamily


SUPPORTED_SUMMARY_OUTPUT_FIELDS = (
    "pv_generation_kw",
    "net_grid_power_kw",
    "unmet_load_kw",
    "step_settlement",
)


@dataclass(frozen=True, slots=True)
class WeatherFamilyEvaluationRequest:
    """Stable simulator-side request for one sampled weather family."""

    base_scenario_reference: BatteryLoadPVScenario
    weather_family: "WeatherScenarioFamily"
    summary_output_fields: tuple[str, ...] = field(default_factory=tuple)
    numeric_tolerance: float = 1e-6


@dataclass(frozen=True, slots=True)
class WeatherScenarioEvaluationResult:
    """Per-scenario simulator result for one sampled weather trace."""

    scenario_index: int
    pv_generation_kw: tuple[float, ...]
    net_grid_power_kw: tuple[float, ...]
    unmet_load_kw: tuple[float, ...]
    blackout_active: tuple[bool, ...]
    step_settlement: tuple[float, ...]
    total_settlement: float
    weather_reference: str
    constraint_events: list[str]


@dataclass(frozen=True, slots=True)
class WeatherFamilyEvaluationResult:
    """Scenario-indexed stochastic simulator outputs plus family summaries."""

    family_id: str
    scenario_results: tuple[WeatherScenarioEvaluationResult, ...]
    summary_statistics: dict[str, dict[str, tuple[float, ...]]]
    supported_summary_fields: tuple[str, ...] = field(default_factory=tuple)
    family_seed: int = 0
    timestep_hours: float = 0.0


def evaluate_weather_family(
    request: WeatherFamilyEvaluationRequest,
) -> WeatherFamilyEvaluationResult:
    """Evaluate one sampled weather family against a deterministic simulator base."""

    summary_fields = validated_summary_fields(
        request.summary_output_fields, supported=SUPPORTED_SUMMARY_OUTPUT_FIELDS
    )
    base_scenario = request.base_scenario_reference
    family = request.weather_family
    _validate_request(request)

    blackout_by_scenario = _blackout_grid_availability(family)
    scenario_results = tuple(
        _evaluate_sampled_trace(
            base_scenario=base_scenario,
            sampled_trace=sampled_trace,
            blackout_grid_available=blackout_by_scenario.get(sampled_trace.scenario_index),
        )
        for sampled_trace in family.sampled_traces
    )

    return WeatherFamilyEvaluationResult(
        family_id=family.family_id,
        scenario_results=scenario_results,
        summary_statistics={
            field_name: summary_bucket(scenario_results, field_name)
            for field_name in summary_fields
        },
        supported_summary_fields=SUPPORTED_SUMMARY_OUTPUT_FIELDS,
        family_seed=family.family_seed,
        timestep_hours=family.timestep_hours,
    )


__all__ = [
    "WeatherFamilyEvaluationRequest",
    "WeatherScenarioEvaluationResult",
    "WeatherFamilyEvaluationResult",
    "SUPPORTED_SUMMARY_OUTPUT_FIELDS",
    "evaluate_weather_family",
]


def _validate_request(request: WeatherFamilyEvaluationRequest) -> None:
    family = request.weather_family
    base_scenario = request.base_scenario_reference
    if request.numeric_tolerance <= 0:
        raise ValueError("numeric_tolerance must be positive")
    if family.scenario_count <= 0:
        raise ValueError("weather family scenario_count must be positive")
    if family.num_steps <= 0:
        raise ValueError("weather family num_steps must be positive")
    if len(family.sampled_traces) != family.scenario_count:
        raise ValueError("weather family sampled_traces length must match scenario_count")
    if base_scenario.time_grid.num_steps != family.num_steps:
        raise ValueError("weather family num_steps must match the base scenario time grid")
    if abs(base_scenario.time_grid.time_step_hours - family.timestep_hours) > request.numeric_tolerance:
        raise ValueError("weather family timestep_hours must match the base scenario time grid")

    seen_indices: set[int] = set()
    for sampled_trace in family.sampled_traces:
        if sampled_trace.scenario_index in seen_indices:
            raise ValueError("weather family sampled trace scenario_index values must be unique")
        seen_indices.add(sampled_trace.scenario_index)
        if len(sampled_trace.timestamp_utc) != family.num_steps:
            raise ValueError("sampled weather trace length must match weather family num_steps")
        if abs(sampled_trace.timestep_hours - family.timestep_hours) > request.numeric_tolerance:
            raise ValueError("sampled weather trace timestep_hours must match weather family timestep_hours")

    blackout_traces = getattr(family, "blackout_traces", ())
    if blackout_traces and len(blackout_traces) != family.scenario_count:
        raise ValueError("weather family blackout_traces length must match scenario_count")


def _evaluate_sampled_trace(
    *,
    base_scenario: BatteryLoadPVScenario,
    sampled_trace: object,
    blackout_grid_available: tuple[bool, ...] | None,
) -> WeatherScenarioEvaluationResult:
    weather_component = _weather_for_sample(
        base_scenario=base_scenario,
        sampled_trace=sampled_trace,
    )
    evaluated_trace = replace(
        base_scenario,
        scenario_id=f"{base_scenario.scenario_id}:scenario-{sampled_trace.scenario_index}",
        weather=weather_component,
        blackout_grid_available=list(blackout_grid_available) if blackout_grid_available is not None else None,
    ).evaluate_trace()
    return _scenario_result(
        sampled_trace=sampled_trace,
        evaluated_trace=evaluated_trace,
    )


def _weather_for_sample(
    *,
    base_scenario: BatteryLoadPVScenario,
    sampled_trace: object,
) -> "WeatherComponent":
    return weather_component_from_sampled_trace(
        sampled_trace,
        time_grid=base_scenario.time_grid,
        name=f"{base_scenario.weather.name}-scenario-{sampled_trace.scenario_index}",
        notes="Adapted from a sampled canonical weather trace for simulator-side PV evaluation.",
    )


def _scenario_result(
    *,
    sampled_trace: object,
    evaluated_trace: "BatteryLoadPVTrace",
) -> WeatherScenarioEvaluationResult:
    return WeatherScenarioEvaluationResult(
        scenario_index=int(sampled_trace.scenario_index),
        pv_generation_kw=tuple(float(value) for value in evaluated_trace.pv_generation_kw),
        net_grid_power_kw=tuple(float(value) for value in evaluated_trace.net_grid_power_kw),
        unmet_load_kw=tuple(float(value) for value in evaluated_trace.unmet_load_kw),
        blackout_active=tuple(bool(value) for value in evaluated_trace.blackout_active),
        step_settlement=tuple(float(value) for value in evaluated_trace.step_settlement),
        total_settlement=float(evaluated_trace.total_settlement),
        weather_reference=str(sampled_trace.derived_identity),
        constraint_events=[str(value) for value in evaluated_trace.constraint_events],
    )


def _blackout_grid_availability(family: "WeatherScenarioFamily") -> dict[int, tuple[bool, ...]]:
    blackout_traces = getattr(family, "blackout_traces", ())
    if not blackout_traces:
        return {}

    blackout_by_scenario: dict[int, tuple[bool, ...]] = {}
    for blackout_trace in blackout_traces:
        scenario_index = int(lookup(blackout_trace, "scenario_index"))
        if scenario_index in blackout_by_scenario:
            raise ValueError("weather family blackout trace scenario_index values must be unique")

        grid_available = bool_series(
            lookup(blackout_trace, "grid_available"),
            field_name="grid_available",
            expected_length=family.num_steps,
        )
        interval_annotations = lookup_optional(blackout_trace, "interval_annotations")
        if interval_annotations is not None:
            string_series(
                interval_annotations,
                field_name="interval_annotations",
                expected_length=family.num_steps,
            )
        blackout_by_scenario[scenario_index] = grid_available

    return blackout_by_scenario
