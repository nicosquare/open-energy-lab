"""Integration contracts for cooling-service validation and unserved demand."""

from __future__ import annotations

import importlib
import pytest

from open_energy_lab.demand import DemandSamplingRequest, load_demand_artifact, sample_demand_family
from open_energy_lab.simulator import (
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
)
from open_energy_lab.simulator.pricing import ArbitrageObjectiveRepresentation
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
        scenario_id="cooling-service-validation-base",
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


def test_evaluate_demand_family_rejects_mixed_cooling_paths() -> None:
    demand_module = _simulator_demand_module()

    with pytest.raises(ValueError, match="exactly one|mixed|service path"):
        demand_module.CoolingServiceConfiguration(
            service_path="local-electric",
            local_electric_cooling=demand_module.LocalElectricCoolingConfiguration(
                source_name="mixed-local-cooling",
                electric_kw_per_rt=1.15,
                valid_for_feature_version="008-weather-demand-modeling",
            ),
            district_cooling_tariff=demand_module.DistrictCoolingTariff(
                currency="USD",
                rate_per_rt_hour=0.22,
                time_alignment="step-start",
                tariff_name="mixed-district",
            ),
            source="integration-test",
        )


def test_evaluate_demand_family_rejects_district_cooling_without_tariff() -> None:
    module = _stochastic_demand_module()
    demand_module = _simulator_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)

    with pytest.raises(ValueError, match="district|tariff"):
        module.evaluate_demand_family(
            module.DemandFamilyEvaluationRequest(
                base_scenario_reference=_base_scenario(weather_family),
                weather_family=weather_family,
                demand_family=demand_family,
                cooling_service_configuration=demand_module.CoolingServiceConfiguration(
                    service_path="district-cooling",
                    district_served_cooling_rt=[
                        list(trace.cooling_demand_rt) for trace in demand_family.sampled_traces
                    ],
                    source="integration-test",
                ),
                summary_output_fields=("served_cooling_rt",),
                numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
            )
        )


def test_evaluate_demand_family_rejects_district_over_service() -> None:
    module = _stochastic_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)

    served_cooling_rt = [
        [trace.cooling_demand_rt[0] + 1.0, *trace.cooling_demand_rt[1:]]
        for trace in demand_family.sampled_traces
    ]

    with pytest.raises(ValueError, match="serve more thermal demand|served_cooling_rt|over-service"):
        module.evaluate_demand_family(
            module.DemandFamilyEvaluationRequest(
                base_scenario_reference=_base_scenario(weather_family),
                weather_family=weather_family,
                demand_family=demand_family,
                cooling_service_configuration=_district_configuration(
                    served_cooling_rt=served_cooling_rt
                ),
                summary_output_fields=("served_cooling_rt", "unserved_cooling_rt"),
                numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
            )
        )


def test_partial_district_service_reports_unserved_cooling_explicitly() -> None:
    module = _stochastic_demand_module()
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    served_cooling_rt = [
        [0.0, min(2.0, trace.cooling_demand_rt[1]), 0.0]
        for trace in demand_family.sampled_traces
    ]

    result = module.evaluate_demand_family(
        module.DemandFamilyEvaluationRequest(
            base_scenario_reference=_base_scenario(weather_family),
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=_district_configuration(
                served_cooling_rt=served_cooling_rt
            ),
            summary_output_fields=(
                "served_cooling_rt",
                "unserved_cooling_rt",
                "district_cooling_settlement",
                "site_electric_load_kw",
            ),
            numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
        )
    )

    for scenario_result, sampled_trace, configured_service in zip(
        result.scenario_results,
        demand_family.sampled_traces,
        served_cooling_rt,
        strict=True,
    ):
        assert tuple(scenario_result.site_electric_load_kw) == pytest.approx(
            sampled_trace.non_thermal_electric_demand_kw,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(scenario_result.served_cooling_rt) == pytest.approx(
            configured_service,
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert tuple(scenario_result.unserved_cooling_rt) == pytest.approx(
            [
                demand_value - served_value
                for demand_value, served_value in zip(
                    sampled_trace.cooling_demand_rt,
                    configured_service,
                    strict=True,
                )
            ],
            abs=DEFAULT_ABSOLUTE_TOLERANCE,
        )
        assert any(
            value > DEFAULT_ABSOLUTE_TOLERANCE
            for value in scenario_result.unserved_cooling_rt
        )


def _district_configuration(*, served_cooling_rt):
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
