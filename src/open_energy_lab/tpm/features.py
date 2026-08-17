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


__all__ = [
    "SUPPORTED_TPM_FEATURE_TYPES",
    "SUPPORTED_TPM_MONOTONICITY",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
]


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
