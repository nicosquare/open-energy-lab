"""Integration contracts for simulator stochastic weather family evaluation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

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


def _expected_trace_for(trace):
    return _build_base_scenario(_weather_from_trace(trace)).evaluate_trace()


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    rank = (len(sorted_values) - 1) * (percentile / 100.0)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - lower_index
    lower_value = float(sorted_values[lower_index])
    upper_value = float(sorted_values[upper_index])
    return lower_value + ((upper_value - lower_value) * fraction)


def _expected_summary_series(expected_traces: Sequence[object], field_name: str) -> tuple[tuple[float, ...], ...]:
    if field_name == "unmet_load_kw":
        field_values = [[0.0, 0.0, 0.0] for _ in expected_traces]
    else:
        field_values = [getattr(trace, field_name) for trace in expected_traces]

    per_step_values = [
        [float(values[step_index]) for values in field_values]
        for step_index in range(len(field_values[0]))
    ]

    def _reduce(statistic: str) -> tuple[float, ...]:
        reduced = []
        for step_values in per_step_values:
            ordered = sorted(step_values)
            if statistic == "min":
                reduced.append(ordered[0])
            elif statistic == "mean":
                reduced.append(sum(ordered) / len(ordered))
            elif statistic == "max":
                reduced.append(ordered[-1])
            else:
                reduced.append(_percentile(ordered, float(statistic)))
        return tuple(reduced)

    return (
        _reduce("min"),
        _reduce("mean"),
        _reduce("max"),
        _reduce("5"),
        _reduce("50"),
        _reduce("95"),
    )


def _summary_series_values(summary_bucket: object) -> list[tuple[float, ...]]:
    if not isinstance(summary_bucket, Mapping):
        raise AssertionError("summary bucket must be a mapping of statistic names to series values")
    normalized = []
    for values in summary_bucket.values():
        if not isinstance(values, Iterable) or isinstance(values, (str, bytes, bytearray)):
            raise AssertionError("summary values must be numeric series")
        normalized.append(tuple(float(value) for value in values))
    return normalized


def _assert_contains_series(
    actual_series: Sequence[tuple[float, ...]],
    expected_series: Sequence[tuple[float, ...]],
) -> None:
    assert len(actual_series) == len(expected_series)
    for expected in expected_series:
        assert any(actual == pytest.approx(expected, abs=DEFAULT_ABSOLUTE_TOLERANCE) for actual in actual_series)


def test_stochastic_weather_family_returns_scenario_indexed_results_from_sampled_weather() -> None:
    family = _sample_weather_family_fixture()
    request = WeatherFamilyEvaluationRequest(
        base_scenario_reference=_build_base_scenario(_weather_from_trace(family.sampled_traces[0])),
        weather_family=family,
        summary_output_fields=_REQUESTED_SUMMARY_FIELDS,
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    result = evaluate_weather_family(request)
    expected_traces = tuple(_expected_trace_for(trace) for trace in family.sampled_traces)

    assert result.family_id == family.family_id
    assert result.family_seed == family.family_seed
    assert result.timestep_hours == pytest.approx(family.timestep_hours)
    assert set(result.supported_summary_fields) >= set(_REQUESTED_SUMMARY_FIELDS)
    assert [item.scenario_index for item in result.scenario_results] == [0, 1]

    for scenario_result, sampled_trace, expected_trace in zip(
        result.scenario_results,
        family.sampled_traces,
        expected_traces,
        strict=True,
    ):
        assert scenario_result.weather_reference == sampled_trace.derived_identity
        assert scenario_result.pv_generation_kw == pytest.approx(
            expected_trace.pv_generation_kw,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.net_grid_power_kw == pytest.approx(
            expected_trace.net_grid_power_kw,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.step_settlement == pytest.approx(
            expected_trace.step_settlement,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.total_settlement == pytest.approx(
            expected_trace.total_settlement,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.unmet_load_kw == pytest.approx(
            [0.0] * family.num_steps,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert list(scenario_result.blackout_active) == [False] * family.num_steps
        assert scenario_result.constraint_events == expected_trace.constraint_events


def test_stochastic_weather_family_returns_fixed_percentile_summaries() -> None:
    family = _sample_weather_family_fixture()
    request = WeatherFamilyEvaluationRequest(
        base_scenario_reference=_build_base_scenario(_weather_from_trace(family.sampled_traces[0])),
        weather_family=family,
        summary_output_fields=_REQUESTED_SUMMARY_FIELDS,
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    result = evaluate_weather_family(request)
    expected_traces = tuple(_expected_trace_for(trace) for trace in family.sampled_traces)

    for field_name in _REQUESTED_SUMMARY_FIELDS:
        actual_series = _summary_series_values(result.summary_statistics[field_name])
        expected_series = _expected_summary_series(expected_traces, field_name)
        _assert_contains_series(actual_series, expected_series)
