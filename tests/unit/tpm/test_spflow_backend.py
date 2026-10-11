"""Unit coverage for the required SPFlow 1.1 backend boundary."""

from __future__ import annotations

import pytest

import tpm.spflow_backend as spflow_backend_module
from tpm.spflow_backend import REQUIRED_SPFLOW_VERSION, require_spflow_backend


def test_require_spflow_backend_returns_the_required_installed_version() -> None:
    backend = require_spflow_backend()

    assert backend.__name__ == "spflow"
    assert backend.__version__ == REQUIRED_SPFLOW_VERSION == "1.1.0"


def test_backend_only_stabilization_regularizes_unobserved_categorical_values() -> None:
    import torch
    from spflow.meta.data import Scope
    from spflow.modules.leaves import Categorical

    leaf = Categorical(
        scope=Scope(0),
        K=3,
        probs=torch.tensor([[[[1.0, 0.0, 0.0]]]], dtype=torch.float64),
    )

    spflow_backend_module.stabilize_spflow_leaf_parameters(leaf)
    probabilities = leaf.probs.detach()

    assert bool(torch.isfinite(probabilities).all())
    assert bool((probabilities > 0.0).all())
    assert float(probabilities.sum(dim=-1).reshape(-1)[0]) == pytest.approx(1.0)


@pytest.mark.parametrize("dtype", ["float32", "float64"])
def test_stabilization_keeps_degenerate_bernoulli_logits_finite(dtype) -> None:
    # 1 - 1e-9 rounds to 1 in float32, so the clamp acts on logits.
    import torch
    from spflow.meta.data import Scope
    from spflow.modules.leaves import Bernoulli

    leaf = Bernoulli(scope=Scope([0, 1]), probs=torch.tensor([[[1.0]], [[0.0]]], dtype=getattr(torch, dtype)))

    spflow_backend_module.stabilize_spflow_leaf_parameters(leaf)
    probabilities = leaf.probs.detach().reshape(-1).double()

    assert bool(torch.isfinite(leaf.logits).all())
    assert probabilities.tolist() == pytest.approx([1.0 - 1e-9, 1e-9], rel=1e-6)
