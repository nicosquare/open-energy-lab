"""Pure public contracts and orchestration for robust FCR bidding.

The module is intentionally safe to import without Pyomo or a solver.  Private
backend modules are loaded only by an explicit solve operation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, TypeVar


ROBUST_FCR_BATTERY_PARAMETERS_VERSION = "oel.robust-fcr-battery-parameters.v1"
ROBUST_FCR_TIME_CONTRACT_VERSION = "oel.robust-fcr-time-contract.v1"
RECOVERY_WINDOW_ACTIVATION_BUDGET_VERSION = (
    "oel.recovery-window-activation-budget.v1"
)
HORIZON_WIDE_ACTIVATION_BUDGET_VERSION = "oel.horizon-wide-activation-budget.v1"
ROBUST_FCR_UNCERTAINTY_PROFILE_VERSION = "oel.robust-fcr-uncertainty-profile.v1"
TERMINAL_STORED_ENERGY_RULE_VERSION = "oel.terminal-stored-energy-rule.v1"
ROBUST_FCR_PRICE_INPUTS_VERSION = "oel.robust-fcr-price-inputs.v1"
ROBUST_FCR_SOLVE_POLICY_VERSION = "oel.robust-fcr-solve-policy.v1"
ROBUST_FCR_BIDDING_PROBLEM_VERSION = "oel.robust-fcr-bidding-problem.v1"
ROBUST_FCR_FORMULATION_PROFILE_VERSION = "oel.robust-fcr-formulation-profile.v1"
ROBUST_FCR_SOLVE_RESULT_VERSION = "oel.robust-fcr-solve-result.v1"
HORIZON_BUDGET_DERIVATION_RULE = "covering-window-budget-v1"
DECISION_CANONICALIZATION_ID = "solver-output-kw-1e-9-half-even-v1"
DEPLOYABILITY_THRESHOLD = 1e-6

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_T = TypeVar("_T")


class RobustFCRValidationError(ValueError):
    """Raised before model assembly when a public contract is invalid."""


class RobustFCRSolverDependencyUnavailableError(ImportError):
    """Raised when a required solver dependency is absent or incompatible."""


class RobustFCRSolverUnavailableError(RuntimeError):
    """Raised when an installed required solver cannot execute."""


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RobustFCRValidationError(f"{field_name} must be a non-empty string")
    return value


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RobustFCRValidationError(f"{field_name} must be finite")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise RobustFCRValidationError(f"{field_name} must be finite")
    return 0.0 if normalized == 0.0 else normalized


def _positive(value: object, *, field_name: str) -> float:
    normalized = _finite(value, field_name=field_name)
    if normalized <= 0.0:
        raise RobustFCRValidationError(f"{field_name} must be greater than zero")
    return normalized


def _non_negative(value: object, *, field_name: str) -> float:
    normalized = _finite(value, field_name=field_name)
    if normalized < 0.0:
        raise RobustFCRValidationError(f"{field_name} must be non-negative")
    return normalized


def _integer(value: object, *, field_name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RobustFCRValidationError(f"{field_name} must be an integer")
    if minimum is not None and value < minimum:
        raise RobustFCRValidationError(
            f"{field_name} must be greater than or equal to {minimum}"
        )
    return value


def _sha256(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise RobustFCRValidationError(
            f"{field_name} must be a lowercase SHA-256 fingerprint"
        )
    return value


def _utc(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise RobustFCRValidationError(f"{field_name} must be an aware UTC datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise RobustFCRValidationError(f"{field_name} must be an aware UTC datetime")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    normalized = _utc(value, field_name="datetime")
    return normalized.isoformat().replace("+00:00", "Z")


def _deep_freeze(value: _T, *, field_name: str = "value") -> _T:
    """Copy JSON-like input into deterministic immutable containers."""

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, inner in value.items():
            if not isinstance(key, str) or not key:
                raise RobustFCRValidationError(
                    f"{field_name} mapping keys must be non-empty strings"
                )
            normalized[key] = _deep_freeze(
                inner,
                field_name=f"{field_name}.{key}",
            )
        return MappingProxyType(dict(sorted(normalized.items())))  # type: ignore[return-value]
    if isinstance(value, tuple):
        return tuple(
            _deep_freeze(inner, field_name=f"{field_name}[{index}]")
            for index, inner in enumerate(value)
        )  # type: ignore[return-value]
    if isinstance(value, list):
        return tuple(
            _deep_freeze(inner, field_name=f"{field_name}[{index}]")
            for index, inner in enumerate(value)
        )  # type: ignore[return-value]
    if isinstance(value, float):
        return _finite(value, field_name=field_name)  # type: ignore[return-value]
    if value is None or isinstance(value, (str, bool, int, datetime, date)):
        return value
    raise RobustFCRValidationError(
        f"{field_name} must contain only canonical JSON-compatible values"
    )


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(inner) for key, inner in sorted(value.items())}
    if isinstance(value, tuple):
        return [_thaw(inner) for inner in value]
    if isinstance(value, datetime):
        return _utc_text(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return _finite(value, field_name="canonical numeric value")
    if is_dataclass(value) and not isinstance(value, type):
        if hasattr(value, "to_dict"):
            return _thaw(value.to_dict())
        return {
            field.name: _thaw(getattr(value, field.name))
            for field in fields(value)
            if not field.name.startswith("_")
        }
    return value


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            _thaw(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RobustFCRValidationError(
            f"robust FCR data must be finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _validate_semantics_version(
    value: object,
    *,
    expected: str,
    field_name: str = "semantics_version",
) -> str:
    normalized = _non_empty(value, field_name=field_name)
    if normalized != expected:
        raise RobustFCRValidationError(
            f"{field_name} must be {expected!r}; got {normalized!r}"
        )
    return normalized


def _finite_tuple(
    values: object,
    *,
    field_name: str,
    count: int | None = None,
) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RobustFCRValidationError(f"{field_name} must be a sequence")
    normalized = tuple(
        _finite(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(values)
    )
    if count is not None and len(normalized) != count:
        raise RobustFCRValidationError(
            f"{field_name} must contain exactly {count} values"
        )
    return normalized


def _string_tuple(
    values: object,
    *,
    field_name: str,
    count: int | None = None,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RobustFCRValidationError(f"{field_name} must be a sequence")
    normalized = tuple(
        _non_empty(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(values)
    )
    if count is not None and len(normalized) != count:
        raise RobustFCRValidationError(
            f"{field_name} must contain exactly {count} values"
        )
    return normalized


__all__ = [
    "DECISION_CANONICALIZATION_ID",
    "DEPLOYABILITY_THRESHOLD",
    "HORIZON_BUDGET_DERIVATION_RULE",
    "HORIZON_WIDE_ACTIVATION_BUDGET_VERSION",
    "RECOVERY_WINDOW_ACTIVATION_BUDGET_VERSION",
    "ROBUST_FCR_BATTERY_PARAMETERS_VERSION",
    "ROBUST_FCR_BIDDING_PROBLEM_VERSION",
    "ROBUST_FCR_FORMULATION_PROFILE_VERSION",
    "ROBUST_FCR_PRICE_INPUTS_VERSION",
    "ROBUST_FCR_SOLVE_POLICY_VERSION",
    "ROBUST_FCR_SOLVE_RESULT_VERSION",
    "ROBUST_FCR_TIME_CONTRACT_VERSION",
    "ROBUST_FCR_UNCERTAINTY_PROFILE_VERSION",
    "RobustFCRSolverDependencyUnavailableError",
    "RobustFCRSolverUnavailableError",
    "RobustFCRValidationError",
    "TERMINAL_STORED_ENERGY_RULE_VERSION",
]
