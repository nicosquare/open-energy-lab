"""Lazy Pyomo dependency boundary for planning-model solve workflows."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any


class PlanningSolverDependencyUnavailableError(ImportError):
    """Raised when a planning solve workflow requires Pyomo but it is unavailable."""


@dataclass(frozen=True, slots=True)
class PlanningSolveConfig:
    """Minimal placeholder for the planned solver-configuration surface."""

    solver_name: str = "reserved"


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
    """Reserve the optional planning solve entry point."""

    raise NotImplementedError(
        "open_energy_lab.planning.optional_solver.solve_planning_problem is "
        "reserved by spec 009 and will be implemented in User Story 3 tasks."
    )


__all__ = [
    "PlanningSolveConfig",
    "PlanningSolverDependencyUnavailableError",
    "require_pyomo_backend",
    "solve_planning_problem",
]
