"""Scaffolding for chance-constrained planning problem definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


SUPPORTED_FIRST_RELEASE_DECISION_TYPES = ("battery", "solar")


@dataclass(frozen=True, slots=True)
class PlanningProblemDefinition:
    """Minimal placeholder for the planned problem-definition surface."""

    problem_id: str
    decision_features: tuple[str, ...] = field(default_factory=tuple)
    shortfall_threshold: float = 0.0
    chance_limit_epsilon: float = 0.0
    cost_terms: Mapping[str, float] = field(default_factory=dict)


def assemble_planning_problem(*args: object, **kwargs: object) -> object:
    """Reserve the planning problem assembly entry point."""

    raise NotImplementedError(
        "open_energy_lab.planning.problem.assemble_planning_problem is reserved "
        "by spec 009 and will be implemented in User Story 3 tasks."
    )


__all__ = [
    "PlanningProblemDefinition",
    "SUPPORTED_FIRST_RELEASE_DECISION_TYPES",
    "assemble_planning_problem",
]
