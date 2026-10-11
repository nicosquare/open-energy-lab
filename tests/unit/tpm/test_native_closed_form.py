"""The closed-form mixture likelihood agrees with SPFlow on the same model."""

from __future__ import annotations

import numpy as np
import pytest

from tpm import native

# Non-trivial column order: Gaussian columns 0 and 4, Bernoulli 1, 2, 3, 5;
# the conditional target is column 2.
CONFIG = native.TPMNativeMixtureConfig(
    components=5, gaussian_indices=(0, 4), bernoulli_indices=(1, 2, 3, 5),
    target_index=2, conditioning_indices=(1, 3, 5), gaussian_floors=(0.05, 0.1),
    coordinate_id="closed-form-test",
)


def _model():
    rng = np.random.default_rng(21)
    weights = rng.uniform(0.5, 1.5, 5)
    return native.build_native_mixture(
        CONFIG, means=rng.normal(size=(5, 2)), scales=rng.uniform(0.3, 2.0, (5, 2)),
        probabilities=rng.uniform(0.1, 0.9, (5, 4)), weights=weights / weights.sum(),
        device="cpu",
    )


def _rows(count=32):
    rng = np.random.default_rng(5)
    rows = rng.normal(size=(count, 6))
    rows[:, [1, 2, 3, 5]] = rng.integers(0, 2, (count, 4))
    return rows


def test_joint_and_marginal_log_likelihood_match_spflow():
    import torch

    model, rows = _model(), torch.tensor(_rows())
    fast = native.native_mixture_log_likelihood(model, rows, config=CONFIG)
    torch.testing.assert_close(fast, model.log_likelihood(rows).reshape(-1), atol=1e-12, rtol=0)
    marginal = rows.clone()
    marginal[:, [0, 2, 4]] = torch.nan
    marginal[::3, 1] = torch.nan
    fast = native.native_mixture_log_likelihood(model, marginal, config=CONFIG)
    torch.testing.assert_close(fast, model.log_likelihood(marginal).reshape(-1), atol=1e-12, rtol=0)


def test_gradients_match_spflow_for_every_parameter():
    import torch

    rows = torch.tensor(_rows())
    fast_model, spflow_model = _model(), _model()
    (-native.native_mixture_log_likelihood(fast_model, rows, config=CONFIG).mean()).backward()
    (-spflow_model.log_likelihood(rows).reshape(-1).mean()).backward()
    for (name, a), b in zip(fast_model.named_parameters(), spflow_model.parameters(), strict=True):
        torch.testing.assert_close(a.grad, b.grad, atol=1e-12, rtol=0, msg=name)


def test_conditionals_match_spflow_for_both_event_values():
    import torch

    model, rows = _model(), torch.tensor(_rows())
    values = native.native_joint_conditional_log_values(model, rows, config=CONFIG)
    evidence = torch.full_like(rows, torch.nan)
    evidence[:, [1, 3, 5]] = rows[:, [1, 3, 5]]
    with torch.no_grad():
        denominator = model.log_likelihood(evidence).reshape(-1)
        for event, key in ((0, "log_probability_zero"), (1, "log_probability_one")):
            evidence[:, 2] = event
            expected = model.log_likelihood(evidence).reshape(-1) - denominator
            torch.testing.assert_close(values[key], expected, atol=1e-12, rtol=0)


def test_parity_check_reports_agreement_and_rejects_drift(monkeypatch):
    model, rows = _model(), _rows()
    assert native.check_native_mixture_against_spflow(model, rows, config=CONFIG) < 1e-12
    original = native._closed_form_log_likelihood
    monkeypatch.setattr(native, "_closed_form_log_likelihood",
                        lambda *args: original(*args) + 1e-6)
    with pytest.raises(FloatingPointError, match="differs from SPFlow"):
        native.check_native_mixture_against_spflow(model, rows, config=CONFIG)


def test_parameter_export_follows_declared_column_order():
    import torch

    model = _model()
    exported = native.native_mixture_parameters(model, config=CONFIG)
    assert {key: tuple(value.shape) for key, value in exported.items()} == {
        "mixture_logits": (5,), "bernoulli_logits": (5, 4),
        "gaussian_location": (5, 2), "gaussian_log_scale": (5, 2),
    }
    assert all(not value.requires_grad for value in exported.values())
    leaves = native._leaves_by_index(model)
    torch.testing.assert_close(exported["bernoulli_logits"][:, 1], leaves[2].logits.detach().reshape(-1))
    torch.testing.assert_close(exported["gaussian_log_scale"][:, 1],
                               leaves[4].log_scale.detach().reshape(-1))


def test_chunked_gradients_sum_to_the_full_batch_gradient():
    import torch

    rows = torch.tensor(_rows(30))
    full, chunked = _model(), _model()
    (-native.native_mixture_log_likelihood(full, rows, config=CONFIG).mean()).backward()
    for part in rows.split(7):
        (-native.native_mixture_log_likelihood(chunked, part, config=CONFIG).sum() / len(rows)).backward()
    for a, b in zip(full.parameters(), chunked.parameters(), strict=True):
        torch.testing.assert_close(a.grad, b.grad, atol=1e-12, rtol=0)


def test_saturated_bernoulli_logits_keep_their_exponential_tail():
    # torch's softplus returns l for l > 20, dropping e^-l (about 1e-9 here).
    import torch

    model, rows = _model(), torch.tensor(_rows())
    leaves = native._leaves_by_index(model)
    with torch.no_grad():
        leaves[1].logits.fill_(20.5)
        leaves[3].logits.fill_(-21.0)
    fast = native.native_mixture_log_likelihood(model, rows, config=CONFIG)
    torch.testing.assert_close(fast, model.log_likelihood(rows).reshape(-1), atol=1e-12, rtol=0)
