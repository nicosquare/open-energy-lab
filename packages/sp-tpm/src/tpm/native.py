"""Fixed Gaussian/Bernoulli product-mixture parameter learning.

Feature types and conditional roles are explicit, not benchmark-specific. The
caller owns preprocessing, data access, schedules, budgets and evidence. Backend
imports stay inside mathematical operations so configuration remains lightweight.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import math
from numbers import Real
from types import MappingProxyType


@dataclass(frozen=True)
class TPMNativeMixtureConfig:
    components: int
    gaussian_indices: tuple[int, ...]
    bernoulli_indices: tuple[int, ...]
    target_index: int
    conditioning_indices: tuple[int, ...]
    gaussian_floors: tuple[float, ...]
    coordinate_id: str
    lloyd_max_iterations: int = 300
    lloyd_tolerance: float = 1e-6
    initialization_chunk_size: int = 10_000

    def __post_init__(self):
        for value in (self.components, self.lloyd_max_iterations, self.initialization_chunk_size):
            if type(value) is not int or value <= 0:
                raise ValueError("component and initialization limits must be positive integers")
        for indices in (self.gaussian_indices, self.bernoulli_indices, self.conditioning_indices):
            if (type(indices) is not tuple or any(type(i) is not int or i < 0 for i in indices)
                    or len(set(indices)) != len(indices)):
                raise ValueError("feature indices must be unique nonnegative integer tuples")
        combined = (*self.gaussian_indices, *self.bernoulli_indices)
        if tuple(sorted(combined)) != tuple(range(len(combined))):
            raise ValueError("Gaussian and Bernoulli indices must partition every input column")
        if type(self.target_index) is not int or self.target_index not in self.bernoulli_indices:
            raise ValueError("the conditional target must be a declared Bernoulli column")
        if (self.target_index in self.conditioning_indices
                or any(i >= len(combined) for i in self.conditioning_indices)):
            raise ValueError("conditioning columns must be valid and exclude the target")
        if (type(self.gaussian_floors) is not tuple
                or len(self.gaussian_floors) != len(self.gaussian_indices)
                or any(not isinstance(x, Real) or isinstance(x, bool)
                       or not math.isfinite(x) or x <= 0 for x in self.gaussian_floors)):
            raise ValueError("each Gaussian column requires one finite positive width floor")
        if (not isinstance(self.lloyd_tolerance, Real) or isinstance(self.lloyd_tolerance, bool)
                or not math.isfinite(self.lloyd_tolerance) or self.lloyd_tolerance < 0):
            raise ValueError("Lloyd displacement tolerance must be finite and nonnegative")
        if type(self.coordinate_id) is not str or not self.coordinate_id.strip():
            raise ValueError("explicit model-coordinate identity is required")
        object.__setattr__(self, "gaussian_floors", tuple(float(x) for x in self.gaussian_floors))
        object.__setattr__(self, "lloyd_tolerance", float(self.lloyd_tolerance))

    @property
    def feature_count(self) -> int:
        return len(self.gaussian_indices) + len(self.bernoulli_indices)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or value.keys() != {field.name for field in fields(cls)}:
            raise ValueError("native configuration has missing or unknown fields")
        converted = dict(value)
        for key in ("gaussian_indices", "bernoulli_indices", "conditioning_indices", "gaussian_floors"):
            if type(converted[key]) not in (tuple, list):
                raise ValueError("native configuration sequences must be explicit")
            converted[key] = tuple(converted[key])
        return cls(**converted)


def _backend():
    import torch
    from spflow.modules.leaves import Bernoulli, Normal
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum

    return torch, Bernoulli, Normal, Product, Sum


def _require_config(config):
    if type(config) is not TPMNativeMixtureConfig:
        raise ValueError("native operations require an explicit immutable mixture configuration")


def _finite(*values):
    import torch

    if any(not bool(torch.isfinite(value).all()) for value in values):
        raise FloatingPointError("native computation contains nonfinite numerical state")


def _floor_parametrization(floor, *, dtype, device):
    import torch

    class FloorLogScale(torch.nn.Module):
        """Effective log(sigma_min + softplus(a)); checkpoints store a and the floor."""

        def __init__(self):
            super().__init__()
            self.register_buffer("floor", torch.tensor(floor, dtype=dtype, device=device))

        def forward(self, raw):
            return torch.log(self.floor + torch.nn.functional.softplus(raw))

        def right_inverse(self, log_scale):
            difference = torch.exp(log_scale) - self.floor
            if not bool((difference > 0).all()):
                raise FloatingPointError("initial Gaussian width must exceed its declared floor")
            # Stable inverse softplus: x + log(1 - exp(-x)), avoiding cancellation.
            raw = difference + torch.log(-torch.expm1(-difference))
            _finite(raw)
            return raw

    return FloorLogScale()


def _build_mixture(config, *, means, scales, probabilities, weights, device):
    """Construct the declared graph from explicit parameters, without learning structure."""
    _require_config(config)
    torch, Bernoulli, Normal, Product, Sum = _backend()
    from torch.nn.utils.parametrize import register_parametrization

    def tensor(value, shape):
        # Own parameter storage; the graph must not alias caller arrays/tensors.
        result = torch.as_tensor(value, dtype=torch.float64, device=device).detach().clone()
        if tuple(result.shape) != shape:
            raise ValueError("initial parameter shape does not match the declared topology")
        _finite(result)
        return result

    k = config.components
    means = tensor(means, (k, len(config.gaussian_indices)))
    scales = tensor(scales, (k, len(config.gaussian_indices)))
    probabilities = tensor(probabilities, (k, len(config.bernoulli_indices)))
    weights = tensor(weights, (k,))
    if not bool((weights > 0).all()) or not math.isclose(float(weights.sum()), 1, rel_tol=1e-12, abs_tol=1e-15):
        raise ValueError("initial mixture weights must be positive and normalized")
    if not bool(((probabilities > 0) & (probabilities < 1)).all()):
        raise ValueError("initial Bernoulli probabilities must be strictly between zero and one")
    gaussian_positions = {index: position for position, index in enumerate(config.gaussian_indices)}
    bernoulli_positions = {index: position for position, index in enumerate(config.bernoulli_indices)}
    leaves = []
    for index in range(config.feature_count):
        if index in gaussian_positions:
            position = gaussian_positions[index]
            floor = config.gaussian_floors[position]
            if not bool((scales[:, position] > floor).all()):
                raise FloatingPointError("initial Gaussian widths must exceed the declared floor")
            leaf = Normal(scope=[index], loc=means[:, position].reshape(1, k, 1).clone(),
                          scale=scales[:, position].reshape(1, k, 1).clone())
            register_parametrization(leaf, "log_scale", _floor_parametrization(
                floor, dtype=torch.float64, device=device,
            ))
        else:
            position = bernoulli_positions[index]
            leaf = Bernoulli(scope=[index], probs=probabilities[:, position].reshape(1, k, 1).clone())
        leaves.append(leaf)
    model = Sum(inputs=Product(leaves), weights=weights.reshape(1, k, 1, 1)).to(
        device=device, dtype=torch.float64,
    )
    model._native_config = config
    _finite(*model.parameters(), *model.buffers())
    return model


def _work(callback, phase):
    if callback is not None:
        if not callable(callback):
            raise ValueError("bounded-work callback must be callable")
        callback(phase)


def _data_matrix(rows, config, device):
    import torch

    _require_config(config)
    if isinstance(rows, torch.Tensor):
        data = rows.detach().to(dtype=torch.float64, device=device).clone()
    else:
        data = torch.tensor(rows, dtype=torch.float64, device=device)
    if data.ndim != 2 or data.shape[0] == 0 or data.shape[1] != config.feature_count:
        raise ValueError("rows must be a nonempty matrix in the declared feature order")
    _finite(data)
    binary = data[:, list(config.bernoulli_indices)]
    if not bool(((binary == 0) | (binary == 1)).all()):
        raise ValueError("Bernoulli observations must be exactly zero or one")
    return data


def _randbelow(generator, maximum):
    if maximum == 1:
        return 0
    mask = (1 << (maximum - 1).bit_length()) - 1
    while True:
        value = int(generator.random_raw()) & mask
        if value < maximum:
            return value


def _population_moments(data, chunk_size, callback):
    import torch

    total = torch.zeros(data.shape[1], dtype=data.dtype, device=data.device)
    for start in range(0, len(data), chunk_size):
        _work(callback, "initialization.moments.mean")
        total += data[start:start + chunk_size].sum(dim=0)
    mean = total / len(data)
    variance_sum = torch.zeros_like(mean)
    for start in range(0, len(data), chunk_size):
        _work(callback, "initialization.moments.variance")
        variance_sum += ((data[start:start + chunk_size] - mean) ** 2).sum(dim=0)
    deviation = (variance_sum / len(data)).sqrt()
    _finite(mean, deviation)
    return mean, torch.where(deviation == 0, torch.ones_like(deviation), deviation)


def _assign_clusters(data, centers, chunk_size, callback, phase):
    import torch

    labels = torch.empty(len(data), dtype=torch.int64, device=data.device)
    for start in range(0, len(data), chunk_size):
        _work(callback, phase)
        part = data[start:start + chunk_size]
        distances = ((part[:, None, :] - centers[None, :, :]) ** 2).sum(dim=2)
        _finite(distances)
        # argmin returns the first index, fixing exact ties to the smallest ID.
        labels[start:start + len(part)] = distances.argmin(dim=1)
    return labels


def _cluster_sums(data, labels, components, chunk_size, callback, phase):
    import torch

    sums = torch.zeros((components, data.shape[1]), dtype=data.dtype, device=data.device)
    counts = torch.zeros(components, dtype=torch.int64, device=data.device)
    component_ids = torch.arange(components, device=data.device)
    for start in range(0, len(data), chunk_size):
        _work(callback, phase)
        part = data[start:start + chunk_size]
        membership = (labels[start:start + len(part), None] == component_ids).to(data.dtype)
        # Fixed chunk order and dense reductions avoid floating atomic scatter-add.
        counts += membership.sum(dim=0, dtype=torch.int64)
        sums += membership.T @ part
    _finite(sums)
    if bool((counts == 0).any()):
        raise ValueError("empty component in strict unrepaired initialization")
    return sums, counts


def initialize_native_mixture(rows, *, row_ids, config, seed, torch_seed, device, bounded_work=None):
    """One fitting-only Lloyd run, rejecting empties at every assignment.

    Rows are already in model coordinates. Column moments used for clustering
    never become another persisted normalization. This operation makes no data
    access, recipe, timing, seed-replacement or cluster-repair decisions.
    """
    _require_config(config)
    _work(bounded_work, "initialization.start")
    torch, *_ = _backend()
    import numpy as np

    if type(seed) is not int or seed < 0 or type(torch_seed) is not int or not 0 <= torch_seed < 2**63:
        raise ValueError("initialization requires nonnegative explicit local seeds")
    data = _data_matrix(rows, config, device)
    if (type(row_ids) is not tuple or len(row_ids) != len(data)
            or any(type(identity) is not str or not identity for identity in row_ids)
            or len(set(row_ids)) != len(row_ids) or len(data) < config.components):
        raise ValueError("initialization requires unique fitting row identities and at least K rows")
    _work(bounded_work, "initialization.loaded")
    mean, divisors = _population_moments(data, config.initialization_chunk_size, bounded_work)
    standardized = (data - mean) / divisors
    _finite(standardized)
    generator = np.random.PCG64(seed)
    torch_generator = torch.Generator(device=data.device).manual_seed(torch_seed)
    pool = list(range(len(data)))
    for i in range(config.components):
        j = i + _randbelow(generator, len(data) - i)
        pool[i], pool[j] = pool[j], pool[i]
    chosen = tuple(pool[:config.components])
    centers = standardized[list(chosen)].clone()
    displacements = []
    stop_reason = "iteration_cap"
    chunk_size = config.initialization_chunk_size
    for _ in range(config.lloyd_max_iterations):
        labels = _assign_clusters(standardized, centers, chunk_size, bounded_work,
                                  "initialization.lloyd.assignment")
        sums, counts = _cluster_sums(standardized, labels, config.components, chunk_size,
                                     bounded_work, "initialization.lloyd.reduction")
        updated = sums / counts[:, None]
        displacement = ((updated - centers) ** 2).sum()
        _finite(updated, displacement)
        displacements.append(float(displacement))
        centers = updated
        if float(displacement) <= config.lloyd_tolerance:
            stop_reason = "converged"
            break
    labels = _assign_clusters(standardized, centers, chunk_size, bounded_work,
                              "initialization.final_assignment")
    sums, counts = _cluster_sums(data, labels, config.components, chunk_size, bounded_work,
                                 "initialization.final_moments")
    component_means = sums / counts[:, None]
    # Population spreads are centered in the persisted coordinates, not inferred
    # by subtracting two large raw second moments or copied from standardized data.
    squared_deviations = torch.empty_like(data)
    for start in range(0, len(data), chunk_size):
        _work(bounded_work, "initialization.component_variance")
        part = data[start:start + chunk_size]
        squared_deviations[start:start + len(part)] = (part - component_means[labels[start:start + len(part)]]) ** 2
    variance_sums, _ = _cluster_sums(squared_deviations, labels, config.components, chunk_size,
                                    bounded_work, "initialization.variance_reduction")
    gaussian = list(config.gaussian_indices)
    binary = list(config.bernoulli_indices)
    floors = torch.tensor(config.gaussian_floors, dtype=torch.float64, device=data.device)
    scales = torch.maximum((variance_sums[:, gaussian] / counts[:, None]).sqrt(), floors * (1 + 1e-6))
    probabilities = (sums[:, binary] + 0.5) / (counts[:, None] + 1)
    _finite(scales, probabilities)
    _work(bounded_work, "initialization.model")
    model = _build_mixture(config, means=component_means[:, gaussian], scales=scales,
                           probabilities=probabilities, weights=counts.to(torch.float64) / len(data),
                           device=data.device)
    model._native_numpy_rng = generator
    model._native_torch_generator = torch_generator
    _work(bounded_work, "initialization.complete")
    evidence = MappingProxyType({
        "initial_row_indices": chosen, "initial_row_ids": tuple(row_ids[i] for i in chosen),
        "temporary_means": tuple(mean.cpu().tolist()), "temporary_divisors": tuple(divisors.cpu().tolist()),
        "component_counts": tuple(counts.cpu().tolist()), "iterations": len(displacements),
        "displacements": tuple(displacements), "stop_reason": stop_reason,
        "seed": seed, "torch_seed": torch_seed,
    })
    return model, evidence


def _model_parameters(model, config):
    _require_config(config)
    torch, _, Normal, Product, Sum = _backend()
    if (not isinstance(model, Sum) or not isinstance(model.inputs, Product)
            or getattr(model, "_native_config", None) != config
            or model.inputs.out_shape.channels != config.components):
        raise ValueError("model and explicit native configuration do not match")
    parameters = tuple(model.parameters())
    if not parameters or any(parameter.dtype != torch.float64 for parameter in parameters):
        raise ValueError("native model parameters must use float64")
    _finite(*parameters, *model.buffers())
    floors = dict(zip(config.gaussian_indices, config.gaussian_floors))
    for node in model.modules():
        if isinstance(node, Normal):
            index = int(node.scope.query[0])
            if index not in floors:
                raise ValueError("Gaussian leaf is outside the declared schema")
            parametrizations = getattr(node, "parametrizations", None)
            if (parametrizations is None or "log_scale" not in parametrizations
                    or len(parametrizations.log_scale) != 1
                    or float(parametrizations.log_scale[0].floor) != floors[index]):
                raise ValueError("Gaussian floor state differs from the declared configuration")
            scale = node.scale
            _finite(scale)
            # Only the documented exp(log(sigma)) round trip receives an ULP allowance.
            if (bool((scale <= 0).any())
                    or bool((scale < floors[index] - 8 * math.ulp(floors[index])).any())):
                raise FloatingPointError("Gaussian width breaches its declared floor")
    return parameters


def _root_values(model, data):
    values = model.log_likelihood(data)
    if values.shape[0] != len(data) or values.numel() != len(data):
        raise ValueError("native mixture must return exactly one root per row")
    values = values.reshape(-1)
    _finite(values)
    return values


def _log_values(model, data, config):
    import torch

    joint = _root_values(model, data)
    zero = torch.full_like(data, torch.nan)
    zero[:, list(config.conditioning_indices)] = data[:, list(config.conditioning_indices)]
    zero[:, config.target_index] = 0
    one = zero.clone()
    one[:, config.target_index] = 1
    l0, l1 = _root_values(model, zero), _root_values(model, one)
    denominator = torch.logaddexp(l0, l1)
    log_zero, log_one = l0 - denominator, l1 - denominator
    conditional = torch.where(data[:, config.target_index] == 1, log_one, log_zero)
    _finite(denominator, log_zero, log_one, conditional)
    if bool((log_zero > 0).any()) or bool((log_one > 0).any()):
        raise FloatingPointError("conditional log probabilities cannot be positive")
    if not bool(torch.allclose(log_zero.exp() + log_one.exp(), torch.ones_like(log_zero),
                               atol=1e-10, rtol=0)):
        raise FloatingPointError("conditional probabilities lost numerical normalization")
    return {"joint_log": joint, "conditional_log": conditional,
            "log_probability_zero": log_zero, "log_probability_one": log_one}


def native_joint_conditional_log_values(model, rows, *, config):
    """Differentiable joint and binary conditional logs from the same genuine SPN."""
    parameters = _model_parameters(model, config)
    data = _data_matrix(rows, config, parameters[0].device)
    return _log_values(model, data, config)


def _finite_optimizer_state(optimizer):
    import torch

    for state in optimizer.state.values():
        for value in state.values():
            if isinstance(value, torch.Tensor):
                _finite(value)
            elif isinstance(value, Real) and not math.isfinite(value):
                raise FloatingPointError("optimizer state contains nonfinite values")


def _validate_optimizer(optimizer, parameters):
    import torch

    if type(optimizer) is not torch.optim.Adam or len(optimizer.param_groups) != 1:
        raise ValueError("native full gradients require one fixed Adam parameter group")
    attached = tuple(p for group in optimizer.param_groups for p in group["params"])
    if tuple(map(id, attached)) != tuple(map(id, parameters)):
        raise ValueError("optimizer parameters must match the native model exactly once")
    settings = {"betas": (0.9, 0.999), "eps": 1e-8, "weight_decay": 0,
                "amsgrad": False, "foreach": False, "fused": False,
                "maximize": False, "capturable": False, "differentiable": False,
                "decoupled_weight_decay": False}
    for group in optimizer.param_groups:
        if any(group.get(key, False if key == "decoupled_weight_decay" else None) != value
               for key, value in settings.items()):
            raise ValueError("optimizer settings differ from the fixed native Adam policy")
        lr = group.get("lr")
        if not isinstance(lr, Real) or isinstance(lr, bool) or not math.isfinite(lr) or lr <= 0:
            raise ValueError("optimizer learning rate must be finite and positive")
    _finite_optimizer_state(optimizer)
    parameter_ids = {id(parameter) for parameter in parameters}
    for parameter, state in optimizer.state.items():
        if id(parameter) not in parameter_ids:
            raise ValueError("optimizer state refers to an unknown parameter")
        if not state:
            continue
        if set(state) != {"step", "exp_avg", "exp_avg_sq"}:
            raise ValueError("optimizer state must contain exactly the fixed Adam moments")
        step = state["step"]
        if (not isinstance(step, torch.Tensor) or step.numel() != 1
                or float(step) < 1 or not float(step).is_integer()):
            raise ValueError("optimizer step must be a positive integer scalar")
        for key in ("exp_avg", "exp_avg_sq"):
            moment = state[key]
            if (not isinstance(moment, torch.Tensor) or moment.shape != parameter.shape
                    or moment.dtype != torch.float64):
                raise ValueError("optimizer moment does not match its parameter")
        if bool((state["exp_avg_sq"] < 0).any()):
            raise ValueError("Adam squared moments cannot be negative")


def native_full_gradient_step(model, optimizer, chunks, *, config, total_rows,
                              conditional_weight, learning_rate, bounded_work=None):
    """One correctly weighted full gradient, one global clip and one Adam update.

    Every chunk contributes its sum divided by the declared fitting-row count.
    Diagnostics describe pre-update parameters; the caller owns update indices,
    validation, checkpoint selection, deadlines and any terminal classification.
    """
    import torch

    _work(bounded_work, "gradient.start")
    parameters = _model_parameters(model, config)
    _validate_optimizer(optimizer, parameters)
    if type(total_rows) is not int or total_rows <= 0:
        raise ValueError("full-gradient row count must be a positive integer")
    for value, strictly_positive in ((conditional_weight, False), (learning_rate, True)):
        if (not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(value)
                or value < 0 or (strictly_positive and value == 0)):
            raise ValueError("loss weight and learning rate must be finite and within their declared domains")
    optimizer.zero_grad(set_to_none=True)
    observed_rows = 0
    joint_terms, conditional_terms = [], []
    for rows in chunks:
        _work(bounded_work, "gradient.chunk")
        data = _data_matrix(rows, config, parameters[0].device)
        observed_rows += len(data)
        if observed_rows > total_rows:
            raise ValueError("fitting chunks exceed their declared row count")
        values = _log_values(model, data, config)
        joint = -values["joint_log"].sum() / total_rows
        conditional = -values["conditional_log"].sum() / total_rows
        loss = joint + conditional_weight * conditional
        _finite(joint, conditional, loss)
        joint_terms.append(float(joint.detach()))
        conditional_terms.append(float(conditional.detach()))
        loss.backward()
    if observed_rows != total_rows:
        raise ValueError("fitting chunks do not cover their declared row count")
    try:
        joint_nll, conditional_nll = math.fsum(joint_terms), math.fsum(conditional_terms)
        total_loss = joint_nll + conditional_weight * conditional_nll
    except OverflowError:
        raise FloatingPointError("aggregate native loss is nonfinite") from None
    if not all(math.isfinite(value) for value in (joint_nll, conditional_nll, total_loss)):
        raise FloatingPointError("aggregate native loss is nonfinite")
    gradients = tuple(parameter.grad for parameter in parameters if parameter.grad is not None)
    if not gradients:
        raise FloatingPointError("native objective produced no parameter gradients")
    _finite(*gradients)
    try:
        gradient_norm = torch.nn.utils.clip_grad_norm_(parameters, 10, error_if_nonfinite=True, foreach=False)
    except RuntimeError as error:
        if "non-finite" in str(error):
            raise FloatingPointError("native gradient norm is nonfinite") from None
        raise
    _finite(gradient_norm, *gradients)
    _work(bounded_work, "gradient.before_step")
    for group in optimizer.param_groups:
        group["lr"] = float(learning_rate)
    optimizer.step()
    _model_parameters(model, config)
    _finite_optimizer_state(optimizer)
    _work(bounded_work, "gradient.complete")
    return {"joint_nll": joint_nll, "conditional_nll": conditional_nll,
            "loss": total_loss,
            "gradient_norm": float(gradient_norm), "rows": total_rows, "updates": 1}


def _copy_native_state(value):
    """Detached CPU tensors and plain containers; no live modules or pickle hooks."""
    import torch

    if isinstance(value, torch.Tensor):
        _finite(value)
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        if any(type(key) not in (str, int) for key in value):
            raise ValueError("native state keys must be strings or integer parameter IDs")
        return {key: _copy_native_state(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return type(value)(_copy_native_state(item) for item in value)
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("native state contains unsupported or nonfinite values")


def capture_native_training_state(model, optimizer, *, config):
    """Capture only model, Adam and local RNG continuation; the caller owns its ledger."""
    import numpy as np
    import torch

    parameters = _model_parameters(model, config)
    _validate_optimizer(optimizer, parameters)
    numpy_rng = getattr(model, "_native_numpy_rng", None)
    torch_rng = getattr(model, "_native_torch_generator", None)
    if not isinstance(numpy_rng, np.random.PCG64) or not isinstance(torch_rng, torch.Generator):
        raise ValueError("native continuation requires the model's actual local RNG states")
    if torch_rng.device != parameters[0].device:
        raise ValueError("model and local Torch generator must use the same device")
    return _copy_native_state({
        "kind": "native-mixture-training-state", "version": 1,
        "config": config.to_dict(), "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "rng_state": {"numpy": numpy_rng.state, "torch": torch_rng.get_state(),
                      "torch_device_type": torch_rng.device.type},
    })


def _validate_native_state_contract(state, config):
    _require_config(config)
    expected_keys = {"kind", "version", "config", "model_state", "optimizer_state", "rng_state"}
    if (type(state) is not dict or state.keys() != expected_keys
            or state["kind"] != "native-mixture-training-state"
            or type(state["version"]) is not int or state["version"] != 1):
        raise ValueError("not a supported native training state")
    if TPMNativeMixtureConfig.from_dict(state["config"]) != config:
        raise ValueError("native training state belongs to another model contract")


def _restore_native_model(model_state, config, device):
    torch, *_ = _backend()
    k, g, b = config.components, len(config.gaussian_indices), len(config.bernoulli_indices)
    # These placeholders only establish shape and parametrizations. No random
    # draw, fitting row, clustering operation or budget decision occurs here.
    floors = torch.tensor(config.gaussian_floors, dtype=torch.float64, device=device)
    model = _build_mixture(
        config, means=torch.zeros((k, g), dtype=torch.float64, device=device),
        scales=(floors + torch.maximum(floors * 1e-6, torch.ones_like(floors))).expand(k, g),
        probabilities=torch.full((k, b), 0.5, dtype=torch.float64, device=device),
        weights=torch.full((k,), 1 / k, dtype=torch.float64, device=device), device=device,
    )
    expected = model.state_dict()
    if type(model_state) is not dict or model_state.keys() != expected.keys():
        raise ValueError("native model state has missing or unexpected entries")
    for key, value in model_state.items():
        if (not isinstance(value, torch.Tensor) or value.shape != expected[key].shape
                or value.dtype != expected[key].dtype):
            raise ValueError("native model state has an incompatible tensor")
    model.load_state_dict(model_state, strict=True)
    return model


def restore_native_mixture_for_inference(state, *, config, device="cpu"):
    """Load saved density parameters on the requested inference device.

    This is not a training continuation: Adam and local training RNG state are
    neither restored nor changed. No fitting, random draws or parameter-space
    conversion occurs. Caller-owned checkpoint tensors remain independent.
    """
    _validate_native_state_contract(state, config)
    model = _restore_native_model(state["model_state"], config, device)
    _model_parameters(model, config)
    return model.eval().requires_grad_(False)


def restore_native_training_state(state, *, config, device):
    """Rebuild the declared parametrizations and load state without initialization.

    A checkpoint may move between devices of the same backend type. CPU and CUDA
    generators have different algorithms/state formats; changing backend is not
    equivalent continuation and is rejected rather than reseeded.
    """
    _validate_native_state_contract(state, config)
    torch, *_ = _backend()
    import numpy as np

    state = _copy_native_state(state)
    rng = state["rng_state"]
    device = torch.device(device)
    if (type(rng) is not dict or rng.keys() != {"numpy", "torch", "torch_device_type"}
            or rng["torch_device_type"] != device.type):
        raise ValueError("native RNG state does not match the requested backend")
    if (type(rng["numpy"]) is not dict or rng["numpy"].get("bit_generator") != "PCG64"
            or not isinstance(rng["torch"], torch.Tensor)
            or rng["torch"].dtype != torch.uint8 or rng["torch"].ndim != 1):
        raise ValueError("native RNG state is malformed")
    try:
        numpy_rng = np.random.PCG64(0)
        numpy_rng.state = rng["numpy"]
        torch_rng = torch.Generator(device=device)
        torch_rng.set_state(rng["torch"])
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        raise ValueError("native RNG state cannot be restored") from error
    model = _restore_native_model(state["model_state"], config, device)
    model._native_numpy_rng, model._native_torch_generator = numpy_rng, torch_rng
    optimizer_state = state["optimizer_state"]
    if (type(optimizer_state) is not dict or optimizer_state.keys() != {"state", "param_groups"}
            or type(optimizer_state["state"]) is not dict
            or type(optimizer_state["param_groups"]) is not list
            or len(optimizer_state["param_groups"]) != 1):
        raise ValueError("native continuation requires one complete Adam parameter group")
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, betas=(0.9, 0.999), eps=1e-8,
                                 weight_decay=0, amsgrad=False, foreach=False, fused=False)
    try:
        optimizer.load_state_dict(optimizer_state)
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        raise ValueError("native Adam state cannot be restored") from error
    _validate_optimizer(optimizer, _model_parameters(model, config))
    return model, optimizer


def materialize_native_mixture(model):
    """Independent ordinary SPFlow inference graph with identical effective parameters."""
    config = getattr(model, "_native_config", None)
    parameters = _model_parameters(model, config)
    torch, Bernoulli, Normal, Product, Sum = _backend()
    source_leaves = {int(node.scope.query[0]): node for node in model.modules()
                     if isinstance(node, (Normal, Bernoulli))}
    leaves = []
    with torch.no_grad():
        for index in range(config.feature_count):
            source = source_leaves[index]
            if index in config.gaussian_indices:
                leaf = Normal(scope=[index], loc=source.loc.detach().clone(),
                              scale=source.scale.detach().clone())
                leaf.log_scale.copy_(source.log_scale)
            else:
                leaf = Bernoulli(scope=[index], logits=source.logits.detach().clone())
            leaves.append(leaf)
        # Copy logits, not softmax/sigmoid outputs that may underflow to 0 or 1.
        result = Sum(inputs=Product(leaves), weights=torch.full_like(model.logits, 1 / config.components))
        result = result.to(dtype=torch.float64, device=parameters[0].device)
        result.logits.copy_(model.logits)
    _finite(*result.parameters(), *result.buffers())
    return result


def export_native_mixture_scalar(model):
    """Export a fitted native mixture as independent scalar compiler branches.

    The density and feature order are unchanged. Effective Gaussian widths and
    raw Bernoulli/root logits are copied directly, avoiding probability rounding
    at extreme logits. Native training/materialization defaults remain vectorized.
    """
    config = getattr(model, "_native_config", None)
    parameters = _model_parameters(model, config)
    torch, Bernoulli, Normal, Product, Sum = _backend()
    source_leaves = {int(node.scope.query[0]): node for node in model.modules()
                     if isinstance(node, (Normal, Bernoulli))}
    branches = []
    with torch.no_grad():
        for component in range(config.components):
            leaves = []
            for index in range(config.feature_count):
                source = source_leaves[index]

                def scalar(value):
                    return value[:, component:component + 1, :].detach().clone()

                if index in config.gaussian_indices:
                    leaf = Normal(scope=[index], loc=scalar(source.loc), scale=scalar(source.scale))
                    leaf.log_scale.copy_(scalar(source.log_scale))
                else:
                    leaf = Bernoulli(scope=[index], logits=scalar(source.logits))
                leaves.append(leaf)
            branches.append(Product(leaves))
        result = Sum(inputs=branches, weights=torch.full_like(model.logits.reshape(-1),
                                                              1 / config.components))
        result = result.to(dtype=torch.float64, device=parameters[0].device)
        result.logits.copy_(model.logits.reshape(result.logits.shape))
    _finite(*result.parameters(), *result.buffers())
    return result
