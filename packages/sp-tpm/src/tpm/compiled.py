"""Compiled evaluation of learned SPFlow SPNs for training and batch queries.

SPFlow evaluates an SPN module by module, so a learned network with hundreds of
modules costs hundreds of small kernel launches per pass whatever the batch
size. ``compile_spn_evaluator`` flattens the network once into a few operations
per depth level: all leaf densities in one tensor, then for each level one
padded gather and one sum (products) or log-sum-exp (sums). It reads the SPFlow
modules' live parameters on every call, so the SPFlow model still holds every
parameter, an optimizer over ``model.parameters()`` trains it, and the model is
saved, compiled to MIO and queried as SPFlow. Values agree with SPFlow's
``log_likelihood``; see ``check_compiled_spn_against_spflow``.

Supported networks are what ``learn_spflow_structure`` produces: Normal,
Bernoulli and Categorical leaves, Products, Sums and feature or channel
concatenation, each with one channel and one repetition. The structure is fixed
at compilation; compile again after changing it. NaN marginalizes a feature.
There are no atomic scatter-adds, so values and gradients are bitwise
repeatable on CPU and CUDA.
"""

from __future__ import annotations

import math
import weakref

__all__ = [
    "CompiledSPNEvaluator",
    "UnsupportedSPNStructureError",
    "check_compiled_spn_against_spflow",
    "compile_spn_evaluator",
]

_LEAF_KINDS = ("normal", "bernoulli", "categorical")


class UnsupportedSPNStructureError(ValueError):
    """The network uses modules or shapes the compiled evaluator does not cover."""


def _module_types():
    from spflow.modules.leaves import Bernoulli, Categorical, Normal
    from spflow.modules.ops.cat import Cat
    from spflow.modules.products import Product
    from spflow.modules.sums import Sum
    return {Normal: "normal", Bernoulli: "bernoulli", Categorical: "categorical"}, Product, Sum, Cat


def _padded(rows, pad):
    """Rectangular index table from ragged rows, padded with ``pad``."""
    import torch
    width = max((len(row) for row in rows), default=0)
    return torch.tensor([list(row) + [pad] * (width - len(row)) for row in rows], dtype=torch.long)


class CompiledSPNEvaluator:
    """Level-batched evaluator over a learned SPFlow SPN's live parameters."""

    def __init__(self, model):
        import torch
        leaf_types, Product, Sum, Cat = _module_types()
        self.leaves = {kind: [] for kind in _LEAF_KINDS}
        tokens = []      # leaf output scalars: (kind, feature)
        nodes = []       # internal nodes: ("product" | "sum", children, sum module or None)
        memo = {}

        def outputs(module):
            # Scalar outputs of a module: ("leaf", token) or ("node", index).
            if id(module) in memo:
                return memo[id(module)]
            shape, kind = module.out_shape, type(module)
            if shape.channels != 1 or shape.repetitions != 1:
                raise UnsupportedSPNStructureError("compiled SPNs require one channel and one repetition per module")
            if kind in leaf_types:
                if module.is_conditional:
                    raise UnsupportedSPNStructureError("compiled SPNs do not support conditional leaves")
                self.leaves[leaf_types[kind]].append(module)
                result = []
                for feature in module.scope.query:
                    tokens.append((leaf_types[kind], int(feature)))
                    result.append(("leaf", len(tokens) - 1))
            elif kind is Cat and module.dim == 1:
                result = [out for child in module.inputs for out in outputs(child)]
            elif kind is Product and shape.features == 1:
                nodes.append(("product", outputs(module.inputs), None))
                result = [("node", len(nodes) - 1)]
            elif kind is Sum and shape.features == 1:
                inputs = module.inputs
                children = inputs.inputs if type(inputs) is Cat and inputs.dim == 2 else [inputs]
                edges = [outputs(child) for child in children]
                if any(len(edge) != 1 for edge in edges) or tuple(module.logits.shape) != (1, len(edges), 1, 1):
                    raise UnsupportedSPNStructureError("compiled SPN sums require scalar children and one weight per child")
                nodes.append(("sum", [edge[0] for edge in edges], module))
                result = [("node", len(nodes) - 1)]
            else:
                raise UnsupportedSPNStructureError(f"compiled SPNs do not support {kind.__name__} modules here")
            memo[id(module)] = result
            return result

        root = outputs(model)
        if len(root) != 1 or root[0][0] != "node":
            raise UnsupportedSPNStructureError("compiled SPNs require a product or sum root with one output")
        self._model = weakref.ref(model)

        # Leaf units are grouped by kind so leaf densities concatenate in order.
        order = sorted(range(len(tokens)), key=lambda t: _LEAF_KINDS.index(tokens[t][0]))
        unit = {token: position for position, token in enumerate(order)}
        self._leaf_features = {kind: torch.tensor([tokens[t][1] for t in order if tokens[t][0] == kind],
                                                  dtype=torch.long) for kind in _LEAF_KINDS}
        leaf_pad = len(tokens)

        depth = []
        for _, children, _ in nodes:
            depth.append(1 + max((depth[i] if source == "node" else 0) for source, i in children))
        self._sums = [module for kind, _, module in nodes if kind == "sum"]
        sum_slot = {i: slot for slot, i in enumerate(i for i, n in enumerate(nodes) if n[0] == "sum")}
        self._sum_width = max((len(nodes[i][1]) for i in sum_slot), default=1)
        weight_pad = len(self._sums) * self._sum_width
        self._sum_positions = torch.tensor(
            [slot * self._sum_width + e for i, slot in sum_slot.items() for e in range(len(nodes[i][1]))],
            dtype=torch.long)

        position, self._levels = {}, []
        for level in sorted(set(depth)):
            node_pad, step = len(position), {}
            for kind in ("product", "sum"):
                group = [i for i, d in enumerate(depth) if d == level and nodes[i][0] == kind]
                if not group:
                    continue
                leaf_rows, node_rows, weight_rows = [], [], []
                for i in group:
                    children = list(enumerate(nodes[i][1]))
                    leaf_rows.append([(e, unit[j]) for e, (source, j) in children if source == "leaf"])
                    node_rows.append([(e, position[j]) for e, (source, j) in children if source == "node"])
                leaf_width = max(map(len, leaf_rows))
                node_width = max(map(len, node_rows))
                step[kind] = {
                    "leaf": _padded([[j for _, j in row] for row in leaf_rows], leaf_pad) if leaf_width else None,
                    "node": _padded([[j for _, j in row] for row in node_rows], node_pad) if node_width else None,
                }
                if kind == "sum":
                    # Weight slots in the same order as the gathered children.
                    for i, leafs, inner in zip(group, leaf_rows, node_rows):
                        base = sum_slot[i] * self._sum_width
                        weight_rows.append(
                            [base + e for e, _ in leafs] + [weight_pad] * (leaf_width - len(leafs))
                            + [base + e for e, _ in inner] + [weight_pad] * (node_width - len(inner)))
                    step[kind]["weight"] = _padded(weight_rows, weight_pad)
                for i in group:
                    position[i] = len(position)
            self._levels.append(step)
        self._root = position[root[0][1]]
        self._devices = {}

    @property
    def model(self):
        """The SPFlow model this evaluator reads, or None once it is released."""
        return self._model()

    def _on(self, device):
        # Index tables move to each device once.
        if device not in self._devices:
            def move(value):
                if isinstance(value, dict):
                    return {key: move(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [move(item) for item in value]
                return None if value is None else value.to(device)
            self._devices[device] = {"features": move(self._leaf_features), "levels": move(self._levels),
                                     "sum_positions": self._sum_positions.to(device)}
        return self._devices[device]

    def _leaf_log_densities(self, data, features):
        """Leaf log-densities, units x rows, as SPFlow's leaves compute them."""
        import torch
        columns, parts = data.T, []
        for kind in _LEAF_KINDS:
            if not self.leaves[kind]:
                continue
            values = columns[features[kind]]
            observed = ~torch.isnan(values)
            values = torch.where(observed, values, torch.zeros_like(values))
            if kind == "normal":
                # torch.distributions.Normal(loc, exp(log_scale)).log_prob
                loc = torch.cat([m.loc.reshape(-1) for m in self.leaves[kind]])[:, None]
                scale = torch.cat([m.log_scale.reshape(-1) for m in self.leaves[kind]]).exp()[:, None]
                density = (-((values - loc) ** 2) / (2 * scale**2) - scale.log()
                           - math.log(math.sqrt(2 * math.pi)))
            elif kind == "bernoulli":
                # torch.distributions.Bernoulli(logits=...).log_prob
                logits = torch.cat([m.logits.reshape(-1) for m in self.leaves[kind]])[:, None].expand_as(values)
                density = -torch.nn.functional.binary_cross_entropy_with_logits(logits, values, reduction="none")
            else:
                # torch.distributions.Categorical(logits=...).log_prob, padded with -inf to the widest leaf
                width = max(m.K for m in self.leaves[kind])
                tables = []
                for m in self.leaves[kind]:
                    logits = m.logits.reshape(-1, m.K)
                    logits = logits - logits.logsumexp(dim=-1, keepdim=True)
                    tables.append(torch.nn.functional.pad(logits, (0, width - m.K), value=-math.inf))
                density = torch.gather(torch.cat(tables), 1, values.long())
            parts.append(torch.where(observed, density, torch.zeros_like(density)))
        parts.append(data.new_zeros(1, len(data)))      # padding unit
        return torch.cat(parts)

    def _log_likelihood(self, data):
        import torch
        indices = self._on(data.device)
        leaf = self._leaf_log_densities(data, indices["features"])
        weights = None
        if self._sums:
            # One padded log-softmax over every sum's weights, as each Sum normalizes its own.
            logits = torch.cat([m.logits.reshape(-1) for m in self._sums])
            table = logits.new_full((len(self._sums) * self._sum_width,), -math.inf)
            table = table.index_put((indices["sum_positions"],), logits)
            weights = torch.cat([torch.log_softmax(table.view(len(self._sums), -1), dim=1).reshape(-1),
                                 logits.new_full((1,), -math.inf)])
        computed = []
        for step in indices["levels"]:
            done = torch.cat([*computed, data.new_zeros(1, len(data))])     # last row pads
            outputs = []
            for kind in ("product", "sum"):
                if kind not in step:
                    continue
                parts = [table[index] for table, index in ((leaf, step[kind]["leaf"]), (done, step[kind]["node"]))
                         if index is not None]
                if kind == "product":
                    outputs.append(sum(part.sum(dim=1) for part in parts))
                else:
                    terms = torch.cat(parts, dim=1) + weights[step[kind]["weight"]][:, :, None]
                    outputs.append(torch.logsumexp(terms, dim=1))
            computed.append(torch.cat(outputs))
        return torch.cat(computed)[self._root]

    def log_likelihood(self, data):
        """Joint log-likelihood per row, shape (rows,); NaN entries are marginalized."""
        if data.ndim != 2:
            raise ValueError("compiled SPN data must be rows x features")
        return self._log_likelihood(data)


def compile_spn_evaluator(model):
    """Compile a learned SPFlow SPN; the evaluator weakly references the model.

    ``torch.compile(evaluator.log_likelihood, dynamic=True)`` fuses it further
    (about 1.3x on a GPU at 128k rows) at the cost of a warm-up compilation.
    """
    return CompiledSPNEvaluator(model)


def check_compiled_spn_against_spflow(compiled, rows, *, tolerance=None):
    """Compare with SPFlow's ``log_likelihood``; return the max relative error.

    The error of each row is ``|compiled - spflow| / (1 + |spflow|)``. Rows may
    contain NaN to check marginal queries. The default tolerance is 1e-9 for
    float64 models and 1e-4 for float32. Raises ``FloatingPointError`` beyond it.
    """
    import torch
    model = compiled.model
    if model is None:
        raise ValueError("the compiled SPN's model was released")
    parameter = next(model.parameters())
    if tolerance is None:
        tolerance = 1e-9 if parameter.dtype == torch.float64 else 1e-4
    data = torch.as_tensor(rows, dtype=parameter.dtype, device=parameter.device)
    with torch.no_grad():
        fast = compiled.log_likelihood(data)
        reference = model.log_likelihood(data).reshape(-1)
        both_infinite = (fast == reference) & torch.isinf(reference)
        error = torch.where(both_infinite, 0.0, (fast - reference).abs() / (1 + reference.abs()))
        error = float(error.max()) if len(error) else 0.0
    if not error <= tolerance:
        raise FloatingPointError(f"compiled SPN likelihood differs from SPFlow by {error:.3g}")
    return error
