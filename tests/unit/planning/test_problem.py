"""Unit contracts for first-release planning problem definitions."""

from __future__ import annotations

from dataclasses import fields

import pytest

from open_energy_lab.planning.problem import (
    PlanningProblemDefinition,
    SUPPORTED_FIRST_RELEASE_DECISION_TYPES,
    SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES,
    SUPPORTED_OBJECTIVE_DIRECTIONS,
    SUPPORTED_PLANNING_BACKENDS,
    SUPPORTED_RISK_EVALUATION_MODES,
)


def test_planning_problem_definition_accepts_battery_and_solar_scope_only() -> None:
    problem = PlanningProblemDefinition(
        problem_id="planning-problem-unit",
        decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
        decision_feature_types={
            "battery_capacity_kwh": "continuous",
            "solar_capacity_kw": "continuous",
        },
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.1,
        cost_terms={
            "battery_capacity_kwh": 1200.0,
            "solar_capacity_kw": 950.0,
        },
    )

    assert SUPPORTED_FIRST_RELEASE_DECISION_TYPES == ("battery", "solar")
    assert problem.decision_features == ("battery_capacity_kwh", "solar_capacity_kw")
    assert problem.shortfall_threshold == pytest.approx(0.05)
    assert problem.chance_limit_epsilon == pytest.approx(0.1)


def test_planning_problem_definition_rejects_decision_features_outside_battery_and_solar_scope() -> None:
    with pytest.raises(ValueError, match="first-release planning scope|battery/solar"):
        PlanningProblemDefinition(
            problem_id="planning-problem-unit",
            decision_features=("inverter_capacity_kw",),
            decision_feature_types={"inverter_capacity_kw": "continuous"},
            shortfall_threshold=0.05,
            chance_limit_epsilon=0.1,
        )


def test_planning_problem_definition_preserves_distinct_threshold_and_chance_limit_semantics() -> None:
    problem = PlanningProblemDefinition(
        problem_id="planning-problem-unit",
        decision_features=("battery_capacity_kwh",),
        decision_feature_types={"battery_capacity_kwh": "continuous"},
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.2,
    )

    assert problem.shortfall_threshold == pytest.approx(0.05)
    assert problem.chance_limit_epsilon == pytest.approx(0.2)
    assert problem.shortfall_threshold != problem.chance_limit_epsilon


def test_planning_problem_definition_defaults_to_spn_mip_risk_mode() -> None:
    problem = PlanningProblemDefinition(
        problem_id="planning-problem-unit",
        decision_features=("battery_capacity_kwh",),
        decision_feature_types={"battery_capacity_kwh": "continuous"},
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.2,
    )

    assert SUPPORTED_RISK_EVALUATION_MODES == ("empirical_dataset", "spn_mip")
    assert problem.risk_evaluation_mode == "spn_mip"


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("shortfall_threshold", -0.01),
        ("shortfall_threshold", float("inf")),
        ("shortfall_threshold", True),
        ("chance_limit_epsilon", -0.01),
        ("chance_limit_epsilon", 1.01),
        ("chance_limit_epsilon", False),
    ),
)
def test_planning_problem_definition_rejects_invalid_threshold_and_chance_limit_values(
    field_name: str,
    invalid_value: object,
) -> None:
    kwargs = {
        "problem_id": "planning-problem-unit",
        "decision_features": ("battery_capacity_kwh",),
        "decision_feature_types": {"battery_capacity_kwh": "continuous"},
        "shortfall_threshold": 0.05,
        "chance_limit_epsilon": 0.1,
    }
    kwargs[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        PlanningProblemDefinition(**kwargs)


@pytest.mark.parametrize(
    ("feature_name", "feature_type"),
    (
        ("battery_capacity_kwh", "continuous"),
        ("solar_tracking_enabled", "binary"),
        ("solar_tariff_plan", "categorical"),
        ("battery_dispatch_mode", "mixed"),
    ),
)
def test_planning_problem_definition_accepts_each_supported_first_release_decision_variable_type(
    feature_name: str,
    feature_type: str,
) -> None:
    problem = PlanningProblemDefinition(
        problem_id="planning-problem-unit",
        decision_features=(feature_name,),
        decision_feature_types={feature_name: feature_type},
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.1,
    )

    assert SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES == (
        "continuous",
        "binary",
        "categorical",
        "mixed",
    )
    assert problem.decision_feature_types[feature_name] == feature_type


def test_planning_problem_definition_rejects_unsupported_first_release_decision_variable_types() -> None:
    with pytest.raises(ValueError, match="unsupported decision_variable_type|'ordinal'"):
        PlanningProblemDefinition(
            problem_id="planning-problem-unit",
            decision_features=("battery_capacity_kwh",),
            decision_feature_types={"battery_capacity_kwh": "ordinal"},
            shortfall_threshold=0.05,
            chance_limit_epsilon=0.1,
        )


def test_planning_problem_definition_requires_type_metadata_for_each_decision_feature() -> None:
    with pytest.raises(ValueError, match="decision_feature_types must define exactly one type"):
        PlanningProblemDefinition(
            problem_id="planning-problem-unit",
            decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
            decision_feature_types={"battery_capacity_kwh": "continuous"},
            shortfall_threshold=0.05,
            chance_limit_epsilon=0.1,
        )


def test_planning_problem_definition_tracks_documented_problem_fields() -> None:
    field_names = {field.name for field in fields(PlanningProblemDefinition)}

    assert {
        "problem_id",
        "decision_features",
        "decision_feature_types",
        "shortfall_threshold",
        "chance_limit_epsilon",
        "cost_terms",
        "tpm_artifact_reference",
        "risk_evaluation_mode",
        "objective_direction",
        "solver_configuration",
        "approximation_contract",
        "fixture_baseline",
    }.issubset(field_names)


def test_planning_problem_definition_normalizes_reproducibility_metadata() -> None:
    problem = PlanningProblemDefinition(
        problem_id="planning-problem-unit",
        tpm_artifact_reference="tests/fixtures/tpm/tpm_artifact_v1.json",
        decision_features=("battery_capacity_kwh", "solar_capacity_kw"),
        decision_feature_types={
            "battery_capacity_kwh": "continuous",
            "solar_capacity_kw": "continuous",
        },
        shortfall_threshold=0.05,
        chance_limit_epsilon=0.1,
        cost_terms={
            "battery_capacity_kwh": 1200.0,
            "solar_capacity_kw": 950.0,
        },
        solver_configuration={
            "backend_name": "pyomo",
            "solver_name": "fake-pyomo",
            "numeric_tolerance": 1e-8,
            "random_seed": 13,
        },
        approximation_contract={
            "approximation_kind": "piecewise",
            "leaf_encoding_mode": "histogram",
        },
        fixture_baseline={
            "label": "planning-baseline-a",
            "source_fixture_path": "tests/fixtures/planning/planning_problem_case.json",
            "expected_status": "optimal",
            "expected_selected_design": {
                "battery_capacity_kwh": 8.0,
                "solar_capacity_kw": 4.0,
            },
            "expected_objective_value": 13400.0,
            "expected_estimated_shortfall_risk": 0.0,
            "expected_candidate_count": 2,
            "expected_feasible_candidate_count": 2,
        },
    )

    assert SUPPORTED_OBJECTIVE_DIRECTIONS == ("minimize",)
    assert SUPPORTED_PLANNING_BACKENDS == ("pyomo",)
    assert problem.objective_direction == "minimize"
    assert problem.solver_configuration["backend_name"] == "pyomo"
    assert problem.solver_configuration["solver_name"] == "fake-pyomo"
    assert problem.solver_configuration["numeric_tolerance"] == pytest.approx(1e-8)
    assert problem.solver_configuration["random_seed"] == 13
    assert problem.approximation_contract["approximation_kind"] == "piecewise"
    assert problem.fixture_baseline["expected_candidate_count"] == 2
    assert problem.fixture_baseline["expected_selected_design"] == {
        "battery_capacity_kwh": 8.0,
        "solar_capacity_kw": 4.0,
    }


def test_planning_problem_definition_rejects_unsupported_solver_backend() -> None:
    with pytest.raises(ValueError, match="solver_configuration.backend_name"):
        PlanningProblemDefinition(
            problem_id="planning-problem-unit",
            decision_features=("battery_capacity_kwh",),
            decision_feature_types={"battery_capacity_kwh": "continuous"},
            shortfall_threshold=0.05,
            chance_limit_epsilon=0.1,
            solver_configuration={"backend_name": "docplex"},
        )


def test_planning_problem_definition_rejects_fixture_baseline_with_unknown_decision_feature() -> None:
    with pytest.raises(ValueError, match="fixture_baseline.expected_selected_design"):
        PlanningProblemDefinition(
            problem_id="planning-problem-unit",
            decision_features=("battery_capacity_kwh",),
            decision_feature_types={"battery_capacity_kwh": "continuous"},
            shortfall_threshold=0.05,
            chance_limit_epsilon=0.1,
            fixture_baseline={
                "expected_selected_design": {"solar_capacity_kw": 4.0},
            },
        )
