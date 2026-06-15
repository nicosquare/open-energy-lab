"""Public demand package surface for weather-conditioned demand modeling.

Phase 2 keeps the package root import-light while reserving the stable module
paths used by later feature tasks.
"""

from __future__ import annotations

from typing import Any


_EXPORT_MAP: dict[str, tuple[str, str]] = {}

__all__: list[str] = []


def __getattr__(name: str) -> Any:
    """Reject undeclared demand exports while the root surface remains empty."""

    try:
        _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
