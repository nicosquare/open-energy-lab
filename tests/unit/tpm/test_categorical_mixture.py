"""Categorical/Gaussian joint mixture: independent native parity and continuation."""
import math
import numpy as np
import pytest
import torch

from open_energy_lab.tpm.categorical_native import (
    CategoricalMixtureConfig, build_categorical_mixture, initialize_categorical_mixture,
    categorical_mixture_step, save_categorical_mixture_state, load_categorical_mixture_state,
)


def fixture():
    cfg = CategoricalMixtureConfig(components=3, categorical_indices=(0, 2),
        cardinalities=(3, 2), gaussian_indices=(1,), gaussian_floors=(.1,))
    rows = torch.tensor([[i % 3, .13*i, i % 2] for i in range(18)], dtype=torch.float64)
    model = build_categorical_mixture(cfg)
    initialize_categorical_mixture(model, rows, seed=0, iterations=2, chunk_size=5)
    return cfg, rows, model


def test_joint_gradient_marginal_and_conditional_parity():
    cfg, rows, model = fixture()
    native = model.to_spflow()
    expected = native.log_likelihood(rows).flatten()
    actual = model.log_prob(rows)
    torch.testing.assert_close(actual, expected, atol=1e-10, rtol=1e-10)
    (-actual.mean()).backward(); (-expected.mean()).backward()
    leaves = {int(n.scope.query[0]): n for n in native.modules()
              if type(n).__name__ in ('Categorical','Normal')}
    for p, index in zip(model.category_logits, cfg.categorical_indices):
        torch.testing.assert_close(p.grad, leaves[index]._logits.grad.reshape_as(p), atol=1e-10, rtol=1e-9)
    torch.testing.assert_close(model.loc.grad[:,0], leaves[1].loc.grad.flatten(), atol=1e-10, rtol=1e-9)
    torch.testing.assert_close(model.log_scale.grad[:,0], leaves[1].log_scale.grad.flatten(), atol=1e-10, rtol=1e-9)
    torch.testing.assert_close(model.mix.grad, native.logits.grad.flatten(), atol=1e-10, rtol=1e-9)
    for observed in [(),(0,), (0,2), (1,)]:
        query=rows.clone()
        for i in set(range(3))-set(observed):query[:,i]=torch.nan
        torch.testing.assert_close(model.log_prob(rows,observed=observed),native.log_likelihood(query).flatten(),atol=1e-10,rtol=1e-10)
    masses=[]
    for label in (0,1):
        query=rows.clone();query[:,2]=label
        masses.append((model.log_prob(query,observed=(0,2))-model.log_prob(query,observed=(0,))).exp())
    torch.testing.assert_close(sum(masses),torch.ones(len(rows),dtype=torch.float64))


def test_lloyd_matches_readable_full_matrix_reference():
    cfg, rows, model = fixture()
    z=(rows-rows.mean(0))/rows.std(0).clamp_min(1e-8)
    centers=z[np.random.default_rng(0).permutation(len(rows))[:cfg.components]].clone()
    for iteration in range(3):
        distance=z.square().sum(1,keepdim=True)+centers.square().sum(1)[None,:]-2*z@centers.T
        assignment=distance.argmin(1);count=torch.bincount(assignment,minlength=cfg.components)
        if iteration<2:
            sums=torch.zeros_like(centers).index_add_(0,assignment,z)
            centers=torch.where((count>0)[:,None],sums/count.clamp_min(1)[:,None],centers)
    torch.testing.assert_close(model.mix,(count.to(torch.float64)+.5).log())
    for j,index in enumerate(cfg.categorical_indices):
        table=torch.bincount(assignment*cfg.cardinalities[j]+rows[:,index].long(),minlength=cfg.components*cfg.cardinalities[j]).reshape(cfg.components,-1)
        torch.testing.assert_close(model.category_logits[j],(table.to(torch.float64)+.5).log())
    torch.testing.assert_close(model.loc[:,0],torch.stack([rows[assignment==k,1].mean() for k in range(cfg.components)]))


@pytest.mark.parametrize('chunk_size',[1,5,32])
def test_streaming_lloyd_matches_full_matrix_initialization(tmp_path,chunk_size):
    from open_energy_lab.tpm import initialize_categorical_mixture_streaming
    cfg,rows,expected=fixture()
    path=tmp_path/'rows.npy';np.save(path,rows.numpy())
    actual=build_categorical_mixture(cfg)
    record=initialize_categorical_mixture_streaming(actual,np.load(path,mmap_mode='r'),
        seed=0,iterations=2,chunk_size=chunk_size)
    assert sum(record['counts'])==len(rows)
    for a,b in zip(expected.parameters(),actual.parameters()):
        torch.testing.assert_close(a,b,atol=1e-11,rtol=1e-11)


def test_streaming_initialization_preserves_empty_cluster_fallback():
    from open_energy_lab.tpm import initialize_categorical_mixture_streaming
    cfg,rows,_=fixture()
    rows[:]=torch.tensor([0.,.4,1.],dtype=torch.float64)
    expected=build_categorical_mixture(cfg);actual=build_categorical_mixture(cfg)
    initialize_categorical_mixture(expected,rows,seed=0,iterations=2)
    result=initialize_categorical_mixture_streaming(actual,rows.numpy(),seed=0,iterations=2,chunk_size=5)
    assert result['empty_components']==cfg.components-1
    for a,b in zip(expected.parameters(),actual.parameters()):
        torch.testing.assert_close(a,b,atol=1e-10,rtol=1e-10)


def test_streaming_initialization_rejects_invalid_last_chunk():
    from open_energy_lab.tpm import initialize_categorical_mixture_streaming
    cfg,rows,_=fixture();rows[-1,0]=.5
    with pytest.raises(ValueError,match='categorical'):
        initialize_categorical_mixture_streaming(build_categorical_mixture(cfg),rows.numpy(),seed=0,chunk_size=5)


def test_microbatch_gradient_update_matches_whole_batch():
    cfg, rows, a=fixture();b=build_categorical_mixture(cfg);b.load_state_dict(a.state_dict())
    oa=torch.optim.Adam(a.parameters(),lr=.003);ob=torch.optim.Adam(b.parameters(),lr=.003)
    categorical_mixture_step(a,oa,rows,microbatch=4,gradient_clip_norm=10)
    ob.zero_grad(set_to_none=True);loss=-b.log_prob(rows).mean();loss.backward()
    torch.nn.utils.clip_grad_norm_(b.parameters(),10,error_if_nonfinite=True);ob.step();b.project()
    for x,y in zip(a.parameters(),b.parameters()):torch.testing.assert_close(x,y,atol=1e-12,rtol=1e-10)


def test_safe_resume_preserves_adam_schedule_rng_cursor_and_best(tmp_path):
    cfg, rows, a=fixture();oa=torch.optim.Adam(a.parameters(),lr=.003,betas=(.8,.998))
    gen=torch.Generator().manual_seed(0);epoch_start=gen.get_state();perm=torch.randperm(len(rows),generator=gen)
    categorical_mixture_step(a,oa,rows[perm[:7]],microbatch=3,gradient_clip_norm=10)
    progress=dict(epoch=0,row_position=7,epoch_rows=18,permutation_seed=0,updates=1,consumed_rows=7,
                  elapsed_seconds=1.5,schedule_step=1,selected_update=1)
    path=tmp_path/'state.pt';best={k:v.clone() for k,v in a.state_dict().items()}
    save_categorical_mixture_state(path,model=a,optimizer=oa,generator=gen,
        epoch_generator_state=epoch_start,progress=progress,best_state=best,context={'data':'fixture'})
    restored=load_categorical_mixture_state(path,expected_config=cfg,expected_context={'data':'fixture'})
    b,ob=restored['model'],restored['optimizer']
    assert restored['progress']==progress
    torch.testing.assert_close(restored['permutation'],perm)
    assert torch.equal(torch.randperm(8,generator=gen),torch.randperm(8,generator=restored['generator']))
    for model,optimizer in [(a,oa),(b,ob)]:
        optimizer.param_groups[0]['lr']=.001
        categorical_mixture_step(model,optimizer,rows[perm[7:]],microbatch=3,gradient_clip_norm=10)
    for x,y in zip(a.parameters(),b.parameters()):torch.testing.assert_close(x,y,atol=0,rtol=0)
    with pytest.raises(ValueError,match='context'):
        load_categorical_mixture_state(path,expected_config=cfg,expected_context={'data':'other'})
    payload=torch.load(path,weights_only=True);payload['model_state']['mix'][0]=float('nan');torch.save(payload,path)
    with pytest.raises((ValueError,FloatingPointError),match='finite'):
        load_categorical_mixture_state(path,expected_config=cfg,expected_context={'data':'fixture'})


def test_rejects_fractional_categories_and_projects_widths():
    cfg, rows, model=fixture();bad=rows.clone();bad[0,0]=.5
    with pytest.raises(ValueError,match='categorical'):
        initialize_categorical_mixture(model,bad,seed=0,iterations=2)
    with torch.no_grad():model.log_scale.fill_(-100)
    model.project()
    torch.testing.assert_close(model.log_scale.exp(),torch.full_like(model.log_scale,.1))


def test_invalid_configuration():
    with pytest.raises(ValueError):
        CategoricalMixtureConfig(components=2,categorical_indices=(0,),cardinalities=(2,),
                                gaussian_indices=(0,),gaussian_floors=(.1,))


def test_oom_retries_only_the_unfinished_accumulation(monkeypatch):
    cfg,rows,a=fixture();b=build_categorical_mixture(cfg);b.load_state_dict(a.state_dict())
    oa=torch.optim.Adam(a.parameters(),lr=.003);ob=torch.optim.Adam(b.parameters(),lr=.003)
    original=a.log_prob;calls=0;changes=[]
    def fail_once(batch,**kw):
        nonlocal calls
        calls+=1
        if calls==2:raise torch.cuda.OutOfMemoryError('synthetic incomplete backward')
        return original(batch,**kw)
    monkeypatch.setattr(a,'log_prob',fail_once)
    result=categorical_mixture_step(a,oa,rows,microbatch=8,minimum_microbatch=2,
                                   gradient_clip_norm=10,on_oom=changes.append)
    categorical_mixture_step(b,ob,rows,microbatch=4,gradient_clip_norm=10)
    assert changes==[4] and result['microbatch']==4
    assert all(int(s['step'])==1 for s in oa.state.values())
    for x,y in zip(a.parameters(),b.parameters()):torch.testing.assert_close(x,y,atol=0,rtol=0)


def test_constant_columns_and_empty_components_keep_normalized_support():
    cfg=CategoricalMixtureConfig(3,(0,2),(3,2),(1,),(.1,))
    model=build_categorical_mixture(cfg)
    rows=torch.zeros((10,3),dtype=torch.float64)
    result=initialize_categorical_mixture(model,rows,seed=0,iterations=2)
    assert result['empty_components']==2
    assert torch.isfinite(model.log_prob(rows)).all()
    torch.testing.assert_close(model.log_prob(rows,observed=()),torch.zeros(10,dtype=torch.float64))
    assert all(torch.softmax(p,1).min()>0 for p in model.category_logits)


def test_selected_inference_reload_is_separate_from_training_backend_resume(tmp_path):
    from open_energy_lab.tpm import load_categorical_mixture_for_inference
    cfg,rows,model=fixture();optimizer=torch.optim.Adam(model.parameters(),lr=.003)
    generator=torch.Generator().manual_seed(0);epoch=generator.get_state()
    torch.randperm(len(rows),generator=generator)
    best={k:v.detach().clone() for k,v in model.state_dict().items()}
    with torch.no_grad():model.mix[0]+=1  # last iterate differs from the selected checkpoint
    path=tmp_path/'state.pt'
    progress=dict(epoch=0,row_position=0,epoch_rows=len(rows),permutation_seed=0,updates=0,
        consumed_rows=0,elapsed_seconds=0.,schedule_step=0)
    save_categorical_mixture_state(path,model=model,optimizer=optimizer,generator=generator,
        epoch_generator_state=epoch,progress=progress,best_state=best,context={'source':'fixture'})
    payload=torch.load(path,weights_only=True);payload['device_type']='cuda';torch.save(payload,path)
    result=load_categorical_mixture_for_inference(path,expected_config=cfg,expected_context={'source':'fixture'})
    assert result['source_device_type']=='cuda' and result['model'].mix.device.type=='cpu'
    assert torch.equal(result['model'].mix,best['mix'])
    with pytest.raises(ValueError,match='backend'):
        load_categorical_mixture_state(path,expected_config=cfg,expected_context={'source':'fixture'})
    with pytest.raises(ValueError,match='context'):
        load_categorical_mixture_for_inference(path,expected_config=cfg,expected_context={'source':'wrong'})
