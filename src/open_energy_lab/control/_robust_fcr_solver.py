"""Lazy solver loading and backend-neutral raw results for Feature 013."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import import_module
from types import MappingProxyType
from typing import Any

from .robust_fcr_bidding import (
    RobustFCRSolverDependencyUnavailableError,
    RobustFCRSolverUnavailableError,
    _deep_freeze,
    _finite,
    _non_empty,
)


REQUIRED_PYOMO_VERSION = "6.10.1"
REQUIRED_HIGHSPY_VERSION = "1.15.1"


@dataclass(frozen=True, slots=True)
class SolverBackendModules:
    """Explicitly loaded backend modules and their validated versions."""

    pyomo_package: Any
    pyomo_environ: Any
    highspy: Any
    pyomo_version: str
    highspy_version: str


@dataclass(frozen=True, slots=True)
class RawRobustFCRSolveResult:
    """Backend-neutral evidence before public auditing and plan policy."""

    solve_status: str
    termination_status: str
    has_incumbent: bool
    objective_value_eur: float | None = None
    best_upper_bound_eur: float | None = None
    witness: Mapping[str, object] | None = None
    solver_name: str = "unknown"
    solver_version: str | None = None
    pyomo_version: str | None = None
    highspy_version: str | None = None
    configured_options: Mapping[str, object] = field(default_factory=dict)
    model_cardinality: Mapping[str, int] = field(default_factory=dict)
    diagnostics: tuple[Mapping[str, object], ...] = ()
    runtime_seconds: float | None = None
    runtime_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "solve_status",
            _non_empty(self.solve_status, field_name="solve_status"),
        )
        object.__setattr__(
            self,
            "termination_status",
            _non_empty(self.termination_status, field_name="termination_status"),
        )
        if self.objective_value_eur is not None:
            object.__setattr__(
                self,
                "objective_value_eur",
                _finite(self.objective_value_eur, field_name="objective_value_eur"),
            )
        if self.best_upper_bound_eur is not None:
            object.__setattr__(
                self,
                "best_upper_bound_eur",
                _finite(
                    self.best_upper_bound_eur,
                    field_name="best_upper_bound_eur",
                ),
            )
        if self.runtime_seconds is not None:
            runtime = _finite(self.runtime_seconds, field_name="runtime_seconds")
            if runtime < 0.0:
                raise ValueError("runtime_seconds must be non-negative")
            object.__setattr__(self, "runtime_seconds", runtime)
        if self.witness is not None:
            object.__setattr__(
                self,
                "witness",
                _deep_freeze(self.witness, field_name="raw_solve.witness"),
            )
        object.__setattr__(
            self,
            "configured_options",
            _deep_freeze(
                self.configured_options,
                field_name="raw_solve.configured_options",
            ),
        )
        object.__setattr__(
            self,
            "model_cardinality",
            MappingProxyType(dict(sorted(self.model_cardinality.items()))),
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple(
                _deep_freeze(value, field_name="raw_solve.diagnostic")
                for value in self.diagnostics
            ),
        )
        object.__setattr__(
            self,
            "runtime_metadata",
            _deep_freeze(
                self.runtime_metadata,
                field_name="raw_solve.runtime_metadata",
            ),
        )


def _installed_highspy_version(highspy: Any) -> str:
    direct = getattr(highspy, "__version__", None)
    if isinstance(direct, str) and direct:
        return direct
    try:
        value = highspy.Highs().version()
    except Exception as exc:  # pragma: no cover - backend-specific defensive path
        raise RobustFCRSolverDependencyUnavailableError(
            "required highspy is installed but its version could not be determined"
        ) from exc
    return str(value)


def require_highs_backend() -> SolverBackendModules:
    """Load and validate the required Pyomo/HiGHS stack on explicit request."""

    try:
        pyomo_package = import_module("pyomo")
        pyomo_environ = import_module("pyomo.environ")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RobustFCRSolverDependencyUnavailableError(
            "Feature 013 requires Pyomo 6.10.1; run `uv sync --dev` and retry"
        ) from exc
    pyomo_version = str(getattr(pyomo_package, "__version__", "unknown"))
    if pyomo_version != REQUIRED_PYOMO_VERSION:
        raise RobustFCRSolverDependencyUnavailableError(
            "Feature 013 requires Pyomo "
            f"{REQUIRED_PYOMO_VERSION}; installed version is {pyomo_version}"
        )

    try:
        highspy = import_module("highspy")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RobustFCRSolverDependencyUnavailableError(
            "Feature 013 requires highspy 1.15.1; run `uv sync --dev` and retry"
        ) from exc
    highspy_version = _installed_highspy_version(highspy)
    if highspy_version != REQUIRED_HIGHSPY_VERSION:
        raise RobustFCRSolverDependencyUnavailableError(
            "Feature 013 requires highspy "
            f"{REQUIRED_HIGHSPY_VERSION}; installed version is {highspy_version}"
        )

    try:
        available = bool(
            pyomo_environ.SolverFactory("highs").available(exception_flag=False)
        )
    except Exception as exc:  # pragma: no cover - backend-specific defensive path
        raise RobustFCRSolverUnavailableError(
            "HiGHS is installed but Pyomo could not initialize its solver adapter"
        ) from exc
    if not available:
        raise RobustFCRSolverUnavailableError(
            "HiGHS is required for Feature 013 but is unavailable to Pyomo"
        )

    return SolverBackendModules(
        pyomo_package=pyomo_package,
        pyomo_environ=pyomo_environ,
        highspy=highspy,
        pyomo_version=pyomo_version,
        highspy_version=highspy_version,
    )


__all__ = [
    "REQUIRED_HIGHSPY_VERSION",
    "REQUIRED_PYOMO_VERSION",
    "RawRobustFCRSolveResult",
    "SolverBackendModules",
    "require_highs_backend",
]
