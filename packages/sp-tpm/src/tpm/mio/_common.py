"""Schema versions, the Pyomo dependency error, and payload accessors shared by the MIO modules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


_LEGACY_SPFLOW_MIO_SCHEMA_VERSION = "v1"
_LEGACY_SPFLOW_MIO_COMPILER_VERSION = "spflow-v1-mio-v1"
_SPFLOW_MIO_SCHEMA_VERSION = "v2"
_SPFLOW_MIO_COMPILER_VERSION = "spflow-v1-mio-v2"


class SPNSolverDependencyUnavailableError(ImportError):
    """Raised when solving one SPN chance model requires Pyomo but it is unavailable."""


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): inner_value for key, inner_value in value.items()}


def _sequence(value: object, *, field_name: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence")
    return tuple(value)


def _sequence_of_mappings(value: object, *, field_name: str) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of mappings")
    result: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field_name} must contain only mappings")
        result.append(item)
    return tuple(result)


def _float_sequence(value: object) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("expected a numeric sequence")
    return tuple(float(item) for item in value)
