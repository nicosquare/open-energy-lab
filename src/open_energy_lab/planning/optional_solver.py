"""Lazy Pyomo dependency boundary for planning-model solve workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from types import SimpleNamespace
from typing import Any

from .problem import PlanningDecisionCandidate, PlanningProblemAssembly


class PlanningSolverDependencyUnavailableError(ImportError):
    """Raised when a planning solve workflow requires Pyomo but it is unavailable."""


@dataclass(frozen=True, slots=True)
class PlanningSolveConfig:
    """Minimal solver-configuration surface for optional planning solves."""

    solver_name: str = "pyomo"
    skip_if_unavailable: bool = False
    numeric_tolerance: float = 1e-9


@dataclass(frozen=True, slots=True)
class PlanningSolveSummary:
    """Deterministic summary for one optional planning solve attempt."""

    problem_id: str
    status: str
    selected_design: Mapping[str, object]
    objective_value: float | None
    estimated_shortfall_risk: float | None
    threshold: float
    chance_limit_epsilon: float
    feasibility_diagnostics: Mapping[str, object]
    solver_metadata: Mapping[str, object]


def require_pyomo_backend() -> Any:
    """Import Pyomo only when the planning solve path is invoked."""

    try:
        return import_module("pyomo")
    except ImportError as exc:  # pragma: no cover - depends on optional install state
        raise PlanningSolverDependencyUnavailableError(
            "Pyomo-backed planning workflows require the optional 'pyomo' "
            "dependency. This import boundary is intentionally lazy so "
            "open_energy_lab.planning stays import-light until solving is used."
        ) from exc


def solve_planning_problem(*args: object, **kwargs: object) -> object:
    """Solve one assembled planning problem through the optional Pyomo boundary."""

    if args:
        assembled_problem = args[0]
    else:
        assembled_problem = kwargs.get("assembled_problem")
    solve_config = kwargs.get("solve_config")
    pyomo_backend = kwargs.get("pyomo_backend")

    if not isinstance(assembled_problem, PlanningProblemAssembly):
        raise TypeError("assembled_problem must be a PlanningProblemAssembly")

    if solve_config is None:
        solve_config = PlanningSolveConfig()
    if not isinstance(solve_config, PlanningSolveConfig):
        raise TypeError("solve_config must be a PlanningSolveConfig")

    try:
        backend = pyomo_backend if pyomo_backend is not None else require_pyomo_backend()
    except PlanningSolverDependencyUnavailableError as exc:
        if not solve_config.skip_if_unavailable:
            raise
        return PlanningSolveSummary(
            problem_id=assembled_problem.problem_id,
            status="skipped",
            selected_design={},
            objective_value=None,
            estimated_shortfall_risk=None,
            threshold=assembled_problem.shortfall_threshold,
            chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
            feasibility_diagnostics={
                "reason": "optional pyomo backend unavailable",
                "error": str(exc),
            },
            solver_metadata={
                **dict(assembled_problem.solver_metadata),
                "requested_solver_name": solve_config.solver_name,
                "status": "skipped",
            },
        )

    feasible_candidates = tuple(
        candidate
        for candidate in assembled_problem.candidate_designs
        if candidate.estimated_shortfall_risk
        <= assembled_problem.chance_limit_epsilon + solve_config.numeric_tolerance
    )
    if not feasible_candidates:
        minimum_risk = min(
            (
                candidate.estimated_shortfall_risk
                for candidate in assembled_problem.candidate_designs
            ),
            default=None,
        )
        return PlanningSolveSummary(
            problem_id=assembled_problem.problem_id,
            status="infeasible",
            selected_design={},
            objective_value=None,
            estimated_shortfall_risk=minimum_risk,
            threshold=assembled_problem.shortfall_threshold,
            chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
            feasibility_diagnostics={
                "reason": "no candidate design satisfies the chance constraint",
                "candidate_count": len(assembled_problem.candidate_designs),
                "minimum_estimated_shortfall_risk": minimum_risk,
            },
            solver_metadata=_solver_metadata(
                assembled_problem,
                solve_config=solve_config,
                backend=backend,
                status="infeasible",
            ),
        )

    selected_candidate = min(feasible_candidates, key=_candidate_ordering)
    return PlanningSolveSummary(
        problem_id=assembled_problem.problem_id,
        status="optimal",
        selected_design=dict(selected_candidate.selected_design),
        objective_value=selected_candidate.objective_value,
        estimated_shortfall_risk=selected_candidate.estimated_shortfall_risk,
        threshold=assembled_problem.shortfall_threshold,
        chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
        feasibility_diagnostics={
            "matched_row_count": selected_candidate.matched_row_count,
            "candidate_count": len(assembled_problem.candidate_designs),
        },
        solver_metadata=_solver_metadata(
            assembled_problem,
            solve_config=solve_config,
            backend=backend,
            status="optimal",
        ),
    )


__all__ = [
    "PlanningSolveConfig",
    "PlanningSolveSummary",
    "PlanningSolverDependencyUnavailableError",
    "require_pyomo_backend",
    "solve_planning_problem",
]


def _candidate_ordering(candidate: PlanningDecisionCandidate) -> tuple[object, ...]:
    return (
        float(candidate.objective_value),
        float(candidate.estimated_shortfall_risk),
        tuple(sorted((str(key), repr(value)) for key, value in candidate.selected_design.items())),
    )


def _solver_metadata(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    backend: Any,
    status: str,
) -> dict[str, object]:
    backend_name = getattr(backend, "__name__", backend.__class__.__name__)
    backend_version = getattr(backend, "__version__", "unknown")
    if isinstance(backend, SimpleNamespace):
        backend_name = str(getattr(backend, "__name__", backend_name))
        backend_version = str(getattr(backend, "__version__", backend_version))

    return {
        **dict(assembled_problem.solver_metadata),
        "requested_solver_name": solve_config.solver_name,
        "backend_module": backend_name,
        "backend_version": backend_version,
        "status": status,
    }
