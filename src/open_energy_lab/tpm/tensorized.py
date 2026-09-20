"""Exact scalar export and memory-efficient evaluation for SPFlow Linsum EiNets.

Export generalizes the tested lowering in the consumer's
``scripts/method_development/knapsack_rat_einet/scalar_dag_probe.py`` to mixed
categorical leaves. No legacy implementation is imported. Heavy dependencies
remain local to these opt-in operations.
"""


def lower_linsum_einet(model):
    """Freeze a one-class, one-repetition top-down EiNet into a scalar SPN.

    Preserve shared Product children and every learned weight. This changes
    representation, not the distribution; the returned CPU float64 model is
    intended for the supported scalar compiler, not continuation of training.
    Unsupported topology fails explicitly instead of approximating it.
    """
    import numpy as np
    import torch
    from spflow.modules.einsum import LinsumLayer
    from spflow.modules.leaves import Bernoulli, Categorical, Normal
    from spflow.modules.ops.cat import Cat
    from spflow.modules.ops.split_interleaved import SplitInterleaved
    from spflow.modules.products import Product
    from spflow.modules.rat.factorize import Factorize
    from spflow.modules.sums import Sum

    if model.layer_type != 'linsum' or model.structure != 'top-down':
        raise ValueError('lowering requires a top-down Linsum EiNet')
    if model.num_repetitions != 1 or model.num_classes != 1:
        raise ValueError('lowering requires one repetition and one class')
    factorize = model.factorize
    if type(factorize) is not Factorize or len(factorize.inputs) != 1:
        raise TypeError('unexpected factorization module')
    cat = factorize.inputs[0]
    if type(cat) is not Cat or cat.dim != 1:
        raise TypeError('factorization must concatenate leaf features')

    def parameter(value):
        return value.detach().to(device='cpu', dtype=torch.float64).clone()

    def product(children):
        if not children:
            raise ValueError('empty factorization region is unsupported')
        return children[0] if len(children) == 1 else Product(children)

    arrays = []
    for leaf in cat.inputs:
        shape = leaf.out_shape
        array = np.empty((shape.features, shape.channels, shape.repetitions), dtype=object)
        for f, variable in enumerate(leaf.scope.query):
            for c in range(shape.channels):
                for r in range(shape.repetitions):
                    if type(leaf) is Bernoulli:
                        scalar = Bernoulli([variable], logits=parameter(leaf.logits[f,c,r]).reshape(1,1,1))
                    elif type(leaf) is Categorical:
                        scalar = Categorical([variable], probs=parameter(leaf.probs[f,c,r]).reshape(1,1,1,-1))
                    elif type(leaf) is Normal:
                        scalar = Normal([variable], loc=parameter(leaf.loc[f,c,r]).reshape(1,1,1),
                                        scale=parameter(leaf.scale[f,c,r]).reshape(1,1,1))
                    else:
                        raise TypeError(f'unsupported EiNet leaf: {type(leaf).__name__}')
                    array[f,c,r] = scalar
        arrays.append(array)
    leaves = np.concatenate(arrays, axis=0)
    indices = factorize.indices.detach().cpu().numpy()
    if not np.isin(indices, (0., 1.)).all() or not (indices.sum(axis=1) == 1).all():
        raise ValueError('factorization must partition leaf features exactly once')
    shape = factorize.out_shape
    tensor = np.empty((shape.features, shape.channels, shape.repetitions), dtype=object)
    for f in range(shape.features):
        selected = np.flatnonzero(indices[:, f, 0])
        for c in range(shape.channels):
            tensor[f,c,0] = product([leaves[i,c,0] for i in selected])

    layers, current = [], model.root_node
    while type(current) is LinsumLayer:
        layers.append(current)
        split = current.inputs
        if type(split) is not SplitInterleaved or split.num_splits != 2:
            raise TypeError('each Linsum layer must use a two-way interleaved split')
        current = split.inputs
    if current is not factorize or len(layers) != model.depth:
        raise ValueError('unexpected top-down Linsum module chain')
    for layer in reversed(layers):
        left, right = tensor[::2], tensor[1::2]
        shape = layer.out_shape
        output = np.empty((shape.features, shape.channels, shape.repetitions), dtype=object)
        weights = parameter(layer.weights)
        for f in range(shape.features):
            shared = [product([left[f,c,0], right[f,c,0]]) for c in range(layer.in_shape.channels)]
            for c in range(shape.channels):
                output[f,c,0] = Sum(shared, weights=weights[f,c,0])
        tensor = output
    if tensor.shape != (1,1,1):
        raise ValueError(f'lowered root shape {tensor.shape} differs from scalar root')
    root = tensor[0,0,0]
    # Every parameter was constructed in float64 above. Module.double()/eval()
    # recursively revisit shared descendants along every path in this DAG.
    # Supported scalar SPFlow modules have no custom train-mode hooks.
    for module in root.modules():
        module.training = False
    return root


def enable_linsum_contraction(model):
    """Use stable tensor contraction for this model's Linsum forward methods.

    Avoid the batch × feature × output × input intermediate. Parameter objects
    and gradients are unchanged. A detected underflow falls back to SPFlow's
    log-space implementation. Save state dictionaries for the tensorized model;
    scalar export carries no overridden methods. Returns the modified count.
    """
    import types
    import torch
    from spflow.modules.einsum import LinsumLayer
    from spflow.utils.cache import cached

    @cached
    def contracted(self, data, cache=None):
        left, right = self._get_left_right_ll(data, cache)
        product = left + right
        shift = product.amax(dim=2, keepdim=True).detach()
        shift = torch.where(torch.isfinite(shift), shift, torch.zeros_like(shift))
        mass = torch.einsum('nfcr,forc->nfor', (product-shift).exp(), self.weights)
        if torch.any(mass < torch.finfo(mass.dtype).tiny * 1024):
            return LinsumLayer.log_likelihood(self, data, cache=cache)
        return mass.log() + shift

    count = 0
    for module in model.modules():
        if type(module) is LinsumLayer:
            module.log_likelihood = types.MethodType(contracted, module)
            count += 1
    return count
