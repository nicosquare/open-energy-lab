"""Demand-input builders for configurable autonomy planning studies."""

from __future__ import annotations

import csv
import hashlib
import math
import random
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from open_energy_lab.weather._canonical import (
    CANONICAL_WEATHER_FIELD_ORDER,
    CanonicalWeatherDataset,
    LOCAL_CIVIL_TIME_BASIS,
)


DEMAND_WEATHER_FIELDS = (
    "dry_bulb_air_temperature_c",
    "global_horizontal_irradiance_w_per_m2",
    "relative_humidity_pct",
)
MEASURED_DEMAND_COLUMNS = (
    "timestamp_utc",
    *DEMAND_WEATHER_FIELDS,
    "non_thermal_electric_demand_kw",
    "cooling_demand_rt",
)


@dataclass(frozen=True, slots=True)
class SyntheticCommercialDemandConfig:
    """Explicit, illustrative small-commercial demand generator settings."""

    random_seed: int = 20260820
    non_cooling_min_kw: float = 12.0
    non_cooling_max_kw: float = 30.0
    cooling_balance_temperature_c: float = 24.0
    cooling_electric_cap_kw: float = 38.0
    electric_kw_per_rt: float = 1.15
    non_cooling_residual_sigma_kw: float = 1.2
    cooling_residual_sigma_kw: float = 2.0
    residual_correlation: float = 0.65
    residual_autocorrelation: float = 0.70

    def __post_init__(self) -> None:
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise TypeError("random_seed must be an integer")
        if self.non_cooling_min_kw <= 0.0:
            raise ValueError("non_cooling_min_kw must be positive")
        if self.non_cooling_max_kw <= self.non_cooling_min_kw:
            raise ValueError("non_cooling_max_kw must exceed non_cooling_min_kw")
        for name in (
            "cooling_electric_cap_kw",
            "electric_kw_per_rt",
            "non_cooling_residual_sigma_kw",
            "cooling_residual_sigma_kw",
        ):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be positive")
        for name in ("residual_correlation", "residual_autocorrelation"):
            if not -0.99 <= float(getattr(self, name)) <= 0.99:
                raise ValueError(f"{name} must be within [-0.99, 0.99]")


def build_synthetic_demand_training_payload(
    weather_dataset: CanonicalWeatherDataset,
    *,
    config: SyntheticCommercialDemandConfig | None = None,
) -> dict[str, object]:
    """Create a reproducible, explicitly non-site-calibrated demand history."""

    resolved = config or SyntheticCommercialDemandConfig()
    rng = random.Random(resolved.random_seed)
    non_cooling: list[float] = []
    cooling_rt: list[float] = []
    previous_non_cooling_residual = 0.0
    previous_cooling_residual = 0.0
    innovation_scale = math.sqrt(1.0 - resolved.residual_autocorrelation**2)
    cross_scale = math.sqrt(1.0 - resolved.residual_correlation**2)

    temperatures = weather_dataset.field_series["dry_bulb_air_temperature_c"]
    humidities = weather_dataset.field_series["relative_humidity_pct"]
    for index, local_label in enumerate(weather_dataset.local_civil_step_labels):
        local_time = datetime.fromisoformat(local_label)
        occupancy = _commercial_occupancy(local_time)
        baseline = resolved.non_cooling_min_kw + (
            resolved.non_cooling_max_kw - resolved.non_cooling_min_kw
        ) * occupancy

        first_normal = rng.gauss(0.0, 1.0)
        second_normal = (
            resolved.residual_correlation * first_normal
            + cross_scale * rng.gauss(0.0, 1.0)
        )
        previous_non_cooling_residual = (
            resolved.residual_autocorrelation * previous_non_cooling_residual
            + innovation_scale * resolved.non_cooling_residual_sigma_kw * first_normal
        )
        previous_cooling_residual = (
            resolved.residual_autocorrelation * previous_cooling_residual
            + innovation_scale * resolved.cooling_residual_sigma_kw * second_normal
        )

        temperature_excess = max(
            0.0,
            float(temperatures[index]) - resolved.cooling_balance_temperature_c,
        )
        humidity_excess = max(0.0, float(humidities[index]) - 50.0)
        cooling_electric_kw = min(
            resolved.cooling_electric_cap_kw,
            temperature_excess * (0.85 + 1.25 * occupancy)
            + humidity_excess * (0.04 + 0.07 * occupancy),
        )
        non_cooling.append(max(0.0, baseline + previous_non_cooling_residual))
        cooling_rt.append(
            max(
                0.0,
                cooling_electric_kw + previous_cooling_residual,
            )
            / resolved.electric_kw_per_rt
        )

    return _training_payload(
        dataset_id=f"synthetic-small-commercial:{weather_dataset.dataset_id}",
        timezone_name=weather_dataset.timezone_name,
        timestep_hours=weather_dataset.timestep_hours,
        timestamp_utc=weather_dataset.timestamp_utc,
        local_civil_step_labels=weather_dataset.local_civil_step_labels,
        weather_field_series={
            name: tuple(float(value) for value in weather_dataset.field_series[name])
            for name in CANONICAL_WEATHER_FIELD_ORDER[1:]
        },
        non_cooling=tuple(non_cooling),
        cooling_rt=tuple(cooling_rt),
        provenance={
            "demand_source_mode": "synthetic",
            "profile_label": "illustrative_small_commercial",
            "site_calibration_status": "not_site_calibrated",
            "weather_dataset_id": weather_dataset.dataset_id,
            "generator_configuration": asdict(resolved),
            "cooling_conversion_electric_kw_per_rt": resolved.electric_kw_per_rt,
            "notes": [
                "occupancy_temperature_humidity_cooling_interaction",
                "correlated_gaussian_autoregressive_residuals",
                "not_decision_grade_without_aligned_measured_site_demand",
            ],
        },
    )


def build_measured_demand_training_payload(
    csv_path: str | Path,
    *,
    timezone_name: str,
    minimum_complete_days: int = 90,
) -> dict[str, object]:
    """Validate a measured hourly CSV and adapt it to ``fit_demand_model``."""

    path = Path(csv_path)
    if isinstance(minimum_complete_days, bool) or minimum_complete_days <= 0:
        raise ValueError("minimum_complete_days must be a positive integer")
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise ValueError(f"invalid timezone_name {timezone_name!r}") from exc

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if "total_electric_demand_kw" in fieldnames and (
            "non_thermal_electric_demand_kw" not in fieldnames
            or "cooling_demand_rt" not in fieldnames
        ):
            raise ValueError(
                "total_electric_demand_kw without separate non-cooling and cooling "
                "series would double count cooling"
            )
        missing = [name for name in MEASURED_DEMAND_COLUMNS if name not in fieldnames]
        if missing:
            raise ValueError("measured demand CSV is missing columns: " + ", ".join(missing))
        rows = tuple(reader)
    if not rows:
        raise ValueError("measured demand CSV must contain hourly rows")

    timestamps: list[datetime] = []
    weather_values = {name: [] for name in DEMAND_WEATHER_FIELDS}
    non_cooling: list[float] = []
    cooling_rt: list[float] = []
    for row_index, row in enumerate(rows):
        timestamp = _parse_utc(row["timestamp_utc"], row_index=row_index)
        timestamps.append(timestamp)
        for name in DEMAND_WEATHER_FIELDS:
            weather_values[name].append(
                _non_negative_number(row[name], field_name=name, row_index=row_index)
                if name != "dry_bulb_air_temperature_c"
                else _finite_number(row[name], field_name=name, row_index=row_index)
            )
        non_cooling.append(
            _non_negative_number(
                row["non_thermal_electric_demand_kw"],
                field_name="non_thermal_electric_demand_kw",
                row_index=row_index,
            )
        )
        cooling_rt.append(
            _non_negative_number(
                row["cooling_demand_rt"],
                field_name="cooling_demand_rt",
                row_index=row_index,
            )
        )

    _validate_complete_hourly_days(
        timestamps,
        timezone=timezone,
        minimum_complete_days=int(minimum_complete_days),
    )
    timestamp_text = tuple(
        value.isoformat().replace("+00:00", "Z") for value in timestamps
    )
    local_labels = tuple(value.astimezone(timezone).isoformat() for value in timestamps)
    source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return _training_payload(
        dataset_id=f"measured-demand-csv:{source_sha[:16]}",
        timezone_name=timezone_name,
        timestep_hours=1.0,
        timestamp_utc=timestamp_text,
        local_civil_step_labels=local_labels,
        weather_field_series={name: tuple(values) for name, values in weather_values.items()},
        non_cooling=tuple(non_cooling),
        cooling_rt=tuple(cooling_rt),
        provenance={
            "demand_source_mode": "measured_csv",
            "source_path": path.as_posix(),
            "source_sha256": source_sha,
            "minimum_complete_days": int(minimum_complete_days),
            "double_counting_policy": "separate_non_cooling_electric_and_cooling_rt",
        },
    )


def _commercial_occupancy(local_time: datetime) -> float:
    hour = local_time.hour
    if hour < 6 or hour >= 22:
        occupancy = 0.0
    elif hour < 9:
        occupancy = (hour - 6) / 3.0
    elif hour < 17:
        occupancy = 1.0
    elif hour < 22:
        occupancy = max(0.0, 1.0 - (hour - 17) / 5.0)
    else:  # pragma: no cover - covered by the first branch
        occupancy = 0.0
    if local_time.weekday() >= 5:
        occupancy *= 0.65
    return occupancy


def _training_payload(
    *,
    dataset_id: str,
    timezone_name: str,
    timestep_hours: float,
    timestamp_utc: tuple[str, ...],
    local_civil_step_labels: tuple[str, ...],
    weather_field_series: dict[str, tuple[float, ...]],
    non_cooling: tuple[float, ...],
    cooling_rt: tuple[float, ...],
    provenance: dict[str, object],
) -> dict[str, object]:
    canonical_fields = tuple(
        name for name in CANONICAL_WEATHER_FIELD_ORDER[1:] if name in weather_field_series
    )
    return {
        "dataset_id": dataset_id,
        "timezone_name": timezone_name,
        "time_basis": LOCAL_CIVIL_TIME_BASIS,
        "timestep_hours": timestep_hours,
        "timestamp_utc": list(timestamp_utc),
        "local_civil_step_labels": list(local_civil_step_labels),
        "canonical_weather_fields": list(canonical_fields),
        "weather_field_series": {
            name: list(weather_field_series[name]) for name in canonical_fields
        },
        "non_thermal_electric_demand_kw": list(non_cooling),
        "cooling_demand_rt": list(cooling_rt),
        "provenance": provenance,
    }


def _parse_utc(value: str, *, row_index: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"timestamp_utc row {row_index} is not a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp_utc values must be timezone-aware UTC timestamps")
    return parsed


def _finite_number(value: str, *, field_name: str, row_index: int) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} row {row_index} must be numeric") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} row {row_index} must be finite")
    return normalized


def _non_negative_number(value: str, *, field_name: str, row_index: int) -> float:
    normalized = _finite_number(value, field_name=field_name, row_index=row_index)
    if normalized < 0.0:
        raise ValueError(f"{field_name} row {row_index} must be non-negative")
    return normalized


def _validate_complete_hourly_days(
    timestamps: list[datetime],
    *,
    timezone: ZoneInfo,
    minimum_complete_days: int,
) -> None:
    if len(set(timestamps)) != len(timestamps):
        raise ValueError("measured demand timestamps must not contain duplicates")
    for previous, current in zip(timestamps, timestamps[1:]):
        if current - previous != timedelta(hours=1):
            raise ValueError("measured demand timestamps must form one complete hourly series")
    local_timestamps = [value.astimezone(timezone) for value in timestamps]
    day_counts = Counter(value.date() for value in local_timestamps)
    complete_days = sum(count == 24 for count in day_counts.values())
    if any(count != 24 for count in day_counts.values()) or complete_days < minimum_complete_days:
        raise ValueError(
            f"measured demand CSV requires at least {minimum_complete_days} complete hourly days"
        )
    if local_timestamps[0].hour != 0 or local_timestamps[-1].hour != 23:
        raise ValueError(
            f"measured demand CSV requires at least {minimum_complete_days} complete hourly days"
        )


__all__ = [
    "DEMAND_WEATHER_FIELDS",
    "MEASURED_DEMAND_COLUMNS",
    "SyntheticCommercialDemandConfig",
    "build_measured_demand_training_payload",
    "build_synthetic_demand_training_payload",
]
