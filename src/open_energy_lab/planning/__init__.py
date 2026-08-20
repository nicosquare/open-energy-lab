"""Public planning package surface for TPM-backed planning datasets.

The stable planning root stays import-light by resolving documented exports
from focused submodules only when callers access them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .dataset import PlanningDatasetArtifact, load_planning_dataset
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
    from .workflow import (
        CompiledPlanningStudyTPM,
        PlanningStudyRunResult,
        VerifiedPlanningStudySolution,
        compile_planning_study_tpm,
        fit_planning_study_tpm,
        run_planning_study,
        solve_planning_study,
    )

_EXPORT_MAP = {
    "PlanningDatasetArtifact": (".dataset", "PlanningDatasetArtifact"),
    "load_planning_dataset": (".dataset", "load_planning_dataset"),
    "PlanningProblemAssembly": (".problem", "PlanningProblemAssembly"),
    "PlanningProblemDefinition": (".problem", "PlanningProblemDefinition"),
    "assemble_planning_problem": (".problem", "assemble_planning_problem"),
    "PlanningSolveConfig": (".optional_solver", "PlanningSolveConfig"),
    "PlanningSolveSummary": (".optional_solver", "PlanningSolveSummary"),
    "PlanningSolverDependencyUnavailableError": (
        ".optional_solver",
        "PlanningSolverDependencyUnavailableError",
    ),
    "PlanningSolverUnavailableError": (
        ".optional_solver",
        "PlanningSolverUnavailableError",
    ),
    "solve_planning_problem": (".optional_solver", "solve_planning_problem"),
    "AdequacyEventDefinition": (".study", "AdequacyEventDefinition"),
    "BatteryDesignOption": (".study", "BatteryDesignOption"),
    "ControllerStudyConfig": (".study", "ControllerStudyConfig"),
    "GridAvailabilityPolicy": (".study", "GridAvailabilityPolicy"),
    "PlanningStudyRequest": (".study", "PlanningStudyRequest"),
    "SolarDesignOption": (".study", "SolarDesignOption"),
    "PlanningStudyDatasetManifest": (
        ".study_dataset",
        "PlanningStudyDatasetManifest",
    ),
    "iter_study_rows": (".study_dataset", "iter_study_rows"),
    "load_study_dataset_manifest": (
        ".study_dataset",
        "load_study_dataset_manifest",
    ),
    "CalibrationAssessment": (".study_validation", "CalibrationAssessment"),
    "RecommendationAssessment": (
        ".study_validation",
        "RecommendationAssessment",
    ),
    "SPNCandidateScore": (".study_validation", "SPNCandidateScore"),
    "assess_calibration": (".study_validation", "assess_calibration"),
    "assess_recommendation": (".study_validation", "assess_recommendation"),
    "brier_score_by_configuration": (
        ".study_validation",
        "brier_score_by_configuration",
    ),
    "select_spn_candidate": (".study_validation", "select_spn_candidate"),
    "CompiledPlanningStudyTPM": (".workflow", "CompiledPlanningStudyTPM"),
    "PlanningStudyRunResult": (".workflow", "PlanningStudyRunResult"),
    "VerifiedPlanningStudySolution": (
        ".workflow",
        "VerifiedPlanningStudySolution",
    ),
    "compile_planning_study_tpm": (".workflow", "compile_planning_study_tpm"),
    "fit_planning_study_tpm": (".workflow", "fit_planning_study_tpm"),
    "run_planning_study": (".workflow", "run_planning_study"),
    "solve_planning_study": (".workflow", "solve_planning_study"),
}

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
    "CompiledPlanningStudyTPM",
    "PlanningStudyRunResult",
    "VerifiedPlanningStudySolution",
    "compile_planning_study_tpm",
    "fit_planning_study_tpm",
    "run_planning_study",
    "solve_planning_study",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the reserved planning package exports."""

    try:
        module_name, attribute_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
