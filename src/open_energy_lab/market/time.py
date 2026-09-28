"""Canonical UTC intervals and exact multi-rate market time grids."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from open_energy_lab.core.time import format_utc


FRANCE_MARKET_TIMEZONE = "Europe/Paris"
HALF_OPEN_INTERVAL_CONVENTION = "start-inclusive/end-exclusive"

_FIXED_DURATION_PATTERN = re.compile(
    r"^PT(?:(?P<hours>[0-9]+)H)?(?:(?P<minutes>[0-9]+)M)?"
    r"(?:(?P<seconds>[0-9]+)S)?$"
)


class MarketTimeValidationError(ValueError):
    """Raised when canonical market-time semantics are invalid or ambiguous."""


def _timezone(name: str) -> ZoneInfo:
    if not isinstance(name, str) or not name:
        raise MarketTimeValidationError("market timezone must be a non-empty IANA name")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise MarketTimeValidationError(f"unknown market timezone {name!r}") from exc


def _require_utc(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise MarketTimeValidationError(f"{field_name} must be an aware UTC datetime")
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise MarketTimeValidationError(f"{field_name} must be an aware UTC datetime")
    if offset != timedelta(0):
        raise MarketTimeValidationError(f"{field_name} must use UTC, got offset {offset}")
    return value.astimezone(UTC)


def _parse_datetime(value: object, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        raise MarketTimeValidationError(f"{field_name} must be an ISO 8601 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketTimeValidationError(
            f"{field_name} must be an ISO 8601 timestamp, got {value!r}"
        ) from exc


_format_utc = format_utc


def _offset_seconds(value: datetime) -> int:
    offset = value.utcoffset()
    if offset is None:
        raise MarketTimeValidationError("local delivery label must be timezone-aware")
    return int(offset.total_seconds())


@dataclass(frozen=True, slots=True)
class CanonicalInterval:
    """One aware, UTC-authoritative, half-open market delivery interval."""

    start_utc: datetime
    end_utc: datetime
    local_start: datetime
    local_end: datetime
    start_utc_offset_seconds: int
    end_utc_offset_seconds: int
    start_fold: int
    end_fold: int
    market_timezone: str = FRANCE_MARKET_TIMEZONE
    interval_convention: str = HALF_OPEN_INTERVAL_CONVENTION

    def __post_init__(self) -> None:
        start = _require_utc(self.start_utc, field_name="start_utc")
        end = _require_utc(self.end_utc, field_name="end_utc")
        if start >= end:
            raise MarketTimeValidationError(
                "interval start_utc must be before end_utc and have positive duration"
            )
        if self.interval_convention != HALF_OPEN_INTERVAL_CONVENTION:
            raise MarketTimeValidationError(
                "interval_convention must be start-inclusive/end-exclusive"
            )
        zone = _timezone(self.market_timezone)
        expected_local_start = start.astimezone(zone)
        expected_local_end = end.astimezone(zone)
        if self.local_start != expected_local_start:
            raise MarketTimeValidationError(
                "local_start does not match start_utc in the market timezone"
            )
        if self.local_end != expected_local_end:
            raise MarketTimeValidationError(
                "local_end does not match end_utc in the market timezone"
            )
        expected_start_offset = _offset_seconds(expected_local_start)
        expected_end_offset = _offset_seconds(expected_local_end)
        if self.start_utc_offset_seconds != expected_start_offset:
            raise MarketTimeValidationError(
                "start_utc_offset_seconds does not match Europe/Paris conversion"
            )
        if self.end_utc_offset_seconds != expected_end_offset:
            raise MarketTimeValidationError(
                "end_utc_offset_seconds does not match Europe/Paris conversion"
            )
        if self.start_fold not in (0, 1) or self.start_fold != expected_local_start.fold:
            raise MarketTimeValidationError("start_fold does not match local_start")
        if self.end_fold not in (0, 1) or self.end_fold != expected_local_end.fold:
            raise MarketTimeValidationError("end_fold does not match local_end")
        object.__setattr__(self, "start_utc", start)
        object.__setattr__(self, "end_utc", end)
        object.__setattr__(self, "local_start", expected_local_start)
        object.__setattr__(self, "local_end", expected_local_end)

    @classmethod
    def from_utc(
        cls,
        start_utc: datetime,
        end_utc: datetime,
        *,
        market_timezone: str = FRANCE_MARKET_TIMEZONE,
    ) -> CanonicalInterval:
        """Construct canonical local metadata from authoritative UTC bounds."""

        start = _require_utc(start_utc, field_name="start_utc")
        end = _require_utc(end_utc, field_name="end_utc")
        if start >= end:
            raise MarketTimeValidationError(
                "interval start_utc must be before end_utc and have positive duration"
            )
        zone = _timezone(market_timezone)
        local_start = start.astimezone(zone)
        local_end = end.astimezone(zone)
        return cls(
            start_utc=start,
            end_utc=end,
            local_start=local_start,
            local_end=local_end,
            start_utc_offset_seconds=_offset_seconds(local_start),
            end_utc_offset_seconds=_offset_seconds(local_end),
            start_fold=local_start.fold,
            end_fold=local_end.fold,
            market_timezone=market_timezone,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CanonicalInterval:
        """Load and verify persisted UTC and local delivery metadata."""

        required = (
            "start_utc",
            "end_utc",
            "local_start",
            "local_end",
            "start_utc_offset_seconds",
            "end_utc_offset_seconds",
            "start_fold",
            "end_fold",
            "market_timezone",
            "interval_convention",
        )
        missing = [name for name in required if name not in payload]
        if missing:
            raise MarketTimeValidationError(
                "canonical interval is missing required fields: " + ", ".join(missing)
            )
        start = _require_utc(
            _parse_datetime(payload["start_utc"], field_name="start_utc"),
            field_name="start_utc",
        )
        end = _require_utc(
            _parse_datetime(payload["end_utc"], field_name="end_utc"),
            field_name="end_utc",
        )
        local_start = _parse_datetime(payload["local_start"], field_name="local_start")
        local_end = _parse_datetime(payload["local_end"], field_name="local_end")
        return cls(
            start_utc=start,
            end_utc=end,
            local_start=local_start,
            local_end=local_end,
            start_utc_offset_seconds=int(payload["start_utc_offset_seconds"]),
            end_utc_offset_seconds=int(payload["end_utc_offset_seconds"]),
            start_fold=int(payload["start_fold"]),
            end_fold=int(payload["end_fold"]),
            market_timezone=str(payload["market_timezone"]),
            interval_convention=str(payload["interval_convention"]),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the complete auditable interval representation."""

        return {
            "start_utc": _format_utc(self.start_utc),
            "end_utc": _format_utc(self.end_utc),
            "local_start": self.local_start.isoformat(),
            "local_end": self.local_end.isoformat(),
            "start_utc_offset_seconds": self.start_utc_offset_seconds,
            "end_utc_offset_seconds": self.end_utc_offset_seconds,
            "start_fold": self.start_fold,
            "end_fold": self.end_fold,
            "market_timezone": self.market_timezone,
            "interval_convention": self.interval_convention,
        }


def canonical_interval(
    start_utc: datetime,
    end_utc: datetime,
    *,
    market_timezone: str = FRANCE_MARKET_TIMEZONE,
) -> CanonicalInterval:
    """Build one validated canonical interval from UTC bounds."""

    return CanonicalInterval.from_utc(
        start_utc,
        end_utc,
        market_timezone=market_timezone,
    )


def parse_iso8601_duration(value: str) -> timedelta:
    """Parse the positive fixed-width ISO durations supported by market grids."""

    if not isinstance(value, str):
        raise MarketTimeValidationError("ISO duration must be a string")
    match = _FIXED_DURATION_PATTERN.fullmatch(value)
    if match is None or not any(match.groupdict().values()):
        raise MarketTimeValidationError(
            f"resolution must be a positive fixed ISO duration, got {value!r}"
        )
    duration = timedelta(
        hours=int(match.group("hours") or 0),
        minutes=int(match.group("minutes") or 0),
        seconds=int(match.group("seconds") or 0),
    )
    if duration <= timedelta(0):
        raise MarketTimeValidationError("resolution duration must be positive")
    return duration


def _build_utc_intervals(
    start_utc: datetime,
    end_utc: datetime,
    resolution: timedelta,
    *,
    market_timezone: str,
) -> tuple[CanonicalInterval, ...]:
    intervals: list[CanonicalInterval] = []
    cursor = start_utc
    while cursor < end_utc:
        next_cursor = cursor + resolution
        if next_cursor > end_utc:
            raise MarketTimeValidationError(
                "period is not exactly divisible by the requested resolution"
            )
        intervals.append(
            canonical_interval(
                cursor,
                next_cursor,
                market_timezone=market_timezone,
            )
        )
        cursor = next_cursor
    return tuple(intervals)


def build_local_delivery_day(
    local_day: date,
    *,
    resolution: str,
    market_timezone: str = FRANCE_MARKET_TIMEZONE,
) -> tuple[CanonicalInterval, ...]:
    """Construct one complete local delivery day on an authoritative UTC grid."""

    if not isinstance(local_day, date) or isinstance(local_day, datetime):
        raise MarketTimeValidationError("local_day must be a date")
    zone = _timezone(market_timezone)
    local_start = datetime.combine(local_day, time.min, tzinfo=zone)
    local_end = datetime.combine(local_day + timedelta(days=1), time.min, tzinfo=zone)
    start_utc = local_start.astimezone(UTC)
    end_utc = local_end.astimezone(UTC)
    parsed_resolution = parse_iso8601_duration(resolution)
    total_seconds = int((end_utc - start_utc).total_seconds())
    resolution_seconds = int(parsed_resolution.total_seconds())
    if total_seconds % resolution_seconds:
        raise MarketTimeValidationError(
            "local delivery day is not exactly divisible by the requested resolution"
        )
    return _build_utc_intervals(
        start_utc,
        end_utc,
        parsed_resolution,
        market_timezone=market_timezone,
    )


def _local_block_offset_seconds(value: datetime, zone: ZoneInfo) -> int:
    local = value.astimezone(zone)
    midnight = datetime.combine(local.date(), time.min)
    naive_local = local.replace(tzinfo=None)
    return int((naive_local - midnight).total_seconds())


def require_complete_blocks(
    start_utc: datetime,
    end_utc: datetime,
    *,
    resolution: str,
    market_timezone: str = FRANCE_MARKET_TIMEZONE,
) -> None:
    """Require a period to contain only complete, aligned product blocks."""

    start = _require_utc(start_utc, field_name="start_utc")
    end = _require_utc(end_utc, field_name="end_utc")
    if start >= end:
        raise MarketTimeValidationError("block start must be before block end")
    parsed = parse_iso8601_duration(resolution)
    block_seconds = int(parsed.total_seconds())
    total_seconds = int((end - start).total_seconds())
    if total_seconds % block_seconds:
        raise MarketTimeValidationError(
            f"period does not contain complete {resolution} blocks"
        )
    zone = _timezone(market_timezone)
    if _local_block_offset_seconds(start, zone) % block_seconds:
        raise MarketTimeValidationError(
            f"start boundary does not align with a {resolution} delivery block"
        )
    if _local_block_offset_seconds(end, zone) % block_seconds:
        raise MarketTimeValidationError(
            f"end boundary does not align with a {resolution} delivery block"
        )


@dataclass(frozen=True, slots=True)
class MultiRateTimeIndex:
    """Exact containment maps from activation intervals to coarser grids."""

    activation_resolution: str
    checkpoint_resolution: str
    energy_resolution: str
    fcr_resolution: str
    activation_intervals: tuple[CanonicalInterval, ...]
    checkpoint_intervals: tuple[CanonicalInterval, ...]
    energy_intervals: tuple[CanonicalInterval, ...]
    fcr_intervals: tuple[CanonicalInterval, ...]
    activation_to_checkpoint: tuple[int, ...]
    activation_to_energy: tuple[int, ...]
    activation_to_fcr: tuple[int, ...]


def build_multi_rate_index(
    start_utc: datetime,
    end_utc: datetime,
    *,
    activation_resolution: str,
    checkpoint_resolution: str,
    energy_resolution: str,
    fcr_resolution: str,
    market_timezone: str = FRANCE_MARKET_TIMEZONE,
) -> MultiRateTimeIndex:
    """Build exact PT10S/PT15M/PT1H/PT4H-style containment maps."""

    start = _require_utc(start_utc, field_name="start_utc")
    end = _require_utc(end_utc, field_name="end_utc")
    if start >= end:
        raise MarketTimeValidationError("time-grid start must be before end")
    labels = (
        activation_resolution,
        checkpoint_resolution,
        energy_resolution,
        fcr_resolution,
    )
    durations = tuple(parse_iso8601_duration(label) for label in labels)
    seconds = tuple(int(duration.total_seconds()) for duration in durations)
    for finer, coarser in zip(seconds, seconds[1:]):
        if coarser < finer or coarser % finer:
            raise MarketTimeValidationError(
                "each coarser resolution must divide exactly by the next finer resolution"
            )

    require_complete_blocks(
        start,
        end,
        resolution=fcr_resolution,
        market_timezone=market_timezone,
    )
    total_seconds = int((end - start).total_seconds())
    for label, resolution_seconds in zip(labels, seconds):
        if total_seconds % resolution_seconds:
            raise MarketTimeValidationError(
                f"period does not contain complete {label} blocks"
            )

    grids = tuple(
        _build_utc_intervals(
            start,
            end,
            duration,
            market_timezone=market_timezone,
        )
        for duration in durations
    )
    activation_count = len(grids[0])
    activation_to_checkpoint = tuple(
        index // (seconds[1] // seconds[0]) for index in range(activation_count)
    )
    activation_to_energy = tuple(
        index // (seconds[2] // seconds[0]) for index in range(activation_count)
    )
    activation_to_fcr = tuple(
        index // (seconds[3] // seconds[0]) for index in range(activation_count)
    )
    return MultiRateTimeIndex(
        activation_resolution=activation_resolution,
        checkpoint_resolution=checkpoint_resolution,
        energy_resolution=energy_resolution,
        fcr_resolution=fcr_resolution,
        activation_intervals=grids[0],
        checkpoint_intervals=grids[1],
        energy_intervals=grids[2],
        fcr_intervals=grids[3],
        activation_to_checkpoint=activation_to_checkpoint,
        activation_to_energy=activation_to_energy,
        activation_to_fcr=activation_to_fcr,
    )


__all__ = [
    "CanonicalInterval",
    "FRANCE_MARKET_TIMEZONE",
    "HALF_OPEN_INTERVAL_CONVENTION",
    "MarketTimeValidationError",
    "MultiRateTimeIndex",
    "build_local_delivery_day",
    "build_multi_rate_index",
    "canonical_interval",
    "parse_iso8601_duration",
    "require_complete_blocks",
]
