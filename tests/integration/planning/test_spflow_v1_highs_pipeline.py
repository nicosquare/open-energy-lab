"""End-to-end current-SPFlow compiler to real Pyomo/HiGHS coverage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from open_energy_lab.planning import (
    PlanningProblemDefinition,
    PlanningSolveConfig,
    assemble_planning_problem,
    solve_planning_problem,
)
from open_energy_lab.planning.workflow import compile_planning_study_tpm
from tpm import TPMApproximationDomain
from tpm import compile_spflow_model_to_mio, load_tpm_artifact
from tpm.optional_spflow import load_spflow_payload
from tpm.query import marginalize_spflow_model
from tests.integration.planning.fixture_utils import (
    TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH,
)


DECLARED_DOMAINS_ARTIFACT_PATH = "tests/fixtures/tpm/tpm_artifact_domains_v3.json"


NUMERIC_TOLERANCE = 1e-9
MIO_TOLERANCE = 1e-6


def _find_compiled_mio(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        if value.get("payload_format") == "open-energy-lab-spflow-mio":
            return value
        for nested in value.values():
            try:
                return _find_compiled_mio(nested)
            except LookupError:
                continue
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for nested in value:
            try:
                return _find_compiled_mio(nested)
            except LookupError:
                continue
    raise LookupError("planning handoff does not contain current-SPFlow MIO output")


def test_current_spflow_compiler_output_is_solved_by_real_highs() -> None:
    artifact = load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH)
    runtime_payload = load_spflow_payload(artifact)
    assert runtime_payload is not None
    compilation_model = marginalize_spflow_model(runtime_payload["model"], [2, 3, 4])
    compiled = compile_spflow_model_to_mio(
        compilation_model,
        feature_schema=artifact.feature_specs,
    )

    assembled = assemble_planning_problem(
        PlanningProblemDefinition(
            problem_id="current-spflow-v1-highs-pipeline",
            tpm_artifact_reference=str(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH),
            decision_features=("battery_capacity_kwh", "solar_enabled"),
            decision_feature_types={
                "battery_capacity_kwh": "continuous",
                "solar_enabled": "binary",
            },
            shortfall_threshold=0.08,
            chance_limit_epsilon=0.9,
            cost_terms={
                "battery_capacity_kwh": 1200.0,
                "solar_enabled": 950.0,
            },
            solver_configuration={
                "backend_name": "pyomo",
                "solver_name": "highs",
                "solver_backend_required": True,
                "solver_execution_optional": False,
                "numeric_tolerance": NUMERIC_TOLERANCE,
                "random_seed": 13,
                "threads": 1,
                "time_limit_seconds": 30.0,
            },
        ),
        artifact,
    )

    assert artifact.execution_mode == "production"
    assert compiled["compiler_version"] == "spflow-v1-mio-v1"
    assert compiled["breakpoint_policy"]["breakpoint_count"] == 5
    assert compiled["mio_epsilon"] == MIO_TOLERANCE
    assert assembled.risk_evaluation_mode == "spn_mip"
    planning_compiled = _find_compiled_mio(assembled.spn_mip_payload)
    assert planning_compiled == compiled
    assert compilation_model.scope.query == (0, 1, 5)

    summary = solve_planning_problem(
        assembled,
        solve_config=PlanningSolveConfig(solver_name="highs"),
    )

    assert summary.status == "optimal"
    assert summary.selected_design == {
        "battery_capacity_kwh": pytest.approx(2.0, abs=NUMERIC_TOLERANCE),
        "solar_enabled": 0.0,
    }
    assert summary.objective_value == pytest.approx(
        2400.0,
        rel=0.0,
        abs=NUMERIC_TOLERANCE,
    )
    assert summary.estimated_shortfall_risk == pytest.approx(
        5.0 / 6.0,
        rel=0.0,
        abs=MIO_TOLERANCE,
    )
    assert summary.estimated_shortfall_risk <= 0.9 + NUMERIC_TOLERANCE
    assert summary.feasibility_diagnostics["termination_condition"] == "optimal"
    assert summary.solver_metadata["requested_solver_name"] == "highs"
    assert summary.solver_metadata["handoff_strategy"] == "native-pyomo-spn"
    assert summary.solver_metadata["solve_execution_mode"] == "native-pyomo-solver"


def test_v3_planning_marginalizes_before_requesting_only_retained_intervals(
    tmp_path: Path,
) -> None:
    artifact = load_tpm_artifact(DECLARED_DOMAINS_ARTIFACT_PATH)

    result = compile_planning_study_tpm(
        artifact,
        output_path=tmp_path / "compiled-artifact.json",
        decision_features=("x", "activation"),
        approximation_domains=(
            TPMApproximationDomain(
                feature_name="x",
                lower=60.0,
                upper=140.0,
                source="planning-integration",
            ),
        ),
    )

    compiled = result.compiled_payload
    assert compiled["schema_version"] == "v2"
    assert [record["feature_name"] for record in compiled["compiled_validity"]] == [
        "x"
    ]
    retained_scopes = {
        int(scope)
        for node in compiled["nodes"]
        for scope in node.get("scope", ())
    }
    assert retained_scopes == {0, 1, 4}
    assert "demand" not in {
        curve["feature_name"]
        for node in compiled["nodes"]
        if node["type"] == "normal"
        for curve in node["curves"]
    }
