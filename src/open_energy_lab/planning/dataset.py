"""Persisted planning-dataset artifacts and offline loading helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FEATURE_NAME = "009-tpm-planning"
SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS = ("v1",)
PLANNING_DATASET_REQUIRED_KEYS = (
    "dataset_id",
    "schema_version",
    "created_at",
    "row_count",
    "horizon_steps",
    "timestep_hours",
    "column_order",
    "rows",
    "design_feature_schema",
    "series_field_schema",
    "target_metadata",
    "provenance",
    "export_configuration",
)
_WRAPPED_PAYLOAD_HINT_KEYS = ("metadata", "table", "dataframe", "dataset")


class UnsupportedPlanningDatasetVersionError(ValueError):
    """Raised when planning dataset loading sees an unsupported schema version."""


@dataclass(frozen=True, slots=True)
class PlanningDatasetArtifact:
    """Import-light persisted planning-dataset artifact."""

    dataset_id: str
    schema_version: str
    created_at: str = ""
    row_count: int = 0
    horizon_steps: int = 0
    timestep_hours: float = 0.0
    column_order: tuple[str, ...] = field(default_factory=tuple)
    rows: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    design_feature_schema: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    series_field_schema: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    target_metadata: Mapping[str, object] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)
    export_configuration: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS:
            raise UnsupportedPlanningDatasetVersionError(
                f"unsupported planning dataset schema_version {self.schema_version!r}"
            )

    def to_dict(self) -> dict[str, object]:
        """Serialize the dataset artifact into its persisted JSON shape."""

        return {
            "dataset_id": self.dataset_id,
            "schema_version": self.schema_version,
            "created_at": _persisted_created_at(self.created_at),
            "row_count": self.row_count,
            "horizon_steps": self.horizon_steps,
            "timestep_hours": self.timestep_hours,
            "column_order": list(self.column_order),
            "rows": [dict(row) for row in self.rows],
            "design_feature_schema": [dict(feature) for feature in self.design_feature_schema],
            "series_field_schema": {
                key: dict(value) for key, value in self.series_field_schema.items()
            },
            "target_metadata": dict(self.target_metadata),
            "provenance": dict(self.provenance),
            "export_configuration": dict(self.export_configuration),
        }

    def write_json(self, path: str | Path) -> Path:
        """Persist the artifact as human-inspectable JSON."""

        output_path = Path(path)
        output_path.write_text(
            json.dumps(self.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlanningDatasetArtifact:
        """Construct a validated artifact from one decoded JSON payload."""

        _reject_wrapped_dataset_payloads(data)

        missing = [key for key in PLANNING_DATASET_REQUIRED_KEYS if key not in data]
        if missing:
            raise ValueError(
                "planning dataset artifact is missing required keys: "
                + ", ".join(missing)
            )

        schema_version = str(data["schema_version"])
        if schema_version not in SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS:
            raise UnsupportedPlanningDatasetVersionError(
                f"unsupported planning dataset schema_version {schema_version!r}"
            )

        dataset_id = str(data["dataset_id"])
        if not dataset_id:
            raise ValueError("dataset_id must be non-empty")

        created_at = str(data["created_at"])
        _validate_timestamp(created_at, field_name="created_at")

        row_count = _non_negative_int(data["row_count"], field_name="row_count")
        horizon_steps = _positive_int(data["horizon_steps"], field_name="horizon_steps")
        timestep_hours = _positive_float(data["timestep_hours"], field_name="timestep_hours")
        column_order = _string_sequence(data["column_order"], field_name="column_order")
        if not column_order:
            raise ValueError("column_order must not be empty")
        if len(set(column_order)) != len(column_order):
            raise ValueError("column_order must not contain duplicates")

        export_configuration = _mapping(data["export_configuration"], field_name="export_configuration")
        numeric_tolerance = _positive_float(
            export_configuration.get("numeric_tolerance"),
            field_name="export_configuration.numeric_tolerance",
        )
        row_order_policy = str(export_configuration.get("row_order_policy", ""))
        if not row_order_policy:
            raise ValueError("export_configuration.row_order_policy must be non-empty")
        flattened_series_fields = _string_sequence(
            export_configuration.get("flattened_series_fields"),
            field_name="export_configuration.flattened_series_fields",
        )
        if not flattened_series_fields:
            raise ValueError(
                "export_configuration.flattened_series_fields must not be empty"
            )
        if not isinstance(export_configuration.get("include_provenance"), bool):
            raise TypeError("export_configuration.include_provenance must be a bool")

        series_field_schema = {
            str(key): _mapping(value, field_name=f"series_field_schema.{key}")
            for key, value in _mapping(
                data["series_field_schema"], field_name="series_field_schema"
            ).items()
        }
        if not series_field_schema:
            raise ValueError("series_field_schema must not be empty")
        _validate_series_field_schema(
            series_field_schema,
            flattened_series_fields=flattened_series_fields,
            column_order=column_order,
            horizon_steps=horizon_steps,
        )

        target_metadata = _mapping(data["target_metadata"], field_name="target_metadata")
        _validate_target_metadata(target_metadata)

        provenance = _mapping(data["provenance"], field_name="provenance")
        _validate_seed_lineage(provenance)
        if export_configuration["include_provenance"] and not provenance:
            raise ValueError(
                "provenance must not be empty when include_provenance is enabled"
            )

        design_feature_schema = _design_feature_schema(
            data["design_feature_schema"],
            column_order=column_order,
        )

        rows = _ordered_rows(
            data["rows"],
            column_order=column_order,
            row_count=row_count,
        )
        _validate_row_order(rows, row_order_policy=row_order_policy)
        _validate_shortfall_rows(
            rows,
            target_metadata=target_metadata,
            series_field_schema=series_field_schema,
            horizon_steps=horizon_steps,
            timestep_hours=timestep_hours,
            numeric_tolerance=numeric_tolerance,
        )

        return cls(
            dataset_id=dataset_id,
            schema_version=schema_version,
            created_at=created_at,
            row_count=row_count,
            horizon_steps=horizon_steps,
            timestep_hours=timestep_hours,
            column_order=column_order,
            rows=rows,
            design_feature_schema=design_feature_schema,
            series_field_schema=series_field_schema,
            target_metadata=target_metadata,
            provenance=provenance,
            export_configuration={
                "row_order_policy": row_order_policy,
                "flattened_series_fields": list(flattened_series_fields),
                "include_provenance": export_configuration["include_provenance"],
                "numeric_tolerance": numeric_tolerance,
                **{
                    key: value
                    for key, value in export_configuration.items()
                    if key
                    not in {
                        "row_order_policy",
                        "flattened_series_fields",
                        "include_provenance",
                        "numeric_tolerance",
                    }
                },
            },
        )


def load_planning_dataset(source: str | Path | Mapping[str, Any]) -> PlanningDatasetArtifact:
    """Load and validate a persisted planning dataset artifact."""

    if isinstance(source, Mapping):
        raw_payload = source
    else:
        raw_payload = json.loads(Path(source).read_text(encoding="utf-8"))

    return PlanningDatasetArtifact.from_dict(raw_payload)


__all__ = [
    "FEATURE_NAME",
    "PLANNING_DATASET_REQUIRED_KEYS",
    "PlanningDatasetArtifact",
    "SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS",
    "UnsupportedPlanningDatasetVersionError",
    "load_planning_dataset",
]


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): inner_value for key, inner_value in value.items()}


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")
    normalized = tuple(str(item) for item in value)
    if any(not item for item in normalized):
        raise ValueError(f"{field_name} must not contain empty strings")
    return normalized


def _positive_int(value: object, *, field_name: str) -> int:
    normalized = int(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _non_negative_int(value: object, *, field_name: str) -> int:
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return normalized


def _positive_float(value: object, *, field_name: str) -> float:
    normalized = float(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _validate_timestamp(value: object, *, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty ISO-8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from exc


def _persisted_created_at(created_at: str) -> str:
    if created_at:
        _validate_timestamp(created_at, field_name="created_at")
        return created_at
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _reject_wrapped_dataset_payloads(data: Mapping[str, Any]) -> None:
    has_required_top_level_shape = all(key in data for key in PLANNING_DATASET_REQUIRED_KEYS)
    if has_required_top_level_shape:
        return
    if any(key in data for key in _WRAPPED_PAYLOAD_HINT_KEYS):
        raise ValueError(
            "planning dataset payload must store rows directly at the top level; "
            "wrapped metadata/table payloads are unsupported"
        )


def _validate_series_field_schema(
    series_field_schema: Mapping[str, Mapping[str, object]],
    *,
    flattened_series_fields: tuple[str, ...],
    column_order: tuple[str, ...],
    horizon_steps: int,
) -> None:
    flattened_field_set = set(flattened_series_fields)
    seen_source_fields: set[str] = set()
    for prefix, schema in series_field_schema.items():
        source_field = str(schema.get("source_field", ""))
        column_prefix = str(schema.get("column_prefix", ""))
        if not source_field:
            raise ValueError(f"series_field_schema.{prefix}.source_field must be non-empty")
        if not column_prefix:
            raise ValueError(f"series_field_schema.{prefix}.column_prefix must be non-empty")
        if column_prefix != prefix:
            raise ValueError(
                f"series_field_schema.{prefix}.column_prefix must match its key"
            )
        if source_field not in flattened_field_set:
            raise ValueError(
                f"series_field_schema.{prefix}.source_field must appear in "
                "export_configuration.flattened_series_fields"
            )
        if source_field in seen_source_fields:
            raise ValueError("series_field_schema source_field values must be unique")
        seen_source_fields.add(source_field)
        expected_columns = {f"{column_prefix}_{step}" for step in range(horizon_steps)}
        if not expected_columns.issubset(column_order):
            raise ValueError(
                f"column_order must contain all expected series columns for prefix {column_prefix!r}"
            )

    if seen_source_fields != flattened_field_set:
        raise ValueError(
            "series_field_schema must describe every flattened series field exactly once"
        )


def _validate_target_metadata(target_metadata: Mapping[str, object]) -> None:
    required_keys = (
        "target_name",
        "numerator_source_field",
        "denominator_source_field",
        "aggregation_rule",
        "threshold_default",
        "supported_query_mode",
    )
    missing = [key for key in required_keys if key not in target_metadata]
    if missing:
        raise ValueError(
            "target_metadata is missing required keys: " + ", ".join(missing)
        )
    target_name = str(target_metadata["target_name"])
    if target_name != "shortfall":
        raise ValueError("target_metadata.target_name must be 'shortfall'")
    if "timestep_hours" not in str(target_metadata["aggregation_rule"]):
        raise ValueError(
            "target_metadata.aggregation_rule must document timestep_hours weighting"
        )
    float(target_metadata["threshold_default"])
    if not str(target_metadata["supported_query_mode"]):
        raise ValueError("target_metadata.supported_query_mode must be non-empty")


def _validate_seed_lineage(provenance: Mapping[str, object]) -> None:
    if "family_seed" in provenance:
        int(provenance["family_seed"])
    if "paired_family_seed" in provenance:
        int(provenance["paired_family_seed"])
    if "family_seed" in provenance and "paired_family_seed" in provenance:
        if int(provenance["family_seed"]) != int(provenance["paired_family_seed"]):
            raise ValueError("family_seed and paired_family_seed must align")


def _design_feature_schema(
    value: object,
    *,
    column_order: tuple[str, ...],
) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError("design_feature_schema must be a sequence of mappings")

    features: list[Mapping[str, object]] = []
    seen_feature_names: set[str] = set()
    for index, raw_feature in enumerate(value):
        feature = _mapping(raw_feature, field_name=f"design_feature_schema[{index}]")
        for required_key in ("feature_name", "feature_role", "feature_type"):
            if required_key not in feature or not str(feature[required_key]):
                raise ValueError(
                    f"design_feature_schema[{index}].{required_key} must be non-empty"
                )
        feature_name = str(feature["feature_name"])
        if feature_name not in column_order:
            raise ValueError(
                f"design_feature_schema[{index}].feature_name must appear in column_order"
            )
        if feature_name in {"scenario_index", "shortfall"}:
            raise ValueError(
                "design_feature_schema must describe decision/design columns only"
            )
        if feature_name in seen_feature_names:
            raise ValueError("design_feature_schema feature_name values must be unique")
        seen_feature_names.add(feature_name)
        features.append(feature)
    return tuple(features)


def _ordered_rows(
    value: object,
    *,
    column_order: tuple[str, ...],
    row_count: int,
) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError("rows must be a sequence of mappings")

    rows: list[Mapping[str, object]] = []
    for index, raw_row in enumerate(value):
        row = _mapping(raw_row, field_name=f"rows[{index}]")
        row_keys = tuple(row.keys())
        expected_keys = set(column_order)
        if set(row_keys) != expected_keys:
            missing = expected_keys - set(row_keys)
            extra = set(row_keys) - expected_keys
            details: list[str] = []
            if missing:
                details.append("missing " + ", ".join(sorted(missing)))
            if extra:
                details.append("unexpected " + ", ".join(sorted(extra)))
            raise ValueError(f"rows[{index}] must match column_order exactly: {'; '.join(details)}")
        rows.append({column_name: row[column_name] for column_name in column_order})

    if len(rows) != row_count:
        raise ValueError("row_count must match the number of persisted rows")
    return tuple(rows)


def _validate_row_order(
    rows: Sequence[Mapping[str, object]],
    *,
    row_order_policy: str,
) -> None:
    if row_order_policy != "scenario_index_ascending":
        return
    scenario_indices = [int(row["scenario_index"]) for row in rows]
    if scenario_indices != sorted(scenario_indices):
        raise ValueError("rows must preserve scenario_index_ascending order")


def _validate_shortfall_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    target_metadata: Mapping[str, object],
    series_field_schema: Mapping[str, Mapping[str, object]],
    horizon_steps: int,
    timestep_hours: float,
    numeric_tolerance: float,
) -> None:
    numerator_source_field = str(target_metadata["numerator_source_field"])
    denominator_source_field = str(target_metadata["denominator_source_field"])
    prefix_by_source_field = {
        str(schema["source_field"]): str(schema["column_prefix"])
        for schema in series_field_schema.values()
    }

    numerator_prefix = prefix_by_source_field.get(numerator_source_field)
    denominator_prefix = prefix_by_source_field.get(denominator_source_field)
    if numerator_prefix is None or denominator_prefix is None:
        raise ValueError(
            "series_field_schema must include prefixes for the shortfall numerator and denominator"
        )

    for index, row in enumerate(rows):
        load_series = tuple(
            float(row[f"{denominator_prefix}_{step}"]) for step in range(horizon_steps)
        )
        unmet_load_series = tuple(
            float(row[f"{numerator_prefix}_{step}"]) for step in range(horizon_steps)
        )
        expected_shortfall = _derive_shortfall(
            load_series=load_series,
            unmet_load_series=unmet_load_series,
            timestep_hours=timestep_hours,
            numeric_tolerance=numeric_tolerance,
        )
        actual_shortfall = float(row["shortfall"])
        if abs(actual_shortfall - expected_shortfall) > numeric_tolerance:
            raise ValueError(
                f"rows[{index}].shortfall must match the documented energy-ratio target"
            )


def _derive_shortfall(
    *,
    load_series: Sequence[float],
    unmet_load_series: Sequence[float],
    timestep_hours: float,
    numeric_tolerance: float,
) -> float:
    unmet_energy = sum(unmet_load_series) * timestep_hours
    load_energy = sum(load_series) * timestep_hours
    if abs(load_energy) <= numeric_tolerance:
        if abs(unmet_energy) <= numeric_tolerance:
            return 0.0
        raise ValueError("shortfall target cannot be derived from zero total load energy")
    return unmet_energy / load_energy
