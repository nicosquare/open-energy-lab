"""Contracts for shared conditional graph transformation and evaluation."""

from __future__ import annotations

import pytest

from open_energy_lab.tpm.mio import condition_compiled_spflow_mio


def _feature_schema() -> list[dict[str, object]]:
    return [
        {"feature_name": "x", "feature_type": "continuous"},
        {
            "feature_name": "activation",
            "feature_type": "binary",
            "ordering": ["off", "on"],
        },
        {
            "feature_name": "service_tier",
            "feature_type": "categorical",
            "ordering": ["economy", "standard", "priority"],
        },
        {"feature_name": "demand", "feature_type": "continuous"},
        {
            "feature_name": "violation",
            "feature_type": "binary",
            "ordering": [0.0, 1.0],
        },
    ]


def _compiled_graph() -> dict[str, object]:
    return {
        "schema_version": "v2",
        "compiler_version": "spflow-v1-mio-v2",
        "fitted_artifact": {
            "artifact_id": "conditional-unit",
            "schema_version": "v3",
            "payload_hash": "a" * 64,
        },
        "feature_schema": _feature_schema(),
        "root_id": 8,
        "nodes": [
            {
                "id": 0,
                "type": "normal",
                "curves": [
                    {
                        "scope": 0,
                        "feature_name": "x",
                        "breakpoints": [0.0, 0.5, 1.0],
                        "log_values": [-2.0, -1.0, -2.0],
                    },
                    {
                        "scope": 3,
                        "feature_name": "demand",
                        "breakpoints": [-2.0, 0.0, 2.0],
                        "log_values": [-3.0, -1.0, -3.0],
                    },
                ],
            },
            {
                "id": 1,
                "type": "bernoulli",
                "feature_names": ["activation", "violation"],
                "probabilities": [[0.6, 0.4], [0.7, 0.3]],
            },
            {
                "id": 2,
                "type": "categorical",
                "feature_names": ["service_tier"],
                "probabilities": [[0.5, 0.3, 0.2]],
            },
            {"id": 3, "type": "product", "children": [0, 1, 2]},
            {
                "id": 4,
                "type": "normal",
                "curves": [
                    {
                        "scope": 0,
                        "feature_name": "x",
                        "breakpoints": [0.0, 0.5, 1.0],
                        "log_values": [-1.5, -0.7, -1.5],
                    },
                    {
                        "scope": 3,
                        "feature_name": "demand",
                        "breakpoints": [-2.0, 0.0, 2.0],
                        "log_values": [-2.5, -0.8, -2.5],
                    },
                ],
            },
            {
                "id": 5,
                "type": "bernoulli",
                "feature_names": ["activation", "violation"],
                "probabilities": [[0.2, 0.8], [0.25, 0.75]],
            },
            {
                "id": 6,
                "type": "categorical",
                "feature_names": ["service_tier"],
                "probabilities": [[0.2, 0.3, 0.5]],
            },
            {"id": 7, "type": "product", "children": [4, 5, 6]},
            {
                "id": 8,
                "type": "sum",
                "children": [3, 7],
                "weights": [0.55, 0.45],
            },
        ],
    }


def _node_types(conditioned: dict[str, object]) -> list[str]:
    return [str(node["type"]) for node in conditioned["nodes"]]


@pytest.mark.parametrize("event_index", [0, 1])
def test_conditioner_fixes_arbitrary_binary_event_index(event_index: int) -> None:
    conditioned = condition_compiled_spflow_mio(
        _compiled_graph(),
        decision_features=("x", "activation", "service_tier"),
        event_target_name="violation",
        event_value_index=event_index,
    )

    event_leaves = [
        node
        for node in conditioned["nodes"]
        if node.get("feature_name") == "violation"
    ]
    assert event_leaves
    assert {node["fixed_value"] for node in event_leaves} == {event_index}
    assert conditioned["conditioning"]["event_treatment"] == "fixed"
    assert conditioned["conditioning"]["event_value_index"] == event_index


def test_numerator_fixes_event_and_denominator_marginalizes_it() -> None:
    compiled = _compiled_graph()
    numerator = condition_compiled_spflow_mio(
        compiled,
        decision_features=("x", "activation", "service_tier"),
        event_target_name="violation",
        event_value_index=1,
    )
    denominator = condition_compiled_spflow_mio(
        compiled,
        decision_features=("x", "activation", "service_tier"),
        event_target_name="violation",
        event_value_index=None,
    )

    assert any(
        node.get("feature_name") == "violation" for node in numerator["nodes"]
    )
    assert not any(
        node.get("feature_name") == "violation" for node in denominator["nodes"]
    )
    assert denominator["conditioning"]["event_treatment"] == "marginalized"
    assert numerator["source_model"] == denominator["source_model"]


def test_conditioner_marginalizes_every_common_nonevent_feature() -> None:
    numerator = condition_compiled_spflow_mio(
        _compiled_graph(),
        decision_features=("x", "activation", "service_tier"),
        event_target_name="violation",
        event_value_index=1,
    )

    assert not any(node.get("feature_name") == "demand" for node in numerator["nodes"])
    assert numerator["conditioning"]["marginalized_features"] == ["demand"]


def test_empty_product_and_fully_marginalized_sum_become_exact_log_one() -> None:
    compiled = {
        **_compiled_graph(),
        "root_id": 2,
        "nodes": [
            {
                "id": 0,
                "type": "normal",
                "curves": [
                    {
                        "scope": 3,
                        "feature_name": "demand",
                        "breakpoints": [-1.0, 0.0, 1.0],
                        "log_values": [-2.0, -1.0, -2.0],
                    }
                ],
            },
            {
                "id": 1,
                "type": "normal",
                "curves": [
                    {
                        "scope": 3,
                        "feature_name": "demand",
                        "breakpoints": [-1.0, 0.0, 1.0],
                        "log_values": [-3.0, -1.0, -3.0],
                    }
                ],
            },
            {"id": 2, "type": "sum", "children": [0, 1], "weights": [0.4, 0.6]},
        ],
    }

    conditioned = condition_compiled_spflow_mio(
        compiled,
        decision_features=("x",),
        event_target_name="violation",
        event_value_index=None,
    )

    assert conditioned["nodes"] == [{"id": 0, "type": "log_one", "log_value": 0.0}]
    assert conditioned["root_id"] == 0


def test_product_drops_log_one_and_collapses_single_retained_child() -> None:
    compiled = {
        **_compiled_graph(),
        "root_id": 2,
        "nodes": [
            {
                "id": 0,
                "type": "normal",
                "curves": [
                    {
                        "scope": 0,
                        "feature_name": "x",
                        "breakpoints": [0.0, 1.0],
                        "log_values": [-1.0, -1.0],
                    }
                ],
            },
            {
                "id": 1,
                "type": "normal",
                "curves": [
                    {
                        "scope": 3,
                        "feature_name": "demand",
                        "breakpoints": [-1.0, 1.0],
                        "log_values": [-1.0, -1.0],
                    }
                ],
            },
            {"id": 2, "type": "product", "children": [0, 1]},
        ],
    }

    conditioned = condition_compiled_spflow_mio(
        compiled,
        decision_features=("x",),
        event_target_name="violation",
        event_value_index=None,
    )

    assert _node_types(conditioned) == ["leaf_piecewise"]
    assert conditioned["nodes"][0]["feature_name"] == "x"


@pytest.mark.parametrize(
    "nodes",
    [
        [{"id": 0, "type": "product", "children": [1]}],
        [
            {"id": 0, "type": "product", "children": [1]},
            {"id": 1, "type": "product", "children": [0]},
        ],
    ],
)
def test_conditioner_rejects_missing_or_cyclic_source_graphs(
    nodes: list[dict[str, object]],
) -> None:
    compiled = {**_compiled_graph(), "root_id": 0, "nodes": nodes}

    with pytest.raises(ValueError, match="does not exist|acyclic"):
        condition_compiled_spflow_mio(
            compiled,
            decision_features=("x",),
            event_target_name="violation",
            event_value_index=None,
        )


def test_conditioner_rejects_invalid_event_index_and_decision_feature() -> None:
    with pytest.raises(ValueError, match="event_value_index"):
        condition_compiled_spflow_mio(
            _compiled_graph(),
            decision_features=("x",),
            event_target_name="violation",
            event_value_index=2,
        )
    with pytest.raises(ValueError, match="decision feature"):
        condition_compiled_spflow_mio(
            _compiled_graph(),
            decision_features=("unknown",),
            event_target_name="violation",
            event_value_index=1,
        )

