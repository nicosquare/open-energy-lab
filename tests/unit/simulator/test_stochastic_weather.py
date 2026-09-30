"""Unit contracts for simulator-side stochastic weather family evaluation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.simulator import (
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    TimeGrid,
    WeatherComponent,
)
from open_energy_lab.simulator.pricing import ArbitrageObjectiveRepresentation
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


_REQUESTED_SUMMARY_FIELDS = (
    "pv_generation_kw",
    "net_grid_power_kw",
    "unmet_load_kw",
    "step_settlement",
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
    deferred_fields = (
        "relative_humidity_pct",
        "infrared_radiation_downwards_w_per_m2",
        "windspeed_10m_m_per_s",
        "wind_direction_10m_deg",
        "surface_air_pressure_pa",
    )
    return WeatherComponent(
        name=f"sampled-weather-{trace.scenario_index}",
        time_grid=TimeGrid(num_steps=len(trace.timestamp_utc), time_step_hours=trace.timestep_hours),
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
        deferred_fields=deferred_fields,
        source=trace.derived_identity,
    )


def _base_scenario() -> BatteryLoadPVScenario:
    family = _sample_weather_family_fixture()
    weather = _weather_from_trace(family.sampled_traces[0])
    grid = weather.time_grid
    return BatteryLoadPVScenario(
        scenario_id="stochastic-weather-base",
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
            source="unit-test",
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
            source="unit-test",
        ),
    )


def test_weather_family_request_tracks_base_scenario_and_sampled_family() -> None:
    family = _sample_weather_family_fixture()
    base_scenario = _base_scenario()

    request = WeatherFamilyEvaluationRequest(
        base_scenario_reference=base_scenario,
        weather_family=family,
        summary_output_fields=_REQUESTED_SUMMARY_FIELDS,
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    assert request.base_scenario_reference is base_scenario
    assert request.weather_family.family_id == family.family_id
    assert request.summary_output_fields == _REQUESTED_SUMMARY_FIELDS
    assert request.numeric_tolerance == pytest.approx(DEFAULT_ABSOLUTE_TOLERANCE)


def test_weather_family_evaluation_returns_blackout_and_unmet_load_series() -> None:
    family = _sample_weather_family_fixture()
    blackout_traces = tuple(
        {
            "scenario_index": trace.scenario_index,
            "grid_available": [False] * family.num_steps,
            "interval_annotations": ["grid-outage"] * family.num_steps,
        }
        for trace in family.sampled_traces
    )
    request = WeatherFamilyEvaluationRequest(
        base_scenario_reference=_base_scenario(),
        weather_family=replace(family, blackout_traces=blackout_traces),
        summary_output_fields=_REQUESTED_SUMMARY_FIELDS,
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    result = evaluate_weather_family(request)
    first_result = result.scenario_results[0]

    assert first_result.scenario_index == 0
    assert len(first_result.blackout_active) == family.num_steps
    assert len(first_result.unmet_load_kw) == family.num_steps
    assert all(isinstance(value, bool) for value in first_result.blackout_active)
    assert all(value >= 0.0 for value in first_result.unmet_load_kw)
    assert all(first_result.blackout_active)


def test_weather_family_result_exposes_requested_summary_fields() -> None:
    family = _sample_weather_family_fixture()
    request = WeatherFamilyEvaluationRequest(
        base_scenario_reference=_base_scenario(),
        weather_family=family,
        summary_output_fields=_REQUESTED_SUMMARY_FIELDS,
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    result = evaluate_weather_family(request)

    assert set(result.supported_summary_fields) >= set(_REQUESTED_SUMMARY_FIELDS)
    assert set(result.summary_statistics) >= set(_REQUESTED_SUMMARY_FIELDS)
    for field_name in _REQUESTED_SUMMARY_FIELDS:
        assert len(result.summary_statistics[field_name]) == 6
