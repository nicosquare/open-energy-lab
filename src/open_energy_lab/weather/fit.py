"""Artifact fitting helpers for the stochastic-weather feature."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import fmean
from zoneinfo import ZoneInfo

from open_energy_lab.simulator._weather_schema import IRRADIANCE_FIELD_NAMES

from ._canonical import CANONICAL_WEATHER_FIELD_ORDER, LOCAL_CIVIL_TIME_BASIS
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
    intervals_per_day = max(1, round(24 / dataset.timestep_hours))
    numeric_field_summaries = {
        field_name: {
            "min": min(values),
            "mean": fmean(values),
            "max": max(values),
        }
        for field_name, values in dataset.field_series.items()
        if field_name != "timestamp_utc"
    }

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
            "field_order": list(dataset.canonical_field_order),
            "training_day_count": max(1, record_count // intervals_per_day),
            "field_summaries": numeric_field_summaries,
            "physical_bounds_policy": {
                "non_negative_fields": list(IRRADIANCE_FIELD_NAMES)
                + [
                    "relative_humidity_pct",
                    "windspeed_10m_m_per_s",
                    "surface_air_pressure_pa",
                ],
            },
        },
        cloud_event_model={
            "irradiance_fields": list(IRRADIANCE_FIELD_NAMES),
            "start_probability_by_local_step": [],
            "duration_distribution": {"kind": "placeholder", "parameters": []},
            "attenuation_distribution": {"kind": "placeholder", "parameters": []},
            "minimum_base_irradiance_w_per_m2": 0.0,
            "calibration_summary": "placeholder until stochastic calibration is implemented",
        },
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
