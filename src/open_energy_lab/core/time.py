"""UTC timestamp checks and formatting shared across packages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .errors import ValidationError
from .validation import non_empty_str


def format_utc(value: datetime) -> str:
    """Format an aware datetime as ISO 8601 UTC with a ``Z`` suffix."""

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def utc_datetime(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> datetime:
    """Return ``value`` if it is a timezone-aware datetime at UTC offset zero."""

    if not isinstance(value, datetime):
        raise error(f"{field_name} must be an aware UTC datetime")
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None or offset != timedelta(0):
        raise error(f"{field_name} must be an aware UTC datetime")
    return value.astimezone(UTC)


def utc_timestamp_text(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> str:
    """Normalize an ISO 8601 UTC timestamp string to its ``Z``-suffixed form."""

    text = non_empty_str(value, field_name=field_name, error=error)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise error(f"{field_name} must be an ISO 8601 timestamp") from exc
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None or offset.total_seconds() != 0:
        raise error(f"{field_name} must be an aware UTC timestamp")
    return format_utc(parsed)


__all__ = ["format_utc", "utc_datetime", "utc_timestamp_text"]
