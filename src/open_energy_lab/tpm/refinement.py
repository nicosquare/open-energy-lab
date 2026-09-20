"""Small supported-SPN refinement operations; training policy belongs to callers.

Rows are already in the typed schema's model coordinates. Conditional binary
queries marginalize every nonconditioning, nontarget feature. Checkpoints use
restricted Torch loading and retain Adam, RNG and the caller's work cursor.
"""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import random
import tempfile


def _supported_types():
    from torch.nn import ModuleList
    from spflow.meta.data.scope import Scope
    from spflow.modules.module_shape import ModuleShape
    from spflow.modules.leaves import Normal, Bernoulli, Categorical
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum
    from spflow.modules.ops.cat import Cat
    return (Normal, Bernoulli, Categorical, Product, Sum, Cat, ModuleList), (Scope, ModuleShape)


def validate_refinement_spn(model, *, feature_count, normalization_tolerance=1e-8):
    """One-time supported topology/parameter and all-marginalized mass admission."""
    import torch
    if not math.isfinite(normalization_tolerance) or normalization_tolerance <= 0:
        raise ValueError('normalization tolerance must be positive and finite')
    types, _ = _supported_types()
    modules = tuple(model.modules())
    if any(type(module) not in types for module in modules):
        raise ValueError('refinement requires exact supported SPFlow module types')
    if type(feature_count) is not int or feature_count < 1 or tuple(model.scope.query) != tuple(range(feature_count)):
        raise ValueError('model scope must exactly cover the declared feature coordinates')
    if tuple((model.out_shape.features, model.out_shape.channels, model.out_shape.repetitions)) != (1, 1, 1):
        raise ValueError('refinement requires one scalar joint model output')
    parameters = tuple(model.parameters())
    if not parameters or any(not torch.isfinite(p).all() for p in (*parameters, *model.buffers())):
        raise ValueError('model parameters must be finite')
    dtype, device = parameters[0].dtype, parameters[0].device
    if dtype not in (torch.float32, torch.float64) or any(p.dtype != dtype or p.device != device for p in parameters):
        raise ValueError('model parameters must share a supported precision and device')
    with torch.no_grad():
        mass = model.log_likelihood(torch.full((1, feature_count), torch.nan, dtype=dtype, device=device)).reshape(-1)
    if mass.numel() != 1 or not torch.isfinite(mass).all() or abs(float(mass[0])) > normalization_tolerance:
        raise ValueError('model all-marginalized log mass is not normalized')
    return dict(modules=len(modules),
        scalar_outputs=sum(math.prod((m.out_shape.features, m.out_shape.channels, m.out_shape.repetitions))
                           for m in modules if hasattr(m, 'out_shape')),
        parameters=sum(p.numel() for p in parameters), all_marginalized_log_mass=float(mass[0]),
        dtype=str(dtype), device_type=device.type)


def project_spn_gaussian_widths(model, gaussian_floors):
    """Project every Gaussian scale against explicit feature-index floors."""
    import torch
    from spflow.modules.leaves import Normal
    leaves = [m for m in model.modules() if type(m) is Normal]
    indices = {int(i) for leaf in leaves for i in leaf.scope.query}
    if set(gaussian_floors) != indices or any(type(i) is not int for i in gaussian_floors):
        raise ValueError('Gaussian width floors must exactly cover Gaussian feature indices')
    if any(isinstance(v, bool) or not math.isfinite(float(v)) or float(v) <= 0 for v in gaussian_floors.values()):
        raise ValueError('Gaussian width floors must be positive and finite')
    with torch.no_grad():
        for leaf in leaves:
            floors = torch.tensor([gaussian_floors[int(i)] for i in leaf.scope.query],
                                  dtype=leaf.log_scale.dtype, device=leaf.log_scale.device).reshape(-1, 1, 1)
            leaf.log_scale.copy_(torch.maximum(leaf.log_scale, floors.log()))


def spn_binary_conditional_logs(model, rows, *, conditioning_indices, target_index):
    """Return normalized log p(Y=0|X), log p(Y=1|X), marginalizing other columns."""
    import torch
    from spflow.modules.leaves import Normal, Bernoulli, Categorical
    indices = tuple(conditioning_indices)
    if (rows.ndim != 2 or type(target_index) is not int or target_index < 0
            or target_index >= rows.shape[1] or len(set(indices)) != len(indices)
            or target_index in indices or any(type(i) is not int or not 0 <= i < rows.shape[1] for i in indices)):
        raise ValueError('invalid conditional feature coordinates')
    target_leaves = [m for m in model.modules() if type(m) in (Normal, Bernoulli, Categorical)
                     and target_index in m.scope.query]
    if not target_leaves or any(type(m) is not Bernoulli for m in target_leaves):
        raise ValueError('conditional target must be represented by binary Bernoulli leaves')
    evidence = torch.full_like(rows, torch.nan)
    evidence[:, list(indices)] = rows[:, list(indices)]
    evidence[:, target_index] = 0
    zero = model.log_likelihood(evidence).reshape(len(rows), -1)
    evidence = evidence.clone()
    evidence[:, target_index] = 1
    one = model.log_likelihood(evidence).reshape(len(rows), -1)
    if zero.shape[1] != 1 or one.shape[1] != 1:
        raise ValueError('conditional refinement requires scalar outputs')
    return torch.log_softmax(torch.stack((zero[:, 0], one[:, 0]), dim=1), dim=1)


def spn_refinement_loss(model, rows, *, conditioning_indices, target_index, conditional_weight):
    """Joint NLL plus caller-weighted binary conditional NLL, with autograd intact."""
    import torch
    if rows.ndim != 2 or not len(rows) or not torch.isfinite(rows).all():
        raise ValueError('refinement batches must be nonempty finite model-coordinate rows')
    if not math.isfinite(conditional_weight) or conditional_weight < 0:
        raise ValueError('conditional loss weight must be finite and nonnegative')
    logs = spn_binary_conditional_logs(model, rows, conditioning_indices=conditioning_indices, target_index=target_index)
    labels = rows[:, target_index]
    if not ((labels == 0) | (labels == 1)).all():
        raise ValueError('conditional target must use binary model indices')
    joint_values = model.log_likelihood(rows).reshape(len(rows), -1)
    if joint_values.shape[1] != 1:
        raise ValueError('joint refinement requires scalar outputs')
    joint = -joint_values[:, 0].mean()
    conditional = -logs[torch.arange(len(rows), device=rows.device), labels.long()].mean()
    loss = joint + conditional_weight * conditional
    if not torch.isfinite(loss):
        raise ValueError('nonfinite joint or conditional refinement loss')
    return loss, dict(joint_nll=float(joint.detach()), conditional_nll=float(conditional.detach()), loss=float(loss.detach()))


def refine_spn_step(model, optimizer, rows, *, conditioning_indices, target_index,
                    conditional_weight, gaussian_floors, gradient_clip_norm):
    """One gradient update and width projection; no sampling, schedule or selection."""
    import torch
    if not math.isfinite(gradient_clip_norm) or gradient_clip_norm <= 0:
        raise ValueError('gradient clipping norm must be positive and finite')
    model.train()
    optimizer.zero_grad(set_to_none=True)
    loss, scores = spn_refinement_loss(model, rows, conditioning_indices=conditioning_indices,
                                     target_index=target_index, conditional_weight=conditional_weight)
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm, error_if_nonfinite=True)
    optimizer.step()
    project_spn_gaussian_widths(model, gaussian_floors)
    return {**scores, 'gradient_norm': float(norm)}


def _finite_metadata(value):
    # JSON validation excludes executable objects and nonfinite cursor/metric values.
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError('checkpoint metadata must contain finite plain JSON values') from exc


def _validate_progress(progress):
    progress = _finite_metadata(progress)
    fields = ('epoch', 'row_position', 'epoch_rows', 'permutation_seed', 'updates', 'consumed_rows')
    if (not isinstance(progress, dict) or any(type(progress.get(k)) is not int or progress[k] < 0 for k in fields)
            or progress['epoch_rows'] < 1 or progress['row_position'] > progress['epoch_rows']
            or progress['consumed_rows'] != progress['epoch'] * progress['epoch_rows'] + progress['row_position']
            or not isinstance(progress.get('elapsed_seconds'), (float, int)) or progress['elapsed_seconds'] < 0):
        raise ValueError('checkpoint cursor must preserve consistent consumed work')
    return progress


def _cpu_tree(value):
    import torch
    if isinstance(value, torch.Tensor): return value.detach().cpu().clone()
    if isinstance(value, dict): return {k: _cpu_tree(v) for k, v in value.items()}
    if isinstance(value, tuple): return tuple(_cpu_tree(v) for v in value)
    if isinstance(value, list): return [_cpu_tree(v) for v in value]
    if value is None or type(value) in (str, bool, int, float): return value
    raise ValueError('unsupported checkpoint state value')


def _validate_optimizer(model, optimizer):
    import torch
    if type(optimizer) is not torch.optim.Adam or len(optimizer.param_groups) != 1:
        raise ValueError('refinement checkpoint supports a single declared Adam parameter group')
    _finite_metadata(optimizer.defaults)
    _finite_metadata({k: v for k, v in optimizer.param_groups[0].items() if k != 'params'})
    params = tuple(model.parameters())
    if tuple(id(p) for p in optimizer.param_groups[0]['params']) != tuple(id(p) for p in params):
        raise ValueError('optimizer parameters must exactly match model order')
    for p, state in optimizer.state.items():
        if not any(p is candidate for candidate in params):
            raise ValueError('optimizer state has foreign parameters')
        if set(state) not in (set(), {'step', 'exp_avg', 'exp_avg_sq'}, {'step', 'exp_avg', 'exp_avg_sq', 'max_exp_avg_sq'}):
            raise ValueError('optimizer state has unsupported fields')
        for key, tensor in state.items():
            if not isinstance(tensor, torch.Tensor) or not torch.isfinite(tensor).all():
                raise ValueError('optimizer state must contain finite tensors')
            if key == 'step':
                if tensor.numel() != 1 or float(tensor) < 0 or not float(tensor).is_integer():
                    raise ValueError('optimizer step must be a nonnegative integer')
            elif tensor.shape != p.shape or tensor.dtype != p.dtype:
                raise ValueError('optimizer moment shape/precision differs from its parameter')


def _validate_best(model, best_state):
    import torch
    if best_state is None: return
    expected = model.state_dict()
    if set(best_state) != set(expected): raise ValueError('best model state keys differ')
    for key, tensor in best_state.items():
        if (not isinstance(tensor, torch.Tensor) or tensor.shape != expected[key].shape
                or tensor.dtype != expected[key].dtype or not torch.isfinite(tensor).all()):
            raise ValueError('best model state must preserve finite shapes and precision')


def _validate_optimizer_cursor(optimizer, progress):
    steps = [int(state['step']) for state in optimizer.state.values() if state]
    maximum = max(steps, default=0)
    if maximum != progress['updates']:
        raise ValueError('optimizer steps differ from the saved update cursor')


def _move_modules_once(model, device):
    """Move admitted SPFlow DAG parameters without revisiting shared branches."""
    # All admitted module types inherit Torch's _apply; none has a device hook.
    # Reversing the unique traversal retains child-before-parent conversion.
    for module in reversed(tuple(model.modules())):
        module._apply(lambda value: value.to(device), recurse=False)
    return model


def save_spn_refinement_state(path, *, model, optimizer, feature_schema, progress, best_state, context):
    """Atomically save a CPU snapshot without mutating the live model/optimizer."""
    import numpy as np
    import torch
    from .features import dump_feature_schema
    schema = dump_feature_schema(feature_schema, schema_version='v3')
    admission = validate_refinement_spn(model, feature_count=len(schema))
    _validate_optimizer(model, optimizer)
    _validate_best(model, best_state)
    cursor = _validate_progress(progress)
    _validate_optimizer_cursor(optimizer, cursor)
    context = _finite_metadata(context)
    np_state = np.random.get_state()
    device = next(model.parameters()).device
    payload = dict(schema='supported-spn-refinement-v1', feature_schema=schema,
        model=_move_modules_once(copy.deepcopy(model), 'cpu'), optimizer_state=_cpu_tree(optimizer.state_dict()),
        optimizer_defaults=_cpu_tree(optimizer.defaults), progress=cursor, best_state=_cpu_tree(best_state),
        context=context, admission=admission, torch_version=str(torch.__version__), spflow_version='1.1.0',
        torch_rng_state=torch.get_rng_state().clone(),
        cuda_rng_state=torch.cuda.get_rng_state(device).cpu() if device.type == 'cuda' else None,
        python_rng_state=random.getstate(),
        numpy_rng_state=(np_state[0], np_state[1].tolist(), *np_state[2:]))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def save_supported_spn_model(path, *, model, feature_schema):
    """Write a restricted-load model sidecar for a declared v3 compiler artifact.

    Use the returned digest in the artifact and declare sidecar serialization
    ``torch-weights-only-v1``. This preserves learned topology without a pickle
    conversion between refinement and the conditional compiler.
    """
    import io
    import torch
    from .features import dump_feature_schema
    from .artifact import write_tpm_sidecar
    schema = dump_feature_schema(feature_schema, schema_version='v3')
    validate_refinement_spn(model, feature_count=len(schema))
    payload = dict(payload_kind='current-spflow-model-sidecar', artifact_schema_version='v3',
        backend_generation='current-spflow', backend_api_version='1.1.0', query_strategy='spflow',
        feature_schema=schema, model=_move_modules_once(copy.deepcopy(model), 'cpu'))
    buffer = io.BytesIO()
    torch.save(payload, buffer)
    return write_tpm_sidecar(path, buffer.getvalue())


def load_spn_refinement_state(path, *, expected_feature_schema, expected_context, device='cpu'):
    """Restricted restore; reject incompatible context/backend instead of restarting."""
    import numpy as np
    import torch
    from .features import dump_feature_schema, load_feature_schema
    from .optional_spflow import load_supported_spflow_checkpoint
    payload = load_supported_spflow_checkpoint(path)
    required = {'schema', 'feature_schema', 'model', 'optimizer_state', 'optimizer_defaults', 'progress',
                'best_state', 'context', 'admission', 'torch_version', 'spflow_version', 'torch_rng_state',
                'cuda_rng_state', 'python_rng_state', 'numpy_rng_state'}
    if not isinstance(payload, dict) or set(payload) != required or payload['schema'] != 'supported-spn-refinement-v1':
        raise ValueError('unsupported refinement checkpoint schema')
    if payload['context'] != _finite_metadata(expected_context): raise ValueError('refinement checkpoint context differs')
    expected = dump_feature_schema(expected_feature_schema, schema_version='v3')
    if payload['feature_schema'] != expected: raise ValueError('refinement feature schema differs')
    load_feature_schema(payload['feature_schema'], schema_version='v3')
    if payload['torch_version'] != str(torch.__version__) or payload['spflow_version'] != '1.1.0':
        raise ValueError('checkpoint dependency versions differ')
    target = torch.device(device)
    if target.type != payload['admission']['device_type']:
        raise ValueError('checkpoint backend migration is not supported')
    model = payload['model']
    validate_refinement_spn(model, feature_count=len(expected))
    progress = _validate_progress(payload['progress'])
    _validate_best(model, payload['best_state'])
    _move_modules_once(model, target)
    optimizer = torch.optim.Adam(model.parameters(), **payload['optimizer_defaults'])
    optimizer.load_state_dict(payload['optimizer_state'])
    _validate_optimizer(model, optimizer)
    _validate_optimizer_cursor(optimizer, progress)
    # Set RNG only after admitting model, optimizer, schema and conserved cursor.
    torch.set_rng_state(payload['torch_rng_state'])
    if target.type == 'cuda': torch.cuda.set_rng_state(payload['cuda_rng_state'], target)
    random.setstate(payload['python_rng_state'])
    np_state = payload['numpy_rng_state']
    np.random.set_state((np_state[0], np.asarray(np_state[1], dtype=np.uint32), *np_state[2:]))
    return dict(model=model, optimizer=optimizer, feature_schema=expected, progress=progress,
                best_state=payload['best_state'], context=payload['context'])
