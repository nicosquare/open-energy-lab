from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from open_energy_lab.demand import (
    DemandSamplingRequest,
    load_demand_artifact,
    sample_demand_family,
)
from open_energy_lab.planning import (
    PlanningProblemDefinition,
    assemble_planning_problem,
    solve_planning_problem,
)
from open_energy_lab.simulator import (
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    PVComponent,
    PlanningExportRequest,
    PriceSignal,
    evaluate_demand_family,
    export_planning_dataset,
)
from open_energy_lab.simulator.pricing import ArbitrageObjectiveRepresentation
from open_energy_lab.simulator._units import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    POSITIVE_DISPATCH_MEANING,
)
from open_energy_lab.simulator.demand import (
    CoolingServiceConfiguration,
    LocalElectricCoolingConfiguration,
)
from open_energy_lab.simulator.load import LoadComponent
from open_energy_lab.simulator.stochastic_demand import DemandFamilyEvaluationRequest
from open_energy_lab.simulator.weather import weather_component_from_sampled_trace
from tpm import (
    TPMFitConfig,
    TPMQueryRequest,
    compile_spflow_model_to_mio,
    detect_spflow_backend_capabilities,
    load_tpm_artifact,
    query_tpm_artifact,
)
from open_energy_lab.planning import fit_tpm_artifact
from tpm.optional_spflow import load_spflow_payload
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    load_weather_artifact,
    sample_weather_family,
)


EXAMPLE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_ROOT.parent.parent
OUTPUT_ROOT = REPO_ROOT / "tmp" / "open-energy-lab-pipeline-real-backends"


def build_base_scenario(weather_family) -> BatteryLoadPVScenario:
    weather = weather_component_from_sampled_trace(weather_family.sampled_traces[0])
    grid = weather.time_grid
    return BatteryLoadPVScenario(
        scenario_id="example-pipeline-real-base",
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
            source="example-pipeline-real-placeholder",
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
            source="example-pipeline-real",
        ),
    )


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    capability_report = detect_spflow_backend_capabilities()

    weather_artifact = load_weather_artifact(
        REPO_ROOT / "tests/fixtures/weather/fitted_weather_artifact_v1.json",
        expected_timestep_hours=24.0,
    )
    weather_family = sample_weather_family(
        weather_artifact,
        request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=13),
        expected_timestep_hours=24.0,
    )

    demand_artifact = load_demand_artifact(
        REPO_ROOT / "tests/fixtures/demand/fitted_demand_artifact_v1.json",
        expected_timestep_hours=24.0,
    )
    demand_family = sample_demand_family(
        demand_artifact,
        request=DemandSamplingRequest(
            weather_family_reference=weather_family,
            num_steps=3,
            scenario_count=2,
            paired_family_seed=13,
        ),
    )

    cooling_service_configuration = CoolingServiceConfiguration(
        service_path="local-electric",
        local_electric_cooling=LocalElectricCoolingConfiguration(
            source_name="example-pipeline-real-local-cooling",
            electric_kw_per_rt=1.15,
            valid_for_feature_version="008-weather-demand-modeling",
            notes="Deterministic real-backend conversion factor.",
        ),
        source="example-pipeline-real",
    )

    family_result = evaluate_demand_family(
        DemandFamilyEvaluationRequest(
            base_scenario_reference=build_base_scenario(weather_family),
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=cooling_service_configuration,
            summary_output_fields=("site_electric_load_kw",),
            numeric_tolerance=DEFAULT_ABSOLUTE_TOLERANCE,
        )
    )

    dataset = export_planning_dataset(
        family_result_reference=family_result,
        weather_family_reference=weather_family,
        request=PlanningExportRequest(
            export_id="example-pipeline-real-dataset",
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
        ),
    )
    dataset_path = OUTPUT_ROOT / "planning_dataset.json"
    dataset.write_json(dataset_path)

    tpm_path = OUTPUT_ROOT / "tpm_artifact.json"
    fit_tpm_artifact(
        dataset_path,
        output_path=tpm_path,
        fit_config=TPMFitConfig(
            training_random_seed=13,
            spn_payload_format="spflow-model-sidecar",
            execution_mode="production",
            notes=("real-simulator-to-highs-example",),
        ),
    )
    tpm_artifact = load_tpm_artifact(tpm_path)
    runtime_payload = load_spflow_payload(tpm_artifact)
    if runtime_payload is None or runtime_payload.get("model") is None:
        raise RuntimeError("production fit did not persist a current-SPFlow model")
    compiled_mio = compile_spflow_model_to_mio(
        runtime_payload["model"],
        feature_schema=tpm_artifact.feature_specs,
    )
    compiler_policy = dict(compiled_mio["breakpoint_policy"])
    tpm_artifact = replace(
        tpm_artifact,
        approximation_metadata={
            **dict(tpm_artifact.approximation_metadata),
            "backend_compiler_version": compiled_mio["backend_compiler_version"],
            "compiler_schema_version": compiled_mio["schema_version"],
            "compiler_version": compiled_mio["compiler_version"],
            "compiler_status": "production-validated",
            "compiler_sum_encoding_mode": compiled_mio["sum_encoding_mode"],
            "leaf_encoding_mode": compiled_mio["leaf_encoding_mode"],
            "breakpoint_policy": {
                **compiler_policy,
                "piecewise_breakpoint_count": compiler_policy["breakpoint_count"],
            },
            "mio_epsilon": compiled_mio["mio_epsilon"],
        },
    )
    tpm_artifact.write_json(tpm_path)
    tpm_artifact = load_tpm_artifact(tpm_path)

    query_result = query_tpm_artifact(
        tpm_artifact,
        TPMQueryRequest(
            decision_assignments={
                "battery_capacity_kwh": 8.0,
                "design_name": "baseline-a",
            },
            marginalized_features=("solar_capacity_kw",),
            output_mode="conditional_probability",
            target_name="shortfall",
        ),
    )

    assembled_problem = assemble_planning_problem(
        PlanningProblemDefinition(
            problem_id="example-pipeline-real-problem",
            tpm_artifact_reference=str(tpm_path),
            decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
            decision_feature_types={
                "battery_capacity_kwh": "continuous",
                "solar_capacity_kw": "continuous",
            },
            shortfall_threshold=0.05,
            chance_limit_epsilon=0.3,
            risk_evaluation_mode="spn_mip",
            cost_terms={
                "battery_capacity_kwh": 1200.0,
                "solar_capacity_kw": 950.0,
            },
        ),
        tpm_artifact,
    )
    solve_summary = solve_planning_problem(assembled_problem)

    summary = {
        "generated_by": str(Path(__file__).relative_to(REPO_ROOT)),
        "output_dir": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
        "dataset_path": str(dataset_path.relative_to(REPO_ROOT)),
        "tpm_path": str(tpm_path.relative_to(REPO_ROOT)),
        "spflow_capabilities": capability_report,
        "used_real_spflow_backend": True,
        "spn_payload_format": tpm_artifact.spn_payload_format,
        "spn_payload_locator": tpm_artifact.spn_payload.get("locator"),
        "query_result": query_result,
        "compiler_version": compiled_mio["compiler_version"],
        "compiler_breakpoint_count": compiled_mio["breakpoint_policy"][
            "breakpoint_count"
        ],
        "mio_epsilon": compiled_mio["mio_epsilon"],
        "risk_evaluation_mode": assembled_problem.risk_evaluation_mode,
        "solve_status": solve_summary.status,
        "selected_design": dict(solve_summary.selected_design),
        "objective_value": solve_summary.objective_value,
        "estimated_event_probability": solve_summary.estimated_shortfall_risk,
        "estimated_shortfall_risk": solve_summary.estimated_shortfall_risk,
        "solver_backend_module": solve_summary.solver_metadata.get("backend_module"),
        "requested_solver_name": solve_summary.solver_metadata.get("requested_solver_name"),
        "solve_execution_mode": solve_summary.solver_metadata.get("solve_execution_mode"),
        "termination_condition": solve_summary.solver_metadata.get(
            "termination_condition"
        ),
        "solver_options": solve_summary.solver_metadata.get("solver_options"),
        "pyomo_version": solve_summary.solver_metadata.get("pyomo_version"),
        "highspy_version": solve_summary.solver_metadata.get("highspy_version"),
    }
    summary_path = OUTPUT_ROOT / "pipeline_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
