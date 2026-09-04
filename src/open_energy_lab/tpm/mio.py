"""Pyomo-facing SPN-to-MIO encoding helpers for serialized TPM payloads."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from itertools import product as cartesian_product
from pathlib import Path
from typing import Any

from .artifact import TPMArtifact, load_tpm_artifact
from .domains import (
    TPMApproximationDomain,
    TPMCompiledValidityRecord,
)
from .features import TPMFeatureSpec, dump_feature_schema, load_feature_schema
from .optional_spflow import (
    CURRENT_SPFLOW_BACKEND_GENERATION,
    REQUIRED_SPFLOW_VERSION,
    build_spn_mip_payload,
    require_spflow_backend,
)
from .piecewise import build_histogram_piecewise_points
from .piecewise import guarded_exponential_points
from .piecewise import load_piecewise_metadata


_SUM_BIG_M = 100.0
_DEFAULT_EXP_DOMAIN_FLOOR = -500.0
_LEGACY_SPFLOW_MIO_SCHEMA_VERSION = "v1"
_LEGACY_SPFLOW_MIO_COMPILER_VERSION = "spflow-v1-mio-v1"
_SPFLOW_MIO_SCHEMA_VERSION = "v2"
_SPFLOW_MIO_COMPILER_VERSION = "spflow-v1-mio-v2"
_CANONICAL_BREAKPOINT_COUNT = 5
_MINIMUM_BREAKPOINT_COUNT = 3
_DEFAULT_MIO_EPSILON = 1e-6
_SUPPORTED_SPFLOW_MODULE_TYPES = (
    "Sum",
    "Product",
    "Normal",
    "Bernoulli",
    "Categorical",
)


class UnsupportedSPFlowModuleError(ValueError):
    """Raised when a current-SPFlow graph is outside the compiler subset."""

    def __init__(
        self,
        *,
        module_type: str,
        scope: tuple[int, ...] | None,
        reason: str,
    ) -> None:
        self.module_type = str(module_type)
        self.scope = scope
        self.reason = str(reason)
        scope_label = "unknown" if scope is None else repr(scope)
        super().__init__(
            f"unsupported SPFlow module type {self.module_type!r} at scope "
            f"{scope_label}: {self.reason}"
        )


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
    cache: dict[int, int] = {}
    active: set[int] = set()

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

    def transform(source_id: int) -> int:
        if source_id in cache:
            return cache[source_id]
        if source_id in active:
            raise ValueError("compiled MIO nodes must form an acyclic graph")
        if source_id not in source_nodes:
            raise ValueError(f"compiled MIO node {source_id} does not exist")
        active.add(source_id)
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
        active.remove(source_id)
        cache[source_id] = result
        return result

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
    source_digest = hashlib.sha256(
        (
            json.dumps(
                source_payload,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
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
    active: set[int] = set()
    order: list[int] = []

    def visit(node_id: int) -> None:
        if node_id in order:
            return
        if node_id in active:
            raise ValueError("conditioned circuit nodes must form an acyclic graph")
        if node_id not in node_by_id:
            raise ValueError(f"conditioned circuit node {node_id} does not exist")
        active.add(node_id)
        children = node_by_id[node_id].get("children", ())
        if not _is_sequence_value(children):
            raise ValueError("conditioned circuit children must be a sequence")
        for child in children:
            visit(int(child))
        active.remove(node_id)
        order.append(node_id)

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


def compile_spflow_model_to_mio(
    model: object,
    *,
    feature_schema: Sequence[TPMFeatureSpec | Mapping[str, object]] | None = None,
    fitted_artifact: TPMArtifact | str | Path | Mapping[str, Any] | None = None,
    approximation_domains: Sequence[
        TPMApproximationDomain | Mapping[str, object]
    ]
    | None = None,
    breakpoint_count: int = _CANONICAL_BREAKPOINT_COUNT,
    breakpoints: Sequence[float] | None = None,
    breakpoint_overrides: Mapping[str | int, Sequence[float]] | None = None,
    breakpoint_policy: Mapping[str, object] | None = None,
    mio_epsilon: float = _DEFAULT_MIO_EPSILON,
) -> dict[str, object]:
    """Compile the supported SPFlow 1.1 subset into a solver-neutral MIO payload.

    The compiler deliberately accepts only exact current-SPFlow ``Sum``,
    ``Product``, ``Normal``, ``Bernoulli``, and ``Categorical`` module types.
    SPFlow's internal ``Cat`` adapters are unwrapped as graph edges and are not
    emitted as MIO nodes. Normal log densities are sampled on deterministic
    normalized-domain breakpoints; discrete leaves and graph composition remain
    exact.
    """

    require_spflow_backend()
    bindings = _load_spflow_mio_bindings()
    compiled_v2 = fitted_artifact is not None or approximation_domains is not None
    artifact = None if fitted_artifact is None else _load_artifact(fitted_artifact)
    if compiled_v2:
        if artifact is None:
            raise ValueError(
                "compiled-v2 requires a fitted v3 artifact; refit with declared domains"
            )
        if artifact.schema_version != "v3":
            raise ValueError(
                "compiled-v2 requires a fitted artifact with schema_version 'v3'; "
                "refit legacy evidence with declared domains"
            )
        schema = artifact.feature_specs
        if feature_schema is not None:
            supplied_schema = _resolve_compiler_feature_schema(feature_schema)
            if dump_feature_schema(
                supplied_schema,
                schema_version="v3",
            ) != dump_feature_schema(schema, schema_version="v3"):
                raise ValueError(
                    "feature_schema must exactly match the fitted v3 artifact schema"
                )
    else:
        if feature_schema is None:
            raise ValueError("feature_schema is required for compiled-v1 compatibility")
        schema = _resolve_compiler_feature_schema(feature_schema)
    resolved_policy, feature_breakpoints, resolved_epsilon = _resolve_compiler_policy(
        schema=schema,
        breakpoint_count=breakpoint_count,
        breakpoints=breakpoints,
        breakpoint_overrides=breakpoint_overrides,
        breakpoint_policy=breakpoint_policy,
        mio_epsilon=mio_epsilon,
    )
    validity_records: dict[int, TPMCompiledValidityRecord] = {}
    if compiled_v2:
        validity_records = _resolve_compiled_v2_validity(
            model=model,
            schema=schema,
            approximation_domains=approximation_domains,
            relative_breakpoints=feature_breakpoints,
        )
        feature_breakpoints = {
            index: validity.model_breakpoints
            for index, validity in validity_records.items()
        }
        resolved_policy = {
            **resolved_policy,
            "policy_name": "physical-interval-relative-v2",
            "relative_breakpoints": resolved_policy.pop("breakpoints"),
        }

    nodes: list[dict[str, object]] = []
    seen_modules: set[int] = set()

    def compile_module(module: object) -> int:
        module_scope = _spflow_module_scope(module)
        module_type = type(module).__name__
        identity = id(module)
        if identity in seen_modules:
            raise UnsupportedSPFlowModuleError(
                module_type=module_type,
                scope=module_scope,
                reason="shared subgraphs cannot be represented by the first-release compiler",
            )
        seen_modules.add(identity)

        exact_type = type(module)
        if exact_type is bindings["sum"]:
            _validate_compiler_module_shape(module, scope=module_scope)
            children = _spflow_operation_children(
                module,
                operation="sum",
                cat_class=bindings["cat"],
            )
            child_ids = tuple(compile_module(child) for child in children)
            weights = _spflow_sum_weights(module, expected_count=len(child_ids))
            node = {
                "id": len(nodes),
                "type": "sum",
                "scope": list(module_scope or ()),
                "children": list(child_ids),
                "weights": list(weights),
                "operation": "weighted_logsumexp",
            }
        elif exact_type is bindings["product"]:
            _validate_compiler_module_shape(module, scope=module_scope)
            children = _spflow_operation_children(
                module,
                operation="product",
                cat_class=bindings["cat"],
            )
            child_ids = tuple(compile_module(child) for child in children)
            node = {
                "id": len(nodes),
                "type": "product",
                "scope": list(module_scope or ()),
                "children": list(child_ids),
                "operation": "sum_log_likelihoods",
            }
        elif exact_type is bindings["normal"]:
            node = _compile_normal_leaf(
                module,
                schema=schema,
                feature_breakpoints=feature_breakpoints,
                validity_records=validity_records,
                mio_epsilon=resolved_epsilon,
            )
            node["id"] = len(nodes)
        elif exact_type is bindings["bernoulli"]:
            node = _compile_bernoulli_leaf(
                module,
                schema=schema,
                mio_epsilon=resolved_epsilon,
            )
            node["id"] = len(nodes)
        elif exact_type is bindings["categorical"]:
            node = _compile_categorical_leaf(
                module,
                schema=schema,
                mio_epsilon=resolved_epsilon,
            )
            node["id"] = len(nodes)
        else:
            supported_base = _supported_spflow_base_type(module, bindings=bindings)
            reason = (
                "custom subclasses are not supported; use the exact native module type"
                if supported_base is not None
                else "the module is outside the declared first-release compiler subset"
            )
            raise UnsupportedSPFlowModuleError(
                module_type=module_type,
                scope=module_scope,
                reason=reason,
            )

        node_id = int(node["id"])
        nodes.append(node)
        return node_id

    root_id = compile_module(model)
    root_shape = _spflow_shape(model)
    if root_shape != (1, 1, 1):
        raise UnsupportedSPFlowModuleError(
            module_type=type(model).__name__,
            scope=_spflow_module_scope(model),
            reason=(
                "the compiled root must expose exactly one feature, one output channel, "
                f"and one repetition; found shape {root_shape!r}"
            ),
        )

    schema_version = (
        _SPFLOW_MIO_SCHEMA_VERSION
        if compiled_v2
        else _LEGACY_SPFLOW_MIO_SCHEMA_VERSION
    )
    compiler_version = (
        _SPFLOW_MIO_COMPILER_VERSION
        if compiled_v2
        else _LEGACY_SPFLOW_MIO_COMPILER_VERSION
    )
    payload = {
        "schema_version": schema_version,
        "payload_format": "open-energy-lab-spflow-mio",
        "compiler_version": compiler_version,
        "backend_compiler_version": compiler_version,
        "backend_generation": CURRENT_SPFLOW_BACKEND_GENERATION,
        "backend_api_version": REQUIRED_SPFLOW_VERSION,
        "supported_module_types": list(_SUPPORTED_SPFLOW_MODULE_TYPES),
        "supported_spflow_module_types": list(_SUPPORTED_SPFLOW_MODULE_TYPES),
        "approximation_kind": "piecewise",
        "leaf_encoding_mode": "piecewise-log-density",
        "sum_encoding_mode": "weighted-logsumexp",
        "output_channels": 1,
        "num_repetitions": 1,
        "feature_schema": list(
            dump_feature_schema(
                schema,
                schema_version="v3" if compiled_v2 else "v2",
            )
        ),
        "breakpoint_policy": resolved_policy,
        "mio_epsilon": resolved_epsilon,
        "root_id": root_id,
        "nodes": nodes,
    }
    if compiled_v2:
        payload["fitted_artifact"] = {
            "artifact_id": artifact.artifact_id,
            "schema_version": artifact.schema_version,
            "payload_hash": artifact.payload_hash,
        }
        payload["compiled_validity"] = [
            validity_records[index].to_dict() for index in sorted(validity_records)
        ]
    return payload


def evaluate_compiled_spflow_probability(
    compiled: Mapping[str, object],
    *,
    normalized_evidence: Sequence[float] | Mapping[str, float] | None = None,
    physical_evidence: Sequence[object] | Mapping[str, object] | None = None,
    model_coordinate_evidence: Sequence[float] | Mapping[str, float] | None = None,
) -> float:
    """Evaluate one solver-neutral payload through its versioned evidence contract."""

    payload = _mapping(compiled, field_name="compiled")
    schema_version = payload.get("schema_version")
    if schema_version not in {
        _LEGACY_SPFLOW_MIO_SCHEMA_VERSION,
        _SPFLOW_MIO_SCHEMA_VERSION,
    }:
        raise ValueError(
            "compiled schema_version must be one of "
            f"{(_LEGACY_SPFLOW_MIO_SCHEMA_VERSION, _SPFLOW_MIO_SCHEMA_VERSION)!r}, "
            f"found {schema_version!r}"
        )
    expected_compiler_version = (
        _LEGACY_SPFLOW_MIO_COMPILER_VERSION
        if schema_version == _LEGACY_SPFLOW_MIO_SCHEMA_VERSION
        else _SPFLOW_MIO_COMPILER_VERSION
    )
    if payload.get("compiler_version") != expected_compiler_version:
        raise ValueError(
            "compiled compiler_version must be "
            f"{expected_compiler_version!r}, found {payload.get('compiler_version')!r}"
        )

    schema = load_feature_schema(
        _sequence_of_mappings(payload.get("feature_schema"), field_name="feature_schema"),
        schema_version="v3" if schema_version == _SPFLOW_MIO_SCHEMA_VERSION else "v2",
    )
    nodes = _sequence_of_mappings(payload.get("nodes"), field_name="nodes")
    if schema_version == _LEGACY_SPFLOW_MIO_SCHEMA_VERSION:
        if physical_evidence is not None or model_coordinate_evidence is not None:
            raise ValueError(
                "compiled-v1 supports normalized_evidence only and has no physical validity"
            )
        if normalized_evidence is None:
            raise ValueError("compiled-v1 requires normalized_evidence")
        evidence = _resolve_normalized_evidence(normalized_evidence, schema=schema)
    else:
        if normalized_evidence is not None:
            raise ValueError(
                "compiled-v2 requires physical_evidence or model_coordinate_evidence; "
                "normalized_evidence is the compiled-v1 compatibility path"
            )
        supplied = tuple(
            value is not None for value in (physical_evidence, model_coordinate_evidence)
        )
        if sum(supplied) != 1:
            raise ValueError(
                "compiled-v2 requires exactly one of physical_evidence or "
                "model_coordinate_evidence"
            )
        validity = _load_compiled_validity(payload)
        active_indices = _compiled_feature_indices(nodes)
        if physical_evidence is not None:
            evidence = _resolve_compiled_v2_physical_evidence(
                physical_evidence,
                schema=schema,
                active_indices=active_indices,
                validity=validity,
            )
        else:
            evidence = _resolve_compiled_v2_model_evidence(
                model_coordinate_evidence,
                schema=schema,
                active_indices=active_indices,
                validity=validity,
            )
    node_by_id = {int(node["id"]): node for node in nodes}
    if len(node_by_id) != len(nodes):
        raise ValueError("compiled nodes must use unique integer ids")
    root_id = int(payload["root_id"])
    cache: dict[int, float] = {}
    active: set[int] = set()

    def evaluate_log(node_id: int) -> float:
        if node_id in cache:
            return cache[node_id]
        if node_id in active:
            raise ValueError("compiled nodes must form an acyclic graph")
        if node_id not in node_by_id:
            raise ValueError(f"compiled node {node_id} does not exist")
        active.add(node_id)
        node = node_by_id[node_id]
        node_type = str(node.get("type", ""))
        if node_type == "normal":
            value = _evaluate_normal_leaf(node, evidence=evidence)
        elif node_type in {"bernoulli", "categorical"}:
            value = _evaluate_discrete_leaf(node, evidence=evidence)
        elif node_type == "product":
            children = _compiled_child_ids(node)
            value = math.fsum(evaluate_log(child_id) for child_id in children)
        elif node_type == "sum":
            children = _compiled_child_ids(node)
            weights = _float_sequence(node.get("weights"))
            if len(weights) != len(children) or not weights:
                raise ValueError("compiled sum node weights must match its children")
            terms = tuple(
                evaluate_log(child_id) + math.log(weight)
                for child_id, weight in zip(children, weights, strict=True)
            )
            maximum = max(terms)
            value = maximum + math.log(math.fsum(math.exp(term - maximum) for term in terms))
        else:
            raise ValueError(f"unsupported compiled node type {node_type!r}")
        active.remove(node_id)
        cache[node_id] = value
        return value

    return math.exp(evaluate_log(root_id))


def _load_spflow_mio_bindings() -> dict[str, type]:
    leaves = import_module("spflow.modules.leaves")
    return {
        "sum": getattr(import_module("spflow.modules.sums"), "Sum"),
        "product": getattr(import_module("spflow.modules.products"), "Product"),
        "normal": getattr(leaves, "Normal"),
        "bernoulli": getattr(leaves, "Bernoulli"),
        "categorical": getattr(leaves, "Categorical"),
        "cat": getattr(import_module("spflow.modules.ops.cat"), "Cat"),
    }


def _resolve_compiler_feature_schema(
    feature_schema: Sequence[TPMFeatureSpec | Mapping[str, object]],
) -> tuple[TPMFeatureSpec, ...]:
    if isinstance(feature_schema, Mapping) or isinstance(feature_schema, (str, bytes)):
        raise TypeError("feature_schema must be a sequence of TPM feature specs or mappings")
    schema: list[TPMFeatureSpec] = []
    for index, item in enumerate(feature_schema):
        if isinstance(item, TPMFeatureSpec):
            schema.append(item)
        elif isinstance(item, Mapping):
            schema.append(TPMFeatureSpec.from_dict(item))
        else:
            raise TypeError(
                f"feature_schema[{index}] must be a TPMFeatureSpec or mapping"
            )
    if not schema:
        raise ValueError("feature_schema must not be empty")
    names = tuple(spec.feature_name for spec in schema)
    if len(set(names)) != len(names):
        raise ValueError("feature_schema feature_name values must be unique")
    return tuple(schema)


def _resolve_compiled_v2_validity(
    *,
    model: object,
    schema: Sequence[TPMFeatureSpec],
    approximation_domains: Sequence[
        TPMApproximationDomain | Mapping[str, object]
    ]
    | None,
    relative_breakpoints: Mapping[int, tuple[float, ...]],
) -> dict[int, TPMCompiledValidityRecord]:
    model_scope = _spflow_module_scope(model)
    if model_scope is None:
        raise ValueError(
            "compiled-v2 requires a model with an auditable retained feature scope"
        )
    if any(index < 0 or index >= len(schema) for index in model_scope):
        raise ValueError("compiled-v2 model scope is outside the fitted artifact schema")
    for feature_index in model_scope:
        spec = schema[feature_index]
        domain = spec.mathematical_domain
        if (
            domain is None
            or domain.origin == "omitted"
            or domain.shape == "unknown"
        ):
            raise ValueError(
                f"retained feature {spec.feature_name!r} has unknown or legacy-inferred "
                "mathematical meaning; refit or declare its domain before compiled-v2"
            )

    requests: dict[str, TPMApproximationDomain] = {}
    raw_requests: object = () if approximation_domains is None else approximation_domains
    if isinstance(raw_requests, Mapping) or isinstance(raw_requests, (str, bytes)):
        raise TypeError("approximation_domains must be a sequence")
    if not isinstance(raw_requests, Sequence):
        raise TypeError("approximation_domains must be a sequence")
    for index, item in enumerate(raw_requests):
        if isinstance(item, TPMApproximationDomain):
            request = item
        elif isinstance(item, Mapping):
            request = TPMApproximationDomain.from_dict(item)
        else:
            raise TypeError(
                f"approximation_domains[{index}] must be a TPMApproximationDomain or mapping"
            )
        if request.feature_name in requests:
            raise ValueError(
                f"duplicate approximation domain for feature {request.feature_name!r}"
            )
        requests[request.feature_name] = request

    schema_by_name = {spec.feature_name: (index, spec) for index, spec in enumerate(schema)}
    for feature_name in requests:
        if feature_name not in schema_by_name:
            raise ValueError(f"unknown approximation-domain feature {feature_name!r}")
        feature_index, spec = schema_by_name[feature_name]
        if spec.feature_type != "continuous":
            raise ValueError(
                f"approximation-domain feature {feature_name!r} must be continuous"
            )
        if feature_index not in model_scope:
            raise ValueError(
                f"approximation-domain feature {feature_name!r} is unused or marginalized"
            )

    continuous_indices = tuple(
        index for index in model_scope if schema[index].feature_type == "continuous"
    )
    validity: dict[int, TPMCompiledValidityRecord] = {}
    for feature_index in continuous_indices:
        spec = schema[feature_index]
        domain = spec.mathematical_domain
        normalization = spec.normalization
        if domain is None or normalization is None:
            raise ValueError(
                f"compiled-v2 feature {spec.feature_name!r} lacks v3 declared semantics; "
                "refit with declared domains"
            )
        if domain.origin != "caller-declared" or domain.shape == "unknown":
            raise ValueError(
                f"retained continuous feature {spec.feature_name!r} requires explicit "
                "mathematical domain semantics; unknown or legacy-inferred meaning "
                "cannot qualify compiled-v2"
            )
        if (
            spec.feature_role == "decision"
            and domain.shape == "finite"
            and domain.lower == domain.upper
        ):
            raise ValueError(
                f"fixed decision feature {spec.feature_name!r} must be fixed or conditioned "
                "before piecewise compilation"
            )
        request = requests.get(spec.feature_name)
        if request is None:
            raise ValueError(
                f"missing explicit approximation domain for retained continuous feature "
                f"{spec.feature_name!r}; no fallback is permitted"
            )
        if spec.feature_role == "decision":
            if (
                domain.purpose != "decision-domain"
                or domain.origin != "caller-declared"
                or domain.shape != "finite"
                or domain.lower is None
                or domain.upper is None
            ):
                raise ValueError(
                    f"retained continuous decision {spec.feature_name!r} requires a finite "
                    "caller-declared decision domain; refit with declared domains"
                )
            if request.lower < domain.lower or request.upper > domain.upper:
                raise ValueError(
                    f"approximation domain for {spec.feature_name!r} must lie within its "
                    f"declared decision domain [{domain.lower}, {domain.upper}]"
                )
        validity[feature_index] = request.derive_validity(
            feature_index=feature_index,
            normalization=normalization,
            relative_breakpoints=relative_breakpoints[feature_index],
            compiler_version=_SPFLOW_MIO_COMPILER_VERSION,
            payload_schema_version=_SPFLOW_MIO_SCHEMA_VERSION,
        )
    return validity


def _resolve_compiler_policy(
    *,
    schema: Sequence[TPMFeatureSpec],
    breakpoint_count: int,
    breakpoints: Sequence[float] | None,
    breakpoint_overrides: Mapping[str | int, Sequence[float]] | None,
    breakpoint_policy: Mapping[str, object] | None,
    mio_epsilon: float,
) -> tuple[dict[str, object], dict[int, tuple[float, ...]], float]:
    policy_payload = dict(breakpoint_policy or {})
    unknown_keys = set(policy_payload).difference(
        {"breakpoint_count", "breakpoints", "feature_breakpoints", "mio_epsilon"}
    )
    if unknown_keys:
        raise ValueError(
            "invalid breakpoint_policy keys: " + ", ".join(sorted(unknown_keys))
        )

    if "breakpoint_count" in policy_payload:
        policy_count = policy_payload["breakpoint_count"]
        if breakpoint_count != _CANONICAL_BREAKPOINT_COUNT and policy_count != breakpoint_count:
            raise ValueError("conflicting breakpoint_count values")
        breakpoint_count = policy_count  # type: ignore[assignment]
    if isinstance(breakpoint_count, bool) or not isinstance(breakpoint_count, int):
        raise TypeError("breakpoint_count must be an integer")
    if breakpoint_count < _MINIMUM_BREAKPOINT_COUNT:
        raise ValueError(
            f"breakpoint_count must be at least {_MINIMUM_BREAKPOINT_COUNT}"
        )

    policy_breakpoints = policy_payload.get("breakpoints")
    if policy_breakpoints is not None:
        if breakpoints is not None and tuple(policy_breakpoints) != tuple(breakpoints):
            raise ValueError("conflicting explicit breakpoints")
        breakpoints = policy_breakpoints  # type: ignore[assignment]
    if breakpoints is None:
        global_breakpoints = tuple(
            index / (breakpoint_count - 1) for index in range(breakpoint_count)
        )
    else:
        global_breakpoints = _validate_normalized_breakpoints(
            breakpoints,
            field_name="breakpoints",
        )
        if len(global_breakpoints) != breakpoint_count:
            raise ValueError("breakpoints length must equal breakpoint_count")

    policy_overrides = policy_payload.get("feature_breakpoints")
    if policy_overrides is not None:
        if not isinstance(policy_overrides, Mapping):
            raise TypeError("breakpoint_policy.feature_breakpoints must be a mapping")
        if breakpoint_overrides is not None and dict(policy_overrides) != dict(
            breakpoint_overrides
        ):
            raise ValueError("conflicting feature breakpoint overrides")
        breakpoint_overrides = policy_overrides  # type: ignore[assignment]

    if "mio_epsilon" in policy_payload:
        policy_epsilon = float(policy_payload["mio_epsilon"])
        if mio_epsilon != _DEFAULT_MIO_EPSILON and policy_epsilon != float(mio_epsilon):
            raise ValueError("conflicting mio_epsilon values")
        mio_epsilon = policy_epsilon
    resolved_epsilon = float(mio_epsilon)
    if not math.isfinite(resolved_epsilon) or not 0.0 < resolved_epsilon < 1.0:
        raise ValueError("mio_epsilon must be finite and between zero and one")

    name_to_index = {spec.feature_name: index for index, spec in enumerate(schema)}
    per_feature = {
        index: global_breakpoints
        for index, spec in enumerate(schema)
        if spec.feature_type == "continuous"
    }
    recorded_feature_overrides: dict[str, list[float]] = {}
    if breakpoint_overrides is not None:
        if not isinstance(breakpoint_overrides, Mapping):
            raise TypeError("breakpoint_overrides must be a mapping")
        for raw_key, raw_points in breakpoint_overrides.items():
            if isinstance(raw_key, bool):
                raise TypeError("breakpoint override keys must be feature names or indices")
            if isinstance(raw_key, int):
                feature_index = raw_key
            else:
                key = str(raw_key)
                if key not in name_to_index:
                    raise ValueError(f"unknown breakpoint override feature {key!r}")
                feature_index = name_to_index[key]
            if feature_index < 0 or feature_index >= len(schema):
                raise ValueError(f"unknown breakpoint override scope {feature_index}")
            spec = schema[feature_index]
            if spec.feature_type != "continuous":
                raise ValueError(
                    f"breakpoint override feature {spec.feature_name!r} must be continuous"
                )
            points = _validate_normalized_breakpoints(
                raw_points,
                field_name=f"breakpoint_overrides[{spec.feature_name!r}]",
            )
            per_feature[feature_index] = points
            recorded_feature_overrides[spec.feature_name] = list(points)

    count_overridden = breakpoint_count != _CANONICAL_BREAKPOINT_COUNT
    points_overridden = global_breakpoints != (0.0, 0.25, 0.5, 0.75, 1.0)
    has_override = count_overridden or points_overridden or bool(recorded_feature_overrides)
    explicit_overrides: dict[str, object] = {}
    if count_overridden:
        explicit_overrides["breakpoint_count"] = breakpoint_count
    if points_overridden:
        explicit_overrides["breakpoints"] = list(global_breakpoints)
    if recorded_feature_overrides:
        explicit_overrides["feature_breakpoints"] = recorded_feature_overrides

    return (
        {
            "policy_name": (
                "explicit-normalized-breakpoint-v1"
                if has_override
                else "canonical-five-breakpoint-v1"
            ),
            "canonical_breakpoint_count": _CANONICAL_BREAKPOINT_COUNT,
            "breakpoint_count": breakpoint_count,
            "breakpoints": list(global_breakpoints),
            "normalized_domain": [0.0, 1.0],
            "explicit_override": has_override,
            "explicit_overrides": explicit_overrides,
        },
        per_feature,
        resolved_epsilon,
    )


def _validate_normalized_breakpoints(
    values: object,
    *,
    field_name: str,
) -> tuple[float, ...]:
    points = _float_sequence(values)
    if len(points) < _MINIMUM_BREAKPOINT_COUNT:
        raise ValueError(
            f"{field_name} must contain at least {_MINIMUM_BREAKPOINT_COUNT} breakpoints"
        )
    if any(not math.isfinite(value) for value in points):
        raise ValueError(f"{field_name} must contain only finite breakpoints")
    if any(right <= left for left, right in zip(points, points[1:])):
        raise ValueError(f"{field_name} breakpoints must be strictly increasing")
    if points[0] != 0.0 or points[-1] != 1.0:
        raise ValueError(f"{field_name} must span the normalized domain [0.0, 1.0]")
    return points


def _spflow_module_scope(module: object) -> tuple[int, ...] | None:
    try:
        scope = getattr(module, "scope")
    except (AttributeError, RuntimeError):
        return None
    query = getattr(scope, "query", None)
    if query is None:
        return None
    try:
        return tuple(int(value) for value in query)
    except (TypeError, ValueError):
        return None


def _spflow_shape(module: object) -> tuple[int, int, int] | None:
    shape = getattr(module, "out_shape", None)
    if shape is None:
        return None
    try:
        return (int(shape.features), int(shape.channels), int(shape.repetitions))
    except (AttributeError, TypeError, ValueError):
        return None


def _validate_compiler_module_shape(
    module: object,
    *,
    scope: tuple[int, ...] | None,
    allow_multiple_features: bool = False,
) -> None:
    shape = _spflow_shape(module)
    feature_count = None if shape is None else shape[0]
    invalid_features = feature_count != 1 and not allow_multiple_features
    if shape is None or invalid_features or shape[1:] != (1, 1):
        raise UnsupportedSPFlowModuleError(
            module_type=type(module).__name__,
            scope=scope,
            reason=(
                "only one output channel and one repetition are supported"
                if shape is not None and shape[1:] != (1, 1)
                else f"unsupported module output shape {shape!r}"
            ),
        )


def _spflow_operation_children(
    module: object,
    *,
    operation: str,
    cat_class: type,
) -> tuple[object, ...]:
    inputs = getattr(module, "inputs", None)
    if inputs is None:
        raise UnsupportedSPFlowModuleError(
            module_type=type(module).__name__,
            scope=_spflow_module_scope(module),
            reason=f"{operation} module has no inputs",
        )
    if type(inputs) is cat_class:
        expected_dim = 2 if operation == "sum" else 1
        if int(getattr(inputs, "dim", -1)) != expected_dim:
            raise UnsupportedSPFlowModuleError(
                module_type=type(module).__name__,
                scope=_spflow_module_scope(module),
                reason=f"{operation} uses an unsupported Cat dimension",
            )
        children = tuple(getattr(inputs, "inputs", ()))
    else:
        children = (inputs,)
    if not children:
        raise UnsupportedSPFlowModuleError(
            module_type=type(module).__name__,
            scope=_spflow_module_scope(module),
            reason=f"{operation} module must have at least one child",
        )
    return children


def _spflow_sum_weights(module: object, *, expected_count: int) -> tuple[float, ...]:
    tensor = getattr(module, "weights", None)
    values = _tensor_values(tensor, field_name="Sum.weights")
    weights = tuple(_flatten_numeric(values))
    if len(weights) != expected_count:
        raise UnsupportedSPFlowModuleError(
            module_type=type(module).__name__,
            scope=_spflow_module_scope(module),
            reason=(
                f"sum weights contain {len(weights)} values for {expected_count} children"
            ),
        )
    if any(not math.isfinite(weight) or weight <= 0.0 for weight in weights):
        raise ValueError("SPFlow sum weights must be finite and positive")
    total = math.fsum(weights)
    if not math.isclose(total, 1.0, abs_tol=1e-9, rel_tol=0.0):
        raise ValueError("SPFlow sum weights must total one")
    return tuple(weight / total for weight in weights)


def _supported_spflow_base_type(
    module: object,
    *,
    bindings: Mapping[str, type],
) -> type | None:
    for name in ("sum", "product", "normal", "bernoulli", "categorical"):
        base = bindings[name]
        if isinstance(module, base):
            return base
    return None


def _compile_normal_leaf(
    module: object,
    *,
    schema: Sequence[TPMFeatureSpec],
    feature_breakpoints: Mapping[int, tuple[float, ...]],
    validity_records: Mapping[int, TPMCompiledValidityRecord],
    mio_epsilon: float,
) -> dict[str, object]:
    scope = _validate_leaf_scope(module, schema=schema, expected_type="continuous")
    _validate_compiler_module_shape(module, scope=scope, allow_multiple_features=True)
    _reject_conditional_leaf(module, scope=scope)
    loc = _leaf_scalar_parameters(
        getattr(module, "loc", None),
        scope=scope,
        field_name="Normal.loc",
    )
    scale = _leaf_scalar_parameters(
        getattr(module, "scale", None),
        scope=scope,
        field_name="Normal.scale",
    )
    if any(not math.isfinite(value) for value in loc):
        raise ValueError("Normal.loc values must be finite")
    if any(not math.isfinite(value) or value <= 0.0 for value in scale):
        raise ValueError("Normal.scale values must be finite and positive")

    curves: list[dict[str, object]] = []
    for feature_index, mean, deviation in zip(scope, loc, scale, strict=True):
        points = feature_breakpoints[feature_index]
        log_values = tuple(
            math.log(
                max(
                    math.exp(-0.5 * ((point - mean) / deviation) ** 2)
                    / (deviation * math.sqrt(2.0 * math.pi)),
                    mio_epsilon,
                )
            )
            for point in points
        )
        curve = {
            "scope": feature_index,
            "feature_name": schema[feature_index].feature_name,
            "breakpoints": list(points),
            "log_values": list(log_values),
        }
        if feature_index in validity_records:
            curve["physical_breakpoints"] = list(
                validity_records[feature_index].physical_breakpoints
            )
            curve["model_breakpoints"] = list(
                validity_records[feature_index].model_breakpoints
            )
        curves.append(curve)
    return {
        "type": "normal",
        "scope": list(scope),
        "feature_names": [schema[index].feature_name for index in scope],
        "loc": list(loc),
        "scale": list(scale),
        "curves": curves,
        "operation": "piecewise_log_density",
    }


def _compile_bernoulli_leaf(
    module: object,
    *,
    schema: Sequence[TPMFeatureSpec],
    mio_epsilon: float,
) -> dict[str, object]:
    scope = _validate_leaf_scope(module, schema=schema, expected_type="binary")
    _validate_compiler_module_shape(module, scope=scope, allow_multiple_features=True)
    _reject_conditional_leaf(module, scope=scope)
    success = _leaf_scalar_parameters(
        getattr(module, "probs", None),
        scope=scope,
        field_name="Bernoulli.probs",
    )
    probabilities: list[list[float]] = []
    log_probabilities: list[list[float]] = []
    for probability in success:
        if not math.isfinite(probability) or probability < 0.0 or probability > 1.0:
            raise ValueError("Bernoulli probabilities must be finite and between zero and one")
        pair = [1.0 - probability, probability]
        probabilities.append(pair)
        log_probabilities.append([math.log(max(value, mio_epsilon)) for value in pair])
    return {
        "type": "bernoulli",
        "scope": list(scope),
        "feature_names": [schema[index].feature_name for index in scope],
        "probabilities": probabilities,
        "log_probabilities": log_probabilities,
        "operation": "discrete_log_probability",
    }


def _compile_categorical_leaf(
    module: object,
    *,
    schema: Sequence[TPMFeatureSpec],
    mio_epsilon: float,
) -> dict[str, object]:
    scope = _validate_leaf_scope(module, schema=schema, expected_type="categorical")
    _validate_compiler_module_shape(module, scope=scope, allow_multiple_features=True)
    _reject_conditional_leaf(module, scope=scope)
    category_count = int(getattr(module, "K", 0))
    if category_count < 2:
        raise ValueError("Categorical.K must be at least two")
    raw = _tensor_values(getattr(module, "probs", None), field_name="Categorical.probs")
    probabilities = _categorical_parameter_rows(
        raw,
        feature_count=len(scope),
        category_count=category_count,
    )
    for feature_index, row in zip(scope, probabilities, strict=True):
        if len(schema[feature_index].ordering) != category_count:
            raise ValueError(
                f"Categorical scope {feature_index} has K={category_count}, but feature "
                f"{schema[feature_index].feature_name!r} defines "
                f"{len(schema[feature_index].ordering)} categories"
            )
        if any(not math.isfinite(value) or value < 0.0 for value in row):
            raise ValueError("Categorical probabilities must be finite and non-negative")
        if not math.isclose(math.fsum(row), 1.0, abs_tol=1e-9, rel_tol=0.0):
            raise ValueError("Categorical probabilities must total one")
    return {
        "type": "categorical",
        "scope": list(scope),
        "feature_names": [schema[index].feature_name for index in scope],
        "category_count": category_count,
        "probabilities": [list(row) for row in probabilities],
        "log_probabilities": [
            [math.log(max(value, mio_epsilon)) for value in row]
            for row in probabilities
        ],
        "operation": "discrete_log_probability",
    }


def _validate_leaf_scope(
    module: object,
    *,
    schema: Sequence[TPMFeatureSpec],
    expected_type: str,
) -> tuple[int, ...]:
    scope = _spflow_module_scope(module)
    if not scope:
        raise UnsupportedSPFlowModuleError(
            module_type=type(module).__name__,
            scope=scope,
            reason="supported leaves require a non-empty typed scope",
        )
    if len(set(scope)) != len(scope):
        raise ValueError(f"SPFlow leaf scope must not contain duplicates: {scope!r}")
    for feature_index in scope:
        if feature_index < 0 or feature_index >= len(schema):
            raise ValueError(
                f"SPFlow leaf scope {feature_index} is outside feature_schema"
            )
        actual_type = schema[feature_index].feature_type
        if actual_type != expected_type:
            raise UnsupportedSPFlowModuleError(
                module_type=type(module).__name__,
                scope=scope,
                reason=(
                    f"scope {feature_index} maps to feature_type {actual_type!r}; "
                    f"expected {expected_type!r}"
                ),
            )
    return scope


def _reject_conditional_leaf(
    module: object,
    *,
    scope: tuple[int, ...],
) -> None:
    if getattr(module, "parameter_fn", None) is not None:
        raise UnsupportedSPFlowModuleError(
            module_type=type(module).__name__,
            scope=scope,
            reason="conditional parameter networks are outside the first-release subset",
        )


def _tensor_values(value: object, *, field_name: str) -> object:
    if value is None:
        raise ValueError(f"{field_name} is required")
    detach = getattr(value, "detach", None)
    if not callable(detach):
        raise TypeError(f"{field_name} must be a tensor")
    tensor = detach()
    cpu = getattr(tensor, "cpu", None)
    if callable(cpu):
        tensor = cpu()
    tolist = getattr(tensor, "tolist", None)
    if not callable(tolist):
        raise TypeError(f"{field_name} tensor must support tolist()")
    return tolist()


def _flatten_numeric(value: object) -> list[float]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        result: list[float] = []
        for item in value:
            result.extend(_flatten_numeric(item))
        return result
    return [float(value)]


def _leaf_scalar_parameters(
    value: object,
    *,
    scope: Sequence[int],
    field_name: str,
) -> tuple[float, ...]:
    values = tuple(_flatten_numeric(_tensor_values(value, field_name=field_name)))
    if len(values) != len(scope):
        raise UnsupportedSPFlowModuleError(
            module_type=field_name.split(".", maxsplit=1)[0],
            scope=tuple(scope),
            reason=(
                f"{field_name} exposes {len(values)} values for {len(scope)} scoped features"
            ),
        )
    return values


def _categorical_parameter_rows(
    value: object,
    *,
    feature_count: int,
    category_count: int,
) -> tuple[tuple[float, ...], ...]:
    flat = tuple(_flatten_numeric(value))
    expected = feature_count * category_count
    if len(flat) != expected:
        raise ValueError(
            "Categorical.probs contains "
            f"{len(flat)} values; expected {feature_count} x {category_count}"
        )
    return tuple(
        tuple(flat[offset : offset + category_count])
        for offset in range(0, expected, category_count)
    )


def _resolve_normalized_evidence(
    normalized_evidence: Sequence[float] | Mapping[str, float],
    *,
    schema: Sequence[TPMFeatureSpec],
) -> tuple[float, ...]:
    if isinstance(normalized_evidence, Mapping):
        expected_names = tuple(spec.feature_name for spec in schema)
        missing = tuple(name for name in expected_names if name not in normalized_evidence)
        extra = tuple(str(name) for name in normalized_evidence if name not in expected_names)
        if missing or extra:
            raise ValueError(
                f"normalized_evidence keys do not match feature_schema; missing={missing!r}, "
                f"extra={extra!r}"
            )
        raw_values = tuple(normalized_evidence[name] for name in expected_names)
    else:
        raw_values = _sequence(normalized_evidence, field_name="normalized_evidence")
    if len(raw_values) != len(schema):
        raise ValueError(
            f"normalized_evidence has {len(raw_values)} values; expected {len(schema)}"
        )
    values = tuple(float(value) for value in raw_values)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("normalized_evidence must contain only finite values")
    return values


def _load_compiled_validity(
    payload: Mapping[str, object],
) -> dict[int, TPMCompiledValidityRecord]:
    records = _sequence_of_mappings(
        payload.get("compiled_validity"),
        field_name="compiled_validity",
    )
    resolved: dict[int, TPMCompiledValidityRecord] = {}
    for raw in records:
        record = TPMCompiledValidityRecord.from_dict(raw)
        if record.payload_schema_version != _SPFLOW_MIO_SCHEMA_VERSION:
            raise ValueError(
                f"compiled validity for {record.feature_name!r} has incompatible "
                f"payload schema {record.payload_schema_version!r}"
            )
        if record.compiler_version != _SPFLOW_MIO_COMPILER_VERSION:
            raise ValueError(
                f"compiled validity for {record.feature_name!r} has incompatible "
                f"compiler version {record.compiler_version!r}"
            )
        if record.feature_index in resolved:
            raise ValueError("compiled validity feature indices must be unique")
        resolved[record.feature_index] = record
    return resolved


def _compiled_feature_indices(
    nodes: Sequence[Mapping[str, object]],
) -> tuple[int, ...]:
    indices: set[int] = set()
    for node in nodes:
        node_type = str(node.get("type", ""))
        if node_type == "normal":
            for curve in _sequence_of_mappings(
                node.get("curves"),
                field_name="normal.curves",
            ):
                indices.add(int(curve["scope"]))
        elif node_type in {"bernoulli", "categorical"}:
            indices.update(
                int(value)
                for value in _sequence(node.get("scope"), field_name=f"{node_type}.scope")
            )
    return tuple(sorted(indices))


def _active_evidence_values(
    supplied: Sequence[object] | Mapping[str, object],
    *,
    field_name: str,
    schema: Sequence[TPMFeatureSpec],
    active_indices: Sequence[int],
) -> dict[int, object]:
    if isinstance(supplied, Mapping):
        active_names = tuple(schema[index].feature_name for index in active_indices)
        missing = tuple(name for name in active_names if name not in supplied)
        extra = tuple(str(name) for name in supplied if name not in active_names)
        if missing or extra:
            raise ValueError(
                f"{field_name} keys do not match retained compiled features; "
                f"missing={missing!r}, extra={extra!r}"
            )
        return {
            index: supplied[schema[index].feature_name] for index in active_indices
        }
    values = _sequence(supplied, field_name=field_name)
    if len(values) != len(schema):
        raise ValueError(
            f"{field_name} sequence has {len(values)} values; expected the full fitted "
            f"schema length {len(schema)}"
        )
    return {index: values[index] for index in active_indices}


def _resolve_compiled_v2_physical_evidence(
    supplied: Sequence[object] | Mapping[str, object],
    *,
    schema: Sequence[TPMFeatureSpec],
    active_indices: Sequence[int],
    validity: Mapping[int, TPMCompiledValidityRecord],
) -> tuple[float, ...]:
    raw_values = _active_evidence_values(
        supplied,
        field_name="physical_evidence",
        schema=schema,
        active_indices=active_indices,
    )
    coordinates = [0.0] * len(schema)
    for index, raw_value in raw_values.items():
        spec = schema[index]
        if spec.mathematical_domain is None or spec.normalization is None:
            raise ValueError(
                f"compiled-v2 feature {spec.feature_name!r} lacks persisted semantics"
            )
        spec.mathematical_domain.validate_value(raw_value)
        coordinate = float(spec.normalization.normalize_value(raw_value))
        if spec.feature_type == "continuous":
            if index not in validity:
                raise ValueError(
                    f"compiled-v2 continuous feature {spec.feature_name!r} lacks validity"
                )
            record = validity[index]
            physical = float(raw_value)
            if physical < record.physical_lower or physical > record.physical_upper:
                raise ValueError(
                    f"physical evidence for {spec.feature_name!r} is outside compiled "
                    f"validity [{record.physical_lower}, {record.physical_upper}]"
                )
            if coordinate < record.model_lower or coordinate > record.model_upper:
                raise ValueError(
                    f"derived model coordinate for {spec.feature_name!r} is outside compiled "
                    f"validity [{record.model_lower}, {record.model_upper}]"
                )
        coordinates[index] = coordinate
    return tuple(coordinates)


def _resolve_compiled_v2_model_evidence(
    supplied: Sequence[float] | Mapping[str, float] | None,
    *,
    schema: Sequence[TPMFeatureSpec],
    active_indices: Sequence[int],
    validity: Mapping[int, TPMCompiledValidityRecord],
) -> tuple[float, ...]:
    if supplied is None:
        raise ValueError("model_coordinate_evidence is required")
    raw_values = _active_evidence_values(
        supplied,
        field_name="model_coordinate_evidence",
        schema=schema,
        active_indices=active_indices,
    )
    coordinates = [0.0] * len(schema)
    for index, raw_value in raw_values.items():
        spec = schema[index]
        try:
            coordinate = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"model coordinate for {spec.feature_name!r} must be finite numeric"
            ) from exc
        if not math.isfinite(coordinate):
            raise ValueError(
                f"model coordinate for {spec.feature_name!r} must be finite numeric"
            )
        if spec.feature_type == "continuous":
            if index not in validity:
                raise ValueError(
                    f"compiled-v2 continuous feature {spec.feature_name!r} lacks validity"
                )
            record = validity[index]
            if coordinate < record.model_lower or coordinate > record.model_upper:
                raise ValueError(
                    f"model coordinate for {spec.feature_name!r} is outside compiled "
                    f"validity [{record.model_lower}, {record.model_upper}]"
                )
        else:
            if spec.normalization is None or spec.mathematical_domain is None:
                raise ValueError(
                    f"compiled-v2 feature {spec.feature_name!r} lacks persisted semantics"
                )
            physical = spec.normalization.denormalize_value(coordinate)
            spec.mathematical_domain.validate_value(physical)
        coordinates[index] = coordinate
    return tuple(coordinates)


def _compiled_child_ids(node: Mapping[str, object]) -> tuple[int, ...]:
    children = tuple(
        int(value) for value in _sequence(node.get("children"), field_name="children")
    )
    if not children:
        raise ValueError("compiled sum/product nodes must have at least one child")
    return children


def _evaluate_normal_leaf(
    node: Mapping[str, object],
    *,
    evidence: Sequence[float],
) -> float:
    curves = _sequence_of_mappings(node.get("curves"), field_name="normal.curves")
    log_likelihood = 0.0
    for curve in curves:
        feature_index = int(curve["scope"])
        point = float(evidence[feature_index])
        x_values = _float_sequence(curve.get("breakpoints"))
        y_values = _float_sequence(curve.get("log_values"))
        if len(x_values) != len(y_values):
            raise ValueError("normal curve breakpoints and log_values must have equal length")
        if point < x_values[0] or point > x_values[-1]:
            raise ValueError(
                f"normalized evidence for scope {feature_index} must be within "
                f"[{x_values[0]}, {x_values[-1]}]"
            )
        log_likelihood += _linear_interpolate(point, x_values=x_values, y_values=y_values)
    return log_likelihood


def _evaluate_discrete_leaf(
    node: Mapping[str, object],
    *,
    evidence: Sequence[float],
) -> float:
    scope = tuple(int(value) for value in _sequence(node.get("scope"), field_name="scope"))
    rows = _sequence(node.get("log_probabilities"), field_name="log_probabilities")
    if len(scope) != len(rows):
        raise ValueError("discrete leaf scope and probability rows must align")
    result = 0.0
    for feature_index, raw_row in zip(scope, rows, strict=True):
        probabilities = _float_sequence(raw_row)
        supplied = float(evidence[feature_index])
        category = int(supplied)
        if supplied != category or category < 0 or category >= len(probabilities):
            raise ValueError(
                f"normalized discrete evidence for scope {feature_index} must be one of "
                f"{tuple(range(len(probabilities)))!r}"
            )
        result += probabilities[category]
    return result


def _linear_interpolate(
    value: float,
    *,
    x_values: Sequence[float],
    y_values: Sequence[float],
) -> float:
    if value == x_values[-1]:
        return float(y_values[-1])
    for left_x, right_x, left_y, right_y in zip(
        x_values,
        x_values[1:],
        y_values,
        y_values[1:],
    ):
        if left_x <= value <= right_x:
            ratio = (value - left_x) / (right_x - left_x)
            return float(left_y) + ratio * (float(right_y) - float(left_y))
    raise ValueError("interpolation value is outside the breakpoint domain")


@dataclass(frozen=True, slots=True)
class SPNPiecewiseCurveSpec:
    x_points: tuple[float, ...]
    y_points: tuple[float, ...]
    domain_lower_bound: float
    domain_upper_bound: float
    unbounded_domain_var: bool = False


@dataclass(frozen=True, slots=True)
class SPNModelingTerms:
    approximation_kind: str
    leaf_encoding_mode: str
    sum_encoding_mode: str
    exp_curve: SPNPiecewiseCurveSpec
    log_curve: SPNPiecewiseCurveSpec
    max_terms: int
    mio_epsilon: float
    fit_numeric_tolerance: float
    query_numeric_tolerance: float


class SPNSolverDependencyUnavailableError(ImportError):
    """Raised when solving one SPN chance model requires Pyomo but it is unavailable."""


class SPNSolverUnavailableError(RuntimeError):
    """Raised when one requested solver cannot be used for SPN chance solving."""


@dataclass(frozen=True, slots=True)
class SPNSolveConfig:
    solver_name: str = "gurobi"
    numeric_tolerance: float = 1e-9
    time_limit_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class SPNSolveSummary:
    problem_id: str
    status: str
    selected_design: Mapping[str, object]
    objective_value: float | None
    estimated_event_probability: float | None
    estimated_shortfall_risk: float | None
    chance_limit_epsilon: float
    solver_metadata: Mapping[str, object]


def build_spn_chance_model(
    backend: Any,
    *,
    problem_id: str,
    spn_payload: Mapping[str, object],
    cost_terms: Mapping[str, float],
    option_costs: Mapping[str, Mapping[object, float]] | None = None,
    chance_limit_epsilon: float,
    numeric_tolerance: float,
    piecewise_terms: object,
) -> object:
    """Build one direct-design SPN chance-constrained Pyomo model."""

    conditional_models = _mapping(spn_payload.get("conditional_models"), field_name="conditional_models")
    numerator_model = _mapping(conditional_models.get("numerator_model"), field_name="conditional_models.numerator_model")
    denominator_model = _mapping(
        conditional_models.get("denominator_model"),
        field_name="conditional_models.denominator_model",
    )
    feature_schema = load_feature_schema(
        _sequence_of_mappings(
            spn_payload.get("feature_schema"),
            field_name="feature_schema",
        ),
        schema_version=str(spn_payload.get("fitted_artifact_schema_version", "v2")),
    )
    feature_by_name = {spec.feature_name: spec for spec in feature_schema}
    compiled_validity_by_name: dict[str, TPMCompiledValidityRecord] = {}
    for raw_validity in _sequence_of_mappings(
        spn_payload.get("compiled_validity", ()),
        field_name="compiled_validity",
    ):
        validity = TPMCompiledValidityRecord.from_dict(raw_validity)
        if validity.feature_name in compiled_validity_by_name:
            raise ValueError("compiled validity feature names must be unique")
        compiled_validity_by_name[validity.feature_name] = validity
    decision_features = tuple(
        str(name)
        for name in _string_sequence(
            spn_payload.get("decision_features"),
            field_name="decision_features",
        )
    )
    sum_encoding_mode = str(
        spn_payload.get("sum_encoding_mode", getattr(piecewise_terms, "sum_encoding_mode", "piecewise"))
    )
    if sum_encoding_mode not in {"max", "piecewise"}:
        raise ValueError("sum_encoding_mode must be 'max' or 'piecewise'")

    model = backend.ConcreteModel(name=f"{problem_id}-spn-mio")
    model.decision_features = backend.Set(initialize=decision_features, ordered=True)
    model._open_energy_lab_feature_by_name = feature_by_name
    model._open_energy_lab_decision_variables = {}
    model._open_energy_lab_decision_decoders = {}

    total_cost = 0.0
    resolved_option_costs = dict(option_costs or {})
    for feature_name in decision_features:
        if feature_name not in feature_by_name:
            raise ValueError(f"decision feature {feature_name!r} not present in feature_schema")
        feature_spec = feature_by_name[feature_name]
        per_option_costs = resolved_option_costs.get(feature_name)
        if per_option_costs is None and feature_name not in cost_terms:
            raise ValueError(f"missing cost definition for {feature_name!r}")
        coefficient = (
            1.0 if per_option_costs is not None else float(cost_terms[feature_name])
        )
        decision_payload = _add_decision_variable(
            backend,
            model,
            feature_spec=feature_spec,
            feature_name=feature_name,
            option_costs=per_option_costs,
            compiled_validity=compiled_validity_by_name.get(feature_name),
        )
        model._open_energy_lab_decision_variables[feature_name] = decision_payload
        model._open_energy_lab_decision_decoders[feature_name] = _decision_decoder(feature_spec)
        total_cost += coefficient * decision_payload["cost_expression"]

    if _supports_exact_categorical_lookup(
        decision_features=decision_features,
        feature_by_name=feature_by_name,
        numerator_model=numerator_model,
        denominator_model=denominator_model,
    ):
        return _build_exact_categorical_lookup_model(
            backend,
            model,
            decision_features=decision_features,
            feature_by_name=feature_by_name,
            decision_variables=model._open_energy_lab_decision_variables,
            numerator_model=numerator_model,
            denominator_model=denominator_model,
            total_cost=total_cost,
            chance_limit_epsilon=float(chance_limit_epsilon),
            sum_encoding_mode=sum_encoding_mode,
        )

    numerator_block = backend.Block()
    denominator_block = backend.Block()
    model.add_component("numerator_spn", numerator_block)
    model.add_component("denominator_spn", denominator_block)

    numerator_root = _encode_serialized_spn(
        backend,
        numerator_block,
        model=model,
        spn_model=numerator_model,
        feature_by_name=feature_by_name,
        decision_variables=model._open_energy_lab_decision_variables,
        sum_encoding_mode=sum_encoding_mode,
        piecewise_terms=piecewise_terms,
    )
    denominator_root = _encode_serialized_spn(
        backend,
        denominator_block,
        model=model,
        spn_model=denominator_model,
        feature_by_name=feature_by_name,
        decision_variables=model._open_energy_lab_decision_variables,
        sum_encoding_mode=sum_encoding_mode,
        piecewise_terms=piecewise_terms,
    )

    chance_limit_log = math.log(max(float(chance_limit_epsilon), float(numeric_tolerance)))
    model.chance_constraint = backend.Constraint(
        expr=numerator_root - denominator_root <= chance_limit_log
    )
    model.total_cost = backend.Objective(expr=total_cost, sense=backend.minimize)
    model._open_energy_lab_risk_log_numerator = numerator_root
    model._open_energy_lab_risk_log_denominator = denominator_root
    model._open_energy_lab_chance_limit_epsilon = float(chance_limit_epsilon)
    model._open_energy_lab_sum_encoding_mode = sum_encoding_mode
    return model


def _supports_exact_categorical_lookup(
    *,
    decision_features: Sequence[str],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    numerator_model: Mapping[str, object],
    denominator_model: Mapping[str, object],
) -> bool:
    if not decision_features or any(
        feature_by_name[feature_name].feature_type != "categorical"
        for feature_name in decision_features
    ):
        return False
    decision_names = set(decision_features)
    for spn_model in (numerator_model, denominator_model):
        for node in _sequence_of_mappings(
            spn_model.get("nodes"),
            field_name="spn_model.nodes",
        ):
            node_type = str(node.get("type", ""))
            if node_type not in {
                "leaf_binary",
                "leaf_categorical",
                "product",
                "sum",
            }:
                return False
            if node_type.startswith("leaf_") and "fixed_value" not in node:
                if str(node.get("feature_name", "")) not in decision_names:
                    return False
    return True


def _build_exact_categorical_lookup_model(
    backend: Any,
    model: object,
    *,
    decision_features: Sequence[str],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
    numerator_model: Mapping[str, object],
    denominator_model: Mapping[str, object],
    total_cost: object,
    chance_limit_epsilon: float,
    sum_encoding_mode: str,
) -> object:
    """Encode exact compiled-SPN risks over a finite categorical design grid."""

    category_domains = tuple(
        tuple(decision_variables[feature_name]["category_values"])
        for feature_name in decision_features
    )
    combinations = tuple(cartesian_product(*category_domains))
    risks: list[float] = []
    for combination in combinations:
        assignments = dict(zip(decision_features, combination, strict=True))
        numerator_log = _evaluate_serialized_categorical_spn(
            numerator_model,
            assignments=assignments,
            feature_by_name=feature_by_name,
        )
        denominator_log = _evaluate_serialized_categorical_spn(
            denominator_model,
            assignments=assignments,
            feature_by_name=feature_by_name,
        )
        risks.append(math.exp(min(0.0, numerator_log - denominator_log)))

    combination_ids = tuple(range(len(combinations)))
    model.categorical_combination_ids = backend.Set(
        initialize=combination_ids,
        ordered=True,
    )
    model.categorical_combination_selected = backend.Var(
        model.categorical_combination_ids,
        domain=backend.Binary,
    )
    model.categorical_combination_one_hot = backend.Constraint(
        expr=sum(
            model.categorical_combination_selected[combination_id]
            for combination_id in combination_ids
        )
        == 1
    )

    for feature_index, feature_name in enumerate(decision_features):
        decision_var = decision_variables[feature_name]["normalized_var"]
        for category_index in range(len(category_domains[feature_index])):
            matching_combinations = tuple(
                combination_id
                for combination_id, combination in enumerate(combinations)
                if combination[feature_index]
                == category_domains[feature_index][category_index]
            )
            model.add_component(
                f"categorical_combination_link_{feature_name}_{category_index}",
                backend.Constraint(
                    expr=decision_var[category_index]
                    == sum(
                        model.categorical_combination_selected[combination_id]
                        for combination_id in matching_combinations
                    )
                ),
            )

    risk_expression = sum(
        risks[combination_id]
        * model.categorical_combination_selected[combination_id]
        for combination_id in combination_ids
    )
    model.chance_constraint = backend.Constraint(
        expr=risk_expression <= chance_limit_epsilon
    )
    model.total_cost = backend.Objective(expr=total_cost, sense=backend.minimize)
    model._open_energy_lab_risk_probability = risk_expression
    model._open_energy_lab_risk_by_combination = tuple(risks)
    model._open_energy_lab_categorical_combinations = combinations
    model._open_energy_lab_chance_limit_epsilon = chance_limit_epsilon
    model._open_energy_lab_sum_encoding_mode = sum_encoding_mode
    model._open_energy_lab_risk_encoding_strategy = "exact-categorical-lookup"
    return model


def _evaluate_serialized_categorical_spn(
    spn_model: Mapping[str, object],
    *,
    assignments: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
) -> float:
    """Evaluate one conditioned compiled graph at categorical assignments."""

    nodes = _sequence_of_mappings(
        spn_model.get("nodes"),
        field_name="spn_model.nodes",
    )
    node_by_id = {int(node["id"]): node for node in nodes}
    if len(node_by_id) != len(nodes):
        raise ValueError("serialized categorical SPN nodes must use unique ids")
    cache: dict[int, float] = {}
    active: set[int] = set()

    def evaluate(node_id: int) -> float:
        if node_id in cache:
            return cache[node_id]
        if node_id in active:
            raise ValueError("serialized categorical SPN nodes must be acyclic")
        if node_id not in node_by_id:
            raise ValueError(f"serialized categorical SPN node {node_id} does not exist")
        active.add(node_id)
        node = node_by_id[node_id]
        node_type = str(node.get("type", ""))
        if node_type in {"leaf_binary", "leaf_categorical"}:
            densities = _float_sequence(node.get("densities"))
            if "fixed_value" in node:
                value_index = int(float(node["fixed_value"]))
            else:
                feature_name = str(node.get("feature_name", ""))
                if feature_name not in assignments or feature_name not in feature_by_name:
                    raise ValueError(
                        f"categorical SPN leaf requires assignment for {feature_name!r}"
                    )
                feature_spec = feature_by_name[feature_name]
                category_values = tuple(
                    feature_spec.ordering or feature_spec.discrete_values
                )
                value_index = category_values.index(assignments[feature_name])
            if not 0 <= value_index < len(densities):
                raise ValueError("categorical SPN leaf value index is outside densities")
            value = math.log(max(densities[value_index], 1e-12))
        elif node_type == "product":
            value = math.fsum(
                evaluate(int(child_id)) for child_id in node.get("children", ())
            )
        elif node_type == "sum":
            child_ids = tuple(int(child_id) for child_id in node.get("children", ()))
            weights = _float_sequence(node.get("weights"))
            if not child_ids or len(child_ids) != len(weights):
                raise ValueError("categorical SPN sum children and weights must align")
            weighted_terms = tuple(
                evaluate(child_id) + math.log(max(weight, 1e-12))
                for child_id, weight in zip(child_ids, weights, strict=True)
            )
            maximum = max(weighted_terms)
            value = maximum + math.log(
                math.fsum(math.exp(term - maximum) for term in weighted_terms)
            )
        else:
            raise ValueError(
                f"unsupported exact categorical SPN node type {node_type!r}"
            )
        active.remove(node_id)
        cache[node_id] = value
        return value

    return evaluate(int(spn_model["root_id"]))


def build_spn_chance_model_from_artifact(
    backend: Any,
    *,
    artifact: TPMArtifact | str | Path | Mapping[str, object],
    problem_id: str,
    decision_features: Sequence[str],
    cost_terms: Mapping[str, float],
    option_costs: Mapping[str, Mapping[object, float]] | None = None,
    chance_limit_epsilon: float,
    target_threshold: float | None = None,
    numeric_tolerance: float = 1e-9,
    piecewise_terms: object | None = None,
) -> object:
    """Build one generic SPN chance-constrained model directly from a TPM artifact."""

    resolved_artifact = _load_artifact(artifact)
    resolved_decision_features = tuple(str(name) for name in decision_features)
    if target_threshold is None:
        resolved_target_threshold = float(
            resolved_artifact.target_definition.get("threshold_default", 0.0)
        )
    else:
        resolved_target_threshold = float(target_threshold)

    spn_payload = build_spn_mip_payload(
        resolved_artifact,
        decision_features=resolved_decision_features,
        chance_limit_epsilon=float(chance_limit_epsilon),
        target_threshold=resolved_target_threshold,
    )
    if spn_payload is None:
        raise ValueError(
            "TPM artifact does not expose a serialized SPN MIO payload for direct chance-model assembly"
        )

    resolved_piecewise_terms = (
        piecewise_terms
        if piecewise_terms is not None
        else build_spn_modeling_terms(
            resolved_artifact.approximation_metadata,
            max_terms=infer_max_sum_terms(spn_payload),
        )
    )
    return build_spn_chance_model(
        backend,
        problem_id=problem_id,
        spn_payload=spn_payload,
        cost_terms=cost_terms,
        option_costs=option_costs,
        chance_limit_epsilon=float(chance_limit_epsilon),
        numeric_tolerance=float(numeric_tolerance),
        piecewise_terms=resolved_piecewise_terms,
    )


def solve_spn_chance_model(
    model: object,
    *,
    backend: Any | None = None,
    solve_config: SPNSolveConfig | None = None,
) -> SPNSolveSummary:
    """Solve one already-built SPN chance model with Pyomo and decode the result."""

    resolved_backend = backend if backend is not None else require_pyomo_backend()
    resolved_config = solve_config or SPNSolveConfig()
    solver_factory = getattr(resolved_backend, "SolverFactory", None)
    if solver_factory is None:
        raise SPNSolverUnavailableError(
            "pyomo backend does not expose SolverFactory for SPN chance solving"
        )

    try:
        solver = solver_factory(resolved_config.solver_name)
    except Exception as exc:  # pragma: no cover - backend specific
        raise SPNSolverUnavailableError(str(exc)) from exc
    if not _solver_is_available(solver):
        raise SPNSolverUnavailableError(
            f"solver {resolved_config.solver_name!r} is unavailable"
        )

    _apply_time_limit_if_supported(
        solver,
        time_limit_seconds=resolved_config.time_limit_seconds,
    )
    results = solver.solve(model, tee=False)
    diagnostics = _solver_result_metadata(results)
    risk_encoding_strategy = str(
        getattr(model, "_open_energy_lab_risk_encoding_strategy", "piecewise-spn")
    )
    if _solver_result_reports_infeasible(results):
        return SPNSolveSummary(
            problem_id=str(getattr(model, "name", "spn-mio-problem")),
            status="infeasible",
            selected_design={},
            objective_value=None,
            estimated_event_probability=None,
            estimated_shortfall_risk=None,
            chance_limit_epsilon=float(getattr(model, "_open_energy_lab_chance_limit_epsilon")),
            solver_metadata={
                "requested_solver_name": resolved_config.solver_name,
                "backend_module": getattr(resolved_backend, "__name__", resolved_backend.__class__.__name__),
                "backend_version": getattr(resolved_backend, "__version__", "unknown"),
                "status": "infeasible",
                "solve_execution_mode": "native-pyomo-solver",
                "risk_encoding_strategy": risk_encoding_strategy,
                **diagnostics,
            },
        )

    solution = extract_spn_solution(
        model,
        backend=resolved_backend,
        numeric_tolerance=resolved_config.numeric_tolerance,
    )
    return SPNSolveSummary(
        problem_id=str(getattr(model, "name", "spn-mio-problem")),
        status="optimal",
        selected_design=_mapping(solution.get("selected_design"), field_name="selected_design"),
        objective_value=float(solution["objective_value"]),
        estimated_event_probability=float(solution["estimated_event_probability"]),
        estimated_shortfall_risk=float(solution["estimated_shortfall_risk"]),
        chance_limit_epsilon=float(getattr(model, "_open_energy_lab_chance_limit_epsilon")),
        solver_metadata={
            "requested_solver_name": resolved_config.solver_name,
            "backend_module": getattr(resolved_backend, "__name__", resolved_backend.__class__.__name__),
            "backend_version": getattr(resolved_backend, "__version__", "unknown"),
            "status": "optimal",
            "solve_execution_mode": "native-pyomo-solver",
            "risk_encoding_strategy": risk_encoding_strategy,
            **diagnostics,
        },
    )


def solve_spn_chance_model_from_artifact(
    *,
    artifact: TPMArtifact | str | Path | Mapping[str, object],
    problem_id: str,
    decision_features: Sequence[str],
    cost_terms: Mapping[str, float],
    option_costs: Mapping[str, Mapping[object, float]] | None = None,
    chance_limit_epsilon: float,
    target_threshold: float | None = None,
    numeric_tolerance: float = 1e-9,
    piecewise_terms: object | None = None,
    backend: Any | None = None,
    solve_config: SPNSolveConfig | None = None,
) -> SPNSolveSummary:
    """Build and solve one generic SPN chance-constrained model from a TPM artifact."""

    resolved_backend = backend if backend is not None else require_pyomo_backend()
    model = build_spn_chance_model_from_artifact(
        resolved_backend,
        artifact=artifact,
        problem_id=problem_id,
        decision_features=decision_features,
        cost_terms=cost_terms,
        option_costs=option_costs,
        chance_limit_epsilon=chance_limit_epsilon,
        target_threshold=target_threshold,
        numeric_tolerance=numeric_tolerance,
        piecewise_terms=piecewise_terms,
    )
    return solve_spn_chance_model(
        model,
        backend=resolved_backend,
        solve_config=solve_config,
    )


def extract_spn_solution(
    model: object,
    *,
    backend: Any,
    numeric_tolerance: float,
) -> dict[str, object]:
    """Decode one solved direct-design SPN model into a stable summary payload."""

    value_function = getattr(backend, "value", None)
    if not callable(value_function):
        raise TypeError("backend must expose value() to decode a solved SPN model")

    decision_variables = getattr(model, "_open_energy_lab_decision_variables")
    feature_by_name = getattr(model, "_open_energy_lab_feature_by_name")
    selected_design: dict[str, object] = {}
    for feature_name, decision_payload in decision_variables.items():
        feature_spec = feature_by_name[feature_name]
        selected_design[feature_name] = _decode_decision_value(
            feature_spec,
            decision_payload=decision_payload,
            value_function=value_function,
            numeric_tolerance=numeric_tolerance,
        )

    objective_value = float(value_function(model.total_cost))
    risk_probability = getattr(model, "_open_energy_lab_risk_probability", None)
    result = {
        "selected_design": selected_design,
        "objective_value": objective_value,
    }
    if risk_probability is not None:
        estimated_risk = float(value_function(risk_probability))
        result.update(
            {
                "estimated_event_probability": estimated_risk,
                "estimated_shortfall_risk": estimated_risk,
                "risk_encoding_strategy": "exact-categorical-lookup",
            }
        )
        return result

    numerator_log = float(value_function(model._open_energy_lab_risk_log_numerator))
    denominator_log = float(value_function(model._open_energy_lab_risk_log_denominator))
    estimated_risk = math.exp(min(0.0, numerator_log - denominator_log))
    result.update(
        {
            "estimated_event_probability": estimated_risk,
            "estimated_shortfall_risk": estimated_risk,
            "numerator_log_likelihood": numerator_log,
            "denominator_log_likelihood": denominator_log,
            "risk_encoding_strategy": "piecewise-spn",
        }
    )
    return result


def infer_max_sum_terms(spn_payload: Mapping[str, object]) -> int:
    """Infer the largest sum-node arity across one serialized conditional SPN payload."""

    conditional_models = _mapping(
        spn_payload.get("conditional_models"),
        field_name="conditional_models",
    )
    max_terms = 2
    for model_name in ("numerator_model", "denominator_model"):
        model_payload = _mapping(
            conditional_models.get(model_name),
            field_name=f"conditional_models.{model_name}",
        )
        nodes = _sequence_of_mappings(model_payload.get("nodes"), field_name=f"{model_name}.nodes")
        for node in nodes:
            if str(node.get("type", "")) != "sum":
                continue
            child_count = len(_sequence(node.get("children"), field_name=f"{model_name}.children"))
            if child_count > max_terms:
                max_terms = child_count
    return max_terms


def build_spn_modeling_terms(
    approximation_metadata: Mapping[str, object],
    *,
    max_terms: int,
) -> SPNModelingTerms:
    """Build generic SPN modeling terms without planning-specific decision-scope validation."""

    resolved_metadata = load_piecewise_metadata(approximation_metadata)
    normalized_max_terms = int(max_terms)
    if normalized_max_terms < 1:
        raise ValueError("max_terms must be at least 1")
    breakpoint_policy = resolved_metadata.breakpoint_policy
    exp_breakpoints = breakpoint_policy.exp_breakpoints()
    exp_values = breakpoint_policy.exp_values()
    log_breakpoints = breakpoint_policy.log_breakpoints(max_terms=normalized_max_terms)
    log_values = breakpoint_policy.log_values(max_terms=normalized_max_terms)
    return SPNModelingTerms(
        approximation_kind=resolved_metadata.approximation_kind,
        leaf_encoding_mode=resolved_metadata.leaf_encoding_mode,
        sum_encoding_mode=resolved_metadata.sum_encoding_mode,
        exp_curve=SPNPiecewiseCurveSpec(
            x_points=(_DEFAULT_EXP_DOMAIN_FLOOR, exp_breakpoints[0], *exp_breakpoints),
            y_points=(0.0, 0.0, *exp_values),
            domain_lower_bound=_DEFAULT_EXP_DOMAIN_FLOOR,
            domain_upper_bound=0.0,
            unbounded_domain_var=True,
        ),
        log_curve=SPNPiecewiseCurveSpec(
            x_points=log_breakpoints,
            y_points=log_values,
            domain_lower_bound=log_breakpoints[0],
            domain_upper_bound=log_breakpoints[-1],
        ),
        max_terms=normalized_max_terms,
        mio_epsilon=resolved_metadata.mio_epsilon,
        fit_numeric_tolerance=resolved_metadata.fit_numeric_tolerance,
        query_numeric_tolerance=resolved_metadata.query_numeric_tolerance,
    )


def build_compiled_spflow_decision_link_model(
    backend: Any,
    *,
    compiled_payload: Mapping[str, object],
    decision_features: Sequence[str],
) -> object:
    """Build a constant-objective Pyomo model exposing compiled-v2 decision links."""

    compiled = _mapping(compiled_payload, field_name="compiled_payload")
    if compiled.get("schema_version") != _SPFLOW_MIO_SCHEMA_VERSION:
        raise ValueError("physical decision linking requires a compiled-v2 payload")
    if compiled.get("compiler_version") != _SPFLOW_MIO_COMPILER_VERSION:
        raise ValueError("physical decision linking requires the current compiled-v2 compiler")
    schema = load_feature_schema(
        _sequence_of_mappings(compiled.get("feature_schema"), field_name="feature_schema"),
        schema_version="v3",
    )
    feature_by_name = {spec.feature_name: spec for spec in schema}
    validity_by_index = _load_compiled_validity(compiled)
    validity_by_name = {
        record.feature_name: record for record in validity_by_index.values()
    }
    normalized_decisions = tuple(str(name) for name in decision_features)
    if not normalized_decisions or len(set(normalized_decisions)) != len(
        normalized_decisions
    ):
        raise ValueError("decision_features must be non-empty and unique")

    model = backend.ConcreteModel(name="compiled-spflow-decision-links")
    model._open_energy_lab_decision_variables = {}
    model._open_energy_lab_decision_decoders = {}
    for feature_name in normalized_decisions:
        if feature_name not in feature_by_name:
            raise ValueError(f"unknown compiled decision feature {feature_name!r}")
        feature_spec = feature_by_name[feature_name]
        if feature_spec.feature_role != "decision" or not feature_spec.modifiable:
            raise ValueError(
                f"compiled feature {feature_name!r} is not a modifiable decision"
            )
        validity = validity_by_name.get(feature_name)
        if feature_spec.feature_type == "continuous" and validity is None:
            raise ValueError(
                f"continuous decision {feature_name!r} lacks compiled-v2 validity"
            )
        decision_payload = _add_decision_variable(
            backend,
            model,
            feature_spec=feature_spec,
            feature_name=feature_name,
            compiled_validity=validity,
        )
        model._open_energy_lab_decision_variables[feature_name] = decision_payload
        model._open_energy_lab_decision_decoders[feature_name] = _decision_decoder(
            feature_spec
        )
    model.constant_objective = backend.Objective(expr=0.0)
    return model


def _add_decision_variable(
    backend: Any,
    model: object,
    *,
    feature_spec: TPMFeatureSpec,
    feature_name: str,
    option_costs: Mapping[object, float] | None = None,
    compiled_validity: TPMCompiledValidityRecord | None = None,
) -> dict[str, object]:
    if feature_spec.feature_type == "continuous":
        if compiled_validity is not None:
            physical_var = backend.Var(
                bounds=(
                    compiled_validity.physical_lower,
                    compiled_validity.physical_upper,
                )
            )
            model_var = backend.Var(
                bounds=(compiled_validity.model_lower, compiled_validity.model_upper)
            )
            model.add_component(f"decision_{feature_name}_physical", physical_var)
            model.add_component(
                f"decision_{feature_name}_model_coordinate",
                model_var,
            )
            model.add_component(
                f"decision_{feature_name}_physical_validity_lower",
                backend.Constraint(
                    expr=physical_var >= compiled_validity.physical_lower
                ),
            )
            model.add_component(
                f"decision_{feature_name}_physical_validity_upper",
                backend.Constraint(
                    expr=physical_var <= compiled_validity.physical_upper
                ),
            )
            model.add_component(
                f"decision_{feature_name}_model_validity_lower",
                backend.Constraint(expr=model_var >= compiled_validity.model_lower),
            )
            model.add_component(
                f"decision_{feature_name}_model_validity_upper",
                backend.Constraint(expr=model_var <= compiled_validity.model_upper),
            )
            normalization = compiled_validity.normalization
            if normalization.kind == "min-max":
                link_expression = model_var == (
                    physical_var - normalization.lower
                ) / (normalization.upper - normalization.lower)
            elif normalization.kind == "identity":
                link_expression = model_var == physical_var
            else:
                raise ValueError(
                    f"continuous decision {feature_name!r} uses unsupported compiled "
                    f"normalization {normalization.kind!r}"
                )
            link = backend.Constraint(expr=link_expression)
            model.add_component(f"decision_{feature_name}_coordinate_link", link)
            return {
                "kind": "continuous",
                "physical_var": physical_var,
                "model_coordinate_var": model_var,
                "normalized_var": model_var,
                "coordinate_link": link,
                "cost_expression": physical_var,
                "compiled_validity": compiled_validity,
            }
        var = backend.Var(bounds=(0.0, 1.0))
        model.add_component(f"decision_{feature_name}", var)
        lower, upper = feature_spec.bounds or (0.0, 1.0)
        cost_expression = lower + var * (upper - lower)
        return {
            "kind": "continuous",
            "normalized_var": var,
            "cost_expression": cost_expression,
        }

    if feature_spec.feature_type == "binary":
        var = backend.Var(domain=backend.Binary)
        model.add_component(f"decision_{feature_name}", var)
        discrete_values = tuple(feature_spec.ordering or feature_spec.discrete_values)
        if len(discrete_values) != 2:
            raise ValueError(
                f"binary decision feature {feature_name!r} must declare two ordered labels"
            )
        return {
            "kind": "binary",
            "normalized_var": var,
            "category_values": discrete_values,
            "cost_expression": var,
        }

    if feature_spec.feature_type == "categorical":
        categories = tuple(feature_spec.ordering or feature_spec.discrete_values)
        if option_costs is not None and set(option_costs) != set(categories):
            raise ValueError(
                f"option_costs for {feature_name!r} must exactly match {categories!r}"
            )
        index_set = backend.Set(initialize=tuple(range(len(categories))), ordered=True)
        model.add_component(f"decision_{feature_name}_set", index_set)
        var = backend.Var(index_set, domain=backend.Binary)
        model.add_component(f"decision_{feature_name}", var)
        model.add_component(
            f"decision_{feature_name}_one_hot",
            backend.Constraint(expr=sum(var[index] for index in index_set) == 1),
        )
        return {
            "kind": "categorical",
            "normalized_var": var,
            "category_values": categories,
            "cost_expression": (
                sum(float(option_costs[category]) * var[index]
                    for index, category in enumerate(categories))
                if option_costs is not None
                else 0.0
            ),
        }

    raise ValueError(
        f"SPN MIO builder does not yet support decision feature_type {feature_spec.feature_type!r}"
    )


def _decision_decoder(feature_spec: TPMFeatureSpec) -> object:
    return feature_spec


def _decode_decision_value(
    feature_spec: TPMFeatureSpec,
    *,
    decision_payload: Mapping[str, object],
    value_function: Any,
    numeric_tolerance: float,
) -> object:
    kind = str(decision_payload["kind"])
    if kind == "continuous":
        if "physical_var" in decision_payload:
            return float(value_function(decision_payload["physical_var"]))
        normalized_value = float(value_function(decision_payload["normalized_var"]))
        lower, upper = feature_spec.bounds or (0.0, 1.0)
        return lower + normalized_value * (upper - lower)

    if kind == "binary":
        normalized_value = float(value_function(decision_payload["normalized_var"]))
        labels = tuple(decision_payload.get("category_values", (0.0, 1.0)))
        return (
            labels[1]
            if normalized_value >= 1.0 - numeric_tolerance
            else labels[0]
        )

    if kind == "categorical":
        category_values = tuple(decision_payload["category_values"])
        var = decision_payload["normalized_var"]
        best_index = max(
            range(len(category_values)),
            key=lambda index: float(value_function(var[index])),
        )
        return category_values[best_index]

    raise ValueError(f"unsupported decision payload kind {kind!r}")


def encode_conditioned_spflow_circuit(
    backend: Any,
    block: object,
    *,
    circuit: Mapping[str, object],
    decision_variables: Mapping[str, Mapping[str, object]],
    encoding: Mapping[str, object],
    formulation: Mapping[str, object],
) -> Mapping[str, object]:
    """Encode one conditioned circuit against shared caller-supplied coordinates."""

    nodes = _sequence_of_mappings(
        circuit.get("nodes"), field_name="conditioned circuit nodes"
    )
    root_id = int(circuit["root_id"])
    node_ids = tuple(int(node["id"]) for node in nodes)
    if len(set(node_ids)) != len(node_ids) or root_id not in set(node_ids):
        raise ValueError("conditioned circuit node ids must be unique and contain root_id")
    encoding_mode = str(encoding.get("mode", ""))
    if encoding_mode not in {"max", "piecewise"}:
        raise ValueError("conditioned circuit encoding mode must be max or piecewise")
    leaf_configuration = _mapping(
        encoding.get("leaf_configuration"),
        field_name="conditional leaf_configuration",
    )
    sum_configuration = _mapping(
        encoding.get("sum_configuration"),
        field_name="conditional sum_configuration",
    )
    probability_floor = float(leaf_configuration["discrete_probability_floor"])
    if not math.isfinite(probability_floor) or probability_floor <= 0.0:
        raise ValueError("conditional discrete probability floor must be positive and finite")

    formulation_payload = _mapping(
        formulation, field_name="conditional attachment formulation"
    )
    node_bound_records = _sequence_of_mappings(
        formulation_payload.get("node_output_bounds"),
        field_name="conditional node output bounds",
    )
    node_bounds = {
        int(record["node_id"]): (
            float(record["lower"]),
            float(record["upper"]),
        )
        for record in node_bound_records
    }
    if set(node_bounds) != set(node_ids) or any(
        not math.isfinite(value) or node_bounds[node_id][0] > node_bounds[node_id][1]
        for node_id in node_ids
        for value in node_bounds[node_id]
    ):
        raise ValueError("conditional attachment node bounds are incomplete or invalid")
    leaf_representation_records = _sequence_of_mappings(
        formulation_payload.get("leaf_piecewise_representations", ()),
        field_name="conditional leaf Piecewise representations",
    )
    leaf_representations = {
        int(record["node_id"]): str(record["representation"])
        for record in leaf_representation_records
    }
    sum_records = _sequence_of_mappings(
        formulation_payload.get("sum_nodes", ()),
        field_name="conditional Sum formulation records",
    )
    sum_formulations = {int(record["node_id"]): record for record in sum_records}
    guarded_input_coordinate = formulation_payload.get("guarded_input_coordinate")

    block.NODE_IDS = backend.Set(initialize=node_ids, ordered=True)
    block.node_out = backend.Var(
        block.NODE_IDS,
        within=backend.Reals,
        bounds=lambda _block, node_id: node_bounds[int(node_id)],
    )
    node_by_id = {int(node["id"]): node for node in nodes}
    for node_id in node_ids:
        node = node_by_id[node_id]
        node_type = str(node["type"])
        if node_type == "log_one":
            block.add_component(
                f"log_one_{node_id}",
                backend.Constraint(expr=block.node_out[node_id] == 0.0),
            )
            continue
        if node_type == "leaf_piecewise":
            _encode_conditioned_piecewise_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                decision_variables=decision_variables,
                representation=leaf_representations.get(node_id),
            )
            continue
        if node_type in {"leaf_binary", "leaf_categorical"}:
            densities = _float_sequence(node["densities"])
            log_densities = tuple(
                math.log(max(value, probability_floor)) for value in densities
            )
            if "fixed_value" in node:
                index = int(node["fixed_value"])
                if not 0 <= index < len(densities):
                    raise ValueError(
                        f"conditioned discrete leaf {node_id} fixed index is invalid"
                    )
                block.add_component(
                    f"discrete_leaf_fixed_{node_id}",
                    backend.Constraint(
                        expr=block.node_out[node_id] == log_densities[index]
                    ),
                )
                continue
            feature_name = str(node["feature_name"])
            if feature_name not in decision_variables:
                raise ValueError(
                    f"conditioned discrete leaf {node_id} has no decision mapping"
                )
            payload = decision_variables[feature_name]
            kind = str(payload.get("kind"))
            if node_type == "leaf_binary" and kind == "binary":
                variable = payload["normalized_var"]
                block.add_component(
                    f"binary_leaf_{node_id}",
                    backend.Constraint(
                        expr=block.node_out[node_id]
                        == (1.0 - variable) * log_densities[0]
                        + variable * log_densities[1]
                    ),
                )
                continue
            if node_type == "leaf_categorical" and kind == "categorical":
                indicators = tuple(payload["normalized_var"])
                if len(indicators) != len(log_densities):
                    raise ValueError(
                        f"categorical leaf {node_id} indicator count differs from densities"
                    )
                block.add_component(
                    f"categorical_leaf_{node_id}",
                    backend.Constraint(
                        expr=block.node_out[node_id]
                        == sum(
                            indicator * log_density
                            for indicator, log_density in zip(
                                indicators, log_densities, strict=True
                            )
                        )
                    ),
                )
                continue
            raise ValueError(
                f"conditioned discrete leaf {node_id} mapping kind {kind!r} is invalid"
            )
        if node_type == "product":
            child_ids = tuple(int(value) for value in node.get("children", ()))
            block.add_component(
                f"product_{node_id}",
                backend.Constraint(
                    expr=block.node_out[node_id]
                    == sum(block.node_out[child_id] for child_id in child_ids)
                ),
            )
            continue
        if node_type == "sum":
            _encode_conditioned_sum_node(
                backend,
                block,
                node_id=node_id,
                node=node,
                mode=encoding_mode,
                sum_configuration=sum_configuration,
                formulation=sum_formulations.get(node_id),
                guarded_input_coordinate=guarded_input_coordinate,
            )
            continue
        raise ValueError(f"unsupported conditioned circuit node type {node_type!r}")

    constraint_names = tuple(
        component.getname(fully_qualified=False)
        for component in block.component_objects(
            backend.Constraint, active=True, descend_into=True
        )
    )
    return {
        "root": block.node_out[root_id],
        "node_output": block.node_out,
        "constraint_component_names": constraint_names,
    }


def _encode_conditioned_piecewise_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    decision_variables: Mapping[str, Mapping[str, object]],
    representation: str | None,
) -> None:
    feature_name = str(node["feature_name"])
    breakpoints = _float_sequence(node["breakpoints"])
    log_values = _float_sequence(node["log_values"])
    if len(breakpoints) < 2 or len(breakpoints) != len(log_values):
        raise ValueError(
            f"conditioned piecewise leaf {node_id} points must align"
        )
    if feature_name in decision_variables:
        payload = decision_variables[feature_name]
        if str(payload.get("kind")) != "continuous":
            raise ValueError(
                f"conditioned piecewise leaf {node_id} requires a continuous mapping"
            )
        expected_representation = "DLOG" if len(breakpoints) - 1 == 4 else "DCC"
        if representation != expected_representation:
            raise ValueError(
                f"conditioned piecewise leaf {node_id} representation must be "
                f"{expected_representation}"
            )
        piecewise = backend.Piecewise(
            block.node_out[node_id],
            payload["normalized_var"],
            pw_pts=list(breakpoints),
            pw_constr_type="EQ",
            pw_repn=representation,
            f_rule=list(log_values),
        )
        block.add_component(f"piecewise_leaf_{node_id}", piecewise)
        _bound_piecewise_auxiliaries(backend, piecewise)
        return
    if "fixed_value" not in node:
        raise ValueError(
            f"conditioned piecewise leaf {node_id} has no decision mapping"
        )
    fixed_log_value = _linear_interpolate(
        float(node["fixed_value"]),
        x_values=breakpoints,
        y_values=log_values,
    )
    block.add_component(
        f"piecewise_leaf_fixed_{node_id}",
        backend.Constraint(expr=block.node_out[node_id] == fixed_log_value),
    )


def _encode_conditioned_sum_node(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    mode: str,
    sum_configuration: Mapping[str, object],
    formulation: Mapping[str, object] | None,
    guarded_input_coordinate: object,
) -> None:
    child_ids = tuple(int(value) for value in node["children"])
    weights = _float_sequence(node["weights"])
    if not child_ids or len(child_ids) != len(weights):
        raise ValueError(f"conditioned Sum {node_id} children and weights must align")
    if any(not math.isfinite(weight) or weight <= 0.0 for weight in weights):
        raise ValueError(f"conditioned Sum {node_id} weights must be positive and finite")
    weighted_terms = tuple(
        block.node_out[child_id] + math.log(weight)
        for child_id, weight in zip(child_ids, weights, strict=True)
    )
    if not isinstance(formulation, Mapping):
        raise ValueError(f"conditioned Sum {node_id} lacks persisted formulation")
    term_records = _sequence_of_mappings(
        formulation.get("term_bounds"),
        field_name=f"conditioned Sum {node_id} term bounds",
    )
    relative_records = _sequence_of_mappings(
        formulation.get("relative_bounds"),
        field_name=f"conditioned Sum {node_id} relative bounds",
    )
    big_m_records = _sequence_of_mappings(
        formulation.get("branch_big_m"),
        field_name=f"conditioned Sum {node_id} branch big-M",
    )
    if not (
        len(term_records) == len(relative_records) == len(big_m_records) == len(child_ids)
    ):
        raise ValueError(f"conditioned Sum {node_id} formulation branches must align")
    maximum_bounds = _formulation_interval(
        formulation.get("maximum_bounds"),
        field_name=f"conditioned Sum {node_id} maximum bounds",
    )
    relative_bounds = tuple(
        _formulation_interval(
            record,
            field_name=f"conditioned Sum {node_id} relative branch {index}",
        )
        for index, record in enumerate(relative_records)
    )
    branch_big_m = tuple(float(record["value"]) for record in big_m_records)
    if any(not math.isfinite(value) or value < 0.0 for value in branch_big_m):
        raise ValueError(f"conditioned Sum {node_id} branch big-M values are invalid")
    indices = tuple(range(len(child_ids)))
    choice_index = backend.Set(initialize=indices, ordered=True)
    block.add_component(f"sum_choice_index_{node_id}", choice_index)
    active = backend.Var(choice_index, domain=backend.Binary)
    block.add_component(f"sum_choice_var_{node_id}", active)
    block.add_component(
        f"sum_choice_one_hot_{node_id}",
        backend.Constraint(expr=sum(active[index] for index in indices) == 1),
    )
    maximum = backend.Var(within=backend.Reals, bounds=maximum_bounds)
    block.add_component(f"sum_max_var_{node_id}", maximum)
    block.add_component(
        f"sum_max_lb_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: maximum >= weighted_terms[index],
        ),
    )
    block.add_component(
        f"sum_max_ub_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: maximum
            <= weighted_terms[index] + branch_big_m[index] * (1 - active[index]),
        ),
    )
    if mode == "max":
        block.add_component(
            f"sum_max_output_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == maximum),
        )
        return

    exp_x, exp_y = guarded_exponential_points(sum_configuration)
    coordinate = _mapping(
        guarded_input_coordinate,
        field_name=f"conditioned Sum {node_id} guarded input coordinate",
    )
    if coordinate.get("policy") != "unit-affine-log-v1":
        raise ValueError(
            f"conditioned Sum {node_id} guarded input coordinate policy is unsupported"
        )
    native_offset = float(coordinate.get("native_offset"))
    native_scale = float(coordinate.get("native_scale"))
    if native_offset != 500.0 or native_scale != 500.0:
        raise ValueError(
            f"conditioned Sum {node_id} guarded input coordinate must be "
            "q=(r+500)/500"
        )
    solver_x = _float_sequence(coordinate.get("solver_breakpoints"))
    expected_solver_x = tuple(
        (value + native_offset) / native_scale for value in exp_x
    )
    if solver_x != expected_solver_x or solver_x[0] != 0.0 or solver_x[-1] != 1.0:
        raise ValueError(
            f"conditioned Sum {node_id} guarded solver breakpoints are inconsistent"
        )
    log_x = _float_sequence(sum_configuration["log_x_points"])
    log_y = _float_sequence(sum_configuration["log_y_points"])
    exponential_records = _sequence_of_mappings(
        formulation.get("exponential_bounds"),
        field_name=f"conditioned Sum {node_id} exponential bounds",
    )
    exponential_bounds = tuple(
        _formulation_interval(
            record,
            field_name=f"conditioned Sum {node_id} exponential branch {index}",
        )
        for index, record in enumerate(exponential_records)
    )
    solver_input_records = _sequence_of_mappings(
        formulation.get("solver_input_bounds"),
        field_name=f"conditioned Sum {node_id} solver input bounds",
    )
    solver_input_bounds = tuple(
        _formulation_interval(
            record,
            field_name=f"conditioned Sum {node_id} solver input branch {index}",
        )
        for index, record in enumerate(solver_input_records)
    )
    if not (
        len(exponential_bounds) == len(solver_input_bounds) == len(indices)
    ):
        raise ValueError(
            f"conditioned Sum {node_id} exponential and solver input bounds must align"
        )
    if formulation.get("exponential_representation") != "DCC":
        raise ValueError(f"conditioned Sum {node_id} exponential representation must be DCC")
    if formulation.get("logarithm_representation") != "DCC":
        raise ValueError(f"conditioned Sum {node_id} logarithm representation must be DCC")
    relative = backend.Var(
        choice_index, bounds=lambda _block, index: relative_bounds[index]
    )
    block.add_component(f"sum_relative_var_{node_id}", relative)
    exponentials = backend.Var(
        choice_index, bounds=lambda _block, index: exponential_bounds[index]
    )
    block.add_component(f"sum_exp_var_{node_id}", exponentials)
    solver_input = backend.Var(
        choice_index, bounds=lambda _block, index: solver_input_bounds[index]
    )
    block.add_component(f"sum_exp_input_var_{node_id}", solver_input)
    block.add_component(
        f"sum_relative_constraint_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: relative[index]
            == weighted_terms[index] - maximum,
        ),
    )
    block.add_component(
        f"sum_exp_input_constraint_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: solver_input[index]
            == (relative[index] + native_offset) / native_scale,
        ),
    )
    for index in indices:
        piecewise = backend.Piecewise(
            exponentials[index],
            solver_input[index],
            pw_pts=list(solver_x),
            pw_constr_type="EQ",
            pw_repn="DCC",
            f_rule=list(exp_y),
        )
        block.add_component(f"sum_exp_piecewise_{node_id}_{index}", piecewise)
        _bound_piecewise_auxiliaries(backend, piecewise)
    total_bounds = _formulation_interval(
        formulation.get("total_bounds"),
        field_name=f"conditioned Sum {node_id} total bounds",
    )
    total = backend.Var(bounds=total_bounds)
    block.add_component(f"sum_exp_total_{node_id}", total)
    block.add_component(
        f"sum_exp_total_constraint_{node_id}",
        backend.Constraint(
            expr=total == sum(exponentials[index] for index in indices)
        ),
    )
    logarithm_bounds = _formulation_interval(
        formulation.get("logarithm_bounds"),
        field_name=f"conditioned Sum {node_id} logarithm bounds",
    )
    logarithm = backend.Var(bounds=logarithm_bounds)
    block.add_component(f"sum_log_var_{node_id}", logarithm)
    log_piecewise = backend.Piecewise(
        logarithm,
        total,
        pw_pts=list(log_x),
        pw_constr_type="EQ",
        pw_repn="DCC",
        f_rule=list(log_y),
    )
    block.add_component(f"sum_log_piecewise_{node_id}", log_piecewise)
    _bound_piecewise_auxiliaries(backend, log_piecewise)
    block.add_component(
        f"sum_output_{node_id}",
        backend.Constraint(expr=block.node_out[node_id] == maximum + logarithm),
    )


def _formulation_interval(
    value: object,
    *,
    field_name: str,
) -> tuple[float, float]:
    payload = _mapping(value, field_name=field_name)
    if not {"lower", "upper"}.issubset(payload):
        raise ValueError(f"{field_name} must contain lower and upper")
    lower = float(payload["lower"])
    upper = float(payload["upper"])
    if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
        raise ValueError(f"{field_name} must be a finite ordered interval")
    return lower, upper


def _bound_piecewise_auxiliaries(backend: Any, piecewise: object) -> None:
    """Apply explicit unit bounds to representation-owned convex weights."""

    for variable in piecewise.component_data_objects(
        backend.Var, active=True, descend_into=True
    ):
        if variable.lb is None:
            variable.setlb(0.0)
        if variable.ub is None:
            variable.setub(1.0)


def _encode_serialized_spn(
    backend: Any,
    block: object,
    *,
    model: object,
    spn_model: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
    sum_encoding_mode: str,
    piecewise_terms: object,
) -> object:
    nodes = _sequence_of_mappings(spn_model.get("nodes"), field_name="spn_model.nodes")
    root_id = int(spn_model["root_id"])
    node_ids = tuple(int(node["id"]) for node in nodes)
    block.NODE_IDS = backend.Set(initialize=node_ids, ordered=True)
    block.node_out = backend.Var(block.NODE_IDS, within=backend.Reals)
    node_by_id = {int(node["id"]): node for node in nodes}

    for node in nodes:
        node_id = int(node["id"])
        node_type = str(node["type"])
        if node_type == "leaf_histogram":
            _encode_histogram_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
                piecewise_terms=piecewise_terms,
            )
            continue
        if node_type == "leaf_piecewise":
            _encode_piecewise_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
            )
            continue
        if node_type == "leaf_binary":
            _encode_binary_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
            )
            continue
        if node_type == "leaf_categorical":
            _encode_categorical_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
            )
            continue
        if node_type == "product":
            child_ids = tuple(int(value) for value in node["children"])
            block.add_component(
                f"product_{node_id}",
                backend.Constraint(
                    expr=block.node_out[node_id]
                    == sum(block.node_out[child_id] for child_id in child_ids)
                ),
            )
            continue
        if node_type == "sum":
            _encode_sum_node(
                backend,
                block,
                node_id=node_id,
                node=node,
                sum_encoding_mode=sum_encoding_mode,
                piecewise_terms=piecewise_terms,
            )
            continue
        raise ValueError(f"unsupported serialized SPN node type {node_type!r}")

    if root_id not in node_by_id:
        raise ValueError(f"root_id {root_id!r} is not present in serialized SPN nodes")
    return block.node_out[root_id]


def _encode_histogram_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
    piecewise_terms: object,
) -> None:
    feature_name = str(node["feature_name"])
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        fixed_value = float(node["fixed_value"])
        log_density = _histogram_log_density(
            breaks=_float_sequence(node["breaks"]),
            densities=_float_sequence(node["densities"]),
            value=fixed_value,
        )
        block.add_component(
            f"hist_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == log_density),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "continuous":
        raise ValueError(f"histogram leaf {node_id} requires a continuous decision variable")

    in_var = decision_payload["normalized_var"]
    log_densities = tuple(math.log(max(value, 1e-12)) for value in _float_sequence(node["densities"]))
    pw_x, pw_y = build_histogram_piecewise_points(
        _float_sequence(node["breaks"]),
        log_densities,
    )
    pw_constraint = backend.Piecewise(
        block.node_out[node_id],
        in_var,
        pw_pts=list(pw_x),
        pw_constr_type="EQ",
        pw_repn="DCC",
        f_rule=list(pw_y),
    )
    block.add_component(f"hist_leaf_piecewise_{node_id}", pw_constraint)


def _encode_piecewise_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
) -> None:
    feature_name = str(node["feature_name"])
    breakpoints = _float_sequence(node["breakpoints"])
    log_values = _float_sequence(node["log_values"])
    if len(breakpoints) != len(log_values) or len(breakpoints) < 2:
        raise ValueError(
            f"piecewise leaf {node_id} breakpoints and log_values must align"
        )
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        if "fixed_value" not in node:
            raise ValueError(
                f"piecewise leaf {node_id} requires a decision variable or fixed_value"
            )
        fixed_value = float(node["fixed_value"])
        fixed_log_value = _linear_interpolate(
            fixed_value,
            x_values=breakpoints,
            y_values=log_values,
        )
        block.add_component(
            f"piecewise_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == fixed_log_value),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "continuous":
        raise ValueError(
            f"piecewise leaf {node_id} requires a continuous decision variable"
        )
    block.add_component(
        f"piecewise_leaf_{node_id}",
        backend.Piecewise(
            block.node_out[node_id],
            decision_payload["normalized_var"],
            pw_pts=list(breakpoints),
            pw_constr_type="EQ",
            pw_repn="DCC",
            f_rule=list(log_values),
        ),
    )


def _encode_binary_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
) -> None:
    feature_name = str(node["feature_name"])
    densities = tuple(math.log(max(value, 1e-12)) for value in _float_sequence(node["densities"]))
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        fixed_value = int(float(node["fixed_value"]))
        block.add_component(
            f"binary_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == densities[fixed_value]),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "binary":
        raise ValueError(f"binary leaf {node_id} requires a binary decision variable")
    in_var = decision_payload["normalized_var"]
    block.add_component(
        f"binary_leaf_{node_id}",
        backend.Constraint(
            expr=block.node_out[node_id]
            == (1.0 - in_var) * densities[0] + in_var * densities[1]
        ),
    )


def _encode_categorical_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
) -> None:
    feature_name = str(node["feature_name"])
    densities = tuple(math.log(max(value, 1e-12)) for value in _float_sequence(node["densities"]))
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        fixed_value = int(float(node["fixed_value"]))
        block.add_component(
            f"categorical_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == densities[fixed_value]),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "categorical":
        raise ValueError(f"categorical leaf {node_id} requires a categorical decision variable")
    in_var = decision_payload["normalized_var"]
    block.add_component(
        f"categorical_leaf_{node_id}",
        backend.Constraint(
            expr=block.node_out[node_id]
            == sum(in_var[index] * densities[index] for index in range(len(densities)))
        ),
    )


def _encode_sum_node(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    sum_encoding_mode: str,
    piecewise_terms: object,
) -> None:
    child_ids = tuple(int(value) for value in node["children"])
    weights = tuple(float(value) for value in node["weights"])
    weighted_terms = [block.node_out[child_id] + math.log(max(weight, 1e-12)) for child_id, weight in zip(child_ids, weights, strict=True)]

    slack_index = backend.Set(initialize=tuple(range(len(child_ids))), ordered=True)
    block.add_component(f"sum_choice_index_{node_id}", slack_index)
    active = backend.Var(slack_index, domain=backend.Binary)
    block.add_component(f"sum_choice_var_{node_id}", active)
    block.add_component(
        f"sum_choice_one_hot_{node_id}",
        backend.Constraint(expr=sum(active[index] for index in slack_index) == 1),
    )
    max_value = backend.Var(within=backend.Reals)
    block.add_component(f"sum_max_var_{node_id}", max_value)
    block.add_component(
        f"sum_max_lb_{node_id}",
        backend.Constraint(
            slack_index,
            rule=lambda _b, index: max_value >= weighted_terms[index],
        ),
    )
    block.add_component(
        f"sum_max_ub_{node_id}",
        backend.Constraint(
            slack_index,
            rule=lambda _b, index: max_value
            <= weighted_terms[index] + _SUM_BIG_M * (1 - active[index]),
        ),
    )

    if sum_encoding_mode == "max":
        block.add_component(
            f"sum_max_output_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == max_value),
        )
        return

    sub_index = backend.Set(initialize=tuple(range(len(child_ids))), ordered=True)
    block.add_component(f"sum_sub_index_{node_id}", sub_index)
    sub_var = backend.Var(sub_index, bounds=(piecewise_terms.exp_curve.domain_lower_bound, 0.0))
    block.add_component(f"sum_sub_var_{node_id}", sub_var)
    exp_var = backend.Var(sub_index, bounds=(0.0, 1.0))
    block.add_component(f"sum_exp_var_{node_id}", exp_var)
    block.add_component(
        f"sum_sub_constraint_{node_id}",
        backend.Constraint(
            sub_index,
            rule=lambda _b, index: sub_var[index] == weighted_terms[index] - max_value,
        ),
    )
    for index in range(len(child_ids)):
        piecewise = backend.Piecewise(
            exp_var[index],
            sub_var[index],
            pw_pts=list(piecewise_terms.exp_curve.x_points),
            pw_constr_type="EQ",
            pw_repn="DCC",
            f_rule=list(piecewise_terms.exp_curve.y_points),
            unbounded_domain_var=True,
        )
        block.add_component(f"sum_exp_piecewise_{node_id}_{index}", piecewise)

    sum_var = backend.Var(
        bounds=(
            piecewise_terms.log_curve.domain_lower_bound,
            piecewise_terms.log_curve.domain_upper_bound,
        )
    )
    block.add_component(f"sum_exp_total_{node_id}", sum_var)
    block.add_component(
        f"sum_exp_total_constraint_{node_id}",
        backend.Constraint(expr=sum_var == sum(exp_var[index] for index in sub_index)),
    )
    log_var = backend.Var(
        bounds=(
            min(piecewise_terms.log_curve.y_points),
            max(piecewise_terms.log_curve.y_points),
        )
    )
    block.add_component(f"sum_log_var_{node_id}", log_var)
    block.add_component(
        f"sum_log_piecewise_{node_id}",
        backend.Piecewise(
            log_var,
            sum_var,
            pw_pts=list(piecewise_terms.log_curve.x_points),
            pw_constr_type="EQ",
            pw_repn="DCC",
            f_rule=list(piecewise_terms.log_curve.y_points),
        ),
    )
    block.add_component(
        f"sum_output_{node_id}",
        backend.Constraint(expr=block.node_out[node_id] == max_value + log_var),
    )
def _histogram_log_density(*, breaks: Sequence[float], densities: Sequence[float], value: float) -> float:
    for density, upper_bound in zip(
        [densities[0], *densities, densities[-1]],
        [*breaks, math.inf],
        strict=True,
    ):
        if upper_bound > value:
            return math.log(max(density, 1e-12))
    return math.log(max(densities[-1], 1e-12))


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): inner_value for key, inner_value in value.items()}


def _sequence(value: object, *, field_name: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence")
    return tuple(value)


def _sequence_of_mappings(value: object, *, field_name: str) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of mappings")
    result: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field_name} must contain only mappings")
        result.append(item)
    return tuple(result)


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")
    return tuple(str(item) for item in value)


def _float_sequence(value: object) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("expected a numeric sequence")
    return tuple(float(item) for item in value)


def _load_artifact(
    artifact: TPMArtifact | str | Path | Mapping[str, object],
) -> TPMArtifact:
    if isinstance(artifact, TPMArtifact):
        return artifact
    return load_tpm_artifact(artifact)


def require_pyomo_backend() -> Any:
    """Import Pyomo only when the generic TPM solve path is invoked."""

    try:
        return import_module("pyomo.environ")
    except ImportError as exc:  # pragma: no cover - depends on installation state
        raise SPNSolverDependencyUnavailableError(
            "Pyomo-backed SPN chance solving requires the project 'pyomo' dependency."
        ) from exc


def _solver_is_available(solver: object) -> bool:
    available = getattr(solver, "available", None)
    if not callable(available):
        return True
    try:
        return bool(available(exception_flag=False))
    except TypeError:
        return bool(available())


def _apply_time_limit_if_supported(solver: object, *, time_limit_seconds: float | None) -> None:
    if time_limit_seconds is None or not hasattr(solver, "options"):
        return
    options = getattr(solver, "options")
    if not isinstance(options, dict):
        return
    options.setdefault("timelimit", float(time_limit_seconds))


def _solver_result_reports_infeasible(results: object) -> bool:
    diagnostics = _solver_result_metadata(results)
    termination_condition = str(diagnostics.get("termination_condition", "")).lower()
    return "infeasible" in termination_condition


def _solver_result_metadata(results: object) -> dict[str, object]:
    solver_block = getattr(results, "solver", None)
    diagnostics: dict[str, object] = {}
    if solver_block is not None:
        status = getattr(solver_block, "status", None)
        termination_condition = getattr(solver_block, "termination_condition", None)
        if status is not None:
            diagnostics["solver_status"] = str(status)
        if termination_condition is not None:
            diagnostics["termination_condition"] = str(termination_condition)
    return diagnostics


__all__ = [
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_compiled_spflow_decision_link_model",
    "build_spn_chance_model_from_artifact",
    "build_spn_modeling_terms",
    "build_spn_chance_model",
    "compile_spflow_model_to_mio",
    "evaluate_compiled_spflow_probability",
    "encode_conditioned_spflow_circuit",
    "extract_spn_solution",
    "infer_max_sum_terms",
    "require_pyomo_backend",
    "solve_spn_chance_model",
    "solve_spn_chance_model_from_artifact",
]
