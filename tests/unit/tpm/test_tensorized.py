"""Mixed-leaf tensorized/scalar parity and contraction-gradient regression."""
import copy

import pytest
import torch

from open_energy_lab.tpm.tensorized import enable_linsum_contraction, lower_linsum_einet


@pytest.fixture(autouse=True)
def double_default():
    original = torch.get_default_dtype()
    torch.set_default_dtype(torch.float64)
    yield
    torch.set_default_dtype(original)


def make_model(depth=2, width=3, repetitions=1):
    from spflow.zoo.einet import Einet
    from spflow.modules.leaves import Bernoulli, Categorical, Normal
    torch.manual_seed(17)
    return Einet([
        Categorical([0], out_channels=width, num_repetitions=repetitions, K=3),
        Categorical([1], out_channels=width, num_repetitions=repetitions, K=4),
        Normal([2,3], out_channels=width, num_repetitions=repetitions),
        Bernoulli([4], out_channels=width, num_repetitions=repetitions),
    ], num_classes=1, num_sums=width, num_leaves=width, depth=depth,
       num_repetitions=repetitions, layer_type='linsum', structure='top-down').double()


def evidence():
    rows = torch.tensor([[i%3, i%4, (i-5)/3, (i+1)/7, i%2] for i in range(12)], dtype=torch.float64)
    mixed = rows.clone()
    mixed[::2,2:] = float('nan')
    mixed[1::2,4] = float('nan')
    return torch.cat([rows, mixed, torch.full((1,5), float('nan'), dtype=torch.float64)])


@pytest.mark.parametrize('depth', [1,2])
def test_scalar_lowering_preserves_joint_and_marginal_likelihoods(depth):
    model = make_model(depth)
    scalar = lower_linsum_einet(model)
    rows = evidence()
    torch.testing.assert_close(scalar.log_likelihood(rows), model.log_likelihood(rows), rtol=0, atol=1e-10)
    assert abs(scalar.log_likelihood(rows[-1:]).item()) < 1e-10


def test_contraction_matches_native_parameter_and_input_gradients():
    original = make_model()
    optimized = copy.deepcopy(original)
    assert enable_linsum_contraction(optimized) == 2
    rows = evidence()[:12]
    losses = []
    gradients = []
    for model in (original, optimized):
        values = rows.clone().requires_grad_(True)
        loss = -model.log_likelihood(values).sum()
        loss.backward()
        losses.append(loss)
        gradients.append([p.grad for p in model.parameters()] + [values.grad])
    torch.testing.assert_close(losses[0], losses[1], rtol=0, atol=1e-10)
    for expected, actual in zip(*gradients, strict=True):
        torch.testing.assert_close(expected, actual, rtol=1e-9, atol=1e-10)
    torch.testing.assert_close(original.log_likelihood(evidence()), optimized.log_likelihood(evidence()), rtol=0, atol=1e-10)


def test_lowering_rejects_unsupported_repetitions():
    with pytest.raises(ValueError, match='one repetition'):
        lower_linsum_einet(make_model(repetitions=2))


def test_scalar_export_does_not_recursively_revisit_shared_modules(monkeypatch):
    model = make_model()
    def forbidden(*args, **kwargs):
        raise AssertionError('recursive conversion or train-mode traversal in scalar lowering')
    monkeypatch.setattr(torch.nn.Module,'_apply',forbidden)
    monkeypatch.setattr(torch.nn.Module,'train',forbidden)
    scalar = lower_linsum_einet(model)
    assert all(not module.training for module in scalar.modules())
    assert all(p.dtype == torch.float64 and p.device.type == 'cpu' for p in scalar.parameters())


def test_device_movement_visits_each_shared_module_once(monkeypatch):
    from open_energy_lab.tpm.refinement import _move_modules_once
    model = lower_linsum_einet(make_model())
    before = model.log_likelihood(evidence()).detach()
    visited = []
    original = torch.nn.Module._apply
    def counted(self, fn, recurse=True):
        visited.append(id(self))
        return original(self, fn, recurse=recurse)
    monkeypatch.setattr(torch.nn.Module,'_apply',counted)
    _move_modules_once(model,'cpu')
    assert len(visited) == len(set(visited)) == len(tuple(model.modules()))
    torch.testing.assert_close(before,model.log_likelihood(evidence()),rtol=0,atol=0)


def test_scalar_marginalization_preserves_shared_graph_and_probabilities(monkeypatch):
    from spflow.modules.sums import Sum
    from open_energy_lab.tpm.query import marginalize_spflow_model
    model = lower_linsum_einet(make_model())
    rows = evidence()
    rows[:,2:4] = float('nan')
    expected = model.log_likelihood(rows).detach()
    def forbidden(*args, **kwargs):
        raise AssertionError('scalar DAG used recursive native marginalization')
    monkeypatch.setattr(Sum,'marginalize',forbidden)
    marginal = marginalize_spflow_model(model,(2,3))
    torch.testing.assert_close(marginal.log_likelihood(rows),expected,rtol=0,atol=1e-10)
    assert len(tuple(marginal.modules())) <= len(tuple(model.modules()))
    assert tuple(marginal.scope.query) == (0,1,4)
    from collections import Counter
    references = Counter(id(child) for node in marginal.modules() for child in node.children())
    assert max(references.values()) > 1
    original_ids = {id(p) for p in model.parameters()}
    assert not original_ids.intersection(id(p) for p in marginal.parameters())
    assert marginalize_spflow_model(model,(0,1,2,3,4)) is None


def test_conditioned_compaction_keeps_shared_nodes_once_and_rejects_cycles():
    from open_energy_lab.tpm.mio import _compact_conditioned_graph
    nodes=[dict(id=i,type='constant',value=0.) for i in range(20)]
    nodes.extend(dict(id=20+i,type='product',children=list(range(20))) for i in range(500))
    nodes.append(dict(id=520,type='sum',children=list(range(20,520))))
    root,compacted=_compact_conditioned_graph(520,nodes)
    assert root==520 and len(compacted)==521
    assert all(n['children']==list(range(20)) for n in compacted[20:520])
    with pytest.raises(ValueError,match='acyclic'):
        _compact_conditioned_graph(1,[dict(id=0,children=[1]),dict(id=1,children=[0])])
