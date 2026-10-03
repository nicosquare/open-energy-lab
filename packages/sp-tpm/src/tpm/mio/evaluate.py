"""Evaluate compiled MIO payloads against normalized or physical evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from ..domains import (
    TPMCompiledValidityRecord,
)
from ..features import TPMFeatureSpec, load_feature_schema
from ..piecewise import interpolate_within_breakpoints
from ._common import (
    _LEGACY_SPFLOW_MIO_COMPILER_VERSION,
    _LEGACY_SPFLOW_MIO_SCHEMA_VERSION,
    _SPFLOW_MIO_COMPILER_VERSION,
    _SPFLOW_MIO_SCHEMA_VERSION,
    _float_sequence,
    _mapping,
    _sequence,
    _sequence_of_mappings,
)


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
        log_likelihood += interpolate_within_breakpoints(point, x_values=x_values, y_values=y_values)
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
