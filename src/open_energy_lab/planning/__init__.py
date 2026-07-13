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
