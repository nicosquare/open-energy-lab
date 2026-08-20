"""Typed TPM feature metadata and schema helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real
from typing import Any


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

        object.__setattr__(self, "bounds", bounds)
        object.__setattr__(self, "discrete_values", discrete_values)
        object.__setattr__(self, "ordering", ordering)
        object.__setattr__(self, "legacy_reference", legacy_reference)

        normalization_rule = str(self.normalization_rule or _default_normalization_rule(self.feature_type))
        object.__setattr__(self, "normalization_rule", normalization_rule)

        _validate_feature_shape(
            feature_name=feature_name,
            feature_type=self.feature_type,
            bounds=bounds,
            discrete_values=discrete_values,
            ordering=ordering,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the spec into a JSON-compatible mapping."""

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
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TPMFeatureSpec:
        """Load one TPM feature spec from a persisted mapping."""

        if not isinstance(payload, Mapping):
            raise TypeError("TPM feature payload must be a mapping")
        return cls(
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

    def validate_value(self, value: object) -> None:
        """Validate that one feature assignment conforms to this schema."""

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

        if self.feature_type == "continuous":
            return _normalize_numeric_value(float(value), bounds=self.bounds)

        if self.feature_type in {"binary", "categorical"}:
            return float(self.ordering.index(value))

        if value in self.discrete_values:
            return -float(self.ordering.index(value) + 1)
        return _normalize_numeric_value(float(value), bounds=self.bounds)


class TPMFeatureValidationError(ValueError):
    """Structured pre-backend validation failure for one typed feature."""

    def __init__(
        self,
        *,
        feature_name: str,
        expected_domain: Sequence[object],
        reason: str,
        supplied_value: object = _MISSING_SUPPLIED_VALUE,
    ) -> None:
        if reason not in SUPPORTED_SPFLOW_VALIDATION_REASONS:
            raise ValueError(
                f"unsupported feature validation reason {reason!r}; expected one of "
                f"{SUPPORTED_SPFLOW_VALIDATION_REASONS!r}"
            )
        self.feature_name = str(feature_name)
        self.expected_domain = tuple(expected_domain)
        self.reason = reason
        self._has_supplied_value = supplied_value is not _MISSING_SUPPLIED_VALUE
        if self._has_supplied_value:
            self.supplied_value = supplied_value
        message = (
            f"invalid TPM feature {self.feature_name!r}: reason={reason}; "
            f"expected_domain={self.expected_domain!r}"
        )
        if self._has_supplied_value:
            message += f"; supplied_value={supplied_value!r}"
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "feature_name": self.feature_name,
            "expected_domain": list(self.expected_domain),
            "reason": self.reason,
        }
        if self._has_supplied_value:
            payload["supplied_value"] = self.supplied_value
        return payload


def load_feature_schema(items: Sequence[Mapping[str, Any]]) -> tuple[TPMFeatureSpec, ...]:
    """Load a persisted feature schema into validated TPM feature specs."""

    if isinstance(items, Mapping) or isinstance(items, (str, bytes)):
        raise TypeError("feature schema must be a sequence of mappings")

    schema = tuple(TPMFeatureSpec.from_dict(item) for item in items)
    names = tuple(spec.feature_name for spec in schema)
    if len(set(names)) != len(names):
        raise ValueError("feature schema feature_name values must be unique")
    return schema


def dump_feature_schema(schema: Sequence[TPMFeatureSpec]) -> tuple[dict[str, object], ...]:
    """Serialize feature specs into persisted mappings."""

    return tuple(spec.to_dict() for spec in schema)


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

    # Maximum-likelihood leaf fits are undefined at zero variance or infinite
    # discrete logits. Keep persisted values unchanged while supplying a
    # deterministic backend-only regularization observation.
    for column_index, spec in enumerate(schema):
        if len(matrix) < 2:
            continue
        values = [row[column_index] for row in matrix]
        if min(values) != max(values):
            continue
        if spec.feature_type == "continuous":
            for row_index, row in enumerate(matrix):
                row[column_index] = values[0] + (row_index % 2) * 1e-6
        elif spec.feature_type in {"binary", "categorical"} and len(spec.ordering) >= 2:
            current_index = int(values[0])
            matrix[-1][column_index] = float(
                1 if current_index == 0 else 0
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


def _coerce_bounds(
    bounds: tuple[float, float] | None,
    *,
    feature_name: str,
) -> tuple[float, float] | None:
    if bounds is None:
        return None
    if len(bounds) != 2:
        raise ValueError(f"{feature_name} bounds must contain exactly two values")
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
            raise ValueError(f"{feature_name} binary features must define exactly two discrete_values")
        if len(ordering) != 2:
            raise ValueError(f"{feature_name} binary features must define exactly two ordered values")
        return

    if feature_type == "categorical":
        if bounds is not None:
            raise ValueError(f"{feature_name} categorical features cannot define bounds")
        if len(discrete_values) < 2:
            raise ValueError(
                f"{feature_name} categorical features must define at least two discrete_values"
            )
        if len(ordering) != len(discrete_values):
            raise ValueError(f"{feature_name} categorical ordering must cover every discrete value")
        return

    if not discrete_values:
        raise ValueError(f"{feature_name} mixed features must define discrete_values")
    if len(ordering) != len(discrete_values):
        raise ValueError(f"{feature_name} mixed ordering must cover every discrete value")


def _require_numeric_value(value: object, *, feature_name: str) -> None:
    if not _is_non_boolean_real(value):
        raise ValueError(f"{feature_name} requires a numeric value, found {value!r}")


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
