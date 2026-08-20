"""Unit contracts for the optional planning-solver boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import open_energy_lab.planning.optional_solver as optional_solver_module
from open_energy_lab.planning.optional_solver import (
    PlanningSolveConfig,
    PlanningSolverDependencyUnavailableError,
    PlanningSolverUnavailableError,
    require_pyomo_backend,
    solve_planning_problem,
)
from open_energy_lab.planning.problem import (
    PlanningDecisionCandidate,
    PlanningProblemAssembly,
)


class _FakePyomoBackend(SimpleNamespace):
    def build_candidate_model(self, **kwargs):
        return SimpleNamespace(model_name=f"{kwargs['problem_id']}-handoff", **kwargs)

    def solve_candidate_model(self, handoff, solve_config):
        if getattr(self, "solver_unavailable", False):
            raise PlanningSolverUnavailableError("fake solver unavailable")

        selected_candidate_id = min(
            handoff.feasible_candidate_ids,
            key=lambda candidate_id: (
                handoff.candidate_lookup[candidate_id].objective_value,
                handoff.candidate_lookup[candidate_id].estimated_shortfall_risk,
            ),
        )
        return {
            "status": "optimal",
            "candidate_id": selected_candidate_id,
            "solver_metadata": {
                "backend_solver_name": solve_config.solver_name,
            },
            "feasibility_diagnostics": {
                "model_name": handoff.model.model_name,
            },
        }


def _assembled_problem() -> PlanningProblemAssembly:
    return PlanningProblemAssembly(
        problem_id="planning-problem-unit",
        artifact_id="tpm-artifact:planning-dataset-export-integration",
        dataset_reference="planning-dataset-export-integration",
        risk_evaluation_mode="empirical_dataset",
        decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
        target_name="shortfall",
        risk_target_name="shortfall_exceeds_threshold",
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.1,
        objective_direction="minimize",
        cost_terms={
            "battery_capacity_kwh": 1200.0,
            "solar_capacity_kw": 950.0,
        },
        candidate_designs=(
            PlanningDecisionCandidate(
                selected_design={
                    "battery_capacity_kwh": 8.0,
                    "solar_capacity_kw": 4.0,
                },
                objective_value=13400.0,
                estimated_shortfall_risk=0.0,
                matched_row_count=1,
            ),
        ),
        piecewise_terms=SimpleNamespace(
            approximation_kind="piecewise",
            fit_numeric_tolerance=1e-9,
            query_numeric_tolerance=1e-9,
        ),
        solver_metadata={
            "canonical_backend": "pyomo",
            "solver_execution_optional": True,
        },
        spn_mip_payload={},
    )


class _FakeSPNBackend(SimpleNamespace):
    def build_spn_model(self, **kwargs):
        return SimpleNamespace(model_name=f"{kwargs['problem_id']}-spn-handoff", **kwargs)

    def solve_candidate_model(self, handoff, solve_config):
        return {
            "status": "optimal",
            "selected_design": {
                "battery_capacity_kwh": 6.0,
                "solar_capacity_kw": 5.0,
            },
            "objective_value": 11950.0,
            "estimated_shortfall_risk": 0.08,
            "solver_metadata": {
                "backend_solver_name": solve_config.solver_name,
            },
            "feasibility_diagnostics": {
                "model_name": handoff.model.model_name,
            },
        }


def _assembled_spn_problem() -> PlanningProblemAssembly:
    problem = _assembled_problem()
    return PlanningProblemAssembly(
        problem_id=problem.problem_id,
        artifact_id=problem.artifact_id,
        dataset_reference=problem.dataset_reference,
        risk_evaluation_mode="spn_mip",
        decision_features=problem.decision_features,
        target_name=problem.target_name,
        risk_target_name=problem.risk_target_name,
        shortfall_threshold=problem.shortfall_threshold,
        chance_limit_epsilon=problem.chance_limit_epsilon,
        objective_direction=problem.objective_direction,
        cost_terms=problem.cost_terms,
        candidate_designs=problem.candidate_designs,
        piecewise_terms=SimpleNamespace(
            approximation_kind="piecewise",
            fit_numeric_tolerance=1e-9,
            query_numeric_tolerance=1e-9,
            exp_curve=SimpleNamespace(
                x_points=(-500.0, -6.9, 0.0),
                y_points=(0.0, 0.001, 1.0),
                domain_lower_bound=-500.0,
                domain_upper_bound=0.0,
            ),
            log_curve=SimpleNamespace(
                x_points=(1.0, 2.0),
                y_points=(0.0, 0.6931471805599453),
                domain_lower_bound=1.0,
                domain_upper_bound=2.0,
            ),
            sum_encoding_mode="piecewise",
            mio_epsilon=1e-6,
        ),
        solver_metadata=problem.solver_metadata,
        spn_mip_payload={
            "decision_features": ["battery_capacity_kwh", "solar_capacity_kw"],
            "feature_schema": [
                {
                    "feature_name": "battery_capacity_kwh",
                    "feature_role": "decision",
                    "feature_type": "continuous",
                    "bounds": [0.0, 20.0],
                    "modifiable": True,
                },
                {
                    "feature_name": "solar_capacity_kw",
                    "feature_role": "decision",
                    "feature_type": "continuous",
                    "bounds": [0.0, 10.0],
                    "modifiable": True,
                },
                {
                    "feature_name": "shortfall_exceeds_threshold",
                    "feature_role": "target",
                    "feature_type": "binary",
                    "discrete_values": [0.0, 1.0],
                    "ordering": [0.0, 1.0],
                    "modifiable": False,
                },
            ],
            "sum_encoding_mode": "piecewise",
            "conditional_models": {
                "numerator_model": {"root_id": 1, "nodes": [{"id": 1, "type": "sum", "children": [], "weights": []}]},
                "denominator_model": {"root_id": 1, "nodes": [{"id": 1, "type": "sum", "children": [], "weights": []}]},
            },
        },
    )


def test_require_pyomo_backend_raises_required_lazy_dependency_error(monkeypatch) -> None:
    def _raise_import_error(module_name: str):
        raise ImportError(module_name)

    monkeypatch.setattr(optional_solver_module, "import_module", _raise_import_error)

    with pytest.raises(
        PlanningSolverDependencyUnavailableError,
        match=r"(?i)required.*Pyomo|Pyomo.*required",
    ):
        require_pyomo_backend()


def test_solve_planning_problem_rejects_skip_when_required_backend_is_unavailable(
    monkeypatch,
) -> None:
    def _raise_dependency_error():
        raise PlanningSolverDependencyUnavailableError("pyomo missing")

    monkeypatch.setattr(optional_solver_module, "require_pyomo_backend", _raise_dependency_error)

    with pytest.raises(PlanningSolverDependencyUnavailableError, match="pyomo missing"):
        solve_planning_problem(
            _assembled_problem(),
            solve_config=PlanningSolveConfig(skip_if_unavailable=True),
        )


def test_solve_planning_problem_uses_injected_backend_without_importing_pyomo() -> None:
    summary = solve_planning_problem(
        _assembled_problem(),
        solve_config=PlanningSolveConfig(solver_name="fake-pyomo"),
        pyomo_backend=_FakePyomoBackend(__name__="pyomo.testing", __version__="0.test"),
    )

    assert summary.status == "optimal"
    assert summary.selected_design == {
        "battery_capacity_kwh": 8.0,
        "solar_capacity_kw": 4.0,
    }
    assert summary.objective_value == pytest.approx(13400.0)
    assert summary.estimated_shortfall_risk == pytest.approx(0.0)
    assert summary.solver_metadata["backend_module"] == "pyomo.testing"
    assert summary.solver_metadata["handoff_strategy"] == "custom-backend-hook"
    assert summary.solver_metadata["solve_execution_mode"] == "custom-backend-hook"
    assert summary.feasibility_diagnostics["model_name"] == "planning-problem-unit-handoff"


def test_solve_planning_problem_rejects_skip_for_non_supplemental_solver() -> None:
    with pytest.raises(PlanningSolverUnavailableError, match="fake solver unavailable"):
        solve_planning_problem(
            _assembled_problem(),
            solve_config=PlanningSolveConfig(
                solver_name="fake-pyomo",
                skip_if_unavailable=True,
            ),
            pyomo_backend=_FakePyomoBackend(
                __name__="pyomo.testing",
                __version__="0.test",
                solver_unavailable=True,
            ),
        )


def test_solve_planning_problem_accepts_direct_spn_backend_results() -> None:
    summary = solve_planning_problem(
        _assembled_spn_problem(),
        solve_config=PlanningSolveConfig(solver_name="fake-pyomo"),
        pyomo_backend=_FakeSPNBackend(__name__="pyomo.testing", __version__="0.test"),
    )

    assert summary.status == "optimal"
    assert summary.selected_design == {
        "battery_capacity_kwh": 6.0,
        "solar_capacity_kw": 5.0,
    }
    assert summary.objective_value == pytest.approx(11950.0)
    assert summary.estimated_shortfall_risk == pytest.approx(0.08)
    assert summary.solver_metadata["handoff_strategy"] == "custom-backend-hook"
    assert summary.solver_metadata["solve_execution_mode"] == "custom-backend-hook"
    assert summary.feasibility_diagnostics["model_name"] == "planning-problem-unit-spn-handoff"


def test_native_solver_time_limit_returns_diagnostic_summary_without_loading_solution() -> None:
    class _TimeLimitedSolver:
        def __init__(self) -> None:
            self.options: dict[str, object] = {}

        def available(self, *, exception_flag: bool = False) -> bool:
            return True

        def solve(self, model, *, tee: bool, load_solutions: bool):
            assert tee is False
            assert load_solutions is False
            return SimpleNamespace(
                solver=SimpleNamespace(
                    status="aborted",
                    termination_condition="maxTimeLimit",
                )
            )

    def _fail_if_loaded(results) -> None:
        raise AssertionError("a time-limited result must not be loaded")

    solver = _TimeLimitedSolver()
    backend = SimpleNamespace(
        __name__="pyomo.testing",
        __version__="0.test",
        _open_energy_lab_pyomo_version="6.10.1",
        _open_energy_lab_highspy_version="1.15.1",
        SolverFactory=lambda solver_name: solver,
    )
    problem = _assembled_problem()
    candidate = problem.candidate_designs[0]
    handoff = optional_solver_module._PlanningPyomoModelHandoff(
        model=SimpleNamespace(
            solutions=SimpleNamespace(load_from=_fail_if_loaded),
        ),
        backend=backend,
        backend_name="pyomo.testing",
        backend_version="0.test",
        handoff_strategy="native-pyomo",
        requested_solver_name="highs",
        candidate_ids=(0,),
        candidate_lookup={0: candidate},
        feasible_candidate_ids=(0,),
    )

    summary = optional_solver_module._solve_through_pyomo_solver(
        problem,
        solve_config=PlanningSolveConfig(time_limit_seconds=12.0),
        handoff=handoff,
    )

    assert summary.status == "time_limit"
    assert summary.selected_design == {}
    assert summary.objective_value is None
    assert summary.estimated_shortfall_risk is None
    assert summary.feasibility_diagnostics == {
        "reason": "solver reached its configured time limit before proving optimality",
        "candidate_count": 1,
        "feasible_candidate_count": 1,
        "solver_status": "aborted",
        "termination_condition": "maxTimeLimit",
    }
    assert summary.solver_metadata["solutions_loaded"] is False
    assert summary.solver_metadata["solver_options"]["time_limit"] == 12.0
