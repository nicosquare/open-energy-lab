"""TPM training-data handling and deterministic schema normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real

from .features import TPMFeatureSpec, infer_feature_role


@dataclass(frozen=True, slots=True)
class TPMTrainingData:
    """Normalized TPM training data with inferred typed feature metadata."""

    column_order: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    feature_schema: tuple[TPMFeatureSpec, ...] = field(default_factory=tuple)
    normalized_rows: tuple[Mapping[str, float], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.column_order:
            raise ValueError("column_order must not be empty")
        if len(set(self.column_order)) != len(self.column_order):
            raise ValueError("column_order must not contain duplicates")
        if self.feature_schema:
            schema_names = tuple(feature.feature_name for feature in self.feature_schema)
            if schema_names != self.column_order:
                raise ValueError("feature_schema order must match column_order")
        for index, row in enumerate(self.rows):
            _validate_row_mapping(row, column_order=self.column_order, row_index=index)
        for index, row in enumerate(self.normalized_rows):
            _validate_row_mapping(row, column_order=self.column_order, row_index=index)

    @property
    def matrix(self) -> tuple[tuple[float, ...], ...]:
        """Expose normalized rows in feature-order matrix form."""

        return tuple(
            tuple(float(row[column]) for column in self.column_order)
            for row in self.normalized_rows
        )


def normalize_training_data(rows: Sequence[Mapping[str, object]]) -> TPMTrainingData:
    """Validate and normalize training rows into a deterministic TPM payload."""

    if isinstance(rows, Mapping) or isinstance(rows, (str, bytes)):
        raise TypeError("rows must be a sequence of row mappings")
    if not rows:
        raise ValueError("rows must not be empty")
    if any(not isinstance(row, Mapping) for row in rows):
        raise TypeError("every training row must be a mapping")

    column_order = tuple(str(key) for key in rows[0].keys())
    if not column_order:
        raise ValueError("training rows must contain at least one feature column")
    if len(set(column_order)) != len(column_order):
        raise ValueError("training rows must not contain duplicate feature names")

    canonical_rows = tuple(
        _canonicalize_row(row, column_order=column_order, row_index=index)
        for index, row in enumerate(rows)
    )
    feature_schema = tuple(
        _infer_feature_spec(column_name, [row[column_name] for row in canonical_rows])
        for column_name in column_order
    )
    normalized_rows = tuple(
        {
            feature.feature_name: feature.normalize_value(row[feature.feature_name])
            for feature in feature_schema
        }
        for row in canonical_rows
    )

    return TPMTrainingData(
        column_order=column_order,
        rows=canonical_rows,
        feature_schema=feature_schema,
        normalized_rows=normalized_rows,
    )


__all__ = ["TPMTrainingData", "normalize_training_data"]


def _validate_row_mapping(
    row: Mapping[str, object],
    *,
    column_order: tuple[str, ...],
    row_index: int,
) -> None:
    if tuple(row.keys()) != column_order:
        raise ValueError(
            f"row {row_index} must preserve the same keys and order as the inferred schema"
        )


def _canonicalize_row(
    row: Mapping[str, object],
    *,
    column_order: tuple[str, ...],
    row_index: int,
) -> dict[str, object]:
    row_keys = tuple(str(key) for key in row.keys())
    if row_keys != column_order:
        missing = sorted(set(column_order) - set(row_keys))
        extra = sorted(set(row_keys) - set(column_order))
        details: list[str] = []
        if missing:
            details.append(f"missing keys {missing!r}")
        if extra:
            details.append(f"unexpected keys {extra!r}")
        if not details:
            details.append("keys differ from the first row")
        raise ValueError(
            f"all training rows must use the same keys and order; row {row_index} has "
            + ", ".join(details)
        )
    return {column_name: row[column_name] for column_name in column_order}


def _infer_feature_spec(
    feature_name: str,
    values: Sequence[object],
) -> TPMFeatureSpec:
    non_null_values = [value for value in values if value is not None]
    if not non_null_values:
        raise ValueError(f"{feature_name} must contain at least one non-null value")

    feature_role = infer_feature_role(feature_name)
    modifiable = feature_role != "target"

    numeric_values = [float(value) for value in non_null_values if _is_numeric_scalar(value)]
    categorical_values = [value for value in non_null_values if not _is_numeric_scalar(value)]

    if numeric_values and categorical_values:
        return TPMFeatureSpec(
            feature_name=feature_name,
            feature_type="mixed",
            feature_role=feature_role,
            modifiable=modifiable,
            bounds=(min(numeric_values), max(numeric_values)),
            discrete_values=_sorted_unique(categorical_values),
        )

    if numeric_values:
        return TPMFeatureSpec(
            feature_name=feature_name,
            feature_type="continuous",
            feature_role=feature_role,
            modifiable=modifiable,
            bounds=(min(numeric_values), max(numeric_values)),
        )

    discrete_values = _sorted_unique(categorical_values)
    feature_type = "binary" if _is_binary_domain(discrete_values) else "categorical"
    return TPMFeatureSpec(
        feature_name=feature_name,
        feature_type=feature_type,
        feature_role=feature_role,
        modifiable=modifiable,
        discrete_values=discrete_values,
    )


def _is_numeric_scalar(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _sorted_unique(values: Sequence[object]) -> tuple[object, ...]:
    seen: dict[tuple[str, str], object] = {}
    for value in values:
        key = (type(value).__name__, str(value))
        seen.setdefault(key, value)
    return tuple(seen[key] for key in sorted(seen))


def _is_binary_domain(values: tuple[object, ...]) -> bool:
    if len(values) != 2:
        return False
    if all(isinstance(value, bool) for value in values):
        return True
    normalized = frozenset(str(value).strip().lower() for value in values)
    return normalized in {
        frozenset({"0", "1"}),
        frozenset({"disabled", "enabled"}),
        frozenset({"false", "true"}),
        frozenset({"n", "y"}),
        frozenset({"no", "yes"}),
        frozenset({"off", "on"}),
    }
