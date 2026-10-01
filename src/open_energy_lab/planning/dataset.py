"""Persisted planning-dataset artifacts and offline loading helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from open_energy_lab.core.artifact import read_artifact_source
from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import write_bytes_atomically
from open_energy_lab.core.time import format_utc, utc_timestamp_text
from open_energy_lab.core.validation import (
    boolean,
    finite,
    integer,
    mapping,
    non_empty_str,
    non_negative_int,
    positive,
    positive_int,
    require_fields,
    sequence,
)


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


class PlanningDatasetValidationError(ValidationError):
    """Raised when a planning dataset artifact is malformed."""


class UnsupportedPlanningDatasetVersionError(PlanningDatasetValidationError):
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
        if self.created_at:
            created_at = _validate_timestamp(self.created_at, field_name="created_at")
        else:
            created_at = format_utc(datetime.now(UTC).replace(microsecond=0))
        object.__setattr__(self, "created_at", created_at)

    def to_dict(self) -> dict[str, object]:
        """Serialize the dataset artifact into its persisted JSON shape."""

        return {
            "dataset_id": self.dataset_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
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
        document = json.dumps(self.to_dict(), indent=2, allow_nan=False) + "\n"
        write_bytes_atomically(output_path, document.encode("utf-8"))
        return output_path

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlanningDatasetArtifact:
        """Construct a validated artifact from one decoded JSON payload."""

        _reject_wrapped_dataset_payloads(data)

        _require_fields(data, PLANNING_DATASET_REQUIRED_KEYS, field_name="planning dataset artifact")

        schema_version = _non_empty(data["schema_version"], field_name="schema_version")
        if schema_version not in SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS:
            raise UnsupportedPlanningDatasetVersionError(
                f"unsupported planning dataset schema_version {schema_version!r}"
            )

        dataset_id = _non_empty(data["dataset_id"], field_name="dataset_id")
        created_at = _validate_timestamp(data["created_at"], field_name="created_at")

        row_count = _non_negative_int(data["row_count"], field_name="row_count")
        horizon_steps = _positive_int(data["horizon_steps"], field_name="horizon_steps")
        timestep_hours = _positive_float(data["timestep_hours"], field_name="timestep_hours")
        column_order = _string_sequence(data["column_order"], field_name="column_order")
        if not column_order:
            raise PlanningDatasetValidationError("column_order must not be empty")
        if len(set(column_order)) != len(column_order):
            raise PlanningDatasetValidationError("column_order must not contain duplicates")

        export_configuration = _mapping(data["export_configuration"], field_name="export_configuration")
        numeric_tolerance = _positive_float(
            export_configuration.get("numeric_tolerance"),
            field_name="export_configuration.numeric_tolerance",
        )
        row_order_policy = _non_empty(
            export_configuration.get("row_order_policy"),
            field_name="export_configuration.row_order_policy",
        )
        flattened_series_fields = _string_sequence(
            export_configuration.get("flattened_series_fields"),
            field_name="export_configuration.flattened_series_fields",
        )
        if not flattened_series_fields:
            raise PlanningDatasetValidationError(
                "export_configuration.flattened_series_fields must not be empty"
            )
        _boolean(
            export_configuration.get("include_provenance"),
            field_name="export_configuration.include_provenance",
        )

        series_field_schema = {
            str(key): _mapping(value, field_name=f"series_field_schema.{key}")
            for key, value in _mapping(
                data["series_field_schema"], field_name="series_field_schema"
            ).items()
        }
        if not series_field_schema:
            raise PlanningDatasetValidationError("series_field_schema must not be empty")
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
            raise PlanningDatasetValidationError(
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

    raw_payload, _, _ = read_artifact_source(
        source, label="planning dataset artifact", error=PlanningDatasetValidationError
    )
    return PlanningDatasetArtifact.from_dict(raw_payload)


__all__ = [
    "FEATURE_NAME",
    "PLANNING_DATASET_REQUIRED_KEYS",
    "PlanningDatasetArtifact",
    "PlanningDatasetValidationError",
    "SUPPORTED_PLANNING_DATASET_SCHEMA_VERSIONS",
    "UnsupportedPlanningDatasetVersionError",
    "load_planning_dataset",
]


_E = PlanningDatasetValidationError
_mapping = partial(mapping, error=_E)
_non_empty = partial(non_empty_str, error=_E)
_finite = partial(finite, error=_E)
_integer = partial(integer, error=_E)
_boolean = partial(boolean, error=_E)
_positive_int = partial(positive_int, error=_E)
_non_negative_int = partial(non_negative_int, error=_E)
_positive_float = partial(positive, error=_E)
_require_fields = partial(require_fields, error=_E)
_sequence = partial(sequence, error=_E)
_validate_timestamp = partial(utc_timestamp_text, error=_E)


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    items = _sequence(value, field_name=field_name)
    return tuple(
        _non_empty(item, field_name=f"{field_name}[{index}]") for index, item in enumerate(items)
    )


def _reject_wrapped_dataset_payloads(data: Mapping[str, Any]) -> None:
    has_required_top_level_shape = all(key in data for key in PLANNING_DATASET_REQUIRED_KEYS)
    if has_required_top_level_shape:
        return
    if any(key in data for key in _WRAPPED_PAYLOAD_HINT_KEYS):
        raise PlanningDatasetValidationError(
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
        source_field = _non_empty(
            schema.get("source_field"), field_name=f"series_field_schema.{prefix}.source_field"
        )
        column_prefix = _non_empty(
            schema.get("column_prefix"), field_name=f"series_field_schema.{prefix}.column_prefix"
        )
        if column_prefix != prefix:
            raise PlanningDatasetValidationError(
                f"series_field_schema.{prefix}.column_prefix must match its key"
            )
        if source_field not in flattened_field_set:
            raise PlanningDatasetValidationError(
                f"series_field_schema.{prefix}.source_field must appear in "
                "export_configuration.flattened_series_fields"
            )
        if source_field in seen_source_fields:
            raise PlanningDatasetValidationError("series_field_schema source_field values must be unique")
        seen_source_fields.add(source_field)
        expected_columns = {f"{column_prefix}_{step}" for step in range(horizon_steps)}
        if not expected_columns.issubset(column_order):
            raise PlanningDatasetValidationError(
                f"column_order must contain all expected series columns for prefix {column_prefix!r}"
            )

    if seen_source_fields != flattened_field_set:
        raise PlanningDatasetValidationError(
            "series_field_schema must describe every flattened series field exactly once"
        )


def _validate_target_metadata(target_metadata: Mapping[str, object]) -> None:
    required_keys = (
        "target_name",
        "event_target_name",
        "numerator_source_field",
        "denominator_source_field",
        "aggregation_rule",
        "threshold_default",
        "event_threshold_source",
        "event_threshold_comparison",
        "supported_query_mode",
    )
    _require_fields(target_metadata, required_keys, field_name="target_metadata")
    target_name = str(target_metadata["target_name"])
    if target_name != "shortfall":
        raise PlanningDatasetValidationError("target_metadata.target_name must be 'shortfall'")
    event_target_name = str(target_metadata["event_target_name"])
    if event_target_name != "shortfall_exceeds_threshold":
        raise PlanningDatasetValidationError(
            "target_metadata.event_target_name must be 'shortfall_exceeds_threshold'"
        )
    if "timestep_hours" not in _non_empty(target_metadata["aggregation_rule"], field_name="target_metadata.aggregation_rule"):
        raise PlanningDatasetValidationError(
            "target_metadata.aggregation_rule must document timestep_hours weighting"
        )
    _finite(target_metadata["threshold_default"], field_name="target_metadata.threshold_default")
    if str(target_metadata["event_threshold_source"]) != "threshold_default":
        raise PlanningDatasetValidationError(
            "target_metadata.event_threshold_source must be 'threshold_default'"
        )
    if str(target_metadata["event_threshold_comparison"]) != ">":
        raise PlanningDatasetValidationError(
            "target_metadata.event_threshold_comparison must be '>'"
        )
    _non_empty(target_metadata["supported_query_mode"], field_name="target_metadata.supported_query_mode")


def _validate_seed_lineage(provenance: Mapping[str, object]) -> None:
    seeds = {
        name: _integer(provenance[name], field_name=f"provenance.{name}")
        for name in ("family_seed", "paired_family_seed")
        if name in provenance
    }
    if len(seeds) == 2:
        if seeds["family_seed"] != seeds["paired_family_seed"]:
            raise PlanningDatasetValidationError("family_seed and paired_family_seed must align")


def _design_feature_schema(
    value: object,
    *,
    column_order: tuple[str, ...],
) -> tuple[Mapping[str, object], ...]:
    value = _sequence(value, field_name="design_feature_schema")
    features: list[Mapping[str, object]] = []
    seen_feature_names: set[str] = set()
    for index, raw_feature in enumerate(value):
        feature = _mapping(raw_feature, field_name=f"design_feature_schema[{index}]")
        for required_key in ("feature_name", "feature_role", "feature_type"):
            _non_empty(
                feature.get(required_key), field_name=f"design_feature_schema[{index}].{required_key}"
            )
        feature_name = feature["feature_name"]
        if feature_name not in column_order:
            raise PlanningDatasetValidationError(
                f"design_feature_schema[{index}].feature_name must appear in column_order"
            )
        if feature_name in {"scenario_index", "shortfall", "shortfall_exceeds_threshold"}:
            raise PlanningDatasetValidationError(
                "design_feature_schema must describe decision/design columns only"
            )
        if feature_name in seen_feature_names:
            raise PlanningDatasetValidationError("design_feature_schema feature_name values must be unique")
        seen_feature_names.add(feature_name)
        features.append(feature)
    return tuple(features)


def _ordered_rows(
    value: object,
    *,
    column_order: tuple[str, ...],
    row_count: int,
) -> tuple[Mapping[str, object], ...]:
    value = _sequence(value, field_name="rows")
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
            raise PlanningDatasetValidationError(f"rows[{index}] must match column_order exactly: {'; '.join(details)}")
        rows.append({column_name: row[column_name] for column_name in column_order})

    if len(rows) != row_count:
        raise PlanningDatasetValidationError("row_count must match the number of persisted rows")
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
        raise PlanningDatasetValidationError("rows must preserve scenario_index_ascending order")


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
        raise PlanningDatasetValidationError(
            "series_field_schema must include prefixes for the shortfall numerator and denominator"
        )

    event_target_name = str(target_metadata["event_target_name"])
    threshold_default = _finite(
        target_metadata["threshold_default"], field_name="target_metadata.threshold_default"
    )

    for index, row in enumerate(rows):
        load_series = tuple(
            _finite(row[name], field_name=f"rows[{index}].{name}")
            for name in (f"{denominator_prefix}_{step}" for step in range(horizon_steps))
        )
        unmet_load_series = tuple(
            _finite(row[name], field_name=f"rows[{index}].{name}")
            for name in (f"{numerator_prefix}_{step}" for step in range(horizon_steps))
        )
        expected_shortfall = _derive_shortfall(
            load_series=load_series,
            unmet_load_series=unmet_load_series,
            timestep_hours=timestep_hours,
            numeric_tolerance=numeric_tolerance,
        )
        actual_shortfall = _finite(row["shortfall"], field_name=f"rows[{index}].shortfall")
        if abs(actual_shortfall - expected_shortfall) > numeric_tolerance:
            raise PlanningDatasetValidationError(
                f"rows[{index}].shortfall must match the documented energy-ratio target"
            )
        actual_event = int(row[event_target_name])
        expected_event = int(expected_shortfall > threshold_default)
        if actual_event != expected_event:
            raise PlanningDatasetValidationError(
                f"rows[{index}].{event_target_name} must match the documented event target"
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
        raise PlanningDatasetValidationError("shortfall target cannot be derived from zero total load energy")
    return unmet_energy / load_energy
