"""Offline 2x2 discrete solar-storage planning study."""

from __future__ import annotations

import json
from pathlib import Path

from open_energy_lab.demand import load_demand_artifact
from open_energy_lab.planning import (
    AdequacyEventDefinition,
    BatteryDesignOption,
    GridAvailabilityPolicy,
    PlanningStudyRequest,
    SolarDesignOption,
    run_planning_study,
)
from open_energy_lab.simulator.demand import (
    CoolingServiceConfiguration,
    LocalElectricCoolingConfiguration,
)
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    load_weather_artifact,
    sample_weather_family,
)

from run_real_backend_pipeline import build_base_scenario


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "tmp/open-energy-lab-discrete-study"


def main() -> None:
    weather = load_weather_artifact(
        REPO_ROOT / "tests/fixtures/weather/fitted_weather_artifact_v1.json",
        expected_timestep_hours=24.0,
    )
    demand = load_demand_artifact(
        REPO_ROOT / "tests/fixtures/demand/fitted_demand_artifact_v1.json",
        expected_timestep_hours=24.0,
    )
    base_weather = sample_weather_family(
        weather,
        request=WeatherSamplingRequest(num_steps=3, scenario_count=1, family_seed=13),
        expected_timestep_hours=24.0,
    )
    request = PlanningStudyRequest(
        study_id="offline-2x2-study",
        battery_options=(
            BatteryDesignOption("battery-5", 5.0, 2.0, 2.0, 5000.0),
            BatteryDesignOption("battery-10", 10.0, 4.0, 4.0, 9000.0),
        ),
        solar_options=(
            SolarDesignOption("solar-3", 3.0, 3000.0),
            SolarDesignOption("solar-6", 6.0, 5500.0),
        ),
        samples_per_configuration=8,
        horizon_steps=3,
        batch_size=4,
        worker_count=1,
        adequacy_event=AdequacyEventDefinition("shortfall_ratio", 0.05),
        grid_availability=GridAvailabilityPolicy(mode="islanded"),
    )
    result = run_planning_study(
        request,
        weather_artifact=weather,
        demand_artifact=demand,
        base_scenario_reference=build_base_scenario(base_weather),
        cooling_service_configuration=CoolingServiceConfiguration(
            service_path="local-electric",
            local_electric_cooling=LocalElectricCoolingConfiguration(
                source_name="discrete-study-example",
                electric_kw_per_rt=1.15,
                valid_for_feature_version="008-weather-demand-modeling",
                notes="Offline deterministic example conversion.",
            ),
            source="discrete-study-example",
        ),
        output_dir=OUTPUT_ROOT,
        chance_limit_epsilon=1.0,
        expected_timestep_hours=24.0,
    )
    summary = {
        "status": result.solution.status,
        "row_count": result.dataset_manifest.row_count,
        "selected_design": dict(result.solution.solve_summary.selected_design),
        "objective_value": result.solution.solve_summary.objective_value,
        "encoded_risk": result.solution.solve_summary.estimated_shortfall_risk,
        "native_risk": result.solution.native_event_probability,
        "probability_discrepancy": result.solution.probability_discrepancy,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
