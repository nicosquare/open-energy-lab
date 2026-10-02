from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest

from open_energy_lab.planning.optional_solver import PlanningSolveConfig, PlanningSolveSummary
from open_energy_lab.planning.study_dataset import PlanningStudyDatasetWriter
from open_energy_lab.planning.workflow import solve_planning_study
from open_energy_lab.planning import fit_tpm_artifact_from_study_manifest
from open_energy_lab.tpm.fit import TPMFitMemoryError


def _manifest(tmp_path):
    columns = (
        "battery_option_id",
        "solar_option_id",
        "shortfall_ratio",
        "shortfall_ratio_exceeds_threshold",
    )
    writer = PlanningStudyDatasetWriter(
        output_dir=tmp_path,
        dataset_id="compact-fit-unit",
        request_fingerprint="request-sha",
        column_order=columns,
        shard_format="jsonl",
    )
    writer.write_shard(
        0,
        (
            dict(zip(columns, ("battery-a", "solar-a", 0.1, 1), strict=True)),
            dict(zip(columns, ("battery-b", "solar-a", 0.0, 0), strict=True)),
        ),
    )
    return writer.finalize(
        metadata={
            "study_request": {
                "random_seed": 13,
                "adequacy_event": {"kind": "shortfall_ratio", "threshold": 0.05},
            },
            "active_event_target": "shortfall_ratio_exceeds_threshold",
            "default_fit_feature_names": list(columns),
            "equipment_catalog": [
                {
                    "battery": {"option_id": "battery-a", "installed_cost": 5.0},
                    "solar": {"option_id": "solar-a", "installed_cost": 3.0},
                },
                {
                    "battery": {"option_id": "battery-b", "installed_cost": 7.0},
                    "solar": {"option_id": "solar-a", "installed_cost": 3.0},
                },
            ],
        }
    )


def test_compact_fit_fails_before_backend_when_tensor_budget_is_exceeded(tmp_path) -> None:
    manifest = _manifest(tmp_path / "dataset")

    with pytest.raises(TPMFitMemoryError, match="max_tensor_bytes=1"):
        fit_tpm_artifact_from_study_manifest(
            manifest,
            output_path=tmp_path / "artifact.json",
            max_tensor_bytes=1,
        )


def test_postsolve_verification_rejects_encoded_native_probability_mismatch(
    tmp_path, monkeypatch
) -> None:
    manifest = _manifest(tmp_path / "dataset")
    summary = PlanningSolveSummary(
        problem_id="study-unit",
        status="optimal",
        selected_design={
            "battery_option_id": "battery-a",
            "solar_option_id": "solar-a",
        },
        objective_value=8.0,
        estimated_shortfall_risk=0.1,
        threshold=0.05,
        chance_limit_epsilon=0.2,
        feasibility_diagnostics={},
        solver_metadata={},
    )
    workflow = import_module("open_energy_lab.planning.workflow")
    captured_definition = None

    def _capture_definition(definition, artifact):
        nonlocal captured_definition
        captured_definition = definition
        return object()

    monkeypatch.setattr(workflow, "assemble_planning_problem", _capture_definition)
    monkeypatch.setattr(workflow, "solve_planning_problem", lambda *args, **kwargs: summary)
    monkeypatch.setattr(
        workflow,
        "query_tpm_artifact",
        lambda *args, **kwargs: {"value": 0.3, "source": "spflow_backend"},
    )

    result = solve_planning_study(
        SimpleNamespace(
            target_definition={"threshold_default": 0.05},
        ),
        manifest,
        chance_limit_epsilon=0.2,
        solve_config=PlanningSolveConfig(time_limit_seconds=120.0),
    )

    assert captured_definition.solver_configuration["time_limit_seconds"] == 120.0
    assert result.status == "validation_failed"
    assert result.probability_discrepancy == pytest.approx(0.2)
    assert result.diagnostics["encoded_native_mismatch"] is True
    assert result.diagnostics["native_limit_violation"] is True
