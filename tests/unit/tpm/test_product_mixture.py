"""General feature maps preserve native likelihood, gradients and conditionals."""
import numpy as np
import pytest
from tpm.product_mixture import (
    ProductMixtureSchema, initialize_product_mixture, materialize_product_mixture,
    product_mixture_log_prob, product_mixture_conditional_probability,
)


def test_non_knapsack_feature_order_joint_gradients_and_both_event_values():
    import torch
    schema=ProductMixtureSchema((1,3,5),(0,4),2)
    rng=np.random.default_rng(21)
    rows=rng.normal(size=(32,6))
    rows[:,(1,2,3,5)]=rng.integers(0,2,(32,4))
    params=initialize_product_mixture(rows,5,1,schema=schema)
    native=materialize_product_mixture(params,schema=schema)
    tensor=torch.tensor(rows,dtype=torch.float64)
    fast=product_mixture_log_prob(tensor,params,schema=schema)
    reference=native.log_likelihood(tensor).reshape(-1)
    torch.testing.assert_close(fast,reference,atol=1e-10,rtol=0)
    (-fast.mean()).backward();(-reference.mean()).backward()
    leaves=native.inputs.inputs.inputs
    for j,i in enumerate(schema.binary_indices):
        torch.testing.assert_close(params[0].grad[:,j],leaves[i]._logits.grad.reshape(-1),atol=1e-10,rtol=0)
    for j,i in enumerate(schema.gaussian_indices):
        torch.testing.assert_close(params[2].grad[:,j],leaves[i].loc.grad.reshape(-1),atol=1e-10,rtol=0)
        torch.testing.assert_close(params[3].grad[:,j],leaves[i].log_scale.grad.reshape(-1),atol=1e-10,rtol=0)
    torch.testing.assert_close(params[4].grad,leaves[2]._logits.grad.reshape(-1),atol=1e-10,rtol=0)
    torch.testing.assert_close(params[1].grad,native.logits.grad.reshape(-1),atol=1e-10,rtol=0)
    evidence=torch.full_like(tensor,torch.nan)
    evidence[:,list(schema.binary_indices)]=tensor[:,list(schema.binary_indices)]
    with torch.no_grad():
        denominator=native.log_likelihood(evidence).reshape(-1)
        torch.testing.assert_close(product_mixture_log_prob(evidence,params,schema=schema,marginal=True),denominator,atol=1e-10,rtol=0)
        probabilities=[]
        for event in (0,1):
            evidence[:,schema.event_index]=event
            reference=(native.log_likelihood(evidence).reshape(-1)-denominator).exp()
            actual=product_mixture_conditional_probability(evidence,params,schema=schema,event_value=event)
            torch.testing.assert_close(actual,reference,atol=1e-10,rtol=0)
            probabilities.append(actual)
        torch.testing.assert_close(sum(probabilities),torch.ones(32,dtype=torch.float64),atol=1e-10,rtol=0)
        before=native.log_likelihood(tensor).clone()
        params[0].add_(1)
        torch.testing.assert_close(native.log_likelihood(tensor),before)


def test_effective_batch_chunk_gradients_match_full_batch():
    import torch
    schema=ProductMixtureSchema((0,),(1,),2)
    rows=np.array([[0,-1,0],[1,2,1],[0,3,1],[1,-2,0],[1,1,0]],dtype=float)
    params=initialize_product_mixture(rows,3,1,schema=schema)
    tensor=torch.tensor(rows,dtype=torch.float64)
    loss=-product_mixture_log_prob(tensor,params,schema=schema).mean();loss.backward()
    expected=[p.grad.clone() for p in params]
    for p in params:p.grad=None
    for chunk in tensor.split(2):
        (-product_mixture_log_prob(chunk,params,schema=schema).sum()/len(tensor)).backward()
    for p,gradient in zip(params,expected):
        torch.testing.assert_close(p.grad,gradient,atol=1e-10,rtol=0)


@pytest.mark.parametrize('binary,gaussian,event', [((0,),(0,),1),((0,),(1,),-1),((0,),(2,),3),((),(0,),1)])
def test_invalid_schemas_rejected(binary,gaussian,event):
    with pytest.raises(ValueError):ProductMixtureSchema(binary,gaussian,event)


def test_deterministic_initialization_preserves_negative_weights_and_validates_labels():
    schema=ProductMixtureSchema((0,),(1,),2)
    rows=np.array([[0,-5,0],[1,2,1],[0,-3,1]],dtype=float)
    a=initialize_product_mixture(rows,3,1,schema=schema)
    b=initialize_product_mixture(rows,3,1,schema=schema)
    for x,y in zip(a,b):np.testing.assert_array_equal(x.detach().numpy(),y.detach().numpy())
    assert float(a[2].min().detach())==-5
    rows[0,2]=.5
    with pytest.raises(ValueError,match='zero or one'):initialize_product_mixture(rows,3,1,schema=schema)
