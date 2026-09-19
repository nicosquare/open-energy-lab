"""Vectorized joint product mixtures with categorical and Gaussian coordinates.

Promotes the tested categorical/Gaussian equations and standardized full-data
Lloyd initialization. Data access, loss selection, schedules, and scientific
budgets remain caller-owned. Torch/SPFlow are loaded only when used.
"""
from dataclasses import asdict, dataclass
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


def build_categorical_mixture(config, *, device='cpu'):
    """Build explicit float64 parameters, with no random initialization or data."""
    import torch
    if not isinstance(config, CategoricalMixtureConfig):
        raise TypeError('expected CategoricalMixtureConfig')

    class Mixture(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.config = config
            k, g = config.components, len(config.gaussian_indices)
            self.category_logits = torch.nn.ParameterList([
                torch.nn.Parameter(torch.zeros(k, n, dtype=torch.float64, device=device))
                for n in config.cardinalities])
            self.mix = torch.nn.Parameter(torch.zeros(k, dtype=torch.float64, device=device))
            self.loc = torch.nn.Parameter(torch.zeros(k, g, dtype=torch.float64, device=device))
            self.log_scale = torch.nn.Parameter(torch.zeros(k, g, dtype=torch.float64, device=device))

        def log_prob(self, rows, *, observed=None):
            # observed=() is the normalized all-marginalized query. Demand rows
            # can be marginalized without evaluating their Gaussian densities.
            if rows.ndim != 2 or rows.shape[1] != self.config.feature_count:
                raise ValueError('rows differ from declared feature dimensions')
            observed = tuple(range(self.config.feature_count)) if observed is None else tuple(observed)
            if len(set(observed)) != len(observed) or any(i not in range(self.config.feature_count) for i in observed):
                raise ValueError('invalid observed coordinate set')
            terms = torch.log_softmax(self.mix, 0).expand(len(rows), -1)
            for p, index in zip(self.category_logits, self.config.categorical_indices):
                if index in observed:
                    values = rows[:, index]
                    if not bool(((values >= 0) & (values < p.shape[1]) & (values == values.round())).all()):
                        raise ValueError('categorical values must be integers in their declared support')
                    terms = terms + torch.log_softmax(p, 1)[:, values.long()].T
            gaussian = [(j, i) for j, i in enumerate(self.config.gaussian_indices) if i in observed]
            if gaussian:
                positions, indices = zip(*gaussian)
                d = rows[:, list(indices)]
                loc, scale = self.loc[:, list(positions)], self.log_scale[:, list(positions)]
                precision = torch.exp(-2*scale)
                terms = terms - .5*(d*d)@precision.T + d@(loc*precision).T
                terms = terms - .5*(loc*loc*precision+2*scale+math.log(2*math.pi)).sum(1)
            return torch.logsumexp(terms, 1)

        def project(self):
            with torch.no_grad():
                floor = self.log_scale.new_tensor(self.config.gaussian_floors).log()
                self.log_scale.copy_(torch.maximum(self.log_scale, floor))

        def to_spflow(self):
            from spflow.modules.leaves import Categorical, Normal
            from spflow.modules.products import Product
            from spflow.modules.sums import Sum
            k = self.config.components
            leaves = {}
            for index, p in zip(self.config.categorical_indices, self.category_logits):
                leaves[index] = Categorical(scope=[index], logits=p.detach().cpu().reshape(1,k,1,-1).clone())
            for j, index in enumerate(self.config.gaussian_indices):
                leaf = Normal(scope=[index], loc=self.loc[:,j].detach().cpu().reshape(1,k,1).clone(),
                              scale=self.log_scale[:,j].detach().cpu().exp().reshape(1,k,1))
                with torch.no_grad():leaf.log_scale.copy_(self.log_scale[:,j].detach().cpu().reshape(1,k,1))
                leaves[index] = leaf
            result = Sum(inputs=Product([leaves[i] for i in range(self.config.feature_count)]),
                         weights=torch.softmax(self.mix.detach().cpu(),0).reshape(1,k,1,1))
            with torch.no_grad():result.logits.copy_(self.mix.detach().cpu().reshape_as(result.logits))
            return result

    return Mixture()


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
            or rows.dtype != torch.float64 or rows.device != model.mix.device
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
        for p,index,cardinality in zip(model.category_logits,cfg.categorical_indices,cfg.cardinalities):
            table=torch.bincount(labels*cardinality+rows[:,index].long(),minlength=k*cardinality).reshape(k,cardinality)
            p.copy_((table.to(rows.dtype)+pseudocount).log())
        d=rows[:,list(cfg.gaussian_indices)]
        sums=torch.zeros_like(model.loc).index_add_(0,labels,d)
        squares=torch.zeros_like(model.loc).index_add_(0,labels,d.square())
        means=sums/counts.clamp_min(1)[:,None]
        variance=(squares/counts.clamp_min(1)[:,None]-means.square()).clamp_min(0)
        empty=counts==0
        means[empty]=d.mean(0);variance[empty]=d.var(0,unbiased=False)
        model.loc.copy_(means);model.log_scale.copy_(variance.sqrt().clamp_min(1e-12).log())
        model.mix.copy_((counts.to(rows.dtype)+pseudocount).log());model.project()
    return dict(rows=n,iterations=iterations,components=k,empty_components=int(empty.sum()))


def categorical_mixture_step(model, optimizer, rows, *, microbatch, gradient_clip_norm,
                             minimum_microbatch=2048, on_oom=None):
    """One joint-MLE update; retry only an uncompleted OOM gradient accumulation."""
    import torch
    if (type(microbatch) is not int or microbatch < 1 or len(rows) < 1
            or type(minimum_microbatch) is not int or minimum_microbatch < 1
            or not math.isfinite(gradient_clip_norm) or gradient_clip_norm <= 0):
        raise ValueError('invalid joint-MLE update settings')
    while True:
        optimizer.zero_grad(set_to_none=True)
        try:
            total=0.
            for part in rows.split(microbatch):
                loss=-model.log_prob(part).sum()/len(rows)
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
    return dict(loss=total,gradient_norm=float(norm),microbatch=microbatch)


def save_categorical_mixture_state(path, *, model, optimizer, generator, epoch_generator_state,
                                   progress, best_state, context):
    """Atomic weights-only full continuation, without serializing live classes."""
    import os
    import tempfile
    import torch
    from .native import _copy_native_state
    from .refinement import (_finite_metadata, _validate_progress, _validate_optimizer,
                             _validate_best, _validate_optimizer_cursor)
    cursor=_validate_progress(progress)
    if cursor.get('schedule_step') != cursor['updates']:
        raise ValueError('schedule step differs from consumed updates')
    _validate_optimizer(model,optimizer);_validate_optimizer_cursor(optimizer,cursor)
    _validate_best(model,best_state)
    if generator.device != model.mix.device:raise ValueError('shuffle generator backend differs')
    payload=_copy_native_state(dict(schema='categorical-mixture-training-v1',config=asdict(model.config),
        model_state=model.state_dict(),optimizer_state=optimizer.state_dict(),
        optimizer_defaults=optimizer.defaults,progress=cursor,best_state=best_state,
        context=_finite_metadata(context),generator_state=generator.get_state(),
        epoch_generator_state=epoch_generator_state,device_type=model.mix.device.type,
        torch_version=str(torch.__version__)))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.'+path.name,suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name);torch.save(payload,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def _read_categorical_mixture_state(path, expected_config, expected_context):
    import torch
    from .native import _copy_native_state
    from .refinement import _finite_metadata
    payload=torch.load(path,map_location='cpu',weights_only=True)
    required={'schema','config','model_state','optimizer_state','optimizer_defaults','progress','best_state',
              'context','generator_state','epoch_generator_state','device_type','torch_version'}
    if not isinstance(payload,dict) or set(payload)!=required or payload['schema']!='categorical-mixture-training-v1':
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
