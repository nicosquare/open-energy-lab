"""Offline seeded weather-family sampling from persisted artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha1, sha256
from math import ceil, sqrt
from pathlib import Path
from random import Random
from typing import Any
from zoneinfo import ZoneInfo

from .artifact import WeatherArtifact, load_weather_artifact
from .events import CloudEventAnnotation, apply_cloud_event_overlay, enforce_physical_bounds


@dataclass(frozen=True, slots=True)
class WeatherSamplingRequest:
    """Stable first-release request surface for offline family sampling."""

    num_steps: int
    scenario_count: int
    family_seed: int


@dataclass(frozen=True, slots=True)
class SampledWeatherTrace:
    """One seeded sampled weather trace within a scenario family."""

    scenario_index: int
    family_seed: int
    derived_identity: str
    timestep_hours: float
    timestamp_utc: tuple[str, ...]
    canonical_field_series: dict[str, tuple[float, ...]]
    cloud_event_annotations: tuple[CloudEventAnnotation, ...]


@dataclass(frozen=True, slots=True)
class WeatherScenarioFamily:
    """Offline weather family sampled from one fitted artifact."""

    family_id: str
    artifact_reference: str
    family_seed: int
    scenario_count: int
    num_steps: int
    timestep_hours: float
    sampled_traces: tuple[SampledWeatherTrace, ...]
    blackout_traces: tuple[object, ...] = ()


def sample_weather_family(
    artifact: WeatherArtifact | str | Path | Mapping[str, Any],
    *,
    request: WeatherSamplingRequest,
    expected_timestep_hours: float | None = None,
) -> WeatherScenarioFamily:
    """Sample a reproducible family of arbitrary-horizon weather traces."""

    loaded_artifact = _coerce_artifact(
        artifact,
        expected_timestep_hours=expected_timestep_hours,
    )
    _validate_request(request)

    base_parameters = loaded_artifact.base_model_parameters
    field_order = _field_order(loaded_artifact)
    intervals_per_day = _positive_int(
        base_parameters.get("intervals_per_day"),
        field_name="intervals_per_day",
    )
    if len(loaded_artifact.cloud_event_model["start_probability_by_local_step"]) != intervals_per_day:
        raise ValueError(
            "cloud_event_model start_probability_by_local_step must align with intervals_per_day"
        )

    mean_vector = _numeric_vector(
        base_parameters.get("mean_vector"),
        field_name="mean_vector",
    )
    covariance_matrix = _covariance_matrix(
        base_parameters.get("covariance_matrix"),
        expected_size=len(mean_vector),
    )
    expected_feature_count = intervals_per_day * len(field_order)
    if len(mean_vector) != expected_feature_count:
        raise ValueError(
            "base_model_parameters mean_vector length must equal "
            "intervals_per_day * len(field_order)"
        )

    physical_bounds_policy = _physical_bounds_policy(loaded_artifact)
    cholesky_factor = _cholesky_factor(covariance_matrix)
    day_count = ceil(request.num_steps / intervals_per_day)
    family_id = _family_id(
        artifact_id=loaded_artifact.artifact_id,
        family_seed=request.family_seed,
        scenario_count=request.scenario_count,
        num_steps=request.num_steps,
    )

    sampled_traces = tuple(
        _sample_trace(
            artifact=loaded_artifact,
            field_order=field_order,
            intervals_per_day=intervals_per_day,
            mean_vector=mean_vector,
            cholesky_factor=cholesky_factor,
            physical_bounds_policy=physical_bounds_policy,
            family_seed=request.family_seed,
            scenario_index=scenario_index,
            day_count=day_count,
            num_steps=request.num_steps,
        )
        for scenario_index in range(request.scenario_count)
    )

    return WeatherScenarioFamily(
        family_id=family_id,
        artifact_reference=loaded_artifact.artifact_id,
        family_seed=request.family_seed,
        scenario_count=request.scenario_count,
        num_steps=request.num_steps,
        timestep_hours=loaded_artifact.timestep_hours,
        sampled_traces=sampled_traces,
    )


def _coerce_artifact(
    artifact: WeatherArtifact | str | Path | Mapping[str, Any],
    *,
    expected_timestep_hours: float | None,
) -> WeatherArtifact:
    if isinstance(artifact, WeatherArtifact):
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

    return load_weather_artifact(
        artifact,
        expected_timestep_hours=expected_timestep_hours,
    )


def _validate_request(request: WeatherSamplingRequest) -> None:
    if request.num_steps <= 0:
        raise ValueError("num_steps must be positive")
    if request.scenario_count <= 0:
        raise ValueError("scenario_count must be positive")


def _field_order(artifact: WeatherArtifact) -> tuple[str, ...]:
    field_order = tuple(str(field_name) for field_name in artifact.base_model_parameters["field_order"])
    expected = tuple(artifact.canonical_field_order[1:])
    if field_order != expected:
        raise ValueError("artifact field_order must match canonical_field_order without timestamp_utc")
    return field_order


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise TypeError(f"{field_name} must be a positive integer")
    integer_value = int(value)
    if integer_value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return integer_value


def _numeric_vector(value: object, *, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a numeric sequence")
    return tuple(float(item) for item in value)


def _covariance_matrix(value: object, *, expected_size: int) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("covariance_matrix must be a square numeric sequence")

    rows: list[tuple[float, ...]] = []
    for row in value:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes, bytearray)):
            raise TypeError("covariance_matrix rows must be numeric sequences")
        rows.append(tuple(float(item) for item in row))

    if len(rows) != expected_size:
        raise ValueError("covariance_matrix row count must match mean_vector length")
    if any(len(row) != expected_size for row in rows):
        raise ValueError("covariance_matrix must be square with mean_vector-aligned dimensions")
    return tuple(rows)


def _physical_bounds_policy(artifact: WeatherArtifact) -> Mapping[str, object]:
    physical_bounds_policy = artifact.base_model_parameters.get("physical_bounds_policy")
    if not isinstance(physical_bounds_policy, Mapping):
        raise ValueError("artifact base_model_parameters must include physical_bounds_policy")
    return physical_bounds_policy


def _sample_trace(
    *,
    artifact: WeatherArtifact,
    field_order: Sequence[str],
    intervals_per_day: int,
    mean_vector: Sequence[float],
    cholesky_factor: Sequence[Sequence[float]],
    physical_bounds_policy: Mapping[str, object],
    family_seed: int,
    scenario_index: int,
    day_count: int,
    num_steps: int,
) -> SampledWeatherTrace:
    scenario_rng = _seeded_random(
        "weather-family",
        family_seed=family_seed,
        scenario_index=scenario_index,
    )
    concatenated_series = {field_name: [] for field_name in field_order}
    annotations: list[CloudEventAnnotation] = []

    for day_index in range(day_count):
        sampled_vector = _sample_multivariate_day(
            mean_vector=mean_vector,
            cholesky_factor=cholesky_factor,
            rng=scenario_rng,
        )
        base_day_series = _reshape_daily_vector(
            sampled_vector,
            field_order=field_order,
            intervals_per_day=intervals_per_day,
        )
        bounded_day_series = enforce_physical_bounds(
            canonical_field_series=base_day_series,
            physical_bounds_policy=physical_bounds_policy,
        )
        overlay_result = apply_cloud_event_overlay(
            canonical_field_series=bounded_day_series,
            cloud_event_model=artifact.cloud_event_model,
            family_seed=family_seed,
            scenario_index=scenario_index,
            physical_bounds_policy=physical_bounds_policy,
            day_index=day_index,
        )
        for field_name in field_order:
            concatenated_series[field_name].extend(
                overlay_result.canonical_field_series[field_name]
            )
        annotations.extend(
            CloudEventAnnotation(
                start_index=annotation.start_index + (day_index * intervals_per_day),
                duration_steps=annotation.duration_steps,
                attenuation_fraction=annotation.attenuation_fraction,
            )
            for annotation in overlay_result.cloud_event_annotations
        )

    trimmed_series = {
        field_name: tuple(values[:num_steps])
        for field_name, values in concatenated_series.items()
    }
    trimmed_annotations = tuple(
        annotation
        for annotation in annotations
        if annotation.start_index < num_steps
    )
    timestamp_utc = _timestamp_sequence(
        artifact=artifact,
        num_steps=num_steps,
    )
    derived_identity = (
        f"{artifact.artifact_id}:family-{family_seed}:scenario-{scenario_index}"
    )
    return SampledWeatherTrace(
        scenario_index=scenario_index,
        family_seed=family_seed,
        derived_identity=derived_identity,
        timestep_hours=artifact.timestep_hours,
        timestamp_utc=timestamp_utc,
        canonical_field_series=trimmed_series,
        cloud_event_annotations=trimmed_annotations,
    )


def _sample_multivariate_day(
    *,
    mean_vector: Sequence[float],
    cholesky_factor: Sequence[Sequence[float]],
    rng: Random,
) -> tuple[float, ...]:
    standard_normal = [rng.gauss(0.0, 1.0) for _ in range(len(mean_vector))]
    sampled_values = []
    for row_index, row in enumerate(cholesky_factor):
        value = mean_vector[row_index]
        value += sum(
            row[column_index] * standard_normal[column_index]
            for column_index in range(row_index + 1)
        )
        sampled_values.append(value)
    return tuple(sampled_values)


def _reshape_daily_vector(
    sampled_vector: Sequence[float],
    *,
    field_order: Sequence[str],
    intervals_per_day: int,
) -> dict[str, tuple[float, ...]]:
    reshaped: dict[str, tuple[float, ...]] = {}
    for field_index, field_name in enumerate(field_order):
        start_index = field_index * intervals_per_day
        end_index = start_index + intervals_per_day
        reshaped[field_name] = tuple(sampled_vector[start_index:end_index])
    return reshaped


def _cholesky_factor(
    covariance_matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    size = len(covariance_matrix)
    jitter = 0.0
    for _ in range(8):
        try:
            lower = [[0.0] * size for _ in range(size)]
            for row_index in range(size):
                for column_index in range(row_index + 1):
                    covariance_value = covariance_matrix[row_index][column_index]
                    if row_index == column_index:
                        covariance_value += jitter
                    inner_product = sum(
                        lower[row_index][k] * lower[column_index][k]
                        for k in range(column_index)
                    )
                    value = covariance_value - inner_product
                    if row_index == column_index:
                        if value <= 0.0:
                            raise ValueError("covariance_matrix must be positive semi-definite")
                        lower[row_index][column_index] = sqrt(value)
                    else:
                        lower[row_index][column_index] = value / lower[column_index][column_index]
            return tuple(tuple(row) for row in lower)
        except ValueError:
            jitter = 1e-10 if jitter == 0.0 else jitter * 10.0

    raise ValueError("covariance_matrix must be positive semi-definite")


def _timestamp_sequence(
    *,
    artifact: WeatherArtifact,
    num_steps: int,
) -> tuple[str, ...]:
    first_timestamp = str(artifact.training_record_summary["first_timestamp_utc"])
    timestamp = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
    local_timezone = ZoneInfo(artifact.timezone_name)
    local_timestamp = timestamp.astimezone(local_timezone)
    delta = timedelta(hours=artifact.timestep_hours)

    timestamps = []
    for _ in range(num_steps):
        timestamps.append(
            local_timestamp.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        local_timestamp = local_timestamp + delta
    return tuple(timestamps)


def _family_id(
    *,
    artifact_id: str,
    family_seed: int,
    scenario_count: int,
    num_steps: int,
) -> str:
    digest = sha1(
        f"{artifact_id}|{family_seed}|{scenario_count}|{num_steps}".encode("utf-8")
    ).hexdigest()[:12]
    return f"weather-family:{digest}"


def _seeded_random(
    namespace: str,
    *,
    family_seed: int,
    scenario_index: int,
) -> Random:
    seed_bytes = sha256(
        f"{namespace}:{family_seed}:{scenario_index}".encode("utf-8")
    ).digest()
    return Random(int.from_bytes(seed_bytes[:8], byteorder="big", signed=False))


__all__ = [
    "SampledWeatherTrace",
    "WeatherSamplingRequest",
    "WeatherScenarioFamily",
    "sample_weather_family",
]
