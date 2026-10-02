"""Unit contracts for the supported current-SPFlow-to-piecewise-MIO compiler."""

from __future__ import annotations

import pytest

import tpm.mio as mio_module
from tpm import load_tpm_artifact
from tpm.domains import TPMApproximationDomain
from tpm.features import TPMFeatureSpec


FEATURE_SCHEMA = (
    TPMFeatureSpec(
        feature_name="battery_capacity_kwh",
        feature_type="continuous",
        feature_role="decision",
        modifiable=True,
        bounds=(0.0, 20.0),
    ),
    TPMFeatureSpec(
        feature_name="solar_enabled",
        feature_type="binary",
        feature_role="decision",
        modifiable=True,
        discrete_values=(0, 1),
    ),
    TPMFeatureSpec(
        feature_name="design_class",
        feature_type="categorical",
        feature_role="decision",
        modifiable=True,
        discrete_values=("compact", "balanced", "resilient"),
    ),
)


def _component(*, loc: float, binary_probability: float, category_probabilities):
    import torch
    from spflow.modules.leaves import Bernoulli, Categorical, Normal
    from spflow.modules.products import Product

    return Product(
        [
            Normal(
                0,
                loc=torch.tensor([[[loc]]], dtype=torch.float64),
                scale=torch.tensor([[[0.5]]], dtype=torch.float64),
            ),
            Bernoulli(
                1,
                probs=torch.tensor([[[binary_probability]]], dtype=torch.float64),
            ),
            Categorical(
                2,
                K=3,
                probs=torch.tensor(
                    [[[[*category_probabilities]]]],
                    dtype=torch.float64,
                ),
            ),
        ]
    )


def _supported_sum_product_graph():
    import torch
    from spflow.modules.sums import Sum

    return Sum(
        [
            _component(
                loc=0.25,
                binary_probability=0.2,
                category_probabilities=(0.6, 0.3, 0.1),
            ),
            _component(
                loc=0.75,
                binary_probability=0.8,
                category_probabilities=(0.1, 0.3, 0.6),
            ),
        ],
        weights=torch.tensor([0.4, 0.6], dtype=torch.float64),
    )


def _compile(model, **kwargs):
    compile_model = getattr(mio_module, "compile_spflow_model_to_mio")
    return compile_model(model, feature_schema=FEATURE_SCHEMA, **kwargs)


def _compile_v2(model, *, domains=None, artifact=None, **kwargs):
    fitted = artifact or load_tpm_artifact(
        "tests/fixtures/tpm/tpm_artifact_domains_v3.json"
    )
    compile_model = getattr(mio_module, "compile_spflow_model_to_mio")
    return compile_model(
        model,
        fitted_artifact=fitted,
        approximation_domains=(
            (
                TPMApproximationDomain(
                    feature_name="x",
                    lower=60.0,
                    upper=140.0,
                    source="unit-compiler-contract",
                ),
            )
            if domains is None
            else domains
        ),
        **kwargs,
    )


def test_supported_sum_product_graph_compiles_with_canonical_five_breakpoints() -> None:
    compiled = _compile(_supported_sum_product_graph())

    assert compiled["compiler_version"] == "spflow-v1-mio-v1"
    assert compiled["backend_generation"] == "current-spflow"
    assert compiled["breakpoint_policy"]["breakpoint_count"] == 5
    assert compiled["breakpoint_policy"]["policy_name"] == "canonical-five-breakpoint-v1"
    assert compiled["output_channels"] == 1
    assert compiled["num_repetitions"] == 1

    nodes = compiled["nodes"]
    node_types = {node["type"] for node in nodes}
    assert node_types == {"sum", "product", "normal", "bernoulli", "categorical"}
    assert {tuple(node["scope"]) for node in nodes if node["type"] == "normal"} == {(0,)}
    assert {tuple(node["scope"]) for node in nodes if node["type"] == "bernoulli"} == {(1,)}
    assert {tuple(node["scope"]) for node in nodes if node["type"] == "categorical"} == {
        (2,)
    }


@pytest.mark.parametrize("breakpoint_count", (0, 1, 2, -5))
def test_invalid_breakpoint_counts_are_rejected(breakpoint_count: int) -> None:
    with pytest.raises(ValueError, match=r"breakpoint.*at least|invalid.*breakpoint"):
        _compile(_supported_sum_product_graph(), breakpoint_count=breakpoint_count)


def _arbitrary_torch_module():
    import torch

    return torch.nn.ReLU()


def _custom_leaf():
    import torch
    from spflow.modules.leaves import Normal

    class CustomNormal(Normal):
        pass

    return CustomNormal(
        0,
        loc=torch.tensor([[[0.0]]], dtype=torch.float64),
        scale=torch.tensor([[[1.0]]], dtype=torch.float64),
    )


def _extra_channels():
    from spflow.modules.leaves import Normal

    return Normal(0, out_channels=2)


def _extra_repetitions():
    from spflow.modules.leaves import Normal

    return Normal(0, num_repetitions=2)


def _shared_subgraph():
    import torch
    from spflow.modules.leaves import Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum

    shared = Product([Normal(0, loc=torch.tensor([[[.5]]], dtype=torch.float64),
                             scale=torch.tensor([[[.5]]], dtype=torch.float64))])
    return Sum([shared, shared], weights=torch.tensor([0.5, 0.5]))


def _legacy_histogram():
    import torch
    from spflow.meta.data import Scope
    from spflow.modules.leaves import Histogram

    return Histogram(
        Scope(0),
        bin_edges=torch.tensor([0.0, 0.5, 1.0]),
        probs=torch.tensor([[[[0.5, 0.5]]]]),
    )


@pytest.mark.parametrize(
    ("model_factory", "expected_type", "expected_scope"),
    (
        (_arbitrary_torch_module, "ReLU", None),
        (_custom_leaf, "CustomNormal", (0,)),
        (_extra_channels, "Normal", (0,)),
        (_extra_repetitions, "Normal", (0,)),
        (_legacy_histogram, "Histogram", (0,)),
    ),
)
def test_unsupported_modules_report_type_and_scope(
    model_factory,
    expected_type,
    expected_scope,
) -> None:
    compiler_error = getattr(mio_module, "UnsupportedSPFlowModuleError")

    with pytest.raises(compiler_error) as exc_info:
        _compile(model_factory())

    error = exc_info.value
    assert error.module_type == expected_type
    assert error.scope == expected_scope
    assert expected_type in str(error)
    assert "scope" in str(error).lower()


def test_shared_subgraph_reuses_one_node_and_preserves_native_probability():
    import torch
    model = _shared_subgraph().double()
    compiled = _compile(model)
    assert len(compiled['nodes']) == 3
    assert compiled['nodes'][-1]['children'] == [1, 1]
    rows = torch.tensor([[x, 0., 0.] for x in (0., .25, .5, .75, 1.)], dtype=torch.float64)
    native = model.log_likelihood(rows).exp().detach().reshape(-1).tolist()
    actual = [mio_module.evaluate_compiled_spflow_probability(compiled, normalized_evidence=row.tolist()) for row in rows]
    assert actual == pytest.approx(native, abs=1e-10, rel=1e-10)


def test_cyclic_subgraph_is_rejected_before_recursive_compilation():
    model = _shared_subgraph()
    # Preserve valid cached scope/shape but introduce a back edge in the graph.
    model.inputs.inputs[0] = model
    with pytest.raises(mio_module.UnsupportedSPFlowModuleError, match='cyclic subgraphs'):
        _compile(model)


def test_compiled_v2_persists_physical_and_derived_model_breakpoints() -> None:
    compiled = _compile_v2(_supported_sum_product_graph())

    assert compiled["schema_version"] == "v2"
    assert compiled["compiler_version"] == "spflow-v1-mio-v2"
    assert compiled["fitted_artifact"]["schema_version"] == "v3"
    assert compiled["breakpoint_policy"]["relative_breakpoints"] == [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ]
    validity = compiled["compiled_validity"]
    assert len(validity) == 1
    assert validity[0]["physical_interval"] == [60.0, 140.0]
    assert validity[0]["model_interval"] == pytest.approx([1.0 / 6.0, 5.0 / 6.0])
    assert validity[0]["physical_breakpoints"] == [60.0, 80.0, 100.0, 120.0, 140.0]
    assert validity[0]["model_breakpoints"] == pytest.approx(
        [1.0 / 6.0, 1.0 / 3.0, 0.5, 2.0 / 3.0, 5.0 / 6.0]
    )
    normal_curves = [
        curve
        for node in compiled["nodes"]
        if node["type"] == "normal"
        for curve in node["curves"]
    ]
    assert all(
        curve["breakpoints"] == pytest.approx(validity[0]["model_breakpoints"])
        for curve in normal_curves
    )
    assert all(
        curve["physical_breakpoints"] == validity[0]["physical_breakpoints"]
        for curve in normal_curves
    )


def test_compiled_v2_never_falls_back_when_approximation_domain_is_missing() -> None:
    with pytest.raises(ValueError, match="missing explicit approximation domain.*x"):
        _compile_v2(_supported_sum_product_graph(), domains=())


def test_compiled_v2_rejects_interval_outside_declared_decision_domain() -> None:
    with pytest.raises(ValueError, match="within.*declared decision domain"):
        _compile_v2(
            _supported_sum_product_graph(),
            domains=(
                TPMApproximationDomain(
                    feature_name="x",
                    lower=20.0,
                    upper=140.0,
                    source="invalid-outside-domain",
                ),
            ),
        )


@pytest.mark.parametrize(
    ("feature_name", "message"),
    [
        ("missing", "unknown approximation-domain feature"),
        ("activation", "must be continuous"),
        ("demand", "unused or marginalized"),
    ],
)
def test_compiled_v2_rejects_unknown_discrete_and_unused_requests(
    feature_name: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _compile_v2(
            _supported_sum_product_graph(),
            domains=(
                TPMApproximationDomain(
                    feature_name=feature_name,
                    lower=60.0,
                    upper=140.0,
                    source="invalid-feature-treatment",
                ),
            ),
        )


def test_loaded_v2_fitted_artifact_cannot_be_promoted_by_an_interval() -> None:
    legacy = load_tpm_artifact("tests/fixtures/tpm/tpm_artifact_v2.json")

    with pytest.raises(ValueError, match="schema_version 'v3'.*refit"):
        _compile_v2(_supported_sum_product_graph(), artifact=legacy)
