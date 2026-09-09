"""Independent density, conditional-loss and full-gradient references.

The equations below are test oracles, not a production likelihood implementation.
Both typed layouts use the same public native API without benchmark dispatch.
"""

from __future__ import annotations

from dataclasses import replace
import math
from types import SimpleNamespace

import numpy as np
import pytest

from tests.unit.tpm.test_native_initialization import (
    as_numpy, fitting_rows, initialize, leaves_by_index, make_config, native_api,
)


@pytest.fixture(autouse=True, scope="module")
def one_cpu_thread():
    import torch

    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def optimizer_for(model):
    import torch

    return torch.optim.Adam(model.parameters(), lr=0.005, betas=(0.9, 0.999), eps=1e-8,
                            weight_decay=0, amsgrad=False, foreach=False, fused=False)


def analytic_log(model, rows, config, indices):
    """Direct normalized mixture formula, differentiable in the actual parameters."""
    import torch
    from torch.nn.functional import logsigmoid

    tensor = torch.as_tensor(rows, dtype=torch.float64)
    terms = torch.log(model.weights.reshape(-1)).expand(len(rows), -1).clone()
    leaves = leaves_by_index(model)
    for index in indices:
        leaf = leaves[index]
        value = tensor[:, index, None]
        if index in config.gaussian_indices:
            loc, scale = leaf.loc.reshape(-1), leaf.scale.reshape(-1)
            terms = terms - 0.5 * ((value - loc) / scale) ** 2 - torch.log(scale) - 0.5 * math.log(2 * math.pi)
        else:
            logits = leaf.logits.reshape(-1)
            terms = terms + value * logsigmoid(logits) + (1 - value) * logsigmoid(-logits)
    return torch.logsumexp(terms, dim=1)


def analytic_values(model, rows, config):
    import torch

    joint = analytic_log(model, rows, config, range(rows.shape[1]))
    zero, one = rows.copy(), rows.copy()
    zero[:, config.target_index], one[:, config.target_index] = 0, 1
    retained = (*config.conditioning_indices, config.target_index)
    log_zero = analytic_log(model, zero, config, retained)
    log_one = analytic_log(model, one, config, retained)
    denominator = torch.logaddexp(log_zero, log_one)
    conditional = torch.where(torch.as_tensor(rows[:, config.target_index]) == 1,
                              log_one, log_zero) - denominator
    return joint, conditional, log_zero - denominator, log_one - denominator


def native_values(api, model, rows, config):
    return api.native_joint_conditional_log_values(model, rows, config=config)


def test_analytic_oracle_matches_hand_calculated_single_component():
    import torch
    from spflow.modules.leaves import Bernoulli, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum

    def parameter(value):
        return torch.full((1, 1, 1), value, dtype=torch.float64)

    model = Sum(inputs=Product([
        Normal(scope=[0], loc=parameter(1), scale=parameter(2)),
        Normal(scope=[1], loc=parameter(4), scale=parameter(3)),
        Bernoulli(scope=[2], probs=parameter(0.25)),
    ]), weights=torch.ones((1, 1, 1, 1), dtype=torch.float64))
    rows = np.array([[1.0, 4.0, 1.0], [3.0, 1.0, 0.0]])
    config = SimpleNamespace(gaussian_indices=(0, 1), target_index=2, conditioning_indices=(0,))
    joint, conditional, zero, one = analytic_values(model, rows, config)
    expected = [math.log(0.25) - math.log(12 * math.pi),
                math.log(0.75) - math.log(12 * math.pi) - 1]
    np.testing.assert_allclose(as_numpy(joint), expected, atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(as_numpy(conditional), np.log([0.25, 0.75]), atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(as_numpy(zero), math.log(0.75), atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(as_numpy(one), math.log(0.25), atol=1e-10, rtol=1e-10)


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_declared_graph_construction_uses_real_typed_leaves_and_owned_parameters(layout):
    import torch
    from spflow.modules.leaves import Bernoulli, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum

    api = native_api()
    config = make_config(api, layout)
    g, b = len(config.gaussian_indices), len(config.bernoulli_indices)
    means = np.arange(2 * g, dtype=np.float64).reshape(2, g)
    scales = np.full((2, g), 0.2)
    probabilities = np.tile([[0.2], [0.7]], (1, b))
    weights = np.array([0.3, 0.7])
    model = api._build_mixture(config, means=means, scales=scales,
                               probabilities=probabilities, weights=weights, device="cpu")
    assert isinstance(model, Sum) and isinstance(model.inputs, Product)
    assert model.inputs.out_shape.channels == 2
    assert list(model.scope.query) == list(range(g + b))
    leaves = leaves_by_index(model)
    assert len(leaves) == g + b
    for index in config.gaussian_indices:
        assert isinstance(leaves[index], Normal)
        assert leaves[index].parametrizations.log_scale.original.numel() == 2
    for index in config.bernoulli_indices:
        assert isinstance(leaves[index], Bernoulli)
    assert all(value.dtype == torch.float64 for value in model.parameters())
    rows = fitting_rows(layout)
    expected = analytic_values(model, rows, config)[0]
    np.testing.assert_allclose(as_numpy(model.log_likelihood(torch.as_tensor(rows))),
                               as_numpy(expected), atol=1e-10, rtol=1e-10)
    before = [parameter.detach().clone() for parameter in model.parameters()]
    means[:] = 900
    scales[:] = 800
    probabilities[:] = 0.01
    weights[:] = 0.5
    assert all(torch.equal(a, b) for a, b in zip(before, model.parameters(), strict=True))


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_joint_and_conditional_logs_match_independent_mixture_equations(layout):
    api = native_api()
    rows, config = fitting_rows(layout), make_config(api, layout)
    model, _ = initialize(api, rows, config)
    expected = analytic_values(model, rows, config)
    actual = native_values(api, model, rows, config)
    for key, value in zip(("joint_log", "conditional_log", "log_probability_zero", "log_probability_one"), expected):
        assert actual[key].shape == (len(rows),)
        assert actual[key].requires_grad
        np.testing.assert_allclose(as_numpy(actual[key]), as_numpy(value), atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(as_numpy(actual["log_probability_zero"].exp() +
                                       actual["log_probability_one"].exp()), 1, atol=1e-10, rtol=1e-10)


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_every_nonconditioning_coordinate_is_marginalized(layout):
    api = native_api()
    config = make_config(api, layout, conditioning_indices=(0,))
    rows = fitting_rows(layout)
    model, _ = initialize(api, rows, config)
    changed = rows.copy()
    for i in range(rows.shape[1]):
        if i not in (*config.conditioning_indices, config.target_index):
            changed[:, i] = 1 - changed[:, i] if i in config.bernoulli_indices else changed[:, i] + 17
    before, after = native_values(api, model, rows, config), native_values(api, model, changed, config)
    np.testing.assert_allclose(as_numpy(before["conditional_log"]), as_numpy(after["conditional_log"]), atol=1e-10, rtol=1e-10)
    assert not np.allclose(as_numpy(before["joint_log"]), as_numpy(after["joint_log"]))
    # An independent SPFlow structural marginalization must agree with NaN evidence.
    marginalized = model.marginalize([i for i in range(rows.shape[1])
                                    if i not in (*config.conditioning_indices, config.target_index)])
    import torch

    zero, one = torch.as_tensor(rows.copy()), torch.as_tensor(rows.copy())
    zero[:, config.target_index], one[:, config.target_index] = 0, 1
    l0 = marginalized.log_likelihood(zero).reshape(-1)
    l1 = marginalized.log_likelihood(one).reshape(-1)
    np.testing.assert_allclose(as_numpy(before["log_probability_one"]),
                               as_numpy(l1 - torch.logaddexp(l0, l1)), atol=1e-10, rtol=1e-10)


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_column_permutation_changes_schema_not_density_or_query(layout):
    api = native_api()
    rows, config = fitting_rows(layout), make_config(api, layout, components=1)
    permutation = tuple(reversed(range(rows.shape[1])))
    remap = {old: new for new, old in enumerate(permutation)}
    other = replace(config, gaussian_indices=tuple(remap[i] for i in config.gaussian_indices),
                    bernoulli_indices=tuple(remap[i] for i in config.bernoulli_indices),
                    target_index=remap[config.target_index],
                    conditioning_indices=tuple(remap[i] for i in config.conditioning_indices),
                    coordinate_id="permuted-fixture-v1")
    first, _ = initialize(api, rows, config)
    second, _ = initialize(api, rows[:, permutation], other)
    a, b = native_values(api, first, rows, config), native_values(api, second, rows[:, permutation], other)
    for key in ("joint_log", "conditional_log", "log_probability_one"):
        np.testing.assert_allclose(as_numpy(a[key]), as_numpy(b[key]), atol=1e-10, rtol=1e-10)


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
@pytest.mark.parametrize("weight", [0.0, 10.0, 20.0])
@pytest.mark.parametrize("sizes", [(12,), (1, 4, 7)])
def test_chunked_full_gradient_and_adam_match_analytic_row_mean(layout, weight, sizes):
    import torch

    api = native_api()
    rows, config = fitting_rows(layout), make_config(api, layout)
    if layout == "binary":
        # Break the exactly stationary mixture-weight symmetry for Adam parity.
        # At zero gradient, eps=1e-8 amplifies ~1e-16 reduction roundoff; the
        # unperturbed fixture retains a separate loss/gradient check below.
        rows[0, 2] += 0.37
    actual, _ = initialize(api, rows, config)
    reference, _ = initialize(api, rows, config)
    optimizer, expected_optimizer = optimizer_for(actual), optimizer_for(reference)
    joint, conditional, _, _ = analytic_values(reference, rows, config)
    loss = -joint.mean() + weight * (-conditional.mean())
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(reference.parameters(), 10, error_if_nonfinite=True)
    expected_optimizer.step()
    chunks, offset = [], 0
    for size in sizes:
        chunks.append(rows[offset:offset + size])
        offset += size
    diagnostics = api.native_full_gradient_step(actual, optimizer, iter(chunks), config=config,
                                               total_rows=len(rows), conditional_weight=weight,
                                               learning_rate=0.005, bounded_work=None)
    assert diagnostics["joint_nll"] == pytest.approx(float(-joint.detach().mean()), abs=1e-10, rel=1e-10)
    assert diagnostics["conditional_nll"] == pytest.approx(float(-conditional.detach().mean()), abs=1e-10, rel=1e-10)
    assert diagnostics["loss"] == pytest.approx(float(loss.detach()), abs=1e-10, rel=1e-10)
    assert diagnostics["gradient_norm"] == pytest.approx(float(norm), abs=1e-10, rel=1e-10)
    for a, b in zip(actual.parameters(), reference.parameters(), strict=True):
        np.testing.assert_allclose(as_numpy(a), as_numpy(b), atol=1e-10, rtol=1e-10)
        if b.grad is not None:
            np.testing.assert_allclose(as_numpy(a.grad), as_numpy(b.grad), atol=1e-10, rtol=1e-10)
    assert all(int(state["step"]) == 1 for state in optimizer.state.values())


@pytest.mark.parametrize("weight", [10.0, 20.0])
def test_stationary_binary_fixture_retains_loss_and_gradient_parity(weight):
    import torch

    api = native_api()
    rows, config = fitting_rows("binary"), make_config(api, "binary")
    actual, _ = initialize(api, rows, config)
    reference, _ = initialize(api, rows, config)
    joint, conditional, _, _ = analytic_values(reference, rows, config)
    loss = -joint.mean() + weight * (-conditional.mean())
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(reference.parameters(), 10, error_if_nonfinite=True)
    result = api.native_full_gradient_step(
        actual, optimizer_for(actual), [rows[:1], rows[1:5], rows[5:]],
        config=config, total_rows=len(rows), conditional_weight=weight, learning_rate=0.005,
    )
    assert result["loss"] == pytest.approx(float(loss.detach()), abs=1e-10, rel=1e-10)
    assert result["gradient_norm"] == pytest.approx(float(norm), abs=1e-10, rel=1e-10)
    for a, b in zip(actual.parameters(), reference.parameters(), strict=True):
        np.testing.assert_allclose(as_numpy(a.grad), as_numpy(b.grad), atol=1e-10, rtol=1e-10)
    assert float(actual.logits.grad.abs().max()) < 1e-14
    assert float(reference.logits.grad.abs().max()) < 1e-14


def test_global_gradient_is_clipped_once_after_all_chunks():
    import torch

    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    optimizer = optimizer_for(model)
    calls = []
    result = api.native_full_gradient_step(model, optimizer, [rows[:5], rows[5:]], config=config,
                                          total_rows=12, conditional_weight=1e6, learning_rate=0.01,
                                          bounded_work=calls.append)
    assert result["gradient_norm"] > 10
    norm = torch.linalg.vector_norm(torch.stack([p.grad.norm() for p in model.parameters() if p.grad is not None]))
    assert float(norm) <= 10 + 1e-10
    assert all(group["lr"] == 0.01 for group in optimizer.param_groups)
    assert len(calls) >= 3  # Checks between chunks and before the single mutation.
    assert all(int(state["step"]) == 1 for state in optimizer.state.values())


def test_width_floor_parameterization_is_trainable_and_respects_roundoff_bound():
    import torch

    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    values = native_values(api, model, rows, config)
    (-values["joint_log"].mean()).backward()
    for index, floor in zip(config.gaussian_indices, config.gaussian_floors):
        leaf = leaves_by_index(model)[index]
        raw = leaf.parametrizations.log_scale.original
        assert raw.numel() == config.components
        assert torch.isfinite(raw).all() and torch.isfinite(raw.grad).all()
        assert torch.any(raw.grad != 0)
        with torch.no_grad():
            before = leaf.scale.clone().reshape(-1)
            raw.reshape(-1)[0] += 0.2
            after = leaf.scale.clone().reshape(-1)
            assert after[0] != before[0]
            assert torch.equal(after[1:], before[1:])
            raw.fill_(-1000)
        for value in as_numpy(leaf.scale):
            assert value >= floor - 8 * math.ulp(floor), (value, floor, value - floor)


def test_extremely_small_bernoulli_probability_has_finite_unclipped_log():
    import torch

    api = native_api()
    config, rows = make_config(api, components=1), fitting_rows()
    model, _ = initialize(api, rows, config)
    with torch.no_grad():
        leaves_by_index(model)[config.target_index].logits.fill_(-1000)
    logs = native_values(api, model, rows, config)
    np.testing.assert_allclose(as_numpy(logs["log_probability_one"]), -1000, atol=1e-10, rtol=1e-10)
    assert torch.isfinite(logs["joint_log"]).all()
    assert torch.isfinite(logs["conditional_log"]).all()


@pytest.mark.parametrize("where", ["parameter", "input", "gradient", "post_step"])
def test_nonfinite_state_is_failure_not_probability_clipping(where, monkeypatch):
    import torch

    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    optimizer = optimizer_for(model)
    parameter = next(model.parameters())
    if where == "parameter":
        with torch.no_grad():
            parameter.fill_(float("nan"))
    elif where == "input":
        rows[0, 0] = np.inf
    elif where == "gradient":
        parameter.register_hook(lambda gradient: torch.full_like(gradient, float("nan")))
    else:
        original = optimizer.step

        def invalid_step(*args, **kwargs):
            original(*args, **kwargs)
            with torch.no_grad():
                parameter.fill_(float("nan"))

        monkeypatch.setattr(optimizer, "step", invalid_step)
    with pytest.raises(FloatingPointError):
        api.native_full_gradient_step(model, optimizer, [rows], config=config, total_rows=12,
                                      conditional_weight=10, learning_rate=0.005, bounded_work=None)


@pytest.mark.parametrize("kind", ["count", "weight", "lr", "cancel", "optimizer"])
def test_invalid_or_cancelled_update_does_not_mutate_parameters(kind):
    import torch

    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    optimizer = optimizer_for(model)
    before = [p.detach().clone() for p in model.parameters()]

    def cancel(_phase):
        raise TimeoutError("test deadline")

    if kind == "optimizer":
        optimizer.param_groups[0]["weight_decay"] = 0.1
    with pytest.raises(TimeoutError if kind == "cancel" else ValueError):
        api.native_full_gradient_step(
            model, optimizer, [rows[:5], rows[5:]], config=config,
            total_rows=13 if kind == "count" else 12,
            conditional_weight=-1 if kind == "weight" else 10,
            learning_rate=-0.01 if kind == "lr" else 0.005,
            bounded_work=cancel if kind == "cancel" else None,
        )
    assert all(torch.equal(a, b) for a, b in zip(before, model.parameters(), strict=True))
    assert not optimizer.state


def test_nonfinite_aggregate_loss_fails_before_adam_mutation(monkeypatch):
    import torch

    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    optimizer = optimizer_for(model)
    before = [p.detach().clone() for p in model.parameters()]

    def extreme_logs(model, data, config):
        # Each weighted chunk loss is finite; their aggregate overflows. Keep
        # gradients finite to isolate the aggregate diagnostic check.
        log_value = model.logits.sum() * 0 - 1e308
        return {"joint_log": log_value.expand(len(data)),
                "conditional_log": log_value.expand(len(data))}

    monkeypatch.setattr(api, "_log_values", extreme_logs)
    with pytest.raises(FloatingPointError):
        api.native_full_gradient_step(model, optimizer, [rows[:1], rows[1:2]],
                                      config=config, total_rows=2,
                                      conditional_weight=2, learning_rate=0.005)
    assert all(torch.equal(a, b) for a, b in zip(before, model.parameters(), strict=True))
    assert not optimizer.state
