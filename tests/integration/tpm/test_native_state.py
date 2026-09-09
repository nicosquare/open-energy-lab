"""Small real-model continuation/export contracts; no campaign runner or GPU."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from io import BytesIO
import pickle

import numpy as np
import pytest

from tests.unit.tpm.test_native_initialization import (
    as_numpy, fitting_rows, initial_selection, initialize, leaves_by_index, make_config, native_api,
)
from tests.unit.tpm.test_native_math import (
    analytic_values, native_values, one_cpu_thread, optimizer_for,
)


def update(api, model, optimizer, rows, config, *, lr=0.005):
    return api.native_full_gradient_step(model, optimizer, [rows[:5], rows[5:]],
                                        config=config, total_rows=len(rows), conditional_weight=10,
                                        learning_rate=lr, bounded_work=None)


def assert_state_equal(left, right):
    """Exact frozen tensor/container equality, including optimizer and RNG state."""
    import torch

    if isinstance(left, torch.Tensor):
        assert isinstance(right, torch.Tensor)
        assert left.dtype == right.dtype and left.shape == right.shape
        assert torch.equal(left.cpu(), right.cpu())
    elif isinstance(left, dict):
        assert isinstance(right, dict) and left.keys() == right.keys()
        for key in left:
            assert_state_equal(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        assert type(left) is type(right) and len(left) == len(right)
        for a, b in zip(left, right, strict=True):
            assert_state_equal(a, b)
    else:
        assert left == right


def assert_no_live_modules(value):
    import torch

    assert not isinstance(value, torch.nn.Module)
    if isinstance(value, dict):
        for item in value.values():
            assert_no_live_modules(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            assert_no_live_modules(item)
    elif isinstance(value, torch.Tensor):
        assert not value.requires_grad


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_serialized_state_restores_parameters_adam_rng_and_next_update(layout, monkeypatch):
    import torch

    api = native_api()
    config, rows = make_config(api, layout), fitting_rows(layout)
    model, _ = initialize(api, rows, config)
    optimizer = optimizer_for(model)
    update(api, model, optimizer, rows, config)
    state = api.capture_native_training_state(model, optimizer, config=config)
    snapshot = deepcopy(state)
    assert_no_live_modules(state)
    assert {"config", "model_state", "optimizer_state", "rng_state"} <= state.keys()
    assert not {"time_budget", "elapsed_seconds", "remaining_updates", "campaign_id"} & state.keys()
    assert {"numpy", "torch"} <= state["rng_state"].keys()
    assert_state_equal(state["rng_state"]["numpy"], initial_selection(len(rows), config.components, 17)[1])
    assert torch.equal(state["rng_state"]["torch"], torch.Generator(device="cpu").manual_seed(91).get_state())

    serialized = BytesIO()
    torch.save(state, serialized)
    serialized.seek(0)
    loaded = torch.load(serialized, map_location="cpu", weights_only=True)
    assert_state_equal(state, loaded)

    def no_reinitialization(*_args, **_kwargs):
        raise AssertionError("restore must reconstruct parameters, not rerun clustering")

    monkeypatch.setattr(api, "initialize_native_mixture", no_reinitialization)
    resumed, resumed_optimizer = api.restore_native_training_state(loaded, config=config, device="cpu")
    restored = api.capture_native_training_state(resumed, resumed_optimizer, config=config)
    assert_state_equal(state, restored)
    for index in config.gaussian_indices:
        assert hasattr(leaves_by_index(resumed)[index], "parametrizations")
    for key in ("joint_log", "conditional_log", "log_probability_one"):
        a = native_values(api, model, rows, config)[key]
        b = native_values(api, resumed, rows, config)[key]
        np.testing.assert_allclose(as_numpy(a), as_numpy(b), atol=1e-10, rtol=1e-10)

    # Both continue with the next caller-supplied cosine rate, not an initial-rate reset.
    result_a = update(api, model, optimizer, rows, config, lr=0.004)
    result_b = update(api, resumed, resumed_optimizer, rows, config, lr=0.004)
    assert result_a["loss"] == pytest.approx(result_b["loss"], abs=1e-10, rel=1e-10)
    for a, b in zip(model.parameters(), resumed.parameters(), strict=True):
        np.testing.assert_allclose(as_numpy(a), as_numpy(b), atol=1e-10, rtol=1e-10)
    assert all(int(item["step"]) == 2 for item in resumed_optimizer.state.values())
    assert all(group["lr"] == 0.004 for group in resumed_optimizer.param_groups)
    assert_state_equal(state, snapshot)  # Captured tensors/state never alias the live model.
    assert_state_equal(loaded, snapshot)  # Restoration must not mutate the persisted payload.

    # Recorded local RNG states genuinely reconstruct the same next random values.
    first_rng, second_rng = np.random.PCG64(), np.random.PCG64()
    first_rng.state, second_rng.state = state["rng_state"]["numpy"], restored["rng_state"]["numpy"]
    np.testing.assert_array_equal(first_rng.random_raw(7), second_rng.random_raw(7))
    first_torch, second_torch = torch.Generator(device="cpu"), torch.Generator(device="cpu")
    first_torch.set_state(state["rng_state"]["torch"])
    second_torch.set_state(restored["rng_state"]["torch"])
    assert torch.equal(torch.rand(7, generator=first_torch), torch.rand(7, generator=second_torch))


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_untrained_state_can_resume_without_an_adam_step(layout):
    api = native_api()
    config, rows = make_config(api, layout), fitting_rows(layout)
    model, _ = initialize(api, rows, config)
    state = api.capture_native_training_state(model, optimizer_for(model), config=config)
    resumed, optimizer = api.restore_native_training_state(state, config=config, device="cpu")
    assert not optimizer.state
    update(api, resumed, optimizer, rows, config)
    assert all(int(item["step"]) == 1 for item in optimizer.state.values())


@pytest.mark.parametrize("field", ["components", "coordinates", "floors", "query", "types"])
def test_state_cannot_be_restored_under_another_model_contract(field):
    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    state = api.capture_native_training_state(model, optimizer_for(model), config=config)
    changes = {
        "components": {"components": 3},
        "coordinates": {"coordinate_id": "another-transform-v1"},
        "floors": {"gaussian_floors": (0.01, 0.02)},
        "query": {"conditioning_indices": (1,)},
        "types": {"gaussian_indices": (0,), "bernoulli_indices": (1, 2), "gaussian_floors": (0.025,)},
    }
    with pytest.raises(ValueError):
        api.restore_native_training_state(state, config=replace(config, **changes[field]), device="cpu")


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_plain_spflow_export_reload_preserves_density_and_conditional_logs(layout):
    import torch
    from spflow.modules.sums import Sum
    from torch.nn.utils.parametrize import is_parametrized

    api = native_api()
    config, rows = make_config(api, layout), fitting_rows(layout)
    model, _ = initialize(api, rows, config)
    update(api, model, optimizer_for(model), rows, config)
    expected = native_values(api, model, rows, config)
    original = [p.detach().clone() for p in model.parameters()]
    exported = api.materialize_native_mixture(model)
    assert isinstance(exported, Sum) and exported is not model
    assert all(not is_parametrized(node) for node in exported.modules())
    # Only this plain graph is pickled; the locally generated test bytes are trusted.
    reloaded = pickle.loads(pickle.dumps(exported))
    actual = analytic_values(reloaded, rows, config)
    graph_joint = reloaded.log_likelihood(torch.as_tensor(rows)).reshape(-1)
    np.testing.assert_allclose(as_numpy(graph_joint), as_numpy(expected["joint_log"]), atol=1e-10, rtol=1e-10)
    for key, value in zip(("joint_log", "conditional_log", "log_probability_zero", "log_probability_one"), actual):
        np.testing.assert_allclose(as_numpy(value), as_numpy(expected[key]), atol=1e-10, rtol=1e-10)
    with torch.no_grad():
        for parameter in exported.parameters():
            parameter.add_(0.1)
    assert all(torch.equal(a, b) for a, b in zip(original, model.parameters(), strict=True))
    with pytest.raises(ValueError):
        api.restore_native_training_state(reloaded, config=config, device="cpu")


@pytest.mark.parametrize("corruption", ["missing_model", "nonfinite_model", "missing_rng", "wrong_kind",
                                       "floor", "shape", "dtype", "rng_backend", "rng_bytes"])
def test_corrupt_or_incomplete_native_state_is_rejected(corruption):
    import torch

    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    state = deepcopy(api.capture_native_training_state(model, optimizer_for(model), config=config))
    if corruption == "missing_model":
        del state["model_state"]
    elif corruption == "nonfinite_model":
        next(iter(state["model_state"].values())).fill_(float("nan"))
    elif corruption == "missing_rng":
        del state["rng_state"]
    elif corruption == "wrong_kind":
        state["kind"] = "plain-inference-export"
    elif corruption == "floor":
        key = next(key for key in state["model_state"] if key.endswith(".floor"))
        state["model_state"][key].mul_(0.5)
    elif corruption in ("shape", "dtype"):
        key = next(iter(state["model_state"]))
        value = state["model_state"][key]
        state["model_state"][key] = value.flatten() if corruption == "shape" else value.float()
    elif corruption == "rng_backend":
        state["rng_state"]["torch_device_type"] = "cuda"
    else:
        state["rng_state"]["torch"] = torch.zeros(3, dtype=torch.uint8)
    with pytest.raises((ValueError, FloatingPointError)):
        api.restore_native_training_state(state, config=config, device="cpu")


@pytest.mark.parametrize("corruption", ["missing_moment", "moment_shape", "negative_square", "step", "settings"])
def test_corrupt_adam_state_is_rejected_before_continuation(corruption):
    api = native_api()
    config, rows = make_config(api), fitting_rows()
    model, _ = initialize(api, rows, config)
    optimizer = optimizer_for(model)
    update(api, model, optimizer, rows, config)
    state = api.capture_native_training_state(model, optimizer, config=config)
    moment = next(iter(state["optimizer_state"]["state"].values()))
    if corruption == "missing_moment":
        del moment["exp_avg"]
    elif corruption == "moment_shape":
        moment["exp_avg"] = moment["exp_avg"].flatten()
    elif corruption == "negative_square":
        moment["exp_avg_sq"].fill_(-1)
    elif corruption == "step":
        moment["step"].fill_(0.5)
    else:
        state["optimizer_state"]["param_groups"][0]["eps"] = 1e-7
    with pytest.raises(ValueError):
        api.restore_native_training_state(state, config=config, device="cpu")


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_plain_export_preserves_extreme_logits_without_probability_roundtrips(layout):
    import torch

    api = native_api()
    config, rows = make_config(api, layout), fitting_rows(layout)
    model, _ = initialize(api, rows, config)
    with torch.no_grad():
        model.logits.reshape(-1).copy_(torch.tensor([-1000.0, 0.0]))
        for index in config.bernoulli_indices:
            leaves_by_index(model)[index].logits.reshape(-1).copy_(torch.tensor([-1000.0, 1000.0]))
    expected = native_values(api, model, rows, config)
    exported = pickle.loads(pickle.dumps(api.materialize_native_mixture(model)))
    assert torch.equal(exported.logits, model.logits)
    for index in config.bernoulli_indices:
        assert torch.equal(leaves_by_index(exported)[index].logits, leaves_by_index(model)[index].logits)
    np.testing.assert_allclose(as_numpy(exported.log_likelihood(torch.as_tensor(rows))),
                               as_numpy(expected["joint_log"]), atol=1e-10, rtol=1e-10)
    zero = torch.full_like(torch.as_tensor(rows), torch.nan)
    zero[:, list(config.conditioning_indices)] = torch.as_tensor(rows[:, list(config.conditioning_indices)])
    zero[:, config.target_index] = 0
    one = zero.clone()
    one[:, config.target_index] = 1
    l0, l1 = exported.log_likelihood(zero).reshape(-1), exported.log_likelihood(one).reshape(-1)
    np.testing.assert_allclose(as_numpy(l1 - torch.logaddexp(l0, l1)),
                               as_numpy(expected["log_probability_one"]), atol=1e-10, rtol=1e-10)
