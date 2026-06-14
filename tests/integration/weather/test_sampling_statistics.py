"""Stochastic acceptance coverage for offline weather-family sampling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import cos, pi, sin, sqrt
from random import Random

import pytest

from open_energy_lab.weather.artifact import load_weather_artifact
from open_energy_lab.weather.sampling import WeatherSamplingRequest, sample_weather_family


FIELD_ORDER = (
    "dry_bulb_air_temperature_c",
    "global_horizontal_irradiance_w_per_m2",
    "direct_beam_irradiance_w_per_m2",
    "diffuse_horizontal_irradiance_w_per_m2",
    "relative_humidity_pct",
    "infrared_radiation_downwards_w_per_m2",
    "windspeed_10m_m_per_s",
    "wind_direction_10m_deg",
    "surface_air_pressure_pa",
)
CORRELATION_FIELDS = tuple(
    field_name for field_name in FIELD_ORDER if field_name != "wind_direction_10m_deg"
)


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


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


def _build_training_days(
    *,
    seed: int = 20260614,
    day_count: int = 96,
    intervals_per_day: int = 6,
) -> list[list[list[float]]]:
    rng = Random(seed)
    hour_indices = [step * (24.0 / intervals_per_day) for step in range(intervals_per_day)]
    days: list[list[list[float]]] = []

    for day_index in range(day_count):
        day_rows: list[list[float]] = []
        weekly_scale = 1.0 + 0.08 * sin(2.0 * pi * day_index / 7.0)
        cloud_bias = 1.0 - 0.12 * cos(2.0 * pi * day_index / 9.0)
        for hour_value in hour_indices:
            diurnal_phase = 2.0 * pi * hour_value / 24.0
            solar_shape = max(0.0, sin(pi * (hour_value - 4.0) / 12.0))

            temperature = 24.0 + 8.0 * sin(diurnal_phase - 0.75) + rng.gauss(0.0, 0.8)
            ghi = max(
                0.0,
                820.0 * solar_shape * weekly_scale * cloud_bias + rng.gauss(0.0, 28.0),
            )
            dni = max(0.0, ghi * (0.67 + 0.05 * cos(diurnal_phase - 0.2)) + rng.gauss(0.0, 18.0))
            dhi = max(0.0, ghi * (0.30 + 0.04 * sin(diurnal_phase + 0.3)) + rng.gauss(0.0, 10.0))
            humidity = min(
                100.0,
                max(0.0, 62.0 - 0.75 * (temperature - 20.0) + rng.gauss(0.0, 3.0)),
            )
            infrared = max(0.0, 280.0 + 2.2 * temperature + rng.gauss(0.0, 5.0))
            windspeed = max(
                0.0,
                3.1 + 0.7 * sin(diurnal_phase + day_index / 5.0) + rng.gauss(0.0, 0.25),
            )
            wind_direction = (
                155.0
                + 20.0 * sin(diurnal_phase + 0.5)
                + 4.0 * day_index
                + rng.gauss(0.0, 4.0)
            ) % 360.0
            pressure = max(
                0.0,
                101050.0 + 95.0 * cos(diurnal_phase - 0.4) + rng.gauss(0.0, 14.0),
            )

            day_rows.append(
                [
                    temperature,
                    ghi,
                    dni,
                    dhi,
                    humidity,
                    infrared,
                    windspeed,
                    wind_direction,
                    pressure,
                ]
            )
        days.append(day_rows)

    return days


def _flatten_training_days(training_days: list[list[list[float]]]) -> list[list[float]]:
    flattened_days: list[list[float]] = []
    for day_rows in training_days:
        vector: list[float] = []
        for field_index in range(len(FIELD_ORDER)):
            vector.extend(step[field_index] for step in day_rows)
        flattened_days.append(vector)
    return flattened_days


def _baseline_statistics(training_days: list[list[list[float]]]) -> dict[str, object]:
    series_by_field = {
        field_name: [step[field_index] for day_rows in training_days for step in day_rows]
        for field_index, field_name in enumerate(FIELD_ORDER)
    }
    lag1_by_field = {
        field_name: _lag1_correlation(series_by_field[field_name])
        for field_name in CORRELATION_FIELDS
    }
    pairwise_correlation = _pairwise_correlation_matrix(
        [series_by_field[field_name] for field_name in CORRELATION_FIELDS]
    )
    return {
        "lag1_by_field": lag1_by_field,
        "pairwise_correlation": pairwise_correlation,
    }


def _statistics_artifact():
    training_days = _build_training_days()
    flattened_days = _flatten_training_days(training_days)
    mean_vector = [
        sum(day_vector[column_index] for day_vector in flattened_days) / len(flattened_days)
        for column_index in range(len(flattened_days[0]))
    ]
    covariance_matrix = _covariance_matrix(flattened_days, regularization=1e-6)
    baseline = _baseline_statistics(training_days)
    steps_per_day = len(training_days[0])
    total_steps = len(training_days) * steps_per_day

    artifact = load_weather_artifact(
        {
            "artifact_id": "weather-artifact:synthetic-us2-statistics",
            "schema_version": "v1",
            "feature_name": "007-stochastic-weather",
            "created_at": "2026-06-14T00:00:00Z",
            "latitude": 33.4484,
            "longitude": -112.0740,
            "timezone_name": "America/Phoenix",
            "time_basis": "local_civil_time",
            "timestep_hours": 4.0,
            "canonical_field_order": [
                "timestamp_utc",
                *FIELD_ORDER,
            ],
            "training_record_summary": {
                "dataset_id": "synthetic-weather-statistics:v1",
                "record_count": total_steps,
                "first_timestamp_utc": "2024-01-01T00:00:00Z",
                "last_timestamp_utc": "2024-04-06T20:00:00Z",
                "local_step_count": total_steps,
            },
            "base_model_kind": "joint-daily-block-summary",
            "base_model_parameters": {
                "intervals_per_day": steps_per_day,
                "field_order": list(FIELD_ORDER),
                "mean_vector": mean_vector,
                "covariance_matrix": covariance_matrix,
                "training_day_count": len(training_days),
                "regularization_note": "synthetic-statistics-acceptance",
                "field_summaries": {
                    field_name: {
                        "min": min(
                            step[field_index] for day_rows in training_days for step in day_rows
                        ),
                        "mean": sum(
                            step[field_index] for day_rows in training_days for step in day_rows
                        )
                        / total_steps,
                        "max": max(
                            step[field_index] for day_rows in training_days for step in day_rows
                        ),
                    }
                    for field_index, field_name in enumerate(FIELD_ORDER)
                },
                "physical_bounds_policy": _physical_bounds_policy(),
            },
            "cloud_event_model": {
                "irradiance_fields": [
                    "global_horizontal_irradiance_w_per_m2",
                    "direct_beam_irradiance_w_per_m2",
                    "diffuse_horizontal_irradiance_w_per_m2",
                ],
                "start_probability_by_local_step": [0.0, 0.0, 0.35, 0.40, 0.15, 0.0],
                "duration_distribution": {
                    "kind": "empirical",
                    "durations": [2, 3, 4],
                    "probabilities": [0.45, 0.35, 0.20],
                },
                "attenuation_distribution": {
                    "kind": "empirical",
                    "attenuation_values": [0.20, 0.35, 0.50],
                    "probabilities": [0.30, 0.45, 0.25],
                },
                "minimum_base_irradiance_w_per_m2": 120.0,
                "calibration_summary": {
                    "event_count": 192,
                    "training_record_count": total_steps,
                    "inferred_day_count": len(training_days),
                },
            },
            "provenance": {
                "source_name": "Synthetic statistics acceptance artifact",
                "source_metadata": {
                    "generation_method": "integration-test",
                    "derived_from": "documented-us2-contract",
                },
                "source_field_labels": {
                    "timestamp_utc": "Date & time (UTC)",
                    "dry_bulb_air_temperature_c": "T2m [°C]",
                    "global_horizontal_irradiance_w_per_m2": "G(h) [W/m2]",
                    "direct_beam_irradiance_w_per_m2": "Gb(n) [W/m2]",
                    "diffuse_horizontal_irradiance_w_per_m2": "Gd(h) [W/m2]",
                    "relative_humidity_pct": "RH [%]",
                    "infrared_radiation_downwards_w_per_m2": "IR(h) [W/m2]",
                    "windspeed_10m_m_per_s": "WS10m [m/s]",
                    "wind_direction_10m_deg": "WD10m [°]",
                    "surface_air_pressure_pa": "SP [Pa]",
                },
                "fit_notes": [
                    "synthetic-statistics-acceptance",
                ],
            },
            "supported_load_modes": ["offline"],
        },
        expected_timestep_hours=4.0,
    )
    return artifact, baseline


def _lag1_correlation(series: Sequence[float]) -> float:
    if len(series) < 2:
        return 0.0
    return _pearson_correlation(series[:-1], series[1:])


def _pearson_correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("correlation inputs must have equal lengths")
    if not left:
        return 0.0

    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    numerator = sum(a * b for a, b in zip(left_centered, right_centered, strict=True))
    left_scale = sqrt(sum(value * value for value in left_centered))
    right_scale = sqrt(sum(value * value for value in right_centered))
    if left_scale == 0.0 or right_scale == 0.0:
        return 0.0
    return numerator / (left_scale * right_scale)


def _pairwise_correlation_matrix(series_list: Sequence[Sequence[float]]) -> list[list[float]]:
    return [
        [_pearson_correlation(left, right) for right in series_list]
        for left in series_list
    ]


def _covariance_matrix(
    rows: Sequence[Sequence[float]],
    *,
    regularization: float,
) -> list[list[float]]:
    feature_count = len(rows[0])
    mean_vector = [
        sum(row[column_index] for row in rows) / len(rows)
        for column_index in range(feature_count)
    ]
    scale = 1.0 / max(1, len(rows) - 1)
    covariance_rows: list[list[float]] = []
    for row_index in range(feature_count):
        covariance_row: list[float] = []
        for column_index in range(feature_count):
            covariance = scale * sum(
                (row[row_index] - mean_vector[row_index])
                * (row[column_index] - mean_vector[column_index])
                for row in rows
            )
            if row_index == column_index:
                covariance += regularization
            covariance_row.append(covariance)
        covariance_rows.append(covariance_row)
    return covariance_rows


def _collect_family_traces(family: object) -> Sequence[object]:
    traces = _field(family, "sampled_traces")
    assert isinstance(traces, Sequence)
    return traces


def _sampled_lag1_by_field(traces: Sequence[object]) -> dict[str, float]:
    lag1_values: dict[str, float] = {}
    for field_name in CORRELATION_FIELDS:
        scenario_lag1 = []
        for trace in traces:
            canonical_field_series = _field(trace, "canonical_field_series")
            scenario_lag1.append(_lag1_correlation(canonical_field_series[field_name]))
        lag1_values[field_name] = sum(scenario_lag1) / len(scenario_lag1)
    return lag1_values


def _sampled_pairwise_correlation(traces: Sequence[object]) -> list[list[float]]:
    concatenated = []
    for field_name in CORRELATION_FIELDS:
        field_chunks: list[float] = []
        for trace in traces:
            canonical_field_series = _field(trace, "canonical_field_series")
            field_chunks.extend(float(value) for value in canonical_field_series[field_name])
        concatenated.append(field_chunks)
    return _pairwise_correlation_matrix(concatenated)


def _assert_physical_bounds(traces: Sequence[object], physical_bounds_policy: Mapping[str, object]) -> None:
    bounds_by_field = physical_bounds_policy["bounds_by_field"]
    for trace in traces:
        canonical_field_series = _field(trace, "canonical_field_series")
        for field_name, bounds in bounds_by_field.items():
            values = [float(value) for value in canonical_field_series[field_name]]
            minimum = bounds["minimum"]
            maximum = bounds["maximum"]
            if minimum is not None:
                assert min(values) >= float(minimum) - 1e-9
            if maximum is not None:
                assert max(values) <= float(maximum) + 1e-9


def _cloud_event_annotations(traces: Sequence[object]) -> list[object]:
    annotations: list[object] = []
    for trace in traces:
        trace_annotations = _field(trace, "cloud_event_annotations")
        assert isinstance(trace_annotations, Sequence)
        annotations.extend(trace_annotations)
    return annotations


@pytest.mark.parametrize("family_seed", list(range(10)))
def test_sampling_statistics_preserve_documented_acceptance_thresholds(
    family_seed: int,
) -> None:
    artifact, baseline = _statistics_artifact()
    family = sample_weather_family(
        artifact,
        request=WeatherSamplingRequest(
            num_steps=168,
            scenario_count=100,
            family_seed=family_seed,
        ),
        expected_timestep_hours=4.0,
    )

    traces = _collect_family_traces(family)
    assert len(traces) == 100

    _assert_physical_bounds(
        traces,
        artifact.base_model_parameters["physical_bounds_policy"],
    )

    sampled_lag1 = _sampled_lag1_by_field(traces)
    lag1_errors = [
        abs(sampled_lag1[field_name] - baseline["lag1_by_field"][field_name])
        for field_name in CORRELATION_FIELDS
    ]
    lag1_mae = sum(lag1_errors) / len(lag1_errors)
    assert lag1_mae <= 0.15

    sampled_pairwise_correlation = _sampled_pairwise_correlation(traces)
    baseline_pairwise_correlation = baseline["pairwise_correlation"]
    pairwise_errors = []
    for row_index in range(len(sampled_pairwise_correlation)):
        for column_index in range(row_index + 1, len(sampled_pairwise_correlation)):
            pairwise_errors.append(
                abs(
                    sampled_pairwise_correlation[row_index][column_index]
                    - baseline_pairwise_correlation[row_index][column_index]
                )
            )
    pairwise_mae = sum(pairwise_errors) / len(pairwise_errors)
    assert pairwise_mae <= 0.20

    annotations = _cloud_event_annotations(traces)
    assert annotations
    assert len(annotations) >= 50

    multi_step_fraction = sum(
        1 for annotation in annotations if _field(annotation, "duration_steps") >= 2
    ) / len(annotations)
    assert multi_step_fraction >= 0.80
