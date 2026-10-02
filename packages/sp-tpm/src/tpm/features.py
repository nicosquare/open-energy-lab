"""Typed TPM feature metadata and schema helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from numbers import Real
from typing import Any

from .domains import TPMFeatureDomain, TPMNormalizationSpec, TPMTrainingSupport


SUPPORTED_TPM_FEATURE_TYPES = (
    "continuous",
    "binary",
    "categorical",
    "mixed",
)
SUPPORTED_TPM_MONOTONICITY = (
    "decreasing",
    "none",
    "increasing",
)
SUPPORTED_SPFLOW_VALIDATION_REASONS = (
    "missing",
    "out_of_bounds",
    "unseen_category",
    "invalid_binary",
    "non_finite",
    "decision_domain_violation",
    "distribution_support_violation",
    "declared_discrete_violation",
    "legacy_operational_restriction",
    "unknown_domain",
)
_MISSING_SUPPLIED_VALUE = object()


def _is_non_boolean_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class TPMFeatureSpec:
    """Persisted typed-feature metadata used by TPM workflows."""

    feature_name: str
    feature_type: str
    feature_role: str = "input"
    modifiable: bool = False
    monotonicity: str = "none"
    bounds: tuple[float, float] | None = None
    discrete_values: tuple[object, ...] = field(default_factory=tuple)
    ordering: tuple[object, ...] = field(default_factory=tuple)
    normalization_rule: str = ""
    legacy_reference: tuple[str, ...] = field(default_factory=tuple)
    mathematical_domain: TPMFeatureDomain | None = None
    training_support: TPMTrainingSupport | None = None
    normalization: TPMNormalizationSpec | None = None

    def __post_init__(self) -> None:
        feature_name = str(self.feature_name)
        if not feature_name:
            raise ValueError("feature_name must be non-empty")
        object.__setattr__(self, "feature_name", feature_name)

        if self.feature_type not in SUPPORTED_TPM_FEATURE_TYPES:
            raise ValueError(
                f"unsupported TPM feature_type {self.feature_type!r}; "
                f"expected one of {SUPPORTED_TPM_FEATURE_TYPES!r}"
            )

        feature_role = str(self.feature_role)
        if not feature_role:
            raise ValueError("feature_role must be non-empty")
        object.__setattr__(self, "feature_role", feature_role)

        monotonicity = str(self.monotonicity)
        if monotonicity not in SUPPORTED_TPM_MONOTONICITY:
            raise ValueError(
                f"unsupported monotonicity {monotonicity!r}; "
                f"expected one of {SUPPORTED_TPM_MONOTONICITY!r}"
            )
        object.__setattr__(self, "monotonicity", monotonicity)

        bounds = _coerce_bounds(self.bounds, feature_name=feature_name)
        discrete_values = tuple(self.discrete_values)
        if len(set(discrete_values)) != len(discrete_values):
            raise ValueError(f"{feature_name} discrete_values must be unique")
        ordering = tuple(self.ordering) if self.ordering else discrete_values
        if ordering and set(ordering) != set(discrete_values):
            raise ValueError(
                f"{feature_name} ordering must contain the same values as discrete_values"
            )
        legacy_reference = tuple(str(entry) for entry in self.legacy_reference)
        if any(not entry for entry in legacy_reference):
            raise ValueError("legacy_reference entries must be non-empty")

        semantic_records = (
            self.mathematical_domain,
            self.training_support,
            self.normalization,
        )
        if any(record is not None for record in semantic_records):
            if any(record is None for record in semantic_records):
                raise ValueError(
                    f"{feature_name} resolved semantics require mathematical_domain, "
                    "training_support, and normalization together"
                )
            (
                resolved_bounds,
                resolved_values,
                resolved_ordering,
                resolved_rule,
            ) = _validate_resolved_semantics(
                feature_name=feature_name,
                feature_type=self.feature_type,
                feature_role=feature_role,
                mathematical_domain=self.mathematical_domain,
                training_support=self.training_support,
                normalization=self.normalization,
            )
            _validate_compatibility_projection(
                feature_name=feature_name,
                supplied_bounds=bounds,
                supplied_values=discrete_values,
                supplied_ordering=ordering,
                supplied_rule=str(self.normalization_rule),
                resolved_bounds=resolved_bounds,
                resolved_values=resolved_values,
                resolved_ordering=resolved_ordering,
                resolved_rule=resolved_rule,
            )
            bounds = resolved_bounds
            discrete_values = resolved_values
            ordering = resolved_ordering
            normalization_rule = resolved_rule
        else:
            normalization_rule = str(
                self.normalization_rule
                or _default_normalization_rule(self.feature_type)
            )

        object.__setattr__(self, "bounds", bounds)
        object.__setattr__(self, "discrete_values", discrete_values)
        object.__setattr__(self, "ordering", ordering)
        object.__setattr__(self, "legacy_reference", legacy_reference)
        object.__setattr__(self, "normalization_rule", normalization_rule)

        _validate_feature_shape(
            feature_name=feature_name,
            feature_type=self.feature_type,
            bounds=bounds,
            discrete_values=discrete_values,
            ordering=ordering,
        )

    def to_dict(self, *, schema_version: str = "v2") -> dict[str, object]:
        """Serialize the spec into a JSON-compatible mapping."""

        if schema_version not in {"v2", "v3"}:
            raise ValueError(f"unsupported TPM feature schema version {schema_version!r}")

        payload: dict[str, object] = {
            "feature_name": self.feature_name,
            "feature_role": self.feature_role,
            "feature_type": self.feature_type,
            "modifiable": self.modifiable,
            "monotonicity": self.monotonicity,
            "normalization_rule": self.normalization_rule,
        }
        if self.bounds is not None:
            payload["bounds"] = [self.bounds[0], self.bounds[1]]
        if self.discrete_values:
            payload["discrete_values"] = list(self.discrete_values)
        if self.ordering:
            payload["ordering"] = list(self.ordering)
        if self.legacy_reference:
            payload["legacy_reference"] = list(self.legacy_reference)
        if schema_version == "v3":
            if self.feature_type == "mixed" and any(
                record is None
                for record in (
                    self.mathematical_domain,
                    self.training_support,
                    self.normalization,
                )
            ):
                payload["legacy_mixed_semantics"] = "legacy-inferred"
            elif any(
                record is None
                for record in (
                    self.mathematical_domain,
                    self.training_support,
                    self.normalization,
                )
            ):
                raise ValueError(
                    f"{self.feature_name} cannot serialize as v3 without resolved semantics"
                )
            else:
                payload["mathematical_domain"] = self.mathematical_domain.to_dict()
                payload["training_support"] = self.training_support.to_dict()
                payload["normalization"] = self.normalization.to_dict()
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        schema_version: str = "v2",
    ) -> TPMFeatureSpec:
        """Load one TPM feature spec from a persisted mapping."""

        if not isinstance(payload, Mapping):
            raise TypeError("TPM feature payload must be a mapping")
        if schema_version not in {"v2", "v3"}:
            raise ValueError(f"unsupported TPM feature schema version {schema_version!r}")

        common_arguments = dict(
            feature_name=str(payload.get("feature_name", "")),
            feature_role=str(payload.get("feature_role", "input")),
            feature_type=str(payload.get("feature_type", "")),
            modifiable=bool(payload.get("modifiable", False)),
            monotonicity=str(payload.get("monotonicity", "none")),
            bounds=_bounds_from_payload(payload.get("bounds")),
            discrete_values=_sequence_payload(payload.get("discrete_values")),
            ordering=_sequence_payload(payload.get("ordering")),
            normalization_rule=str(payload.get("normalization_rule", "")),
            legacy_reference=tuple(
                str(entry) for entry in _sequence_payload(payload.get("legacy_reference"))
            ),
        )
        if schema_version == "v3":
            feature_type = common_arguments["feature_type"]
            if (
                feature_type == "mixed"
                and payload.get("legacy_mixed_semantics") == "legacy-inferred"
            ):
                return cls(**common_arguments)
            missing = [
                name
                for name in (
                    "mathematical_domain",
                    "training_support",
                    "normalization",
                )
                if name not in payload
            ]
            if missing:
                raise ValueError(
                    "schema-v3 feature metadata is missing required semantic records: "
                    + ", ".join(missing)
                )
            return cls(
                **common_arguments,
                mathematical_domain=TPMFeatureDomain.from_dict(
                    payload["mathematical_domain"]
                ),
                training_support=TPMTrainingSupport.from_dict(
                    payload["training_support"]
                ),
                normalization=TPMNormalizationSpec.from_dict(
                    payload["normalization"]
                ),
            )

        feature = cls(**common_arguments)
        legacy_records = _legacy_semantic_records(feature)
        if legacy_records is None:
            return feature
        return cls(
            **common_arguments,
            mathematical_domain=legacy_records[0],
            training_support=legacy_records[1],
            normalization=legacy_records[2],
        )

    def validate_value(self, value: object) -> None:
        """Validate that one feature assignment conforms to this schema."""

        if self.mathematical_domain is not None:
            if self.mathematical_domain.origin == "omitted":
                if self.training_support is None:
                    raise ValueError(
                        f"{self.feature_name} has no legacy-inferred operational support"
                    )
                self.training_support.validate_legacy_value(value)
            else:
                self.mathematical_domain.validate_value(value)
            return

        if self.feature_type == "continuous":
            _require_numeric_value(value, feature_name=self.feature_name)
            _validate_bounds(value, bounds=self.bounds, feature_name=self.feature_name)
            return

        if self.feature_type in {"binary", "categorical"}:
            if value not in self.discrete_values:
                raise ValueError(
                    f"{self.feature_name} categorical value {value!r} is not one of "
                    f"{self.discrete_values!r}"
                )
            return

        if value in self.discrete_values:
            return
        _require_numeric_value(value, feature_name=self.feature_name)
        _validate_bounds(value, bounds=self.bounds, feature_name=self.feature_name)

    def normalize_value(self, value: object) -> float:
        """Normalize one feature assignment into a scalar training representation."""

        self.validate_value(value)

        if self.normalization is not None:
            return self.normalization.normalize_value(value)

        if self.feature_type == "continuous":
            return _normalize_numeric_value(float(value), bounds=self.bounds)

        if self.feature_type in {"binary", "categorical"}:
            return float(self.ordering.index(value))

        if value in self.discrete_values:
            return -float(self.ordering.index(value) + 1)
        return _normalize_numeric_value(float(value), bounds=self.bounds)

    def denormalize_value(self, coordinate: object) -> object:
        """Recover one physical value from a persisted model coordinate."""

        if self.normalization is None:
            raise ValueError(
                f"{self.feature_name} does not have auditable normalization metadata"
            )
        physical_value = self.normalization.denormalize_value(coordinate)
        self.validate_value(physical_value)
        return physical_value


class TPMFeatureValidationError(ValueError):
    """Structured pre-backend validation failure for one typed feature."""

    def __init__(
        self,
        *,
        feature_name: str,
        expected_domain: Sequence[object],
        reason: str,
        supplied_value: object = _MISSING_SUPPLIED_VALUE,
        semantic_source: str = "",
    ) -> None:
        if reason not in SUPPORTED_SPFLOW_VALIDATION_REASONS:
            raise ValueError(
                f"unsupported feature validation reason {reason!r}; expected one of "
                f"{SUPPORTED_SPFLOW_VALIDATION_REASONS!r}"
            )
        self.feature_name = str(feature_name)
        self.expected_domain = tuple(expected_domain)
        self.reason = reason
        self.semantic_source = str(semantic_source)
        self._has_supplied_value = supplied_value is not _MISSING_SUPPLIED_VALUE
        if self._has_supplied_value:
            self.supplied_value = supplied_value
        message = (
            f"invalid TPM feature {self.feature_name!r}: reason={reason}; "
            f"expected_domain={self.expected_domain!r}"
        )
        if self._has_supplied_value:
            message += f"; supplied_value={supplied_value!r}"
        if self.semantic_source:
            message += f"; semantic_source={self.semantic_source}"
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "feature_name": self.feature_name,
            "expected_domain": list(self.expected_domain),
            "reason": self.reason,
        }
        if self._has_supplied_value:
            payload["supplied_value"] = self.supplied_value
        if self.semantic_source:
            payload["semantic_source"] = self.semantic_source
        return payload


def load_feature_schema(
    items: Sequence[Mapping[str, Any]],
    *,
    schema_version: str = "v2",
) -> tuple[TPMFeatureSpec, ...]:
    """Load a persisted feature schema into validated TPM feature specs."""

    if isinstance(items, Mapping) or isinstance(items, (str, bytes)):
        raise TypeError("feature schema must be a sequence of mappings")

    schema = tuple(
        TPMFeatureSpec.from_dict(item, schema_version=schema_version)
        for item in items
    )
    names = tuple(spec.feature_name for spec in schema)
    if len(set(names)) != len(names):
        raise ValueError("feature schema feature_name values must be unique")
    return schema


def dump_feature_schema(
    schema: Sequence[TPMFeatureSpec],
    *,
    schema_version: str = "v2",
) -> tuple[dict[str, object], ...]:
    """Serialize feature specs into persisted mappings."""

    return tuple(spec.to_dict(schema_version=schema_version) for spec in schema)


def infer_feature_role(feature_name: str) -> str:
    """Infer the default TPM feature role from one column name.

    The generic TPM layer does not reserve any dataset column names as targets.
    Callers that need metric or event targets must declare them explicitly in
    artifact-building metadata.
    """

    return "input"


def build_spflow_leaf_modules(
    feature_schema: Sequence[TPMFeatureSpec],
) -> tuple[object, ...]:
    """Build disjoint SPFlow 1.1 leaf modules for a typed feature schema.

    Continuous and binary features can share their respective multivariate
    leaf modules. Categorical features share a leaf only when their cardinality
    agrees. The imports stay inside this workflow helper so importing the TPM
    package does not eagerly import SPFlow or Torch.
    """

    schema = _validated_feature_schema(feature_schema)

    from spflow.modules.leaves import Bernoulli, Categorical, Normal
    from spflow.modules.module import Scope

    typed_scopes: list[tuple[int, str, tuple[int, ...], int | None]] = []
    continuous_scope = tuple(
        index for index, spec in enumerate(schema) if spec.feature_type == "continuous"
    )
    if continuous_scope:
        typed_scopes.append((continuous_scope[0], "continuous", continuous_scope, None))

    binary_scope = tuple(
        index for index, spec in enumerate(schema) if spec.feature_type == "binary"
    )
    if binary_scope:
        typed_scopes.append((binary_scope[0], "binary", binary_scope, None))

    categorical_scopes: dict[int, list[int]] = {}
    for index, spec in enumerate(schema):
        if spec.feature_type == "mixed":
            raise ValueError(
                f"{spec.feature_name} uses feature_type 'mixed', which cannot map "
                "to one SPFlow 1.1 leaf; represent its concrete continuous, "
                "binary, or categorical components on separate feature scopes"
            )
        if spec.feature_type == "categorical":
            categorical_scopes.setdefault(len(spec.ordering), []).append(index)

    for cardinality, indices in categorical_scopes.items():
        scope = tuple(indices)
        typed_scopes.append((scope[0], "categorical", scope, cardinality))

    leaves: list[object] = []
    for _, feature_type, indices, cardinality in sorted(typed_scopes):
        scope = Scope(query=indices)
        if feature_type == "continuous":
            leaves.append(Normal(scope=scope))
        elif feature_type == "binary":
            leaves.append(Bernoulli(scope=scope))
        else:
            categorical_class = _spflow_categorical_template_class(
                categorical_base=Categorical,
                cardinality=cardinality,
            )
            leaves.append(categorical_class(scope=scope))
    return tuple(leaves)


def build_spflow_training_tensor(
    rows: Sequence[Mapping[str, object]],
    *,
    feature_schema: Sequence[TPMFeatureSpec],
) -> object:
    """Encode typed rows as a CPU ``torch.float64`` training tensor."""

    if isinstance(rows, Mapping) or isinstance(rows, (str, bytes)):
        raise TypeError("rows must be a sequence of row mappings")
    if not rows:
        raise ValueError("rows must not be empty")
    schema = _validated_feature_schema(feature_schema)

    matrix: list[list[float]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError(f"rows[{row_index}] must be a mapping")
        missing = [spec.feature_name for spec in schema if spec.feature_name not in row]
        if missing:
            raise ValueError(
                f"rows[{row_index}] is missing feature values: {', '.join(missing)}"
            )
        matrix.append(
            [spec.normalize_value(row[spec.feature_name]) for spec in schema]
        )

    import torch

    return torch.tensor(matrix, dtype=torch.float64, device="cpu")


def validate_spflow_feature_assignments(
    feature_schema: Sequence[TPMFeatureSpec],
    assignments: Mapping[str, object],
    *,
    required_decision_features: Sequence[str] = (),
) -> None:
    """Validate typed assignments before a required SPFlow workflow starts."""

    if not isinstance(assignments, Mapping):
        raise TypeError("feature assignments must be a mapping")
    schema = _validated_feature_schema(feature_schema)
    feature_by_name = {spec.feature_name: spec for spec in schema}

    for feature_name in required_decision_features:
        normalized_name = str(feature_name)
        spec = feature_by_name.get(normalized_name)
        if spec is None:
            raise ValueError(
                f"required decision feature {normalized_name!r} is not in feature_schema"
            )
        if normalized_name not in assignments:
            raise TPMFeatureValidationError(
                feature_name=normalized_name,
                expected_domain=_feature_expected_domain(spec),
                reason="missing",
            )

    for feature_name, value in assignments.items():
        normalized_name = str(feature_name)
        spec = feature_by_name.get(normalized_name)
        if spec is None:
            raise ValueError(f"unknown TPM feature assignment {normalized_name!r}")
        expected_domain = _feature_expected_domain(spec)
        if spec.mathematical_domain is not None:
            _validate_semantic_assignment(
                spec,
                value,
                expected_domain=expected_domain,
            )
            continue
        if spec.feature_type == "continuous":
            if not _is_non_boolean_real(value) or not _value_within_bounds(
                value,
                spec.bounds,
            ):
                raise TPMFeatureValidationError(
                    feature_name=normalized_name,
                    expected_domain=expected_domain,
                    reason="out_of_bounds",
                    supplied_value=value,
                )
        elif spec.feature_type == "binary":
            if value not in spec.discrete_values:
                raise TPMFeatureValidationError(
                    feature_name=normalized_name,
                    expected_domain=expected_domain,
                    reason="invalid_binary",
                    supplied_value=value,
                )
        elif spec.feature_type == "categorical":
            if value not in spec.discrete_values:
                raise TPMFeatureValidationError(
                    feature_name=normalized_name,
                    expected_domain=expected_domain,
                    reason="unseen_category",
                    supplied_value=value,
                )
        elif value not in spec.discrete_values and (
            not _is_non_boolean_real(value)
            or not _value_within_bounds(value, spec.bounds)
        ):
            raise TPMFeatureValidationError(
                feature_name=normalized_name,
                expected_domain=expected_domain,
                reason="out_of_bounds",
                supplied_value=value,
            )


def _validate_semantic_assignment(
    spec: TPMFeatureSpec,
    value: object,
    *,
    expected_domain: tuple[object, ...],
) -> None:
    domain = spec.mathematical_domain
    if spec.feature_type == "continuous" and (
        not _is_non_boolean_real(value) or not math.isfinite(float(value))
    ):
        raise TPMFeatureValidationError(
            feature_name=spec.feature_name,
            expected_domain=expected_domain,
            reason="non_finite",
            supplied_value=value,
            semantic_source=(
                "legacy-inferred"
                if domain.origin == "omitted"
                else domain.purpose
            ),
        )
    try:
        spec.validate_value(value)
    except (TypeError, ValueError) as exc:
        if domain.origin == "omitted":
            reason = {
                "continuous": "out_of_bounds",
                "binary": "invalid_binary",
                "categorical": "unseen_category",
            }.get(spec.feature_type, "legacy_operational_restriction")
            semantic_source = "legacy-inferred"
        elif spec.feature_type in {"binary", "categorical"}:
            reason = "declared_discrete_violation"
            semantic_source = domain.purpose
        elif domain.purpose == "decision-domain":
            reason = "decision_domain_violation"
            semantic_source = "decision-domain"
        else:
            reason = "distribution_support_violation"
            semantic_source = "distribution-support"
        error = TPMFeatureValidationError(
            feature_name=spec.feature_name,
            expected_domain=expected_domain,
            reason=reason,
            supplied_value=value,
            semantic_source=semantic_source,
        )
        raise error from exc


__all__ = [
    "SUPPORTED_TPM_FEATURE_TYPES",
    "SUPPORTED_TPM_MONOTONICITY",
    "SUPPORTED_SPFLOW_VALIDATION_REASONS",
    "TPMFeatureSpec",
    "TPMFeatureValidationError",
    "build_spflow_leaf_modules",
    "build_spflow_training_tensor",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
    "validate_spflow_feature_assignments",
]


def _validated_feature_schema(
    feature_schema: Sequence[TPMFeatureSpec],
) -> tuple[TPMFeatureSpec, ...]:
    if isinstance(feature_schema, (str, bytes)):
        raise TypeError("feature_schema must be a sequence of TPMFeatureSpec values")
    schema = tuple(feature_schema)
    if not schema:
        raise ValueError("feature_schema must not be empty")
    if any(not isinstance(spec, TPMFeatureSpec) for spec in schema):
        raise TypeError("feature_schema must contain only TPMFeatureSpec values")
    feature_names = tuple(spec.feature_name for spec in schema)
    if len(set(feature_names)) != len(feature_names):
        raise ValueError("feature_schema feature_name values must be unique")
    return schema


def _feature_expected_domain(spec: TPMFeatureSpec) -> tuple[object, ...]:
    if spec.mathematical_domain is not None:
        domain = spec.mathematical_domain
        if domain.origin == "omitted" and spec.training_support is not None:
            if spec.feature_type == "continuous":
                return (spec.training_support.minimum, spec.training_support.maximum)
            return tuple(spec.training_support.observed_values)
        if spec.feature_type == "continuous":
            if domain.shape == "finite":
                return (domain.lower, domain.upper)
            if domain.shape == "lower-bounded":
                return (domain.lower, "+unbounded")
            if domain.shape == "upper-bounded":
                return ("-unbounded", domain.upper)
            if domain.shape == "unbounded":
                return ("all-finite-values",)
            return ("finite-value; mathematical extent unknown",)
        return tuple(domain.ordering)
    if spec.feature_type == "continuous":
        return tuple(spec.bounds or ("numeric",))
    if spec.feature_type in {"binary", "categorical"}:
        return tuple(spec.ordering)
    domain: list[object] = list(spec.ordering)
    if spec.bounds is not None:
        domain.extend(spec.bounds)
    return tuple(domain)


def _value_within_bounds(
    value: object,
    bounds: tuple[float, float] | None,
) -> bool:
    if bounds is None:
        return True
    numeric_value = float(value)
    return bounds[0] <= numeric_value <= bounds[1]


def _spflow_categorical_template_class(
    *,
    categorical_base: type,
    cardinality: int | None,
) -> type:
    """Return a lazy categorical template that retains ``K`` during learning.

    SPFlow 1.1's ``learn_spn`` recreates leaf templates from their class using
    only ``scope`` and ``out_channels``. Its base ``Categorical`` class also
    requires ``K``, so a cardinality-specific subclass supplies that omitted
    constructor default. Registering the generated class in this module keeps
    it pickle-addressable for the later model-sidecar workflow.
    """

    if cardinality is None or cardinality < 2:
        raise ValueError("categorical leaf cardinality must be at least two")
    class_name = f"_SPFlowCategoricalK{cardinality}"
    existing = globals().get(class_name)
    if isinstance(existing, type) and issubclass(existing, categorical_base):
        return existing

    def __init__(
        self: object,
        scope: object,
        out_channels: int = 1,
        num_repetitions: int = 1,
        K: int | None = None,
        probs: object = None,
        logits: object = None,
        parameter_fn: object = None,
        validate_args: bool | None = True,
    ) -> None:
        resolved_cardinality = cardinality if K is None else int(K)
        if resolved_cardinality != cardinality:
            raise ValueError(
                f"{class_name} requires K={cardinality}, found K={resolved_cardinality}"
            )
        categorical_base.__init__(
            self,
            scope=scope,
            out_channels=out_channels,
            num_repetitions=num_repetitions,
            K=resolved_cardinality,
            probs=probs,
            logits=logits,
            parameter_fn=parameter_fn,
            validate_args=validate_args,
        )

    categorical_class = type(
        class_name,
        (categorical_base,),
        {
            "__doc__": f"SPFlow categorical leaf template with fixed K={cardinality}.",
            "__init__": __init__,
            "__module__": __name__,
            "__qualname__": class_name,
        },
    )
    globals()[class_name] = categorical_class
    return categorical_class


def __getattr__(name: str) -> object:
    """Recreate persisted lazy categorical templates without eager imports."""

    prefix = "_SPFlowCategoricalK"
    if name.startswith(prefix) and name.removeprefix(prefix).isdigit():
        from spflow.modules.leaves import Categorical

        return _spflow_categorical_template_class(
            categorical_base=Categorical,
            cardinality=int(name.removeprefix(prefix)),
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _default_normalization_rule(feature_type: str) -> str:
    return {
        "continuous": "minmax",
        "binary": "binary_index",
        "categorical": "categorical_index",
        "mixed": "mixed_index_minmax",
    }[feature_type]


def _validate_resolved_semantics(
    *,
    feature_name: str,
    feature_type: str,
    feature_role: str,
    mathematical_domain: TPMFeatureDomain,
    training_support: TPMTrainingSupport,
    normalization: TPMNormalizationSpec,
) -> tuple[
    tuple[float, float] | None,
    tuple[object, ...],
    tuple[object, ...],
    str,
]:
    records = (mathematical_domain, training_support, normalization)
    expected_types = (TPMFeatureDomain, TPMTrainingSupport, TPMNormalizationSpec)
    if any(not isinstance(record, expected) for record, expected in zip(records, expected_types)):
        raise TypeError(
            f"{feature_name} semantic records use unsupported record types"
        )
    for record in records:
        if record.feature_name != feature_name:
            raise ValueError(
                f"{feature_name} semantic record is owned by feature_name "
                f"{record.feature_name!r}"
            )
        if record.feature_kind != feature_type:
            raise ValueError(
                f"{feature_name} semantic feature_kind {record.feature_kind!r} "
                f"does not match feature_type {feature_type!r}"
            )

    expected_purpose = (
        "decision-domain" if feature_role == "decision" else "distribution-support"
    )
    if mathematical_domain.purpose != expected_purpose:
        raise ValueError(
            f"{feature_name} domain purpose {mathematical_domain.purpose!r} is "
            f"incompatible with feature role {feature_role!r}"
        )

    if mathematical_domain.origin != "omitted":
        if feature_type == "continuous":
            mathematical_domain.validate_value(training_support.minimum)
            mathematical_domain.validate_value(training_support.maximum)
        else:
            for observed_value in training_support.observed_values:
                mathematical_domain.validate_value(observed_value)

    expected_normalization_origin = {
        "caller-declared": "caller-declared",
        "omitted": "legacy-inferred",
        "internal-exact-target": "internal-exact-target",
    }[mathematical_domain.origin]
    if normalization.origin != expected_normalization_origin:
        raise ValueError(
            f"{feature_name} normalization origin {normalization.origin!r} "
            f"contradicts mathematical domain origin {mathematical_domain.origin!r}"
        )

    if feature_type == "continuous":
        if mathematical_domain.origin == "omitted":
            expected_kind = (
                "fixed-zero"
                if training_support.minimum == training_support.maximum
                else "min-max"
            )
            expected_endpoints = (
                training_support.minimum,
                training_support.maximum,
            )
        elif mathematical_domain.shape == "finite":
            expected_kind = (
                "fixed-zero"
                if mathematical_domain.lower == mathematical_domain.upper
                else "min-max"
            )
            expected_endpoints = (
                mathematical_domain.lower,
                mathematical_domain.upper,
            )
        else:
            expected_kind = "identity"
            expected_endpoints = (None, None)
        if normalization.kind != expected_kind or (
            normalization.lower,
            normalization.upper,
        ) != expected_endpoints:
            raise ValueError(
                f"{feature_name} normalization contradicts its mathematical domain "
                "and training-support semantics"
            )
        bounds = (
            expected_endpoints
            if normalization.kind in {"min-max", "fixed-zero"}
            else None
        )
        return bounds, (), (), (
            "identity" if normalization.kind == "identity" else "minmax"
        )

    if mathematical_domain.origin == "omitted":
        expected_ordering = normalization.ordering
        ordering_is_valid = (
            len(expected_ordering) == len(training_support.observed_values)
            and set(expected_ordering) == set(training_support.observed_values)
        )
    else:
        expected_ordering = mathematical_domain.ordering
        ordering_is_valid = normalization.ordering == expected_ordering
    if normalization.kind != "ordered-index" or not ordering_is_valid:
        raise ValueError(
            f"{feature_name} normalization ordering contradicts its mathematical domain"
        )
    rule = "binary_index" if feature_type == "binary" else "categorical_index"
    return None, expected_ordering, expected_ordering, rule


def _validate_compatibility_projection(
    *,
    feature_name: str,
    supplied_bounds: tuple[float, float] | None,
    supplied_values: tuple[object, ...],
    supplied_ordering: tuple[object, ...],
    supplied_rule: str,
    resolved_bounds: tuple[float, float] | None,
    resolved_values: tuple[object, ...],
    resolved_ordering: tuple[object, ...],
    resolved_rule: str,
) -> None:
    comparisons = (
        (supplied_bounds is not None, supplied_bounds, resolved_bounds, "bounds"),
        (bool(supplied_values), supplied_values, resolved_values, "discrete_values"),
        (bool(supplied_ordering), supplied_ordering, resolved_ordering, "ordering"),
        (bool(supplied_rule), supplied_rule, resolved_rule, "normalization_rule"),
    )
    for was_supplied, supplied, resolved, field_name in comparisons:
        if was_supplied and supplied != resolved:
            raise ValueError(
                f"{feature_name} compatibility field {field_name} contradicts "
                "resolved semantic records"
            )


def _legacy_semantic_records(
    feature: TPMFeatureSpec,
) -> tuple[TPMFeatureDomain, TPMTrainingSupport, TPMNormalizationSpec] | None:
    if feature.feature_type == "mixed":
        return None
    purpose = (
        "decision-domain"
        if feature.feature_role == "decision"
        else "distribution-support"
    )
    if feature.feature_type == "continuous":
        if feature.bounds is None:
            return None
        lower, upper = feature.bounds
        return (
            TPMFeatureDomain(
                feature_name=feature.feature_name,
                feature_kind="continuous",
                purpose=purpose,
                shape="unknown",
                origin="omitted",
            ),
            TPMTrainingSupport(
                feature_name=feature.feature_name,
                feature_kind="continuous",
                minimum=lower,
                maximum=upper,
                origin="legacy-artifact-range",
            ),
            TPMNormalizationSpec(
                feature_name=feature.feature_name,
                feature_kind="continuous",
                kind="fixed-zero" if lower == upper else "min-max",
                origin="legacy-inferred",
                lower=lower,
                upper=upper,
            ),
        )

    return (
        TPMFeatureDomain(
            feature_name=feature.feature_name,
            feature_kind=feature.feature_type,
            purpose=purpose,
            shape="unknown",
            origin="omitted",
        ),
        TPMTrainingSupport(
            feature_name=feature.feature_name,
            feature_kind=feature.feature_type,
            observed_values=feature.ordering,
            origin="legacy-artifact-values",
        ),
        TPMNormalizationSpec(
            feature_name=feature.feature_name,
            feature_kind=feature.feature_type,
            kind="ordered-index",
            origin="legacy-inferred",
            ordering=feature.ordering,
        ),
    )


def _coerce_bounds(
    bounds: tuple[float, float] | None,
    *,
    feature_name: str,
) -> tuple[float, float] | None:
    if bounds is None:
        return None
    if len(bounds) != 2:
        raise ValueError(f"{feature_name} bounds must contain exactly two values")
    if any(
        not _is_non_boolean_real(endpoint) or not math.isfinite(float(endpoint))
        for endpoint in bounds
    ):
        raise ValueError(f"{feature_name} bounds must contain finite numeric values")
    lower, upper = float(bounds[0]), float(bounds[1])
    if lower > upper:
        raise ValueError(f"{feature_name} bounds must be ordered as (lower, upper)")
    return (lower, upper)


def _bounds_from_payload(value: object) -> tuple[float, float] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("feature bounds must be a two-item sequence")
    if len(value) != 2:
        raise ValueError("feature bounds must contain exactly two values")
    return (float(value[0]), float(value[1]))


def _sequence_payload(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("feature metadata sequences must be stored as sequences")
    return tuple(value)


def _validate_feature_shape(
    *,
    feature_name: str,
    feature_type: str,
    bounds: tuple[float, float] | None,
    discrete_values: tuple[object, ...],
    ordering: tuple[object, ...],
) -> None:
    if feature_type == "continuous":
        if discrete_values:
            raise ValueError(f"{feature_name} continuous features cannot define discrete_values")
        if ordering:
            raise ValueError(f"{feature_name} continuous features cannot define ordering")
        return

    if feature_type == "binary":
        if bounds is not None:
            raise ValueError(f"{feature_name} binary features cannot define bounds")
        if len(discrete_values) != 2:
            raise ValueError(
                f"{feature_name} binary features must define exactly two discrete_values"
            )
        if len(ordering) != 2:
            raise ValueError(
                f"{feature_name} binary features must define exactly two ordered values"
            )
        return

    if feature_type == "categorical":
        if bounds is not None:
            raise ValueError(f"{feature_name} categorical features cannot define bounds")
        if len(discrete_values) < 1:
            raise ValueError(
                f"{feature_name} categorical features must define at least one discrete value"
            )
        if len(ordering) != len(discrete_values):
            raise ValueError(f"{feature_name} categorical ordering must cover every discrete value")
        return

    if not discrete_values:
        raise ValueError(f"{feature_name} mixed features must define discrete_values")
    if len(ordering) != len(discrete_values):
        raise ValueError(f"{feature_name} mixed ordering must cover every discrete value")


def _require_numeric_value(value: object, *, feature_name: str) -> None:
    if not _is_non_boolean_real(value) or not math.isfinite(float(value)):
        raise ValueError(
            f"{feature_name} requires a finite numeric value, found {value!r}"
        )


def _validate_bounds(
    value: object,
    *,
    bounds: tuple[float, float] | None,
    feature_name: str,
) -> None:
    if bounds is None:
        return
    numeric_value = float(value)
    lower, upper = bounds
    if numeric_value < lower or numeric_value > upper:
        raise ValueError(
            f"{feature_name} value {numeric_value!r} is outside bounds {bounds!r}"
        )


def _normalize_numeric_value(
    value: float,
    *,
    bounds: tuple[float, float] | None,
) -> float:
    if bounds is None:
        return value
    lower, upper = bounds
    if lower == upper:
        return 0.0
    return (value - lower) / (upper - lower)
