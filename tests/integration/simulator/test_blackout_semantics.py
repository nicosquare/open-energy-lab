"""Integration contracts for blackout-aware simulator weather families."""

from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    TimeGrid,
    WeatherComponent,
)
from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE, POSITIVE_DISPATCH_MEANING
from open_energy_lab.simulator.stochastic_weather import (
    WeatherFamilyEvaluationRequest,
    evaluate_weather_family,
)
from open_energy_lab.weather import WeatherSamplingRequest, load_weather_artifact, sample_weather_family
from tests.integration.weather.fixture_utils import (
    FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
    load_weather_fixture,
)


def _sample_weather_family_fixture():
    artifact = load_weather_artifact(
        load_weather_fixture(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )
    return sample_weather_family(
        artifact,
        request=WeatherSamplingRequest(
            num_steps=3,
            scenario_count=2,
            family_seed=13,
        ),
        expected_timestep_hours=24.0,
    )


def _weather_from_trace(trace) -> WeatherComponent:
    grid = TimeGrid(num_steps=len(trace.timestamp_utc), time_step_hours=trace.timestep_hours)
    return WeatherComponent(
        name=f"sampled-weather-{trace.scenario_index}",
        time_grid=grid,
        timestamp_utc=list(trace.timestamp_utc),
        dry_bulb_air_temperature_c=list(
            trace.canonical_field_series["dry_bulb_air_temperature_c"]
        ),
        global_horizontal_irradiance_w_per_m2=list(
            trace.canonical_field_series["global_horizontal_irradiance_w_per_m2"]
        ),
        direct_beam_irradiance_w_per_m2=list(
            trace.canonical_field_series["direct_beam_irradiance_w_per_m2"]
        ),
        diffuse_horizontal_irradiance_w_per_m2=list(
            trace.canonical_field_series["diffuse_horizontal_irradiance_w_per_m2"]
        ),
        deferred_fields=(
            "relative_humidity_pct",
            "infrared_radiation_downwards_w_per_m2",
            "windspeed_10m_m_per_s",
            "wind_direction_10m_deg",
            "surface_air_pressure_pa",
        ),
        source=trace.derived_identity,
    )


def _build_base_scenario(weather: WeatherComponent) -> BatteryLoadPVScenario:
    grid = weather.time_grid
    return BatteryLoadPVScenario(
        scenario_id="stochastic-weather-blackout",
        time_grid=grid,
        battery=BatteryComponent(
            name="battery",
            capacity_kwh=8.0,
            max_charge_kw=3.0,
            max_discharge_kw=3.0,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
            initial_soc=0.25,
        ),
        load=LoadComponent(
            name="load",
            demand_kw=[3.0, 1.0, 4.0],
            interpretation="exogenous-consumption",
            time_grid=grid,
            source="integration-test",
        ),
        weather=weather,
        pv=PVComponent(
            name="pv",
            rated_power_kw=4.0,
            temperature_coefficient_pct_per_c=-0.4,
            reference_irradiance_w_per_m2=1000.0,
            reference_temperature_c=25.0,
            derivation_name="ghi-linear-temperature-adjusted",
            irradiance_field_names=("global_horizontal_irradiance_w_per_m2",),
        ),
        price_signal=PriceSignal(
            currency="USD",
            unit_rate_name="energy-price",
            import_prices=[0.10, 0.20, 0.30],
            export_price_ratio=0.8,
            interpretation="discounted export relative to import prices",
            time_alignment="step-start",
            time_grid=grid,
        ),
        objective=ArbitrageObjectiveRepresentation(
            objective_name="grid-settlement",
            settlement_basis="grid-settlement",
            allow_export=True,
            export_price_ratio=0.8,
        ),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=[0.0, 0.0, 0.0],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="integration-test",
        ),
    )


def _blackout_traces_for(family) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "scenario_index": trace.scenario_index,
            "grid_available": [False] * family.num_steps,
            "interval_annotations": ["grid-outage"] * family.num_steps,
        }
        for trace in family.sampled_traces
    )


def _expected_no_blackout_trace(trace):
    return _build_base_scenario(_weather_from_trace(trace)).evaluate_trace()


def test_blackouts_disable_grid_exchange_and_surface_unmet_load() -> None:
    family = _sample_weather_family_fixture()
    request = WeatherFamilyEvaluationRequest(
        base_scenario_reference=_build_base_scenario(_weather_from_trace(family.sampled_traces[0])),
        weather_family=replace(family, blackout_traces=_blackout_traces_for(family)),
        summary_output_fields=("pv_generation_kw", "net_grid_power_kw", "unmet_load_kw", "step_settlement"),
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    result = evaluate_weather_family(request)
    expected_traces = tuple(_expected_no_blackout_trace(trace) for trace in family.sampled_traces)

    for scenario_result, expected_trace in zip(
        result.scenario_results,
        expected_traces,
        strict=True,
    ):
        expected_unmet_load = [
            max(0.0, value) for value in expected_trace.net_grid_power_kw
        ]

        assert list(scenario_result.blackout_active) == [True] * family.num_steps
        assert scenario_result.pv_generation_kw == pytest.approx(
            expected_trace.pv_generation_kw,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.net_grid_power_kw == pytest.approx(
            [0.0] * family.num_steps,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.step_settlement == pytest.approx(
            [0.0] * family.num_steps,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.total_settlement == pytest.approx(0.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)
        assert scenario_result.unmet_load_kw == pytest.approx(
            expected_unmet_load,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert any(value > 0.0 for value in scenario_result.unmet_load_kw)
