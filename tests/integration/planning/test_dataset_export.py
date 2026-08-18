"""Offline integration contracts for simulator-family planning dataset export."""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from open_energy_lab.demand import (
    DemandSamplingRequest,
    load_demand_artifact,
    sample_demand_family,
)
from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    TimeGrid,
    evaluate_demand_family,
)
from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE, POSITIVE_DISPATCH_MEANING
from open_energy_lab.simulator.demand import (
    CoolingServiceConfiguration,
    LocalElectricCoolingConfiguration,
)
from open_energy_lab.simulator.planning_export import (
    PlanningExportRequest,
    export_planning_dataset,
)
from open_energy_lab.simulator.stochastic_demand import DemandFamilyEvaluationRequest
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
from tests.integration.planning.fixture_utils import (
    PLANNING_DATASET_ARTIFACT_FIXTURE_PATH,
    PLANNING_DATASET_EXPORT_FIXTURE_PATH,
    load_planning_fixture,
)
from tests.integration.weather.fixture_utils import (
    FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
    load_weather_fixture,
)
from open_energy_lab.planning.dataset import load_planning_dataset


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
        scenario_id="planning-export-integration-base",
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
            source="planning-export-fixture-placeholder",
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
            source="planning-export-fixture",
        ),
    )


def _cooling_service_configuration() -> CoolingServiceConfiguration:
    return CoolingServiceConfiguration(
        service_path="local-electric",
        local_electric_cooling=LocalElectricCoolingConfiguration(
            source_name="planning-export-local-cooling",
            electric_kw_per_rt=1.15,
            valid_for_feature_version="008-weather-demand-modeling",
            notes="Deterministic first-release conversion factor.",
        ),
        source="planning-export-fixture",
    )


def _evaluated_demand_family():
    weather_family = _sample_weather_family_fixture()
    demand_family = _sample_demand_family_fixture(weather_family)
    result = evaluate_demand_family(
        DemandFamilyEvaluationRequest(
            base_scenario_reference=_base_scenario(weather_family),
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=_cooling_service_configuration(),
            summary_output_fields=("site_electric_load_kw",),
            numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
        )
    )
    return weather_family, result


def _request() -> PlanningExportRequest:
    return PlanningExportRequest(
        export_id="planning-dataset-export-integration",
        flattened_series_fields=(
            "global_horizontal_irradiance_w_per_m2",
            "site_electric_load_kw",
            "unmet_load_kw",
        ),
        design_metadata_rows=(
            {
                "scenario_index": 0,
                "battery_capacity_kwh": 8.0,
                "solar_capacity_kw": 4.0,
                "design_name": "baseline-a",
            },
            {
                "scenario_index": 1,
                "battery_capacity_kwh": 10.0,
                "solar_capacity_kw": 5.0,
                "design_name": "baseline-b",
            },
        ),
        target_name="shortfall",
        include_provenance=True,
        numeric_tolerance=1e-9,
    )


def test_fixture_backed_simulator_families_provide_aligned_export_inputs() -> None:
    weather_family, family_result = _evaluated_demand_family()

    assert family_result.paired_family_seed == weather_family.family_seed
    assert family_result.timestep_hours == pytest.approx(weather_family.timestep_hours)
    assert [trace.scenario_index for trace in weather_family.sampled_traces] == [0, 1]
    assert [result.scenario_index for result in family_result.scenario_results] == [0, 1]
    assert all(
        len(result.site_electric_load_kw) == weather_family.num_steps
        for result in family_result.scenario_results
    )
    assert all(
        len(result.unmet_load_kw) == weather_family.num_steps
        for result in family_result.scenario_results
    )


def test_export_planning_dataset_flattens_fixture_backed_weather_and_load_series() -> None:
    weather_family, family_result = _evaluated_demand_family()

    dataset = export_planning_dataset(
        family_result_reference=family_result,
        weather_family_reference=weather_family,
        request=_request(),
    )

    assert dataset.row_count == 2
    assert dataset.horizon_steps == weather_family.num_steps
    assert dataset.column_order[:7] == (
        "scenario_index",
        "battery_capacity_kwh",
        "solar_capacity_kw",
        "design_name",
        "ghi_0",
        "ghi_1",
        "ghi_2",
    )

    first_row = dataset.rows[0]
    assert first_row["scenario_index"] == 0
    assert first_row["ghi_0"] == pytest.approx(
        weather_family.sampled_traces[0].canonical_field_series[
            "global_horizontal_irradiance_w_per_m2"
        ][0]
    )
    assert first_row["load_0"] == pytest.approx(
        family_result.scenario_results[0].site_electric_load_kw[0]
    )
    assert first_row["unmet_load_2"] == pytest.approx(
        family_result.scenario_results[0].unmet_load_kw[2]
    )


def test_export_planning_dataset_records_shortfall_and_reproducibility_metadata() -> None:
    weather_family, family_result = _evaluated_demand_family()

    dataset = export_planning_dataset(
        family_result_reference=family_result,
        weather_family_reference=weather_family,
        request=_request(),
    )

    expected_shortfall = (
        sum(family_result.scenario_results[0].unmet_load_kw) * family_result.timestep_hours
    ) / (
        sum(family_result.scenario_results[0].site_electric_load_kw) * family_result.timestep_hours
    )

    assert dataset.rows[0]["shortfall"] == pytest.approx(expected_shortfall)
    assert dataset.rows[0]["shortfall_exceeds_threshold"] == int(expected_shortfall > 0.05)
    assert dataset.rows[1]["shortfall"] == pytest.approx(0.0)
    assert dataset.rows[1]["shortfall_exceeds_threshold"] == 0
    assert dataset.provenance["weather_family_id"] == weather_family.family_id
    assert dataset.provenance["family_seed"] == weather_family.family_seed
    assert dataset.export_configuration["row_order_policy"] == "scenario_index_ascending"
    assert dataset.export_configuration["flattened_series_fields"] == [
        "global_horizontal_irradiance_w_per_m2",
        "site_electric_load_kw",
        "unmet_load_kw",
    ]
    assert dataset.target_metadata["event_target_name"] == "shortfall_exceeds_threshold"


def test_committed_planning_dataset_fixture_replays_the_export_contract() -> None:
    weather_family, family_result = _evaluated_demand_family()
    export_fixture = load_planning_fixture(PLANNING_DATASET_EXPORT_FIXTURE_PATH)
    committed_dataset = load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)

    dataset = export_planning_dataset(
        family_result_reference=family_result,
        weather_family_reference=weather_family,
        request=_request(),
    )

    assert committed_dataset.dataset_id == export_fixture["expected_dataset_id"]
    assert committed_dataset.row_count == export_fixture["expected_row_count"]
    assert committed_dataset.horizon_steps == export_fixture["expected_horizon_steps"]
    assert tuple(export_fixture["expected_column_order"]) == committed_dataset.column_order
    assert committed_dataset.column_order == dataset.column_order
    assert committed_dataset.rows == dataset.rows
    assert committed_dataset.design_feature_schema == dataset.design_feature_schema
    assert committed_dataset.series_field_schema == dataset.series_field_schema
    assert committed_dataset.target_metadata == dataset.target_metadata
    assert committed_dataset.export_configuration["flattened_series_fields"] == export_fixture[
        "flattened_series_fields"
    ]
    assert committed_dataset.provenance["family_id"] == dataset.provenance["family_id"]
    assert committed_dataset.provenance["weather_family_id"] == dataset.provenance["weather_family_id"]
    assert committed_dataset.provenance["family_seed"] == dataset.provenance["family_seed"]
    assert committed_dataset.provenance["paired_family_seed"] == dataset.provenance[
        "paired_family_seed"
    ]


def test_dataset_export_and_reload_do_not_import_required_backends(tmp_path) -> None:
    output_path = tmp_path / "planning-dataset.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import sys
                from pathlib import Path

                from open_energy_lab.planning.dataset import load_planning_dataset
                from open_energy_lab.simulator.planning_export import export_planning_dataset
                from tests.integration.planning.test_dataset_export import (
                    _evaluated_demand_family,
                    _request,
                )

                required_backend_roots = {"highspy", "pyomo", "spflow", "torch"}

                def loaded_required_backends():
                    return sorted(
                        module_name
                        for module_name in sys.modules
                        if module_name.split(".", maxsplit=1)[0] in required_backend_roots
                    )

                assert not loaded_required_backends()

                weather_family, family_result = _evaluated_demand_family()
                exported = export_planning_dataset(
                    family_result_reference=family_result,
                    weather_family_reference=weather_family,
                    request=_request(),
                )
                exported.write_json(Path(sys.argv[1]))
                reloaded = load_planning_dataset(Path(sys.argv[1]))

                assert reloaded.dataset_id == exported.dataset_id
                assert reloaded.column_order == exported.column_order
                assert reloaded.rows == exported.rows
                loaded = loaded_required_backends()
                assert not loaded, f"dataset export/reload imported required backends: {loaded}"
                """
            ),
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, (
        "isolated dataset export/reload failed\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
