"""Scaffolding for solver-facing piecewise planning assembly."""

from __future__ import annotations


def build_piecewise_planning_terms(*args: object, **kwargs: object) -> object:
    """Reserve the solver-facing piecewise assembly entry point."""

    raise NotImplementedError(
        "open_energy_lab.planning.piecewise.build_piecewise_planning_terms is "
        "reserved by spec 009 and will be implemented in User Story 3 tasks."
    )


__all__ = ["build_piecewise_planning_terms"]
