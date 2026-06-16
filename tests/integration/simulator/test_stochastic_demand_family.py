"""Integration contracts for cooling-aware paired demand-family evaluation."""

from __future__ import annotations

import importlib
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
        scenario_id="stochastic-demand-integration-base",
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
            source="integration-test-placeholder",
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


def _local_cooling_service_configuration():
    module = _simulator_demand_module()
    return module.CoolingServiceConfiguration(
        service_path="local-electric",
        local_electric_cooling=module.LocalElectricCoolingConfiguration(
            source_name="integration-test-local-cooling",
            electric_kw_per_rt=1.15,
            valid_for_feature_version="008-weather-demand-modeling",
        ),
        source="integration-test",
    )


def _district_cooling_service_configuration(*, served_cooling_rt=None):
    module = _simulator_demand_module()
    return module.CoolingServiceConfiguration(
        service_path="district-cooling",
        district_cooling_tariff=module.DistrictCoolingTariff(
            currency="USD",
            rate_per_rt_hour=0.22,
            time_alignment="step-start",
            tariff_name="integration-test-district",
        ),
        district_served_cooling_rt=served_cooling_rt,
        source="integration-test",
    )


def test_local_electric_and_district_cooling_paths_produce_distinct_accounting() -> None:
    module = _stochastic_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    base_scenario = _base_scenario(weather_family)
    requested_fields = (
        "site_electric_load_kw",
        "local_cooling_electric_kw",
        "served_cooling_rt",
        "unserved_cooling_rt",
        "net_grid_power_kw",
        "step_settlement",
        "district_cooling_settlement",
    )

    local_result = module.evaluate_demand_family(
        module.DemandFamilyEvaluationRequest(
            base_scenario_reference=base_scenario,
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=_local_cooling_service_configuration(),
            summary_output_fields=requested_fields,
            numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
        )
    )
    district_result = module.evaluate_demand_family(
        module.DemandFamilyEvaluationRequest(
            base_scenario_reference=base_scenario,
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=_district_cooling_service_configuration(),
            summary_output_fields=requested_fields,
            numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
        )
    )

    assert local_result.cooling_service_path == "local-electric"
    assert district_result.cooling_service_path == "district-cooling"
    assert [item.scenario_index for item in local_result.scenario_results] == [0, 1]
    assert [item.scenario_index for item in district_result.scenario_results] == [0, 1]

    for local_item, district_item, sampled_trace in zip(
        local_result.scenario_results,
        district_result.scenario_results,
        demand_family.sampled_traces,
        strict=True,
    ):
        assert local_item.non_thermal_electric_demand_kw == pytest.approx(
            sampled_trace.non_thermal_electric_demand_kw,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert district_item.non_thermal_electric_demand_kw == pytest.approx(
            sampled_trace.non_thermal_electric_demand_kw,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert local_item.cooling_demand_rt == pytest.approx(
            sampled_trace.cooling_demand_rt,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert district_item.cooling_demand_rt == pytest.approx(
            sampled_trace.cooling_demand_rt,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(local_item.site_electric_load_kw) == pytest.approx(
            [
                non_thermal + cooling_kw
                for non_thermal, cooling_kw in zip(
                    local_item.non_thermal_electric_demand_kw,
                    local_item.local_cooling_electric_kw,
                    strict=True,
                )
            ],
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(district_item.local_cooling_electric_kw) == pytest.approx(
            [0.0] * demand_family.num_steps,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(district_item.site_electric_load_kw) == pytest.approx(
            district_item.non_thermal_electric_demand_kw,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(district_item.served_cooling_rt) == pytest.approx(
            sampled_trace.cooling_demand_rt,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(district_item.unserved_cooling_rt) == pytest.approx(
            [0.0] * demand_family.num_steps,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert any(
            value > DEFAULT_ABSOLUTE_TOLERANCE
            for value in district_item.district_cooling_settlement
        )

    assert local_result.summary_statistics["site_electric_load_kw"] != pytest.approx(
        district_result.summary_statistics["site_electric_load_kw"],
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_blackout_traces_remain_simulator_side_and_do_not_mutate_sampled_demand() -> None:
    module = _stochastic_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    original_demand_traces = tuple(
        (
            trace.non_thermal_electric_demand_kw,
            trace.cooling_demand_rt,
            trace.local_civil_step_labels,
        )
        for trace in demand_family.sampled_traces
    )
    blackout_family = replace(
        weather_family,
        blackout_traces=(
            {
                "scenario_index": 0,
                "grid_available": [False, True, False],
                "interval_annotations": ["grid-blackout", "", "grid-blackout"],
            },
            {
                "scenario_index": 1,
                "grid_available": [True, True, True],
                "interval_annotations": ["", "", ""],
            },
        ),
    )

    result = module.evaluate_demand_family(
        module.DemandFamilyEvaluationRequest(
            base_scenario_reference=_base_scenario(blackout_family),
            weather_family=blackout_family,
            demand_family=demand_family,
            cooling_service_configuration=_local_cooling_service_configuration(),
            summary_output_fields=("unserved_cooling_rt", "step_settlement"),
            numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
        )
    )

    assert tuple(result.scenario_results[0].blackout_active) == (True, False, True)
    assert tuple(result.scenario_results[1].blackout_active) == (False, False, False)

    for scenario_result, sampled_trace, original_trace in zip(
        result.scenario_results,
        demand_family.sampled_traces,
        original_demand_traces,
        strict=True,
    ):
        assert scenario_result.non_thermal_electric_demand_kw == pytest.approx(
            original_trace[0],
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert scenario_result.cooling_demand_rt == pytest.approx(
            original_trace[1],
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert sampled_trace.non_thermal_electric_demand_kw == original_trace[0]
        assert sampled_trace.cooling_demand_rt == original_trace[1]
        assert sampled_trace.local_civil_step_labels == original_trace[2]
