"""Contracts for shared conditional graph transformation and evaluation."""

from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path

import pytest

import open_energy_lab.tpm.conditional_mio as conditional_mio_module
import open_energy_lab.tpm.query as query_module
from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.conditional import (
    TPMConditionalCircuit,
    TPMConditionalCircuitNode,
    TPMConditionalCompilationRequest,
    TPMConditionalEncodingPolicy,
    TPMConditionalNumericalPolicy,
    TPMConditionalPair,
)
from open_energy_lab.tpm.conditional_mio import (
    TPMConditionalEvaluationError,
    compile_conditional_mio_pair,
    evaluate_conditional_mio_pair,
)
from open_energy_lab.tpm.domains import TPMFeatureDomain, TPMNormalizationSpec
from open_energy_lab.tpm.mio import condition_compiled_spflow_mio
from open_energy_lab.tpm.query import evaluate_native_conditional_pair
from open_energy_lab.tpm.optional_spflow import SPFlowDependencyUnavailableError
from tests.unit.tpm.test_conditional_pair import _encoding, _pair


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TPM_FIXTURE_DIRECTORY = REPOSITORY_ROOT / "tests" / "fixtures" / "tpm"


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


def _compilation_request(
    *,
    event_value: object = 1.0,
    retained_decisions: tuple[str, ...] = ("x", "activation", "service_tier"),
    encoding: TPMConditionalEncodingPolicy | None = None,
    approximation_domains: tuple[dict[str, object], ...] = (
        {
            "feature_name": "x",
            "lower": 40.0,
            "upper": 160.0,
            "source": "conditional-unit",
            "encoding": "piecewise-log-density",
        },
    ),
) -> TPMConditionalCompilationRequest:
    return TPMConditionalCompilationRequest(
        source_artifact="tests/fixtures/tpm/tpm_artifact_domains_v3.json",
        event_target="demand_above_100",
        event_value=event_value,
        retained_decisions=retained_decisions,
        approximation_domains=approximation_domains,
        encoding=encoding or _encoding(),
        numerical_policy=TPMConditionalNumericalPolicy(
            tolerances={
                "embedding_parity_absolute_tolerance": 1e-6,
                "constraint_residual_absolute_tolerance": 1e-6,
                "positive_log_risk_limit": 1e-6,
                "domain_membership_tolerance": 0.0,
            }
        ),
    )


def _compiled_for_artifact(artifact) -> dict[str, object]:
    compiled = _compiled_graph()
    event_name = str(artifact.target_definition["event_target_name"])
    for node in compiled["nodes"]:
        if node.get("type") == "bernoulli":
            node["feature_names"] = [
                event_name if name == "violation" else name
                for name in node["feature_names"]
            ]
    compiled["mio_epsilon"] = 1e-6
    compiled["breakpoint_policy"] = {
        "policy_name": "physical-interval-relative-v2",
        "relative_breakpoints": [0.0, 0.5, 1.0],
    }
    compiled["feature_schema"] = [
        spec.to_dict(schema_version="v3") for spec in artifact.feature_specs
    ]
    compiled["fitted_artifact"] = {
        "artifact_id": artifact.artifact_id,
        "schema_version": artifact.schema_version,
        "payload_hash": artifact.payload_hash,
    }
    compiled["compiled_validity"] = [
        {
            "feature_name": "x",
            "feature_index": 0,
            "physical_interval": [40.0, 160.0],
            "model_interval": [0.0, 1.0],
            "physical_breakpoints": [40.0, 100.0, 160.0],
            "model_breakpoints": [0.0, 0.5, 1.0],
            "source": "conditional-unit",
            "encoding": "piecewise-log-density",
            "normalization": {
                "feature_name": "x",
                "feature_kind": "continuous",
                "kind": "min-max",
                "origin": "caller-declared",
                "lower": 40.0,
                "upper": 160.0
            },
            "compiler_version": "spflow-v1-mio-v2",
            "payload_schema_version": "v2",
        }
    ]
    return compiled


def _install_compiler_stubs(monkeypatch: pytest.MonkeyPatch, artifact) -> None:
    monkeypatch.setattr(
        conditional_mio_module,
        "load_tpm_artifact",
        lambda _source: artifact,
    )
    monkeypatch.setattr(
        conditional_mio_module,
        "load_spflow_payload",
        lambda _artifact: {
            "payload_kind": "current-spflow-model-sidecar",
            "backend_generation": "current-spflow",
            "backend_api_version": "1.1.0",
            "query_strategy": "spflow",
            "model": object(),
        },
    )
    monkeypatch.setattr(
        conditional_mio_module,
        "marginalize_spflow_model",
        lambda model, _indices: model,
    )
    monkeypatch.setattr(
        conditional_mio_module,
        "compile_spflow_model_to_mio",
        lambda *_args, **_kwargs: _compiled_for_artifact(artifact),
    )


def test_compiler_builds_one_explicit_learned_denominator_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    artifact = load_tpm_artifact(source_path)
    original_manifest = source_path.read_bytes()
    original_sidecar = artifact.sidecar_path.read_bytes()
    _install_compiler_stubs(monkeypatch, artifact)

    pair = compile_conditional_mio_pair(_compilation_request())

    assert pair.source.artifact_id == artifact.artifact_id
    assert pair.source.model_digest == pair.numerator.metadata["source_model"]["model_digest"]
    assert pair.source.model_digest == pair.denominator.metadata["source_model"]["model_digest"]
    assert pair.event.feature_name == "demand_above_100"
    assert pair.event.declared_value == 1.0
    assert pair.event.model_index == 1
    assert pair.retained_decisions == ("x", "activation", "service_tier")
    assert pair.marginalized_features == ("demand",)
    assert pair.numerator.metadata["event_treatment"] == "fixed"
    assert pair.denominator.metadata["event_treatment"] == "marginalized"
    assert any(node.node_type == "sum" for node in pair.numerator.nodes)
    assert any(node.node_type == "sum" for node in pair.denominator.nodes)
    assert any(
        node.feature_name == "demand_above_100" for node in pair.numerator.nodes
    )
    assert not any(
        node.feature_name == "demand_above_100" for node in pair.denominator.nodes
    )
    assert pair.encoding.approximation_label.endswith("max-approximation")
    assert pair.encoding.certification_label == "uncertified"
    assert source_path.read_bytes() == original_manifest
    assert artifact.sidecar_path.read_bytes() == original_sidecar


def test_compiler_resolves_max_and_pwl_without_fallback_and_changes_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)

    max_pair = compile_conditional_mio_pair(_compilation_request())
    pwl_pair = compile_conditional_mio_pair(
        _compilation_request(encoding=_encoding("piecewise"))
    )
    other_event = compile_conditional_mio_pair(
        _compilation_request(event_value=0.0)
    )
    reordered_decisions = compile_conditional_mio_pair(
        _compilation_request(
            retained_decisions=("service_tier", "activation", "x")
        )
    )

    assert max_pair.encoding.mode == "max"
    assert pwl_pair.encoding.mode == "piecewise"
    assert pwl_pair.encoding.approximation_label.endswith("linear-approximation")
    assert max_pair.pair_id != pwl_pair.pair_id
    assert max_pair.pair_id != other_event.pair_id
    assert max_pair.pair_id != reordered_decisions.pair_id


def test_compiler_rejects_ineligible_legacy_or_omitted_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    legacy = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_spflow_v1.json"
    )
    _install_compiler_stubs(monkeypatch, legacy)
    with pytest.raises(ValueError, match="schema-v3|declared U-Bounds"):
        compile_conditional_mio_pair(_compilation_request())

    x_spec = current.feature_specs[0]
    omitted_x = replace(
        x_spec,
        bounds=(60.0, 140.0),
        mathematical_domain=TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape="unknown",
            origin="omitted",
        ),
        normalization=TPMNormalizationSpec(
            feature_name="x",
            feature_kind="continuous",
            kind="min-max",
            origin="legacy-inferred",
            lower=60.0,
            upper=140.0,
        ),
    )
    omitted = replace(
        current,
        feature_schema=tuple(
            omitted_x.to_dict(schema_version="v3")
            if spec.feature_name == "x"
            else spec.to_dict(schema_version="v3")
            for spec in current.feature_specs
        ),
    )
    _install_compiler_stubs(monkeypatch, omitted)
    with pytest.raises(ValueError, match="omitted|legacy-inferred"):
        compile_conditional_mio_pair(_compilation_request())


def test_compiler_rejects_invalid_event_domains_and_approximation_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)

    with pytest.raises(ValueError, match="event value"):
        compile_conditional_mio_pair(_compilation_request(event_value="unknown"))
    with pytest.raises(ValueError, match="approximation domain"):
        compile_conditional_mio_pair(
            _compilation_request(approximation_domains=())
        )
    with pytest.raises(ValueError, match="outside"):
        compile_conditional_mio_pair(
            _compilation_request(
                approximation_domains=(
                    {
                        "feature_name": "x",
                        "lower": 39.0,
                        "upper": 160.0,
                        "source": "conditional-unit",
                        "encoding": "piecewise-log-density",
                    },
                )
            )
        )
    with pytest.raises(TypeError, match="unexpected"):
        TPMConditionalCompilationRequest(
            source_artifact="source.json",
            event_target="demand_above_100",
            event_value=1.0,
            retained_decisions=("x",),
            approximation_domains=(),
            encoding=_encoding(),
            numerical_policy=_compilation_request().numerical_policy,
            fixed_context={"weather": "sunny"},
        )


def _pair_with_circuits(
    *,
    mode: str,
    numerator: TPMConditionalCircuit,
    denominator: TPMConditionalCircuit,
) -> TPMConditionalPair:
    base = _pair(encoding=_encoding(mode))
    payload = base.to_dict()
    payload["pair_id"] = ""
    payload["numerator"] = numerator.to_dict()
    payload["denominator"] = denominator.to_dict()
    return TPMConditionalPair.from_dict(payload)


def _constant_curve(value: float, *, treatment: str) -> TPMConditionalCircuit:
    return TPMConditionalCircuit(
        root_id=0,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [value, value],
                }
            ),
        ),
        metadata={"event_treatment": treatment},
    )


def test_direct_evaluator_accepts_exactly_one_complete_assignment_mode() -> None:
    pair = _pair()

    declared = evaluate_conditional_mio_pair(
        pair,
        declared_domain_assignments={"x": 100.0},
    )
    coordinate = evaluate_conditional_mio_pair(
        pair,
        model_coordinate_assignments={"x": 0.5},
    )

    assert declared.assignment_mode == "declared-domain"
    assert coordinate.assignment_mode == "model-coordinate"
    assert declared.numerator_log == pytest.approx(coordinate.numerator_log)
    with pytest.raises(ValueError, match="exactly one"):
        evaluate_conditional_mio_pair(pair)
    with pytest.raises(ValueError, match="exactly one"):
        evaluate_conditional_mio_pair(
            pair,
            declared_domain_assignments={"x": 100.0},
            model_coordinate_assignments={"x": 0.5},
        )
    with pytest.raises(ValueError, match="missing|complete"):
        evaluate_conditional_mio_pair(pair, declared_domain_assignments={})
    with pytest.raises(ValueError, match="unknown|extra"):
        evaluate_conditional_mio_pair(
            pair,
            declared_domain_assignments={"x": 100.0, "extra": 1.0},
        )


def test_direct_evaluator_preserves_closed_boundaries_without_clipping() -> None:
    pair = _pair()

    evaluate_conditional_mio_pair(pair, declared_domain_assignments={"x": 40.0})
    evaluate_conditional_mio_pair(pair, declared_domain_assignments={"x": 160.0})
    with pytest.raises(ValueError, match="closed approximation domain"):
        evaluate_conditional_mio_pair(
            pair,
            declared_domain_assignments={"x": math.nextafter(40.0, -math.inf)},
        )
    with pytest.raises(ValueError, match="finite"):
        evaluate_conditional_mio_pair(
            pair,
            declared_domain_assignments={"x": math.inf},
        )


def test_direct_evaluator_classifies_raw_positive_risk_without_clamping() -> None:
    numerical_noise = _pair_with_circuits(
        mode="max",
        numerator=_constant_curve(5e-7, treatment="fixed"),
        denominator=_constant_curve(0.0, treatment="marginalized"),
    )
    invalid = _pair_with_circuits(
        mode="max",
        numerator=_constant_curve(2e-6, treatment="fixed"),
        denominator=_constant_curve(0.0, treatment="marginalized"),
    )

    result = evaluate_conditional_mio_pair(
        numerical_noise,
        model_coordinate_assignments={"x": 0.5},
    )
    assert result.conditional_log_risk == pytest.approx(5e-7)
    assert result.conditional_probability > 1.0
    assert result.classification == "positive-numerical-noise"
    with pytest.raises(TPMConditionalEvaluationError) as error:
        evaluate_conditional_mio_pair(
            invalid,
            model_coordinate_assignments={"x": 0.5},
        )
    assert error.value.evaluation.conditional_log_risk == pytest.approx(2e-6)


def test_direct_evaluator_preserves_probability_underflow() -> None:
    pair = _pair_with_circuits(
        mode="max",
        numerator=_constant_curve(-1000.0, treatment="fixed"),
        denominator=_constant_curve(0.0, treatment="marginalized"),
    )

    result = evaluate_conditional_mio_pair(
        pair,
        model_coordinate_assignments={"x": 0.5},
    )

    assert result.conditional_log_risk == -1000.0
    assert result.conditional_probability == 0.0
    assert result.classification == "valid"


def _sum_circuits() -> tuple[TPMConditionalCircuit, TPMConditionalCircuit]:
    numerator = TPMConditionalCircuit(
        root_id=6,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [-2.0, -2.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 1,
                    "type": "leaf_binary",
                    "feature_name": "violation",
                    "densities": [0.5, 0.5],
                    "fixed_value": 1,
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {"id": 2, "type": "product", "children": [0, 1]}
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 3,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [-3.0, -3.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 4,
                    "type": "leaf_binary",
                    "feature_name": "violation",
                    "densities": [0.2, 0.8],
                    "fixed_value": 1,
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {"id": 5, "type": "product", "children": [3, 4]}
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 6,
                    "type": "sum",
                    "children": [2, 5],
                    "weights": [0.5, 0.5],
                }
            ),
        ),
        metadata={"event_treatment": "fixed"},
    )
    denominator = TPMConditionalCircuit(
        root_id=2,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [-1.0, -1.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 1,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [-2.0, -2.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 2,
                    "type": "sum",
                    "children": [0, 1],
                    "weights": [0.5, 0.5],
                }
            ),
        ),
        metadata={"event_treatment": "marginalized"},
    )
    return numerator, denominator


def _strict_test_interpolate(
    value: float,
    x_points: tuple[float, ...],
    y_points: tuple[float, ...],
) -> float:
    for left_x, right_x, left_y, right_y in zip(
        x_points, x_points[1:], y_points, y_points[1:]
    ):
        if left_x <= value <= right_x:
            return left_y + (value - left_x) * (right_y - left_y) / (
                right_x - left_x
            )
    raise AssertionError("test interpolation point is out of range")


def test_direct_evaluator_executes_persisted_pwl_operation_order() -> None:
    numerator, denominator = _sum_circuits()
    pair = _pair_with_circuits(
        mode="piecewise",
        numerator=numerator,
        denominator=denominator,
    )
    result = evaluate_conditional_mio_pair(
        pair,
        model_coordinate_assignments={"x": 0.5},
    )

    exp_x = tuple(pair.encoding.sum_configuration["exp_x_points"])
    exp_y = tuple(pair.encoding.sum_configuration["exp_y_points"])
    log_x = tuple(pair.encoding.sum_configuration["log_x_points"])
    log_y = tuple(pair.encoding.sum_configuration["log_y_points"])

    def approximate_sum(terms: tuple[float, ...]) -> float:
        maximum = max(terms)
        exponentials = tuple(
            _strict_test_interpolate(term - maximum, exp_x, exp_y)
            for term in terms
        )
        return maximum + _strict_test_interpolate(
            math.fsum(exponentials), log_x, log_y
        )

    expected_numerator = approximate_sum(
        (
            -2.0 + math.log(0.5) + math.log(0.5),
            -3.0 + math.log(0.8) + math.log(0.5),
        )
    )
    expected_denominator = approximate_sum(
        (-1.0 + math.log(0.5), -2.0 + math.log(0.5))
    )
    assert result.numerator_log == pytest.approx(expected_numerator)
    assert result.denominator_log == pytest.approx(expected_denominator)


def test_direct_evaluator_executes_max_rather_than_exact_logsumexp() -> None:
    numerator, denominator = _sum_circuits()
    pair = _pair_with_circuits(
        mode="max",
        numerator=numerator,
        denominator=denominator,
    )

    result = evaluate_conditional_mio_pair(
        pair,
        model_coordinate_assignments={"x": 0.5},
    )

    expected_numerator = max(
        -2.0 + math.log(0.5) + math.log(0.5),
        -3.0 + math.log(0.8) + math.log(0.5),
    )
    assert result.numerator_log == pytest.approx(expected_numerator)
    exact = math.log(
        math.exp(-2.0 + math.log(0.5) + math.log(0.5))
        + math.exp(-3.0 + math.log(0.8) + math.log(0.5))
    )
    assert result.numerator_log != pytest.approx(exact)


def test_direct_evaluator_rejects_pwl_interpolation_outside_persisted_domain() -> None:
    numerator, denominator = _sum_circuits()
    base = _pair_with_circuits(
        mode="piecewise",
        numerator=numerator,
        denominator=denominator,
    )
    payload = base.to_dict()
    payload["pair_id"] = ""
    payload["encoding"]["sum_configuration"].update(
        {
            "exp_domain_floor": -0.1,
            "exp_x_points": [-0.1, 0.0],
            "exp_y_points": [0.9, 1.0],
        }
    )
    narrow = TPMConditionalPair.from_dict(payload)

    with pytest.raises(ValueError, match="outside"):
        evaluate_conditional_mio_pair(
            narrow,
            model_coordinate_assignments={"x": 0.5},
        )


def test_native_evaluator_returns_raw_explicit_event_roots_without_clamping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import torch

    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    pair = compile_conditional_mio_pair(_compilation_request())

    class FakeNativeModel:
        def log_likelihood(self, evidence):
            event_coordinate = evidence[0, 4]
            value = -1.0 if bool(torch.isnan(event_coordinate)) else -0.5
            return torch.tensor([value], dtype=torch.float64)

    monkeypatch.setattr(
        query_module,
        "load_spflow_payload",
        lambda _artifact: {
            "payload_kind": "current-spflow-model-sidecar",
            "backend_generation": "current-spflow",
            "backend_api_version": "1.1.0",
            "query_strategy": "spflow",
            "model": FakeNativeModel(),
        },
    )

    result = evaluate_native_conditional_pair(
        artifact,
        pair,
        declared_domain_assignments={
            "x": 100.0,
            "activation": "on",
            "service_tier": "standard",
        },
    )

    assert result.denominator_log == -1.0
    assert result.numerator_log == -0.5
    assert result.conditional_log_risk == 0.5
    assert result.conditional_probability == pytest.approx(math.exp(0.5))


def test_native_evaluator_rejects_pair_source_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    pair = compile_conditional_mio_pair(_compilation_request())
    mismatched = replace(artifact, artifact_id="different-artifact")

    with pytest.raises(ValueError, match="source provenance"):
        evaluate_native_conditional_pair(
            mismatched,
            pair,
            declared_domain_assignments={
                "x": 100.0,
                "activation": "on",
                "service_tier": "standard",
            },
        )


def test_compiler_reports_missing_spflow_before_loading_a_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    monkeypatch.setattr(
        conditional_mio_module,
        "load_tpm_artifact",
        lambda _source: artifact,
    )

    def missing_backend():
        raise SPFlowDependencyUnavailableError("locked SPFlow dependency is absent")

    monkeypatch.setattr(
        conditional_mio_module, "require_spflow_backend", missing_backend
    )
    monkeypatch.setattr(
        conditional_mio_module,
        "load_spflow_payload",
        lambda _artifact: pytest.fail("sidecar must not be loaded without SPFlow"),
    )

    with pytest.raises(
        SPFlowDependencyUnavailableError, match="SPFlow dependency is absent"
    ):
        compile_conditional_mio_pair(_compilation_request())


def test_native_evaluator_reports_missing_spflow_before_loading_a_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    pair = compile_conditional_mio_pair(_compilation_request())

    def missing_backend():
        raise SPFlowDependencyUnavailableError("locked SPFlow dependency is absent")

    monkeypatch.setattr(query_module, "require_spflow_backend", missing_backend)
    monkeypatch.setattr(
        query_module,
        "load_spflow_payload",
        lambda _artifact: pytest.fail("sidecar must not be loaded without SPFlow"),
    )

    with pytest.raises(
        SPFlowDependencyUnavailableError, match="SPFlow dependency is absent"
    ):
        evaluate_native_conditional_pair(
            artifact,
            pair,
            declared_domain_assignments={
                "x": 100.0,
                "activation": "on",
                "service_tier": "standard",
            },
        )


def test_direct_evaluator_accepts_declared_and_coordinate_mixed_decisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    pair = compile_conditional_mio_pair(_compilation_request())

    declared = evaluate_conditional_mio_pair(
        pair,
        declared_domain_assignments={
            "x": 100.0,
            "activation": "on",
            "service_tier": "priority",
        },
    )
    coordinate = evaluate_conditional_mio_pair(
        pair,
        model_coordinate_assignments={
            "x": 0.5,
            "activation": 1.0,
            "service_tier": 2.0,
        },
    )

    assert declared.numerator_log == pytest.approx(coordinate.numerator_log)
    assert declared.denominator_log == pytest.approx(coordinate.denominator_log)
    assert pair.validity[1].declared_domain["ordering"] == ("off", "on")
    assert pair.validity[2].declared_domain["ordering"] == (
        "economy",
        "standard",
        "priority",
    )


@pytest.mark.parametrize(
    "assignments",
    [
        {"x": 100.0, "activation": "invalid", "service_tier": "economy"},
        {"x": 100.0, "activation": "off", "service_tier": "invalid"},
    ],
)
def test_direct_evaluator_rejects_invalid_declared_discrete_values(
    monkeypatch: pytest.MonkeyPatch,
    assignments: dict[str, object],
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    pair = compile_conditional_mio_pair(_compilation_request())

    with pytest.raises(ValueError, match="domain|declared|value"):
        evaluate_conditional_mio_pair(
            pair, declared_domain_assignments=assignments
        )


@pytest.mark.parametrize(
    "assignments",
    [
        {"x": 0.5, "activation": 0.5, "service_tier": 0.0},
        {"x": 0.5, "activation": 0.0, "service_tier": 3.0},
    ],
)
def test_direct_evaluator_rejects_invalid_discrete_model_indices(
    monkeypatch: pytest.MonkeyPatch,
    assignments: dict[str, object],
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    pair = compile_conditional_mio_pair(_compilation_request())

    with pytest.raises(ValueError, match="ordered-index|ordering|domain|invalid"):
        evaluate_conditional_mio_pair(
            pair, model_coordinate_assignments=assignments
        )


def test_mixed_conditional_pair_contains_symbolic_graph_not_cartesian_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    pair = compile_conditional_mio_pair(_compilation_request())
    serialized = json.dumps(pair.to_dict(), sort_keys=True)

    assert "leaf_binary" in serialized
    assert "leaf_categorical" in serialized
    assert "cartesian" not in serialized.casefold()
    assert "combination" not in serialized.casefold()
    assert "lookup" not in serialized.casefold()
