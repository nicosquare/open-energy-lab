"""Integration coverage for paired weather-and-demand replay reproducibility."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass

import pytest

import open_energy_lab.demand.sampling as demand_sampling_module
from open_energy_lab.demand.artifact import load_demand_artifact
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    load_weather_artifact,
    sample_weather_family,
)
from tests.integration.demand.fixture_utils import (
    FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
    load_demand_fixture,
)
from tests.integration.weather.fixture_utils import (
    FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
    load_weather_fixture,
)


def _request_type():
    try:
        request_type = demand_sampling_module.DemandSamplingRequest
    except AttributeError:
        pytest.fail(
            "open_energy_lab.demand.sampling.DemandSamplingRequest is not implemented"
        )
    return request_type


def _sample_demand_family(*, artifact, request):
    try:
        sample = demand_sampling_module.sample_demand_family
    except AttributeError:
        pytest.fail(
            "open_energy_lab.demand.sampling.sample_demand_family is not implemented"
        )
    return sample(artifact, request=request)


def _normalize(value: object) -> object:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Mapping):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    return value


def _load_demand_artifact_fixture():
    return load_demand_artifact(
        load_demand_fixture(FITTED_DEMAND_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )


def _load_weather_artifact_fixture():
    return load_weather_artifact(
        load_weather_fixture(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )


def test_paired_weather_and_demand_sampling_replays_exactly() -> None:
    demand_artifact = _load_demand_artifact_fixture()
    weather_artifact = _load_weather_artifact_fixture()
    request_type = _request_type()
    weather_request = WeatherSamplingRequest(num_steps=5, scenario_count=3, family_seed=37)

    first_weather_family = sample_weather_family(
        weather_artifact,
        request=weather_request,
        expected_timestep_hours=24.0,
    )
    repeated_weather_family = sample_weather_family(
        weather_artifact,
        request=weather_request,
        expected_timestep_hours=24.0,
    )

    first_demand_family = _sample_demand_family(
        artifact=demand_artifact,
        request=request_type(
            weather_family_reference=first_weather_family,
            num_steps=5,
            scenario_count=3,
            paired_family_seed=37,
        ),
    )
    repeated_demand_family = _sample_demand_family(
        artifact=demand_artifact,
        request=request_type(
            weather_family_reference=repeated_weather_family,
            num_steps=5,
            scenario_count=3,
            paired_family_seed=37,
        ),
    )

    assert _normalize(first_weather_family) == _normalize(repeated_weather_family)
    assert _normalize(first_demand_family) == _normalize(repeated_demand_family)

    for first_weather, repeated_weather, first_demand, repeated_demand in zip(
        first_weather_family.sampled_traces,
        repeated_weather_family.sampled_traces,
        first_demand_family.sampled_traces,
        repeated_demand_family.sampled_traces,
        strict=True,
    ):
        assert first_weather.timestamp_utc == repeated_weather.timestamp_utc
        assert first_weather.canonical_field_series == repeated_weather.canonical_field_series
        assert first_demand.non_thermal_electric_demand_kw == (
            repeated_demand.non_thermal_electric_demand_kw
        )
        assert first_demand.cooling_demand_rt == repeated_demand.cooling_demand_rt
