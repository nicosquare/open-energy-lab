"""Package-surface maturity checks for the planned planning package."""

from __future__ import annotations

import importlib


PLANNING_PACKAGE = "open_energy_lab.planning"
EXPECTED_ROOT_EXPORTS = [
    "PlanningDatasetArtifact",
    "load_planning_dataset",
    "PlanningProblemAssembly",
    "PlanningProblemDefinition",
    "assemble_planning_problem",
    "PlanningSolveConfig",
    "PlanningSolveSummary",
    "PlanningSolverDependencyUnavailableError",
    "PlanningSolverUnavailableError",
    "solve_planning_problem",
    "AdequacyEventDefinition",
    "BatteryDesignOption",
    "ControllerStudyConfig",
    "GridAvailabilityPolicy",
    "PlanningStudyRequest",
    "SolarDesignOption",
    "PlanningStudyDatasetManifest",
    "iter_study_rows",
    "load_study_dataset_manifest",
    "CalibrationAssessment",
    "RecommendationAssessment",
    "SPNCandidateScore",
    "assess_calibration",
    "assess_recommendation",
    "brier_score_by_configuration",
    "select_spn_candidate",
    "fit_tpm_artifact",
    "fit_tpm_artifact_from_study_manifest",
    "CompiledPlanningStudyTPM",
    "PlanningStudyRunResult",
    "VerifiedPlanningStudySolution",
    "compile_planning_study_tpm",
    "fit_planning_study_tpm",
    "run_planning_study",
    "solve_planning_study",
]


def test_planning_root_surface_stays_explicit_about_surface_maturity() -> None:
    module = importlib.import_module(PLANNING_PACKAGE)

    assert module.__doc__ is not None
    assert "Public planning package surface" in module.__doc__
    assert module.__all__ == EXPECTED_ROOT_EXPORTS
    for name in module.__all__:
        export = getattr(module, name)
        assert export.__module__.startswith("open_energy_lab.planning.")


def test_planning_root_reserves_only_documented_public_exports() -> None:
    module = importlib.import_module(PLANNING_PACKAGE)

    assert all("." not in export_name for export_name in module.__all__)
    assert all(not export_name.startswith("_") for export_name in module.__all__)
