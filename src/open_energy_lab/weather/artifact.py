"""Artifact schema and loading helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._canonical import CANONICAL_WEATHER_FIELD_ORDER, LOCAL_CIVIL_TIME_BASIS

if TYPE_CHECKING:
    from .sampling import WeatherSamplingRequest, WeatherScenarioFamily


SUPPORTED_ARTIFACT_SCHEMA_VERSIONS = ("v1",)
_IRRADIANCE_FIELDS = {
    "global_horizontal_irradiance_w_per_m2",
    "direct_beam_irradiance_w_per_m2",
    "diffuse_horizontal_irradiance_w_per_m2",
}


class UnsupportedWeatherArtifactVersionError(ValueError):
    """Raised when artifact loading sees an unsupported schema version."""


@dataclass(frozen=True, slots=True)
class WeatherArtifact:
    """Import-light persisted weather artifact."""

    artifact_id: str
    schema_version: str
    feature_name: str
    created_at: str
    latitude: float
    longitude: float
    timezone_name: str
    time_basis: str
    timestep_hours: float
    canonical_field_order: tuple[str, ...]
    training_record_summary: dict[str, object]
    base_model_kind: str
    base_model_parameters: dict[str, object]
    cloud_event_model: dict[str, object]
    provenance: dict[str, object]
    supported_load_modes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_ARTIFACT_SCHEMA_VERSIONS:
            raise UnsupportedWeatherArtifactVersionError(
                f"unsupported weather artifact schema_version {self.schema_version!r}"
            )
        if self.time_basis != LOCAL_CIVIL_TIME_BASIS:
            raise ValueError(
                f"time_basis must be {LOCAL_CIVIL_TIME_BASIS!r}, got {self.time_basis!r}"
            )
        if self.canonical_field_order != CANONICAL_WEATHER_FIELD_ORDER:
            raise ValueError("canonical_field_order must match the first-release canonical schema")
        if self.timestep_hours <= 0:
            raise ValueError("timestep_hours must be positive")
        if not self.supported_load_modes:
            raise ValueError("supported_load_modes must not be empty")
        if "offline" not in self.supported_load_modes:
            raise ValueError("supported_load_modes must include 'offline'")
        _validate_training_record_summary(self.training_record_summary)
        _validate_base_model_parameters(
            self.base_model_parameters,
            canonical_field_order=self.canonical_field_order,
        )
        _validate_cloud_event_model(
            self.cloud_event_model,
            intervals_per_day=_positive_int(
                self.base_model_parameters.get("intervals_per_day"),
                field_name="intervals_per_day",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the artifact into its persisted JSON shape."""

        return {
            "artifact_id": self.artifact_id,
            "schema_version": self.schema_version,
            "feature_name": self.feature_name,
            "created_at": self.created_at,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone_name": self.timezone_name,
            "time_basis": self.time_basis,
            "timestep_hours": self.timestep_hours,
            "canonical_field_order": list(self.canonical_field_order),
            "training_record_summary": self.training_record_summary,
            "base_model_kind": self.base_model_kind,
            "base_model_parameters": self.base_model_parameters,
            "cloud_event_model": self.cloud_event_model,
            "provenance": self.provenance,
            "supported_load_modes": list(self.supported_load_modes),
        }

    def write_json(self, path: str | Path) -> Path:
        """Persist the artifact as human-inspectable JSON."""

        output_path = Path(path)
        output_path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output_path

    def sample_family(
        self,
        *,
        request: WeatherSamplingRequest,
        expected_timestep_hours: float | None = None,
    ) -> WeatherScenarioFamily:
        """Sample one offline weather family from this loaded artifact."""

        from .sampling import sample_weather_family

        return sample_weather_family(
            self.to_dict(),
            request=request,
            expected_timestep_hours=expected_timestep_hours,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WeatherArtifact:
        """Construct an artifact from one decoded JSON payload."""

        required_keys = (
            "artifact_id",
            "schema_version",
            "feature_name",
            "created_at",
            "latitude",
            "longitude",
            "timezone_name",
            "time_basis",
            "timestep_hours",
            "canonical_field_order",
            "training_record_summary",
            "base_model_kind",
            "base_model_parameters",
            "cloud_event_model",
            "provenance",
            "supported_load_modes",
        )
        missing = [key for key in required_keys if key not in data]
        if missing:
            raise ValueError(f"weather artifact is missing required keys: {', '.join(missing)}")

        return cls(
            artifact_id=str(data["artifact_id"]),
            schema_version=str(data["schema_version"]),
            feature_name=str(data["feature_name"]),
            created_at=str(data["created_at"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            timezone_name=str(data["timezone_name"]),
            time_basis=str(data["time_basis"]),
            timestep_hours=float(data["timestep_hours"]),
            canonical_field_order=tuple(data["canonical_field_order"]),
            training_record_summary=dict(data["training_record_summary"]),
            base_model_kind=str(data["base_model_kind"]),
            base_model_parameters=dict(data["base_model_parameters"]),
            cloud_event_model=dict(data["cloud_event_model"]),
            provenance=dict(data["provenance"]),
            supported_load_modes=tuple(data["supported_load_modes"]),
        )


def load_weather_artifact(
    source: str | Path | Mapping[str, Any],
    *,
    expected_timestep_hours: float | None = None,
) -> WeatherArtifact:
    """Load and validate a persisted weather artifact."""

    if isinstance(source, Mapping):
        raw_payload = source
    else:
        raw_payload = json.loads(Path(source).read_text(encoding="utf-8"))

    artifact = WeatherArtifact.from_dict(raw_payload)
    if expected_timestep_hours is not None and artifact.timestep_hours != expected_timestep_hours:
        raise ValueError(
            "expected artifact timestep_hours "
            f"{expected_timestep_hours:g}, got {artifact.timestep_hours:g}"
        )
    return artifact


__all__ = [
    "SUPPORTED_ARTIFACT_SCHEMA_VERSIONS",
    "UnsupportedWeatherArtifactVersionError",
    "WeatherArtifact",
    "load_weather_artifact",
]


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
            "training_record_summary is missing required keys: "
            + ", ".join(missing)
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


def _validate_base_model_parameters(
    base_model_parameters: Mapping[str, object],
    *,
    canonical_field_order: Sequence[str],
) -> None:
    required_keys = (
        "intervals_per_day",
        "field_order",
        "mean_vector",
        "covariance_matrix",
        "physical_bounds_policy",
    )
    missing = [key for key in required_keys if key not in base_model_parameters]
    if missing:
        raise ValueError(
            "base_model_parameters is missing required keys: " + ", ".join(missing)
        )

    intervals_per_day = _positive_int(
        base_model_parameters["intervals_per_day"],
        field_name="intervals_per_day",
    )
    field_order = _string_sequence(
        base_model_parameters["field_order"],
        field_name="field_order",
    )
    if tuple(field_order) != tuple(canonical_field_order[1:]):
        raise ValueError(
            "base_model_parameters field_order must match canonical_field_order without timestamp_utc"
        )

    mean_vector = _numeric_vector(
        base_model_parameters["mean_vector"],
        field_name="mean_vector",
    )
    expected_size = intervals_per_day * len(field_order)
    if len(mean_vector) != expected_size:
        raise ValueError(
            "base_model_parameters mean_vector length must equal "
            "intervals_per_day * len(field_order)"
        )

    covariance_matrix = _covariance_matrix(
        base_model_parameters["covariance_matrix"],
        expected_size=expected_size,
    )
    if len(covariance_matrix) != expected_size:
        raise ValueError("covariance_matrix row count must match mean_vector length")

    _validate_physical_bounds_policy(
        base_model_parameters["physical_bounds_policy"],
        field_order=field_order,
    )


def _validate_cloud_event_model(
    cloud_event_model: Mapping[str, object],
    *,
    intervals_per_day: int,
) -> None:
    required_keys = (
        "irradiance_fields",
        "start_probability_by_local_step",
        "duration_distribution",
        "attenuation_distribution",
        "minimum_base_irradiance_w_per_m2",
        "calibration_summary",
    )
    missing = [key for key in required_keys if key not in cloud_event_model]
    if missing:
        raise ValueError("cloud_event_model is missing required keys: " + ", ".join(missing))

    irradiance_fields = _string_sequence(
        cloud_event_model["irradiance_fields"],
        field_name="irradiance_fields",
    )
    if not set(irradiance_fields).issubset(_IRRADIANCE_FIELDS):
        raise ValueError("cloud_event_model irradiance_fields must be a subset of the canonical irradiance fields")

    probabilities = _numeric_vector(
        cloud_event_model["start_probability_by_local_step"],
        field_name="start_probability_by_local_step",
    )
    if len(probabilities) != intervals_per_day:
        raise ValueError(
            "cloud_event_model start_probability_by_local_step must align with intervals_per_day"
        )

    _validate_empirical_distribution(
        cloud_event_model["duration_distribution"],
        value_key="durations",
        probability_key="probabilities",
        field_name="duration_distribution",
    )
    _validate_empirical_distribution(
        cloud_event_model["attenuation_distribution"],
        value_key="attenuation_values",
        probability_key="probabilities",
        field_name="attenuation_distribution",
    )


def _validate_physical_bounds_policy(
    physical_bounds_policy: object,
    *,
    field_order: Sequence[str],
) -> None:
    if not isinstance(physical_bounds_policy, Mapping):
        raise ValueError("base_model_parameters must include physical_bounds_policy")

    bounds_by_field = physical_bounds_policy.get("bounds_by_field")
    if not isinstance(bounds_by_field, Mapping):
        raise ValueError("physical_bounds_policy must include bounds_by_field")

    missing_fields = [field_name for field_name in field_order if field_name not in bounds_by_field]
    if missing_fields:
        raise ValueError(
            "physical_bounds_policy bounds_by_field is missing canonical fields: "
            + ", ".join(missing_fields)
        )


def _validate_empirical_distribution(
    value: object,
    *,
    value_key: str,
    probability_key: str,
    field_name: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")

    values = _numeric_vector(value.get(value_key), field_name=f"{field_name}.{value_key}")
    probabilities = _numeric_vector(
        value.get(probability_key),
        field_name=f"{field_name}.{probability_key}",
    )
    if len(values) != len(probabilities):
        raise ValueError(
            f"{field_name} {value_key} and {probability_key} must have matching lengths"
        )


def _validate_timestamp(value: object, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO 8601 UTC timestamp string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO 8601 UTC timestamp string") from exc


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name} must be a positive integer")
    integer_value = int(value)
    if integer_value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return integer_value


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence")
    return tuple(str(item) for item in value)


def _numeric_vector(value: object, *, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a numeric sequence")
    return tuple(float(item) for item in value)


def _covariance_matrix(
    value: object,
    *,
    expected_size: int,
) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("covariance_matrix must be a square numeric sequence")

    rows: list[tuple[float, ...]] = []
    for row in value:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes, bytearray)):
            raise ValueError("covariance_matrix rows must be numeric sequences")
        rows.append(tuple(float(item) for item in row))

    if len(rows) != expected_size:
        raise ValueError("covariance_matrix row count must match mean_vector length")
    if any(len(row) != expected_size for row in rows):
        raise ValueError("covariance_matrix must be square with mean_vector-aligned dimensions")
    return tuple(rows)
