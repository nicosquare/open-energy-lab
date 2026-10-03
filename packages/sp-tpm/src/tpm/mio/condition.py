"""Condition compiled MIO payloads on fixed evidence and compact the graph."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence

from .._graph import memoized_acyclic
from .._io import canonical_json_bytes
from ._common import _sequence_of_mappings


def condition_compiled_spflow_mio(
    compiled: Mapping[str, object],
    *,
    decision_features: Sequence[str],
    event_target_name: str,
    event_value_index: int | None,
    compatibility_mode: str | None = None,
) -> dict[str, object]:
    """Derive one event-fixed or event-marginalized serialized circuit.

    The default feature-016 representation uses an exact ``log_one`` node and
    removes normalized subcircuits that have become fully marginalized before
    a Sum approximation is selected. ``planning-v1`` preserves the established
    planning payload vocabulary while delegating the transformation itself to
    this TPM-owned primitive.
    """

    if not isinstance(compiled, Mapping):
        raise TypeError("compiled MIO payload must be a mapping")
    if compatibility_mode not in {None, "planning-v1"}:
        raise ValueError("compatibility_mode must be None or 'planning-v1'")
    event_target = str(event_target_name)
    if not event_target:
        raise ValueError("event_target_name must be nonempty")
    if event_value_index is not None and (
        isinstance(event_value_index, bool) or event_value_index not in (0, 1)
    ):
        raise ValueError("event_value_index must be 0, 1, or None")
    retained = tuple(str(name) for name in decision_features)
    if not retained or any(not name for name in retained):
        raise ValueError("decision_features must contain nonempty names")
    if len(set(retained)) != len(retained):
        raise ValueError("decision_features must be unique")
    if event_target in retained:
        raise ValueError("event target cannot also be a retained decision feature")

    feature_schema = _sequence_of_mappings(
        compiled.get("feature_schema"), field_name="feature_schema"
    )
    feature_names = tuple(str(spec.get("feature_name", "")) for spec in feature_schema)
    if any(not name for name in feature_names) or len(set(feature_names)) != len(
        feature_names
    ):
        raise ValueError("compiled feature_schema must use unique nonempty names")
    unknown_decisions = [name for name in retained if name not in feature_names]
    if unknown_decisions:
        raise ValueError(
            "compiled MIO decision feature does not exist: "
            + ", ".join(unknown_decisions)
        )
    if event_target not in feature_names:
        raise ValueError(f"compiled MIO event target {event_target!r} does not exist")
    event_spec = feature_schema[feature_names.index(event_target)]
    event_ordering = tuple(
        event_spec.get("ordering") or event_spec.get("discrete_values") or ()
    )
    if event_spec.get("feature_type") != "binary" or len(event_ordering) != 2:
        raise ValueError("compiled MIO event target must have a declared binary ordering")

    raw_nodes = _sequence_of_mappings(compiled.get("nodes"), field_name="nodes")
    source_nodes = {int(node["id"]): node for node in raw_nodes}
    if len(source_nodes) != len(raw_nodes):
        raise ValueError("compiled MIO nodes must use unique integer ids")
    root_id = int(compiled.get("root_id", -1))
    if root_id not in source_nodes:
        raise ValueError(f"compiled MIO root node {root_id} does not exist")

    output_nodes: list[dict[str, object]] = []

    def append(node: Mapping[str, object]) -> int:
        node_id = len(output_nodes)
        output_nodes.append({"id": node_id, **dict(node)})
        return node_id

    def log_one() -> int:
        if compatibility_mode == "planning-v1":
            return append(
                {
                    "type": "leaf_binary",
                    "feature_name": "__marginalized_constant__",
                    "densities": [1.0, 1.0],
                    "fixed_value": 0,
                }
            )
        return append({"type": "log_one", "log_value": 0.0})

    def is_exact_log_one(node_id: int) -> bool:
        return (
            compatibility_mode is None
            and output_nodes[node_id].get("type") == "log_one"
        )

    def product(children: Sequence[int]) -> int:
        normalized = tuple(int(child) for child in children)
        if compatibility_mode is None:
            normalized = tuple(
                child for child in normalized if not is_exact_log_one(child)
            )
        if not normalized:
            return log_one()
        if len(normalized) == 1:
            return normalized[0]
        return append({"type": "product", "children": list(normalized)})

    def transform_node(source_id: int) -> int:
        source = source_nodes[source_id]
        node_type = str(source.get("type", ""))
        if node_type == "normal":
            retained_leaves: list[int] = []
            for curve in _sequence_of_mappings(
                source.get("curves"), field_name=f"normal node {source_id} curves"
            ):
                feature_name = str(curve.get("feature_name", ""))
                if feature_name not in retained:
                    continue
                curve_payload = {
                    str(key): value
                    for key, value in curve.items()
                    if key not in {"feature_name"}
                }
                retained_leaves.append(
                    append(
                        {
                            "type": "leaf_piecewise",
                            "feature_name": feature_name,
                            **curve_payload,
                        }
                    )
                )
            result = product(retained_leaves)
        elif node_type in {"bernoulli", "categorical"}:
            scoped_names = tuple(str(name) for name in source.get("feature_names", ()))
            probabilities = source.get("probabilities")
            if not _is_sequence_value(probabilities):
                raise ValueError(
                    f"compiled MIO {node_type} node {source_id} probabilities must be a sequence"
                )
            retained_leaves = []
            for index, feature_name in enumerate(scoped_names):
                if index >= len(probabilities) or not _is_sequence_value(
                    probabilities[index]
                ):
                    raise ValueError(
                        f"compiled MIO {node_type} node {source_id} probabilities do not align"
                    )
                density_row = [float(value) for value in probabilities[index]]
                leaf_type = (
                    "leaf_binary" if node_type == "bernoulli" else "leaf_categorical"
                )
                if feature_name in retained:
                    retained_leaves.append(
                        append(
                            {
                                "type": leaf_type,
                                "feature_name": feature_name,
                                "densities": density_row,
                            }
                        )
                    )
                elif feature_name == event_target and event_value_index is not None:
                    if node_type != "bernoulli":
                        raise ValueError("conditional event target must use a Bernoulli leaf")
                    if event_value_index >= len(density_row):
                        raise ValueError(
                            "event_value_index is outside the compiled event ordering"
                        )
                    retained_leaves.append(
                        append(
                            {
                                "type": "leaf_binary",
                                "feature_name": feature_name,
                                "densities": density_row,
                                "fixed_value": event_value_index,
                            }
                        )
                    )
            result = product(retained_leaves)
        elif node_type == "product":
            children = source.get("children")
            if not _is_sequence_value(children):
                raise ValueError(
                    f"compiled MIO product node {source_id} children must be a sequence"
                )
            result = product(tuple(transform(int(child)) for child in children))
        elif node_type == "sum":
            children = source.get("children")
            weights = source.get("weights")
            if not _is_sequence_value(children) or not _is_sequence_value(weights):
                raise ValueError(
                    f"compiled MIO sum node {source_id} children and weights must be sequences"
                )
            transformed = tuple(transform(int(child)) for child in children)
            normalized_weights = tuple(float(weight) for weight in weights)
            if not transformed or len(transformed) != len(normalized_weights):
                raise ValueError(
                    f"compiled MIO sum node {source_id} children and weights must align"
                )
            if any(
                not math.isfinite(weight) or weight <= 0.0
                for weight in normalized_weights
            ):
                raise ValueError(
                    f"compiled MIO sum node {source_id} weights must be finite and positive"
                )
            if compatibility_mode is None and all(
                is_exact_log_one(child) for child in transformed
            ):
                result = log_one()
            else:
                result = append(
                    {
                        "type": "sum",
                        "children": list(transformed),
                        "weights": list(normalized_weights),
                    }
                )
        else:
            raise ValueError(
                f"compiled MIO node {source_id} has unsupported type {node_type!r}"
            )
        return result

    transform = memoized_acyclic(
        transform_node,
        cycle_message="compiled MIO nodes must form an acyclic graph",
        nodes=source_nodes,
        missing_message="compiled MIO node {node_id} does not exist",
    )
    conditioned_root = transform(root_id)
    compact_root, compact_nodes = _compact_conditioned_graph(
        conditioned_root, output_nodes
    )
    if compatibility_mode == "planning-v1":
        return {"root_id": compact_root, "nodes": compact_nodes}

    source_payload = {
        "schema_version": compiled.get("schema_version"),
        "compiler_version": compiled.get("compiler_version"),
        "root_id": root_id,
        "nodes": [dict(node) for node in raw_nodes],
        "feature_schema": [dict(spec) for spec in feature_schema],
        "fitted_artifact": dict(compiled.get("fitted_artifact", {})),
    }
    source_digest = hashlib.sha256(canonical_json_bytes(source_payload)).hexdigest()
    marginalized = [
        name for name in feature_names if name not in retained and name != event_target
    ]
    return {
        "root_id": compact_root,
        "nodes": compact_nodes,
        "conditioning": {
            "decision_features": list(retained),
            "event_target_name": event_target,
            "event_treatment": (
                "marginalized" if event_value_index is None else "fixed"
            ),
            "event_value_index": event_value_index,
            "marginalized_features": marginalized,
        },
        "source_model": {
            "schema_version": compiled.get("schema_version"),
            "compiler_version": compiled.get("compiler_version"),
            "source_root_id": root_id,
            "model_digest": source_digest,
            "fitted_artifact": dict(compiled.get("fitted_artifact", {})),
        },
    }


def _compact_conditioned_graph(
    root_id: int,
    nodes: Sequence[Mapping[str, object]],
) -> tuple[int, list[dict[str, object]]]:
    """Remove superseded simplification nodes and assign stable postorder ids."""

    node_by_id = {int(node["id"]): node for node in nodes}
    order: list[int] = []

    def visit_node(node_id: int) -> None:
        children = node_by_id[node_id].get("children", ())
        if not _is_sequence_value(children):
            raise ValueError("conditioned circuit children must be a sequence")
        for child in children:
            visit(int(child))
        order.append(node_id)

    visit = memoized_acyclic(
        visit_node,
        cycle_message="conditioned circuit nodes must form an acyclic graph",
        nodes=node_by_id,
        missing_message="conditioned circuit node {node_id} does not exist",
    )
    visit(root_id)
    remap = {old_id: new_id for new_id, old_id in enumerate(order)}
    compact: list[dict[str, object]] = []
    for old_id in order:
        source = dict(node_by_id[old_id])
        source["id"] = remap[old_id]
        if "children" in source:
            source["children"] = [remap[int(child)] for child in source["children"]]
        compact.append(source)
    return remap[root_id], compact


def _is_sequence_value(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )
