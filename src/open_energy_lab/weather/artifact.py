"""Artifact schema and loading helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._canonical import CANONICAL_WEATHER_FIELD_ORDER, LOCAL_CIVIL_TIME_BASIS


SUPPORTED_ARTIFACT_SCHEMA_VERSIONS = ("v1",)


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
        if "intervals_per_day" not in self.base_model_parameters:
            raise ValueError("base_model_parameters must include intervals_per_day")
        if "field_order" not in self.base_model_parameters:
            raise ValueError("base_model_parameters must include field_order")
        if "mean_vector" not in self.base_model_parameters:
            raise ValueError("base_model_parameters must include mean_vector")
        if "covariance_matrix" not in self.base_model_parameters:
            raise ValueError("base_model_parameters must include covariance_matrix")
        if "irradiance_fields" not in self.cloud_event_model:
            raise ValueError("cloud_event_model must include irradiance_fields")
        if "start_probability_by_local_step" not in self.cloud_event_model:
            raise ValueError(
                "cloud_event_model must include start_probability_by_local_step"
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
