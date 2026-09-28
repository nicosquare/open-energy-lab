"""Scalar and container checks shared across packages.

Every check takes ``field_name`` for the error message and ``error`` for the
exception class to raise, so a package can bind its own error type once::

    _finite = partial(finite, error=MarketArtifactValidationError)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
import math
import re
from typing import Any, TypeVar

from .errors import ValidationError

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

E = TypeVar("E", bound=Enum)


def finite(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
    normalize_zero: bool = False,
) -> float:
    """Return ``value`` as a finite float; bools are rejected.

    With ``normalize_zero`` a negative zero is returned as ``0.0``.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error(f"{field_name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise error(f"{field_name} must be finite")
    if normalize_zero and normalized == 0.0:
        return 0.0
    return normalized


def non_empty_str(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
    strip: bool = False,
) -> str:
    """Return ``value`` unchanged if it is a non-empty string.

    With ``strip`` a whitespace-only string also counts as empty.
    """

    if not isinstance(value, str) or not (value.strip() if strip else value):
        raise error(f"{field_name} must be a non-empty string")
    return value


def optional_str(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> str | None:
    """Return ``None`` or a non-empty string."""

    if value is None:
        return None
    return non_empty_str(value, field_name=field_name, error=error)


def non_negative_int(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> int:
    """Return ``value`` if it is an ``int`` (not bool) greater than or equal to zero."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise error(f"{field_name} must be a non-negative integer")
    return value


def positive_int(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> int:
    """Return ``value`` if it is an ``int`` (not bool) greater than zero."""

    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise error(f"{field_name} must be a positive integer")
    return value


def boolean(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> bool:
    """Return ``value`` if it is a bool."""

    if not isinstance(value, bool):
        raise error(f"{field_name} must be boolean")
    return value


def mapping(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> dict[str, Any]:
    """Return a shallow ``dict`` copy of a mapping with string keys."""

    if not isinstance(value, Mapping):
        raise error(f"{field_name} must be a mapping")
    return {str(key): inner for key, inner in value.items()}


def sequence(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> list[Any]:
    """Return a list copy of a non-string sequence."""

    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise error(f"{field_name} must be a sequence")
    return list(value)


def require_fields(
    payload: Mapping[str, Any],
    names: Sequence[str],
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> None:
    """Raise if any of ``names`` is missing from ``payload``."""

    missing = [name for name in names if name not in payload]
    if missing:
        raise error(f"{field_name} is missing required fields: {', '.join(missing)}")


def sha256_digest(
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> str:
    """Return ``value`` if it is a lowercase hexadecimal SHA-256 digest."""

    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise error(f"{field_name} must be a lowercase SHA-256 hexadecimal digest")
    return value


def enum_member(
    enum_type: type[E],
    value: object,
    *,
    field_name: str,
    error: type[Exception] = ValidationError,
) -> E:
    """Return the ``enum_type`` member for ``value``."""

    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(str(member.value) for member in enum_type)
        raise error(f"{field_name} must be one of: {allowed}") from exc


__all__ = [
    "boolean",
    "enum_member",
    "finite",
    "mapping",
    "non_empty_str",
    "non_negative_int",
    "optional_str",
    "positive_int",
    "require_fields",
    "sequence",
    "sha256_digest",
]
