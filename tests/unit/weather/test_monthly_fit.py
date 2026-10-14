"""Unit tests for the opt-in monthly (seasonal) weather model."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import fmean

import pytest

from open_energy_lab.weather._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    LOCAL_CIVIL_TIME_BASIS,
    SOURCE_FIELD_LABELS,
    CanonicalWeatherDataset,
)
from open_energy_lab.weather.fit import WeatherFitConfig, fit_weather_dataset
from open_energy_lab.weather.sampling import WeatherSamplingRequest, sample_weather_family


def _two_month_dataset(*, july_days: int = 4) -> CanonicalWeatherDataset:
    """Six-hour UTC records: cool January days and hot July days."""

    starts = [datetime(2024, 1, day, tzinfo=timezone.utc) for day in range(1, 5)]
    starts += [datetime(2024, 7, day, tzinfo=timezone.utc) for day in range(1, july_days + 1)]
    stamps = [start + timedelta(hours=6 * step) for start in starts for step in range(4)]
    series: dict[str, list[object]] = {
        "timestamp_utc": [stamp.strftime("%Y-%m-%dT%H:%M:%SZ") for stamp in stamps]
    }
    for field_name in CANONICAL_WEATHER_FIELD_ORDER[1:]:
        series[field_name] = [0.0] * len(stamps)
    series["dry_bulb_air_temperature_c"] = [
        (15.0 if stamp.month == 1 else 40.0) + (stamp.day % 3) + stamp.hour / 6
        for stamp in stamps
    ]
    return CanonicalWeatherDataset(
        dataset_id="two-month-test",
        latitude=24.4,
        longitude=54.6,
        source_name="unit-test",
        source_metadata={},
        timezone_name="UTC",
        time_basis=LOCAL_CIVIL_TIME_BASIS,
        timestep_hours=6.0,
        timestamp_utc=tuple(series["timestamp_utc"]),
        local_civil_step_labels=tuple(
            stamp.isoformat() for stamp in stamps
        ),
        canonical_field_order=CANONICAL_WEATHER_FIELD_ORDER,
        field_series={name: tuple(values) for name, values in series.items()},
        source_field_labels=dict(SOURCE_FIELD_LABELS),
    )


def test_monthly_fit_samples_each_scenario_from_one_season() -> None:
    artifact = fit_weather_dataset(
        _two_month_dataset(),
        fit_config=WeatherFitConfig(timestep_hours=6.0, monthly=True),
    )
    components = artifact.base_model_parameters["monthly_components"]

    assert artifact.base_model_kind == "monthly-daily-block-summary"
    assert artifact.artifact_id == "weather-artifact:two-month-test:monthly"
    assert [c["month"] for c in components] == [1, 7]
    assert [c["training_day_count"] for c in components] == [4, 4]

    family = sample_weather_family(
        artifact,
        request=WeatherSamplingRequest(num_steps=4, scenario_count=200, family_seed=3),
    )
    daily_means = [
        fmean(trace.canonical_field_series["dry_bulb_air_temperature_c"])
        for trace in family.sampled_traces
    ]
    # A single all-year Gaussian centers near 29 C; seasonal samples stay near
    # 17 C (January) or 42 C (July) and both seasons appear.
    assert all(abs(value - 17.0) < 4.0 or abs(value - 42.0) < 4.0 for value in daily_means)
    assert any(value < 25.0 for value in daily_means)
    assert any(value > 35.0 for value in daily_means)


def test_default_fit_keeps_the_single_joint_model() -> None:
    artifact = fit_weather_dataset(
        _two_month_dataset(), fit_config=WeatherFitConfig(timestep_hours=6.0)
    )

    assert artifact.base_model_kind == "joint-daily-block-summary"
    assert artifact.artifact_id == "weather-artifact:two-month-test"
    assert "monthly_components" not in artifact.base_model_parameters


def test_monthly_fit_needs_two_complete_days_per_month() -> None:
    with pytest.raises(ValueError, match="two complete days per month"):
        fit_weather_dataset(
            _two_month_dataset(july_days=1),
            fit_config=WeatherFitConfig(timestep_hours=6.0, monthly=True),
        )
