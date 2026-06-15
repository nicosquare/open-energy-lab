"""Integration coverage for offline weather-family sampling from loaded artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass

import pytest

from open_energy_lab.weather.artifact import load_weather_artifact
from open_energy_lab.weather.sampling import WeatherSamplingRequest, sample_weather_family
from tests.integration.weather.fixture_utils import (
    FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
    load_weather_fixture,
)


def _artifact_fixture():
    return load_weather_artifact(
        load_weather_fixture(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _normalize(value: object) -> object:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Mapping):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    return value


def test_offline_sampling_is_reproducible_from_a_loaded_artifact() -> None:
    artifact = _artifact_fixture()
    request = WeatherSamplingRequest(num_steps=7, scenario_count=4, family_seed=31)

    first_family = sample_weather_family(
        artifact,
        request=request,
        expected_timestep_hours=24.0,
    )
    repeated_family = sample_weather_family(
        artifact,
        request=request,
        expected_timestep_hours=24.0,
    )

    assert _normalize(first_family) == _normalize(repeated_family)


@pytest.mark.parametrize("num_steps", [1, 3, 9])
def test_offline_sampling_returns_exact_requested_num_steps(num_steps: int) -> None:
    artifact = _artifact_fixture()
    family = sample_weather_family(
        artifact,
        request=WeatherSamplingRequest(
            num_steps=num_steps,
            scenario_count=2,
            family_seed=13,
        ),
        expected_timestep_hours=24.0,
    )

    assert _field(family, "num_steps") == num_steps
    traces = _field(family, "sampled_traces")
    assert len(traces) == 2

    for trace in traces:
        assert len(_field(trace, "timestamp_utc")) == num_steps
        canonical_field_series = _field(trace, "canonical_field_series")
        assert tuple(canonical_field_series.keys()) == artifact.canonical_field_order[1:]
        assert all(
            len(canonical_field_series[field_name]) == num_steps
            for field_name in artifact.canonical_field_order[1:]
        )
