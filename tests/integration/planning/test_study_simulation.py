from __future__ import annotations

from dataclasses import replace

from open_energy_lab.demand import load_demand_artifact
from open_energy_lab.planning.study import (
    AdequacyEventDefinition,
    BatteryDesignOption,
    GridAvailabilityPolicy,
    PlanningStudyRequest,
    SolarDesignOption,
)
from open_energy_lab.planning.study_dataset import iter_study_rows
from open_energy_lab.planning.workflow import (
    compile_planning_study_tpm,
    fit_planning_study_tpm,
    solve_planning_study,
)
from open_energy_lab.simulator.planning_study import generate_planning_study_dataset
from open_energy_lab.simulator.planning_study import (
    PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION,
)
from open_energy_lab.weather import load_weather_artifact
from tests.integration.demand.fixture_utils import FITTED_DEMAND_ARTIFACT_FIXTURE_PATH
from tests.integration.weather.fixture_utils import FITTED_WEATHER_ARTIFACT_FIXTURE_PATH
from tests.unit.simulator.test_stochastic_demand import (
    _base_scenario,
    _local_cooling_service_configuration,
    _sample_weather_family_fixture,
)


def _request(
    *, worker_count: int, shard_format: str, local_start_step: int = 0
) -> PlanningStudyRequest:
    return PlanningStudyRequest(
        study_id="simulation-integration",
        battery_options=(
            BatteryDesignOption("battery-5", 5.0, 2.0, 2.0, 5000.0),
            BatteryDesignOption("battery-10", 10.0, 4.0, 4.0, 9000.0),
        ),
        solar_options=(
            SolarDesignOption("solar-3", 3.0, 3000.0),
            SolarDesignOption("solar-6", 6.0, 5500.0),
        ),
        samples_per_configuration=2,
        horizon_steps=3,
        batch_size=1,
        worker_count=worker_count,
        random_seed=13,
        shard_format=shard_format,
        local_start_step=local_start_step,
        adequacy_event=AdequacyEventDefinition("shortfall_ratio", 0.05),
        grid_availability=GridAvailabilityPolicy(mode="islanded"),
    )


def _run(
    tmp_path, *, worker_count: int, shard_format: str, local_start_step: int = 0
):
    weather = load_weather_artifact(
        FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
        expected_timestep_hours=24.0,
    )
    demand = load_demand_artifact(
        FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
        expected_timestep_hours=24.0,
    )
    base = _base_scenario(_sample_weather_family_fixture())
    return generate_planning_study_dataset(
        _request(
            worker_count=worker_count,
            shard_format=shard_format,
            local_start_step=local_start_step,
        ),
        weather_artifact=weather,
        demand_artifact=demand,
        base_scenario_reference=base,
        cooling_service_configuration=_local_cooling_service_configuration(),
        output_dir=tmp_path,
        expected_timestep_hours=24.0,
    )


def test_study_sweep_derives_physical_metadata_and_reuses_samples(tmp_path) -> None:
    manifest = _run(tmp_path / "study", worker_count=1, shard_format="jsonl")
    rows = tuple(iter_study_rows(manifest))

    assert manifest.row_count == 8
    assert manifest.metadata["simulation_semantics_version"] == (
        PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION
    )
    assert [row["configuration_id"] for row in rows] == [
        "battery-5__solar-3",
        "battery-5__solar-3",
        "battery-5__solar-6",
        "battery-5__solar-6",
        "battery-10__solar-3",
        "battery-10__solar-3",
        "battery-10__solar-6",
        "battery-10__solar-6",
    ]
    sample_zero = [row for row in rows if row["sample_id"] == 0]
    assert len({row["ghi_0"] for row in sample_zero}) == 1
    assert sample_zero[0]["battery_capacity_kwh"] == 5.0
    assert sample_zero[-1]["battery_capacity_kwh"] == 10.0
    assert sample_zero[0]["solar_capacity_kw"] == 3.0
    assert sample_zero[-1]["solar_capacity_kw"] == 6.0
    assert {row["controller_name"] for row in sample_zero} == {
        "PVSelfConsumptionController"
    }
    assert sample_zero[0]["pv_generation_0"] < sample_zero[-1]["pv_generation_0"]
    assert isinstance(sample_zero[0]["grid_available_0"], bool)
    for row in sample_zero:
        assert 0.0 <= row["battery_soc_0"] <= 1.0
        assert "controller_request_0" in row
        assert "battery_power_0" in row
        assert 0.0 <= row["shortfall_ratio"] <= 1.0


def test_larger_battery_does_not_increase_unmet_energy_for_shared_samples(tmp_path) -> None:
    manifest = _run(tmp_path / "study", worker_count=1, shard_format="jsonl")
    rows = tuple(iter_study_rows(manifest))
    by_case = {
        (str(row["battery_option_id"]), str(row["solar_option_id"]), int(row["sample_id"])): row
        for row in rows
    }

    for solar_option_id in ("solar-3", "solar-6"):
        for sample_id in (0, 1):
            small = by_case[("battery-5", solar_option_id, sample_id)]
            large = by_case[("battery-10", solar_option_id, sample_id)]
            assert float(large["unmet_energy_kwh"]) <= float(
                small["unmet_energy_kwh"]
            ) + 1e-9


def test_worker_count_and_storage_format_preserve_semantic_rows(tmp_path) -> None:
    sequential = _run(tmp_path / "jsonl", worker_count=1, shard_format="jsonl")
    parallel = _run(tmp_path / "parquet", worker_count=2, shard_format="parquet")

    assert tuple(iter_study_rows(sequential)) == tuple(iter_study_rows(parallel))
    assert sequential.semantic_sha256 == parallel.semantic_sha256


def test_real_discrete_study_fits_compiles_solves_and_verifies(tmp_path) -> None:
    manifest = _run(tmp_path / "study", worker_count=1, shard_format="parquet")
    artifact_path = tmp_path / "tpm" / "artifact.json"
    artifact_path.parent.mkdir(parents=True)

    artifact = fit_planning_study_tpm(manifest, output_path=artifact_path)
    compiled = compile_planning_study_tpm(artifact, output_path=artifact_path)
    result = solve_planning_study(
        compiled.artifact,
        manifest,
        chance_limit_epsilon=1.0,
    )

    assert result.status == "optimal"
    assert result.solve_summary.selected_design == {
        "battery_option_id": "battery-5",
        "solar_option_id": "solar-3",
    }
    assert result.solve_summary.objective_value == 8000.0
    assert result.probability_discrepancy <= 1e-6
    assert (
        result.solve_summary.solver_metadata["risk_encoding_strategy"]
        == "exact-categorical-lookup"
    )


def test_study_manifest_preserves_local_start_step(tmp_path) -> None:
    # The daily fixture has one interval per local day, so zero is its only
    # valid local offset; this integration assertion covers propagation while
    # hourly offset behavior is exercised by focused weather/demand tests.
    manifest = _run(
        tmp_path / "study",
        worker_count=1,
        shard_format="jsonl",
        local_start_step=0,
    )

    assert manifest.metadata["study_request"]["local_start_step"] == 0
