"""Unit coverage for serialized SPN-to-MIO model assembly."""

from __future__ import annotations

from pathlib import Path

import pyomo.environ as pyo
import pytest

from open_energy_lab.planning.piecewise import build_piecewise_planning_terms
from open_energy_lab.tpm.mio import (
    build_spn_chance_model,
    build_spn_chance_model_from_artifact,
    build_spn_modeling_terms,
    infer_max_sum_terms,
)
from open_energy_lab.tpm.artifact import LegacyTPMArtifactVersionError


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


def _artifact_payload(locator: str) -> dict[str, object]:
    return {
        "artifact_id": "tpm-artifact-mio-unit",
        "schema_version": "v1",
        "created_at": "2026-07-14T00:00:00Z",
        "dataset_reference": "synthetic-dataset",
        "feature_schema": [
            {
                "feature_name": "battery_capacity_kwh",
                "feature_role": "decision",
                "feature_type": "continuous",
                "bounds": [0.0, 10.0],
                "modifiable": True,
            },
            {
                "feature_name": "shortfall",
                "feature_role": "metric_target",
                "feature_type": "continuous",
                "bounds": [0.0, 1.0],
                "modifiable": False,
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
        "target_definition": {
            "target_name": "shortfall",
            "event_target_name": "shortfall_exceeds_threshold",
            "threshold_default": 0.05,
            "supported_query_mode": "exceedance-probability",
        },
        "fit_configuration": {"backend_name": "spflow"},
        "spn_payload": {
            "locator": locator,
            "serialization": "pickle",
            "backend": "spflow",
        },
        "spn_payload_format": "pickle-path",
        "query_configuration": {
            "supported_output_modes": ["conditional_probability", "log_likelihood"],
            "required_decision_features": ["battery_capacity_kwh"],
        },
        "approximation_metadata": {
            "approximation_kind": "piecewise",
            "sum_encoding_mode": "piecewise",
            "query_numeric_tolerance": 1e-9,
        },
        "provenance": {},
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


def test_legacy_fake_backend_artifact_cannot_enter_public_generic_tpm_surface(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        __import__("json").dumps(
            _artifact_payload("legacy-fake-spn-payload.pkl"),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LegacyTPMArtifactVersionError, match=r"(?i)legacy|refit"):
        build_spn_chance_model_from_artifact(
            pyo,
            artifact=artifact_path,
            problem_id="artifact-spn-mio-unit",
            decision_features=("battery_capacity_kwh",),
            cost_terms={"battery_capacity_kwh": 100.0},
            chance_limit_epsilon=0.1,
        )
