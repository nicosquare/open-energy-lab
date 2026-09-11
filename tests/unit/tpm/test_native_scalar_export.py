"""Scalar export preserves the fitted density, storage and native training state."""
import copy

import pytest

from tests.unit.tpm.test_native_initialization import make_config, fitting_rows, leaves_by_index


@pytest.mark.parametrize("layout", ["gaussian", "binary"])
@pytest.mark.parametrize("extreme", [False, True])
def test_scalar_export_preserves_joint_conditional_parameters_and_state(layout, extreme):
    import torch
    import open_energy_lab.tpm as public
    from open_energy_lab.tpm import native
    from spflow.modules.leaves import Bernoulli, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum

    config = make_config(native, layout)
    g, b = len(config.gaussian_indices), len(config.bernoulli_indices)
    model = native._build_mixture(
        config, means=[[0.2] * g, [0.7] * g], scales=[[0.3] * g, [0.5] * g],
        probabilities=[[0.2] * b, [0.8] * b], weights=[0.3, 0.7], device="cpu",
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    rows = torch.as_tensor(fitting_rows(layout), dtype=torch.float64)
    model.log_likelihood(rows).sum().backward()
    optimizer.step()
    if extreme:
        with torch.no_grad():
            model.logits.reshape(-1).copy_(torch.tensor([-1000., 0.]))
            for leaf in leaves_by_index(model).values():
                if isinstance(leaf, Bernoulli):
                    leaf.logits.reshape(-1).copy_(torch.tensor([-1000., 1000.]))
    before = {k: v.clone() for k, v in model.state_dict().items()}
    gradients = [p.grad.clone() for p in model.parameters()]
    optimizer_before = copy.deepcopy(optimizer.state_dict())
    rng = torch.get_rng_state().clone()
    exported = public.export_native_mixture_scalar(model)
    assert torch.equal(rng, torch.get_rng_state())
    assert all(torch.equal(v, model.state_dict()[k]) for k, v in before.items())
    assert all(torch.equal(g, p.grad) for g, p in zip(gradients, model.parameters(), strict=True))
    assert optimizer_before["param_groups"] == optimizer.state_dict()["param_groups"]
    for key, state in optimizer_before["state"].items():
        assert all(torch.equal(v, optimizer.state_dict()["state"][key][name]) for name, v in state.items())
    assert isinstance(exported, Sum)
    products = [node for node in exported.modules() if isinstance(node, Product)]
    assert len(products) == config.components
    assert all(node.out_shape.channels == node.out_shape.repetitions == 1
               for node in exported.modules() if isinstance(node, (Normal, Bernoulli, Product)))
    assert list(exported.scope.query) == list(range(config.feature_count))
    assert torch.equal(exported.logits.reshape(-1), model.logits.reshape(-1))
    source = leaves_by_index(model)
    for component, product in enumerate(products):
        for leaf in product.modules():
            if not isinstance(leaf, (Normal, Bernoulli)):
                continue
            index = int(leaf.scope.query[0])
            for field in (("loc", "log_scale") if isinstance(leaf, Normal) else ("logits",)):
                assert torch.equal(getattr(leaf, field).reshape(-1),
                                   getattr(source[index], field).reshape(-1)[component:component+1])
    for marginalized in ((), tuple(i for i in range(config.feature_count)
                                   if i not in (*config.conditioning_indices, config.target_index)),
                         tuple(i for i in range(config.feature_count) if i not in config.conditioning_indices)):
        evidence = rows.clone()
        evidence[:, list(marginalized)] = torch.nan
        torch.testing.assert_close(exported.log_likelihood(evidence), model.log_likelihood(evidence),
                                   atol=1e-10, rtol=0)
    native_logs = native.native_joint_conditional_log_values(model, rows, config=config)
    numerator = rows.clone()
    numerator[:, [i for i in range(config.feature_count)
                  if i not in (*config.conditioning_indices, config.target_index)]] = torch.nan
    numerator[:, config.target_index] = 1
    denominator = numerator.clone()
    denominator[:, config.target_index] = torch.nan
    conditional = (exported.log_likelihood(numerator) - exported.log_likelihood(denominator)).reshape(-1)
    torch.testing.assert_close(conditional, native_logs["log_probability_one"], atol=1e-10, rtol=0)
    source_storage = {p.data_ptr() for p in model.parameters()} | {p.data_ptr() for p in model.buffers()}
    assert not source_storage & {p.data_ptr() for p in exported.parameters()}
    with torch.no_grad():
        next(exported.parameters()).add_(1)
    assert all(torch.equal(v, model.state_dict()[k]) for k, v in before.items())
