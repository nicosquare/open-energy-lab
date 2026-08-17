"""Offline weather-conditioned demand-family sampling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from math import sqrt
from pathlib import Path
from random import Random
from typing import Any
from zoneinfo import ZoneInfo

from .artifact import (
    DemandArtifact,
    load_demand_artifact,
    validate_sampling_weather_family,
)


@dataclass(frozen=True, slots=True)
class DemandSamplingRequest:
    """Stable first-release request surface for offline demand-family sampling."""

    weather_family_reference: object
    num_steps: int
    scenario_count: int
    paired_family_seed: int


@dataclass(frozen=True, slots=True)
class SampledDemandTrace:
    """One sampled demand trace aligned to one sampled weather trace."""

    scenario_index: int
    paired_family_seed: int
    derived_identity: str
    weather_trace_reference: str
    timestep_hours: float
    non_thermal_electric_demand_kw: tuple[float, ...]
    cooling_demand_rt: tuple[float, ...]
    local_civil_step_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DemandScenarioFamily:
    """Offline demand family sampled from one fitted artifact and weather family."""

    family_id: str
    artifact_reference: str
    weather_family_reference: str
    paired_family_seed: int
    scenario_count: int
    num_steps: int
    timestep_hours: float
    sampled_traces: tuple[SampledDemandTrace, ...]


def sample_demand_family(
    artifact: DemandArtifact | str | Path | Mapping[str, Any],
    *,
    request: DemandSamplingRequest,
    expected_timestep_hours: float | None = None,
) -> DemandScenarioFamily:
    """Sample a reproducible family of demand traces from a persisted artifact."""

    loaded_artifact = _coerce_artifact(
        artifact,
        expected_timestep_hours=expected_timestep_hours,
    )
    _validate_request(request)
    weather_family = request.weather_family_reference
    sampled_weather_traces = validate_sampling_weather_family(
        loaded_artifact,
        weather_family,
        expected_num_steps=request.num_steps,
        expected_scenario_count=request.scenario_count,
        paired_family_seed=request.paired_family_seed,
    )

    intervals_per_day = _intervals_per_day(loaded_artifact)
    shared_scales = _shared_residual_scales(loaded_artifact)
    correlation_matrix = _correlation_matrix(loaded_artifact)
    cholesky_factor = _two_dimensional_cholesky(correlation_matrix)
    weather_field_order = loaded_artifact.required_weather_field_order
    family_id = _family_id(
        artifact_id=loaded_artifact.artifact_id,
        weather_family_id=str(getattr(weather_family, "family_id")),
        paired_family_seed=request.paired_family_seed,
        scenario_count=request.scenario_count,
        num_steps=request.num_steps,
    )

    sampled_traces = tuple(
        _sample_trace(
            artifact=loaded_artifact,
            weather_trace=weather_trace,
            weather_field_order=weather_field_order,
            intervals_per_day=intervals_per_day,
            shared_scales=shared_scales,
            cholesky_factor=cholesky_factor,
            paired_family_seed=request.paired_family_seed,
            scenario_index=scenario_index,
        )
        for scenario_index, weather_trace in enumerate(sampled_weather_traces)
    )

    return DemandScenarioFamily(
        family_id=family_id,
        artifact_reference=loaded_artifact.artifact_id,
        weather_family_reference=str(getattr(weather_family, "family_id")),
        paired_family_seed=request.paired_family_seed,
        scenario_count=request.scenario_count,
        num_steps=request.num_steps,
        timestep_hours=loaded_artifact.timestep_hours,
        sampled_traces=sampled_traces,
    )


__all__ = [
    "DemandSamplingRequest",
    "SampledDemandTrace",
    "DemandScenarioFamily",
    "sample_demand_family",
]


def _coerce_artifact(
    artifact: DemandArtifact | str | Path | Mapping[str, Any],
    *,
    expected_timestep_hours: float | None,
) -> DemandArtifact:
    if isinstance(artifact, DemandArtifact):
        loaded_artifact = artifact
        if (
            expected_timestep_hours is not None
            and loaded_artifact.timestep_hours != expected_timestep_hours
        ):
            raise ValueError(
                "expected artifact timestep_hours "
                f"{expected_timestep_hours:g}, got {loaded_artifact.timestep_hours:g}"
            )
        return loaded_artifact

    return load_demand_artifact(
        artifact,
        expected_timestep_hours=expected_timestep_hours,
    )


def _validate_request(request: DemandSamplingRequest) -> None:
    if request.num_steps <= 0:
        raise ValueError("num_steps must be positive")
    if request.scenario_count <= 0:
        raise ValueError("scenario_count must be positive")


def _intervals_per_day(artifact: DemandArtifact) -> int:
    value = int(artifact.shared_residual_model["intervals_per_day"])
    if value <= 0:
        raise ValueError("artifact shared_residual_model intervals_per_day must be positive")
    return value


def _shared_residual_scales(artifact: DemandArtifact) -> tuple[float, float]:
    non_thermal_summary = artifact.non_thermal_electric_model["residual_scale_summary"]
    cooling_summary = artifact.cooling_demand_model["residual_scale_summary"]
    if not isinstance(non_thermal_summary, Mapping) or not isinstance(cooling_summary, Mapping):
        raise ValueError("artifact residual_scale_summary entries must be mappings")

    non_thermal_scale = max(
        float(non_thermal_summary["mae_kw"]),
        float(non_thermal_summary["max_abs_error_kw"]) / 2.0,
    )
    cooling_scale = max(
        float(cooling_summary["mae_rt"]),
        float(cooling_summary["max_abs_error_rt"]) / 2.0,
    )
    return non_thermal_scale, cooling_scale


def _correlation_matrix(artifact: DemandArtifact) -> tuple[tuple[float, float], tuple[float, float]]:
    raw_matrix = artifact.shared_residual_model["correlation_matrix"]
    if isinstance(raw_matrix, str) or not isinstance(raw_matrix, Sequence):
        raise TypeError("artifact correlation_matrix must be a numeric matrix")
    if len(raw_matrix) != 2:
        raise ValueError("first-release demand sampling requires a 2x2 correlation_matrix")

    rows: list[tuple[float, float]] = []
    for row in raw_matrix:
        if isinstance(row, str) or not isinstance(row, Sequence) or len(row) != 2:
            raise ValueError("first-release demand sampling requires a 2x2 correlation_matrix")
        rows.append((float(row[0]), float(row[1])))
    return rows[0], rows[1]


def _two_dimensional_cholesky(
    correlation_matrix: tuple[tuple[float, float], tuple[float, float]]
) -> tuple[tuple[float, float], tuple[float, float]]:
    a11 = correlation_matrix[0][0]
    a21 = correlation_matrix[1][0]
    a22 = correlation_matrix[1][1]
    if a11 <= 0.0 or a22 <= 0.0:
        raise ValueError("correlation_matrix must be positive on the diagonal")

    l11 = sqrt(a11)
    l21 = a21 / l11
    residual = a22 - (l21 * l21)
    if residual < 0.0:
        residual = 0.0
    l22 = sqrt(residual)
    return ((l11, 0.0), (l21, l22))


def _sample_trace(
    *,
    artifact: DemandArtifact,
    weather_trace: object,
    weather_field_order: Sequence[str],
    intervals_per_day: int,
    shared_scales: tuple[float, float],
    cholesky_factor: tuple[tuple[float, float], tuple[float, float]],
    paired_family_seed: int,
    scenario_index: int,
) -> SampledDemandTrace:
    weather_trace_reference = str(getattr(weather_trace, "derived_identity"))
    canonical_field_series = getattr(weather_trace, "canonical_field_series")
    timestamp_utc = tuple(str(value) for value in getattr(weather_trace, "timestamp_utc"))
    scenario_rng = _seeded_random(
        artifact_id=artifact.artifact_id,
        paired_family_seed=paired_family_seed,
        scenario_index=scenario_index,
    )

    non_thermal_values: list[float] = []
    cooling_values: list[float] = []
    for step_index in range(len(timestamp_utc)):
        local_step_index = step_index % intervals_per_day
        non_thermal_base = _baseline_with_weather(
            output_model=artifact.non_thermal_electric_model,
            baseline_field_name="local_step_baseline_kw",
            weather_field_order=weather_field_order,
            canonical_field_series=canonical_field_series,
            local_step_index=local_step_index,
            step_index=step_index,
        )
        cooling_base = _baseline_with_weather(
            output_model=artifact.cooling_demand_model,
            baseline_field_name="local_step_baseline_rt",
            weather_field_order=weather_field_order,
            canonical_field_series=canonical_field_series,
            local_step_index=local_step_index,
            step_index=step_index,
        )
        correlated_noise = _sample_correlated_pair(
            rng=scenario_rng,
            cholesky_factor=cholesky_factor,
            scales=shared_scales,
        )
        non_thermal_values.append(max(0.0, non_thermal_base + correlated_noise[0]))
        cooling_values.append(max(0.0, cooling_base + correlated_noise[1]))

    derived_identity = (
        f"{artifact.artifact_id}:weather-{paired_family_seed}:scenario-{scenario_index}"
    )
    return SampledDemandTrace(
        scenario_index=scenario_index,
        paired_family_seed=paired_family_seed,
        derived_identity=derived_identity,
        weather_trace_reference=weather_trace_reference,
        timestep_hours=artifact.timestep_hours,
        non_thermal_electric_demand_kw=tuple(non_thermal_values),
        cooling_demand_rt=tuple(cooling_values),
        local_civil_step_labels=_local_civil_step_labels(
            timestamp_utc=timestamp_utc,
            timezone_name=artifact.timezone_name,
        ),
    )


def _baseline_with_weather(
    *,
    output_model: Mapping[str, object],
    baseline_field_name: str,
    weather_field_order: Sequence[str],
    canonical_field_series: Mapping[str, Sequence[float]],
    local_step_index: int,
    step_index: int,
) -> float:
    baseline_values = output_model[baseline_field_name]
    if isinstance(baseline_values, str) or not isinstance(baseline_values, Sequence):
        raise TypeError(f"{baseline_field_name} must be a numeric sequence")
    baseline = float(baseline_values[local_step_index])

    weather_response_terms = output_model["weather_response_terms"]
    if not isinstance(weather_response_terms, Mapping):
        raise TypeError("weather_response_terms must be a mapping")

    response = 0.0
    for field_name in weather_field_order:
        field_values = canonical_field_series[field_name]
        response += float(weather_response_terms[field_name]) * float(field_values[step_index])
    return baseline + response


def _sample_correlated_pair(
    *,
    rng: Random,
    cholesky_factor: tuple[tuple[float, float], tuple[float, float]],
    scales: tuple[float, float],
) -> tuple[float, float]:
    z1 = rng.gauss(0.0, 1.0)
    z2 = rng.gauss(0.0, 1.0)
    first = cholesky_factor[0][0] * z1
    second = (cholesky_factor[1][0] * z1) + (cholesky_factor[1][1] * z2)
    return first * scales[0], second * scales[1]


def _local_civil_step_labels(
    *, timestamp_utc: Sequence[str], timezone_name: str
) -> tuple[str, ...]:
    timezone = ZoneInfo(timezone_name)
    labels = []
    for value in timestamp_utc:
        utc_timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        labels.append(utc_timestamp.astimezone(timezone).isoformat())
    return tuple(labels)


def _family_id(
    *,
    artifact_id: str,
    weather_family_id: str,
    paired_family_seed: int,
    scenario_count: int,
    num_steps: int,
) -> str:
    digest = sha256(
        (
            f"{artifact_id}|{weather_family_id}|{paired_family_seed}|"
            f"{scenario_count}|{num_steps}"
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"demand-family:{digest}"


def _seeded_random(
    *, artifact_id: str, paired_family_seed: int, scenario_index: int
) -> Random:
    digest = sha256(
        f"{artifact_id}|{paired_family_seed}|{scenario_index}".encode("utf-8")
    ).digest()
    return Random(int.from_bytes(digest[:8], byteorder="big", signed=False))
