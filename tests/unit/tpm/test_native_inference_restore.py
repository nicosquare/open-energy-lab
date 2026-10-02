"""Saved density restoration does not restore training RNG or Adam state."""
import copy

import pytest

from tests.unit.tpm.test_native_initialization import fitting_rows, initialize, make_config


@pytest.fixture
def checkpoint():
    import torch
    from tpm import native

    config = make_config(native)
    model, _ = initialize(native,fitting_rows(),config)
    optimizer = torch.optim.Adam(model.parameters(),lr=.005,foreach=False,fused=False)
    return model,config,native.capture_native_training_state(model,optimizer,config=config)


def test_inference_restore_ignores_training_backend_preserves_density_and_state(checkpoint):
    import torch
    import tpm as public
    from tpm import native

    model,config,state = checkpoint
    # An opaque foreign-backend training RNG is deliberately unusable on CPU.
    # Inference must neither inspect it nor fabricate an equivalent CPU stream.
    state['rng_state']['torch_device_type'] = 'cuda'
    state['rng_state']['torch'] = torch.tensor([1,2,3],dtype=torch.uint8)
    original = copy.deepcopy(state)
    global_rng = torch.get_rng_state().clone()
    restored = public.restore_native_mixture_for_inference(state,config=config,device='cpu')
    assert torch.equal(global_rng,torch.get_rng_state())
    assert not hasattr(restored,'_native_torch_generator')
    assert not hasattr(restored,'_native_numpy_rng')
    assert not any(p.requires_grad for p in restored.parameters())
    for key,value in state['model_state'].items():
        assert torch.equal(value,original['model_state'][key])
        assert torch.equal(value,restored.state_dict()[key])
        assert value.data_ptr() != restored.state_dict()[key].data_ptr()
    assert state['optimizer_state'] == original['optimizer_state']
    assert torch.equal(state['rng_state']['torch'],original['rng_state']['torch'])
    expected = native.native_joint_conditional_log_values(model,fitting_rows(),config=config)
    actual = native.native_joint_conditional_log_values(restored,fitting_rows(),config=config)
    for key in expected:
        torch.testing.assert_close(actual[key],expected[key],atol=1e-10,rtol=0)
    exported = public.export_native_mixture_scalar(restored)
    torch.testing.assert_close(exported.log_likelihood(torch.tensor(fitting_rows())),
                               model.log_likelihood(torch.tensor(fitting_rows())),atol=1e-10,rtol=0)
    with pytest.raises(ValueError,match='RNG state'):
        public.restore_native_training_state(state,config=config,device='cpu')


def test_training_restore_still_restores_its_local_rng(checkpoint):
    import torch
    from tpm import native
    model,config,state = checkpoint
    restored,optimizer = native.restore_native_training_state(state,config=config,device='cpu')
    assert torch.equal(model._native_torch_generator.get_state(),restored._native_torch_generator.get_state())
    assert model._native_numpy_rng.state == restored._native_numpy_rng.state
    assert all(p.requires_grad for p in restored.parameters())
    assert optimizer.state_dict() == state['optimizer_state']


@pytest.mark.parametrize('damage',['nonfinite','shape','missing','floor','config'])
def test_inference_rejects_incompatible_model_state(checkpoint,damage):
    import torch
    from tpm import native
    _model,config,state = checkpoint
    key = next(iter(state['model_state']))
    if damage == 'nonfinite':
        state['model_state'][key].fill_(float('nan'))
    elif damage == 'shape':
        state['model_state'][key] = torch.zeros((999,),dtype=torch.float64)
    elif damage == 'missing':
        del state['model_state'][key]
    elif damage == 'floor':
        key = next(key for key in state['model_state'] if key.endswith('.floor'))
        state['model_state'][key].mul_(2)
    else:
        state['config']['coordinate_id'] = 'another-coordinate-contract'
    with pytest.raises((ValueError,FloatingPointError)):
        native.restore_native_mixture_for_inference(state,config=config,device='cpu')
