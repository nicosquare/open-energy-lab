"""Environment-independent policy contracts for supplemental Gurobi solves."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from open_energy_lab.planning.optional_solver import (
    PlanningSolveConfig,
    PlanningSolverUnavailableError,
    solve_planning_problem,
)
from open_energy_lab.planning.problem import PlanningProblemAssembly
from tests.integration.planning.fixture_utils import (
    PLANNING_PROBLEM_FIXTURE_PATH,
    load_planning_fixture,
)


class _GurobiPolicyBackend(SimpleNamespace):
    failure: str | None = None
    observed_solver_name: str | None = None

    def build_spn_model(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(**kwargs)

    def solve_candidate_model(self, handoff: object, solve_config: object):
        self.observed_solver_name = str(getattr(solve_config, "solver_name"))
        if self.failure is not None:
            raise PlanningSolverUnavailableError(self.failure)
        return {
            "status": "optimal",
            "selected_design": {
                "battery_capacity_kwh": 8.0,
                "solar_capacity_kw": 4.0,
            },
            "objective_value": 13400.0,
            "estimated_shortfall_risk": 0.0,
            "solver_metadata": {
                "candidate_solver": self.observed_solver_name,
                "supplemental_solver": True,
            },
        }


def _assembled_problem() -> PlanningProblemAssembly:
    return PlanningProblemAssembly(
        problem_id="supplemental-gurobi-policy-unit",
        artifact_id="tpm-artifact:gurobi-policy-unit",
        dataset_reference="gurobi-policy-unit",
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
        piecewise_terms=SimpleNamespace(approximation_kind="piecewise"),
        solver_metadata={"canonical_backend": "pyomo"},
        solver_configuration={
            "backend_name": "pyomo",
            "solver_name": "highs",
            "solver_backend_required": True,
            "solver_execution_optional": False,
            "numeric_tolerance": 1e-9,
        },
        # The policy backend builds its own model, so the payload is opaque here.
        spn_mip_payload={"source": "gurobi-policy-unit"},
    )


def test_gurobi_must_be_selected_explicitly_as_a_supplemental_solver() -> None:
    backend = _GurobiPolicyBackend(__name__="pyomo.testing", __version__="0.test")

    summary = solve_planning_problem(
        _assembled_problem(),
        solve_config=PlanningSolveConfig(solver_name="gurobi"),
        pyomo_backend=backend,
    )

    assert backend.observed_solver_name == "gurobi"
    assert summary.status == "optimal"
    assert summary.solver_metadata["requested_solver_name"] == "gurobi"
    assert summary.solver_metadata["candidate_solver"] == "gurobi"
    assert summary.solver_metadata["supplemental_solver"] is True


@pytest.mark.parametrize(
    ("failure", "diagnostic"),
    [
        ("Gurobi binary unavailable", "binary unavailable"),
        ("Gurobi license unavailable", "license unavailable"),
    ],
)
def test_explicit_gurobi_can_skip_with_binary_or_license_diagnostics(
    failure: str,
    diagnostic: str,
) -> None:
    backend = _GurobiPolicyBackend(
        __name__="pyomo.testing",
        __version__="0.test",
        failure=failure,
    )

    summary = solve_planning_problem(
        _assembled_problem(),
        solve_config=PlanningSolveConfig(
            solver_name="gurobi",
            skip_if_unavailable=True,
        ),
        pyomo_backend=backend,
    )

    assert summary.status == "skipped"
    assert summary.solver_metadata["requested_solver_name"] == "gurobi"
    assert summary.feasibility_diagnostics["reason"] == (
        "requested planning solver unavailable"
    )
    assert diagnostic in summary.feasibility_diagnostics["error"].lower()


def test_required_highs_cannot_use_supplemental_skip_policy() -> None:
    backend = _GurobiPolicyBackend(
        __name__="pyomo.testing",
        __version__="0.test",
        failure="required HiGHS solver unavailable",
    )

    with pytest.raises(PlanningSolverUnavailableError, match="required HiGHS"):
        solve_planning_problem(
            _assembled_problem(),
            solve_config=PlanningSolveConfig(
                solver_name="highs",
                skip_if_unavailable=True,
            ),
            pyomo_backend=backend,
        )


def test_planning_fixture_defines_supplemental_solver_comparison_tolerances() -> None:
    fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)

    comparison = fixture["supplemental_solver_comparison"]
    assert isinstance(comparison, dict)
    assert comparison["reference_solver"] == "highs"
    assert comparison["candidate_solver"] == "gurobi"
    for tolerance_name in ("objective_tolerance", "risk_tolerance"):
        tolerance = comparison[tolerance_name]
        assert isinstance(tolerance, (int, float)) and not isinstance(tolerance, bool)
        assert float(tolerance) >= 0.0
