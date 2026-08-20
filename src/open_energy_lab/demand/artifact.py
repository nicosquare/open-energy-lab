"""Persisted demand-artifact loading helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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


class UnsupportedDemandArtifactVersionError(ValueError):
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

    def __post_init__(self) -> None:
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

    def to_dict(self) -> dict[str, object]:
        """Serialize the artifact into its persisted JSON shape."""

        return {
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

    def write_json(self, path: str | Path) -> Path:
        """Persist the artifact as human-inspectable JSON."""

        output_path = Path(path)
        output_path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
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
        missing = [key for key in required_keys if key not in data]
        if missing:
            raise ValueError(
                "demand artifact is missing required keys: " + ", ".join(missing)
            )

        provenance = data["provenance"]
        if not isinstance(provenance, Mapping):
            raise TypeError("provenance must be a mapping")

        return cls(
            artifact_id=str(data["artifact_id"]),
            schema_version=str(data["schema_version"]),
            feature_name=str(data["feature_name"]),
            created_at=str(data["created_at"]),
            timezone_name=str(data["timezone_name"]),
            time_basis=str(data["time_basis"]),
            timestep_hours=float(data["timestep_hours"]),
            required_weather_field_order=_string_sequence(
                data["required_weather_field_order"],
                field_name="required_weather_field_order",
            ),
            training_record_summary=dict(data["training_record_summary"]),
            non_thermal_electric_model=dict(data["non_thermal_electric_model"]),
            cooling_demand_model=dict(data["cooling_demand_model"]),
            shared_residual_model=dict(data["shared_residual_model"]),
            double_counting_policy=str(data["double_counting_policy"]),
            provenance=dict(provenance),
            supported_sampling_modes=_string_sequence(
                data["supported_sampling_modes"],
                field_name="supported_sampling_modes",
            ),
        )


def load_demand_artifact(
    source: str | Path | Mapping[str, Any],
    *,
    expected_timestep_hours: float | None = None,
) -> DemandArtifact:
    """Load and validate a persisted demand artifact."""

    if isinstance(source, Mapping):
        raw_payload = source
    else:
        raw_payload = json.loads(Path(source).read_text(encoding="utf-8"))

    artifact = DemandArtifact.from_dict(raw_payload)
    if expected_timestep_hours is not None and artifact.timestep_hours != expected_timestep_hours:
        raise ValueError(
            "expected artifact timestep_hours "
            f"{expected_timestep_hours:g}, got {artifact.timestep_hours:g}"
        )
    return artifact


__all__ = [
    "SUPPORTED_DEMAND_ARTIFACT_SCHEMA_VERSIONS",
    "UnsupportedDemandArtifactVersionError",
    "DemandArtifact",
    "load_demand_artifact",
    "validate_sampling_weather_family",
]


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

    baseline = _numeric_sequence(
        output_model[baseline_field_name],
        field_name=baseline_field_name,
    )
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
        float(value)

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
        _ = metric_name
        float(metric_value)

    if require_explicit_training_requirement:
        explicit_training_requirement = str(output_model["explicit_training_requirement"])
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
            numeric_value = float(value)
            if row_index == column_index and numeric_value != 1.0:
                raise ValueError("correlation_matrix diagonal entries must equal 1.0")


def _validate_timestamp(value: object, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be an ISO timestamp string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _positive_int(value: object, *, field_name: str) -> int:
    normalized = int(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


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


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")
    normalized = tuple(str(item) for item in value)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicates")
    return normalized


def _numeric_sequence(value: object, *, field_name: str) -> tuple[float, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of numeric values")
    normalized = tuple(float(item) for item in value)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized
