"""One-level categorical/Gaussian mixtures: SPFlow models with closed-form training.

``build_categorical_mixture`` returns a ``CategoricalMixture``: a genuine SPFlow
``Sum(Product(Categorical and Normal leaves))`` whose leaves hold every
parameter, so ``log_likelihood`` is SPFlow's own evaluation. ``log_prob`` is the
closed form used for training (one log-softmax lookup per categorical column and
one quadratic form for the Gaussians); it reads the same leaves and agrees with
SPFlow, see ``check_categorical_mixture_against_spflow``. Parameters are read
with ``categorical_mixture_parameters`` and written with
``assign_categorical_mixture_parameters``.

Standardized full-data Lloyd initialization is included. Data access, loss
selection, schedules and scientific budgets remain caller-owned. Torch and
SPFlow are loaded only when used.
"""
from dataclasses import asdict, dataclass
from functools import lru_cache
import math
from pathlib import Path


@dataclass(frozen=True)
class CategoricalMixtureConfig:
    components: int
    categorical_indices: tuple[int, ...]
    cardinalities: tuple[int, ...]
    gaussian_indices: tuple[int, ...]
    gaussian_floors: tuple[float, ...]

    def __post_init__(self):
        indices = (*self.categorical_indices, *self.gaussian_indices)
        if (type(self.components) is not int or self.components < 1
                or not self.categorical_indices or not self.gaussian_indices
                or any(type(i) is not int for i in indices)
                or sorted(indices) != list(range(len(indices)))
                or len(self.cardinalities) != len(self.categorical_indices)
                or any(type(n) is not int or n < 2 for n in self.cardinalities)
                or len(self.gaussian_floors) != len(self.gaussian_indices)
                or any(not math.isfinite(v) or v <= 0 for v in self.gaussian_floors)):
            raise ValueError('invalid categorical/Gaussian mixture configuration')

    @property
    def feature_count(self):
        return len(self.categorical_indices) + len(self.gaussian_indices)


@lru_cache(maxsize=None)
def _mixture_class():
    import torch
    from spflow.modules.leaves import Categorical, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum

    class CategoricalMixture(Sum):
        """SPFlow Sum over one Product of per-column leaves, with a training closed form."""

        def __init__(self, config, device):
            k = config.components
            leaves = {}
            for index, cardinality in zip(config.categorical_indices, config.cardinalities):
                leaves[index] = Categorical(scope=[index], logits=torch.zeros(
                    1, k, 1, cardinality, dtype=torch.float64, device=device))
            for index in config.gaussian_indices:
                leaves[index] = Normal(
                    scope=[index], loc=torch.zeros(1, k, 1, dtype=torch.float64, device=device),
                    scale=torch.ones(1, k, 1, dtype=torch.float64, device=device))
            super().__init__(inputs=Product([leaves[i] for i in range(config.feature_count)]),
                             weights=torch.full((1, k, 1, 1), 1 / k, dtype=torch.float64, device=device))
            self.to(dtype=torch.float64, device=device)
            self.config = config
            self._categorical_leaves = tuple(leaves[i] for i in config.categorical_indices)
            self._gaussian_leaves = tuple(leaves[i] for i in config.gaussian_indices)

        def log_prob(self, rows, *, observed=None):
            """Closed-form log-likelihood; ``observed`` lists the columns not marginalized.

            ``observed=()`` is the normalized all-marginalized query. Demand rows
            can be marginalized without evaluating their Gaussian densities.
            """
            k = self.config.components
            if rows.ndim != 2 or rows.shape[1] != self.config.feature_count:
                raise ValueError('rows differ from declared feature dimensions')
            observed = tuple(range(self.config.feature_count)) if observed is None else tuple(observed)
            if len(set(observed)) != len(observed) or any(i not in range(self.config.feature_count) for i in observed):
                raise ValueError('invalid observed coordinate set')
            terms = torch.log_softmax(self.logits.reshape(k), 0).expand(len(rows), -1)
            for leaf, index in zip(self._categorical_leaves, self.config.categorical_indices):
                if index in observed:
                    table = leaf.logits.reshape(k, -1)
                    values = rows[:, index]
                    if not bool(((values >= 0) & (values < table.shape[1]) & (values == values.round())).all()):
                        raise ValueError('categorical values must be integers in their declared support')
                    terms = terms + torch.log_softmax(table, 1)[:, values.long()].T
            gaussian = [(j, i) for j, i in enumerate(self.config.gaussian_indices) if i in observed]
            if gaussian:
                positions, indices = zip(*gaussian)
                d = rows[:, list(indices)]
                loc = torch.cat([self._gaussian_leaves[j].loc.reshape(k, 1) for j in positions], 1)
                scale = torch.cat([self._gaussian_leaves[j].log_scale.reshape(k, 1) for j in positions], 1)
                precision = torch.exp(-2*scale)
                terms = terms - .5*(d*d)@precision.T + d@(loc*precision).T
                terms = terms - .5*(loc*loc*precision+2*scale+math.log(2*math.pi)).sum(1)
            return torch.logsumexp(terms, 1)

        def project(self):
            """Clamp each Gaussian log-width to its declared floor."""
            with torch.no_grad():
                for leaf, floor in zip(self._gaussian_leaves, self.config.gaussian_floors):
                    leaf.log_scale.clamp_(min=math.log(floor))

    return CategoricalMixture


def build_categorical_mixture(config, *, device='cpu'):
    """Build the SPFlow mixture with zero logits and unit widths; no data or randomness."""
    if not isinstance(config, CategoricalMixtureConfig):
        raise TypeError('expected CategoricalMixtureConfig')
    return _mixture_class()(config, device)


def categorical_mixture_parameters(model):
    """Live views of the leaf parameters, stacked for encoders and reports.

    Keys: ``mixture_logits`` (components,), ``category_logits`` (one components x
    cardinality table per categorical column, unnormalized), and
    ``gaussian_location``/``gaussian_log_scale`` (components x Gaussian columns).
    Detach before storing; write with ``assign_categorical_mixture_parameters``.
    """
    import torch
    k = model.config.components
    return dict(
        mixture_logits=model.logits.reshape(k),
        category_logits=[leaf.logits.reshape(k, -1) for leaf in model._categorical_leaves],
        gaussian_location=torch.cat([leaf.loc.reshape(k, 1) for leaf in model._gaussian_leaves], 1),
        gaussian_log_scale=torch.cat([leaf.log_scale.reshape(k, 1) for leaf in model._gaussian_leaves], 1),
    )


def assign_categorical_mixture_parameters(model, *, mixture_logits=None, category_logits=None,
                                          gaussian_location=None, gaussian_log_scale=None):
    """Copy values into the SPFlow leaves; ``None`` leaves a group unchanged."""
    import torch
    k = model.config.components
    with torch.no_grad():
        if mixture_logits is not None:
            model.logits.copy_(torch.as_tensor(mixture_logits).reshape(model.logits.shape))
        if category_logits is not None:
            if len(category_logits) != len(model._categorical_leaves):
                raise ValueError('one logit table is required per categorical column')
            for leaf, table in zip(model._categorical_leaves, category_logits):
                leaf.logits.copy_(torch.as_tensor(table).reshape(leaf.logits.shape))
        for values, attribute in ((gaussian_location, 'loc'), (gaussian_log_scale, 'log_scale')):
            if values is not None:
                values = torch.as_tensor(values)
                if values.shape != (k, len(model._gaussian_leaves)):
                    raise ValueError('Gaussian parameters must be components x Gaussian columns')
                for j, leaf in enumerate(model._gaussian_leaves):
                    getattr(leaf, attribute).copy_(values[:, j].reshape(getattr(leaf, attribute).shape))


def check_categorical_mixture_against_spflow(model, rows, *, tolerance=1e-9):
    """Compare ``log_prob`` with SPFlow's ``log_likelihood``; return the max error."""
    import torch
    with torch.no_grad():
        error = float((model.log_prob(rows) - model.log_likelihood(rows).reshape(-1)).abs().max())
    if not error <= tolerance:
        raise FloatingPointError(f'closed-form mixture likelihood differs from SPFlow by {error:.3g}')
    return error


def initialize_categorical_mixture(model, rows, *, seed, iterations=20, chunk_size=65536,
                                   pseudocount=.5, progress=None):
    """Standardized Lloyd updates with categorical smoothing and Gaussian moments.

    Keep the reference sample standard deviation, initial PCG64 permutation,
    final assignment pass and empty-cluster moment fallback. No label balancing.
    """
    import numpy as np
    import torch
    cfg = model.config
    n, k = len(rows), cfg.components
    if (rows.ndim != 2 or rows.shape[1] != cfg.feature_count or n < max(2,k)
            or rows.dtype != torch.float64 or rows.device != model.logits.device
            or not bool(torch.isfinite(rows).all())
            or type(iterations) is not int or iterations < 1
            or type(chunk_size) is not int or chunk_size < 1
            or not math.isfinite(pseudocount) or pseudocount <= 0):
        raise ValueError('invalid finite mixture initialization rows or settings')
    for index, cardinality in zip(cfg.categorical_indices, cfg.cardinalities):
        v = rows[:,index]
        if not bool(((v >= 0) & (v < cardinality) & (v == v.round())).all()):
            raise ValueError('invalid categorical initialization values')
    with torch.no_grad():
        z = (rows-rows.mean(0))/rows.std(0).clamp_min(1e-8)
        ids = np.random.default_rng(seed).permutation(n)[:k]
        centers = z[torch.tensor(ids, device=rows.device)].clone()
        labels = torch.empty(n, dtype=torch.long, device=rows.device)
        for iteration in range(iterations+1):
            for offset in range(0,n,chunk_size):
                block=z[offset:offset+chunk_size]
                distance=block.square().sum(1,keepdim=True)+centers.square().sum(1)[None,:]-2*block@centers.T
                labels[offset:offset+len(block)]=distance.argmin(1)
            counts=torch.bincount(labels,minlength=k)
            if iteration == iterations:break
            sums=torch.zeros_like(centers).index_add_(0,labels,z)
            centers=torch.where((counts>0)[:,None],sums/counts.clamp_min(1)[:,None],centers)
            if progress is not None:progress(iteration+1)
        tables=[]
        for index,cardinality in zip(cfg.categorical_indices,cfg.cardinalities):
            table=torch.bincount(labels*cardinality+rows[:,index].long(),minlength=k*cardinality).reshape(k,cardinality)
            tables.append((table.to(rows.dtype)+pseudocount).log())
        d=rows[:,list(cfg.gaussian_indices)]
        sums=torch.zeros(k,d.shape[1],dtype=d.dtype,device=d.device).index_add_(0,labels,d)
        squares=torch.zeros_like(sums).index_add_(0,labels,d.square())
        means=sums/counts.clamp_min(1)[:,None]
        variance=(squares/counts.clamp_min(1)[:,None]-means.square()).clamp_min(0)
        empty=counts==0
        means[empty]=d.mean(0);variance[empty]=d.var(0,unbiased=False)
        assign_categorical_mixture_parameters(model,mixture_logits=(counts.to(rows.dtype)+pseudocount).log(),
            category_logits=tables,gaussian_location=means,
            gaussian_log_scale=variance.sqrt().clamp_min(1e-12).log())
        model.project()
    return dict(rows=n,iterations=iterations,components=k,empty_components=int(empty.sum()))


def initialize_categorical_mixture_streaming(model, rows, *, seed, iterations=20,
                                             chunk_size=32768, pseudocount=.5, progress=None):
    """Full-data Lloyd initialization from a float64 NumPy array or memory map.

    Match the full-matrix initializer's standardized distances, PCG64 center
    selection, empty-cluster fallback and smoothed categorical counts. Only one
    input chunk and its distance matrix reside on the model's device. Population
    moments are accumulated with parallel Welford updates for numerical stability.
    """
    import numpy as np
    import torch
    cfg = model.config
    if (not isinstance(rows,np.ndarray) or rows.dtype != np.float64 or rows.ndim != 2
            or rows.shape[1] != cfg.feature_count or len(rows) < max(2,cfg.components)
            or type(iterations) is not int or iterations < 1
            or type(chunk_size) is not int or chunk_size < 1
            or not math.isfinite(pseudocount) or pseudocount <= 0):
        raise ValueError('invalid streaming initialization rows or settings')
    n,k,device = len(rows),cfg.components,model.logits.device

    def block_at(start, stop):
        # Explicit copy also admits read-only memory maps without writable-view warnings.
        return torch.as_tensor(np.array(rows[start:stop],copy=True),dtype=torch.float64,device=device)

    with torch.no_grad():
        mean = torch.zeros(cfg.feature_count,dtype=torch.float64,device=device)
        m2 = torch.zeros_like(mean)
        seen = 0
        cardinalities = torch.tensor(cfg.cardinalities,device=device)
        for start in range(0,n,chunk_size):
            block = block_at(start,min(n,start+chunk_size))
            categorical = block[:,list(cfg.categorical_indices)]
            if (not bool(torch.isfinite(block).all()) or
                    not bool(((categorical >= 0) & (categorical < cardinalities) &
                              (categorical == categorical.round())).all())):
                raise ValueError('invalid finite rows or categorical initialization values')
            count = len(block)
            local_mean = block.mean(0)
            delta = local_mean-mean
            m2 += ((block-local_mean)**2).sum(0)+delta.square()*(seen*count/(seen+count))
            mean += delta*(count/(seen+count))
            seen += count
        std = (m2/(n-1)).sqrt().clamp_min(1e-8)
        ids = np.random.default_rng(seed).permutation(n)[:k]
        centers = (torch.as_tensor(np.array(rows[ids],copy=True),device=device)-mean)/std
        for iteration in range(iterations+1):
            counts = torch.zeros(k,dtype=torch.int64,device=device)
            sums = torch.zeros_like(centers)
            final = iteration == iterations
            if final:
                tables = [torch.zeros(k,c,dtype=torch.int64,device=device) for c in cfg.cardinalities]
                demand_sums = torch.zeros(k,len(cfg.gaussian_indices),dtype=torch.float64,device=device)
                demand_squares = torch.zeros_like(demand_sums)
            for start in range(0,n,chunk_size):
                block = block_at(start,min(n,start+chunk_size))
                z = (block-mean)/std
                distance = z.square().sum(1,keepdim=True)+centers.square().sum(1)[None,:]-2*z@centers.T
                labels = distance.argmin(1)
                counts += torch.bincount(labels,minlength=k)
                if not final:
                    sums.index_add_(0,labels,z)
                else:
                    for table,index,c in zip(tables,cfg.categorical_indices,cfg.cardinalities):
                        table += torch.bincount(labels*c+block[:,index].long(),minlength=k*c).reshape(k,c)
                    demand = block[:,list(cfg.gaussian_indices)]
                    demand_sums.index_add_(0,labels,demand)
                    demand_squares.index_add_(0,labels,demand.square())
            if not final:
                centers = torch.where((counts>0)[:,None],sums/counts.clamp_min(1)[:,None],centers)
            if progress is not None:
                progress(dict(phase='lloyd' if not final else 'final_assignment',
                              completed_passes=iteration+1,total_passes=iterations+1,rows=n))
        means = demand_sums/counts.clamp_min(1)[:,None]
        variance = (demand_squares/counts.clamp_min(1)[:,None]-means.square()).clamp_min(0)
        empty = counts == 0
        means[empty] = mean[list(cfg.gaussian_indices)]
        variance[empty] = m2[list(cfg.gaussian_indices)]/n
        assign_categorical_mixture_parameters(model,mixture_logits=(counts.to(torch.float64)+pseudocount).log(),
            category_logits=[(table.to(torch.float64)+pseudocount).log() for table in tables],
            gaussian_location=means,gaussian_log_scale=variance.sqrt().clamp_min(1e-12).log())
        model.project()
    return dict(rows=n,iterations=iterations,components=k,empty_components=int(empty.sum()),
        chunk_size=chunk_size,center_indices=ids.tolist(),counts=counts.cpu().tolist(),
        standardization_mean=mean.cpu().tolist(),standardization_std=std.cpu().tolist())


def categorical_mixture_step(model, optimizer, rows, *, microbatch, gradient_clip_norm,
                             minimum_microbatch=2048, on_oom=None, conditional_weight=0.0,
                             conditioning_indices=(), target_index=None):
    """One joint-MLE update; retry only an uncompleted OOM gradient accumulation.

    conditional_weight > 0 adds that multiple of the conditional NLL of column target_index given
    conditioning_indices (as spn_refinement_loss): the joint term stays whole, so the model stays generative."""
    import torch
    if (type(microbatch) is not int or microbatch < 1 or len(rows) < 1
            or type(minimum_microbatch) is not int or minimum_microbatch < 1
            or not math.isfinite(gradient_clip_norm) or gradient_clip_norm <= 0):
        raise ValueError('invalid joint-MLE update settings')
    if not math.isfinite(conditional_weight) or conditional_weight < 0:
        raise ValueError('conditional loss weight must be finite and nonnegative')
    if conditional_weight and (target_index is None or target_index in conditioning_indices):
        raise ValueError('a conditional loss needs a target column outside the conditioning columns')
    observed=tuple(conditioning_indices)
    while True:
        optimizer.zero_grad(set_to_none=True)
        try:
            total=0.;conditional=0.
            for part in rows.split(microbatch):
                loss=-model.log_prob(part).sum()/len(rows)
                if conditional_weight:
                    term=-(model.log_prob(part,observed=(*observed,target_index))
                           -model.log_prob(part,observed=observed)).sum()/len(rows)
                    loss=loss+conditional_weight*term;conditional+=float(term.detach())
                if not bool(torch.isfinite(loss)):raise ValueError('nonfinite joint loss')
                loss.backward();total+=float(loss.detach())
            break
        except torch.cuda.OutOfMemoryError:
            optimizer.zero_grad(set_to_none=True)
            if microbatch <= minimum_microbatch:raise
            microbatch=max(minimum_microbatch,microbatch//2)
            torch.cuda.empty_cache()
            if on_oom is not None:on_oom(microbatch)
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),gradient_clip_norm,error_if_nonfinite=True)
    optimizer.step();model.project()
    if any(not bool(torch.isfinite(p).all()) for p in model.parameters()):
        raise ValueError('nonfinite mixture parameters after joint update')
    return dict(loss=total,gradient_norm=float(norm),microbatch=microbatch,
                **(dict(conditional_nll=conditional) if conditional_weight else {}))


def save_categorical_mixture_state(path, *, model, optimizer, generator, epoch_generator_state,
                                   progress, best_state, context):
    """Atomic weights-only full continuation, without serializing live classes."""
    import torch
    from ._io import atomic_write
    from .native import _copy_native_state
    from .refinement import (_finite_metadata, _validate_progress, _validate_optimizer,
                             _validate_best, _validate_optimizer_cursor)
    cursor=_validate_progress(progress)
    if cursor.get('schedule_step') != cursor['updates']:
        raise ValueError('schedule step differs from consumed updates')
    _validate_optimizer(model,optimizer);_validate_optimizer_cursor(optimizer,cursor)
    _validate_best(model,best_state)
    if generator.device != model.logits.device:raise ValueError('shuffle generator backend differs')
    payload=_copy_native_state(dict(schema='categorical-mixture-training-v2',config=asdict(model.config),
        model_state=model.state_dict(),optimizer_state=optimizer.state_dict(),
        optimizer_defaults=optimizer.defaults,progress=cursor,best_state=best_state,
        context=_finite_metadata(context),generator_state=generator.get_state(),
        epoch_generator_state=epoch_generator_state,device_type=model.logits.device.type,
        torch_version=str(torch.__version__)))
    atomic_write(Path(path),lambda stream:torch.save(payload,stream))


def _read_categorical_mixture_state(path, expected_config, expected_context):
    import torch
    from .native import _copy_native_state
    from .refinement import _finite_metadata
    payload=torch.load(path,map_location='cpu',weights_only=True)
    required={'schema','config','model_state','optimizer_state','optimizer_defaults','progress','best_state',
              'context','generator_state','epoch_generator_state','device_type','torch_version'}
    if not isinstance(payload,dict) or set(payload)!=required or payload['schema']!='categorical-mixture-training-v2':
        raise ValueError('unsupported categorical mixture checkpoint')
    payload=_copy_native_state(payload)
    if payload['config']!=asdict(expected_config):raise ValueError('checkpoint feature configuration differs')
    if payload['context']!=_finite_metadata(expected_context):raise ValueError('checkpoint context differs')
    return payload


def load_categorical_mixture_state(path, *, expected_config, expected_context, device='cpu'):
    """Restore Adam, selected state and the current permutation without a budget reset."""
    import torch
    from .refinement import (_validate_progress, _validate_optimizer,
                             _validate_best, _validate_optimizer_cursor)
    payload=_read_categorical_mixture_state(path,expected_config,expected_context)
    target=torch.device(device)
    if target.type!=payload['device_type'] or payload['torch_version']!=str(torch.__version__):
        raise ValueError('checkpoint backend or dependency version differs')
    progress=_validate_progress(payload['progress'])
    if progress.get('schedule_step')!=progress['updates']:raise ValueError('checkpoint schedule step differs')
    model=build_categorical_mixture(expected_config,device=target)
    _validate_best(model,payload['model_state']);_validate_best(model,payload['best_state'])
    model.load_state_dict(payload['model_state'],strict=True)
    optimizer=torch.optim.Adam(model.parameters(),**payload['optimizer_defaults'])
    optimizer.load_state_dict(payload['optimizer_state'])
    _validate_optimizer(model,optimizer);_validate_optimizer_cursor(optimizer,progress)
    generator=torch.Generator(device=target);generator.set_state(payload['generator_state'])
    epoch_generator=torch.Generator(device=target);epoch_generator.set_state(payload['epoch_generator_state'])
    permutation=torch.randperm(progress['epoch_rows'],generator=epoch_generator,device=target)
    if not torch.equal(epoch_generator.get_state(),generator.get_state()):
        raise ValueError('checkpoint shuffle states do not describe the same epoch')
    return dict(model=model,optimizer=optimizer,generator=generator,permutation=permutation,
                epoch_generator_state=payload['epoch_generator_state'],progress=progress,
                best_state=payload['best_state'],context=payload['context'])


def load_categorical_mixture_for_inference(path, *, expected_config, expected_context, device='cpu'):
    """Load only the selected state for inference, allowing a different device.

    This cannot resume an optimizer or migrate a fitting backend. Training
    continuation remains strict through load_categorical_mixture_state.
    """
    import torch
    from .refinement import _validate_best, _validate_progress
    payload=_read_categorical_mixture_state(path,expected_config,expected_context)
    if payload['torch_version']!=str(torch.__version__):
        raise ValueError('checkpoint dependency version differs')
    progress=_validate_progress(payload['progress'])
    if progress.get('schedule_step')!=progress['updates'] or payload['best_state'] is None:
        raise ValueError('checkpoint lacks a consistent selected state')
    model=build_categorical_mixture(expected_config,device=device)
    _validate_best(model,payload['best_state'])
    model.load_state_dict(payload['best_state'],strict=True);model.eval()
    return dict(model=model,progress=progress,context=payload['context'],source_device_type=payload['device_type'])


__all__ = [
    "CategoricalMixtureConfig",
    "assign_categorical_mixture_parameters",
    "build_categorical_mixture",
    "categorical_mixture_parameters",
    "categorical_mixture_step",
    "check_categorical_mixture_against_spflow",
    "initialize_categorical_mixture",
    "initialize_categorical_mixture_streaming",
    "load_categorical_mixture_for_inference",
    "load_categorical_mixture_state",
    "save_categorical_mixture_state",
]
