"""TPM training-data handling and deterministic schema normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from numbers import Real

from .domains import TPMFeatureDomain, TPMNormalizationSpec, TPMTrainingSupport
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


def normalize_training_data(
    rows: Sequence[Mapping[str, object]],
    *,
    feature_domains: Mapping[str, TPMFeatureDomain] | None = None,
    feature_roles: Mapping[str, str] | None = None,
) -> TPMTrainingData:
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
    resolved_domains = _validated_feature_domains(
        feature_domains,
        column_order=column_order,
    )
    resolved_roles = _validated_feature_roles(
        feature_roles,
        column_order=column_order,
    )
    feature_schema = tuple(
        _resolve_feature_spec(
            column_name,
            [row[column_name] for row in canonical_rows],
            feature_role=resolved_roles.get(
                column_name,
                infer_feature_role(column_name),
            ),
            mathematical_domain=resolved_domains.get(column_name),
        )
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
        if _is_binary_numeric_domain(feature_name, numeric_values):
            ordered_values = _binary_numeric_order(numeric_values)
            return TPMFeatureSpec(
                feature_name=feature_name,
                feature_type="binary",
                feature_role=feature_role,
                modifiable=modifiable,
                discrete_values=ordered_values,
                ordering=ordered_values,
            )
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


def _resolve_feature_spec(
    feature_name: str,
    values: Sequence[object],
    *,
    feature_role: str,
    mathematical_domain: TPMFeatureDomain | None,
) -> TPMFeatureSpec:
    if mathematical_domain is None:
        inferred = _infer_feature_spec(feature_name, values)
        if inferred.feature_type == "mixed":
            return TPMFeatureSpec(
                feature_name=feature_name,
                feature_type="mixed",
                feature_role=feature_role,
                modifiable=feature_role == "decision",
                bounds=inferred.bounds,
                discrete_values=inferred.discrete_values,
                ordering=inferred.ordering,
                normalization_rule=inferred.normalization_rule,
            )
        mathematical_domain = TPMFeatureDomain(
            feature_name=feature_name,
            feature_kind=inferred.feature_type,
            purpose=(
                "decision-domain"
                if feature_role == "decision"
                else "distribution-support"
            ),
            shape="unknown",
            origin="omitted",
        )
        training_support = _derive_training_support(
            feature_name,
            values,
            feature_kind=inferred.feature_type,
        )
        normalization = _legacy_normalization(
            feature_name=feature_name,
            feature_kind=inferred.feature_type,
            inferred=inferred,
        )
    else:
        if mathematical_domain.feature_name != feature_name:
            raise ValueError(
                f"feature_domains mapping key {feature_name!r} does not match "
                f"declaration feature_name {mathematical_domain.feature_name!r}"
            )
        training_support = _derive_training_support(
            feature_name,
            values,
            feature_kind=mathematical_domain.feature_kind,
        )
        for value in values:
            mathematical_domain.validate_value(value)
        normalization = _declared_normalization(mathematical_domain)

    return TPMFeatureSpec(
        feature_name=feature_name,
        feature_type=mathematical_domain.feature_kind,
        feature_role=feature_role,
        modifiable=feature_role == "decision",
        mathematical_domain=mathematical_domain,
        training_support=training_support,
        normalization=normalization,
    )


def _derive_training_support(
    feature_name: str,
    values: Sequence[object],
    *,
    feature_kind: str,
) -> TPMTrainingSupport:
    if feature_kind == "continuous":
        numeric_values: list[float] = []
        for value in values:
            if not _is_numeric_scalar(value):
                raise ValueError(
                    f"{feature_name} physical observations must be finite numeric values"
                )
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise ValueError(
                    f"{feature_name} physical observations must be finite numeric values"
                )
            numeric_values.append(numeric_value)
        return TPMTrainingSupport(
            feature_name=feature_name,
            feature_kind="continuous",
            minimum=min(numeric_values),
            maximum=max(numeric_values),
        )

    observed_values = _stable_unique(values)
    return TPMTrainingSupport(
        feature_name=feature_name,
        feature_kind=feature_kind,
        observed_values=observed_values,
    )


def _declared_normalization(domain: TPMFeatureDomain) -> TPMNormalizationSpec:
    if domain.feature_kind == "continuous":
        if domain.shape != "finite":
            return TPMNormalizationSpec(
                feature_name=domain.feature_name,
                feature_kind="continuous",
                kind="identity",
                origin="caller-declared",
            )
        return TPMNormalizationSpec(
            feature_name=domain.feature_name,
            feature_kind="continuous",
            kind=(
                "fixed-zero" if domain.lower == domain.upper else "min-max"
            ),
            origin="caller-declared",
            lower=domain.lower,
            upper=domain.upper,
        )
    return TPMNormalizationSpec(
        feature_name=domain.feature_name,
        feature_kind=domain.feature_kind,
        kind="ordered-index",
        origin="caller-declared",
        ordering=domain.ordering,
    )


def _legacy_normalization(
    *,
    feature_name: str,
    feature_kind: str,
    inferred: TPMFeatureSpec,
) -> TPMNormalizationSpec:
    if feature_kind == "continuous":
        lower, upper = inferred.bounds
        return TPMNormalizationSpec(
            feature_name=feature_name,
            feature_kind="continuous",
            kind="fixed-zero" if lower == upper else "min-max",
            origin="legacy-inferred",
            lower=lower,
            upper=upper,
        )
    return TPMNormalizationSpec(
        feature_name=feature_name,
        feature_kind=feature_kind,
        kind="ordered-index",
        origin="legacy-inferred",
        ordering=inferred.ordering,
    )


def _validated_feature_domains(
    feature_domains: Mapping[str, TPMFeatureDomain] | None,
    *,
    column_order: tuple[str, ...],
) -> dict[str, TPMFeatureDomain]:
    if feature_domains is None:
        return {}
    if not isinstance(feature_domains, Mapping):
        raise TypeError("feature_domains must be a mapping")
    normalized: dict[str, TPMFeatureDomain] = {}
    for key, domain in feature_domains.items():
        feature_name = str(key)
        if not isinstance(domain, TPMFeatureDomain):
            raise TypeError(
                f"feature_domains[{feature_name!r}] must be a TPMFeatureDomain"
            )
        if domain.feature_name != feature_name:
            raise ValueError(
                f"feature_domains mapping key {feature_name!r} does not match "
                f"declaration feature_name {domain.feature_name!r}"
            )
        normalized[feature_name] = domain
    unknown = sorted(set(normalized) - set(column_order))
    if unknown:
        raise ValueError(
            "feature_domains reference unknown or unselected columns: "
            + ", ".join(unknown)
        )
    return normalized


def _validated_feature_roles(
    feature_roles: Mapping[str, str] | None,
    *,
    column_order: tuple[str, ...],
) -> dict[str, str]:
    if feature_roles is None:
        return {}
    if not isinstance(feature_roles, Mapping):
        raise TypeError("feature_roles must be a mapping")
    normalized = {str(name): str(role) for name, role in feature_roles.items()}
    unknown = sorted(set(normalized) - set(column_order))
    if unknown:
        raise ValueError(
            "feature_roles reference unknown columns: " + ", ".join(unknown)
        )
    if any(not name or not role for name, role in normalized.items()):
        raise ValueError("feature_roles must contain non-empty names and roles")
    return normalized


def _stable_unique(values: Sequence[object]) -> tuple[object, ...]:
    observed: list[object] = []
    for value in values:
        if value not in observed:
            observed.append(value)
    return tuple(observed)


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


def _is_binary_numeric_domain(feature_name: str, values: Sequence[float]) -> bool:
    if feature_name == "scenario_index" or feature_name.endswith("_index"):
        return False
    unique_values = {float(value) for value in values}
    return unique_values == {0.0, 1.0}


def _binary_numeric_order(values: Sequence[float]) -> tuple[float, float]:
    unique_values = sorted({float(value) for value in values})
    return (unique_values[0], unique_values[1])
