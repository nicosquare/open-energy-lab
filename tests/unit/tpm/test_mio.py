"""Unit coverage for serialized SPN-to-MIO model assembly."""

from __future__ import annotations

import copy
import math

import pyomo.environ as pyo
import pytest

import tpm as tpm_package
import tpm.conditional_mio as conditional_mio_module
from open_energy_lab.planning.piecewise import build_piecewise_planning_terms
from tpm.mio import (
    build_spn_chance_model,
    build_spn_modeling_terms,
    evaluate_compiled_spflow_probability,
    infer_max_sum_terms,
)


def _feature_schema() -> list[dict[str, object]]:
    return [
        {
            "feature_name": "battery_capacity_kwh",
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
    ]


def _serialized_conditional_models() -> dict[str, object]:
    return {
        "numerator_model": {
            "root_id": 7,
            "nodes": [
                {
                    "id": 1,
                    "type": "leaf_histogram",
                    "feature_name": "battery_capacity_kwh",
                    "breaks": [0.0, 0.5, 1.0],
                    "densities": [0.8, 0.2],
                },
                {
                    "id": 2,
                    "type": "leaf_binary",
                    "feature_name": "shortfall_exceeds_threshold",
                    "densities": [0.3, 0.7],
                    "fixed_value": 1.0,
                },
                {"id": 3, "type": "product", "children": [1, 2]},
                {
                    "id": 4,
                    "type": "leaf_histogram",
                    "feature_name": "battery_capacity_kwh",
                    "breaks": [0.0, 0.5, 1.0],
                    "densities": [0.2, 0.8],
                },
                {
                    "id": 5,
                    "type": "leaf_binary",
                    "feature_name": "shortfall_exceeds_threshold",
                    "densities": [0.9, 0.1],
                    "fixed_value": 1.0,
                },
                {"id": 6, "type": "product", "children": [4, 5]},
                {"id": 7, "type": "sum", "children": [3, 6], "weights": [0.5, 0.5]},
            ],
        },
        "denominator_model": {
            "root_id": 13,
            "nodes": [
                {
                    "id": 11,
                    "type": "leaf_histogram",
                    "feature_name": "battery_capacity_kwh",
                    "breaks": [0.0, 0.5, 1.0],
                    "densities": [0.7, 0.3],
                },
                {
                    "id": 12,
                    "type": "leaf_histogram",
                    "feature_name": "battery_capacity_kwh",
                    "breaks": [0.0, 0.5, 1.0],
                    "densities": [0.3, 0.7],
                },
                {"id": 13, "type": "sum", "children": [11, 12], "weights": [0.6, 0.4]},
            ],
        },
    }


def _normalized_only_compiled_v1() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "compiler_version": "spflow-v1-mio-v1",
        "feature_schema": [
            {
                "feature_name": "legacy_x",
                "feature_role": "decision",
                "feature_type": "continuous",
                "bounds": [60.0, 140.0],
                "modifiable": True,
            }
        ],
        "root_id": 0,
        "nodes": [
            {
                "id": 0,
                "type": "normal",
                "scope": [0],
                "curves": [
                    {
                        "scope": 0,
                        "feature_name": "legacy_x",
                        "breakpoints": [0.0, 0.5, 1.0],
                        "log_values": [-1.0, -0.5, -1.0],
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize("sum_encoding_mode", ["max", "piecewise"])
def test_build_spn_chance_model_supports_only_valid_sum_encodings(
    sum_encoding_mode: str,
) -> None:
    piecewise_terms = build_piecewise_planning_terms(
        {
            "approximation_kind": "piecewise",
            "sum_encoding_mode": sum_encoding_mode,
        },
        max_terms=2,
        decision_features=("battery_capacity_kwh",),
        decision_feature_types={"battery_capacity_kwh": "continuous"},
    )

    model = build_spn_chance_model(
        pyo,
        problem_id="spn-mio-unit",
        spn_payload={
            "feature_schema": _feature_schema(),
            "decision_features": ["battery_capacity_kwh"],
            "sum_encoding_mode": sum_encoding_mode,
            "conditional_models": _serialized_conditional_models(),
        },
        cost_terms={"battery_capacity_kwh": 100.0},
        chance_limit_epsilon=0.1,
        numeric_tolerance=1e-9,
        piecewise_terms=piecewise_terms,
    )

    assert model._open_energy_lab_sum_encoding_mode == sum_encoding_mode
    assert model.chance_constraint is not None
    assert hasattr(model, "numerator_spn")
    assert hasattr(model, "denominator_spn")
    if sum_encoding_mode == "max":
        assert hasattr(model.numerator_spn, "sum_max_output_7")
        assert not hasattr(model.numerator_spn, "sum_log_piecewise_7")
    else:
        assert hasattr(model.numerator_spn, "sum_log_piecewise_7")
        assert hasattr(model.denominator_spn, "sum_log_piecewise_13")


def test_existing_whole_model_public_entry_point_does_not_route_through_attachment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_composable_attachment(*_args, **_kwargs):
        raise AssertionError("whole-model compatibility path used composable attachment")

    monkeypatch.setattr(
        conditional_mio_module,
        "attach_conditional_mio_pair",
        forbidden_composable_attachment,
    )
    assert tpm_package.build_spn_chance_model is build_spn_chance_model
    piecewise_terms = build_piecewise_planning_terms(
        {"approximation_kind": "piecewise", "sum_encoding_mode": "max"},
        max_terms=2,
        decision_features=("battery_capacity_kwh",),
        decision_feature_types={"battery_capacity_kwh": "continuous"},
    )

    model = tpm_package.build_spn_chance_model(
        pyo,
        problem_id="whole-model-compatibility",
        spn_payload={
            "feature_schema": _feature_schema(),
            "decision_features": ["battery_capacity_kwh"],
            "sum_encoding_mode": "max",
            "conditional_models": _serialized_conditional_models(),
        },
        cost_terms={"battery_capacity_kwh": 100.0},
        chance_limit_epsilon=0.1,
        numeric_tolerance=1e-9,
        piecewise_terms=piecewise_terms,
    )

    assert model._open_energy_lab_sum_encoding_mode == "max"
    assert hasattr(model, "total_cost")
    assert hasattr(model, "chance_constraint")
    assert not hasattr(model, "conditional_pair")


def test_compiled_v1_remains_normalized_only_without_physical_promotion() -> None:
    compiled = _normalized_only_compiled_v1()
    before = copy.deepcopy(compiled)

    probability = evaluate_compiled_spflow_probability(
        compiled,
        normalized_evidence={"legacy_x": 0.5},
    )

    assert probability == pytest.approx(math.exp(-0.5))
    assert compiled == before
    assert "compiled_validity" not in compiled
    with pytest.raises(ValueError, match="compiled-v1.*normalized_evidence only"):
        evaluate_compiled_spflow_probability(
            compiled,
            physical_evidence={"legacy_x": 100.0},
        )


def test_categorical_spn_uses_exact_compiled_risk_lookup() -> None:
    feature_schema = [
        {
            "feature_name": "battery_option_id",
            "feature_role": "decision",
            "feature_type": "categorical",
            "discrete_values": ["battery-small", "battery-large"],
            "ordering": ["battery-small", "battery-large"],
            "modifiable": True,
        },
        {
            "feature_name": "solar_option_id",
            "feature_role": "decision",
            "feature_type": "categorical",
            "discrete_values": ["solar-a", "solar-b"],
            "ordering": ["solar-a", "solar-b"],
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
    ]
    conditional_models = {
        "numerator_model": {
            "root_id": 3,
            "nodes": [
                {
                    "id": 1,
                    "type": "leaf_categorical",
                    "feature_name": "battery_option_id",
                    "densities": [0.1, 0.01],
                },
                {
                    "id": 2,
                    "type": "leaf_categorical",
                    "feature_name": "solar_option_id",
                    "densities": [0.5, 0.5],
                },
                {"id": 3, "type": "product", "children": [1, 2]},
            ],
        },
        "denominator_model": {
            "root_id": 13,
            "nodes": [
                {
                    "id": 11,
                    "type": "leaf_categorical",
                    "feature_name": "battery_option_id",
                    "densities": [0.5, 0.5],
                },
                {
                    "id": 12,
                    "type": "leaf_categorical",
                    "feature_name": "solar_option_id",
                    "densities": [0.5, 0.5],
                },
                {"id": 13, "type": "product", "children": [11, 12]},
            ],
        },
    }
    piecewise_terms = build_piecewise_planning_terms(
        {"approximation_kind": "piecewise", "sum_encoding_mode": "piecewise"},
        max_terms=2,
        decision_features=("battery_option_id", "solar_option_id"),
        decision_feature_types={
            "battery_option_id": "categorical",
            "solar_option_id": "categorical",
        },
    )

    model = build_spn_chance_model(
        pyo,
        problem_id="categorical-lookup-unit",
        spn_payload={
            "feature_schema": feature_schema,
            "decision_features": ["battery_option_id", "solar_option_id"],
            "sum_encoding_mode": "piecewise",
            "conditional_models": conditional_models,
        },
        cost_terms={},
        option_costs={
            "battery_option_id": {"battery-small": 5.0, "battery-large": 10.0},
            "solar_option_id": {"solar-a": 1.0, "solar-b": 2.0},
        },
        chance_limit_epsilon=0.05,
        numeric_tolerance=1e-9,
        piecewise_terms=piecewise_terms,
    )

    assert model._open_energy_lab_risk_encoding_strategy == "exact-categorical-lookup"
    assert model._open_energy_lab_categorical_combinations == (
        ("battery-small", "solar-a"),
        ("battery-small", "solar-b"),
        ("battery-large", "solar-a"),
        ("battery-large", "solar-b"),
    )
    assert model._open_energy_lab_risk_by_combination == pytest.approx(
        (0.2, 0.2, 0.02, 0.02)
    )
    assert not hasattr(model, "numerator_spn")
    assert not hasattr(model, "conditional_pair")
    assert not any(
        name.startswith("conditional_risk") for name in model.component_map()
    )


def test_infer_max_sum_terms_uses_the_largest_sum_node_arity() -> None:
    payload = {
        "conditional_models": {
            "numerator_model": {
                "root_id": 1,
                "nodes": [{"id": 1, "type": "sum", "children": [2, 3, 4], "weights": [0.2, 0.3, 0.5]}],
            },
            "denominator_model": {
                "root_id": 5,
                "nodes": [{"id": 5, "type": "sum", "children": [6, 7], "weights": [0.4, 0.6]}],
            },
        }
    }

    assert infer_max_sum_terms(payload) == 3


def test_infer_max_sum_terms_uses_two_as_the_smallest_supported_piecewise_domain() -> None:
    payload = {
        "conditional_models": {
            "numerator_model": {
                "root_id": 1,
                "nodes": [{"id": 1, "type": "product", "children": [2, 3]}],
            },
            "denominator_model": {
                "root_id": 4,
                "nodes": [{"id": 4, "type": "product", "children": [5, 6]}],
            },
        }
    }

    assert infer_max_sum_terms(payload) == 2


def test_build_spn_modeling_terms_builds_generic_piecewise_terms() -> None:
    terms = build_spn_modeling_terms(
        {
            "approximation_kind": "piecewise",
            "sum_encoding_mode": "piecewise",
        },
        max_terms=3,
    )

    assert terms.sum_encoding_mode == "piecewise"
    assert terms.max_terms == 3
    assert terms.exp_curve.domain_upper_bound == pytest.approx(0.0)
    assert terms.log_curve.domain_lower_bound == pytest.approx(1.0)
    assert terms.log_curve.domain_upper_bound == pytest.approx(3.0)
