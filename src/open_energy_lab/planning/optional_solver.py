"""Lazy Pyomo dependency boundary for planning-model solve workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from types import SimpleNamespace
from typing import Any

from tpm.mio import build_spn_chance_model, extract_spn_solution

from .problem import (
    DEFAULT_SOLVER_NAME,
    DEFAULT_SOLVER_NUMERIC_TOLERANCE,
    DEFAULT_SOLVER_RANDOM_SEED,
    DEFAULT_SOLVER_THREADS,
    DEFAULT_SOLVER_TIME_LIMIT_SECONDS,
    PlanningProblemAssembly,
)


REQUIRED_PYOMO_VERSION = "6.10.1"
REQUIRED_HIGHSPY_VERSION = "1.15.1"
SUPPLEMENTAL_SOLVER_NAMES = frozenset({"gurobi"})


class PlanningSolverDependencyUnavailableError(ImportError):
    """Raised when a planning solve workflow requires Pyomo but it is unavailable."""


class PlanningSolverUnavailableError(RuntimeError):
    """Raised when a planning solve workflow cannot access a requested solver."""


@dataclass(frozen=True, slots=True)
class PlanningSolveConfig:
    """Deterministic configuration for planning solves."""

    solver_name: str = DEFAULT_SOLVER_NAME
    skip_if_unavailable: bool = False
    numeric_tolerance: float = DEFAULT_SOLVER_NUMERIC_TOLERANCE
    random_seed: int = DEFAULT_SOLVER_RANDOM_SEED
    threads: int = DEFAULT_SOLVER_THREADS
    time_limit_seconds: float = DEFAULT_SOLVER_TIME_LIMIT_SECONDS


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


@dataclass(frozen=True, slots=True)
class _PlanningPyomoModelHandoff:
    """Backend-owned SPN chance-constrained planning model."""

    model: object
    backend: Any
    backend_name: str
    backend_version: str
    handoff_strategy: str
    requested_solver_name: str


def require_pyomo_backend() -> Any:
    """Load and validate the required Pyomo/HiGHS solver stack lazily."""

    try:
        pyomo_package = import_module("pyomo")
        pyomo_backend = import_module("pyomo.environ")
    except ImportError as exc:  # pragma: no cover - depends on install state
        raise PlanningSolverDependencyUnavailableError(
            "Required planning dependency Pyomo "
            f"{REQUIRED_PYOMO_VERSION} is unavailable. Install the project "
            "dependencies before invoking the planning solve boundary."
        ) from exc

    pyomo_version = _module_version(pyomo_package)
    if pyomo_version != REQUIRED_PYOMO_VERSION:
        raise PlanningSolverDependencyUnavailableError(
            "Incompatible required Pyomo installation: expected "
            f"{REQUIRED_PYOMO_VERSION}, found {pyomo_version}."
        )

    try:
        highspy_backend = import_module("highspy")
    except ImportError as exc:  # pragma: no cover - depends on install state
        raise PlanningSolverDependencyUnavailableError(
            "Required planning dependency highspy "
            f"{REQUIRED_HIGHSPY_VERSION} is unavailable. Install the project "
            "dependencies before invoking the planning solve boundary."
        ) from exc

    highspy_version = _highspy_version(highspy_backend)
    if highspy_version != REQUIRED_HIGHSPY_VERSION:
        raise PlanningSolverDependencyUnavailableError(
            "Incompatible required highspy installation: expected "
            f"{REQUIRED_HIGHSPY_VERSION}, found {highspy_version}."
        )

    setattr(pyomo_backend, "_open_energy_lab_pyomo_version", pyomo_version)
    setattr(pyomo_backend, "_open_energy_lab_highspy_version", highspy_version)
    return pyomo_backend


def _module_version(module: object) -> str:
    version = getattr(module, "__version__", None)
    return "unknown" if version is None else str(version)


def _highspy_version(module: object) -> str:
    version = getattr(module, "__version__", None)
    if version is not None:
        return str(version)
    highs_factory = getattr(module, "Highs", None)
    if callable(highs_factory):
        highs = highs_factory()
        version_method = getattr(highs, "version", None)
        if callable(version_method):
            return str(version_method())
    return "unknown"


def solve_planning_problem(*args: object, **kwargs: object) -> object:
    """Solve one assembled planning problem through the lazy Pyomo boundary."""

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

    backend = pyomo_backend if pyomo_backend is not None else require_pyomo_backend()

    handoff = _build_pyomo_model_handoff(
        assembled_problem,
        solve_config=solve_config,
        backend=backend,
    )
    requested_solver_name = _resolve_solver_name(
        assembled_problem,
        solve_config=solve_config,
    )
    if handoff.handoff_strategy == "custom-backend-hook":
        return _solve_through_backend_hook(
            assembled_problem,
            solve_config=solve_config,
            handoff=handoff,
        )

    if requested_solver_name in ("", "pyomo"):
        raise ValueError(
            f"solver_name {requested_solver_name!r} selects no MIO solver; "
            "SPN planning models need an explicit solver such as 'highs'"
        )

    return _solve_through_pyomo_solver(
        assembled_problem,
        solve_config=solve_config,
        handoff=handoff,
    )


__all__ = [
    "PlanningSolveConfig",
    "PlanningSolveSummary",
    "PlanningSolverDependencyUnavailableError",
    "PlanningSolverUnavailableError",
    "require_pyomo_backend",
    "solve_planning_problem",
]


def _solver_metadata(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    backend: Any,
    status: str,
    handoff: _PlanningPyomoModelHandoff | None = None,
    solve_execution_mode: str | None = None,
) -> dict[str, object]:
    backend_name = getattr(backend, "__name__", backend.__class__.__name__)
    backend_version = getattr(
        backend,
        "_open_energy_lab_pyomo_version",
        getattr(backend, "__version__", "unknown"),
    )
    if isinstance(backend, SimpleNamespace):
        backend_name = str(getattr(backend, "__name__", backend_name))
        backend_version = str(getattr(backend, "__version__", backend_version))

    metadata = {
        **dict(assembled_problem.solver_metadata),
        "requested_solver_name": (
            handoff.requested_solver_name if handoff is not None else solve_config.solver_name
        ),
        "backend_module": backend_name,
        "backend_version": backend_version,
        "status": status,
    }
    if handoff is not None:
        metadata["handoff_strategy"] = handoff.handoff_strategy
        metadata["pyomo_model_type"] = handoff.model.__class__.__name__
    if solve_execution_mode is not None:
        metadata["solve_execution_mode"] = solve_execution_mode
    return metadata


def _resolve_solver_name(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
) -> str:
    configured_solver_name = str(assembled_problem.solver_configuration.get("solver_name", ""))
    if (
        solve_config.solver_name != DEFAULT_SOLVER_NAME
        or configured_solver_name in {"", DEFAULT_SOLVER_NAME}
    ):
        return solve_config.solver_name
    return configured_solver_name


def _build_pyomo_model_handoff(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    backend: Any,
) -> _PlanningPyomoModelHandoff:
    requested_solver_name = _resolve_solver_name(
        assembled_problem,
        solve_config=solve_config,
    )
    if not assembled_problem.spn_mip_payload:
        raise ValueError(
            f"planning problem {assembled_problem.problem_id!r} has no SPN-MIO payload"
        )

    if hasattr(backend, "build_spn_model"):
        model = backend.build_spn_model(
            problem_id=assembled_problem.problem_id,
            spn_payload=dict(assembled_problem.spn_mip_payload),
            chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
            shortfall_threshold=assembled_problem.shortfall_threshold,
            numeric_tolerance=solve_config.numeric_tolerance,
            piecewise_terms=assembled_problem.piecewise_terms,
            solver_configuration=dict(assembled_problem.solver_configuration),
        )
        handoff_strategy = "custom-backend-hook"
    else:
        model = _build_native_pyomo_spn_model(
            backend,
            problem_id=assembled_problem.problem_id,
            spn_payload=assembled_problem.spn_mip_payload,
            cost_terms=assembled_problem.cost_terms,
            option_costs=assembled_problem.option_costs,
            chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
            numeric_tolerance=solve_config.numeric_tolerance,
            piecewise_terms=assembled_problem.piecewise_terms,
        )
        handoff_strategy = "native-pyomo-spn"

    backend_name = getattr(backend, "__name__", backend.__class__.__name__)
    backend_version = getattr(backend, "__version__", "unknown")
    if isinstance(backend, SimpleNamespace):
        backend_name = str(getattr(backend, "__name__", backend_name))
        backend_version = str(getattr(backend, "__version__", backend_version))

    return _PlanningPyomoModelHandoff(
        model=model,
        backend=backend,
        backend_name=str(backend_name),
        backend_version=str(backend_version),
        handoff_strategy=handoff_strategy,
        requested_solver_name=requested_solver_name,
    )


def _build_native_pyomo_spn_model(
    backend: Any,
    *,
    problem_id: str,
    spn_payload: Mapping[str, object],
    cost_terms: Mapping[str, float],
    option_costs: Mapping[str, Mapping[object, float]],
    chance_limit_epsilon: float,
    numeric_tolerance: float,
    piecewise_terms: object,
) -> object:
    required_attributes = (
        "Binary",
        "Block",
        "ConcreteModel",
        "Constraint",
        "Objective",
        "Piecewise",
        "Reals",
        "Set",
        "Var",
        "minimize",
    )
    missing_attributes = [
        attribute_name
        for attribute_name in required_attributes
        if not hasattr(backend, attribute_name)
    ]
    if missing_attributes:
        raise PlanningSolverUnavailableError(
            "Injected pyomo backend is missing required SPN model-building attributes: "
            + ", ".join(missing_attributes)
        )

    return build_spn_chance_model(
        backend,
        problem_id=problem_id,
        spn_payload=dict(spn_payload),
        cost_terms={str(key): float(value) for key, value in cost_terms.items()},
        option_costs={
            str(name): {option: float(cost) for option, cost in values.items()}
            for name, values in option_costs.items()
        },
        chance_limit_epsilon=float(chance_limit_epsilon),
        numeric_tolerance=float(numeric_tolerance),
        piecewise_terms=piecewise_terms,
    )


def _solve_through_backend_hook(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    handoff: _PlanningPyomoModelHandoff,
) -> PlanningSolveSummary:
    try:
        raw_result = handoff.backend.solve_candidate_model(handoff, solve_config)
    except PlanningSolverUnavailableError as exc:
        return _handle_solver_unavailable(
            assembled_problem,
            solve_config=solve_config,
            handoff=handoff,
            error=exc,
        )
    return _summary_from_backend_result(
        assembled_problem,
        solve_config=solve_config,
        handoff=handoff,
        raw_result=raw_result,
    )


def _summary_from_backend_result(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    handoff: _PlanningPyomoModelHandoff,
    raw_result: object,
) -> PlanningSolveSummary:
    if not isinstance(raw_result, Mapping):
        raise TypeError("backend solve_candidate_model() must return a mapping")

    status = str(raw_result.get("status", ""))
    if status == "optimal":
        if "selected_design" not in raw_result:
            raise ValueError(
                "backend solve_candidate_model() must return selected_design "
                "for an optimal result"
            )
        return _optimal_direct_summary(
            assembled_problem,
            solve_config=solve_config,
            backend=handoff.backend,
            handoff=handoff,
            selected_design=_mapping_from_value(raw_result.get("selected_design")),
            objective_value=_float_or_none(raw_result.get("objective_value")),
            estimated_shortfall_risk=_float_or_none(
                raw_result.get("estimated_shortfall_risk")
            ),
            solve_execution_mode="custom-backend-hook",
            feasibility_diagnostics=_mapping_from_value(
                raw_result.get("feasibility_diagnostics")
            ),
            extra_solver_metadata=_mapping_from_value(raw_result.get("solver_metadata")),
        )
    if status == "infeasible":
        return _infeasible_summary(
            assembled_problem,
            solve_config=solve_config,
            backend=handoff.backend,
            handoff=handoff,
            reason=str(
                raw_result.get(
                    "reason",
                    "custom backend reported no feasible planning candidate",
                )
            ),
            solve_execution_mode="custom-backend-hook",
            extra_diagnostics=_mapping_from_value(raw_result.get("feasibility_diagnostics")),
            extra_solver_metadata=_mapping_from_value(raw_result.get("solver_metadata")),
        )
    if status == "skipped":
        if not _supplemental_skip_allowed(
            solve_config=solve_config,
            handoff=handoff,
        ):
            raise PlanningSolverUnavailableError(
                str(
                    raw_result.get("error")
                    or raw_result.get("reason")
                    or (
                        f"required solver {handoff.requested_solver_name!r} "
                        "cannot skip execution"
                    )
                )
            )
        return _skipped_summary(
            assembled_problem,
            solve_config=solve_config,
            reason=str(raw_result.get("reason", "custom backend skipped execution")),
            error=str(raw_result.get("error", "")) or None,
            backend=handoff.backend,
            handoff=handoff,
            extra_solver_metadata=_mapping_from_value(raw_result.get("solver_metadata")),
        )
    raise ValueError(
        "backend solve_candidate_model() must return status 'optimal', "
        "'infeasible', or 'skipped'"
    )


def _solve_through_pyomo_solver(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    handoff: _PlanningPyomoModelHandoff,
) -> PlanningSolveSummary:
    solver_factory = getattr(handoff.backend, "SolverFactory", None)
    if solver_factory is None:
        return _handle_solver_unavailable(
            assembled_problem,
            solve_config=solve_config,
            handoff=handoff,
            error=PlanningSolverUnavailableError(
                "pyomo backend does not expose SolverFactory for explicit solve execution"
            ),
        )

    try:
        solver = solver_factory(handoff.requested_solver_name)
    except Exception as exc:
        return _handle_solver_unavailable(
            assembled_problem,
            solve_config=solve_config,
            handoff=handoff,
            error=PlanningSolverUnavailableError(str(exc)),
        )

    if not _solver_is_available(solver):
        return _handle_solver_unavailable(
            assembled_problem,
            solve_config=solve_config,
            handoff=handoff,
            error=PlanningSolverUnavailableError(
                f"solver {handoff.requested_solver_name!r} is unavailable"
            ),
        )

    solver_options = _apply_solver_options(
        solver,
        assembled_problem=assembled_problem,
        solve_config=solve_config,
        solver_name=handoff.requested_solver_name,
    )
    try:
        results = solver.solve(handoff.model, tee=False, load_solutions=False)
    except Exception as exc:
        error = PlanningSolverUnavailableError(
            f"solver {handoff.requested_solver_name!r} execution failed: {exc}"
        )
        if handoff.requested_solver_name in SUPPLEMENTAL_SOLVER_NAMES:
            return _handle_solver_unavailable(
                assembled_problem,
                solve_config=solve_config,
                handoff=handoff,
                error=error,
            )
        raise error from exc
    result_metadata = {
        **_solver_result_metadata(results),
        **_solver_stack_metadata(handoff, solver_options=solver_options),
        "solutions_loaded": False,
    }
    if _solver_result_reports_infeasible(results):
        return _infeasible_summary(
            assembled_problem,
            solve_config=solve_config,
            backend=handoff.backend,
            handoff=handoff,
            reason="solver reported the planning model as infeasible",
            solve_execution_mode="native-pyomo-solver",
            extra_diagnostics=_solver_result_diagnostics(results),
            extra_solver_metadata=result_metadata,
        )
    if not _solver_result_reports_optimal(results):
        termination_status = _solver_termination_status(results)
        return _terminated_summary(
            assembled_problem,
            solve_config=solve_config,
            backend=handoff.backend,
            handoff=handoff,
            status=termination_status,
            reason=(
                "solver reached its configured time limit before proving optimality"
                if termination_status == "time_limit"
                else "solver terminated without proving optimality"
            ),
            solve_execution_mode="native-pyomo-solver",
            extra_diagnostics=_solver_result_diagnostics(results),
            extra_solver_metadata=result_metadata,
        )

    _load_pyomo_solution(handoff.model, results=results)
    result_metadata["solutions_loaded"] = True
    solution = extract_spn_solution(
        handoff.model,
        backend=handoff.backend,
        numeric_tolerance=solve_config.numeric_tolerance,
    )
    return _optimal_direct_summary(
        assembled_problem,
        solve_config=solve_config,
        backend=handoff.backend,
        handoff=handoff,
        selected_design=_mapping_from_value(solution.get("selected_design")),
        objective_value=_float_or_none(solution.get("objective_value")),
        estimated_shortfall_risk=_float_or_none(solution.get("estimated_shortfall_risk")),
        solve_execution_mode="native-pyomo-solver",
        feasibility_diagnostics=_solver_result_diagnostics(results),
        extra_solver_metadata=result_metadata,
    )


def _solver_is_available(solver: object) -> bool:
    available = getattr(solver, "available", None)
    if not callable(available):
        return True
    try:
        return bool(available(exception_flag=False))
    except TypeError:
        return bool(available())


def _apply_solver_options(
    solver: object,
    *,
    assembled_problem: PlanningProblemAssembly,
    solve_config: PlanningSolveConfig,
    solver_name: str,
) -> dict[str, object]:
    if not hasattr(solver, "options"):
        return {}
    options = getattr(solver, "options")
    update_options = getattr(options, "update", None)
    if not callable(update_options):
        return {}

    configured = assembled_problem.solver_configuration
    random_seed = configured.get("random_seed")
    if random_seed is None:
        random_seed = solve_config.random_seed
    threads = configured.get("threads", solve_config.threads)
    time_limit_seconds = configured.get("time_limit_seconds")
    if time_limit_seconds is None:
        time_limit_seconds = solve_config.time_limit_seconds
    if solver_name == DEFAULT_SOLVER_NAME:
        resolved = {
            "random_seed": int(random_seed),
            "threads": int(threads),
            "time_limit": float(time_limit_seconds),
        }
    else:
        resolved = (
            {}
            if time_limit_seconds is None
            else {"timelimit": float(time_limit_seconds)}
        )
    update_options(resolved)
    return resolved


def _load_pyomo_solution(model: object, *, results: object) -> None:
    solution_set = getattr(model, "solutions", None)
    load_from = getattr(solution_set, "load_from", None)
    if not callable(load_from):
        raise PlanningSolverUnavailableError(
            "Pyomo model does not expose solutions.load_from() for explicit loading"
        )
    load_from(results)


def _solver_stack_metadata(
    handoff: _PlanningPyomoModelHandoff,
    *,
    solver_options: Mapping[str, object],
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "solver_interface": "pyomo.SolverFactory",
        "solver_options": dict(solver_options),
    }
    risk_encoding_strategy = getattr(
        handoff.model,
        "_tpm_risk_encoding_strategy",
        None,
    )
    if risk_encoding_strategy is not None:
        metadata["risk_encoding_strategy"] = str(risk_encoding_strategy)
    if handoff.requested_solver_name != DEFAULT_SOLVER_NAME:
        return metadata

    pyomo_version = getattr(
        handoff.backend,
        "_open_energy_lab_pyomo_version",
        None,
    )
    highspy_version = getattr(
        handoff.backend,
        "_open_energy_lab_highspy_version",
        None,
    )
    if pyomo_version is None:
        pyomo_version = _module_version(import_module("pyomo"))
    if highspy_version is None:
        highspy_version = _highspy_version(import_module("highspy"))
    metadata["pyomo_version"] = str(pyomo_version)
    metadata["highspy_version"] = str(highspy_version)
    return metadata


def _solver_result_diagnostics(results: object) -> dict[str, object]:
    solver_block = getattr(results, "solver", None)
    diagnostics: dict[str, object] = {}
    if solver_block is not None:
        status = getattr(solver_block, "status", None)
        termination_condition = getattr(solver_block, "termination_condition", None)
        if status is not None:
            diagnostics["solver_status"] = str(status)
        if termination_condition is not None:
            diagnostics["termination_condition"] = str(termination_condition)
    return diagnostics


def _solver_result_metadata(results: object) -> dict[str, object]:
    return _solver_result_diagnostics(results)


def _solver_result_reports_infeasible(results: object) -> bool:
    diagnostics = _solver_result_diagnostics(results)
    termination_condition = str(diagnostics.get("termination_condition", "")).lower()
    return "infeasible" in termination_condition


def _solver_result_reports_optimal(results: object) -> bool:
    diagnostics = _solver_result_diagnostics(results)
    termination_condition = str(diagnostics.get("termination_condition", "")).lower()
    return termination_condition == "optimal"


def _solver_termination_status(results: object) -> str:
    diagnostics = _solver_result_diagnostics(results)
    termination_condition = "".join(
        character
        for character in str(diagnostics.get("termination_condition", "")).lower()
        if character.isalnum()
    )
    if "timelimit" in termination_condition:
        return "time_limit"
    return "solver_terminated"


def _optimal_direct_summary(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    backend: Any,
    handoff: _PlanningPyomoModelHandoff,
    selected_design: Mapping[str, object],
    objective_value: float | None,
    estimated_shortfall_risk: float | None,
    solve_execution_mode: str,
    feasibility_diagnostics: Mapping[str, object],
    extra_solver_metadata: Mapping[str, object] | None = None,
) -> PlanningSolveSummary:
    solver_metadata = _solver_metadata(
        assembled_problem,
        solve_config=solve_config,
        backend=backend,
        status="optimal",
        handoff=handoff,
        solve_execution_mode=solve_execution_mode,
    )
    if extra_solver_metadata:
        solver_metadata.update(dict(extra_solver_metadata))
    return PlanningSolveSummary(
        problem_id=assembled_problem.problem_id,
        status="optimal",
        selected_design=dict(selected_design),
        objective_value=objective_value,
        estimated_shortfall_risk=estimated_shortfall_risk,
        threshold=assembled_problem.shortfall_threshold,
        chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
        feasibility_diagnostics=dict(feasibility_diagnostics),
        solver_metadata=solver_metadata,
    )


def _infeasible_summary(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    backend: Any,
    handoff: _PlanningPyomoModelHandoff,
    reason: str,
    solve_execution_mode: str,
    extra_diagnostics: Mapping[str, object] | None = None,
    extra_solver_metadata: Mapping[str, object] | None = None,
) -> PlanningSolveSummary:
    feasibility_diagnostics: dict[str, object] = {"reason": reason}
    if extra_diagnostics:
        feasibility_diagnostics.update(dict(extra_diagnostics))
    solver_metadata = _solver_metadata(
        assembled_problem,
        solve_config=solve_config,
        backend=backend,
        status="infeasible",
        handoff=handoff,
        solve_execution_mode=solve_execution_mode,
    )
    if extra_solver_metadata:
        solver_metadata.update(dict(extra_solver_metadata))
    return PlanningSolveSummary(
        problem_id=assembled_problem.problem_id,
        status="infeasible",
        selected_design={},
        objective_value=None,
        estimated_shortfall_risk=None,
        threshold=assembled_problem.shortfall_threshold,
        chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
        feasibility_diagnostics=feasibility_diagnostics,
        solver_metadata=solver_metadata,
    )


def _terminated_summary(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    backend: Any,
    handoff: _PlanningPyomoModelHandoff,
    status: str,
    reason: str,
    solve_execution_mode: str,
    extra_diagnostics: Mapping[str, object] | None = None,
    extra_solver_metadata: Mapping[str, object] | None = None,
) -> PlanningSolveSummary:
    feasibility_diagnostics: dict[str, object] = {"reason": reason}
    if extra_diagnostics:
        feasibility_diagnostics.update(dict(extra_diagnostics))
    solver_metadata = _solver_metadata(
        assembled_problem,
        solve_config=solve_config,
        backend=backend,
        status=status,
        handoff=handoff,
        solve_execution_mode=solve_execution_mode,
    )
    if extra_solver_metadata:
        solver_metadata.update(dict(extra_solver_metadata))
    return PlanningSolveSummary(
        problem_id=assembled_problem.problem_id,
        status=status,
        selected_design={},
        objective_value=None,
        estimated_shortfall_risk=None,
        threshold=assembled_problem.shortfall_threshold,
        chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
        feasibility_diagnostics=feasibility_diagnostics,
        solver_metadata=solver_metadata,
    )


def _skipped_summary(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    reason: str,
    error: str | None = None,
    backend: Any | None = None,
    handoff: _PlanningPyomoModelHandoff | None = None,
    extra_solver_metadata: Mapping[str, object] | None = None,
) -> PlanningSolveSummary:
    solver_metadata = dict(assembled_problem.solver_metadata)
    solver_metadata["requested_solver_name"] = solve_config.solver_name
    solver_metadata["status"] = "skipped"
    if backend is not None:
        solver_metadata = _solver_metadata(
            assembled_problem,
            solve_config=solve_config,
            backend=backend,
            status="skipped",
            handoff=handoff,
            solve_execution_mode=(
                "custom-backend-hook" if handoff and handoff.handoff_strategy == "custom-backend-hook"
                else "model-handoff-only"
            ),
        )
    if extra_solver_metadata:
        solver_metadata.update(dict(extra_solver_metadata))

    feasibility_diagnostics: dict[str, object] = {"reason": reason}
    if error:
        feasibility_diagnostics["error"] = error
    return PlanningSolveSummary(
        problem_id=assembled_problem.problem_id,
        status="skipped",
        selected_design={},
        objective_value=None,
        estimated_shortfall_risk=None,
        threshold=assembled_problem.shortfall_threshold,
        chance_limit_epsilon=assembled_problem.chance_limit_epsilon,
        feasibility_diagnostics=feasibility_diagnostics,
        solver_metadata=solver_metadata,
    )


def _handle_solver_unavailable(
    assembled_problem: PlanningProblemAssembly,
    *,
    solve_config: PlanningSolveConfig,
    handoff: _PlanningPyomoModelHandoff,
    error: PlanningSolverUnavailableError,
) -> PlanningSolveSummary:
    if not _supplemental_skip_allowed(
        solve_config=solve_config,
        handoff=handoff,
    ):
        raise error
    return _skipped_summary(
        assembled_problem,
        solve_config=solve_config,
        reason="requested planning solver unavailable",
        error=str(error),
        backend=handoff.backend,
        handoff=handoff,
    )


def _supplemental_skip_allowed(
    *,
    solve_config: PlanningSolveConfig,
    handoff: _PlanningPyomoModelHandoff,
) -> bool:
    return (
        solve_config.skip_if_unavailable
        and handoff.requested_solver_name in SUPPLEMENTAL_SOLVER_NAMES
    )


def _mapping_from_value(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return {str(key): inner_value for key, inner_value in value.items()}
    return {}


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
