"""Tiny learned-SPN math and safe interrupted-refinement fixtures."""
from pathlib import Path
import copy
import math
import time

import pytest


def schema():
    from tpm.artifact import load_tpm_artifact
    path = Path(__file__).resolve().parents[2] / 'fixtures/tpm/tpm_artifact_domains_v3.json'
    specs = load_tpm_artifact(path).feature_specs
    return (specs[0], specs[3], specs[4])


def model_and_rows():
    import torch
    from spflow.modules.leaves import Normal, Bernoulli
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum

    def t(value): return torch.tensor([[[value]]], dtype=torch.float64)
    def component(mean, probability):
        return Product([Normal(0, loc=t(mean), scale=t(.3)),
                        Normal(1, loc=t(mean + .1), scale=t(.4)),
                        Bernoulli(2, probs=t(probability))])
    model = Sum([component(.2, .1), component(.8, .9)], weights=torch.tensor([.4, .6], dtype=torch.float64))
    rows = torch.tensor([[.1, .3, 0], [.8, 1.2, 1], [.4, .7, 1], [.6, .1, 0]], dtype=torch.float64)
    return model, rows


def progress(**changes):
    return dict(epoch=0, row_position=4, epoch_rows=12, permutation_seed=719,
                updates=1, consumed_rows=4, elapsed_seconds=.5,
                best_metrics={'boundary_mae': .02}, last_improvement_epoch=1/3,
                **changes)


def step(model, optimizer, rows):
    from tpm.refinement import refine_spn_step
    return refine_spn_step(model, optimizer, rows, conditioning_indices=(0,), target_index=2,
                           conditional_weight=10., gaussian_floors={0: .025, 1: .05}, gradient_clip_norm=10.)


def test_joint_conditional_loss_matches_independent_mixture_formula_and_gradients():
    import torch
    from tpm.refinement import spn_refinement_loss
    model, rows = model_and_rows()
    loss, scores = spn_refinement_loss(model, rows, conditioning_indices=(0,), target_index=2, conditional_weight=10.)
    logweights = torch.log(torch.tensor([.4, .6], dtype=torch.float64))
    x = torch.stack([torch.distributions.Normal(m, .3).log_prob(rows[:, 0]) for m in (.2, .8)], 1)
    d = torch.stack([torch.distributions.Normal(m, .4).log_prob(rows[:, 1]) for m in (.3, .9)], 1)
    y = torch.stack([torch.distributions.Bernoulli(p).log_prob(rows[:, 2]) for p in (.1, .9)], 1)
    joint = -torch.logsumexp(logweights + x + d + y, 1).mean()
    conditional = -(torch.logsumexp(logweights + x + y, 1) - torch.logsumexp(logweights + x, 1)).mean()
    assert scores['joint_nll'] == pytest.approx(float(joint), abs=1e-6)
    assert scores['conditional_nll'] == pytest.approx(float(conditional), abs=1e-6)
    assert float(loss.detach()) == pytest.approx(float(joint + 10 * conditional), abs=1e-6)
    loss.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    assert any(p.grad.abs().max() > 0 for p in model.parameters())


def test_width_projection_uses_explicit_feature_indices():
    import torch
    from spflow.modules.leaves import Normal
    from tpm.refinement import project_spn_gaussian_widths
    model, _ = model_and_rows()
    project_spn_gaussian_widths(model, {0: .5, 1: .7})
    for leaf in model.modules():
        if isinstance(leaf, Normal):
            assert leaf.scale.item() == pytest.approx({0: .5, 1: .7}[leaf.scope.query[0]])
    for floors in ({0: .1}, {0: .1, 1: 0}, {0: .1, 1: float('nan')}, {0: .1, 1: .2, 2: .3}):
        with pytest.raises(ValueError): project_spn_gaussian_widths(model, floors)


def test_export_reload_preserves_shared_subgraphs(tmp_path):
    import torch
    from spflow.modules.sums import Sum
    from tpm.refinement import save_supported_spn_model
    from tpm.optional_spflow import load_supported_spflow_checkpoint
    branch, rows = model_and_rows()
    model = Sum([branch,branch],weights=torch.tensor([.3,.7],dtype=torch.float64))
    expected = model.log_likelihood(rows).detach()
    path,_ = save_supported_spn_model(tmp_path/'shared.pt',model=model,feature_schema=schema())
    restored = load_supported_spflow_checkpoint(path)['model']
    assert restored.inputs.inputs[0] is restored.inputs.inputs[1]
    assert len(tuple(restored.modules())) == len(tuple(model.modules()))
    torch.testing.assert_close(restored.log_likelihood(rows),expected,rtol=0,atol=0)


def test_safe_cpu_checkpoint_resume_preserves_optimizer_cursor_and_next_update(tmp_path):
    import torch
    from tpm.refinement import save_spn_refinement_state, load_spn_refinement_state
    model, rows = model_and_rows()
    optimizer = torch.optim.Adam(model.parameters(), lr=.01, foreach=False)
    step(model, optimizer, rows)
    best = {k: v.detach().clone() for k, v in model.state_dict().items()}
    before = copy.deepcopy(model.state_dict())
    path = tmp_path / 'latest.pt'
    save_spn_refinement_state(path, model=model, optimizer=optimizer, feature_schema=schema(),
                              progress=progress(), best_state=best, context={'run_id': 'fixture', 'backend': 'cpu'})
    assert all(torch.equal(v, model.state_dict()[k]) for k, v in before.items())
    expected_rng = torch.rand(3)
    restored = load_spn_refinement_state(path, expected_feature_schema=schema(),
                                        expected_context={'run_id': 'fixture', 'backend': 'cpu'}, device='cpu')
    assert torch.equal(torch.rand(3), expected_rng)
    assert restored['progress'] == progress()
    seed = restored['progress']['permutation_seed']
    original_order = torch.randperm(12, generator=torch.Generator().manual_seed(seed))
    resumed_order = torch.randperm(12, generator=torch.Generator().manual_seed(seed))
    assert torch.equal(original_order[4:], resumed_order[restored['progress']['row_position']:])
    assert all(torch.equal(v, restored['best_state'][k]) for k, v in best.items())
    step(model, optimizer, rows)
    step(restored['model'], restored['optimizer'], rows)
    for k, v in model.state_dict().items(): torch.testing.assert_close(v, restored['model'].state_dict()[k], atol=0, rtol=0)
    with pytest.raises(ValueError, match='context'):
        load_spn_refinement_state(path, expected_feature_schema=schema(), expected_context={'run_id': 'other'}, device='cpu')


def test_checkpoint_rejects_unknown_classes_and_malformed_state(tmp_path):
    import torch
    from tpm.refinement import save_spn_refinement_state, load_spn_refinement_state
    path = tmp_path / 'unsafe.pt'
    torch.save({'model': torch.nn.Linear(3, 1)}, path)
    with torch.serialization.safe_globals([torch.nn.Linear]):
        before = set(torch.serialization.get_safe_globals())
        with pytest.raises(ValueError, match='restricted'):
            load_spn_refinement_state(path, expected_feature_schema=schema(), expected_context={}, device='cpu')
        assert set(torch.serialization.get_safe_globals()) == before
    model, rows = model_and_rows()
    optimizer = torch.optim.Adam(model.parameters())
    step(model, optimizer, rows)
    with pytest.raises(ValueError, match='cursor'):
        save_spn_refinement_state(path, model=model, optimizer=optimizer, feature_schema=schema(),
            progress={**progress(), 'row_position': 13}, best_state=None, context={})
    with pytest.raises(ValueError, match='cursor'):
        save_spn_refinement_state(path, model=model, optimizer=optimizer, feature_schema=schema(),
            progress={**progress(), 'updates': 0}, best_state=None, context={})
    next(iter(optimizer.state.values()))['exp_avg'] = torch.ones(23)
    with pytest.raises(ValueError, match='optimizer'):
        save_spn_refinement_state(path, model=model, optimizer=optimizer, feature_schema=schema(),
            progress=progress(), best_state=None, context={})


def test_supported_model_validation_rejects_missing_scope_and_nonfinite_parameters():
    import torch
    from tpm.refinement import validate_refinement_spn
    model, _ = model_and_rows()
    result = validate_refinement_spn(model, feature_count=3)
    assert abs(result['all_marginalized_log_mass']) <= 1e-8
    with pytest.raises(ValueError, match='scope'): validate_refinement_spn(model, feature_count=4)
    with torch.no_grad(): next(model.parameters()).fill_(float('nan'))
    with pytest.raises(ValueError, match='finite'): validate_refinement_spn(model, feature_count=3)


def test_bounded_prometheus_uses_typed_schema_and_reports_missing_label(tmp_path):
    import torch
    from tpm.fit import learn_bounded_prometheus
    from tpm import save_spn_refinement_state, load_spn_refinement_state
    generator = torch.Generator().manual_seed(11)
    rows = torch.rand((48, 3), generator=generator, dtype=torch.float64)
    rows[:, 2] = 0
    model, evidence = learn_bounded_prometheus(rows, feature_schema=schema(),
        settings={'min_features_slice': 8, 'min_instances_slice': 24, 'out_channels': 1,
                  'n_clusters': 2, 'similarity': 'corr', 'affinity_mode': 'full'},
        gaussian_floors={0: .025, 1: .05}, seed=0, maximum_seconds=20,
        maximum_modules=100, maximum_scalar_outputs=200)
    assert evidence['observed_discrete_values'][schema()[2].feature_name] == [0]
    assert evidence['incomplete_discrete_support'] is True
    assert abs(evidence['all_marginalized_log_mass']) <= 1e-8
    optimizer = torch.optim.Adam(model.parameters(), lr=.01)
    step(model, optimizer, rows)
    save_spn_refinement_state(tmp_path / 'learned.pt', model=model, optimizer=optimizer,
        feature_schema=schema(), progress={**progress(), 'epoch_rows': 48, 'row_position': 48, 'consumed_rows': 48},
        best_state=None, context={'learned': True})
    restored = load_spn_refinement_state(tmp_path / 'learned.pt', expected_feature_schema=schema(),
                                        expected_context={'learned': True})
    assert restored['progress']['consumed_rows'] == 48


def test_conditional_queries_reject_continuous_target_and_ignore_uncertainty_values():
    import torch
    from tpm import spn_binary_conditional_logs
    model, rows = model_and_rows()
    before = spn_binary_conditional_logs(model, rows, conditioning_indices=(0,), target_index=2)
    rows[:, 1] = 1e6
    after = spn_binary_conditional_logs(model, rows, conditioning_indices=(0,), target_index=2)
    torch.testing.assert_close(before, after, atol=0, rtol=0)
    with pytest.raises(ValueError, match='Bernoulli'):
        spn_binary_conditional_logs(model, rows, conditioning_indices=(0,), target_index=1)


def test_structure_size_and_work_exhaustion_have_no_fallback(monkeypatch):
    import spflow.learn
    from tpm.fit import learn_bounded_prometheus
    model, rows = model_and_rows()
    calls = []
    def learner(*args, **kwargs): calls.append(1); return model
    monkeypatch.setattr(spflow.learn, 'learn_prometheus', learner)
    kwargs = dict(feature_schema=schema(), settings={'min_features_slice': 8}, gaussian_floors={0: .025, 1: .05},
                  seed=0, maximum_seconds=1., maximum_modules=1, maximum_scalar_outputs=100)
    with pytest.raises(ValueError, match='size'): learn_bounded_prometheus(rows, **kwargs)
    assert len(calls) == 1
    with pytest.raises(ValueError, match='budget'): learn_bounded_prometheus(rows, **{**kwargs, 'maximum_seconds': 0})
    assert len(calls) == 1
    def slow(*args, **kwargs): time.sleep(.1); return model
    monkeypatch.setattr(spflow.learn, 'learn_prometheus', slow)
    with pytest.raises(TimeoutError):
        learn_bounded_prometheus(rows, **{**kwargs, 'maximum_seconds': .01, 'maximum_modules': 100})


def test_public_refinement_imports_do_not_load_scientific_backends():
    import os
    import subprocess
    import sys
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[3] / 'src'))
    result = subprocess.run([sys.executable, '-c', '''
import sys
from tpm import (learn_bounded_prometheus, validate_refinement_spn,
    project_spn_gaussian_widths, spn_binary_conditional_logs, spn_refinement_loss,
    refine_spn_step, save_spn_refinement_state, load_spn_refinement_state)
assert not {'torch', 'spflow', 'pyomo', 'gurobipy'} & set(sys.modules)
'''], capture_output=True, text=True, timeout=20, env=environment)
    assert result.returncode == 0, result.stderr


def test_safe_learned_model_sidecar_reaches_public_integer_compiler(tmp_path, monkeypatch):
    import json
    from dataclasses import replace
    from tpm import (save_supported_spn_model, compile_conditional_mio_pair,
                                     TPMConditionalCompilationRequest)
    from tpm.artifact import load_tpm_artifact
    import tpm.optional_spflow as optional
    from tests.unit.tpm.test_conditional_pair import _encoding, _numerical_policy

    model, _ = model_and_rows()
    sidecar, digest = save_supported_spn_model(tmp_path / 'model.pt', model=model, feature_schema=schema())
    original = load_tpm_artifact(Path(__file__).resolve().parents[2] / 'fixtures/tpm/tpm_artifact_domains_v3.json')
    artifact = replace(original, artifact_id='refined-safe-unit',
        feature_schema=tuple(s.to_dict(schema_version='v3') for s in schema()),
        query_configuration={**original.query_configuration, 'required_decision_features': ['x']},
        spn_payload={'locator': sidecar.name, 'serialization': 'torch-weights-only-v1'},
        payload_hash=digest, source_path=str(tmp_path / 'artifact.json'))
    (tmp_path / 'artifact.json').write_text(json.dumps(artifact.to_dict()))
    def forbidden(*args, **kwargs): pytest.fail('new learned model must not use unrestricted pickle')
    monkeypatch.setattr(optional.pickle, 'loads', forbidden)
    policy = replace(_encoding(), leaf_configuration={**_encoding().leaf_configuration,
        'breakpoint_count': 3, 'integer_grids': {'x': list(range(40, 161))}})
    pair = compile_conditional_mio_pair(TPMConditionalCompilationRequest(
        source_artifact=str(tmp_path / 'artifact.json'), event_target=schema()[2].feature_name, event_value=1,
        retained_decisions=('x',), approximation_domains=({'feature_name': 'x', 'lower': 40, 'upper': 160,
            'source': 'safe-refinement-unit', 'encoding': 'piecewise-log-density'},),
        encoding=policy, numerical_policy=_numerical_policy()))
    assert pair.source.sidecar_sha256 == digest
    assert tuple(pair.encoding.leaf_configuration['integer_grids']['x']) == tuple(range(40, 161))
