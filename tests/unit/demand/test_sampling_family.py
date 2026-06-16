"""Unit coverage for paired offline demand-family sampling contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass, replace

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


def _load_supported_demand_artifact():
    return load_demand_artifact(
        load_demand_fixture(FITTED_DEMAND_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )


def _sample_supported_weather_family():
    artifact = load_weather_artifact(
        load_weather_fixture(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )
    return sample_weather_family(
        artifact,
        request=WeatherSamplingRequest(num_steps=7, scenario_count=4, family_seed=23),
        expected_timestep_hours=24.0,
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


def test_sample_demand_family_is_reproducible_from_paired_family_seed() -> None:
    artifact = _load_supported_demand_artifact()
    weather_family = _sample_supported_weather_family()
    request_type = _request_type()
    request = request_type(
        weather_family_reference=weather_family,
        num_steps=7,
        scenario_count=4,
        paired_family_seed=23,
    )

    first_family = _sample_demand_family(artifact=artifact, request=request)
    repeated_family = _sample_demand_family(artifact=artifact, request=request)

    assert _normalize(first_family) == _normalize(repeated_family)


def test_sample_demand_family_rejects_missing_required_weather_fields() -> None:
    artifact = _load_supported_demand_artifact()
    weather_family = _sample_supported_weather_family()
    request_type = _request_type()
    first_trace = weather_family.sampled_traces[0]
    incomplete_fields = dict(first_trace.canonical_field_series)
    incomplete_fields.pop("relative_humidity_pct")
    incomplete_weather_family = replace(
        weather_family,
        sampled_traces=(
            replace(first_trace, canonical_field_series=incomplete_fields),
            *weather_family.sampled_traces[1:],
        ),
    )

    with pytest.raises(ValueError, match="required weather|weather field"):
        _sample_demand_family(
            artifact=artifact,
            request=request_type(
                weather_family_reference=incomplete_weather_family,
                num_steps=7,
                scenario_count=4,
                paired_family_seed=23,
            ),
        )
