"""Canonical weather schema and normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from math import isclose
from zoneinfo import ZoneInfo

from open_energy_lab.simulator._weather_schema import (
    iter_weather_field_specs,
)


CANONICAL_WEATHER_FIELD_ORDER = tuple(
    spec.field_name for spec in iter_weather_field_specs()
)
LOCAL_CIVIL_TIME_BASIS = "local_civil_time"
SOURCE_FIELD_LABELS = {
    spec.field_name: spec.tmy_label for spec in iter_weather_field_specs()
}


class MissingCanonicalWeatherFieldError(ValueError):
    """Raised when a provider payload omits a required canonical field."""


@dataclass(frozen=True, slots=True)
class CanonicalWeatherDataset:
    """Normalized canonical weather dataset used by the fit workflow."""

    dataset_id: str
    latitude: float
    longitude: float
    source_name: str
    source_metadata: dict[str, object]
    timezone_name: str
    time_basis: str
    timestep_hours: float
    timestamp_utc: tuple[str, ...]
    local_civil_step_labels: tuple[str, ...]
    canonical_field_order: tuple[str, ...]
    field_series: dict[str, tuple[object, ...]]
    source_field_labels: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.time_basis != LOCAL_CIVIL_TIME_BASIS:
            raise ValueError(
                f"time_basis must be {LOCAL_CIVIL_TIME_BASIS!r}, got {self.time_basis!r}"
            )
        if self.canonical_field_order != CANONICAL_WEATHER_FIELD_ORDER:
            raise ValueError("canonical_field_order must match the first-release canonical schema")
        if self.timestep_hours <= 0:
            raise ValueError("timestep_hours must be positive")
        if not self.timestamp_utc:
            raise ValueError("timestamp_utc must not be empty")
        if len(self.timestamp_utc) != len(self.local_civil_step_labels):
            raise ValueError("timestamp_utc and local_civil_step_labels must align")
        if set(self.field_series) != set(self.canonical_field_order):
            raise ValueError("field_series must cover the full canonical field set")

        expected_length = len(self.timestamp_utc)
        for field_name in self.canonical_field_order:
            if len(self.field_series[field_name]) != expected_length:
                raise ValueError(
                    f"field_series[{field_name!r}] length must match timestamp_utc"
                )
        if set(self.source_field_labels) != set(self.canonical_field_order):
            raise ValueError("source_field_labels must cover the full canonical field set")


def normalize_recorded_tmy_response(
    response: Mapping[str, object],
    *,
    latitude: float,
    longitude: float,
    timezone_name: str,
    source_name: str = "PVGIS TMY",
    timestep_hours: float | None = None,
    dataset_id: str | None = None,
) -> CanonicalWeatherDataset:
    """Normalize one recorded provider response into the canonical schema."""

    records_raw = response.get("records")
    if not isinstance(records_raw, list) or not records_raw:
        raise ValueError("TMY response must contain a non-empty 'records' list")

    records: list[Mapping[str, object]] = []
    for index, record in enumerate(records_raw):
        if not isinstance(record, Mapping):
            raise TypeError(f"TMY record at index {index} must be a mapping")
        records.append(record)

    canonical_timestamps = tuple(
        _normalize_utc_timestamp(_coerce_timestamp(records, "timestamp_utc", index))
        for index in range(len(records))
    )
    derived_timestep_hours = _derive_timestep_hours(canonical_timestamps)
    effective_timestep = timestep_hours if timestep_hours is not None else derived_timestep_hours
    if derived_timestep_hours is not None and not isclose(
        effective_timestep,
        derived_timestep_hours,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "requested timestep_hours does not match the recorded provider timestamps"
        )

    local_civil_step_labels = tuple(
        _local_civil_label(timestamp_text, timezone_name)
        for timestamp_text in canonical_timestamps
    )

    field_series: dict[str, tuple[object, ...]] = {"timestamp_utc": canonical_timestamps}
    for field_name in CANONICAL_WEATHER_FIELD_ORDER[1:]:
        label = SOURCE_FIELD_LABELS[field_name]
        values = tuple(
            _coerce_float(records, label, index)
            for index in range(len(records))
        )
        field_series[field_name] = values

    source_metadata = response.get("source_metadata", {})
    if not isinstance(source_metadata, Mapping):
        raise TypeError("source_metadata must be a mapping when provided")

    effective_dataset_id = dataset_id or str(
        response.get(
            "dataset_id",
            f"{source_name.lower().replace(' ', '-')}"
            f":{latitude:.6f}:{longitude:.6f}:{effective_timestep:g}",
        )
    )

    return CanonicalWeatherDataset(
        dataset_id=effective_dataset_id,
        latitude=latitude,
        longitude=longitude,
        source_name=source_name,
        source_metadata=dict(source_metadata),
        timezone_name=timezone_name,
        time_basis=LOCAL_CIVIL_TIME_BASIS,
        timestep_hours=effective_timestep,
        timestamp_utc=canonical_timestamps,
        local_civil_step_labels=local_civil_step_labels,
        canonical_field_order=CANONICAL_WEATHER_FIELD_ORDER,
        field_series=field_series,
        source_field_labels=dict(SOURCE_FIELD_LABELS),
    )


def _coerce_timestamp(
    records: list[Mapping[str, object]],
    field_name: str,
    index: int,
) -> str:
    label = SOURCE_FIELD_LABELS[field_name]
    if label not in records[index]:
        raise MissingCanonicalWeatherFieldError(
            f"provider record is missing canonical field {field_name!r} mapped from {label!r}"
        )
    value = records[index][label]
    if not isinstance(value, str):
        raise TypeError(f"provider field {label!r} must be a string timestamp")
    return value


def _coerce_float(
    records: list[Mapping[str, object]],
    label: str,
    index: int,
) -> float:
    if label not in records[index]:
        field_name = next(
            canonical_name
            for canonical_name, source_label in SOURCE_FIELD_LABELS.items()
            if source_label == label
        )
        raise MissingCanonicalWeatherFieldError(
            f"provider record is missing canonical field {field_name!r} mapped from {label!r}"
        )
    return float(records[index][label])


def _normalize_utc_timestamp(timestamp_text: str) -> str:
    timestamp = _parse_utc_timestamp(timestamp_text)
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc_timestamp(timestamp_text: str) -> datetime:
    normalized = timestamp_text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp_utc values must be timezone-aware UTC timestamps")
    return parsed.astimezone(ZoneInfo("UTC"))


def _derive_timestep_hours(
    timestamp_utc: tuple[str, ...],
) -> float | None:
    if len(timestamp_utc) < 2:
        return None
    first = _parse_utc_timestamp(timestamp_utc[0])
    second = _parse_utc_timestamp(timestamp_utc[1])
    return (second - first).total_seconds() / 3600.0


def _local_civil_label(timestamp_text: str, timezone_name: str) -> str:
    return _parse_utc_timestamp(timestamp_text).astimezone(
        ZoneInfo(timezone_name)
    ).isoformat()

__all__ = [
    "CANONICAL_WEATHER_FIELD_ORDER",
    "CanonicalWeatherDataset",
    "LOCAL_CIVIL_TIME_BASIS",
    "MissingCanonicalWeatherFieldError",
    "SOURCE_FIELD_LABELS",
    "normalize_recorded_tmy_response",
]
