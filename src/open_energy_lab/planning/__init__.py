"""Public planning package surface for TPM-backed planning datasets.

The stable planning root stays import-light by resolving documented exports
from focused submodules only when callers access them.
"""

from __future__ import annotations

from .dataset import (
    PlanningDatasetArtifact,
    load_planning_dataset,
)
from .optional_solver import (
    PlanningSolveConfig,
    PlanningSolveSummary,
    PlanningSolverDependencyUnavailableError,
    PlanningSolverUnavailableError,
    solve_planning_problem,
)
from .problem import (
    PlanningProblemAssembly,
    PlanningProblemDefinition,
    assemble_planning_problem,
)
from .study import (
    AdequacyEventDefinition,
    BatteryDesignOption,
    ControllerStudyConfig,
    GridAvailabilityPolicy,
    PlanningStudyRequest,
    SolarDesignOption,
)
from .study_dataset import (
    PlanningStudyDatasetManifest,
    iter_study_rows,
    load_study_dataset_manifest,
)
from .study_validation import (
    CalibrationAssessment,
    RecommendationAssessment,
    SPNCandidateScore,
    assess_calibration,
    assess_recommendation,
    brier_score_by_configuration,
    select_spn_candidate,
)
from .tpm_fit import fit_tpm_artifact, fit_tpm_artifact_from_study_manifest
from .workflow import (
    CompiledPlanningStudyTPM,
    PlanningStudyRunResult,
    VerifiedPlanningStudySolution,
    compile_planning_study_tpm,
    fit_planning_study_tpm,
    run_planning_study,
    solve_planning_study,
)

__all__ = [
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
