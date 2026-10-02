"""Native-likelihood parity contracts for the current-SPFlow MIO compiler."""

from __future__ import annotations

import pytest

import tpm.mio as mio_module
from tpm.features import TPMFeatureSpec


PARITY_ABSOLUTE_TOLERANCE = 1e-6
REPEATABILITY_TOLERANCE = 1e-9
CANONICAL_BREAKPOINTS = (0.0, 0.25, 0.5, 0.75, 1.0)
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
NORMALIZED_EVIDENCE = tuple(
    (breakpoint, float(index % 2), float(index % 3))
    for index, breakpoint in enumerate(CANONICAL_BREAKPOINTS)
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


def _native_probabilities(model) -> tuple[float, ...]:
    import torch

    evidence = torch.tensor(NORMALIZED_EVIDENCE, dtype=torch.float64)
    with torch.no_grad():
        likelihood = model.log_likelihood(evidence)
    return tuple(float(value) for value in torch.exp(likelihood).reshape(-1))


def _compiled_probabilities(compiled) -> tuple[float, ...]:
    evaluate = getattr(mio_module, "evaluate_compiled_spflow_probability")
    return tuple(
        float(evaluate(compiled, normalized_evidence=row))
        for row in NORMALIZED_EVIDENCE
    )


def _compile(model):
    compile_model = getattr(mio_module, "compile_spflow_model_to_mio")
    return compile_model(
        model,
        feature_schema=FEATURE_SCHEMA,
        breakpoint_count=5,
    )


def test_five_breakpoint_probability_matches_native_spflow_likelihood() -> None:
    model = _supported_sum_product_graph()
    compiled = _compile(model)

    native = _native_probabilities(model)
    approximate = _compiled_probabilities(compiled)
    maximum_absolute_error = max(
        abs(native_value - approximate_value)
        for native_value, approximate_value in zip(native, approximate, strict=True)
    )

    assert compiled["breakpoint_policy"]["breakpoint_count"] == 5
    assert maximum_absolute_error <= PARITY_ABSOLUTE_TOLERANCE


def test_five_breakpoint_probability_is_repeatable_within_one_e_minus_nine() -> None:
    model = _supported_sum_product_graph()

    first = _compiled_probabilities(_compile(model))
    second = _compiled_probabilities(_compile(model))

    assert second == pytest.approx(
        first,
        abs=REPEATABILITY_TOLERANCE,
        rel=0.0,
    )
