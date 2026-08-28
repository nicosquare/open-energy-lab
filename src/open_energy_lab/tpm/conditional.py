"""Import-light immutable records for composable conditional TPM circuits.

This module owns record meaning, canonical identity, and create-or-verify
publication.  It intentionally imports no SPFlow, Torch, Pyomo, or solver
package; backend workflows live behind separate lazy boundaries.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar


CONDITIONAL_PAIR_RECORD_KIND = "conditional-pair-v1"
CONDITIONAL_PAIR_SCHEMA_VERSION = "v1"
CONDITIONAL_PAIR_COMPILER_VERSION = "conditional-mio-v1"
CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND = "conditional-embedding-parity-v1"
CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND = "conditional-compiler-fidelity-v1"
CONDITIONAL_EVIDENCE_SCHEMA_VERSION = "v1"
CONDITIONAL_EVIDENCE_EVALUATOR_VERSION = "conditional-evidence-v1"

_SUPPORTED_NODE_TYPES = frozenset(
    {
        "log_one",
        "leaf_piecewise",
        "leaf_binary",
        "leaf_categorical",
        "product",
        "sum",
    }
)
_MAX_APPROXIMATION_LABEL = "weighted-log-sum-exp-max-approximation"
_PIECEWISE_APPROXIMATION_LABEL = (
    "weighted-log-sum-exp-piecewise-linear-approximation"
)
_REQUIRED_NUMERICAL_TOLERANCES = frozenset(
    {
        "embedding_parity_absolute_tolerance",
        "constraint_residual_absolute_tolerance",
        "positive_log_risk_limit",
        "domain_membership_tolerance",
    }
)


@dataclass(frozen=True, slots=True)
class TPMConditionalSourceReference:
    """Persisted fitted-artifact and current-model origin for one pair."""

    artifact_id: str
    artifact_schema_version: str
    manifest_reference: str
    sidecar_sha256: str
    backend_generation: str
    backend_api_version: str
    model_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_id", _non_empty_string(self.artifact_id, "artifact_id")
        )
        object.__setattr__(
            self,
            "artifact_schema_version",
            _non_empty_string(
                self.artifact_schema_version, "artifact_schema_version"
            ),
        )
        manifest_reference = _non_empty_string(
            self.manifest_reference, "manifest_reference"
        )
        if Path(manifest_reference).is_absolute():
            raise ValueError("manifest_reference must be a portable relative path")
        object.__setattr__(self, "manifest_reference", manifest_reference)
        object.__setattr__(
            self,
            "sidecar_sha256",
            _sha256_digest(self.sidecar_sha256, field_name="sidecar_sha256"),
        )
        object.__setattr__(
            self,
            "backend_generation",
            _non_empty_string(self.backend_generation, "backend_generation"),
        )
        object.__setattr__(
            self,
            "backend_api_version",
            _non_empty_string(self.backend_api_version, "backend_api_version"),
        )
        object.__setattr__(
            self,
            "model_digest",
            _sha256_digest(self.model_digest, field_name="model_digest"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_schema_version": self.artifact_schema_version,
            "manifest_reference": self.manifest_reference,
            "sidecar_sha256": self.sidecar_sha256,
            "backend_generation": self.backend_generation,
            "backend_api_version": self.backend_api_version,
            "model_digest": self.model_digest,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMConditionalSourceReference":
        data = _strict_mapping(
            payload,
            record_name="conditional source reference",
            required={
                "artifact_id",
                "artifact_schema_version",
                "manifest_reference",
                "sidecar_sha256",
                "backend_generation",
                "backend_api_version",
                "model_digest",
            },
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class TPMConditionalEvent:
    """Exactly one binary event value and its persisted model coordinate."""

    feature_name: str
    declared_value: object
    model_index: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        object.__setattr__(
            self,
            "declared_value",
            _freeze_json(self.declared_value, field_name="declared_value"),
        )
        if isinstance(self.model_index, bool) or self.model_index not in (0, 1):
            raise ValueError("event model_index must be exactly 0 or 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_name": self.feature_name,
            "declared_value": _thaw_json(self.declared_value),
            "model_index": self.model_index,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "TPMConditionalEvent":
        return cls(
            **_strict_mapping(
                payload,
                record_name="conditional event",
                required={"feature_name", "declared_value", "model_index"},
            )
        )


@dataclass(frozen=True, slots=True)
class TPMConditionalFeatureValidity:
    """Declared and compiler-valid meaning for one retained feature."""

    feature_name: str
    feature_index: int
    feature_type: str
    declared_domain: Mapping[str, object]
    normalization: Mapping[str, object]
    approximation_domain: Mapping[str, object] | None = None

    _SUPPORTED_FEATURE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"continuous", "binary", "categorical"}
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        if isinstance(self.feature_index, bool) or not isinstance(
            self.feature_index, int
        ):
            raise TypeError("feature_index must be an integer")
        if self.feature_index < 0:
            raise ValueError("feature_index must be non-negative")
        feature_type = _non_empty_string(self.feature_type, "feature_type")
        if feature_type not in self._SUPPORTED_FEATURE_TYPES:
            raise ValueError(
                "feature_type must be continuous, binary, or categorical"
            )
        object.__setattr__(self, "feature_type", feature_type)
        declared_domain = _freeze_json(
            self.declared_domain, field_name="declared_domain"
        )
        normalization = _freeze_json(
            self.normalization, field_name="normalization"
        )
        if not isinstance(declared_domain, Mapping) or not declared_domain:
            raise ValueError("declared_domain must be a nonempty mapping")
        if not isinstance(normalization, Mapping) or not normalization:
            raise ValueError("normalization must be a nonempty mapping")
        approximation_domain = (
            None
            if self.approximation_domain is None
            else _freeze_json(
                self.approximation_domain, field_name="approximation_domain"
            )
        )
        if feature_type == "continuous" and not isinstance(
            approximation_domain, Mapping
        ):
            raise ValueError(
                f"continuous retained feature {self.feature_name!r} requires an "
                "approximation_domain"
            )
        if feature_type != "continuous" and approximation_domain is not None:
            raise ValueError(
                f"discrete retained feature {self.feature_name!r} must not invent an "
                "approximation_domain"
            )
        object.__setattr__(self, "declared_domain", declared_domain)
        object.__setattr__(self, "normalization", normalization)
        object.__setattr__(self, "approximation_domain", approximation_domain)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "feature_name": self.feature_name,
            "feature_index": self.feature_index,
            "feature_type": self.feature_type,
            "declared_domain": _thaw_json(self.declared_domain),
            "normalization": _thaw_json(self.normalization),
        }
        if self.approximation_domain is not None:
            payload["approximation_domain"] = _thaw_json(
                self.approximation_domain
            )
        return payload

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMConditionalFeatureValidity":
        data = _strict_mapping(
            payload,
            record_name="conditional feature validity",
            required={
                "feature_name",
                "feature_index",
                "feature_type",
                "declared_domain",
                "normalization",
            },
            optional={"approximation_domain"},
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class TPMConditionalEncodingPolicy:
    """Fully labelled max or PWL semantics shared by both circuits."""

    mode: str
    approximation_label: str
    certification_label: str
    leaf_configuration: Mapping[str, object]
    sum_configuration: Mapping[str, object]

    def __post_init__(self) -> None:
        mode = _non_empty_string(self.mode, "mode")
        if mode not in {"max", "piecewise"}:
            raise ValueError("conditional Sum encoding mode must be 'max' or 'piecewise'")
        expected_label = (
            _MAX_APPROXIMATION_LABEL
            if mode == "max"
            else _PIECEWISE_APPROXIMATION_LABEL
        )
        approximation_label = _non_empty_string(
            self.approximation_label, "approximation_label"
        )
        if approximation_label != expected_label:
            raise ValueError(
                f"{mode} approximation_label must be {expected_label!r}"
            )
        certification_label = _non_empty_string(
            self.certification_label, "certification_label"
        )
        if mode == "max" and certification_label != "uncertified":
            raise ValueError(
                "max certification_label must remain 'uncertified' in this feature"
            )
        if mode == "piecewise" and certification_label != "not-applicable":
            raise ValueError(
                "piecewise certification_label must be 'not-applicable'"
            )
        leaf_configuration = _freeze_json(
            self.leaf_configuration, field_name="leaf_configuration"
        )
        sum_configuration = _freeze_json(
            self.sum_configuration, field_name="sum_configuration"
        )
        if not isinstance(leaf_configuration, Mapping) or not leaf_configuration:
            raise ValueError("leaf_configuration must be a nonempty mapping")
        if not isinstance(sum_configuration, Mapping) or not sum_configuration:
            raise ValueError("sum_configuration must be a nonempty mapping")
        if "mio_epsilon" not in leaf_configuration:
            raise ValueError("leaf_configuration must resolve mio_epsilon")
        _positive_finite_mapping_value(
            leaf_configuration,
            "mio_epsilon",
            field_name="leaf_configuration.mio_epsilon",
        )
        _positive_finite_mapping_value(
            leaf_configuration,
            "discrete_probability_floor",
            field_name="leaf_configuration.discrete_probability_floor",
        )
        if not any(
            name in leaf_configuration
            for name in ("relative_breakpoints", "breakpoints", "breakpoint_count")
        ):
            raise ValueError(
                "leaf_configuration must resolve breakpoints or breakpoint_count"
            )
        _positive_finite_mapping_value(
            sum_configuration,
            "sum_big_m",
            field_name="sum_configuration.sum_big_m",
        )
        if mode == "piecewise":
            for x_name, y_name in (
                ("exp_x_points", "exp_y_points"),
                ("log_x_points", "log_y_points"),
            ):
                x_values = _finite_sequence(
                    sum_configuration.get(x_name), field_name=x_name
                )
                y_values = _finite_sequence(
                    sum_configuration.get(y_name), field_name=y_name
                )
                if len(x_values) < 2 or len(x_values) != len(y_values):
                    raise ValueError(f"{x_name} and {y_name} must align")
                if any(
                    right <= left for left, right in zip(x_values, x_values[1:])
                ):
                    raise ValueError(f"{x_name} must be strictly increasing")
            _finite_float(
                sum_configuration.get("exp_domain_floor"),
                field_name="sum_configuration.exp_domain_floor",
            )
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "approximation_label", approximation_label)
        object.__setattr__(self, "certification_label", certification_label)
        object.__setattr__(self, "leaf_configuration", leaf_configuration)
        object.__setattr__(self, "sum_configuration", sum_configuration)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "approximation_label": self.approximation_label,
            "certification_label": self.certification_label,
            "leaf_configuration": _thaw_json(self.leaf_configuration),
            "sum_configuration": _thaw_json(self.sum_configuration),
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMConditionalEncodingPolicy":
        return cls(
            **_strict_mapping(
                payload,
                record_name="conditional encoding policy",
                required={
                    "mode",
                    "approximation_label",
                    "certification_label",
                    "leaf_configuration",
                    "sum_configuration",
                },
            )
        )


@dataclass(frozen=True, slots=True)
class TPMConditionalNumericalPolicy:
    """Finite purpose-labelled tolerances without one ambiguous epsilon."""

    tolerances: Mapping[str, float]

    def __post_init__(self) -> None:
        if not isinstance(self.tolerances, Mapping):
            raise TypeError("tolerances must be a mapping")
        normalized: dict[str, float] = {}
        for raw_name, raw_value in self.tolerances.items():
            name = _non_empty_string(raw_name, "tolerance name")
            value = _finite_float(raw_value, field_name=f"tolerance {name}")
            if name == "domain_membership_tolerance":
                if value != 0.0:
                    raise ValueError(
                        "domain_membership_tolerance must be exactly zero"
                    )
            elif value <= 0.0:
                raise ValueError(f"tolerance {name!r} must be positive")
            normalized[name] = value
        missing = sorted(_REQUIRED_NUMERICAL_TOLERANCES - set(normalized))
        if missing:
            raise ValueError(
                "numerical policy is missing purpose-labelled tolerances: "
                + ", ".join(missing)
            )
        object.__setattr__(self, "tolerances", MappingProxyType(normalized))

    def to_dict(self) -> dict[str, object]:
        return {"tolerances": dict(self.tolerances)}

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMConditionalNumericalPolicy":
        data = _strict_mapping(
            payload,
            record_name="conditional numerical policy",
            required={"tolerances"},
        )
        return cls(tolerances=data["tolerances"])


@dataclass(frozen=True, slots=True)
class TPMConditionalCompilationRequest:
    """Complete caller-selected semantics for one conditional compilation."""

    source_artifact: str
    event_target: str
    event_value: object
    retained_decisions: tuple[str, ...]
    approximation_domains: tuple[Mapping[str, object], ...]
    encoding: TPMConditionalEncodingPolicy
    numerical_policy: TPMConditionalNumericalPolicy

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_artifact",
            _non_empty_string(self.source_artifact, "source_artifact"),
        )
        event_target = _non_empty_string(self.event_target, "event_target")
        object.__setattr__(self, "event_target", event_target)
        object.__setattr__(
            self,
            "event_value",
            _freeze_json(self.event_value, field_name="event_value"),
        )
        retained_decisions = tuple(
            _non_empty_string(value, "retained decision")
            for value in self.retained_decisions
        )
        if not retained_decisions:
            raise ValueError("retained_decisions must be nonempty")
        if len(set(retained_decisions)) != len(retained_decisions):
            raise ValueError("retained_decisions must be unique")
        if event_target in retained_decisions:
            raise ValueError("the event target cannot be a retained decision")
        object.__setattr__(self, "retained_decisions", retained_decisions)
        domains = tuple(
            _freeze_json(value, field_name="approximation_domains")
            for value in self.approximation_domains
        )
        if any(not isinstance(value, Mapping) for value in domains):
            raise TypeError("approximation_domains entries must be mappings")
        domain_names = tuple(str(value.get("feature_name", "")) for value in domains)
        if any(not name for name in domain_names):
            raise ValueError("every approximation domain requires feature_name")
        if len(set(domain_names)) != len(domain_names):
            raise ValueError("approximation domain feature names must be unique")
        unknown = sorted(set(domain_names) - set(retained_decisions))
        if unknown:
            raise ValueError(
                "approximation domains refer to unknown retained decisions: "
                + ", ".join(unknown)
            )
        object.__setattr__(self, "approximation_domains", domains)
        if not isinstance(self.encoding, TPMConditionalEncodingPolicy):
            raise TypeError("encoding must be a TPMConditionalEncodingPolicy")
        if not isinstance(self.numerical_policy, TPMConditionalNumericalPolicy):
            raise TypeError(
                "numerical_policy must be a TPMConditionalNumericalPolicy"
            )


@dataclass(frozen=True, slots=True)
class TPMConditionalCircuitNode:
    """One finite immutable node in a conditioned log-space circuit."""

    node_id: int
    node_type: str
    children: tuple[int, ...] = field(default_factory=tuple)
    feature_name: str | None = None
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.node_id, bool) or not isinstance(self.node_id, int):
            raise TypeError("conditional circuit node id must be an integer")
        if self.node_id < 0:
            raise ValueError("conditional circuit node id must be non-negative")
        node_type = _non_empty_string(self.node_type, "node type")
        if node_type not in _SUPPORTED_NODE_TYPES:
            raise ValueError(f"unsupported conditional circuit node type {node_type!r}")
        children = tuple(int(value) for value in self.children)
        if any(value < 0 for value in children):
            raise ValueError("conditional circuit children must be non-negative ids")
        if node_type in {"product", "sum"} and not children:
            raise ValueError(f"{node_type} node requires at least one child")
        if node_type not in {"product", "sum"} and children:
            raise ValueError(f"{node_type} node must not contain children")
        feature_name = self.feature_name
        if node_type.startswith("leaf_"):
            feature_name = _non_empty_string(feature_name, "feature_name")
        elif feature_name is not None:
            raise ValueError(f"{node_type} node must not contain feature_name")
        parameters = _freeze_json(self.parameters, field_name="node parameters")
        if not isinstance(parameters, Mapping):
            raise TypeError("node parameters must be a mapping")
        self._validate_parameters(node_type=node_type, parameters=parameters)
        object.__setattr__(self, "node_type", node_type)
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "feature_name", feature_name)
        object.__setattr__(self, "parameters", parameters)

    @staticmethod
    def _validate_parameters(
        *, node_type: str, parameters: Mapping[str, object]
    ) -> None:
        if node_type == "log_one":
            if set(parameters) != {"log_value"} or parameters["log_value"] != 0.0:
                raise ValueError("log_one node must contain exact log_value 0.0")
            return
        if node_type == "leaf_piecewise":
            x_values = _finite_sequence(
                parameters.get("breakpoints"), field_name="breakpoints"
            )
            y_values = _finite_sequence(
                parameters.get("log_values"), field_name="log_values"
            )
            if len(x_values) < 2 or len(x_values) != len(y_values):
                raise ValueError(
                    "leaf_piecewise breakpoints and log_values must align"
                )
            if any(right <= left for left, right in zip(x_values, x_values[1:])):
                raise ValueError("leaf_piecewise breakpoints must increase")
            return
        if node_type in {"leaf_binary", "leaf_categorical"}:
            densities = _finite_sequence(
                parameters.get("densities"), field_name="densities"
            )
            minimum_count = 2 if node_type == "leaf_binary" else 1
            if len(densities) < minimum_count or any(value < 0.0 for value in densities):
                raise ValueError(f"{node_type} densities are invalid")
            if math.fsum(densities) <= 0.0:
                raise ValueError(f"{node_type} densities must contain positive mass")
            fixed_value = parameters.get("fixed_value")
            if fixed_value is not None:
                if isinstance(fixed_value, bool) or not isinstance(fixed_value, int):
                    raise TypeError("fixed_value must be an integer model index")
                if fixed_value < 0 or fixed_value >= len(densities):
                    raise ValueError("fixed_value is outside the leaf density ordering")
            return
        if node_type == "sum":
            weights = _finite_sequence(
                parameters.get("weights"), field_name="weights"
            )
            if not weights or any(value <= 0.0 for value in weights):
                raise ValueError("sum weights must be finite and positive")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.node_id,
            "type": self.node_type,
        }
        if self.children:
            payload["children"] = list(self.children)
        if self.feature_name is not None:
            payload["feature_name"] = self.feature_name
        payload.update(_thaw_json(self.parameters))
        return payload

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMConditionalCircuitNode":
        if not isinstance(payload, Mapping):
            raise TypeError("conditional circuit node must be a mapping")
        if "id" not in payload or "type" not in payload:
            raise ValueError("conditional circuit node requires id and type")
        node_type = str(payload["type"])
        parameters = {
            str(key): value
            for key, value in payload.items()
            if key not in {"id", "type", "children", "feature_name"}
        }
        if node_type == "log_one" and "log_value" not in parameters:
            parameters["log_value"] = 0.0
        return cls(
            node_id=payload["id"],
            node_type=node_type,
            children=tuple(payload.get("children", ())),
            feature_name=payload.get("feature_name"),
            parameters=parameters,
        )


@dataclass(frozen=True, slots=True)
class TPMConditionalCircuit:
    """One validated finite acyclic conditioned circuit and its treatment metadata."""

    root_id: int
    nodes: tuple[TPMConditionalCircuitNode, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.root_id, bool) or not isinstance(self.root_id, int):
            raise TypeError("conditional circuit root_id must be an integer")
        nodes = tuple(
            node
            if isinstance(node, TPMConditionalCircuitNode)
            else TPMConditionalCircuitNode.from_dict(node)
            for node in self.nodes
        )
        if not nodes:
            raise ValueError("conditional circuit nodes must be nonempty")
        by_id = {node.node_id: node for node in nodes}
        if len(by_id) != len(nodes):
            raise ValueError("conditional circuit node ids must be unique")
        if self.root_id not in by_id:
            raise ValueError(
                f"conditional circuit root_id {self.root_id!r} does not exist"
            )
        active: set[int] = set()
        visited: set[int] = set()

        def visit(node_id: int) -> None:
            if node_id in visited:
                return
            if node_id in active:
                raise ValueError("conditional circuit nodes must form an acyclic graph")
            if node_id not in by_id:
                raise ValueError(f"conditional circuit child {node_id} does not exist")
            active.add(node_id)
            for child_id in by_id[node_id].children:
                visit(child_id)
            active.remove(node_id)
            visited.add(node_id)

        visit(self.root_id)
        for node in nodes:
            if node.node_type == "sum":
                weights = node.parameters.get("weights", ())
                if len(weights) != len(node.children):
                    raise ValueError(
                        "conditional circuit sum weights must match its children"
                    )
        metadata = _freeze_json(self.metadata, field_name="circuit metadata")
        if not isinstance(metadata, Mapping):
            raise TypeError("circuit metadata must be a mapping")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "metadata", metadata)

    def to_dict(self) -> dict[str, object]:
        return {
            "root_id": self.root_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "TPMConditionalCircuit":
        data = _strict_mapping(
            payload,
            record_name="conditional circuit",
            required={"root_id", "nodes", "metadata"},
        )
        nodes = data["nodes"]
        if not _is_sequence(nodes):
            raise TypeError("conditional circuit nodes must be a sequence")
        return cls(
            root_id=data["root_id"],
            nodes=tuple(TPMConditionalCircuitNode.from_dict(node) for node in nodes),
            metadata=data["metadata"],
        )


@dataclass(frozen=True, slots=True)
class TPMConditionalPair:
    """Immutable solver-neutral conditional numerator/denominator pair."""

    source: TPMConditionalSourceReference
    event: TPMConditionalEvent
    feature_schema: tuple[Mapping[str, object], ...]
    retained_decisions: tuple[str, ...]
    marginalized_features: tuple[str, ...]
    validity: tuple[TPMConditionalFeatureValidity, ...]
    encoding: TPMConditionalEncodingPolicy
    numerical_policy: TPMConditionalNumericalPolicy
    numerator: TPMConditionalCircuit
    denominator: TPMConditionalCircuit
    provenance: Mapping[str, object] = field(default_factory=dict)
    pair_id: str = ""
    record_kind: str = CONDITIONAL_PAIR_RECORD_KIND
    schema_version: str = CONDITIONAL_PAIR_SCHEMA_VERSION
    compiler_version: str = CONDITIONAL_PAIR_COMPILER_VERSION

    def __post_init__(self) -> None:
        if self.record_kind != CONDITIONAL_PAIR_RECORD_KIND:
            raise ValueError(
                f"conditional pair record_kind must be {CONDITIONAL_PAIR_RECORD_KIND!r}"
            )
        if self.schema_version != CONDITIONAL_PAIR_SCHEMA_VERSION:
            raise ValueError(
                "conditional pair schema_version must be "
                f"{CONDITIONAL_PAIR_SCHEMA_VERSION!r}"
            )
        if self.compiler_version != CONDITIONAL_PAIR_COMPILER_VERSION:
            raise ValueError(
                "conditional pair compiler_version must be "
                f"{CONDITIONAL_PAIR_COMPILER_VERSION!r}"
            )
        if not isinstance(self.source, TPMConditionalSourceReference):
            raise TypeError("source must be a TPMConditionalSourceReference")
        if not isinstance(self.event, TPMConditionalEvent):
            raise TypeError("event must be a TPMConditionalEvent")
        feature_schema = tuple(
            _freeze_json(value, field_name="feature_schema")
            for value in self.feature_schema
        )
        if not feature_schema or any(
            not isinstance(value, Mapping) for value in feature_schema
        ):
            raise ValueError("feature_schema must contain nonempty mappings")
        feature_names = tuple(
            _non_empty_string(value.get("feature_name"), "feature_schema name")
            for value in feature_schema
        )
        if len(set(feature_names)) != len(feature_names):
            raise ValueError("feature_schema names must be unique")
        retained = tuple(
            _non_empty_string(value, "retained decision")
            for value in self.retained_decisions
        )
        marginalized = tuple(
            _non_empty_string(value, "marginalized feature")
            for value in self.marginalized_features
        )
        if not retained or len(set(retained)) != len(retained):
            raise ValueError("retained_decisions must be nonempty and unique")
        if len(set(marginalized)) != len(marginalized):
            raise ValueError("marginalized_features must be unique")
        if self.event.feature_name not in feature_names:
            raise ValueError("event feature is absent from feature_schema")
        if self.event.feature_name in retained:
            raise ValueError("event feature cannot be a retained decision")
        unknown = sorted((set(retained) | set(marginalized)) - set(feature_names))
        if unknown:
            raise ValueError("pair feature references are unknown: " + ", ".join(unknown))
        if set(retained) & set(marginalized):
            raise ValueError("retained and marginalized features must be disjoint")
        expected_marginalized = set(feature_names) - set(retained) - {
            self.event.feature_name
        }
        if set(marginalized) != expected_marginalized:
            raise ValueError(
                "marginalized_features must contain every nonevent nondecision feature"
            )
        validity = tuple(
            value
            if isinstance(value, TPMConditionalFeatureValidity)
            else TPMConditionalFeatureValidity.from_dict(value)
            for value in self.validity
        )
        if tuple(value.feature_name for value in validity) != retained:
            raise ValueError(
                "validity records must follow and exactly cover retained_decisions"
            )
        if not isinstance(self.encoding, TPMConditionalEncodingPolicy):
            raise TypeError("encoding must be a TPMConditionalEncodingPolicy")
        if not isinstance(self.numerical_policy, TPMConditionalNumericalPolicy):
            raise TypeError(
                "numerical_policy must be a TPMConditionalNumericalPolicy"
            )
        if not isinstance(self.numerator, TPMConditionalCircuit):
            raise TypeError("numerator must be a TPMConditionalCircuit")
        if not isinstance(self.denominator, TPMConditionalCircuit):
            raise TypeError("denominator must be a TPMConditionalCircuit")
        if self.numerator.metadata.get("event_treatment") != "fixed":
            raise ValueError("numerator circuit must declare fixed event treatment")
        if self.denominator.metadata.get("event_treatment") != "marginalized":
            raise ValueError(
                "denominator circuit must declare marginalized event treatment"
            )
        provenance = _freeze_json(self.provenance, field_name="provenance")
        if not isinstance(provenance, Mapping):
            raise TypeError("provenance must be a mapping")
        object.__setattr__(self, "feature_schema", feature_schema)
        object.__setattr__(self, "retained_decisions", retained)
        object.__setattr__(self, "marginalized_features", marginalized)
        object.__setattr__(self, "validity", validity)
        object.__setattr__(self, "provenance", provenance)
        expected_id = hashlib.sha256(
            canonical_conditional_json_bytes(self.identity_payload())
        ).hexdigest()
        if self.pair_id:
            supplied_id = _sha256_digest(self.pair_id, field_name="pair_id")
            if supplied_id != expected_id:
                raise ValueError(
                    f"conditional pair pair_id mismatch: expected {expected_id}, "
                    f"found {supplied_id}"
                )
        object.__setattr__(self, "pair_id", expected_id)

    def identity_payload(self) -> dict[str, object]:
        provenance = {
            key: _thaw_json(value)
            for key, value in self.provenance.items()
            if key not in {"created_at", "output_path", "publication_timestamp"}
        }
        return {
            "record_kind": self.record_kind,
            "schema_version": self.schema_version,
            "compiler_version": self.compiler_version,
            "source": self.source.to_dict(),
            "event": self.event.to_dict(),
            "feature_schema": _thaw_json(self.feature_schema),
            "retained_decisions": list(self.retained_decisions),
            "marginalized_features": list(self.marginalized_features),
            "validity": [value.to_dict() for value in self.validity],
            "encoding": self.encoding.to_dict(),
            "numerical_policy": self.numerical_policy.to_dict(),
            "numerator": self.numerator.to_dict(),
            "denominator": self.denominator.to_dict(),
            "provenance": provenance,
        }

    def to_dict(self) -> dict[str, object]:
        return {"pair_id": self.pair_id, **self.identity_payload()}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "TPMConditionalPair":
        data = _strict_mapping(
            payload,
            record_name="conditional pair",
            required={
                "record_kind",
                "schema_version",
                "compiler_version",
                "pair_id",
                "source",
                "event",
                "feature_schema",
                "retained_decisions",
                "marginalized_features",
                "validity",
                "encoding",
                "numerical_policy",
                "numerator",
                "denominator",
                "provenance",
            },
        )
        for name in (
            "feature_schema",
            "retained_decisions",
            "marginalized_features",
            "validity",
        ):
            if not _is_sequence(data[name]):
                raise TypeError(f"conditional pair {name} must be a sequence")
        return cls(
            source=TPMConditionalSourceReference.from_dict(data["source"]),
            event=TPMConditionalEvent.from_dict(data["event"]),
            feature_schema=tuple(data["feature_schema"]),
            retained_decisions=tuple(data["retained_decisions"]),
            marginalized_features=tuple(data["marginalized_features"]),
            validity=tuple(
                TPMConditionalFeatureValidity.from_dict(value)
                for value in data["validity"]
            ),
            encoding=TPMConditionalEncodingPolicy.from_dict(data["encoding"]),
            numerical_policy=TPMConditionalNumericalPolicy.from_dict(
                data["numerical_policy"]
            ),
            numerator=TPMConditionalCircuit.from_dict(data["numerator"]),
            denominator=TPMConditionalCircuit.from_dict(data["denominator"]),
            provenance=data["provenance"],
            pair_id=data["pair_id"],
            record_kind=data["record_kind"],
            schema_version=data["schema_version"],
            compiler_version=data["compiler_version"],
        )


@dataclass(frozen=True, slots=True)
class TPMContinuousDecisionMapping:
    """Import-light association from one feature to a physical Pyomo expression."""

    feature_name: str
    physical_expression: object

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        if self.physical_expression is None:
            raise ValueError("physical_expression must not be None")


@dataclass(frozen=True, slots=True)
class TPMBinaryDecisionMapping:
    """Import-light association from one binary feature to a caller variable."""

    feature_name: str
    caller_variable: object

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        if self.caller_variable is None:
            raise ValueError("caller_variable must not be None")


@dataclass(frozen=True, slots=True)
class TPMCategoricalDecisionMapping:
    """Ordered labelled one-hot mapping for one categorical feature."""

    feature_name: str
    ordered_indicators: tuple[tuple[object, object], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        entries: list[tuple[object, object]] = []
        for index, entry in enumerate(self.ordered_indicators):
            if not _is_sequence(entry) or len(entry) != 2:
                raise TypeError(
                    f"ordered_indicators[{index}] must be a (category, indicator) pair"
                )
            label = _freeze_json(
                entry[0], field_name=f"ordered_indicators[{index}] category"
            )
            indicator = entry[1]
            if indicator is None:
                raise ValueError(
                    f"ordered_indicators[{index}] indicator must not be None"
                )
            entries.append((label, indicator))
        if not entries:
            raise ValueError("ordered_indicators must be nonempty")
        labels = tuple(label for label, _ in entries)
        if len(set(labels)) != len(labels):
            raise ValueError("ordered categorical labels must be distinct")
        indicators = tuple(indicator for _, indicator in entries)
        if len({id(value) for value in indicators}) != len(indicators):
            raise ValueError("ordered categorical indicators must be distinct")
        object.__setattr__(self, "ordered_indicators", tuple(entries))


@dataclass(frozen=True, slots=True)
class TPMConditionalDecisionLink:
    """Runtime metadata for one caller-owned continuous coordinate link."""

    feature_name: str
    physical_expression: object
    caller_variables: tuple[object, ...]
    model_coordinate: object
    coordinate_link: object
    physical_lower: object
    physical_upper: object
    model_lower: object
    model_upper: object
    normalization: Mapping[str, object]
    approximation_domain: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        caller_variables = tuple(self.caller_variables)
        if not caller_variables or len({id(value) for value in caller_variables}) != len(
            caller_variables
        ):
            raise ValueError("caller_variables must be nonempty and distinct")
        object.__setattr__(self, "caller_variables", caller_variables)
        for field_name in (
            "physical_expression",
            "model_coordinate",
            "coordinate_link",
            "physical_lower",
            "physical_upper",
            "model_lower",
            "model_upper",
        ):
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be None")
        normalization = _freeze_json(
            self.normalization, field_name="decision-link normalization"
        )
        approximation_domain = _freeze_json(
            self.approximation_domain,
            field_name="decision-link approximation_domain",
        )
        if not isinstance(normalization, Mapping) or not isinstance(
            approximation_domain, Mapping
        ):
            raise TypeError("decision-link semantics must be mappings")
        object.__setattr__(self, "normalization", normalization)
        object.__setattr__(self, "approximation_domain", approximation_domain)


@dataclass(frozen=True, slots=True)
class TPMBinaryDecisionLink:
    """Runtime metadata for one caller-owned binary variable."""

    feature_name: str
    caller_variable: object
    declared_ordering: tuple[object, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        if self.caller_variable is None:
            raise ValueError("caller_variable must not be None")
        ordering = tuple(
            _freeze_json(value, field_name="binary declared ordering")
            for value in self.declared_ordering
        )
        if len(ordering) != 2 or ordering[0] == ordering[1]:
            raise ValueError("binary declared_ordering must contain two values")
        object.__setattr__(self, "declared_ordering", ordering)


@dataclass(frozen=True, slots=True)
class TPMCategoricalDecisionLink:
    """Runtime metadata for ordered caller one-hot indicators."""

    feature_name: str
    ordered_indicators: tuple[tuple[object, object], ...]
    declared_ordering: tuple[object, ...]
    exactly_one: object

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            _non_empty_string(self.feature_name, "feature_name"),
        )
        entries = tuple(self.ordered_indicators)
        ordering = tuple(
            _freeze_json(value, field_name="categorical declared ordering")
            for value in self.declared_ordering
        )
        if not entries or tuple(value for value, _ in entries) != ordering:
            raise ValueError(
                "ordered_indicators must exactly follow declared_ordering"
            )
        if len({id(indicator) for _, indicator in entries}) != len(entries):
            raise ValueError("categorical indicators must be distinct")
        if self.exactly_one is None:
            raise ValueError("exactly_one must not be None")
        object.__setattr__(self, "ordered_indicators", entries)
        object.__setattr__(self, "declared_ordering", ordering)


@dataclass(frozen=True, slots=True)
class TPMConditionalAttachment:
    """Frozen runtime result for one namespaced caller-model attachment."""

    pair_id: str
    namespace: str
    retained_decisions: tuple[str, ...]
    block: object
    numerator_root: object
    denominator_root: object
    conditional_log_risk: object
    decision_links: Mapping[
        str,
        TPMConditionalDecisionLink
        | TPMBinaryDecisionLink
        | TPMCategoricalDecisionLink,
    ]
    pair_metadata: Mapping[str, object]
    diagnostic_components: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pair_id",
            _sha256_digest(self.pair_id, field_name="pair_id"),
        )
        object.__setattr__(
            self,
            "namespace",
            _non_empty_string(self.namespace, "namespace"),
        )
        retained = tuple(
            _non_empty_string(value, "retained decision")
            for value in self.retained_decisions
        )
        if not retained or len(set(retained)) != len(retained):
            raise ValueError("retained_decisions must be nonempty and unique")
        links = dict(self.decision_links)
        if tuple(links) != retained:
            raise ValueError(
                "decision_links must follow and exactly cover retained_decisions"
            )
        supported_links = (
            TPMConditionalDecisionLink,
            TPMBinaryDecisionLink,
            TPMCategoricalDecisionLink,
        )
        if any(
            not isinstance(value, supported_links) or value.feature_name != name
            for name, value in links.items()
        ):
            raise TypeError("decision_links must contain matching typed links")
        for field_name in (
            "block",
            "numerator_root",
            "denominator_root",
            "conditional_log_risk",
        ):
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be None")
        pair_metadata = _freeze_json(
            self.pair_metadata, field_name="attachment pair_metadata"
        )
        if not isinstance(pair_metadata, Mapping):
            raise TypeError("pair_metadata must be a mapping")
        diagnostics = tuple(
            _non_empty_string(value, "diagnostic component")
            for value in self.diagnostic_components
        )
        if len(set(diagnostics)) != len(diagnostics):
            raise ValueError("diagnostic_components must be unique")
        object.__setattr__(self, "retained_decisions", retained)
        object.__setattr__(self, "decision_links", MappingProxyType(links))
        object.__setattr__(self, "pair_metadata", pair_metadata)
        object.__setattr__(self, "diagnostic_components", diagnostics)


@dataclass(frozen=True, slots=True)
class TPMConditionalAttachmentDiagnostics:
    """Read-only numerical state observed from one solved attachment."""

    pair_id: str
    namespace: str
    solver_metadata: Mapping[str, object]
    numerator_log: float
    denominator_log: float
    conditional_log_risk: float
    conditional_probability: float
    classification: str
    constraint_residuals: Mapping[str, float]
    maximum_constraint_residual: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pair_id",
            _sha256_digest(self.pair_id, field_name="pair_id"),
        )
        object.__setattr__(
            self,
            "namespace",
            _non_empty_string(self.namespace, "namespace"),
        )
        solver = _strict_mapping(
            self.solver_metadata,
            record_name="conditional solver metadata",
            required={
                "solver_name",
                "solver_version",
                "status",
                "termination_condition",
            },
        )
        normalized_solver = {
            name: _non_empty_string(value, f"solver_metadata.{name}")
            for name, value in solver.items()
        }
        object.__setattr__(
            self,
            "solver_metadata",
            _freeze_json(
                normalized_solver, field_name="conditional solver metadata"
            ),
        )
        for field_name in (
            "numerator_log",
            "denominator_log",
            "conditional_log_risk",
            "conditional_probability",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite_float(getattr(self, field_name), field_name=field_name),
            )
        if self.conditional_probability < 0.0:
            raise ValueError("conditional_probability must be non-negative")
        _require_numeric_identity(
            self.conditional_log_risk,
            self.numerator_log - self.denominator_log,
            field_name="conditional_log_risk",
        )
        _require_numeric_identity(
            self.conditional_probability,
            math.exp(self.conditional_log_risk),
            field_name="conditional_probability",
        )
        if self.classification not in {"valid", "positive-numerical-noise"}:
            raise ValueError(
                "classification must be 'valid' or 'positive-numerical-noise'"
            )
        if not isinstance(self.constraint_residuals, Mapping):
            raise TypeError("constraint_residuals must be a mapping")
        residuals: dict[str, float] = {}
        for raw_name, raw_value in self.constraint_residuals.items():
            name = _non_empty_string(raw_name, "constraint residual name")
            value = _finite_float(
                raw_value, field_name=f"constraint_residuals.{name}"
            )
            if value < 0.0:
                raise ValueError("constraint residuals must be non-negative")
            residuals[name] = value
        maximum = _finite_float(
            self.maximum_constraint_residual,
            field_name="maximum_constraint_residual",
        )
        if maximum < 0.0:
            raise ValueError("maximum_constraint_residual must be non-negative")
        expected_maximum = max(residuals.values(), default=0.0)
        _require_numeric_identity(
            maximum,
            expected_maximum,
            field_name="maximum_constraint_residual",
        )
        object.__setattr__(
            self,
            "constraint_residuals",
            MappingProxyType(residuals),
        )
        object.__setattr__(self, "maximum_constraint_residual", maximum)

    def to_dict(self) -> dict[str, object]:
        return {
            "pair_id": self.pair_id,
            "namespace": self.namespace,
            "solver_metadata": _thaw_json(self.solver_metadata),
            "numerator_log": self.numerator_log,
            "denominator_log": self.denominator_log,
            "conditional_log_risk": self.conditional_log_risk,
            "conditional_probability": self.conditional_probability,
            "classification": self.classification,
            "constraint_residuals": dict(self.constraint_residuals),
            "maximum_constraint_residual": self.maximum_constraint_residual,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMConditionalAttachmentDiagnostics":
        data = _strict_mapping(
            payload,
            record_name="conditional attachment diagnostics",
            required={
                "pair_id",
                "namespace",
                "solver_metadata",
                "numerator_log",
                "denominator_log",
                "conditional_log_risk",
                "conditional_probability",
                "classification",
                "constraint_residuals",
                "maximum_constraint_residual",
            },
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class TPMConditionalEvaluation:
    """Raw direct evaluation of one immutable conditional pair."""

    pair_id: str
    assignment_mode: str
    assignments: Mapping[str, object]
    numerator_log: float
    denominator_log: float
    conditional_log_risk: float
    conditional_probability: float
    classification: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pair_id",
            _sha256_digest(self.pair_id, field_name="pair_id"),
        )
        if self.assignment_mode not in {"declared-domain", "model-coordinate"}:
            raise ValueError(
                "assignment_mode must be 'declared-domain' or 'model-coordinate'"
            )
        assignments = _freeze_json(self.assignments, field_name="assignments")
        if not isinstance(assignments, Mapping):
            raise TypeError("assignments must be a mapping")
        object.__setattr__(self, "assignments", assignments)
        for field_name in (
            "numerator_log",
            "denominator_log",
            "conditional_log_risk",
            "conditional_probability",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite_float(getattr(self, field_name), field_name=field_name),
            )
        if self.conditional_probability < 0.0:
            raise ValueError("conditional_probability must be non-negative")
        if self.classification not in {"valid", "positive-numerical-noise"}:
            raise ValueError(
                "classification must be 'valid' or 'positive-numerical-noise'"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "pair_id": self.pair_id,
            "assignment_mode": self.assignment_mode,
            "assignments": _thaw_json(self.assignments),
            "numerator_log": self.numerator_log,
            "denominator_log": self.denominator_log,
            "conditional_log_risk": self.conditional_log_risk,
            "conditional_probability": self.conditional_probability,
            "classification": self.classification,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMConditionalEvaluation":
        data = _strict_mapping(
            payload,
            record_name="conditional direct evaluation",
            required={
                "pair_id",
                "assignment_mode",
                "assignments",
                "numerator_log",
                "denominator_log",
                "conditional_log_risk",
                "conditional_probability",
                "classification",
            },
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class TPMNativeConditionalEvaluation:
    """Raw current-SPFlow numerator/denominator evidence for compiler fidelity."""

    pair_id: str
    artifact_id: str
    assignments: Mapping[str, object]
    numerator_log: float
    denominator_log: float
    conditional_log_risk: float
    conditional_probability: float
    backend_generation: str
    backend_api_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pair_id",
            _sha256_digest(self.pair_id, field_name="pair_id"),
        )
        object.__setattr__(
            self,
            "artifact_id",
            _non_empty_string(self.artifact_id, "artifact_id"),
        )
        assignments = _freeze_json(self.assignments, field_name="assignments")
        if not isinstance(assignments, Mapping):
            raise TypeError("assignments must be a mapping")
        object.__setattr__(self, "assignments", assignments)
        for field_name in (
            "numerator_log",
            "denominator_log",
            "conditional_log_risk",
            "conditional_probability",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite_float(getattr(self, field_name), field_name=field_name),
            )
        if self.conditional_probability < 0.0:
            raise ValueError("conditional_probability must be non-negative")
        object.__setattr__(
            self,
            "backend_generation",
            _non_empty_string(self.backend_generation, "backend_generation"),
        )
        object.__setattr__(
            self,
            "backend_api_version",
            _non_empty_string(self.backend_api_version, "backend_api_version"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "pair_id": self.pair_id,
            "artifact_id": self.artifact_id,
            "assignments": _thaw_json(self.assignments),
            "numerator_log": self.numerator_log,
            "denominator_log": self.denominator_log,
            "conditional_log_risk": self.conditional_log_risk,
            "conditional_probability": self.conditional_probability,
            "backend_generation": self.backend_generation,
            "backend_api_version": self.backend_api_version,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMNativeConditionalEvaluation":
        data = _strict_mapping(
            payload,
            record_name="native conditional evaluation",
            required={
                "pair_id",
                "artifact_id",
                "assignments",
                "numerator_log",
                "denominator_log",
                "conditional_log_risk",
                "conditional_probability",
                "backend_generation",
                "backend_api_version",
            },
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class TPMEmbeddingParityEvidence:
    """Immutable direct-versus-attached acceptance evidence for one pair."""

    pair_id: str
    encoding: Mapping[str, object]
    numerical_policy: Mapping[str, object]
    cases: tuple[Mapping[str, object], ...]
    metric_definitions: Mapping[str, object]
    evaluator_version: str = CONDITIONAL_EVIDENCE_EVALUATOR_VERSION
    provenance: Mapping[str, object] = field(default_factory=dict)
    evidence_id: str = ""
    record_kind: str = CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND
    schema_version: str = CONDITIONAL_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.record_kind != CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND:
            raise ValueError(
                "embedding parity record_kind must be "
                f"{CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND!r}"
            )
        if self.schema_version != CONDITIONAL_EVIDENCE_SCHEMA_VERSION:
            raise ValueError(
                "embedding parity schema_version must be "
                f"{CONDITIONAL_EVIDENCE_SCHEMA_VERSION!r}"
            )
        object.__setattr__(
            self,
            "pair_id",
            _sha256_digest(self.pair_id, field_name="pair_id"),
        )
        object.__setattr__(
            self,
            "evaluator_version",
            _non_empty_string(self.evaluator_version, "evaluator_version"),
        )
        encoding = _frozen_mapping(self.encoding, field_name="evidence encoding")
        numerical_policy = _frozen_mapping(
            self.numerical_policy, field_name="evidence numerical_policy"
        )
        tolerances = _evidence_tolerances(numerical_policy)
        metrics = _frozen_mapping(
            self.metric_definitions,
            field_name="embedding parity metric_definitions",
        )
        _validate_parity_metric_definitions(metrics)
        cases = tuple(
            _normalize_parity_case(
                value,
                pair_id=self.pair_id,
                parity_tolerance=tolerances[
                    "embedding_parity_absolute_tolerance"
                ],
                residual_tolerance=tolerances[
                    "constraint_residual_absolute_tolerance"
                ],
            )
            for value in self.cases
        )
        if not cases:
            raise ValueError("embedding parity evidence requires at least one case")
        case_names = tuple(str(value["case_name"]) for value in cases)
        if len(set(case_names)) != len(case_names):
            raise ValueError("embedding parity case names must be unique")
        provenance = _frozen_mapping(
            self.provenance, field_name="embedding parity provenance"
        )
        object.__setattr__(self, "encoding", encoding)
        object.__setattr__(self, "numerical_policy", numerical_policy)
        object.__setattr__(self, "metric_definitions", metrics)
        object.__setattr__(self, "cases", cases)
        object.__setattr__(self, "provenance", provenance)
        expected_id = hashlib.sha256(
            canonical_conditional_json_bytes(self.identity_payload())
        ).hexdigest()
        if self.evidence_id:
            supplied = _sha256_digest(
                self.evidence_id, field_name="evidence_id"
            )
            if supplied != expected_id:
                raise ValueError(
                    "embedding parity evidence_id mismatch: "
                    f"expected {expected_id}, found {supplied}"
                )
        object.__setattr__(self, "evidence_id", expected_id)

    @property
    def accepted(self) -> bool:
        return all(bool(value["accepted"]) for value in self.cases)

    def identity_payload(self) -> dict[str, object]:
        return {
            "record_kind": self.record_kind,
            "schema_version": self.schema_version,
            "evaluator_version": self.evaluator_version,
            "pair_id": self.pair_id,
            "encoding": _thaw_json(self.encoding),
            "numerical_policy": _thaw_json(self.numerical_policy),
            "cases": _thaw_json(self.cases),
            "metric_definitions": _thaw_json(self.metric_definitions),
            "provenance": _identity_provenance(self.provenance),
        }

    def to_dict(self) -> dict[str, object]:
        return {"evidence_id": self.evidence_id, **self.identity_payload()}

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMEmbeddingParityEvidence":
        data = _strict_mapping(
            payload,
            record_name="embedding parity evidence",
            required={
                "record_kind",
                "schema_version",
                "evaluator_version",
                "evidence_id",
                "pair_id",
                "encoding",
                "numerical_policy",
                "cases",
                "metric_definitions",
                "provenance",
            },
        )
        if not _is_sequence(data["cases"]):
            raise TypeError("embedding parity cases must be a sequence")
        return cls(
            pair_id=data["pair_id"],
            encoding=data["encoding"],
            numerical_policy=data["numerical_policy"],
            cases=tuple(data["cases"]),
            metric_definitions=data["metric_definitions"],
            evaluator_version=data["evaluator_version"],
            provenance=data["provenance"],
            evidence_id=data["evidence_id"],
            record_kind=data["record_kind"],
            schema_version=data["schema_version"],
        )


@dataclass(frozen=True, slots=True)
class TPMCompilerFidelityEvidence:
    """Immutable compiled-versus-native scientific evidence without a gate."""

    pair_id: str
    source: TPMConditionalSourceReference
    encoding: Mapping[str, object]
    numerical_policy: Mapping[str, object]
    cases: tuple[Mapping[str, object], ...]
    metric_definitions: Mapping[str, object]
    evaluator_version: str = CONDITIONAL_EVIDENCE_EVALUATOR_VERSION
    provenance: Mapping[str, object] = field(default_factory=dict)
    evidence_id: str = ""
    record_kind: str = CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND
    schema_version: str = CONDITIONAL_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.record_kind != CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND:
            raise ValueError(
                "compiler fidelity record_kind must be "
                f"{CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND!r}"
            )
        if self.schema_version != CONDITIONAL_EVIDENCE_SCHEMA_VERSION:
            raise ValueError(
                "compiler fidelity schema_version must be "
                f"{CONDITIONAL_EVIDENCE_SCHEMA_VERSION!r}"
            )
        object.__setattr__(
            self,
            "pair_id",
            _sha256_digest(self.pair_id, field_name="pair_id"),
        )
        if not isinstance(self.source, TPMConditionalSourceReference):
            raise TypeError("source must be a TPMConditionalSourceReference")
        object.__setattr__(
            self,
            "evaluator_version",
            _non_empty_string(self.evaluator_version, "evaluator_version"),
        )
        encoding = _frozen_mapping(self.encoding, field_name="evidence encoding")
        numerical_policy = _frozen_mapping(
            self.numerical_policy, field_name="evidence numerical_policy"
        )
        _evidence_tolerances(numerical_policy)
        metrics = _frozen_mapping(
            self.metric_definitions,
            field_name="compiler fidelity metric_definitions",
        )
        _validate_fidelity_metric_definitions(metrics)
        cases = tuple(
            _normalize_fidelity_case(
                value,
                pair_id=self.pair_id,
                source=self.source,
            )
            for value in self.cases
        )
        if not cases:
            raise ValueError("compiler fidelity evidence requires at least one case")
        case_names = tuple(str(value["case_name"]) for value in cases)
        if len(set(case_names)) != len(case_names):
            raise ValueError("compiler fidelity case names must be unique")
        provenance = _frozen_mapping(
            self.provenance, field_name="compiler fidelity provenance"
        )
        object.__setattr__(self, "encoding", encoding)
        object.__setattr__(self, "numerical_policy", numerical_policy)
        object.__setattr__(self, "metric_definitions", metrics)
        object.__setattr__(self, "cases", cases)
        object.__setattr__(self, "provenance", provenance)
        expected_id = hashlib.sha256(
            canonical_conditional_json_bytes(self.identity_payload())
        ).hexdigest()
        if self.evidence_id:
            supplied = _sha256_digest(
                self.evidence_id, field_name="evidence_id"
            )
            if supplied != expected_id:
                raise ValueError(
                    "compiler fidelity evidence_id mismatch: "
                    f"expected {expected_id}, found {supplied}"
                )
        object.__setattr__(self, "evidence_id", expected_id)

    def identity_payload(self) -> dict[str, object]:
        return {
            "record_kind": self.record_kind,
            "schema_version": self.schema_version,
            "evaluator_version": self.evaluator_version,
            "pair_id": self.pair_id,
            "source": self.source.to_dict(),
            "encoding": _thaw_json(self.encoding),
            "numerical_policy": _thaw_json(self.numerical_policy),
            "cases": _thaw_json(self.cases),
            "metric_definitions": _thaw_json(self.metric_definitions),
            "provenance": _identity_provenance(self.provenance),
        }

    def to_dict(self) -> dict[str, object]:
        return {"evidence_id": self.evidence_id, **self.identity_payload()}

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "TPMCompilerFidelityEvidence":
        data = _strict_mapping(
            payload,
            record_name="compiler fidelity evidence",
            required={
                "record_kind",
                "schema_version",
                "evaluator_version",
                "evidence_id",
                "pair_id",
                "source",
                "encoding",
                "numerical_policy",
                "cases",
                "metric_definitions",
                "provenance",
            },
        )
        if not _is_sequence(data["cases"]):
            raise TypeError("compiler fidelity cases must be a sequence")
        return cls(
            pair_id=data["pair_id"],
            source=TPMConditionalSourceReference.from_dict(data["source"]),
            encoding=data["encoding"],
            numerical_policy=data["numerical_policy"],
            cases=tuple(data["cases"]),
            metric_definitions=data["metric_definitions"],
            evaluator_version=data["evaluator_version"],
            provenance=data["provenance"],
            evidence_id=data["evidence_id"],
            record_kind=data["record_kind"],
            schema_version=data["schema_version"],
        )


@dataclass(frozen=True, slots=True)
class TPMConditionalPublication:
    """Outcome of one create-only or verified-identical publication."""

    path: Path
    created: bool
    reused: bool


def canonical_conditional_json_bytes(value: object) -> bytes:
    """Encode one record or finite JSON value using the canonical pair form."""

    payload = value.to_dict() if hasattr(value, "to_dict") else value
    finite_payload = _thaw_json(
        _freeze_json(payload, field_name="canonical conditional JSON")
    )
    return (
        json.dumps(
            finite_payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def load_conditional_pair(path: str | Path) -> TPMConditionalPair:
    """Load and fully validate one published pair without backend imports."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"conditional pair {source} is unreadable or corrupt") from exc
    if not isinstance(payload, Mapping):
        raise TypeError(f"conditional pair {source} must contain a JSON object")
    return TPMConditionalPair.from_dict(payload)


def publish_conditional_pair(
    pair: TPMConditionalPair,
    path: str | Path,
) -> TPMConditionalPublication:
    """Create one canonical pair path or verify byte-identical existing evidence."""

    if not isinstance(pair, TPMConditionalPair):
        raise TypeError("pair must be a TPMConditionalPair")
    output_path = Path(path)
    payload = canonical_conditional_json_bytes(pair)
    return _publish_create_or_verify(
        output_path,
        payload,
        validator=load_conditional_pair,
        expected_identity=pair.pair_id,
    )


def load_conditional_evidence(
    path: str | Path,
) -> TPMEmbeddingParityEvidence | TPMCompilerFidelityEvidence:
    """Load and validate one focused conditional evidence record."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"conditional evidence {source} is unreadable or corrupt"
        ) from exc
    if not isinstance(payload, Mapping):
        raise TypeError(f"conditional evidence {source} must contain a JSON object")
    record_kind = payload.get("record_kind")
    if record_kind == CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND:
        return TPMEmbeddingParityEvidence.from_dict(payload)
    if record_kind == CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND:
        return TPMCompilerFidelityEvidence.from_dict(payload)
    raise ValueError(
        f"conditional evidence {source} has unsupported record_kind {record_kind!r}"
    )


def publish_conditional_evidence(
    evidence: TPMEmbeddingParityEvidence | TPMCompilerFidelityEvidence,
    path: str | Path,
) -> TPMConditionalPublication:
    """Create one evidence path or verify an identical published record."""

    if not isinstance(
        evidence, (TPMEmbeddingParityEvidence, TPMCompilerFidelityEvidence)
    ):
        raise TypeError("evidence must be a conditional parity or fidelity record")
    output_path = Path(path)
    payload = canonical_conditional_json_bytes(evidence)
    return _publish_create_or_verify(
        output_path,
        payload,
        validator=load_conditional_evidence,
        expected_identity=evidence.evidence_id,
        identity_attribute="evidence_id",
    )


def _publish_create_or_verify(
    path: Path,
    payload: bytes,
    *,
    validator: Any,
    expected_identity: str,
    identity_attribute: str = "pair_id",
) -> TPMConditionalPublication:
    parent = path.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"conditional publication directory does not exist: {parent}")

    def verify_existing() -> TPMConditionalPublication:
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise FileExistsError(
                f"conditional publication target {path} exists but cannot be verified"
            ) from exc
        if existing != payload:
            raise FileExistsError(
                f"conditional publication target {path} conflicts with immutable evidence"
            )
        validated = validator(path)
        actual_identity = getattr(validated, identity_attribute, None)
        if actual_identity != expected_identity:
            raise FileExistsError(
                f"conditional publication target {path} has a mismatched identity"
            )
        return TPMConditionalPublication(path=path, created=False, reused=True)

    if path.exists():
        return verify_existing()

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary_path = Path(temporary_name)
    linked = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, path)
            linked = True
        except FileExistsError:
            return verify_existing()
        _fsync_directory(parent)
        return TPMConditionalPublication(path=path, created=True, reused=False)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        if not linked and path.exists():
            # A concurrently published final name is never removed here.
            pass


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _frozen_mapping(
    value: object,
    *,
    field_name: str,
) -> Mapping[str, object]:
    frozen = _freeze_json(value, field_name=field_name)
    if not isinstance(frozen, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return frozen


def _identity_provenance(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: _thaw_json(item)
        for key, item in value.items()
        if key not in {
            "created_at",
            "output_path",
            "publication_timestamp",
        }
    }


def _evidence_tolerances(
    numerical_policy: Mapping[str, object],
) -> dict[str, float]:
    data = _strict_mapping(
        numerical_policy,
        record_name="evidence numerical policy",
        required={"tolerances"},
    )
    if not isinstance(data["tolerances"], Mapping):
        raise TypeError("evidence numerical policy tolerances must be a mapping")
    tolerances = {
        str(name): _finite_float(
            value, field_name=f"evidence tolerance {name}"
        )
        for name, value in data["tolerances"].items()
    }
    missing = sorted(_REQUIRED_NUMERICAL_TOLERANCES - set(tolerances))
    if missing:
        raise ValueError(
            "evidence numerical policy is missing tolerances: "
            + ", ".join(missing)
        )
    for name in (
        "embedding_parity_absolute_tolerance",
        "constraint_residual_absolute_tolerance",
        "positive_log_risk_limit",
    ):
        if tolerances[name] <= 0.0:
            raise ValueError(f"evidence tolerance {name} must be positive")
    if tolerances["domain_membership_tolerance"] != 0.0:
        raise ValueError("domain membership tolerance must remain exactly zero")
    return tolerances


def _validate_parity_metric_definitions(
    metrics: Mapping[str, object],
) -> None:
    expected = {
        "delta_direction": "attached-minus-direct",
        "acceptance_gate": "absolute-1e-6",
        "constraint_residual": (
            "active-attachment-only-violation-magnitude"
        ),
        "probability_delta": "diagnostic-not-gated",
    }
    for name, expected_value in expected.items():
        if metrics.get(name) != expected_value:
            raise ValueError(
                f"embedding parity metric {name} must be {expected_value!r}"
            )


def _validate_fidelity_metric_definitions(
    metrics: Mapping[str, object],
) -> None:
    expected = {
        "delta_direction": "compiled-minus-native",
        "numerical_gate": "none",
    }
    for name, expected_value in expected.items():
        if metrics.get(name) != expected_value:
            raise ValueError(
                f"compiler fidelity metric {name} must be {expected_value!r}"
            )


def _numeric_metric_mapping(
    value: object,
    *,
    field_name: str,
    required: set[str],
) -> dict[str, float]:
    data = _strict_mapping(
        value,
        record_name=field_name,
        required=required,
    )
    return {
        name: _finite_float(raw_value, field_name=f"{field_name}.{name}")
        for name, raw_value in data.items()
    }


def _normalize_parity_case(
    value: object,
    *,
    pair_id: str,
    parity_tolerance: float,
    residual_tolerance: float,
) -> Mapping[str, object]:
    data = _strict_mapping(
        value,
        record_name="embedding parity case",
        required={
            "case_name",
            "assignment_mode",
            "assignments",
            "direct",
            "attached",
            "deltas",
            "absolute_errors",
            "accepted",
        },
    )
    case_name = _non_empty_string(data["case_name"], "parity case_name")
    direct = TPMConditionalEvaluation.from_dict(data["direct"])
    attached = TPMConditionalAttachmentDiagnostics.from_dict(data["attached"])
    if direct.pair_id != pair_id or attached.pair_id != pair_id:
        raise ValueError("embedding parity case pair identity is mismatched")
    if data["assignment_mode"] != direct.assignment_mode:
        raise ValueError("embedding parity assignment_mode is mismatched")
    assignments = _frozen_mapping(
        data["assignments"], field_name="embedding parity assignments"
    )
    if assignments != direct.assignments:
        raise ValueError("embedding parity assignments differ from direct evaluation")
    fields = {
        "numerator_log",
        "denominator_log",
        "conditional_log_risk",
        "conditional_probability",
    }
    deltas = _numeric_metric_mapping(
        data["deltas"],
        field_name="embedding parity deltas",
        required=fields,
    )
    absolute_errors = _numeric_metric_mapping(
        data["absolute_errors"],
        field_name="embedding parity absolute_errors",
        required=fields,
    )
    for name in fields:
        expected_delta = float(getattr(attached, name)) - float(
            getattr(direct, name)
        )
        _require_numeric_identity(
            deltas[name],
            expected_delta,
            field_name=f"embedding parity delta {name}",
        )
        _require_numeric_identity(
            absolute_errors[name],
            abs(expected_delta),
            field_name=f"embedding parity absolute error {name}",
        )
        if absolute_errors[name] < 0.0:
            raise ValueError("embedding parity absolute errors must be non-negative")
    if not isinstance(data["accepted"], bool):
        raise TypeError("embedding parity accepted must be boolean")
    solver = attached.solver_metadata
    solver_success = (
        str(solver["status"]).casefold() == "ok"
        and str(solver["termination_condition"]).casefold() == "optimal"
    )
    expected_accepted = (
        solver_success
        and all(
            absolute_errors[name] <= parity_tolerance
            for name in (
                "numerator_log",
                "denominator_log",
                "conditional_log_risk",
            )
        )
        and attached.maximum_constraint_residual <= residual_tolerance
    )
    if data["accepted"] is not expected_accepted:
        raise ValueError("embedding parity accepted verdict is inconsistent")
    return _frozen_mapping(
        {
            "case_name": case_name,
            "assignment_mode": direct.assignment_mode,
            "assignments": _thaw_json(assignments),
            "direct": direct.to_dict(),
            "attached": attached.to_dict(),
            "deltas": deltas,
            "absolute_errors": absolute_errors,
            "accepted": expected_accepted,
        },
        field_name=f"embedding parity case {case_name}",
    )


def _normalize_fidelity_case(
    value: object,
    *,
    pair_id: str,
    source: TPMConditionalSourceReference,
) -> Mapping[str, object]:
    data = _strict_mapping(
        value,
        record_name="compiler fidelity case",
        required={
            "case_name",
            "assignment_mode",
            "assignments",
            "compiled",
            "native",
            "differences",
        },
    )
    case_name = _non_empty_string(data["case_name"], "fidelity case_name")
    compiled = TPMConditionalEvaluation.from_dict(data["compiled"])
    native = TPMNativeConditionalEvaluation.from_dict(data["native"])
    if compiled.pair_id != pair_id or native.pair_id != pair_id:
        raise ValueError("compiler fidelity case pair identity is mismatched")
    if native.artifact_id != source.artifact_id:
        raise ValueError("compiler fidelity source artifact identity is mismatched")
    if compiled.assignment_mode != "declared-domain":
        raise ValueError("compiler fidelity requires declared-domain assignments")
    if data["assignment_mode"] != compiled.assignment_mode:
        raise ValueError("compiler fidelity assignment_mode is mismatched")
    assignments = _frozen_mapping(
        data["assignments"], field_name="compiler fidelity assignments"
    )
    if assignments != compiled.assignments or assignments != native.assignments:
        raise ValueError("compiler fidelity assignments are mismatched")
    fields = {
        "numerator_log",
        "denominator_log",
        "conditional_log_risk",
        "conditional_probability",
    }
    differences = _numeric_metric_mapping(
        data["differences"],
        field_name="compiler fidelity differences",
        required=fields,
    )
    for name in fields:
        expected = float(getattr(compiled, name)) - float(getattr(native, name))
        _require_numeric_identity(
            differences[name],
            expected,
            field_name=f"compiler fidelity difference {name}",
        )
    return _frozen_mapping(
        {
            "case_name": case_name,
            "assignment_mode": compiled.assignment_mode,
            "assignments": _thaw_json(assignments),
            "compiled": compiled.to_dict(),
            "native": native.to_dict(),
            "differences": differences,
        },
        field_name=f"compiler fidelity case {case_name}",
    )


def _require_numeric_identity(
    actual: float,
    expected: float,
    *,
    field_name: str,
) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(
            f"{field_name} is inconsistent: expected {expected!r}, found {actual!r}"
        )


def _strict_mapping(
    payload: Mapping[str, object],
    *,
    record_name: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{record_name} must be a mapping")
    keys = {str(key) for key in payload}
    allowed = required | (optional or set())
    missing = sorted(required - keys)
    unknown = sorted(keys - allowed)
    if missing:
        raise ValueError(f"{record_name} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{record_name} contains unknown fields: {', '.join(unknown)}")
    return {str(key): value for key, value in payload.items()}


def _freeze_json(value: object, *, field_name: str) -> object:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Real):
        if not math.isfinite(float(value)):
            raise ValueError(f"{field_name} must contain only finite numbers")
        return int(value) if isinstance(value, int) else float(value)
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{field_name} mapping keys must be nonempty strings")
            frozen[key] = _freeze_json(item, field_name=f"{field_name}.{key}")
        return MappingProxyType(frozen)
    if _is_sequence(value):
        return tuple(
            _freeze_json(item, field_name=f"{field_name}[{index}]")
            for index, item in enumerate(value)
        )
    raise TypeError(f"{field_name} contains a non-JSON value {type(value).__name__}")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _finite_sequence(value: object, *, field_name: str) -> tuple[float, ...]:
    if not _is_sequence(value):
        raise TypeError(f"{field_name} must be a sequence")
    return tuple(
        _finite_float(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


def _positive_finite_mapping_value(
    payload: Mapping[str, object],
    name: str,
    *,
    field_name: str,
) -> float:
    if name not in payload:
        raise ValueError(f"{field_name} is required")
    value = _finite_float(payload[name], field_name=field_name)
    if value <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _non_empty_string(value: object, field_name: str) -> str:
    normalized = str(value)
    if not normalized:
        raise ValueError(f"{field_name} must be nonempty")
    return normalized


def _sha256_digest(value: object, *, field_name: str) -> str:
    normalized = str(value).lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{field_name} must be a 64-character SHA-256 digest")
    return normalized


__all__ = [
    "CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND",
    "CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND",
    "CONDITIONAL_EVIDENCE_EVALUATOR_VERSION",
    "CONDITIONAL_EVIDENCE_SCHEMA_VERSION",
    "CONDITIONAL_PAIR_COMPILER_VERSION",
    "CONDITIONAL_PAIR_RECORD_KIND",
    "CONDITIONAL_PAIR_SCHEMA_VERSION",
    "TPMConditionalCircuit",
    "TPMConditionalCircuitNode",
    "TPMConditionalCompilationRequest",
    "TPMConditionalAttachment",
    "TPMConditionalAttachmentDiagnostics",
    "TPMBinaryDecisionLink",
    "TPMBinaryDecisionMapping",
    "TPMCategoricalDecisionLink",
    "TPMCategoricalDecisionMapping",
    "TPMConditionalDecisionLink",
    "TPMConditionalEncodingPolicy",
    "TPMConditionalEvaluation",
    "TPMConditionalEvent",
    "TPMConditionalFeatureValidity",
    "TPMConditionalNumericalPolicy",
    "TPMNativeConditionalEvaluation",
    "TPMConditionalPair",
    "TPMConditionalPublication",
    "TPMConditionalSourceReference",
    "TPMCompilerFidelityEvidence",
    "TPMContinuousDecisionMapping",
    "TPMEmbeddingParityEvidence",
    "canonical_conditional_json_bytes",
    "load_conditional_evidence",
    "load_conditional_pair",
    "publish_conditional_evidence",
    "publish_conditional_pair",
]
