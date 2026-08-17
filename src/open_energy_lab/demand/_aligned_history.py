"""Aligned demand-history normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isclose
from zoneinfo import ZoneInfo

from open_energy_lab.weather._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    LOCAL_CIVIL_TIME_BASIS,
)


@dataclass(frozen=True, slots=True)
class AlignedTrainingHistory:
    """Validated aligned weather and demand history used by demand fitting."""

    dataset_id: str
    timezone_name: str
    time_basis: str
    timestep_hours: float
    timestamp_utc: tuple[str, ...]
    local_civil_step_labels: tuple[str, ...]
    canonical_weather_fields: tuple[str, ...]
    weather_field_series: dict[str, tuple[float, ...]]
    non_thermal_electric_demand_kw: tuple[float, ...]
    cooling_demand_rt: tuple[float, ...]
    provenance: dict[str, object]

    def __post_init__(self) -> None:
        if self.time_basis != LOCAL_CIVIL_TIME_BASIS:
            raise ValueError(
                f"time_basis must be {LOCAL_CIVIL_TIME_BASIS!r}, got {self.time_basis!r}"
            )
        if self.timestep_hours <= 0:
            raise ValueError("timestep_hours must be positive")
        if not self.timestamp_utc:
            raise ValueError("timestamp_utc must not be empty")
        if len(self.timestamp_utc) != len(self.local_civil_step_labels):
            raise ValueError("timestamp_utc and local_civil_step_labels must align")
        if not self.canonical_weather_fields:
            raise ValueError("canonical_weather_fields must not be empty")
        if tuple(self.weather_field_series) != self.canonical_weather_fields:
            raise ValueError(
                "weather_field_series keys must match canonical_weather_fields in order"
            )

        expected_fields = CANONICAL_WEATHER_FIELD_ORDER[1:]
        if any(field not in expected_fields for field in self.canonical_weather_fields):
            raise ValueError("canonical_weather_fields must use canonical weather field names")
        if tuple(
            field for field in expected_fields if field in self.canonical_weather_fields
        ) != self.canonical_weather_fields:
            raise ValueError(
                "canonical_weather_fields must preserve canonical weather field order"
            )

        utc_timestamps = tuple(_parse_utc_timestamp(value) for value in self.timestamp_utc)
        derived_timestep_hours = _derive_regular_timestep_hours(
            utc_timestamps,
            field_name="timestamp_utc",
        )
        if derived_timestep_hours is not None and not isclose(
            derived_timestep_hours,
            self.timestep_hours,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "timestamp_utc values do not align with the declared timestep_hours"
            )

        zone = ZoneInfo(self.timezone_name)
        normalized_local_labels = tuple(
            _parse_local_timestamp(value, field_name="local_civil_step_labels")
            .astimezone(zone)
            .isoformat()
            for value in self.local_civil_step_labels
        )
        expected_local_labels = tuple(
            timestamp.astimezone(zone).isoformat() for timestamp in utc_timestamps
        )
        if normalized_local_labels != expected_local_labels:
            raise ValueError(
                "local_civil_step_labels must align with timestamp_utc in the declared timezone"
            )

        expected_length = len(self.timestamp_utc)
        for field_name, values in self.weather_field_series.items():
            if len(values) != expected_length:
                raise ValueError(
                    f"weather_field_series[{field_name!r}] length must match timestamp_utc"
                )
        if len(self.non_thermal_electric_demand_kw) != expected_length:
            raise ValueError(
                "non_thermal_electric_demand_kw length must match timestamp_utc"
            )
        if len(self.cooling_demand_rt) != expected_length:
            raise ValueError("cooling_demand_rt length must match timestamp_utc")

    @property
    def record_count(self) -> int:
        """Return the number of aligned training records."""

        return len(self.timestamp_utc)

    def to_dict(self) -> dict[str, object]:
        """Serialize the aligned training history into a JSON-friendly mapping."""

        return {
            "dataset_id": self.dataset_id,
            "timezone_name": self.timezone_name,
            "time_basis": self.time_basis,
            "timestep_hours": self.timestep_hours,
            "timestamp_utc": list(self.timestamp_utc),
            "local_civil_step_labels": list(self.local_civil_step_labels),
            "canonical_weather_fields": list(self.canonical_weather_fields),
            "weather_field_series": {
                field_name: list(values)
                for field_name, values in self.weather_field_series.items()
            },
            "non_thermal_electric_demand_kw": list(self.non_thermal_electric_demand_kw),
            "cooling_demand_rt": list(self.cooling_demand_rt),
            "provenance": dict(self.provenance),
        }


def normalize_aligned_training_history(
    payload: Mapping[str, object],
) -> AlignedTrainingHistory:
    """Normalize one aligned weather-plus-demand training payload."""

    required_keys = (
        "dataset_id",
        "timezone_name",
        "time_basis",
        "timestep_hours",
        "timestamp_utc",
        "local_civil_step_labels",
        "canonical_weather_fields",
        "weather_field_series",
        "non_thermal_electric_demand_kw",
        "cooling_demand_rt",
        "provenance",
    )
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(
            "aligned training history is missing required keys: " + ", ".join(missing)
        )

    if "total_electric_demand_kw" in payload:
        raise ValueError(
            "total_electric_demand_kw is not supported because it can double count "
            "cooling demand"
        )

    canonical_weather_fields = _string_sequence(
        payload["canonical_weather_fields"],
        field_name="canonical_weather_fields",
    )
    raw_weather_field_series = payload["weather_field_series"]
    if not isinstance(raw_weather_field_series, Mapping):
        raise TypeError("weather_field_series must be a mapping")

    missing_weather_fields = [
        field_name
        for field_name in canonical_weather_fields
        if field_name not in raw_weather_field_series
    ]
    if missing_weather_fields:
        raise ValueError(
            "weather_field_series is missing required canonical fields: "
            + ", ".join(missing_weather_fields)
        )

    unexpected_weather_fields = [
        field_name
        for field_name in raw_weather_field_series
        if field_name not in canonical_weather_fields
    ]
    if unexpected_weather_fields:
        raise ValueError(
            "weather_field_series contains unexpected canonical fields: "
            + ", ".join(str(field_name) for field_name in unexpected_weather_fields)
        )

    normalized_weather_field_series = {
        field_name: _numeric_sequence(
            raw_weather_field_series[field_name],
            field_name=f"weather_field_series[{field_name!r}]",
        )
        for field_name in canonical_weather_fields
    }

    provenance = payload["provenance"]
    if not isinstance(provenance, Mapping):
        raise TypeError("provenance must be a mapping")

    return AlignedTrainingHistory(
        dataset_id=str(payload["dataset_id"]),
        timezone_name=str(payload["timezone_name"]),
        time_basis=str(payload["time_basis"]),
        timestep_hours=float(payload["timestep_hours"]),
        timestamp_utc=_timestamp_sequence(payload["timestamp_utc"], field_name="timestamp_utc"),
        local_civil_step_labels=_timestamp_sequence(
            payload["local_civil_step_labels"],
            field_name="local_civil_step_labels",
        ),
        canonical_weather_fields=canonical_weather_fields,
        weather_field_series=normalized_weather_field_series,
        non_thermal_electric_demand_kw=_numeric_sequence(
            payload["non_thermal_electric_demand_kw"],
            field_name="non_thermal_electric_demand_kw",
        ),
        cooling_demand_rt=_numeric_sequence(
            payload["cooling_demand_rt"],
            field_name="cooling_demand_rt",
        ),
        provenance=dict(provenance),
    )


__all__ = ["AlignedTrainingHistory", "normalize_aligned_training_history"]


def _timestamp_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of ISO timestamps")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise TypeError(f"{field_name}[{index}] must be a string timestamp")
        normalized.append(item)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return tuple(normalized)


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise TypeError(f"{field_name}[{index}] must be a string")
        normalized.append(item)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicates")
    return tuple(normalized)


def _numeric_sequence(value: object, *, field_name: str) -> tuple[float, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of numeric values")
    normalized = tuple(float(item) for item in value)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _parse_utc_timestamp(timestamp_text: str) -> datetime:
    parsed = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_utc values must be timezone-aware UTC timestamps")
    return parsed.astimezone(ZoneInfo("UTC"))


def _parse_local_timestamp(timestamp_text: str, *, field_name: str) -> datetime:
    parsed = datetime.fromisoformat(timestamp_text)
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} values must be timezone-aware timestamps")
    return parsed


def _derive_regular_timestep_hours(
    timestamps: tuple[datetime, ...],
    *,
    field_name: str,
) -> float | None:
    if len(timestamps) < 2:
        return None

    timestep_hours = (timestamps[1] - timestamps[0]).total_seconds() / 3600.0
    if timestep_hours <= 0:
        raise ValueError(f"{field_name} values must be strictly increasing")

    for previous, current in zip(timestamps, timestamps[1:]):
        delta_hours = (current - previous).total_seconds() / 3600.0
        if not isclose(delta_hours, timestep_hours, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"{field_name} values must use one regular timestep")
    return timestep_hours
