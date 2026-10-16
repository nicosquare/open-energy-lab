"""Persisted demand-artifact loading helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from open_energy_lab.core.artifact import read_artifact_source
from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import write_bytes_atomically
from open_energy_lab.core.time import utc_timestamp_text
from open_energy_lab.core.validation import (
    finite,
    mapping,
    non_empty_str,
    positive_int,
    require_fields,
    sequence,
)
from open_energy_lab.weather._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    LOCAL_CIVIL_TIME_BASIS,
)



SUPPORTED_DEMAND_ARTIFACT_SCHEMA_VERSIONS = ("v1",)
SUPPORTED_DOUBLE_COUNTING_POLICY = (
    "explicit_cooling_separate_from_non_thermal_electric"
)
EXPECTED_OUTPUT_ORDER = (
    "non_thermal_electric_demand_kw",
    "cooling_demand_rt",
)


class DemandArtifactValidationError(ValidationError):
    """Raised when a demand artifact violates its schema."""


class UnsupportedDemandArtifactVersionError(DemandArtifactValidationError):
    """Raised when artifact loading sees an unsupported schema version."""


@dataclass(frozen=True, slots=True)
class DemandArtifact:
    """Import-light persisted demand artifact."""

    artifact_id: str
    schema_version: str
    feature_name: str
    created_at: str
    timezone_name: str
    time_basis: str
    timestep_hours: float
    required_weather_field_order: tuple[str, ...]
    training_record_summary: dict[str, object]
    non_thermal_electric_model: dict[str, object]
    cooling_demand_model: dict[str, object]
    shared_residual_model: dict[str, object]
    double_counting_policy: str
    provenance: dict[str, object]
    supported_sampling_modes: tuple[str, ...]
    # Optional empirical day-level variability: whole residual days multiplied onto
    # the expected profile instead of per-step Gaussian residuals.
    residual_day_library: dict[str, object] | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "feature_name", "timezone_name", "double_counting_policy"):
            _non_empty(getattr(self, name), field_name=name)
        object.__setattr__(self, "timestep_hours", _finite(self.timestep_hours, field_name="timestep_hours"))
        for name in ("required_weather_field_order", "supported_sampling_modes"):
            object.__setattr__(self, name, _string_sequence(getattr(self, name), field_name=name))
        for name in (
            "training_record_summary",
            "non_thermal_electric_model",
            "cooling_demand_model",
            "shared_residual_model",
            "provenance",
        ):
            object.__setattr__(self, name, _mapping(getattr(self, name), field_name=name))
        if self.schema_version not in SUPPORTED_DEMAND_ARTIFACT_SCHEMA_VERSIONS:
            raise UnsupportedDemandArtifactVersionError(
                f"unsupported demand artifact schema_version {self.schema_version!r}"
            )
        if self.time_basis != LOCAL_CIVIL_TIME_BASIS:
            raise ValueError(
                f"time_basis must be {LOCAL_CIVIL_TIME_BASIS!r}, got {self.time_basis!r}"
            )
        if self.timestep_hours <= 0:
            raise ValueError("timestep_hours must be positive")
        _validate_timestamp(self.created_at, field_name="created_at")
        _validate_required_weather_field_order(self.required_weather_field_order)
        _validate_training_record_summary(self.training_record_summary)
        _validate_output_model(
            self.non_thermal_electric_model,
            baseline_field_name="local_step_baseline_kw",
            required_weather_field_order=self.required_weather_field_order,
            require_explicit_training_requirement=False,
        )
        _validate_output_model(
            self.cooling_demand_model,
            baseline_field_name="local_step_baseline_rt",
            required_weather_field_order=self.required_weather_field_order,
            require_explicit_training_requirement=True,
        )
        _validate_shared_residual_model(self.shared_residual_model)
        if self.double_counting_policy != SUPPORTED_DOUBLE_COUNTING_POLICY:
            raise ValueError(
                "double_counting_policy must be "
                f"{SUPPORTED_DOUBLE_COUNTING_POLICY!r}"
            )
        if not self.supported_sampling_modes:
            raise ValueError("supported_sampling_modes must not be empty")
        if "offline" not in self.supported_sampling_modes:
            raise ValueError("supported_sampling_modes must include 'offline'")
        if self.residual_day_library is not None:
            object.__setattr__(
                self,
                "residual_day_library",
                _validate_residual_day_library(
                    _mapping(self.residual_day_library, field_name="residual_day_library"),
                    intervals_per_day=int(self.shared_residual_model["intervals_per_day"]),
                ),
            )

    def to_dict(self) -> dict[str, object]:
        """Serialize the artifact into its persisted JSON shape."""

        payload = {
            "artifact_id": self.artifact_id,
            "schema_version": self.schema_version,
            "feature_name": self.feature_name,
            "created_at": self.created_at,
            "timezone_name": self.timezone_name,
            "time_basis": self.time_basis,
            "timestep_hours": self.timestep_hours,
            "required_weather_field_order": list(self.required_weather_field_order),
            "training_record_summary": dict(self.training_record_summary),
            "non_thermal_electric_model": dict(self.non_thermal_electric_model),
            "cooling_demand_model": dict(self.cooling_demand_model),
            "shared_residual_model": dict(self.shared_residual_model),
            "double_counting_policy": self.double_counting_policy,
            "provenance": dict(self.provenance),
            "supported_sampling_modes": list(self.supported_sampling_modes),
        }
        if self.residual_day_library is not None:
            payload["residual_day_library"] = dict(self.residual_day_library)
        return payload

    def write_json(self, path: str | Path) -> Path:
        """Persist the artifact as human-inspectable JSON."""

        output_path = Path(path)
        document = json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
        write_bytes_atomically(output_path, document.encode("utf-8"))
        return output_path

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DemandArtifact:
        """Construct an artifact from one decoded JSON payload."""

        required_keys = (
            "artifact_id",
            "schema_version",
            "feature_name",
            "created_at",
            "timezone_name",
            "time_basis",
            "timestep_hours",
            "required_weather_field_order",
            "training_record_summary",
            "non_thermal_electric_model",
            "cooling_demand_model",
            "shared_residual_model",
            "double_counting_policy",
            "provenance",
            "supported_sampling_modes",
        )
        _require_fields(data, required_keys, field_name="demand artifact")
        return cls(
            **{key: data[key] for key in required_keys},
            residual_day_library=data.get("residual_day_library"),
        )


def load_demand_artifact(
    source: str | Path | Mapping[str, Any],
    *,
    expected_timestep_hours: float | None = None,
) -> DemandArtifact:
    """Load and validate a persisted demand artifact."""

    raw_payload, _, _ = read_artifact_source(source, label="demand artifact", error=DemandArtifactValidationError)

    artifact = DemandArtifact.from_dict(raw_payload)
    if expected_timestep_hours is not None and artifact.timestep_hours != expected_timestep_hours:
        raise ValueError(
            "expected artifact timestep_hours "
            f"{expected_timestep_hours:g}, got {artifact.timestep_hours:g}"
        )
    return artifact


__all__ = [
    "SUPPORTED_DEMAND_ARTIFACT_SCHEMA_VERSIONS",
    "DemandArtifactValidationError",
    "UnsupportedDemandArtifactVersionError",
    "DemandArtifact",
    "load_demand_artifact",
    "validate_sampling_weather_family",
]


RESIDUAL_DAY_LIBRARY_KIND = "multiplicative-residual-days"


def _validate_residual_day_library(
    library: dict[str, object], *, intervals_per_day: int
) -> dict[str, object]:
    if library.get("model_kind") != RESIDUAL_DAY_LIBRARY_KIND:
        raise DemandArtifactValidationError(
            f"residual_day_library model_kind must be {RESIDUAL_DAY_LIBRARY_KIND!r}"
        )
    if library.get("intervals_per_day") != intervals_per_day:
        raise DemandArtifactValidationError(
            "residual_day_library intervals_per_day must match the shared residual model"
        )
    days = library.get("days")
    if not isinstance(days, Sequence) or isinstance(days, (str, bytes)) or not days:
        raise DemandArtifactValidationError("residual_day_library days must be a non-empty sequence")
    normalized = []
    for index, day in enumerate(days):
        values = _numeric_values(day, field_name=f"residual_day_library days[{index}]")
        if len(values) != intervals_per_day or any(value < 0.0 for value in values):
            raise DemandArtifactValidationError(
                "residual_day_library days must have intervals_per_day non-negative values"
            )
        normalized.append(list(values))
    return {**library, "days": normalized}


def _validate_required_weather_field_order(required_weather_field_order: Sequence[str]) -> None:
    canonical_fields = CANONICAL_WEATHER_FIELD_ORDER[1:]
    if not required_weather_field_order:
        raise ValueError("required_weather_field_order must not be empty")
    if any(field_name not in canonical_fields for field_name in required_weather_field_order):
        raise ValueError(
            "required_weather_field_order must be a subset of canonical weather fields"
        )
    if len(set(required_weather_field_order)) != len(tuple(required_weather_field_order)):
        raise ValueError("required_weather_field_order must not contain duplicates")


def _validate_training_record_summary(training_record_summary: Mapping[str, object]) -> None:
    required_keys = (
        "dataset_id",
        "record_count",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "local_step_count",
    )
    missing = [key for key in required_keys if key not in training_record_summary]
    if missing:
        raise ValueError(
            "training_record_summary is missing required keys: " + ", ".join(missing)
        )

    if _positive_int(training_record_summary["record_count"], field_name="record_count") <= 0:
        raise ValueError("record_count must be positive")
    if _positive_int(training_record_summary["local_step_count"], field_name="local_step_count") <= 0:
        raise ValueError("local_step_count must be positive")
    _validate_timestamp(
        training_record_summary["first_timestamp_utc"],
        field_name="first_timestamp_utc",
    )
    _validate_timestamp(
        training_record_summary["last_timestamp_utc"],
        field_name="last_timestamp_utc",
    )


def _validate_output_model(
    output_model: Mapping[str, object],
    *,
    baseline_field_name: str,
    required_weather_field_order: Sequence[str],
    require_explicit_training_requirement: bool,
) -> None:
    required_keys = (
        "model_kind",
        baseline_field_name,
        "weather_response_terms",
        "training_day_count",
        "residual_scale_summary",
        "supported_weather_drivers",
    )
    if require_explicit_training_requirement:
        required_keys = required_keys + ("explicit_training_requirement",)

    missing = [key for key in required_keys if key not in output_model]
    if missing:
        raise ValueError(
            f"output model is missing required keys: {', '.join(missing)}"
        )

    baseline = _numeric_values(output_model[baseline_field_name], field_name=baseline_field_name)
    if not baseline:
        raise ValueError(f"{baseline_field_name} must not be empty")

    weather_response_terms = output_model["weather_response_terms"]
    if not isinstance(weather_response_terms, Mapping):
        raise TypeError("weather_response_terms must be a mapping")
    if set(weather_response_terms) != set(required_weather_field_order):
        raise ValueError(
            "weather_response_terms keys must match required_weather_field_order"
        )
    for field_name, value in weather_response_terms.items():
        if field_name not in required_weather_field_order:
            raise ValueError("weather_response_terms keys must be supported weather drivers")
        _finite(value, field_name=f"weather_response_terms.{field_name}")

    supported_weather_drivers = _string_sequence(
        output_model["supported_weather_drivers"],
        field_name="supported_weather_drivers",
    )
    if supported_weather_drivers != tuple(required_weather_field_order):
        raise ValueError(
            "supported_weather_drivers must match required_weather_field_order"
        )

    if _positive_int(
        output_model["training_day_count"],
        field_name="training_day_count",
    ) <= 0:
        raise ValueError("training_day_count must be positive")

    residual_scale_summary = output_model["residual_scale_summary"]
    if not isinstance(residual_scale_summary, Mapping) or not residual_scale_summary:
        raise ValueError("residual_scale_summary must be a non-empty mapping")
    for metric_name, metric_value in residual_scale_summary.items():
        _finite(metric_value, field_name=f"residual_scale_summary.{metric_name}")

    if require_explicit_training_requirement:
        explicit_training_requirement = _non_empty(
            output_model["explicit_training_requirement"],
            field_name="explicit_training_requirement",
        )
        if explicit_training_requirement != "historical_cooling_demand_rt_required":
            raise ValueError(
                "cooling demand model explicit_training_requirement must be "
                "'historical_cooling_demand_rt_required'"
            )


def _validate_shared_residual_model(shared_residual_model: Mapping[str, object]) -> None:
    required_keys = (
        "model_kind",
        "intervals_per_day",
        "output_order",
        "joint_residual_summary",
        "correlation_matrix",
        "sampling_notes",
    )
    missing = [key for key in required_keys if key not in shared_residual_model]
    if missing:
        raise ValueError(
            "shared_residual_model is missing required keys: " + ", ".join(missing)
        )

    output_order = _string_sequence(
        shared_residual_model["output_order"],
        field_name="output_order",
    )
    if output_order != EXPECTED_OUTPUT_ORDER:
        raise ValueError(
            "shared_residual_model output_order must match the first-release output pair"
        )

    intervals_per_day = _positive_int(
        shared_residual_model["intervals_per_day"],
        field_name="intervals_per_day",
    )
    if intervals_per_day <= 0:
        raise ValueError("intervals_per_day must be positive")

    joint_residual_summary = shared_residual_model["joint_residual_summary"]
    if not isinstance(joint_residual_summary, Mapping):
        raise TypeError("joint_residual_summary must be a mapping")
    required_summary_keys = ("training_day_count", "output_count")
    missing_summary_keys = [
        key for key in required_summary_keys if key not in joint_residual_summary
    ]
    if missing_summary_keys:
        raise ValueError(
            "joint_residual_summary is missing required keys: "
            + ", ".join(missing_summary_keys)
        )
    if _positive_int(
        joint_residual_summary["training_day_count"],
        field_name="training_day_count",
    ) <= 0:
        raise ValueError("training_day_count must be positive")
    if _positive_int(
        joint_residual_summary["output_count"],
        field_name="output_count",
    ) != len(output_order):
        raise ValueError("output_count must align with output_order length")

    correlation_matrix = shared_residual_model["correlation_matrix"]
    if isinstance(correlation_matrix, str) or not isinstance(correlation_matrix, Sequence):
        raise TypeError("correlation_matrix must be a numeric matrix")
    if len(correlation_matrix) != len(output_order):
        raise ValueError("correlation_matrix row count must match output_order")
    for row_index, row in enumerate(correlation_matrix):
        if isinstance(row, str) or not isinstance(row, Sequence):
            raise TypeError("correlation_matrix rows must be sequences")
        if len(row) != len(output_order):
            raise ValueError("correlation_matrix must be square")
        for column_index, value in enumerate(row):
            numeric_value = _finite(value, field_name=f"correlation_matrix[{row_index}][{column_index}]")
            if row_index == column_index and numeric_value != 1.0:
                raise ValueError("correlation_matrix diagonal entries must equal 1.0")


_validate_timestamp = partial(utc_timestamp_text, error=DemandArtifactValidationError)
_positive_int = partial(positive_int, error=DemandArtifactValidationError)
_finite = partial(finite, error=DemandArtifactValidationError)
_non_empty = partial(non_empty_str, error=DemandArtifactValidationError)
_mapping = partial(mapping, error=DemandArtifactValidationError)
_require_fields = partial(require_fields, error=DemandArtifactValidationError)


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    items = tuple(
        _non_empty(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(sequence(value, field_name=field_name, error=DemandArtifactValidationError))
    )
    if not items:
        raise DemandArtifactValidationError(f"{field_name} must not be empty")
    if len(set(items)) != len(items):
        raise DemandArtifactValidationError(f"{field_name} must not contain duplicates")
    return items


def _numeric_values(value: object, *, field_name: str) -> tuple[float, ...]:
    items = tuple(
        _finite(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(sequence(value, field_name=field_name, error=DemandArtifactValidationError))
    )
    if not items:
        raise DemandArtifactValidationError(f"{field_name} must not be empty")
    return items


def validate_sampling_weather_family(
    artifact: DemandArtifact,
    weather_family: object,
    *,
    expected_num_steps: int,
    expected_scenario_count: int,
    paired_family_seed: int,
) -> tuple[object, ...]:
    """Validate one weather family against the demand artifact sampling contract."""

    family_timestep_hours = float(getattr(weather_family, "timestep_hours"))
    if family_timestep_hours != artifact.timestep_hours:
        raise ValueError(
            "weather family timestep_hours must match artifact timestep_hours"
        )

    family_num_steps = int(getattr(weather_family, "num_steps"))
    if family_num_steps != expected_num_steps:
        raise ValueError("weather family num_steps must match demand sampling request")

    family_scenario_count = int(getattr(weather_family, "scenario_count"))
    if family_scenario_count != expected_scenario_count:
        raise ValueError(
            "weather family scenario_count must match demand sampling request"
        )

    family_seed = int(getattr(weather_family, "family_seed"))
    if family_seed != paired_family_seed:
        raise ValueError("weather family seed must match paired_family_seed")

    sampled_traces = getattr(weather_family, "sampled_traces")
    if not isinstance(sampled_traces, Sequence) or isinstance(sampled_traces, str):
        raise TypeError("weather_family.sampled_traces must be a sequence")
    if len(sampled_traces) != expected_scenario_count:
        raise ValueError(
            "weather_family.sampled_traces length must match scenario_count"
        )

    required_fields = set(artifact.required_weather_field_order)
    normalized_traces: list[object] = []
    expected_start = int(getattr(weather_family, "scenario_index_start", 0))
    for position, trace in enumerate(sampled_traces):
        trace_index = int(getattr(trace, "scenario_index"))
        if trace_index != expected_start + position:
            raise ValueError("weather family scenario ordering must be contiguous")

        trace_timestep_hours = float(getattr(trace, "timestep_hours"))
        if trace_timestep_hours != artifact.timestep_hours:
            raise ValueError(
                "weather trace timestep_hours must match artifact timestep_hours"
            )

        timestamp_utc = tuple(getattr(trace, "timestamp_utc"))
        if len(timestamp_utc) != expected_num_steps:
            raise ValueError("weather trace timestamp_utc length must match num_steps")

        canonical_field_series = getattr(trace, "canonical_field_series")
        if not isinstance(canonical_field_series, Mapping):
            raise TypeError("weather trace canonical_field_series must be a mapping")

        missing_fields = required_fields.difference(canonical_field_series)
        if missing_fields:
            missing_list = ", ".join(sorted(missing_fields))
            raise ValueError(
                "weather trace is missing required weather fields: "
                f"{missing_list}"
            )

        for field_name in artifact.required_weather_field_order:
            field_series = canonical_field_series[field_name]
            if isinstance(field_series, str) or not isinstance(field_series, Sequence):
                raise TypeError(
                    f"weather field {field_name!r} must be a numeric sequence"
                )
            if len(field_series) != expected_num_steps:
                raise ValueError(
                    f"weather field {field_name!r} length must match num_steps"
                )
            for value in field_series:
                float(value)

        normalized_traces.append(trace)

    return tuple(normalized_traces)


