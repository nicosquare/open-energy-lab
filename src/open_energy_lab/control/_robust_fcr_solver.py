"""Lazy solver loading and backend-neutral raw results for robust FCR bidding."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import import_module
from types import MappingProxyType
from typing import Any
import math
import time

from ._robust_fcr_formulation import AssembledRobustFCRModel

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
class GurobiBackendModules:
    """Explicit optional Gurobi backend loaded only after caller selection."""

    pyomo_package: Any
    pyomo_environ: Any
    gurobipy: Any
    pyomo_version: str
    gurobi_version: str


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
            "robust FCR bidding requires Pyomo 6.10.1; run `uv sync --dev` and retry"
        ) from exc
    pyomo_version = str(getattr(pyomo_package, "__version__", "unknown"))
    if pyomo_version != REQUIRED_PYOMO_VERSION:
        raise RobustFCRSolverDependencyUnavailableError(
            "robust FCR bidding requires Pyomo "
            f"{REQUIRED_PYOMO_VERSION}; installed version is {pyomo_version}"
        )

    try:
        highspy = import_module("highspy")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RobustFCRSolverDependencyUnavailableError(
            "robust FCR bidding requires highspy 1.15.1; run `uv sync --dev` and retry"
        ) from exc
    highspy_version = _installed_highspy_version(highspy)
    if highspy_version != REQUIRED_HIGHSPY_VERSION:
        raise RobustFCRSolverDependencyUnavailableError(
            "robust FCR bidding requires highspy "
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
            "HiGHS is required for robust FCR bidding but is unavailable to Pyomo"
        )

    return SolverBackendModules(
        pyomo_package=pyomo_package,
        pyomo_environ=pyomo_environ,
        highspy=highspy,
        pyomo_version=pyomo_version,
        highspy_version=highspy_version,
    )


def load_optional_gurobi_backend() -> tuple[GurobiBackendModules | None, str | None]:
    """Return optional Gurobi modules or one actionable unavailable reason."""

    try:
        pyomo_package = import_module("pyomo")
        pyomo_environ = import_module("pyomo.environ")
        gurobipy = import_module("gurobipy")
    except (ImportError, ModuleNotFoundError) as exc:
        return None, (
            "optional Gurobi evidence is unavailable because gurobipy is not "
            f"installed ({exc}); install with `uv sync --extra gurobi`; restriction "
            "and relaxation remain available in HiGHS"
        )
    pyomo_version = str(getattr(pyomo_package, "__version__", "unknown"))
    if pyomo_version != REQUIRED_PYOMO_VERSION:
        return None, (
            f"optional exact Gurobi requires Pyomo {REQUIRED_PYOMO_VERSION}; "
            f"installed version is {pyomo_version}"
        )
    try:
        raw_version = gurobipy.gurobi.version()
        gurobi_version = ".".join(str(value) for value in raw_version)
        available = bool(
            pyomo_environ.SolverFactory("gurobi_direct").available(
                exception_flag=False
            )
        )
    except Exception as exc:
        return None, f"optional exact Gurobi adapter is unavailable: {exc}"
    if not available:
        return None, "optional exact Gurobi binary is unavailable to Pyomo"
    return (
        GurobiBackendModules(
            pyomo_package=pyomo_package,
            pyomo_environ=pyomo_environ,
            gurobipy=gurobipy,
            pyomo_version=pyomo_version,
            gurobi_version=gurobi_version,
        ),
        None,
    )


def _finite_backend_value(value: object, *, field_name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise RobustFCRSolverUnavailableError(
            f"solver returned a non-numeric {field_name}"
        ) from exc
    if not math.isfinite(normalized):
        raise RobustFCRSolverUnavailableError(
            f"solver returned a non-finite {field_name}"
        )
    return 0.0 if normalized == 0.0 else normalized


def _component_values(component: Any, indices: tuple[Any, ...], pyo: Any) -> tuple[float, ...]:
    return tuple(
        _finite_backend_value(
            pyo.value(component[index]),
            field_name=f"witness variable {component.name}[{index}]",
        )
        for index in indices
    )


def extract_complete_witness(
    assembled: AssembledRobustFCRModel,
    pyo: Any,
) -> Mapping[str, object]:
    """Extract a complete normalized witness from one assembled model."""

    handles = assembled.variable_handles
    index_sets = assembled.handoff.model_input.index_sets
    planning = index_sets.planning_indices
    energy = index_sets.energy_indices
    fcr = index_sets.fcr_indices
    strict = planning[:-1]
    witness: dict[str, object] = {
        "x0": _component_values(handles["x0"], energy, pyo),
        "xr": _component_values(handles["xr"], fcr, pyo),
        "xa": _component_values(handles["xa"], planning, pyo),
        "symin": _component_values(handles["symin"], planning, pyo),
        "symax": _component_values(handles["symax"], planning, pyo),
        "syK": _component_values(handles["syK"], (0, 1), pyo),
        "alpha": _component_values(handles["alpha"], planning, pyo),
        "beta": _component_values(handles["beta"], planning, pyo),
        "lambda_l": _component_values(handles["lambda_l"], planning, pyo),
        "lambda_h": _component_values(handles["lambda_h"], planning, pyo),
        "Lambda_l": tuple(
            tuple(
                _finite_backend_value(
                    pyo.value(handles["Lambda_l"][outer, inner]),
                    field_name=f"witness variable Lambda_l[{outer},{inner}]",
                )
                for inner in range(outer + 1)
            )
            for outer in planning
        ),
        "Lambda_h": tuple(
            tuple(
                _finite_backend_value(
                    pyo.value(handles["Lambda_h"][outer, inner]),
                    field_name=f"witness variable Lambda_h[{outer},{inner}]",
                )
                for inner in range(outer + 1)
            )
            for outer in planning
        ),
        "u1": _component_values(handles["u1"], strict, pyo),
        "u2": _component_values(handles["u2"], strict, pyo),
    }
    if "v_res" in handles:
        witness["v_res"] = _component_values(handles["v_res"], strict, pyo)
    return MappingProxyType(witness)


def extract_arbitrage_only_witness(
    assembled: AssembledRobustFCRModel,
    pyo: Any,
) -> Mapping[str, object]:
    """Extract the source hourly no-regulation witness and six fixed zeros."""

    handles = assembled.variable_handles
    hours = tuple(range(1, 25))
    blocks = tuple(range(1, 7))
    return MappingProxyType(
        {
            "x0": _component_values(handles["x0"], hours, pyo),
            "xr": _component_values(handles["xr"], blocks, pyo),
            "alpha": _component_values(handles["alpha"], hours, pyo),
            "u": _component_values(handles["u"], tuple(range(1, 24)), pyo),
            "symin": _component_values(handles["symin"], hours, pyo),
            "symax": _component_values(handles["symax"], hours, pyo),
            "syK": _component_values(handles["syK"], (0, 1), pyo),
        }
    )


def extract_rolling_0800_witness(
    assembled: AssembledRobustFCRModel,
    pyo: Any,
) -> Mapping[str, object]:
    """Extract complete extended decisions plus the current 24/6 output frame."""

    handles = assembled.variable_handles
    planning_ext = tuple(range(-63, 97))
    current = tuple(range(1, 97))
    current_strict = tuple(range(1, 96))
    hours = tuple(range(-15, 25))
    blocks = tuple(range(-3, 7))
    return MappingProxyType(
        {
            "x0_extended": _component_values(handles["x0"], hours, pyo),
            "xr_extended": _component_values(handles["xr"], blocks, pyo),
            "x0": _component_values(handles["x0"], tuple(range(1, 25)), pyo),
            "xr": _component_values(handles["xr"], tuple(range(1, 7)), pyo),
            "xa_extended": _component_values(handles["xa"], planning_ext, pyo),
            "symin_extended": _component_values(handles["symin"], planning_ext, pyo),
            "symax_extended": _component_values(handles["symax"], planning_ext, pyo),
            "syK": _component_values(handles["syK"], (0, 1), pyo),
            "alpha_extended": _component_values(handles["alpha"], planning_ext, pyo),
            "beta_extended": _component_values(handles["beta"], planning_ext, pyo),
            "lambda_l": _component_values(handles["lambda_l"], current, pyo),
            "lambda_h": _component_values(handles["lambda_h"], current, pyo),
            "Lambda_l": tuple(
                tuple(
                    _finite_backend_value(
                        pyo.value(handles["Lambda_l"][outer, inner]),
                        field_name=f"witness variable Lambda_l[{outer},{inner}]",
                    )
                    for inner in range(1, outer + 1)
                )
                for outer in current
            ),
            "Lambda_h": tuple(
                tuple(
                    _finite_backend_value(
                        pyo.value(handles["Lambda_h"][outer, inner]),
                        field_name=f"witness variable Lambda_h[{outer},{inner}]",
                    )
                    for inner in range(1, outer + 1)
                )
                for outer in current
            ),
            "u1": _component_values(handles["u1"], current_strict, pyo),
            "u2": _component_values(handles["u2"], current_strict, pyo),
            "v_res": _component_values(handles["v_res"], current_strict, pyo),
        }
    )


def _termination_text(results: Any) -> str:
    value = getattr(results.solver, "termination_condition", "unknown")
    return str(value).strip().lower().replace(" ", "_")


def _has_solver_confirmed_solution(results: Any) -> bool:
    try:
        return len(results.solution) > 0
    except (AttributeError, TypeError):
        return False


def normalize_backend_termination_status(
    termination: str,
    *,
    has_incumbent: bool,
) -> str:
    """Normalize solver-specific termination text without solver imports."""

    compact = termination.replace("_", "")
    if compact == "optimal":
        return "optimal" if has_incumbent else "failed"
    if "infeasible" in compact and "unbounded" not in compact:
        return "infeasible"
    if compact == "unbounded":
        return "unbounded"
    if any(
        token in compact
        for token in (
            "timelimit",
            "maxtimelimit",
            "iterationlimit",
            "maxiterations",
            "userinterrupt",
            "resourceinterrupt",
            "interrupted",
        )
    ):
        return "feasible" if has_incumbent else "no_solution"
    return "feasible" if has_incumbent else "failed"


def _result_upper_bound(results: Any) -> float | None:
    candidates: list[object] = []
    problem = getattr(results, "problem", None)
    if problem is not None:
        candidates.append(getattr(problem, "upper_bound", None))
        try:
            candidates.append(getattr(problem[0], "upper_bound", None))
        except (IndexError, KeyError, TypeError):
            pass
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            normalized = float(candidate)
        except (TypeError, ValueError):
            continue
        if math.isfinite(normalized):
            return 0.0 if normalized == 0.0 else normalized
    return None


def _highs_options(policy: Any) -> dict[str, object]:
    return {
        "time_limit": policy.time_limit_seconds,
        "threads": policy.threads,
        "random_seed": policy.random_seed,
        "primal_feasibility_tolerance": policy.primal_feasibility_tolerance,
        "dual_feasibility_tolerance": policy.dual_feasibility_tolerance,
        "mip_feasibility_tolerance": policy.mip_feasibility_tolerance,
        "mip_rel_gap": policy.relative_mip_gap,
        "parallel": "off",
        "log_to_console": False,
    }


def solve_assembled_model(
    assembled: AssembledRobustFCRModel,
    policy: Any,
    *,
    backend: SolverBackendModules,
    witness_extractor: Any = extract_complete_witness,
) -> RawRobustFCRSolveResult:
    """Execute one assembled routine model without implicit solution loading."""

    if policy.solver_name != "highs":
        raise RobustFCRSolverUnavailableError(
            "restriction and relaxation require solver_name='highs'"
        )
    pyo = backend.pyomo_environ
    solver = pyo.SolverFactory("highs")
    options = _highs_options(policy)
    for name, value in options.items():
        solver.options[name] = value
    started = time.perf_counter()
    try:
        results = solver.solve(
            assembled.model,
            tee=False,
            load_solutions=False,
        )
    except Exception as exc:
        raise RobustFCRSolverUnavailableError(
            f"HiGHS execution failed for {assembled.handoff.formulation_kind}: {exc}"
        ) from exc
    runtime = time.perf_counter() - started
    termination = _termination_text(results)
    confirmed = _has_solver_confirmed_solution(results)
    diagnostics: list[Mapping[str, object]] = []
    witness: Mapping[str, object] | None = None
    objective: float | None = None
    if confirmed:
        try:
            assembled.model.solutions.load_from(results)
            witness = witness_extractor(assembled, pyo)
            objective = _finite_backend_value(
                pyo.value(assembled.model.objective),
                field_name="objective value",
            )
        except Exception as exc:
            diagnostics.append(
                {
                    "code": "incomplete_or_nonfinite_incumbent",
                    "severity": "error",
                    "message": str(exc),
                }
            )
            confirmed = False
            witness = None
            objective = None
    status = normalize_backend_termination_status(termination, has_incumbent=confirmed)
    upper_bound = _result_upper_bound(results)
    if status == "optimal" and objective is not None and upper_bound is None:
        upper_bound = objective
        diagnostics.append(
            {
                "code": "optimal_bound_fallback",
                "severity": "info",
                "message": (
                    "backend omitted a best bound for proven optimal termination; "
                    "the incumbent objective is the normalized bound"
                ),
            }
        )
    return RawRobustFCRSolveResult(
        solve_status=status,
        termination_status=termination,
        has_incumbent=confirmed,
        objective_value_eur=objective,
        best_upper_bound_eur=upper_bound,
        witness=witness,
        solver_name="highs",
        solver_version=backend.highspy_version,
        pyomo_version=backend.pyomo_version,
        highspy_version=backend.highspy_version,
        configured_options={
            **options,
            "load_solutions": False,
        },
        model_cardinality=assembled.handoff.cardinality,
        diagnostics=tuple(diagnostics),
        runtime_seconds=runtime,
        runtime_metadata={
            "elapsed_seconds": runtime,
            "tee": False,
            "temporary_logs_retained": False,
        },
    )


def unavailable_gurobi_raw_result(
    reason: str,
    policy: Any,
    *,
    cardinality: Mapping[str, int] | None = None,
    code: str = "optional_gurobi_unavailable",
    exact: bool = False,
) -> RawRobustFCRSolveResult:
    options: dict[str, object] = {
        "TimeLimit": policy.time_limit_seconds,
        "Threads": policy.threads,
        "Seed": policy.random_seed,
    }
    if exact:
        options["NonConvex"] = 2
    return RawRobustFCRSolveResult(
        solve_status="unavailable",
        termination_status="optional_backend_unavailable",
        has_incumbent=False,
        solver_name="gurobi",
        configured_options=options,
        model_cardinality=cardinality or {},
        diagnostics=(
            {
                "code": code,
                "severity": "warning",
                "message": reason,
            },
        ),
        runtime_metadata={
            "optional_evidence": "unavailable",
            "optional_exact": exact,
        },
    )


def unavailable_exact_raw_result(
    reason: str,
    policy: Any,
    *,
    cardinality: Mapping[str, int] | None = None,
    code: str = "optional_exact_unavailable",
) -> RawRobustFCRSolveResult:
    """Retain the exact-formulation compatibility helper."""

    return unavailable_gurobi_raw_result(
        reason,
        policy,
        cardinality=cardinality,
        code=code,
        exact=True,
    )


def solve_gurobi_assembled_model(
    assembled: AssembledRobustFCRModel,
    policy: Any,
    *,
    backend: GurobiBackendModules,
    exact: bool = False,
) -> RawRobustFCRSolveResult:
    """Run one explicitly selected Gurobi model without any fallback."""

    if policy.solver_name != "gurobi":
        raise RobustFCRSolverUnavailableError(
            "Gurobi execution requires solver_name='gurobi'"
        )
    if exact != (assembled.handoff.formulation_kind == "exact"):
        raise RobustFCRSolverUnavailableError(
            "Gurobi nonconvex mode must match the assembled formulation kind"
        )

    pyo = backend.pyomo_environ
    solver = pyo.SolverFactory("gurobi_direct")
    options = {
        "TimeLimit": policy.time_limit_seconds,
        "Threads": policy.threads,
        "Seed": policy.random_seed,
        "FeasibilityTol": policy.primal_feasibility_tolerance,
        "OptimalityTol": policy.dual_feasibility_tolerance,
        "IntFeasTol": policy.mip_feasibility_tolerance,
        "MIPGap": policy.relative_mip_gap,
        "OutputFlag": 0,
    }
    if exact:
        options["NonConvex"] = 2
    for name, value in options.items():
        solver.options[name] = value
    started = time.perf_counter()
    try:
        results = solver.solve(
            assembled.model,
            tee=False,
            load_solutions=False,
        )
    except Exception as exc:
        return unavailable_gurobi_raw_result(
            f"optional Gurobi execution or license is unavailable: {exc}",
            policy,
            cardinality=assembled.handoff.cardinality,
            code=(
                "optional_exact_execution_unavailable"
                if exact
                else "optional_gurobi_execution_unavailable"
            ),
            exact=exact,
        )
    runtime = time.perf_counter() - started
    termination = _termination_text(results)
    confirmed = _has_solver_confirmed_solution(results)
    witness: Mapping[str, object] | None = None
    objective: float | None = None
    diagnostics: list[Mapping[str, object]] = []
    if confirmed:
        try:
            assembled.model.solutions.load_from(results)
            witness = extract_complete_witness(assembled, pyo)
            objective = _finite_backend_value(
                pyo.value(assembled.model.objective),
                field_name="objective value",
            )
        except Exception as exc:
            confirmed = False
            diagnostics.append(
                {
                    "code": "incomplete_or_nonfinite_incumbent",
                    "severity": "error",
                    "message": str(exc),
                }
            )
    status = normalize_backend_termination_status(termination, has_incumbent=confirmed)
    upper_bound = _result_upper_bound(results)
    if status == "optimal" and objective is not None and upper_bound is None:
        upper_bound = objective
        diagnostics.append(
            {
                "code": "optimal_bound_fallback",
                "severity": "info",
                "message": "proven-optimal exact objective used as omitted bound",
            }
        )
    return RawRobustFCRSolveResult(
        solve_status=status,
        termination_status=termination,
        has_incumbent=confirmed,
        objective_value_eur=objective,
        best_upper_bound_eur=upper_bound,
        witness=witness,
        solver_name="gurobi",
        solver_version=backend.gurobi_version,
        pyomo_version=backend.pyomo_version,
        configured_options={
            **options,
            "load_solutions": False,
        },
        model_cardinality=assembled.handoff.cardinality,
        diagnostics=tuple(diagnostics),
        runtime_seconds=runtime,
        runtime_metadata={
            "elapsed_seconds": runtime,
            "tee": False,
            "temporary_logs_retained": False,
            "optional_gurobi": True,
            "optional_exact": exact,
        },
    )


def solve_exact_assembled_model(
    assembled: AssembledRobustFCRModel,
    policy: Any,
    *,
    backend: GurobiBackendModules,
) -> RawRobustFCRSolveResult:
    """Retain the exact-formulation compatibility helper."""

    return solve_gurobi_assembled_model(
        assembled,
        policy,
        backend=backend,
        exact=True,
    )


__all__ = [
    "REQUIRED_HIGHSPY_VERSION",
    "REQUIRED_PYOMO_VERSION",
    "RawRobustFCRSolveResult",
    "GurobiBackendModules",
    "SolverBackendModules",
    "extract_arbitrage_only_witness",
    "extract_complete_witness",
    "extract_rolling_0800_witness",
    "require_highs_backend",
    "load_optional_gurobi_backend",
    "solve_exact_assembled_model",
    "solve_gurobi_assembled_model",
    "solve_assembled_model",
    "normalize_backend_termination_status",
    "unavailable_exact_raw_result",
    "unavailable_gurobi_raw_result",
]
