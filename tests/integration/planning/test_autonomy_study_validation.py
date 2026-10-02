from __future__ import annotations

from dataclasses import replace

from open_energy_lab.demand import load_demand_artifact
from open_energy_lab.planning.study import AdequacyEventDefinition
from open_energy_lab.planning.study_dataset import iter_study_rows
from open_energy_lab.planning.study_validation import (
    SPNCandidateScore,
    assess_calibration,
    assess_recommendation,
    brier_score_by_configuration,
    select_spn_candidate,
)
from open_energy_lab.planning.workflow import (
    compile_planning_study_tpm,
    fit_planning_study_tpm,
    solve_planning_study,
)
from open_energy_lab.simulator.planning_study import generate_planning_study_dataset
from tpm import TPMFitConfig, TPMQueryRequest, query_tpm_artifact
from open_energy_lab.weather import load_weather_artifact
from tests.integration.demand.fixture_utils import FITTED_DEMAND_ARTIFACT_FIXTURE_PATH
from tests.integration.planning.test_study_simulation import _request
from tests.integration.weather.fixture_utils import FITTED_WEATHER_ARTIFACT_FIXTURE_PATH
from tests.unit.simulator.test_stochastic_demand import (
    _base_scenario,
    _local_cooling_service_configuration,
    _sample_weather_family_fixture,
)


def test_reduced_split_candidate_solve_and_blocking_pipeline(tmp_path) -> None:
    weather = load_weather_artifact(
        FITTED_WEATHER_ARTIFACT_FIXTURE_PATH,
        expected_timestep_hours=24.0,
    )
    demand = load_demand_artifact(
        FITTED_DEMAND_ARTIFACT_FIXTURE_PATH,
        expected_timestep_hours=24.0,
    )
    base_request = replace(
        _request(worker_count=1, shard_format="jsonl"),
        adequacy_event=AdequacyEventDefinition("shortfall_ratio", 1.0),
    )
    manifests = {}
    for split, seed, sample_count in (
        ("train", 13, 40),
        ("validation", 37, 4),
        ("test", 101, 4),
    ):
        request = replace(
            base_request,
            study_id=f"reduced-autonomy-{split}",
            random_seed=seed,
            samples_per_configuration=sample_count,
            batch_size=sample_count,
        )
        manifests[split] = generate_planning_study_dataset(
            request,
            weather_artifact=weather,
            demand_artifact=demand,
            base_scenario_reference=_base_scenario(_sample_weather_family_fixture()),
            cooling_service_configuration=_local_cooling_service_configuration(),
            output_dir=tmp_path / split,
            expected_timestep_hours=24.0,
        )

    assert [manifests[name].row_count for name in ("train", "validation", "test")] == [
        160,
        16,
        16,
    ]
    assert len({manifest.request_fingerprint for manifest in manifests.values()}) == 3

    validation_rows = tuple(iter_study_rows(manifests["validation"]))
    candidates = []
    artifacts = {}
    for name, kwargs in (
        ("default", {}),
        ("coarse", {"min_instances_slice": 100}),
    ):
        artifact_path = tmp_path / "candidates" / name / "artifact.json"
        artifact_path.parent.mkdir(parents=True)
        artifact = fit_planning_study_tpm(
            manifests["train"],
            output_path=artifact_path,
            fit_config=TPMFitConfig(
                training_random_seed=13,
                learn_mspn_kwargs=kwargs,
                spn_payload_format="spflow-model-sidecar",
            ),
        )
        compiled = compile_planning_study_tpm(artifact, output_path=artifact_path)
        probabilities = _configuration_probabilities(compiled.artifact, validation_rows)
        brier = brier_score_by_configuration(
            validation_rows,
            probabilities=probabilities,
            event_target_name="shortfall_ratio_exceeds_threshold",
        )
        score = SPNCandidateScore(
            name,
            brier,
            int(
                artifact.fit_configuration["fit_summary"]["structure"][
                    "module_count"
                ]
            ),
            True,
        )
        candidates.append(score)
        artifacts[name] = compiled.artifact

    selected = select_spn_candidate(candidates)
    selected_artifact = artifacts[selected.candidate_name]
    solution = solve_planning_study(
        selected_artifact,
        manifests["train"],
        chance_limit_epsilon=0.05,
    )
    assert solution.status == "optimal"
    assert solution.probability_discrepancy is not None
    assert solution.probability_discrepancy <= 1e-6

    selected_configuration_id = (
        f"{solution.solve_summary.selected_design['battery_option_id']}__"
        f"{solution.solve_summary.selected_design['solar_option_id']}"
    )
    test_rows = tuple(iter_study_rows(manifests["test"]))
    calibration = assess_calibration(
        test_rows,
        probabilities=_configuration_probabilities(selected_artifact, test_rows),
        event_target_name="shortfall_ratio_exceeds_threshold",
        selected_configuration_id=selected_configuration_id,
    )
    recommendation = assess_recommendation(
        calibration=calibration,
        solve_status=solution.status,
        native_mio_discrepancy=float(solution.probability_discrepancy),
        chance_limit=0.05,
    )

    assert not calibration.both_labels_observed
    assert recommendation.status == "exploratory"
    assert recommendation.blocking_reasons


def _configuration_probabilities(artifact, rows):
    assignments = {
        (
            str(row["configuration_id"]),
            str(row["battery_option_id"]),
            str(row["solar_option_id"]),
        )
        for row in rows
    }
    return {
        configuration_id: float(
            query_tpm_artifact(
                artifact,
                TPMQueryRequest(
                    decision_assignments={
                        "battery_option_id": battery_option_id,
                        "solar_option_id": solar_option_id,
                    },
                    output_mode="conditional_probability",
                    target_threshold=1.0,
                    execution_mode="production",
                ),
            )["value"]
        )
        for configuration_id, battery_option_id, solar_option_id in assignments
    }
