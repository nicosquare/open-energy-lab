"""Base exception shared by package-specific validation errors."""

from __future__ import annotations


class ValidationError(ValueError):
    """Raised when a value violates a library contract."""


__all__ = ["ValidationError"]
