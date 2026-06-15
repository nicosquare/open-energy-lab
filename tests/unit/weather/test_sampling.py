"""Unit coverage for seeded offline weather-family sampling contracts."""

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


def _load_supported_artifact():
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


@pytest.mark.parametrize("num_steps", [1, 2, 5, 9])
def test_sample_weather_family_supports_arbitrary_positive_horizons(
    num_steps: int,
) -> None:
    artifact = _load_supported_artifact()
    request = WeatherSamplingRequest(
        num_steps=num_steps,
        scenario_count=3,
        family_seed=17,
    )

    family = sample_weather_family(
        artifact,
        request=request,
        expected_timestep_hours=24.0,
    )

    assert _field(family, "num_steps") == num_steps
    assert _field(family, "scenario_count") == 3
    assert _field(family, "family_seed") == 17

    traces = _field(family, "sampled_traces")
    assert isinstance(traces, Sequence)
    assert len(traces) == 3

    for scenario_index, trace in enumerate(traces):
        assert _field(trace, "scenario_index") == scenario_index
        assert _field(trace, "family_seed") == 17
        assert _field(trace, "derived_identity")
        assert _field(trace, "timestep_hours") == pytest.approx(24.0)

        timestamp_utc = _field(trace, "timestamp_utc")
        assert len(timestamp_utc) == num_steps

        canonical_field_series = _field(trace, "canonical_field_series")
        assert tuple(canonical_field_series.keys()) == artifact.canonical_field_order[1:]
        assert all(
            len(canonical_field_series[field_name]) == num_steps
            for field_name in artifact.canonical_field_order[1:]
        )

        annotations = _field(trace, "cloud_event_annotations")
        assert isinstance(annotations, Sequence)


def test_sample_weather_family_is_reproducible_from_family_seed_and_ordering() -> None:
    artifact = _load_supported_artifact()
    request = WeatherSamplingRequest(num_steps=7, scenario_count=4, family_seed=23)

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
    changed_seed_family = sample_weather_family(
        artifact,
        request=WeatherSamplingRequest(num_steps=7, scenario_count=4, family_seed=24),
        expected_timestep_hours=24.0,
    )

    assert _normalize(first_family) == _normalize(repeated_family)
    assert _normalize(first_family) != _normalize(changed_seed_family)


def test_sample_weather_family_rejects_non_positive_request_values() -> None:
    artifact = _load_supported_artifact()

    with pytest.raises(ValueError, match="num_steps"):
        sample_weather_family(
            artifact,
            request=WeatherSamplingRequest(num_steps=0, scenario_count=1, family_seed=1),
            expected_timestep_hours=24.0,
        )

    with pytest.raises(ValueError, match="scenario_count"):
        sample_weather_family(
            artifact,
            request=WeatherSamplingRequest(num_steps=1, scenario_count=0, family_seed=1),
            expected_timestep_hours=24.0,
        )


def test_sample_weather_family_rejects_expected_timestep_mismatch() -> None:
    artifact = _load_supported_artifact()
    request = WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=9)

    with pytest.raises(ValueError, match="expected artifact timestep_hours 12"):
        sample_weather_family(
            artifact,
            request=request,
            expected_timestep_hours=12.0,
        )
