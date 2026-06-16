"""Unit contracts for paired stochastic demand-family evaluation."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from dataclasses import replace

import pytest

from open_energy_lab.demand import DemandSamplingRequest, load_demand_artifact, sample_demand_family
from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    TimeGrid,
)
from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE, POSITIVE_DISPATCH_MEANING
from open_energy_lab.simulator.weather import weather_component_from_sampled_trace
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


def _stochastic_demand_module():
    try:
        return importlib.import_module("open_energy_lab.simulator.stochastic_demand")
    except ModuleNotFoundError:
        pytest.fail("open_energy_lab.simulator.stochastic_demand is not implemented")


def _simulator_demand_module():
    try:
        return importlib.import_module("open_energy_lab.simulator.demand")
    except ModuleNotFoundError:
        pytest.fail("open_energy_lab.simulator.demand is not implemented")


def _sample_weather_family_fixture():
    artifact = load_weather_artifact(
        load_weather_fixture(FITTED_WEATHER_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )
    return sample_weather_family(
        artifact,
        request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=13),
        expected_timestep_hours=24.0,
    )


def _sample_demand_family_fixture(weather_family):
    artifact = load_demand_artifact(
        load_demand_fixture(FITTED_DEMAND_ARTIFACT_FIXTURE_PATH),
        expected_timestep_hours=24.0,
    )
    return sample_demand_family(
        artifact,
        request=DemandSamplingRequest(
            weather_family_reference=weather_family,
            num_steps=3,
            scenario_count=2,
            paired_family_seed=13,
        ),
    )


def _base_scenario(weather_family) -> BatteryLoadPVScenario:
    weather = weather_component_from_sampled_trace(weather_family.sampled_traces[0])
    grid = weather.time_grid
    return BatteryLoadPVScenario(
        scenario_id="stochastic-demand-unit-base",
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
            name="placeholder-load",
            demand_kw=[0.0] * grid.num_steps,
            interpretation="exogenous-consumption",
            time_grid=grid,
            source="unit-test-placeholder",
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


def _local_cooling_service_configuration():
    module = _simulator_demand_module()
    return module.CoolingServiceConfiguration(
        service_path="local-electric",
        local_electric_cooling=module.LocalElectricCoolingConfiguration(
            source_name="unit-test-local-cooling",
            electric_kw_per_rt=1.15,
            valid_for_feature_version="008-weather-demand-modeling",
        ),
        source="unit-test",
    )


def _expected_summary_series(
    scenario_results: Sequence[object],
    field_name: str,
) -> dict[str, tuple[float, ...]]:
    series_by_scenario = [tuple(getattr(result, field_name)) for result in scenario_results]
    per_step_values = [
        [float(values[step_index]) for values in series_by_scenario]
        for step_index in range(len(series_by_scenario[0]))
    ]
    return {
        "min": _reduce_per_step(per_step_values, "min"),
        "mean": _reduce_per_step(per_step_values, "mean"),
        "max": _reduce_per_step(per_step_values, "max"),
        "p05": _reduce_per_step(per_step_values, "5"),
        "p50": _reduce_per_step(per_step_values, "50"),
        "p95": _reduce_per_step(per_step_values, "95"),
    }


def _reduce_per_step(
    per_step_values: Sequence[Sequence[float]],
    statistic: str,
) -> tuple[float, ...]:
    reduced: list[float] = []
    for step_values in per_step_values:
        ordered = sorted(float(value) for value in step_values)
        if statistic == "min":
            reduced.append(ordered[0])
        elif statistic == "mean":
            reduced.append(sum(ordered) / len(ordered))
        elif statistic == "max":
            reduced.append(ordered[-1])
        else:
            reduced.append(_percentile(ordered, float(statistic)))
    return tuple(reduced)


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


def test_evaluate_demand_family_rejects_paired_seed_mismatch() -> None:
    module = _stochastic_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    mismatched_family = replace(demand_family, paired_family_seed=91)

    request = module.DemandFamilyEvaluationRequest(
        base_scenario_reference=_base_scenario(weather_family),
        weather_family=weather_family,
        demand_family=mismatched_family,
        cooling_service_configuration=_local_cooling_service_configuration(),
        summary_output_fields=("site_electric_load_kw",),
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    with pytest.raises(ValueError, match="paired|seed"):
        module.evaluate_demand_family(request)


def test_evaluate_demand_family_rejects_scenario_index_misalignment() -> None:
    module = _stochastic_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    out_of_order_trace = replace(demand_family.sampled_traces[0], scenario_index=9)
    misaligned_family = replace(
        demand_family,
        sampled_traces=(out_of_order_trace, *demand_family.sampled_traces[1:]),
    )

    request = module.DemandFamilyEvaluationRequest(
        base_scenario_reference=_base_scenario(weather_family),
        weather_family=weather_family,
        demand_family=misaligned_family,
        cooling_service_configuration=_local_cooling_service_configuration(),
        summary_output_fields=("site_electric_load_kw",),
        numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
    )

    with pytest.raises(ValueError, match="scenario|ordering|alignment|index"):
        module.evaluate_demand_family(request)


def test_evaluate_demand_family_returns_fixed_summary_buckets_for_requested_fields() -> None:
    module = _stochastic_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    request_fields = (
        "site_electric_load_kw",
        "local_cooling_electric_kw",
        "served_cooling_rt",
        "unserved_cooling_rt",
        "net_grid_power_kw",
        "step_settlement",
    )

    result = module.evaluate_demand_family(
        module.DemandFamilyEvaluationRequest(
            base_scenario_reference=_base_scenario(weather_family),
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=_local_cooling_service_configuration(),
            summary_output_fields=request_fields,
            numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
        )
    )

    assert isinstance(result.family_id, str) and result.family_id
    assert result.paired_family_seed == 13
    assert result.timestep_hours == pytest.approx(24.0)
    assert result.cooling_service_path == "local-electric"
    assert set(result.summary_statistics) == set(request_fields)
    assert set(result.supported_summary_fields) >= set(request_fields)
    assert [item.scenario_index for item in result.scenario_results] == [0, 1]

    for scenario_result in result.scenario_results:
        assert scenario_result.site_electric_load_kw != pytest.approx(
            [0.0, 0.0, 0.0],
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(scenario_result.site_electric_load_kw) == pytest.approx(
            [
                non_thermal + cooling_kw
                for non_thermal, cooling_kw in zip(
                    scenario_result.non_thermal_electric_demand_kw,
                    scenario_result.local_cooling_electric_kw,
                    strict=True,
                )
            ],
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )

    for field_name in request_fields:
        assert result.summary_statistics[field_name] == pytest.approx(
            _expected_summary_series(result.scenario_results, field_name),
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
