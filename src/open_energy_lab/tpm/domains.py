"""Import-light semantic records for TPM feature domains and coordinates.

The records in this module deliberately keep three meanings separate:
caller-asserted mathematical domains, observed physical training support, and
the transform used to produce model coordinates.  They contain no fitting or
optimization backend dependencies.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from numbers import Real
from typing import Any, ClassVar


SUPPORTED_TPM_DOMAIN_PURPOSES = (
    "decision-domain",
    "distribution-support",
)
SUPPORTED_TPM_DOMAIN_FEATURE_KINDS = (
    "continuous",
    "binary",
    "categorical",
)
SUPPORTED_TPM_CONTINUOUS_DOMAIN_SHAPES = (
    "finite",
    "lower-bounded",
    "upper-bounded",
    "unbounded",
    "unknown",
)
SUPPORTED_TPM_DOMAIN_ORIGINS = (
    "caller-declared",
    "omitted",
    "internal-exact-target",
)
SUPPORTED_TPM_NORMALIZATION_KINDS = (
    "min-max",
    "fixed-zero",
    "identity",
    "ordered-index",
)
SUPPORTED_TPM_NORMALIZATION_ORIGINS = (
    "caller-declared",
    "legacy-inferred",
    "internal-exact-target",
)


@dataclass(frozen=True, slots=True)
class TPMFeatureDomain:
    """One feature's mathematical decision domain or distribution support."""

    feature_name: str
    feature_kind: str
    purpose: str
    shape: str | None = None
    lower: float | None = None
    upper: float | None = None
    values: tuple[object, ...] = field(default_factory=tuple)
    ordering: tuple[object, ...] = field(default_factory=tuple)
    origin: str = "caller-declared"

    _JSON_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "feature_name",
            "feature_kind",
            "purpose",
            "shape",
            "lower",
            "upper",
            "values",
            "ordering",
            "origin",
        }
    )
    _REQUIRED_JSON_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"feature_name", "feature_kind", "purpose"}
    )

    def __post_init__(self) -> None:
        feature_name = _non_empty_string(self.feature_name, field_name="feature_name")
        feature_kind = _supported_string(
            self.feature_kind,
            field_name="feature_kind",
            supported=SUPPORTED_TPM_DOMAIN_FEATURE_KINDS,
        )
        purpose = _supported_string(
            self.purpose,
            field_name="purpose",
            supported=SUPPORTED_TPM_DOMAIN_PURPOSES,
        )
        origin = _supported_string(
            self.origin,
            field_name="origin",
            supported=SUPPORTED_TPM_DOMAIN_ORIGINS,
        )
        values = _json_scalar_tuple(self.values, field_name="values")
        ordering = _json_scalar_tuple(self.ordering, field_name="ordering")

        object.__setattr__(self, "feature_name", feature_name)
        object.__setattr__(self, "feature_kind", feature_kind)
        object.__setattr__(self, "purpose", purpose)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "ordering", ordering)

        if feature_kind == "continuous":
            self._validate_continuous(values=values, ordering=ordering)
        else:
            self._validate_discrete(
                feature_kind=feature_kind,
                values=values,
                ordering=ordering,
            )

    def _validate_continuous(
        self,
        *,
        values: tuple[object, ...],
        ordering: tuple[object, ...],
    ) -> None:
        shape = _supported_string(
            self.shape,
            field_name="shape",
            supported=SUPPORTED_TPM_CONTINUOUS_DOMAIN_SHAPES,
        )
        lower = _optional_finite_float(self.lower, field_name="lower")
        upper = _optional_finite_float(self.upper, field_name="upper")
        if values or ordering:
            raise ValueError("continuous domain must not contain discrete values or ordering")

        expected_endpoint_presence = {
            "finite": (True, True),
            "lower-bounded": (True, False),
            "upper-bounded": (False, True),
            "unbounded": (False, False),
            "unknown": (False, False),
        }[shape]
        actual_endpoint_presence = (lower is not None, upper is not None)
        if actual_endpoint_presence != expected_endpoint_presence:
            raise ValueError(
                f"continuous domain shape {shape!r} has contradictory endpoint structure"
            )
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("continuous domain lower endpoint must not exceed upper endpoint")
        if self.origin == "omitted" and shape != "unknown":
            raise ValueError("an omitted mathematical domain must have shape 'unknown'")

        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    def _validate_discrete(
        self,
        *,
        feature_kind: str,
        values: tuple[object, ...],
        ordering: tuple[object, ...],
    ) -> None:
        if self.origin == "omitted":
            if self.shape != "unknown" or values or ordering:
                raise ValueError(
                    f"omitted {feature_kind} domain must have shape 'unknown' "
                    "without declared values"
                )
            if self.lower is not None or self.upper is not None:
                raise ValueError(
                    f"omitted {feature_kind} domain must not contain numeric endpoints"
                )
            object.__setattr__(self, "shape", "unknown")
            object.__setattr__(self, "lower", None)
            object.__setattr__(self, "upper", None)
            return

        if self.shape is not None or self.lower is not None or self.upper is not None:
            raise ValueError(
                f"{feature_kind} domain must not contain a continuous shape or endpoints"
            )
        if feature_kind == "binary":
            if len(values) != 2 or len(set(values)) != 2:
                raise ValueError("binary domain requires exactly two distinct values")
            resolved_ordering = ordering or values
            if resolved_ordering != values:
                raise ValueError(
                    "binary ordering must preserve the caller-declared value order"
                )
        else:
            _require_unique(values, field_name="categorical values")
            if not values:
                raise ValueError("categorical domain requires a non-empty complete value set")
            resolved_ordering = ordering or values
            _require_unique(resolved_ordering, field_name="categorical ordering")
            if len(resolved_ordering) != len(values) or set(resolved_ordering) != set(values):
                raise ValueError(
                    "categorical ordering must contain every declared categorical "
                    "value exactly once"
                )

        object.__setattr__(self, "shape", None)
        object.__setattr__(self, "lower", None)
        object.__setattr__(self, "upper", None)
        object.__setattr__(self, "ordering", resolved_ordering)

    def validate_value(self, value: object) -> None:
        """Validate one exact physical value against this mathematical meaning."""

        if self.feature_kind == "continuous":
            numeric_value = _finite_float(
                value,
                field_name=f"{self.feature_name} physical value",
            )
            if self.shape == "finite":
                is_valid = self.lower <= numeric_value <= self.upper
            elif self.shape == "lower-bounded":
                is_valid = numeric_value >= self.lower
            elif self.shape == "upper-bounded":
                is_valid = numeric_value <= self.upper
            else:
                is_valid = True
            if not is_valid:
                raise ValueError(
                    f"{self.feature_name} value {numeric_value!r} is outside its "
                    f"declared {self.purpose} ({self.shape})"
                )
            return

        if self.shape == "unknown":
            return
        if value not in self.values:
            raise ValueError(
                f"{self.feature_name} value {value!r} is outside its declared "
                f"{self.purpose} values {self.ordering!r}"
            )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible semantic payload without numeric infinity."""

        payload: dict[str, object] = {
            "feature_name": self.feature_name,
            "feature_kind": self.feature_kind,
            "purpose": self.purpose,
            "origin": self.origin,
        }
        if self.shape is not None:
            payload["shape"] = self.shape
        if self.lower is not None:
            payload["lower"] = self.lower
        if self.upper is not None:
            payload["upper"] = self.upper
        if self.values:
            payload["values"] = list(self.values)
            payload["ordering"] = list(self.ordering)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TPMFeatureDomain:
        """Load and strictly validate a persisted mathematical domain."""

        data = _validated_payload(
            payload,
            record_name="TPM feature domain",
            allowed=cls._JSON_FIELDS,
            required=cls._REQUIRED_JSON_FIELDS,
        )
        return cls(
            feature_name=data["feature_name"],
            feature_kind=data["feature_kind"],
            purpose=data["purpose"],
            shape=data.get("shape"),
            lower=data.get("lower"),
            upper=data.get("upper"),
            values=_sequence_value(data.get("values"), field_name="values"),
            ordering=_sequence_value(data.get("ordering"), field_name="ordering"),
            origin=data.get("origin", "caller-declared"),
        )


@dataclass(frozen=True, slots=True)
class TPMTrainingSupport:
    """Physical values actually observed in caller-supplied training rows."""

    feature_name: str
    feature_kind: str
    minimum: float | None = None
    maximum: float | None = None
    observed_values: tuple[object, ...] = field(default_factory=tuple)
    origin: str = "physical-training-rows"

    _JSON_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "feature_name",
            "feature_kind",
            "minimum",
            "maximum",
            "observed_values",
            "origin",
        }
    )
    _REQUIRED_JSON_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"feature_name", "feature_kind"}
    )

    def __post_init__(self) -> None:
        feature_name = _non_empty_string(self.feature_name, field_name="feature_name")
        feature_kind = _supported_string(
            self.feature_kind,
            field_name="feature_kind",
            supported=SUPPORTED_TPM_DOMAIN_FEATURE_KINDS,
        )
        origin = _non_empty_string(self.origin, field_name="origin")
        minimum = _optional_finite_float(self.minimum, field_name="minimum")
        maximum = _optional_finite_float(self.maximum, field_name="maximum")
        observed_values = _json_scalar_tuple(
            self.observed_values,
            field_name="observed_values",
        )

        if feature_kind == "continuous":
            if minimum is None or maximum is None or observed_values:
                raise ValueError(
                    "continuous training support requires minimum and maximum only"
                )
            if minimum > maximum:
                raise ValueError(
                    "continuous training support minimum must not exceed maximum"
                )
        else:
            if minimum is not None or maximum is not None:
                raise ValueError(
                    f"{feature_kind} training support must contain observed values only"
                )
            if not observed_values:
                raise ValueError(
                    f"{feature_kind} training support requires observed values"
                )
            _require_unique(observed_values, field_name="observed values")

        object.__setattr__(self, "feature_name", feature_name)
        object.__setattr__(self, "feature_kind", feature_kind)
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "observed_values", observed_values)
        object.__setattr__(self, "origin", origin)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible observed-support payload."""

        payload: dict[str, object] = {
            "feature_name": self.feature_name,
            "feature_kind": self.feature_kind,
            "origin": self.origin,
        }
        if self.feature_kind == "continuous":
            payload["minimum"] = self.minimum
            payload["maximum"] = self.maximum
        else:
            payload["observed_values"] = list(self.observed_values)
        return payload

    def validate_legacy_value(self, value: object) -> None:
        """Apply a visibly legacy-inferred operational support restriction."""

        if self.feature_kind == "continuous":
            numeric_value = _finite_float(
                value,
                field_name=f"{self.feature_name} physical value",
            )
            if not self.minimum <= numeric_value <= self.maximum:
                raise ValueError(
                    f"{self.feature_name} value {numeric_value!r} is outside the "
                    "legacy-inferred observed operational range "
                    f"[{self.minimum!r}, {self.maximum!r}]"
                )
            return
        if value not in self.observed_values:
            raise ValueError(
                f"{self.feature_name} value {value!r} is outside the "
                "legacy-inferred observed values "
                f"{self.observed_values!r}"
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TPMTrainingSupport:
        """Load and strictly validate persisted observed support."""

        data = _validated_payload(
            payload,
            record_name="TPM training support",
            allowed=cls._JSON_FIELDS,
            required=cls._REQUIRED_JSON_FIELDS,
        )
        return cls(
            feature_name=data["feature_name"],
            feature_kind=data["feature_kind"],
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
            observed_values=_sequence_value(
                data.get("observed_values"),
                field_name="observed_values",
            ),
            origin=data.get("origin", "physical-training-rows"),
        )


@dataclass(frozen=True, slots=True)
class TPMNormalizationSpec:
    """Auditable physical-to-model-coordinate transformation metadata."""

    feature_name: str
    feature_kind: str
    kind: str
    origin: str
    lower: float | None = None
    upper: float | None = None
    ordering: tuple[object, ...] = field(default_factory=tuple)

    _JSON_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "feature_name",
            "feature_kind",
            "kind",
            "origin",
            "lower",
            "upper",
            "ordering",
        }
    )
    _REQUIRED_JSON_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"feature_name", "feature_kind", "kind", "origin"}
    )

    def __post_init__(self) -> None:
        feature_name = _non_empty_string(self.feature_name, field_name="feature_name")
        feature_kind = _supported_string(
            self.feature_kind,
            field_name="feature_kind",
            supported=SUPPORTED_TPM_DOMAIN_FEATURE_KINDS,
        )
        kind = _supported_string(
            self.kind,
            field_name="kind",
            supported=SUPPORTED_TPM_NORMALIZATION_KINDS,
        )
        origin = _supported_string(
            self.origin,
            field_name="origin",
            supported=SUPPORTED_TPM_NORMALIZATION_ORIGINS,
        )
        lower = _optional_finite_float(self.lower, field_name="lower")
        upper = _optional_finite_float(self.upper, field_name="upper")
        ordering = _json_scalar_tuple(self.ordering, field_name="ordering")

        if kind == "min-max":
            if feature_kind != "continuous" or lower is None or upper is None:
                raise ValueError(
                    "min-max normalization requires continuous finite lower and upper parameters"
                )
            if lower >= upper:
                raise ValueError(
                    "min-max normalization requires lower to be strictly less than upper"
                )
            if ordering:
                raise ValueError("min-max normalization must not contain ordering")
        elif kind == "fixed-zero":
            if (
                feature_kind != "continuous"
                or lower is None
                or upper is None
                or lower != upper
            ):
                raise ValueError(
                    "fixed-zero normalization requires equal finite continuous endpoints"
                )
            if ordering:
                raise ValueError("fixed-zero normalization must not contain ordering")
        elif kind == "identity":
            if feature_kind != "continuous" or lower is not None or upper is not None or ordering:
                raise ValueError(
                    "identity normalization requires a continuous feature and no parameters"
                )
        else:
            if feature_kind not in {"binary", "categorical"}:
                raise ValueError(
                    "ordered-index normalization requires a binary or categorical feature"
                )
            if lower is not None or upper is not None:
                raise ValueError(
                    "ordered-index normalization must not contain numeric endpoints"
                )
            _require_unique(ordering, field_name="ordered-index ordering")
            minimum_size = 2 if feature_kind == "binary" else 1
            if len(ordering) < minimum_size or (
                feature_kind == "binary" and len(ordering) != 2
            ):
                raise ValueError(
                    "ordered-index normalization requires a complete feature ordering"
                )

        object.__setattr__(self, "feature_name", feature_name)
        object.__setattr__(self, "feature_kind", feature_kind)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)
        object.__setattr__(self, "ordering", ordering)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible normalization payload."""

        payload: dict[str, object] = {
            "feature_name": self.feature_name,
            "feature_kind": self.feature_kind,
            "kind": self.kind,
            "origin": self.origin,
        }
        if self.lower is not None:
            payload["lower"] = self.lower
        if self.upper is not None:
            payload["upper"] = self.upper
        if self.ordering:
            payload["ordering"] = list(self.ordering)
        return payload

    def normalize_value(self, value: object) -> float:
        """Transform one validated physical value to its model coordinate."""

        if self.kind == "ordered-index":
            if value not in self.ordering:
                raise ValueError(
                    f"{self.feature_name} value {value!r} is not in normalization "
                    f"ordering {self.ordering!r}"
                )
            return float(self.ordering.index(value))

        numeric_value = _finite_float(
            value,
            field_name=f"{self.feature_name} physical value",
        )
        if self.kind == "identity":
            return numeric_value
        if self.kind == "fixed-zero":
            if numeric_value != self.lower:
                raise ValueError(
                    f"{self.feature_name} fixed-zero normalization accepts only "
                    f"the physical value {self.lower!r}"
                )
            return 0.0
        return (numeric_value - self.lower) / (self.upper - self.lower)

    def denormalize_value(self, coordinate: object) -> object:
        """Invert one finite model coordinate into its physical representation."""

        numeric_coordinate = _finite_float(
            coordinate,
            field_name=f"{self.feature_name} model coordinate",
        )
        if self.kind == "identity":
            return numeric_coordinate
        if self.kind == "fixed-zero":
            if numeric_coordinate != 0.0:
                raise ValueError(
                    f"{self.feature_name} fixed-zero model coordinate must equal 0"
                )
            return self.lower
        if self.kind == "min-max":
            return self.lower + numeric_coordinate * (self.upper - self.lower)
        index = int(numeric_coordinate)
        if numeric_coordinate != float(index) or not 0 <= index < len(self.ordering):
            raise ValueError(
                f"{self.feature_name} ordered-index model coordinate must be an "
                f"integer from 0 through {len(self.ordering) - 1}"
            )
        return self.ordering[index]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TPMNormalizationSpec:
        """Load and strictly validate persisted normalization meaning."""

        data = _validated_payload(
            payload,
            record_name="TPM normalization",
            allowed=cls._JSON_FIELDS,
            required=cls._REQUIRED_JSON_FIELDS,
        )
        return cls(
            feature_name=data["feature_name"],
            feature_kind=data["feature_kind"],
            kind=data["kind"],
            origin=data["origin"],
            lower=data.get("lower"),
            upper=data.get("upper"),
            ordering=_sequence_value(data.get("ordering"), field_name="ordering"),
        )


def _validated_payload(
    payload: Mapping[str, Any],
    *,
    record_name: str,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{record_name} payload must be a mapping")
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(
            f"{record_name} payload contains unknown field(s): {', '.join(unknown)}"
        )
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(
            f"{record_name} payload is missing required field(s): {', '.join(missing)}"
        )
    return dict(payload)


def _non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _supported_string(
    value: object,
    *,
    field_name: str,
    supported: tuple[str, ...],
) -> str:
    normalized = _non_empty_string(value, field_name=field_name)
    if normalized not in supported:
        raise ValueError(
            f"unsupported {field_name} {normalized!r}; expected one of {supported!r}"
        )
    return normalized


def _optional_finite_float(value: object, *, field_name: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, Real) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite numeric value")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be a finite numeric value")
    return normalized


def _finite_float(value: object, *, field_name: str) -> float:
    normalized = _optional_finite_float(value, field_name=field_name)
    if normalized is None:
        raise TypeError(f"{field_name} must be a finite numeric value")
    return normalized


def _sequence_value(value: object, *, field_name: str) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field_name} must be a sequence of JSON scalar values")
    if not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of JSON scalar values")
    return tuple(value)


def _json_scalar_tuple(value: object, *, field_name: str) -> tuple[object, ...]:
    values = _sequence_value(value, field_name=field_name)
    for item in values:
        if item is None or isinstance(item, str | bool | int):
            continue
        if isinstance(item, float) and math.isfinite(item):
            continue
        raise TypeError(
            f"{field_name} entries must be finite JSON scalar values, found {item!r}"
        )
    return values


def _require_unique(values: tuple[object, ...], *, field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain distinct values")


__all__ = [
    "SUPPORTED_TPM_CONTINUOUS_DOMAIN_SHAPES",
    "SUPPORTED_TPM_DOMAIN_FEATURE_KINDS",
    "SUPPORTED_TPM_DOMAIN_ORIGINS",
    "SUPPORTED_TPM_DOMAIN_PURPOSES",
    "SUPPORTED_TPM_NORMALIZATION_KINDS",
    "SUPPORTED_TPM_NORMALIZATION_ORIGINS",
    "TPMFeatureDomain",
    "TPMNormalizationSpec",
    "TPMTrainingSupport",
]
