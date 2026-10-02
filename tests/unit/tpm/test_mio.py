"""Unit coverage for serialized SPN-to-MIO model assembly."""

from __future__ import annotations

import copy
import math

import pytest

from tpm.mio import (
    build_spn_modeling_terms,
    evaluate_compiled_spflow_probability,
    infer_max_sum_terms,
)


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
