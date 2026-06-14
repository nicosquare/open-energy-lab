"""Artifact fitting helpers for the stochastic-weather feature."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from math import isclose
from pathlib import Path
from statistics import fmean
from zoneinfo import ZoneInfo

from open_energy_lab.simulator._weather_schema import (
    IRRADIANCE_FIELD_NAMES,
    iter_weather_field_specs,
)

from ._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    CanonicalWeatherDataset,
    LOCAL_CIVIL_TIME_BASIS,
)
from .artifact import WeatherArtifact
from .tmy import fetch_tmy_dataset


@dataclass(frozen=True, slots=True)
class WeatherFitConfig:
    """Minimal placeholder for the planned fit-configuration surface."""

    timestep_hours: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def fit_weather_model(
    latitude: float,
    longitude: float,
    *,
    recorded_response: dict[str, object] | None = None,
    fetcher: object | None = None,
    timezone_name: str | None = None,
    source_name: str = "PVGIS TMY",
    fit_config: WeatherFitConfig | None = None,
    output_path: str | Path | None = None,
) -> WeatherArtifact:
    """Fit a deterministic first-release artifact from one recorded TMY response."""

    config = fit_config or WeatherFitConfig(timestep_hours=1.0)
    dataset = fetch_tmy_dataset(
        latitude,
        longitude,
        recorded_response=recorded_response,
        fetcher=fetcher,
        timezone_name=timezone_name,
        source_name=source_name,
        timestep_hours=config.timestep_hours,
    )
    created_at = datetime.now(tz=ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    record_count = len(dataset.timestamp_utc)
    intervals_per_day = _intervals_per_day(dataset.timestep_hours)
    training_matrix, training_day_count, padding_mode = _build_joint_training_matrix(
        dataset,
        intervals_per_day=intervals_per_day,
    )
    numeric_field_order = tuple(
        spec.field_name for spec in iter_weather_field_specs() if spec.field_name != "timestamp_utc"
    )
    numeric_field_summaries = _field_summaries(dataset)
    mean_vector = _mean_vector(training_matrix)
    covariance_matrix = _covariance_matrix(training_matrix, regularization=1e-8)
    cloud_event_model = _fit_cloud_event_model(dataset, intervals_per_day=intervals_per_day)

    artifact = WeatherArtifact(
        artifact_id=f"weather-artifact:{dataset.dataset_id}",
        schema_version="v1",
        feature_name="007-stochastic-weather",
        created_at=created_at,
        latitude=dataset.latitude,
        longitude=dataset.longitude,
        timezone_name=dataset.timezone_name,
        time_basis=LOCAL_CIVIL_TIME_BASIS,
        timestep_hours=dataset.timestep_hours,
        canonical_field_order=CANONICAL_WEATHER_FIELD_ORDER,
        training_record_summary={
            "dataset_id": dataset.dataset_id,
            "record_count": record_count,
            "first_timestamp_utc": dataset.timestamp_utc[0],
            "last_timestamp_utc": dataset.timestamp_utc[-1],
            "local_step_count": len(dataset.local_civil_step_labels),
        },
        base_model_kind="joint-daily-block-summary",
        base_model_parameters={
            "intervals_per_day": intervals_per_day,
            "field_order": list(numeric_field_order),
            "mean_vector": mean_vector,
            "covariance_matrix": covariance_matrix,
            "training_day_count": training_day_count,
            "regularization_note": padding_mode,
            "field_summaries": numeric_field_summaries,
            "physical_bounds_policy": _physical_bounds_policy(),
        },
        cloud_event_model=cloud_event_model,
        provenance={
            "source_name": dataset.source_name,
            "source_metadata": dataset.source_metadata,
            "source_field_labels": dataset.source_field_labels,
            "fit_notes": list(config.notes),
        },
        supported_load_modes=("offline",),
    )
    if output_path is not None:
        artifact.write_json(output_path)
    return artifact


__all__ = ["WeatherFitConfig", "fit_weather_model"]


def _intervals_per_day(timestep_hours: float) -> int:
    intervals = 24.0 / timestep_hours
    rounded = round(intervals)
    if not isclose(intervals, rounded, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("timestep_hours must evenly divide one local civil day")
    return max(1, int(rounded))


def _field_summaries(dataset: CanonicalWeatherDataset) -> dict[str, dict[str, float]]:
    return {
        field_name: {
            "min": min(values),
            "mean": fmean(values),
            "max": max(values),
        }
        for field_name, values in dataset.field_series.items()
        if field_name != "timestamp_utc"
    }


def _build_joint_training_matrix(
    dataset: CanonicalWeatherDataset,
    *,
    intervals_per_day: int,
) -> tuple[list[list[float]], int, str]:
    numeric_field_order = tuple(dataset.canonical_field_order[1:])
    day_rows: dict[str, list[int]] = {}
    for index, local_label in enumerate(dataset.local_civil_step_labels):
        local_day = local_label.split("T", maxsplit=1)[0]
        day_rows.setdefault(local_day, []).append(index)

    training_matrix: list[list[float]] = []
    for indices in day_rows.values():
        if len(indices) != intervals_per_day:
            continue
        vector: list[float] = []
        for field_name in numeric_field_order:
            values = dataset.field_series[field_name]
            vector.extend(float(values[index]) for index in indices)
        training_matrix.append(vector)

    if training_matrix:
        return training_matrix, len(training_matrix), "complete_local_days_only"

    padded_vector = _build_padded_day_vector(dataset, intervals_per_day=intervals_per_day)
    return [padded_vector], 1, "padded_single_day_from_available_record"


def _build_padded_day_vector(
    dataset: CanonicalWeatherDataset,
    *,
    intervals_per_day: int,
) -> list[float]:
    numeric_field_order = tuple(dataset.canonical_field_order[1:])
    vector: list[float] = []
    for field_name in numeric_field_order:
        source_values = tuple(float(value) for value in dataset.field_series[field_name])
        padded_values = [
            source_values[min(index, len(source_values) - 1)]
            for index in range(intervals_per_day)
        ]
        vector.extend(padded_values)
    return vector


def _mean_vector(training_matrix: list[list[float]]) -> list[float]:
    feature_count = len(training_matrix[0])
    return [
        fmean(row[column_index] for row in training_matrix)
        for column_index in range(feature_count)
    ]


def _covariance_matrix(
    training_matrix: list[list[float]],
    *,
    regularization: float,
) -> list[list[float]]:
    feature_count = len(training_matrix[0])
    mean_vector = _mean_vector(training_matrix)
    row_count = len(training_matrix)
    covariance_rows: list[list[float]] = []
    scale = 1.0 / max(1, row_count - 1)
    for row_index in range(feature_count):
        covariance_row: list[float] = []
        for column_index in range(feature_count):
            covariance = scale * sum(
                (row[row_index] - mean_vector[row_index])
                * (row[column_index] - mean_vector[column_index])
                for row in training_matrix
            )
            if row_index == column_index:
                covariance += regularization
            covariance_row.append(covariance)
        covariance_rows.append(covariance_row)
    return covariance_rows


def _physical_bounds_policy() -> dict[str, object]:
    return {
        "bounds_by_field": {
            "dry_bulb_air_temperature_c": {"minimum": None, "maximum": None},
            "global_horizontal_irradiance_w_per_m2": {"minimum": 0.0, "maximum": None},
            "direct_beam_irradiance_w_per_m2": {"minimum": 0.0, "maximum": None},
            "diffuse_horizontal_irradiance_w_per_m2": {"minimum": 0.0, "maximum": None},
            "relative_humidity_pct": {"minimum": 0.0, "maximum": 100.0},
            "infrared_radiation_downwards_w_per_m2": {"minimum": 0.0, "maximum": None},
            "windspeed_10m_m_per_s": {"minimum": 0.0, "maximum": None},
            "wind_direction_10m_deg": {"minimum": 0.0, "maximum": 360.0},
            "surface_air_pressure_pa": {"minimum": 0.0, "maximum": None},
        },
        "non_negative_fields": [
            "global_horizontal_irradiance_w_per_m2",
            "direct_beam_irradiance_w_per_m2",
            "diffuse_horizontal_irradiance_w_per_m2",
            "relative_humidity_pct",
            "infrared_radiation_downwards_w_per_m2",
            "windspeed_10m_m_per_s",
            "surface_air_pressure_pa",
        ],
    }


def _fit_cloud_event_model(
    dataset: CanonicalWeatherDataset,
    *,
    intervals_per_day: int,
) -> dict[str, object]:
    minimum_base_irradiance = 50.0
    ghi_values = tuple(
        float(value)
        for value in dataset.field_series["global_horizontal_irradiance_w_per_m2"]
    )
    start_counts = [0] * intervals_per_day
    day_count = max(1, len(dataset.local_civil_step_labels) // intervals_per_day)
    durations: list[int] = []
    attenuations: list[float] = []

    for start_index in range(1, len(ghi_values)):
        previous = ghi_values[start_index - 1]
        current = ghi_values[start_index]
        local_step = start_index % intervals_per_day
        if previous <= minimum_base_irradiance or current >= previous:
            continue

        attenuation = max(0.0, min(0.95, 1.0 - (current / previous)))
        if attenuation < 0.15:
            continue

        start_counts[local_step] += 1
        duration = 1
        cursor = start_index + 1
        while cursor < len(ghi_values) and ghi_values[cursor] <= ghi_values[cursor - 1]:
            duration += 1
            cursor += 1
        durations.append(duration)
        attenuations.append(attenuation)

    duration_counts = Counter(durations)
    attenuation_counts = Counter(round(value, 3) for value in attenuations)
    return {
        "irradiance_fields": list(IRRADIANCE_FIELD_NAMES),
        "start_probability_by_local_step": [
            count / day_count for count in start_counts
        ],
        "duration_distribution": {
            "kind": "empirical",
            "durations": sorted(duration_counts),
            "probabilities": [
                duration_counts[duration] / max(1, len(durations))
                for duration in sorted(duration_counts)
            ],
        },
        "attenuation_distribution": {
            "kind": "empirical",
            "attenuation_values": sorted(attenuation_counts),
            "probabilities": [
                attenuation_counts[value] / max(1, len(attenuations))
                for value in sorted(attenuation_counts)
            ],
        },
        "minimum_base_irradiance_w_per_m2": minimum_base_irradiance,
        "calibration_summary": {
            "event_count": len(durations),
            "training_record_count": len(ghi_values),
            "inferred_day_count": day_count,
        },
    }
