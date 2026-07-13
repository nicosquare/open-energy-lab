"""Unit contracts for first-release planning problem definitions."""

from __future__ import annotations

from dataclasses import fields

import pytest

from open_energy_lab.planning.problem import (
    PlanningProblemDefinition,
    SUPPORTED_FIRST_RELEASE_DECISION_TYPES,
    SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES,
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


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("shortfall_threshold", -0.01),
        ("shortfall_threshold", 1.01),
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
    }.issubset(field_names)
