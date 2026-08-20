"""Unit coverage for demand sampling request validation."""

from __future__ import annotations

from dataclasses import replace

import pytest

import open_energy_lab.demand.sampling as demand_sampling_module
from open_energy_lab.demand.fit import fit_demand_model
from open_energy_lab.demand.study_inputs import build_synthetic_demand_training_payload
from open_energy_lab.demand.artifact import load_demand_artifact
from open_energy_lab.weather.fit import WeatherFitConfig, fit_weather_model
from open_energy_lab.weather.tmy import fetch_tmy_dataset
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
    RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH,
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
        request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=13),
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


def test_sample_demand_family_rejects_non_positive_request_values() -> None:
    artifact = _load_supported_demand_artifact()
    weather_family = _sample_supported_weather_family()
    request_type = _request_type()

    with pytest.raises(ValueError, match="num_steps"):
        _sample_demand_family(
            artifact=artifact,
            request=request_type(
                weather_family_reference=weather_family,
                num_steps=0,
                scenario_count=2,
                paired_family_seed=13,
            ),
        )

    with pytest.raises(ValueError, match="scenario_count"):
        _sample_demand_family(
            artifact=artifact,
            request=request_type(
                weather_family_reference=weather_family,
                num_steps=3,
                scenario_count=0,
                paired_family_seed=13,
            ),
        )


def test_sample_demand_family_rejects_weather_family_timestep_mismatch() -> None:
    artifact = _load_supported_demand_artifact()
    weather_family = _sample_supported_weather_family()
    mismatched_family = replace(weather_family, timestep_hours=12.0)
    request_type = _request_type()

    with pytest.raises(ValueError, match="timestep"):
        _sample_demand_family(
            artifact=artifact,
            request=request_type(
                weather_family_reference=mismatched_family,
                num_steps=3,
                scenario_count=2,
                paired_family_seed=13,
            ),
        )


def test_hourly_demand_baseline_and_residuals_align_to_local_start_step() -> None:
    response = load_weather_fixture(RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH)
    dataset = fetch_tmy_dataset(
        24.4539,
        54.3773,
        recorded_response=response,
        timezone_name="Asia/Dubai",
    )
    weather_artifact = fit_weather_model(
        24.4539,
        54.3773,
        recorded_response=response,
        timezone_name="Asia/Dubai",
        fit_config=WeatherFitConfig(timestep_hours=1.0),
    )
    demand_artifact = fit_demand_model(
        build_synthetic_demand_training_payload(dataset)
    )
    midnight_weather = sample_weather_family(
        weather_artifact,
        request=WeatherSamplingRequest(
            num_steps=8,
            scenario_count=1,
            family_seed=13,
        ),
    )
    shifted_weather = sample_weather_family(
        weather_artifact,
        request=WeatherSamplingRequest(
            num_steps=3,
            scenario_count=1,
            family_seed=13,
            local_start_step=5,
        ),
    )
    midnight = _sample_demand_family(
        artifact=demand_artifact,
        request=demand_sampling_module.DemandSamplingRequest(
            weather_family_reference=midnight_weather,
            num_steps=8,
            scenario_count=1,
            paired_family_seed=13,
        ),
    )
    shifted = _sample_demand_family(
        artifact=demand_artifact,
        request=demand_sampling_module.DemandSamplingRequest(
            weather_family_reference=shifted_weather,
            num_steps=3,
            scenario_count=1,
            paired_family_seed=13,
            local_start_step=5,
        ),
    )

    assert shifted.sampled_traces[0].non_thermal_electric_demand_kw == (
        midnight.sampled_traces[0].non_thermal_electric_demand_kw[5:8]
    )
    assert shifted.sampled_traces[0].cooling_demand_rt == (
        midnight.sampled_traces[0].cooling_demand_rt[5:8]
    )
    assert shifted.local_start_step == 5
