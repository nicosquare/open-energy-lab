"""Backend-free model handoff and indexing for robust FCR formulations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any

from .robust_fcr_bidding import (
    RobustFCRValidationError,
    _deep_freeze,
    _finite,
    _integer,
    _non_empty,
    _sha256,
)


SOURCE_EQUATION_VERSION = "robust-storage-bidding-non-intraday-milp-v1"
SOURCE_EQUATION_REFERENCES = MappingProxyType(
    {
        "variables": "baselines/robust_storage_bidding/code/02_model.jl:86-135",
        "power_headroom": (
            "baselines/robust_storage_bidding/code/02_model.jl:170-174"
        ),
        "robust_stored_energy": (
            "baselines/robust_storage_bidding/code/02_model.jl:183-188"
        ),
        "efficiency_epigraphs": (
            "baselines/robust_storage_bidding/code/02_model.jl:191-197"
        ),
        "upper_counterpart": (
            "baselines/robust_storage_bidding/code/02_model.jl:199-219"
        ),
        "exact_bilinear": (
            "baselines/robust_storage_bidding/code/02_model.jl:220-224"
        ),
        "restriction_tightening": (
            "baselines/robust_storage_bidding/code/02_model.jl:225-230"
        ),
        "objective_terminal": (
            "baselines/robust_storage_bidding/code/02_model.jl:252-263"
        ),
        "horizon_budget": (
            "baselines/robust_storage_bidding/code/02_model.jl:293-305"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class NormalizedRobustFCRIndexSets:
    """Zero-based deterministic indices used by private model assembly."""

    planning_indices: tuple[int, ...]
    energy_indices: tuple[int, ...]
    fcr_indices: tuple[int, ...]
    planning_to_energy: tuple[int, ...]
    planning_to_fcr: tuple[int, ...]
    triangular_pairs: tuple[tuple[int, int], ...]
    strict_triangular_pairs: tuple[tuple[int, int], ...]

    @property
    def planning_interval_count(self) -> int:
        return len(self.planning_indices)

    def semantic_counts(self) -> dict[str, int]:
        return {
            "planning_intervals": len(self.planning_indices),
            "energy_intervals": len(self.energy_indices),
            "fcr_intervals": len(self.fcr_indices),
            "triangular_pairs": len(self.triangular_pairs),
            "strict_triangular_pairs": len(self.strict_triangular_pairs),
        }


def build_normalized_index_sets(
    planning_interval_count: int,
    *,
    planning_intervals_per_energy_interval: int = 4,
    planning_intervals_per_fcr_block: int = 16,
) -> NormalizedRobustFCRIndexSets:
    count = _integer(
        planning_interval_count,
        field_name="planning_interval_count",
        minimum=1,
    )
    energy_stride = _integer(
        planning_intervals_per_energy_interval,
        field_name="planning_intervals_per_energy_interval",
        minimum=1,
    )
    fcr_stride = _integer(
        planning_intervals_per_fcr_block,
        field_name="planning_intervals_per_fcr_block",
        minimum=1,
    )
    planning = tuple(range(count))
    energy_count = math.ceil(count / energy_stride)
    fcr_count = math.ceil(count / fcr_stride)
    return NormalizedRobustFCRIndexSets(
        planning_indices=planning,
        energy_indices=tuple(range(energy_count)),
        fcr_indices=tuple(range(fcr_count)),
        planning_to_energy=tuple(index // energy_stride for index in planning),
        planning_to_fcr=tuple(index // fcr_stride for index in planning),
        triangular_pairs=tuple(
            (outer, inner)
            for outer in planning
            for inner in range(outer + 1)
        ),
        strict_triangular_pairs=tuple(
            (outer, inner) for outer in planning for inner in range(outer)
        ),
    )


def model_cardinality_basis(index_sets: NormalizedRobustFCRIndexSets) -> dict[str, int]:
    """Return stable semantic index counts before backend assembly."""

    return index_sets.semantic_counts()


@dataclass(frozen=True, slots=True)
class RobustFCRModelInput:
    """Immutable backend-neutral values handed to private model assembly."""

    problem_fingerprint: str
    planning_resolution_hours: float
    index_sets: NormalizedRobustFCRIndexSets
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "problem_fingerprint",
            _sha256(self.problem_fingerprint, field_name="problem_fingerprint"),
        )
        resolution = _finite(
            self.planning_resolution_hours,
            field_name="planning_resolution_hours",
        )
        if resolution <= 0.0:
            raise RobustFCRValidationError(
                "planning_resolution_hours must be greater than zero"
            )
        object.__setattr__(self, "planning_resolution_hours", resolution)
        if not isinstance(self.index_sets, NormalizedRobustFCRIndexSets):
            raise RobustFCRValidationError(
                "index_sets must be NormalizedRobustFCRIndexSets"
            )
        object.__setattr__(
            self,
            "payload",
            _deep_freeze(self.payload, field_name="model_input.payload"),
        )


@dataclass(frozen=True, slots=True)
class RobustFCRModelHandoff:
    """Semantic identity and counts associated with one assembled model."""

    formulation_kind: str
    equation_version: str
    model_input: RobustFCRModelInput
    cardinality: Mapping[str, int]

    def __post_init__(self) -> None:
        if self.formulation_kind not in {"restriction", "relaxation", "exact"}:
            raise RobustFCRValidationError(
                "formulation_kind must be restriction, relaxation, or exact"
            )
        object.__setattr__(
            self,
            "equation_version",
            _non_empty(self.equation_version, field_name="equation_version"),
        )
        normalized: dict[str, int] = {}
        for name, value in self.cardinality.items():
            normalized[_non_empty(name, field_name="cardinality key")] = _integer(
                value,
                field_name=f"cardinality.{name}",
                minimum=0,
            )
        object.__setattr__(
            self,
            "cardinality",
            MappingProxyType(dict(sorted(normalized.items()))),
        )


@dataclass(frozen=True, slots=True)
class AssembledRobustFCRModel:
    """Private solver handoff retaining opaque backend handles."""

    model: Any
    handoff: RobustFCRModelHandoff
    variable_handles: Mapping[str, Any]
    constraint_handles: Mapping[str, Any]


__all__ = [
    "AssembledRobustFCRModel",
    "NormalizedRobustFCRIndexSets",
    "RobustFCRModelHandoff",
    "RobustFCRModelInput",
    "SOURCE_EQUATION_REFERENCES",
    "SOURCE_EQUATION_VERSION",
    "build_normalized_index_sets",
    "model_cardinality_basis",
]
