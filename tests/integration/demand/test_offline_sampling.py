"""Integration coverage for offline demand-family sampling from loaded artifacts."""

from __future__ import annotations

from collections.abc import Mapping

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


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


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


def _load_demand_artifact_fixture():
    return load_demand_artifact(
        load_demand_fixture(FITTED_DEMAND_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )


def _sample_weather_family_fixture():
    weather_artifact = load_weather_artifact(
        load_weather_fixture(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )
    return sample_weather_family(
        weather_artifact,
        request=WeatherSamplingRequest(
            num_steps=7,
            scenario_count=10,
            family_seed=31,
        ),
        expected_timestep_hours=24.0,
    )


def test_offline_sampling_returns_exact_horizon_and_preserves_scenario_ordering() -> None:
    demand_artifact = _load_demand_artifact_fixture()
    weather_family = _sample_weather_family_fixture()
    request_type = _request_type()

    family = _sample_demand_family(
        artifact=demand_artifact,
        request=request_type(
            weather_family_reference=weather_family,
            num_steps=7,
            scenario_count=10,
            paired_family_seed=31,
        ),
    )

    assert _field(family, "artifact_reference") == demand_artifact.artifact_id
    assert _field(family, "weather_family_reference") == weather_family.family_id
    assert _field(family, "paired_family_seed") == 31
    assert _field(family, "scenario_count") == 10
    assert _field(family, "num_steps") == 7
    assert _field(family, "timestep_hours") == pytest.approx(24.0)

    traces = _field(family, "sampled_traces")
    assert len(traces) == 10

    for scenario_index, (trace, weather_trace) in enumerate(
        zip(traces, weather_family.sampled_traces, strict=True)
    ):
        assert _field(trace, "scenario_index") == scenario_index
        assert _field(trace, "paired_family_seed") == 31
        assert _field(trace, "weather_trace_reference") == weather_trace.derived_identity
        assert _field(trace, "timestep_hours") == pytest.approx(24.0)
        assert len(_field(trace, "local_civil_step_labels")) == 7
        assert len(_field(trace, "non_thermal_electric_demand_kw")) == 7
        assert len(_field(trace, "cooling_demand_rt")) == 7
        assert all(value >= 0.0 for value in _field(trace, "non_thermal_electric_demand_kw"))
        assert all(value >= 0.0 for value in _field(trace, "cooling_demand_rt"))
