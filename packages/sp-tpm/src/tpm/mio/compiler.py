"""Compile supported SPFlow modules into the MIO node payload."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import Any

from ..artifact import TPMArtifact, load_tpm_artifact
from ..domains import (
    TPMApproximationDomain,
    TPMCompiledValidityRecord,
)
from ..features import TPMFeatureSpec, dump_feature_schema
from ..spflow_backend import (
    CURRENT_SPFLOW_BACKEND_GENERATION,
    REQUIRED_SPFLOW_VERSION,
    require_spflow_backend,
)
from ._common import (
    _LEGACY_SPFLOW_MIO_COMPILER_VERSION,
    _LEGACY_SPFLOW_MIO_SCHEMA_VERSION,
    _SPFLOW_MIO_COMPILER_VERSION,
    _SPFLOW_MIO_SCHEMA_VERSION,
    _float_sequence,
)


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
    integer_grids: Mapping[str, Sequence[int]] | None = None,
    breakpoint_policy: Mapping[str, object] | None = None,
    mio_epsilon: float = _DEFAULT_MIO_EPSILON,
) -> dict[str, object]:
    """Compile the supported SPFlow 1.1 subset into a solver-neutral MIO payload.

    The compiler deliberately accepts only exact current-SPFlow ``Sum``,
    ``Product``, ``Normal``, ``Bernoulli``, and ``Categorical`` module types.
    SPFlow's internal ``Cat`` adapters are unwrapped as graph edges and are not
    emitted as MIO nodes. Normal log densities are sampled on deterministic
    normalized-domain breakpoints; discrete leaves and graph composition remain
    exact. Shared acyclic subgraphs reuse their compiled node; cycles are rejected.

    ``integer_grids`` optionally maps retained continuous feature names to every
    consecutive physical integer in their declared approximation interval. These
    anchors are normalized once and use the same ``mio_epsilon`` density floor;
    they do not turn the fitted density into a categorical probability mass.
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
    if integer_grids is not None and (not compiled_v2 or not isinstance(integer_grids, Mapping)):
        raise ValueError('integer grids require a declared-domain compiled-v2 artifact')
    if compiled_v2:
        validity_records = _resolve_compiled_v2_validity(
            model=model,
            schema=schema,
            approximation_domains=approximation_domains,
            relative_breakpoints=feature_breakpoints,
        )
        by_name = {record.feature_name: index for index, record in validity_records.items()}
        for name, raw_values in (integer_grids or {}).items():
            values = tuple(raw_values)
            if (name not in by_name or len(values) < 2
                    or any(type(v) is not int for v in values)
                    or any(b != a + 1 for a, b in zip(values, values[1:]))):
                raise ValueError('integer grids require retained continuous features and consecutive integer values')
            index = by_name[name]
            record = validity_records[index]
            if (values[0], values[-1]) != (record.physical_lower, record.physical_upper):
                raise ValueError('integer grid must cover the physical approximation interval')
            # Do not reconstruct integers by multiplying fractional anchors by U:
            # e.g. (29/100)*100 can miss 29. Normalize each physical integer once.
            validity_records[index] = replace(record, physical_breakpoints=values,
                model_breakpoints=tuple(float(record.normalization.normalize_value(k)) for k in values))
        if integer_grids:
            resolved_policy['integer_grids'] = {name: list(values) for name, values in integer_grids.items()}
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
    compiled_modules: dict[int, int] = {}
    active_modules: set[int] = set()

    def compile_module(module: object) -> int:
        module_scope = _spflow_module_scope(module)
        module_type = type(module).__name__
        identity = id(module)
        if identity in compiled_modules:
            return compiled_modules[identity]
        if identity in active_modules:
            raise UnsupportedSPFlowModuleError(
                module_type=module_type,
                scope=module_scope,
                reason="cyclic subgraphs cannot be represented by the compiler",
            )
        active_modules.add(identity)

        exact_type = type(module)
        if exact_type is bindings["sum"]:
            _validate_compiler_module_shape(module, scope=module_scope)
            children = spflow_operation_children(
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
            children = spflow_operation_children(
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
        compiled_modules[identity] = node_id
        active_modules.remove(identity)
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


def spflow_operation_children(
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


def _load_artifact(
    artifact: TPMArtifact | str | Path | Mapping[str, object],
) -> TPMArtifact:
    if isinstance(artifact, TPMArtifact):
        return artifact
    return load_tpm_artifact(artifact)
