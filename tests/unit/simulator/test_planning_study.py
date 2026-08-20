from __future__ import annotations

from open_energy_lab.demand import DemandSamplingRequest, load_demand_artifact, sample_demand_family
from open_energy_lab.weather import WeatherSamplingRequest, load_weather_artifact, sample_weather_family
from tests.integration.demand.fixture_utils import FITTED_DEMAND_ARTIFACT_FIXTURE_PATH
from tests.integration.weather.fixture_utils import FITTED_WEATHER_ARTIFACT_FIXTURE_PATH


def test_absolute_sample_indices_make_batches_equal_to_one_full_family() -> None:
    weather_artifact = load_weather_artifact(
        FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
        expected_timestep_hours=24.0,
    )
    full = sample_weather_family(
        weather_artifact,
        request=WeatherSamplingRequest(
            num_steps=3,
            scenario_count=4,
            family_seed=13,
        ),
        expected_timestep_hours=24.0,
    )
    second_batch = sample_weather_family(
        weather_artifact,
        request=WeatherSamplingRequest(
            num_steps=3,
            scenario_count=2,
            family_seed=13,
            scenario_index_start=2,
        ),
        expected_timestep_hours=24.0,
    )

    assert second_batch.sampled_traces == full.sampled_traces[2:]
    assert [trace.scenario_index for trace in second_batch.sampled_traces] == [2, 3]

    demand_artifact = load_demand_artifact(
        FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
        expected_timestep_hours=24.0,
    )
    demand_batch = sample_demand_family(
        demand_artifact,
        request=DemandSamplingRequest(
            weather_family_reference=second_batch,
            num_steps=3,
            scenario_count=2,
            paired_family_seed=13,
            scenario_index_start=2,
        ),
    )
    assert [trace.scenario_index for trace in demand_batch.sampled_traces] == [2, 3]

