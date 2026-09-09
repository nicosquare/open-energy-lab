"""Small, independent contracts for reusable fixed-product-mixture initialization.

These are synthetic library fixtures, not benchmark streams or campaign seeds.
The NumPy oracle deliberately does not call the implementation under test.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from importlib import import_module
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest


def native_api():
    # A missing required capability is a failure, never an optional-backend skip.
    return import_module("open_energy_lab.tpm.native")


def make_config(api, layout="gaussian", **overrides):
    if layout == "gaussian":
        fields = dict(
            gaussian_indices=(0, 1), bernoulli_indices=(2,),
            target_index=2, conditioning_indices=(0,),
            gaussian_floors=(0.025, 0.05),
        )
    elif layout == "binary":
        fields = dict(
            gaussian_indices=(2,), bernoulli_indices=(0, 1, 3),
            target_index=3, conditioning_indices=(0, 1),
            gaussian_floors=(0.025,),
        )
    else:
        raise AssertionError("unknown test layout")
    fields.update(components=2, coordinate_id=f"fixture-{layout}-v1")
    fields.update(overrides)
    return api.TPMNativeMixtureConfig(**fields)


def fitting_rows(layout="gaussian"):
    index = np.arange(12)
    if layout == "gaussian":
        return np.column_stack((index / 5, ((index * 7) % 13) / 4, index >= 6)).astype(np.float64)
    return np.column_stack((index % 2, (index // 2) % 2, index / 4, index >= 6)).astype(np.float64)


def initialize(api, rows, config, *, seed=17, bounded_work=None):
    return api.initialize_native_mixture(
        rows,
        row_ids=tuple(f"fixture-row-{i}" for i in range(len(rows))),
        config=config,
        seed=seed,
        torch_seed=91,
        device="cpu",
        bounded_work=bounded_work,
    )


def initial_selection(count, components, seed):
    """Reference partial Fisher--Yates with raw-word mask/reject draws."""
    generator = np.random.PCG64(seed)
    pool = list(range(count))
    for i in range(components):
        remaining = count - i
        mask = (1 << (remaining - 1).bit_length()) - 1
        draw = 0
        if remaining > 1:
            while True:
                draw = int(generator.random_raw()) & mask
                if draw < remaining:
                    break
        j = i + draw
        pool[i], pool[j] = pool[j], pool[i]
    return tuple(pool[:components]), generator.state


def initial_indices(count, components, seed):
    return initial_selection(count, components, seed)[0]


def lloyd_oracle(rows, chosen, *, iterations=300, tolerance=1e-6):
    means = rows.mean(axis=0)
    std = np.sqrt(np.mean((rows - means) ** 2, axis=0))
    divisors = np.where(std == 0, 1, std)
    standardized = (rows - means) / divisors
    centers = standardized[list(chosen)].copy()
    history = []
    stop = "iteration_cap"
    for _ in range(iterations):
        labels = ((standardized[:, None, :] - centers) ** 2).sum(axis=2).argmin(axis=1)
        counts = np.bincount(labels, minlength=len(chosen))
        if np.any(counts == 0):
            raise ValueError("empty component during Lloyd assignment")
        updated = np.stack([standardized[labels == k].mean(axis=0) for k in range(len(chosen))])
        displacement = float(np.sum((updated - centers) ** 2))
        history.append(displacement)
        centers = updated
        if displacement <= tolerance:
            stop = "converged"
            break
    labels = ((standardized[:, None, :] - centers) ** 2).sum(axis=2).argmin(axis=1)
    if np.any(np.bincount(labels, minlength=len(chosen)) == 0):
        raise ValueError("empty component in final assignment")
    return means, divisors, labels, tuple(history), stop


def leaves_by_index(model):
    from spflow.modules.leaves import Bernoulli, Normal

    leaves = [node for node in model.modules() if isinstance(node, (Normal, Bernoulli))]
    return {int(leaf.scope.query[0]): leaf for leaf in leaves}


def as_numpy(value):
    return value.detach().cpu().numpy().reshape(-1)


def test_oracle_known_indices_and_final_empty_fixture():
    assert initial_indices(3, 2, 3) == (0, 2)
    assert initial_indices(8, 3, 11) == (6, 5, 1)
    with pytest.raises(ValueError, match="final assignment"):
        lloyd_oracle(final_empty_rows(), (6, 5, 1), iterations=1)


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
def test_initialization_matches_independent_lloyd_and_leaf_moments(layout):
    api = native_api()
    config = make_config(api, layout)
    rows = fitting_rows(layout)
    before = rows.copy()
    chosen = initial_indices(len(rows), config.components, 17)
    means, divisors, labels, history, stop = lloyd_oracle(rows, chosen)
    model, evidence = initialize(api, rows, config)

    from spflow.modules.leaves import Bernoulli, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum
    import torch

    assert isinstance(model, Sum)
    assert isinstance(model.inputs, Product)
    assert model.inputs.out_shape.channels == config.components
    leaves = leaves_by_index(model)
    assert set(leaves) == set(range(rows.shape[1]))
    assert all(parameter.dtype == torch.float64 for parameter in model.parameters())
    np.testing.assert_array_equal(rows, before)
    assert tuple(evidence["initial_row_indices"]) == chosen
    assert tuple(evidence["initial_row_ids"]) == tuple(f"fixture-row-{i}" for i in chosen)
    np.testing.assert_allclose(evidence["temporary_means"], means, atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(evidence["temporary_divisors"], divisors, atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(evidence["displacements"], history, atol=1e-10, rtol=1e-10)
    assert evidence["iterations"] == len(history)
    assert evidence["stop_reason"] == stop
    counts = np.bincount(labels, minlength=config.components)
    np.testing.assert_array_equal(evidence["component_counts"], counts)
    np.testing.assert_allclose(as_numpy(model.weights), counts / len(rows), atol=1e-10, rtol=1e-10)
    for index, leaf in leaves.items():
        if index in config.gaussian_indices:
            assert isinstance(leaf, Normal)
            floor = config.gaussian_floors[config.gaussian_indices.index(index)]
            expected_mean = [rows[labels == k, index].mean() for k in range(config.components)]
            expected_scale = [max(rows[labels == k, index].std(), floor * (1 + 1e-6))
                              for k in range(config.components)]
            np.testing.assert_allclose(as_numpy(leaf.loc), expected_mean, atol=1e-10, rtol=1e-10)
            np.testing.assert_allclose(as_numpy(leaf.scale), expected_scale, atol=1e-10, rtol=1e-10)
        else:
            assert isinstance(leaf, Bernoulli)
            expected = [(rows[labels == k, index].sum() + 0.5) / (counts[k] + 1)
                        for k in range(config.components)]
            np.testing.assert_allclose(as_numpy(leaf.probs), expected, atol=1e-10, rtol=1e-10)


def test_config_is_immutable_and_records_fixed_initialization_defaults():
    config = make_config(native_api())
    assert config.lloyd_max_iterations == 300
    assert config.lloyd_tolerance == 1e-6
    assert config.initialization_chunk_size == 10_000
    with pytest.raises((FrozenInstanceError, AttributeError)):
        config.components = 3


def test_config_round_trip_and_import_do_not_load_training_backends():
    api = native_api()
    config = make_config(api)
    assert api.TPMNativeMixtureConfig.from_dict(json.loads(json.dumps(config.to_dict()))) == config
    with pytest.raises(ValueError):
        api.TPMNativeMixtureConfig.from_dict({**config.to_dict(), "unknown": True})
    code = """
import json, sys
import open_energy_lab.tpm as tpm
for name in ('TPMNativeMixtureConfig', 'initialize_native_mixture',
             'native_joint_conditional_log_values', 'native_full_gradient_step',
             'capture_native_training_state', 'restore_native_training_state',
             'materialize_native_mixture'):
    assert getattr(tpm, name).__module__ == 'open_energy_lab.tpm.native'
print(json.dumps([name for name in ('torch', 'spflow') if name in sys.modules]))
"""
    # The parent environment intentionally retains the old installed dependency until
    # the separate pin update. Test this upstream source tree, like pytest's pythonpath.
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")}
    completed = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True,
                               timeout=30, check=True)
    assert json.loads(completed.stdout) == []


@pytest.mark.parametrize("change", [
    {"gaussian_indices": (0, 0)}, {"bernoulli_indices": (1, 2)},
    {"gaussian_indices": (0, 3)}, {"target_index": 0},
    {"conditioning_indices": (0, 0)}, {"conditioning_indices": (2,)},
    {"conditioning_indices": (5,)}, {"gaussian_floors": (0.1,)},
    {"gaussian_floors": (0, 0.1)}, {"gaussian_floors": (float("nan"), 0.1)},
    {"components": 0}, {"components": True}, {"coordinate_id": ""},
    {"lloyd_max_iterations": 0}, {"lloyd_tolerance": -1},
    {"initialization_chunk_size": 0},
])
def test_invalid_schema_or_initialization_policy_is_rejected(change):
    with pytest.raises(ValueError):
        make_config(native_api(), **change)


def test_constant_columns_and_singletons_keep_finite_unrepaired_parameters():
    api = native_api()
    rows = np.array([[7.0, 0.0, 0.0], [7.0, 2.0, 1.0]])
    model, evidence = initialize(api, rows, make_config(api))
    assert evidence["temporary_divisors"][0] == 1
    assert tuple(evidence["component_counts"]) == (1, 1)
    leaves = leaves_by_index(model)
    assert np.isfinite(as_numpy(leaves[0].scale)).all()
    np.testing.assert_allclose(as_numpy(leaves[0].scale), 0.025 * (1 + 1e-6), rtol=1e-10)
    np.testing.assert_allclose(sorted(as_numpy(leaves[2].probs)), [0.25, 0.75], rtol=1e-10)


def test_equal_distances_choose_lower_component_id():
    api = native_api()
    rows = np.array([[-1.0, 0, 0], [0, 0, 0], [1, 0, 0]])
    _, evidence = initialize(api, rows, make_config(api), seed=3)
    assert tuple(evidence["initial_row_indices"]) == (0, 2)
    assert tuple(evidence["component_counts"]) == (2, 1)


def final_empty_rows():
    return np.array([
        [0, 2, 0], [2, -2, 0], [0, -3, 0], [0, 1, 0],
        [-1, -1, 0], [-3, 2, 0], [2, -3, 0], [1, -3, 0],
    ], dtype=np.float64)


@pytest.mark.parametrize("iterations", [1, 300])
def test_final_or_intermediate_empty_cluster_fails_without_repair(iterations):
    api = native_api()
    config = make_config(api, components=3, lloyd_max_iterations=iterations)
    with pytest.raises(ValueError, match="empty"):
        initialize(api, final_empty_rows(), config, seed=11)


def test_duplicate_values_do_not_trigger_seed_replacement_or_component_reduction():
    api = native_api()
    rows = np.zeros((6, 3), dtype=np.float64)
    with pytest.raises(ValueError, match="empty"):
        initialize(api, rows, make_config(api))


def test_nonempty_iteration_cap_is_recorded_not_rejected():
    api = native_api()
    _, evidence = initialize(api, fitting_rows(), make_config(api, lloyd_max_iterations=1))
    assert evidence["iterations"] == 1
    assert evidence["stop_reason"] == "iteration_cap"


def test_chunking_preserves_seed_choice_clustering_and_parameters():
    api = native_api()
    config = make_config(api)
    first, a = initialize(api, fitting_rows(), config)
    second, b = initialize(api, fitting_rows(), replace(config, initialization_chunk_size=5))
    assert tuple(a["initial_row_indices"]) == tuple(b["initial_row_indices"])
    assert tuple(a["component_counts"]) == tuple(b["component_counts"])
    for x, y in zip(first.parameters(), second.parameters(), strict=True):
        np.testing.assert_allclose(as_numpy(x), as_numpy(y), atol=1e-10, rtol=1e-10)


def test_initializer_uses_local_randomness_and_only_supplied_fitting_rows():
    api = native_api()
    import torch

    fitting = fitting_rows()
    pool = np.vstack((fitting, [[1e6, 1e6, 1]] * 3))
    rows = pool[:len(fitting)]
    numpy_state = np.random.get_state()
    torch_state = torch.random.get_rng_state().clone()
    _, a = initialize(api, rows, make_config(api))
    # The backing array also holds withheld rows; only the supplied view may be read.
    np.testing.assert_allclose(a["temporary_means"], fitting.mean(axis=0), atol=1e-10, rtol=1e-10)
    pool[len(fitting):, :2] = -1e6
    _, b = initialize(api, rows, make_config(api))
    assert tuple(a["initial_row_indices"]) == tuple(b["initial_row_indices"])
    np.testing.assert_array_equal(a["temporary_means"], b["temporary_means"])
    after = np.random.get_state()
    assert after[0] == numpy_state[0] and after[2:] == numpy_state[2:]
    np.testing.assert_array_equal(after[1], numpy_state[1])
    assert torch.equal(torch.random.get_rng_state(), torch_state)


@pytest.mark.parametrize("kind", ["nonbinary", "nonfinite", "wrong_width", "too_few", "duplicate_ids"])
def test_invalid_fitting_inputs_fail_explicitly(kind):
    api = native_api()
    rows = fitting_rows()
    ids = tuple(f"row-{i}" for i in range(len(rows)))
    if kind == "nonbinary":
        rows[0, 2] = 0.25
    elif kind == "nonfinite":
        rows[0, 0] = np.inf
    elif kind == "wrong_width":
        rows = rows[:, :2]
    elif kind == "too_few":
        rows, ids = rows[:1], ids[:1]
    else:
        ids = ("same",) * len(rows)
    with pytest.raises((ValueError, FloatingPointError)):
        api.initialize_native_mixture(rows, row_ids=ids, config=make_config(api), seed=17,
                                      torch_seed=91, device="cpu", bounded_work=None)


@pytest.mark.parametrize("cancel_at", [1, 3])
def test_bounded_work_callback_stops_initialization_without_retry(cancel_at):
    api = native_api()
    calls = []

    def cancel(phase):
        calls.append(phase)
        if len(calls) == cancel_at:
            raise TimeoutError("fixture deadline exhausted")

    with pytest.raises(TimeoutError, match="fixture deadline"):
        initialize(api, fitting_rows(), make_config(api), bounded_work=cancel)
    assert len(calls) == cancel_at
    assert all(isinstance(phase, str) and phase for phase in calls)
