from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.control import PVSelfConsumptionConfig, PVSelfConsumptionController
from open_energy_lab.simulator.stochastic_demand import (
    DemandFamilyEvaluationRequest,
    evaluate_demand_family,
)
from tests.unit.simulator.test_stochastic_demand import (
    _base_scenario,
    _local_cooling_service_configuration,
    _sample_demand_family_fixture,
    _sample_weather_family_fixture,
)


def test_existing_controller_runs_every_stochastic_trace_deterministically() -> None:
    weather_family = _sample_weather_family_fixture()
    weather_family = replace(
        weather_family,
        blackout_traces=tuple(
            {
                "scenario_index": trace.scenario_index,
                "grid_available": [False] * weather_family.num_steps,
                "interval_annotations": ["planning-study"] * weather_family.num_steps,
            }
            for trace in weather_family.sampled_traces
        ),
    )
    demand_family = _sample_demand_family_fixture(weather_family)
    base_scenario = _base_scenario(weather_family)
    base_scenario = replace(
        base_scenario,
        battery=replace(base_scenario.battery, min_soc=0.1),
    )
    controller = PVSelfConsumptionController(
        PVSelfConsumptionConfig(
            reserve_min_soc=0.1,
            reserve_max_soc=1.0,
            charge_request_kw=3.0,
            discharge_request_kw=3.0,
        )
    )
    request = DemandFamilyEvaluationRequest(
        base_scenario_reference=base_scenario,
        weather_family=weather_family,
        demand_family=demand_family,
        cooling_service_configuration=_local_cooling_service_configuration(),
        controller=controller,
    )

    first = evaluate_demand_family(request)
    second = evaluate_demand_family(request)

    assert first == second
    assert first.controller_name == "PVSelfConsumptionController"
    assert len(first.scenario_results) == weather_family.scenario_count
    for scenario_result in first.scenario_results:
        assert len(scenario_result.pv_generation_kw) == weather_family.num_steps
        assert len(scenario_result.requested_battery_power_kw) == weather_family.num_steps
        assert len(scenario_result.realized_battery_power_kw) == weather_family.num_steps
        assert len(scenario_result.battery_soc) == weather_family.num_steps
        assert all(0.1 <= value <= 1.0 for value in scenario_result.battery_soc)
        assert scenario_result.requested_battery_power_kw != pytest.approx(
            [0.0] * weather_family.num_steps
        )


def test_omitted_controller_preserves_direct_trace_mode() -> None:
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    result = evaluate_demand_family(
        DemandFamilyEvaluationRequest(
            base_scenario_reference=_base_scenario(weather_family),
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=_local_cooling_service_configuration(),
        )
    )
    assert result.controller_name == "direct-trace"
    scenario_result = result.scenario_results[0]
    assert len(scenario_result.pv_generation_kw) == weather_family.num_steps
    assert len(scenario_result.requested_battery_power_kw) == weather_family.num_steps
    assert len(scenario_result.realized_battery_power_kw) == weather_family.num_steps
    assert len(scenario_result.battery_soc) == weather_family.num_steps
