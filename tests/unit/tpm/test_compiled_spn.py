"""The compiled evaluator agrees with SPFlow on learned mixed-type SPNs."""

from __future__ import annotations

import copy
import gc
import random

import numpy as np
import pytest

from tpm import compiled as compiled_module
from tpm import refinement
from tpm.features import TPMFeatureSpec

# Columns: x0-x2 continuous, b0-b2 binary, c0 (3 categories), c1 (4 categories).
SCHEMA = (
    *[TPMFeatureSpec(feature_name=f"x{i}", feature_type="continuous", bounds=(-10.0, 10.0)) for i in range(3)],
    *[TPMFeatureSpec(feature_name=f"b{i}", feature_type="binary", discrete_values=(0, 1)) for i in range(3)],
    TPMFeatureSpec(feature_name="c0", feature_type="categorical", discrete_values=("a", "b", "c")),
    TPMFeatureSpec(feature_name="c1", feature_type="categorical", discrete_values=("p", "q", "r", "s")),
)
BERNOULLI_COLUMNS = (3, 4, 5)


def _rows(count=600):
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(count):
        z = int(rng.integers(0, 3))
        rows.append({
            "x0": rng.normal(z, 0.5), "x1": rng.normal(-z, 1.0), "x2": rng.normal(0.0, 1.0),
            "b0": int(rng.random() < 0.2 + 0.3 * z), "b1": int(rng.random() < 0.5),
            "b2": int(rng.random() < 0.8 - 0.3 * z),
            "c0": "abc"[z if rng.random() < 0.7 else int(rng.integers(0, 3))], "c1": "pqrs"[int(rng.integers(0, 4))],
        })
    return rows


@pytest.fixture(scope="module")
def learned():
    import torch
    from tpm.fit import learn_spflow_structure

    torch.manual_seed(0)
    np.random.seed(0)
    random.seed(0)
    result = learn_spflow_structure(_rows(), feature_schema=SCHEMA, fit_configuration={"min_instances_slice": 60})
    kinds = {type(m).__name__ for m in result.model.modules()}
    assert {"Normal", "Bernoulli", "Categorical", "Product", "Sum"} <= kinds
    return result


@pytest.fixture
def model(learned):
    import torch

    return copy.deepcopy(learned.model).to(torch.float64)


@pytest.fixture
def data(learned):
    import torch

    return learned.training_tensor.to(torch.float64)


def _gradients(model):
    import torch

    return [p.grad.clone() if p.grad is not None else torch.zeros_like(p) for p in model.parameters()]


def _assert_gradients_match(model, compiled, data):
    import torch

    model.zero_grad(set_to_none=True)
    (-model.log_likelihood(data).reshape(-1).mean()).backward()
    expected = _gradients(model)
    model.zero_grad(set_to_none=True)
    (-compiled.log_likelihood(data).mean()).backward()
    for (name, _), a, b in zip(model.named_parameters(), _gradients(model), expected, strict=True):
        torch.testing.assert_close(a, b, atol=1e-12, rtol=1e-10, msg=name)


def test_joint_values_and_gradients_match_spflow(model, data):
    compiled = compiled_module.compile_spn_evaluator(model)
    assert compiled_module.check_compiled_spn_against_spflow(compiled, data) < 1e-12
    _assert_gradients_match(model, compiled, data)


def test_marginal_queries_match_spflow(model, data):
    import torch

    compiled = compiled_module.compile_spn_evaluator(model)
    generator = torch.Generator().manual_seed(3)
    scattered = data.clone()
    scattered[torch.rand(data.shape, generator=generator) < 0.3] = torch.nan
    scattered[:, BERNOULLI_COLUMNS] = data[:, BERNOULLI_COLUMNS]
    continuous_and_categorical = data.clone()
    continuous_and_categorical[::2, [0, 2, 6]] = torch.nan
    continuous_and_categorical[1::3, 7] = torch.nan
    for pattern in (scattered, continuous_and_categorical):
        assert compiled_module.check_compiled_spn_against_spflow(compiled, pattern) < 1e-12
        _assert_gradients_match(model, compiled, pattern)


def test_patterns_whose_spflow_backward_fails_still_evaluate(model, data):
    # SPFlow 1.1 cannot backpropagate through a marginalized Bernoulli column or
    # an all-NaN row (in-place masking); values still match, and the compiled
    # gradient is finite and zero for every marginalized leaf.
    import torch

    compiled = compiled_module.compile_spn_evaluator(model)
    bernoulli = data.clone()
    bernoulli[:, 4] = torch.nan
    empty = torch.full_like(data[:4], torch.nan)
    assert compiled_module.check_compiled_spn_against_spflow(compiled, bernoulli) < 1e-12
    assert compiled_module.check_compiled_spn_against_spflow(compiled, empty) < 1e-12
    torch.testing.assert_close(compiled.log_likelihood(empty), torch.zeros(4, dtype=torch.float64),
                               atol=1e-12, rtol=0)
    model.zero_grad(set_to_none=True)
    (-compiled.log_likelihood(bernoulli).mean()).backward()
    assert all(torch.isfinite(g).all() for g in _gradients(model))
    for leaf in compiled.leaves["bernoulli"]:
        if tuple(leaf.scope.query) == (4,):
            assert not leaf.logits.grad.any()


def test_float32_models_match_spflow(learned):
    import torch

    model = copy.deepcopy(learned.model).to(torch.float32)
    compiled = compiled_module.compile_spn_evaluator(model)
    assert compiled_module.check_compiled_spn_against_spflow(compiled, learned.training_tensor) < 1e-6


def test_gradients_are_bitwise_repeatable(model, data):
    import torch

    compiled = compiled_module.compile_spn_evaluator(model)
    runs = []
    for _ in range(2):
        model.zero_grad(set_to_none=True)
        (-compiled.log_likelihood(data).mean()).backward()
        runs.append(torch.cat([g.reshape(-1) for g in _gradients(model)]))
    assert torch.equal(*runs)


def test_parity_check_rejects_drift(model, data, monkeypatch):
    compiled = compiled_module.compile_spn_evaluator(model)
    original = compiled.log_likelihood
    monkeypatch.setattr(compiled, "log_likelihood", lambda rows: original(rows) + 1e-6)
    with pytest.raises(FloatingPointError, match="differs from SPFlow"):
        compiled_module.check_compiled_spn_against_spflow(compiled, data)


def test_unsupported_modules_are_rejected():
    import torch
    from spflow.modules.leaves import Exponential, Normal
    from spflow.modules.products import Product

    model = Product([Normal(0, loc=torch.zeros(1, 1, 1), scale=torch.ones(1, 1, 1)),
                     Exponential(1, rate=torch.ones(1, 1, 1))])
    with pytest.raises(ValueError, match="Exponential"):
        compiled_module.compile_spn_evaluator(model)


def test_refinement_cache_does_not_keep_models_alive(learned, data):
    import torch

    model = copy.deepcopy(learned.model).to(torch.float64)
    before = len(refinement._COMPILED)
    refinement.refinement_spn_evaluator(model, data)
    assert len(refinement._COMPILED) == before + 1
    del model
    gc.collect()
    assert len(refinement._COMPILED) == before


def test_refinement_with_the_compiled_evaluator_follows_spflow(model, data):
    import torch

    floors = {0: 0.05, 1: 0.05, 2: 0.05}
    # x2 is marginalized in the conditional; b1 and b2 stay observed, since
    # SPFlow cannot backpropagate through a marginalized Bernoulli column.
    query = {"conditioning_indices": (0, 1, 4, 5, 6, 7), "target_index": 3, "conditional_weight": 0.5}
    models = {"compiled": model, "spflow": copy.deepcopy(model)}
    optimizers = {key: torch.optim.Adam(m.parameters(), lr=1e-2) for key, m in models.items()}
    for step in range(5):
        batch = data[step * 100:(step + 1) * 100]
        scores = {key: refinement.refine_spn_step(models[key], optimizers[key], batch, **query,
                                                  gaussian_floors=floors, gradient_clip_norm=10.0,
                                                  evaluator=key)
                  for key in models}
        assert scores["compiled"]["loss"] == pytest.approx(scores["spflow"]["loss"], rel=1e-10)
    for a, b in zip(models["compiled"].parameters(), models["spflow"].parameters(), strict=True):
        torch.testing.assert_close(a, b, atol=1e-9, rtol=1e-9)
    with pytest.raises(ValueError, match="evaluator"):
        refinement.spn_refinement_loss(model, data, **query, evaluator="fast")



def test_auto_evaluator_falls_back_to_spflow_for_unsupported_structures():
    import torch
    from spflow.modules.leaves import Bernoulli, Exponential
    from spflow.modules.products import Product

    model = Product([Bernoulli(0, probs=torch.full((1, 1, 1), 0.3, dtype=torch.float64)),
                     Exponential(1, rate=torch.full((1, 1, 1), 2.0, dtype=torch.float64))])
    rows = torch.tensor([[0.0, 0.5], [1.0, 1.5]], dtype=torch.float64)
    query = {"conditioning_indices": (1,), "target_index": 0}
    auto = refinement.spn_binary_conditional_logs(model, rows, **query)
    spflow = refinement.spn_binary_conditional_logs(model, rows, **query, evaluator="spflow")
    torch.testing.assert_close(auto, spflow, atol=0, rtol=0)
    assert refinement.refinement_spn_evaluator(model, rows) is None
    with pytest.raises(compiled_module.UnsupportedSPNStructureError, match="Exponential"):
        refinement.spn_binary_conditional_logs(model, rows, **query, evaluator="compiled")
