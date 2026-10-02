"""Vectorized float64 Bernoulli/Gaussian product-mixture learning primitives.

Extracted from tpm_for_sp/knapsack_tpm/{joint_model.py,filtered/model.py}.
Likelihood and all parameter gradients are qualified against genuine SPFlow.
The caller owns normalization, data selection, optimizer, batches and checkpoints.
Torch and SPFlow remain lazy dependencies.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ProductMixtureSchema:
    binary_indices: tuple[int, ...]
    gaussian_indices: tuple[int, ...]
    event_index: int

    def __post_init__(self):
        object.__setattr__(self, 'binary_indices', tuple(self.binary_indices))
        object.__setattr__(self, 'gaussian_indices', tuple(self.gaussian_indices))
        indices = self.binary_indices+self.gaussian_indices+(self.event_index,)
        if (not self.binary_indices or not self.gaussian_indices
                or any(type(i) is not int or i < 0 for i in indices)
                or sorted(indices) != list(range(len(indices)))):
            raise ValueError('Binary, Gaussian and event indices must partition the input columns')

    @property
    def dimension(self):
        return len(self.binary_indices)+len(self.gaussian_indices)+1


def _parameters(params, schema):
    if not isinstance(schema, ProductMixtureSchema) or len(params) != 5:
        raise ValueError('Explicit schema and five parameter tensors required')
    binary, mixture, location, log_scale, event = params
    k = len(mixture)
    if (k < 1 or mixture.ndim != 1 or binary.shape != (k,len(schema.binary_indices))
            or location.shape != (k,len(schema.gaussian_indices)) or log_scale.shape != location.shape
            or event.shape != (k,)):
        raise ValueError('Parameter shapes differ from the declared product-mixture schema')
    import torch
    if any(p.dtype != torch.float64 or p.device != mixture.device for p in params):
        raise ValueError('All parameters must use float64 on one device')
    return binary, mixture, location, log_scale, event


def product_mixture_action_terms(rows, params, *, schema):
    """Differentiable per-component log P(X,component), marginalizing W and Y."""
    import torch
    binary, mixture, *_ = _parameters(params,schema)
    if rows.ndim != 2 or rows.shape[1] <= max(schema.binary_indices):
        raise ValueError('Rows must contain every declared binary decision column')
    x = rows[:,list(schema.binary_indices)]
    return x @ binary.T-torch.nn.functional.softplus(binary).sum(1)+torch.log_softmax(mixture,0)


def product_mixture_log_prob(rows, params, *, schema, marginal=False):
    """Joint likelihood, or the fitted decision marginal when marginal=True."""
    import torch
    terms = product_mixture_action_terms(rows,params,schema=schema)
    if not marginal:
        if rows.shape[1] != schema.dimension:
            raise ValueError('Joint observations must match the declared schema')
        _,_,mu,logsd,event = params
        w = rows[:,list(schema.gaussian_indices)]
        precision = torch.exp(-2*logsd)
        terms = terms-.5*(w*w)@precision.T+w@(mu*precision).T
        terms = terms-.5*(mu*mu*precision+2*logsd+math.log(2*math.pi)).sum(1)
        terms = terms+rows[:,schema.event_index:schema.event_index+1]*event-torch.nn.functional.softplus(event)
    return torch.logsumexp(terms,1)


def product_mixture_conditional_probability(rows, params, *, schema, event_value=0):
    """P(Y=event_value | X), using the fitted denominator and marginalizing W."""
    import torch
    if event_value not in (0,1):
        raise ValueError('The event value must be binary')
    terms = product_mixture_action_terms(rows,params,schema=schema)
    log_event = event_value*params[4]-torch.nn.functional.softplus(params[4])
    return (torch.logsumexp(terms+log_event,1)-torch.logsumexp(terms,1)).exp()


def initialize_product_mixture(rows, components, seed, *, schema, device='cpu', binary_margin=.15):
    """Fresh row-center initialization; no validation data or target loss policy."""
    import numpy as np
    import torch
    rows = np.asarray(rows,dtype=np.float64)
    if (not isinstance(schema,ProductMixtureSchema) or rows.ndim != 2 or rows.shape[1] != schema.dimension
            or type(components) is not int or not 0 < components <= len(rows)
            or type(seed) is not int or seed < 0 or not np.isfinite(rows).all()
            or not 0 < binary_margin < .5):
        raise ValueError('Finite schema-matching data, valid component count/seed and margin required')
    binary_columns = schema.binary_indices+(schema.event_index,)
    if not np.isin(rows[:,binary_columns],(0,1)).all():
        raise ValueError('Binary decisions and event labels must be zero or one')
    ids = np.random.default_rng(seed).permutation(len(rows))[:components]
    centers = rows[ids]
    # Arithmetic order preserves the qualified .15 + .7*x initialization.
    p = binary_margin+(1-2*binary_margin)*centers[:,schema.binary_indices]
    event = binary_margin+(1-2*binary_margin)*centers[:,schema.event_index]
    values = [np.log(p)-np.log1p(-p), np.zeros(components), centers[:,schema.gaussian_indices],
              np.zeros((components,len(schema.gaussian_indices))), np.log(event)-np.log1p(-event)]
    return [torch.nn.Parameter(torch.tensor(v,dtype=torch.float64,device=device)) for v in values]


def materialize_product_mixture(params, *, schema):
    """Materialize an independent current-SPFlow CPU model, retaining raw logits."""
    import torch
    from spflow.modules.leaves import Bernoulli, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum
    _parameters(params,schema)
    binary,mix,mu,logsd,event = [p.detach().cpu().clone() for p in params]
    k = len(mix)
    leaves = {i:Bernoulli(scope=[i],logits=binary[:,j].reshape(1,k,1))
              for j,i in enumerate(schema.binary_indices)}
    leaves.update({i:Normal(scope=[i],loc=mu[:,j].reshape(1,k,1),scale=logsd[:,j].exp().reshape(1,k,1))
                   for j,i in enumerate(schema.gaussian_indices)})
    leaves[schema.event_index] = Bernoulli(scope=[schema.event_index],logits=event.reshape(1,k,1))
    return Sum(inputs=Product([leaves[i] for i in range(schema.dimension)]),
               weights=torch.softmax(mix,0).reshape(1,k,1,1))


__all__ = ['ProductMixtureSchema', 'initialize_product_mixture', 'materialize_product_mixture', 'product_mixture_action_terms', 'product_mixture_log_prob', 'product_mixture_conditional_probability']
