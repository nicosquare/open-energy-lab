"""Pure public contracts and orchestration for robust FCR bidding.

The module is intentionally safe to import without Pyomo or a solver.  Private
backend modules are loaded only by an explicit solve operation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, TypeVar

from open_energy_lab.market.time import (
    CanonicalInterval,
    MarketTimeValidationError,
    build_local_delivery_day,
)


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


@dataclass(frozen=True, slots=True)
class RobustFCRBatteryParameters:
    maximum_charge_power_kw: float
    maximum_discharge_power_kw: float
    minimum_stored_energy_kwh: float
    maximum_stored_energy_kwh: float
    initial_stored_energy_kwh: float
    charge_efficiency: float
    discharge_efficiency: float
    semantics_version: str = ROBUST_FCR_BATTERY_PARAMETERS_VERSION
    battery_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_BATTERY_PARAMETERS_VERSION,
            ),
        )
        maximum_charge = _positive(
            self.maximum_charge_power_kw,
            field_name="maximum_charge_power_kw",
        )
        maximum_discharge = _positive(
            self.maximum_discharge_power_kw,
            field_name="maximum_discharge_power_kw",
        )
        minimum_energy = _non_negative(
            self.minimum_stored_energy_kwh,
            field_name="minimum_stored_energy_kwh",
        )
        maximum_energy = _positive(
            self.maximum_stored_energy_kwh,
            field_name="maximum_stored_energy_kwh",
        )
        if maximum_energy <= minimum_energy:
            raise RobustFCRValidationError(
                "maximum_stored_energy_kwh must exceed minimum_stored_energy_kwh"
            )
        initial_energy = _finite(
            self.initial_stored_energy_kwh,
            field_name="initial_stored_energy_kwh",
        )
        if not minimum_energy <= initial_energy <= maximum_energy:
            raise RobustFCRValidationError(
                "initial_stored_energy_kwh must be within stored-energy bounds"
            )
        charge_efficiency = _positive(
            self.charge_efficiency,
            field_name="charge_efficiency",
        )
        discharge_efficiency = _positive(
            self.discharge_efficiency,
            field_name="discharge_efficiency",
        )
        if charge_efficiency > 1.0:
            raise RobustFCRValidationError("charge_efficiency must be no greater than 1")
        if discharge_efficiency > 1.0:
            raise RobustFCRValidationError(
                "discharge_efficiency must be no greater than 1"
            )
        object.__setattr__(self, "maximum_charge_power_kw", maximum_charge)
        object.__setattr__(self, "maximum_discharge_power_kw", maximum_discharge)
        object.__setattr__(self, "minimum_stored_energy_kwh", minimum_energy)
        object.__setattr__(self, "maximum_stored_energy_kwh", maximum_energy)
        object.__setattr__(self, "initial_stored_energy_kwh", initial_energy)
        object.__setattr__(self, "charge_efficiency", charge_efficiency)
        object.__setattr__(self, "discharge_efficiency", discharge_efficiency)
        object.__setattr__(
            self,
            "battery_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    @property
    def source_minimum_power_kw(self) -> float:
        return -self.maximum_charge_power_kw

    @property
    def source_maximum_power_kw(self) -> float:
        return self.maximum_discharge_power_kw

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "maximum_charge_power_kw": self.maximum_charge_power_kw,
            "maximum_discharge_power_kw": self.maximum_discharge_power_kw,
            "minimum_stored_energy_kwh": self.minimum_stored_energy_kwh,
            "maximum_stored_energy_kwh": self.maximum_stored_energy_kwh,
            "initial_stored_energy_kwh": self.initial_stored_energy_kwh,
            "charge_efficiency": self.charge_efficiency,
            "discharge_efficiency": self.discharge_efficiency,
            "units": {
                "power": "kW",
                "stored_energy": "kWh",
                "efficiency": "dimensionless",
            },
            "source_power_sign": "positive_is_discharge",
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_payload(), "battery_fingerprint": self.battery_fingerprint}


def _validate_partition(
    intervals: tuple[CanonicalInterval, ...],
    *,
    count: int,
    duration: timedelta,
    field_name: str,
    delivery_period: CanonicalInterval,
) -> None:
    if len(intervals) != count:
        raise RobustFCRValidationError(
            f"{field_name} must contain exactly {count} intervals"
        )
    cursor = delivery_period.start_utc
    for index, interval in enumerate(intervals):
        if not isinstance(interval, CanonicalInterval):
            raise RobustFCRValidationError(
                f"{field_name}[{index}] must be a CanonicalInterval"
            )
        if interval.start_utc != cursor or interval.end_utc - interval.start_utc != duration:
            raise RobustFCRValidationError(
                f"{field_name} must be ordered, gapless, and exactly aligned"
            )
        if interval.market_timezone != delivery_period.market_timezone:
            raise RobustFCRValidationError(
                f"{field_name} must use the delivery market timezone"
            )
        cursor = interval.end_utc
    if cursor != delivery_period.end_utc:
        raise RobustFCRValidationError(
            f"{field_name} must exactly partition the delivery period"
        )


@dataclass(frozen=True, slots=True)
class RobustFCRTimeContract:
    delivery_period: CanonicalInterval
    market_timezone: str
    planning_intervals: tuple[CanonicalInterval, ...]
    energy_intervals: tuple[CanonicalInterval, ...]
    fcr_intervals: tuple[CanonicalInterval, ...]
    planning_to_energy: tuple[int, ...]
    planning_to_fcr: tuple[int, ...]
    semantics_version: str = ROBUST_FCR_TIME_CONTRACT_VERSION
    time_contract_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_TIME_CONTRACT_VERSION,
            ),
        )
        if not isinstance(self.delivery_period, CanonicalInterval):
            raise RobustFCRValidationError(
                "delivery_period must be a CanonicalInterval"
            )
        timezone = _non_empty(self.market_timezone, field_name="market_timezone")
        if self.delivery_period.market_timezone != timezone:
            raise RobustFCRValidationError(
                "delivery_period must use the declared market_timezone"
            )
        if self.delivery_period.end_utc - self.delivery_period.start_utc != timedelta(
            hours=24
        ):
            raise RobustFCRValidationError(
                "Feature 013 requires one ordinary 24-hour delivery day"
            )
        planning = tuple(self.planning_intervals)
        energy = tuple(self.energy_intervals)
        fcr = tuple(self.fcr_intervals)
        _validate_partition(
            planning,
            count=96,
            duration=timedelta(minutes=15),
            field_name="planning_intervals",
            delivery_period=self.delivery_period,
        )
        _validate_partition(
            energy,
            count=24,
            duration=timedelta(hours=1),
            field_name="energy_intervals",
            delivery_period=self.delivery_period,
        )
        _validate_partition(
            fcr,
            count=6,
            duration=timedelta(hours=4),
            field_name="fcr_intervals",
            delivery_period=self.delivery_period,
        )
        planning_to_energy = tuple(self.planning_to_energy)
        planning_to_fcr = tuple(self.planning_to_fcr)
        expected_energy = tuple(index // 4 for index in range(96))
        expected_fcr = tuple(index // 16 for index in range(96))
        if planning_to_energy != expected_energy:
            raise RobustFCRValidationError(
                "planning_to_energy must map each four quarter-hours to one hour"
            )
        if planning_to_fcr != expected_fcr:
            raise RobustFCRValidationError(
                "planning_to_fcr must map each 16 quarter-hours to one FCR block"
            )
        object.__setattr__(self, "market_timezone", timezone)
        object.__setattr__(self, "planning_intervals", planning)
        object.__setattr__(self, "energy_intervals", energy)
        object.__setattr__(self, "fcr_intervals", fcr)
        object.__setattr__(self, "planning_to_energy", planning_to_energy)
        object.__setattr__(self, "planning_to_fcr", planning_to_fcr)
        object.__setattr__(
            self,
            "time_contract_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "delivery_period": self.delivery_period.to_dict(),
            "market_timezone": self.market_timezone,
            "planning_intervals": [value.to_dict() for value in self.planning_intervals],
            "energy_intervals": [value.to_dict() for value in self.energy_intervals],
            "fcr_intervals": [value.to_dict() for value in self.fcr_intervals],
            "mapping": {
                "planning_to_energy": list(self.planning_to_energy),
                "planning_to_fcr": list(self.planning_to_fcr),
                "source_one_based_formulas": {
                    "energy": "ceil(k / 4)",
                    "fcr": "ceil(k / 16)",
                },
            },
            "resolutions": {
                "planning": "PT15M",
                "energy": "PT1H",
                "fcr": "PT4H",
            },
            "source_refs": [
                "baselines/robust_storage_bidding/code/02_model.jl:170-174,252-253",
                "baselines/robust_storage_bidding/code/12.jl:27-47",
            ],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "time_contract_fingerprint": self.time_contract_fingerprint,
        }


def build_robust_fcr_time_contract(
    *,
    delivery_date: date,
    market_timezone: str,
    semantics_version: str = ROBUST_FCR_TIME_CONTRACT_VERSION,
) -> RobustFCRTimeContract:
    if not isinstance(delivery_date, date) or isinstance(delivery_date, datetime):
        raise RobustFCRValidationError("delivery_date must be a date")
    timezone = _non_empty(market_timezone, field_name="market_timezone")
    try:
        planning = build_local_delivery_day(
            delivery_date,
            resolution="PT15M",
            market_timezone=timezone,
        )
        energy = build_local_delivery_day(
            delivery_date,
            resolution="PT1H",
            market_timezone=timezone,
        )
        fcr = build_local_delivery_day(
            delivery_date,
            resolution="PT4H",
            market_timezone=timezone,
        )
    except MarketTimeValidationError as exc:
        raise RobustFCRValidationError(
            "Feature 013 requires one ordinary 24-hour delivery day in a valid "
            f"market timezone: {exc}"
        ) from exc
    if len(planning) != 96 or len(energy) != 24 or len(fcr) != 6:
        raise RobustFCRValidationError(
            "Feature 013 requires one ordinary 24-hour local delivery day"
        )
    period = CanonicalInterval.from_utc(
        planning[0].start_utc,
        planning[-1].end_utc,
        market_timezone=timezone,
    )
    return RobustFCRTimeContract(
        delivery_period=period,
        market_timezone=timezone,
        planning_intervals=planning,
        energy_intervals=energy,
        fcr_intervals=fcr,
        planning_to_energy=tuple(index // 4 for index in range(96)),
        planning_to_fcr=tuple(index // 16 for index in range(96)),
        semantics_version=semantics_version,
    )


@dataclass(frozen=True, slots=True)
class RecoveryWindowActivationBudget:
    recovery_activation_budget_hours: float
    recovery_window_hours: float
    pointwise_activation_lower: float = -1.0
    pointwise_activation_upper: float = 1.0
    semantics_version: str = RECOVERY_WINDOW_ACTIVATION_BUDGET_VERSION
    recovery_window_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=RECOVERY_WINDOW_ACTIVATION_BUDGET_VERSION,
            ),
        )
        budget = _positive(
            self.recovery_activation_budget_hours,
            field_name="recovery_activation_budget_hours",
        )
        window = _positive(
            self.recovery_window_hours,
            field_name="recovery_window_hours",
        )
        if budget > window:
            raise RobustFCRValidationError(
                "recovery_activation_budget_hours cannot exceed recovery_window_hours"
            )
        if not math.isclose(window / 0.25, round(window / 0.25), abs_tol=1e-12):
            raise RobustFCRValidationError(
                "recovery_window_hours must align to the PT15M planning grid"
            )
        lower = _finite(
            self.pointwise_activation_lower,
            field_name="pointwise_activation_lower",
        )
        upper = _finite(
            self.pointwise_activation_upper,
            field_name="pointwise_activation_upper",
        )
        if lower != -1.0 or upper != 1.0:
            raise RobustFCRValidationError(
                "public v1 pointwise activation bounds must be exactly [-1, 1]"
            )
        object.__setattr__(self, "recovery_activation_budget_hours", budget)
        object.__setattr__(self, "recovery_window_hours", window)
        object.__setattr__(self, "pointwise_activation_lower", lower)
        object.__setattr__(self, "pointwise_activation_upper", upper)
        object.__setattr__(
            self,
            "recovery_window_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "recovery_activation_budget_hours": self.recovery_activation_budget_hours,
            "recovery_window_hours": self.recovery_window_hours,
            "pointwise_activation_lower": self.pointwise_activation_lower,
            "pointwise_activation_upper": self.pointwise_activation_upper,
            "units": {
                "activation_budget": "h",
                "window": "h",
                "pointwise_activation": "dimensionless",
            },
            "source_refs": [
                "baselines/robust_storage_bidding/code/01_datastruct.jl:8-9",
                "baselines/robust_storage_bidding/code/12.jl:30-33",
            ],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "recovery_window_fingerprint": self.recovery_window_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class HorizonWideActivationBudget:
    horizon_hours: float
    horizon_activation_budget_hours: float
    derivation_rule: str
    recovery_window_fingerprint: str
    derivation_inputs: Mapping[str, object]
    semantics_version: str = HORIZON_WIDE_ACTIVATION_BUDGET_VERSION
    horizon_budget_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=HORIZON_WIDE_ACTIVATION_BUDGET_VERSION,
            ),
        )
        horizon = _positive(self.horizon_hours, field_name="horizon_hours")
        if horizon != 24.0:
            raise RobustFCRValidationError("public v1 horizon_hours must equal 24")
        budget = _non_negative(
            self.horizon_activation_budget_hours,
            field_name="horizon_activation_budget_hours",
        )
        if budget > horizon:
            raise RobustFCRValidationError(
                "horizon_activation_budget_hours cannot exceed horizon_hours"
            )
        if self.derivation_rule != HORIZON_BUDGET_DERIVATION_RULE:
            raise RobustFCRValidationError("unsupported horizon-budget derivation rule")
        source_fingerprint = _sha256(
            self.recovery_window_fingerprint,
            field_name="recovery_window_fingerprint",
        )
        derivation_inputs = _deep_freeze(
            self.derivation_inputs,
            field_name="derivation_inputs",
        )
        expected_input_names = {
            "horizon_hours",
            "recovery_window_hours",
            "recovery_activation_budget_hours",
            "full_window_count",
            "remainder_hours",
        }
        if set(derivation_inputs) != expected_input_names:
            raise RobustFCRValidationError(
                "derivation_inputs must contain the exact covering-rule inputs"
            )
        input_horizon = _positive(
            derivation_inputs["horizon_hours"],
            field_name="derivation_inputs.horizon_hours",
        )
        input_window = _positive(
            derivation_inputs["recovery_window_hours"],
            field_name="derivation_inputs.recovery_window_hours",
        )
        input_budget = _positive(
            derivation_inputs["recovery_activation_budget_hours"],
            field_name="derivation_inputs.recovery_activation_budget_hours",
        )
        full_windows = _integer(
            derivation_inputs["full_window_count"],
            field_name="derivation_inputs.full_window_count",
            minimum=0,
        )
        remainder = _non_negative(
            derivation_inputs["remainder_hours"],
            field_name="derivation_inputs.remainder_hours",
        )
        expected_full_windows = math.floor(input_horizon / input_window)
        expected_remainder = input_horizon - expected_full_windows * input_window
        expected_budget = expected_full_windows * input_budget + min(
            expected_remainder,
            input_budget,
        )
        if (
            input_horizon != horizon
            or input_budget > input_window
            or full_windows != expected_full_windows
            or not math.isclose(remainder, expected_remainder, abs_tol=1e-12)
        ):
            raise RobustFCRValidationError(
                "derivation_inputs do not reconcile with the covering rule"
            )
        if not math.isclose(budget, expected_budget, abs_tol=1e-12):
            raise RobustFCRValidationError(
                "derived horizon activation budget does not reconcile with derivation_inputs"
            )
        object.__setattr__(self, "horizon_hours", horizon)
        object.__setattr__(self, "horizon_activation_budget_hours", budget)
        object.__setattr__(self, "recovery_window_fingerprint", source_fingerprint)
        object.__setattr__(self, "derivation_inputs", derivation_inputs)
        object.__setattr__(
            self,
            "horizon_budget_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "horizon_hours": self.horizon_hours,
            "horizon_activation_budget_hours": self.horizon_activation_budget_hours,
            "derivation_rule": self.derivation_rule,
            "recovery_window_fingerprint": self.recovery_window_fingerprint,
            "derivation_inputs": _thaw(self.derivation_inputs),
            "unit": "h",
            "source_refs": [
                "baselines/robust_storage_bidding/code/02_model.jl:293-305"
            ],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "horizon_budget_fingerprint": self.horizon_budget_fingerprint,
        }


def derive_non_intraday_horizon_budget(
    recovery_window: RecoveryWindowActivationBudget,
    *,
    horizon_hours: float = 24.0,
    semantics_version: str = HORIZON_WIDE_ACTIVATION_BUDGET_VERSION,
) -> HorizonWideActivationBudget:
    if not isinstance(recovery_window, RecoveryWindowActivationBudget):
        raise RobustFCRValidationError(
            "recovery_window must be RecoveryWindowActivationBudget"
        )
    horizon = _positive(horizon_hours, field_name="horizon_hours")
    window = recovery_window.recovery_window_hours
    budget = recovery_window.recovery_activation_budget_hours
    full_windows = math.floor(horizon / window)
    remainder = horizon - full_windows * window
    derived = full_windows * budget + min(remainder, budget)
    return HorizonWideActivationBudget(
        horizon_hours=horizon,
        horizon_activation_budget_hours=derived,
        derivation_rule=HORIZON_BUDGET_DERIVATION_RULE,
        recovery_window_fingerprint=recovery_window.recovery_window_fingerprint,
        derivation_inputs={
            "horizon_hours": horizon,
            "recovery_window_hours": window,
            "recovery_activation_budget_hours": budget,
            "full_window_count": full_windows,
            "remainder_hours": remainder,
        },
        semantics_version=semantics_version,
    )


@dataclass(frozen=True, slots=True)
class RobustFCRUncertaintyProfile:
    recovery_window: RecoveryWindowActivationBudget
    horizon_wide: HorizonWideActivationBudget
    semantics_version: str = ROBUST_FCR_UNCERTAINTY_PROFILE_VERSION
    uncertainty_profile_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_UNCERTAINTY_PROFILE_VERSION,
            ),
        )
        if not isinstance(self.recovery_window, RecoveryWindowActivationBudget):
            raise RobustFCRValidationError("recovery_window has the wrong contract type")
        if not isinstance(self.horizon_wide, HorizonWideActivationBudget):
            raise RobustFCRValidationError("horizon_wide has the wrong contract type")
        expected = derive_non_intraday_horizon_budget(self.recovery_window)
        if (
            self.horizon_wide.recovery_window_fingerprint
            != self.recovery_window.recovery_window_fingerprint
            or self.horizon_wide.horizon_activation_budget_hours
            != expected.horizon_activation_budget_hours
            or self.horizon_wide.derivation_rule != expected.derivation_rule
        ):
            raise RobustFCRValidationError(
                "horizon_wide budget does not reconcile with recovery_window lineage"
            )
        object.__setattr__(
            self,
            "uncertainty_profile_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "recovery_window": self.recovery_window.to_dict(),
            "horizon_wide": self.horizon_wide.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "uncertainty_profile_fingerprint": self.uncertainty_profile_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class TerminalStoredEnergyRule:
    minimum_terminal_stored_energy_kwh: float
    allow_penalized_shortfall: bool
    shortfall_penalty_eur_per_kwh: float
    rule_id: str
    semantics_version: str = TERMINAL_STORED_ENERGY_RULE_VERSION
    rule_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=TERMINAL_STORED_ENERGY_RULE_VERSION,
            ),
        )
        target = _non_negative(
            self.minimum_terminal_stored_energy_kwh,
            field_name="minimum_terminal_stored_energy_kwh",
        )
        if not isinstance(self.allow_penalized_shortfall, bool):
            raise RobustFCRValidationError(
                "allow_penalized_shortfall must be a boolean"
            )
        penalty = _positive(
            self.shortfall_penalty_eur_per_kwh,
            field_name="shortfall_penalty_eur_per_kwh",
        )
        rule_id = _non_empty(self.rule_id, field_name="rule_id")
        object.__setattr__(self, "minimum_terminal_stored_energy_kwh", target)
        object.__setattr__(self, "shortfall_penalty_eur_per_kwh", penalty)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "rule_fingerprint", _fingerprint(self._semantic_payload()))

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "minimum_terminal_stored_energy_kwh": (
                self.minimum_terminal_stored_energy_kwh
            ),
            "allow_penalized_shortfall": self.allow_penalized_shortfall,
            "shortfall_penalty_eur_per_kwh": self.shortfall_penalty_eur_per_kwh,
            "rule_id": self.rule_id,
            "units": {"stored_energy": "kWh", "shortfall_penalty": "EUR/kWh"},
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_payload(), "rule_fingerprint": self.rule_fingerprint}


@dataclass(frozen=True, slots=True)
class RobustFCRPriceInputs:
    day_ahead_energy_prices_eur_per_kwh: tuple[float, ...]
    fcr_capacity_prices_eur_per_kw_block: tuple[float, ...]
    energy_interval_refs: tuple[str, ...]
    fcr_interval_refs: tuple[str, ...]
    semantics_version: str = ROBUST_FCR_PRICE_INPUTS_VERSION
    price_input_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_PRICE_INPUTS_VERSION,
            ),
        )
        day_ahead = _finite_tuple(
            self.day_ahead_energy_prices_eur_per_kwh,
            field_name="day_ahead_energy_prices_eur_per_kwh",
            count=24,
        )
        fcr = _finite_tuple(
            self.fcr_capacity_prices_eur_per_kw_block,
            field_name="fcr_capacity_prices_eur_per_kw_block",
            count=6,
        )
        energy_refs = _string_tuple(
            self.energy_interval_refs,
            field_name="energy_interval_refs",
            count=24,
        )
        fcr_refs = _string_tuple(
            self.fcr_interval_refs,
            field_name="fcr_interval_refs",
            count=6,
        )
        object.__setattr__(self, "day_ahead_energy_prices_eur_per_kwh", day_ahead)
        object.__setattr__(self, "fcr_capacity_prices_eur_per_kw_block", fcr)
        object.__setattr__(self, "energy_interval_refs", energy_refs)
        object.__setattr__(self, "fcr_interval_refs", fcr_refs)
        object.__setattr__(
            self,
            "price_input_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "day_ahead_energy_prices_eur_per_kwh": list(
                self.day_ahead_energy_prices_eur_per_kwh
            ),
            "fcr_capacity_prices_eur_per_kw_block": list(
                self.fcr_capacity_prices_eur_per_kw_block
            ),
            "energy_interval_refs": list(self.energy_interval_refs),
            "fcr_interval_refs": list(self.fcr_interval_refs),
            "units": {
                "day_ahead_energy": "EUR/kWh",
                "fcr_capacity": "EUR/kW/4h-block",
            },
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "price_input_fingerprint": self.price_input_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RobustFCRSolvePolicy:
    solver_name: str
    time_limit_seconds: float
    threads: int
    random_seed: int
    primal_feasibility_tolerance: float
    dual_feasibility_tolerance: float
    mip_feasibility_tolerance: float
    relative_mip_gap: float
    objective_comparison_absolute_tolerance_eur: float = 1e-6
    objective_comparison_relative_tolerance: float = 1e-9
    allow_feasible_incumbent_plan: bool = False
    decision_canonicalization_id: str = DECISION_CANONICALIZATION_ID
    semantics_version: str = ROBUST_FCR_SOLVE_POLICY_VERSION
    solve_policy_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_SOLVE_POLICY_VERSION,
            ),
        )
        solver_name = _non_empty(self.solver_name, field_name="solver_name").lower()
        if solver_name not in {"highs", "gurobi"}:
            raise RobustFCRValidationError("solver_name must be highs or gurobi")
        time_limit = _positive(
            self.time_limit_seconds,
            field_name="time_limit_seconds",
        )
        threads = _integer(self.threads, field_name="threads", minimum=1)
        seed = _integer(self.random_seed, field_name="random_seed")
        primal = _positive(
            self.primal_feasibility_tolerance,
            field_name="primal_feasibility_tolerance",
        )
        dual = _positive(
            self.dual_feasibility_tolerance,
            field_name="dual_feasibility_tolerance",
        )
        mip_feasibility = _positive(
            self.mip_feasibility_tolerance,
            field_name="mip_feasibility_tolerance",
        )
        relative_gap = _non_negative(
            self.relative_mip_gap,
            field_name="relative_mip_gap",
        )
        objective_absolute = _non_negative(
            self.objective_comparison_absolute_tolerance_eur,
            field_name="objective_comparison_absolute_tolerance_eur",
        )
        objective_relative = _non_negative(
            self.objective_comparison_relative_tolerance,
            field_name="objective_comparison_relative_tolerance",
        )
        if not isinstance(self.allow_feasible_incumbent_plan, bool):
            raise RobustFCRValidationError(
                "allow_feasible_incumbent_plan must be a boolean"
            )
        if self.decision_canonicalization_id != DECISION_CANONICALIZATION_ID:
            raise RobustFCRValidationError(
                "decision_canonicalization_id is an unsupported canonicalization"
            )
        object.__setattr__(self, "solver_name", solver_name)
        object.__setattr__(self, "time_limit_seconds", time_limit)
        object.__setattr__(self, "threads", threads)
        object.__setattr__(self, "random_seed", seed)
        object.__setattr__(self, "primal_feasibility_tolerance", primal)
        object.__setattr__(self, "dual_feasibility_tolerance", dual)
        object.__setattr__(self, "mip_feasibility_tolerance", mip_feasibility)
        object.__setattr__(self, "relative_mip_gap", relative_gap)
        object.__setattr__(
            self,
            "objective_comparison_absolute_tolerance_eur",
            objective_absolute,
        )
        object.__setattr__(
            self,
            "objective_comparison_relative_tolerance",
            objective_relative,
        )
        object.__setattr__(
            self,
            "solve_policy_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def objective_comparison_allowance(self, a: float, b: float) -> float:
        left = _finite(a, field_name="objective comparison a")
        right = _finite(b, field_name="objective comparison b")
        return max(
            self.objective_comparison_absolute_tolerance_eur,
            self.objective_comparison_relative_tolerance
            * max(abs(left), abs(right), 1.0),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "solver_name": self.solver_name,
            "time_limit_seconds": self.time_limit_seconds,
            "threads": self.threads,
            "random_seed": self.random_seed,
            "primal_feasibility_tolerance": self.primal_feasibility_tolerance,
            "dual_feasibility_tolerance": self.dual_feasibility_tolerance,
            "mip_feasibility_tolerance": self.mip_feasibility_tolerance,
            "relative_mip_gap": self.relative_mip_gap,
            "objective_comparison_absolute_tolerance_eur": (
                self.objective_comparison_absolute_tolerance_eur
            ),
            "objective_comparison_relative_tolerance": (
                self.objective_comparison_relative_tolerance
            ),
            "allow_feasible_incumbent_plan": self.allow_feasible_incumbent_plan,
            "decision_canonicalization_id": self.decision_canonicalization_id,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "solve_policy_fingerprint": self.solve_policy_fingerprint,
        }


_DECISION_CUTOFF_FORBIDDEN_TERMS = (
    "activation",
    "realized",
    "expected",
    "replay",
    "comparison",
    "parity",
    "external",
    "credential",
    "token",
    "secret",
)


def _validate_decision_visible_mapping(
    value: Mapping[str, object],
    *,
    field_name: str,
) -> Mapping[str, object]:
    for key, inner in value.items():
        normalized_key = _non_empty(key, field_name=f"{field_name} key")
        lowered = normalized_key.casefold()
        if any(term in lowered for term in _DECISION_CUTOFF_FORBIDDEN_TERMS):
            raise RobustFCRValidationError(
                f"{field_name}.{normalized_key} violates the declared decision cutoff"
            )
        if isinstance(inner, Mapping):
            _validate_decision_visible_mapping(
                inner,
                field_name=f"{field_name}.{normalized_key}",
            )
    return _deep_freeze(value, field_name=field_name)


@dataclass(frozen=True, slots=True)
class RobustFCRBiddingProblem:
    problem_id: str
    battery: RobustFCRBatteryParameters
    time_contract: RobustFCRTimeContract
    prices: RobustFCRPriceInputs
    uncertainty: RobustFCRUncertaintyProfile
    terminal_rule: TerminalStoredEnergyRule
    solve_policy: RobustFCRSolvePolicy
    information_cutoff_utc: datetime
    producer_input_fingerprints: Mapping[str, str]
    provenance: Mapping[str, object]
    semantics_version: str = ROBUST_FCR_BIDDING_PROBLEM_VERSION
    problem_fingerprint: str = field(init=False)
    comparison_problem_fingerprint: str = field(init=False)
    objective_comparison_policy_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", _non_empty(self.problem_id, field_name="problem_id"))
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_BIDDING_PROBLEM_VERSION,
            ),
        )
        expected_types = (
            ("battery", self.battery, RobustFCRBatteryParameters),
            ("time_contract", self.time_contract, RobustFCRTimeContract),
            ("prices", self.prices, RobustFCRPriceInputs),
            ("uncertainty", self.uncertainty, RobustFCRUncertaintyProfile),
            ("terminal_rule", self.terminal_rule, TerminalStoredEnergyRule),
            ("solve_policy", self.solve_policy, RobustFCRSolvePolicy),
        )
        for name, value, expected in expected_types:
            if not isinstance(value, expected):
                raise RobustFCRValidationError(f"{name} has the wrong contract type")
        if self.uncertainty.horizon_wide.horizon_hours != 24.0:
            raise RobustFCRValidationError(
                "uncertainty horizon must match the 24-hour time contract"
            )
        target = self.terminal_rule.minimum_terminal_stored_energy_kwh
        if not (
            self.battery.minimum_stored_energy_kwh
            <= target
            <= self.battery.maximum_stored_energy_kwh
        ):
            raise RobustFCRValidationError(
                "terminal stored energy must lie within battery bounds"
            )
        cutoff = _utc(
            self.information_cutoff_utc,
            field_name="information_cutoff_utc",
        )
        if cutoff > self.time_contract.delivery_period.start_utc:
            raise RobustFCRValidationError(
                "information cutoff cannot be after delivery starts"
            )
        if not isinstance(self.producer_input_fingerprints, Mapping):
            raise RobustFCRValidationError(
                "producer_input_fingerprints must be a mapping"
            )
        inputs: dict[str, str] = {}
        for key, value in self.producer_input_fingerprints.items():
            normalized_key = _non_empty(
                key,
                field_name="producer_input_fingerprints key",
            )
            if any(
                term in normalized_key.casefold()
                for term in _DECISION_CUTOFF_FORBIDDEN_TERMS
            ):
                raise RobustFCRValidationError(
                    f"producer_input_fingerprints.{normalized_key} violates the declared decision cutoff"
                )
            inputs[normalized_key] = _sha256(
                value,
                field_name=f"producer_input_fingerprints.{normalized_key}",
            )
        provenance = _validate_decision_visible_mapping(
            self.provenance,
            field_name="provenance",
        )
        object.__setattr__(self, "information_cutoff_utc", cutoff)
        object.__setattr__(
            self,
            "producer_input_fingerprints",
            MappingProxyType(dict(sorted(inputs.items()))),
        )
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "problem_fingerprint",
            _fingerprint(self._semantic_payload()),
        )
        comparison_payload = self._semantic_payload()
        comparison_payload.pop("solve_policy")
        object.__setattr__(
            self,
            "comparison_problem_fingerprint",
            _fingerprint(comparison_payload),
        )
        object.__setattr__(
            self,
            "objective_comparison_policy_fingerprint",
            _fingerprint(
                {
                    "absolute_tolerance_eur": (
                        self.solve_policy.objective_comparison_absolute_tolerance_eur
                    ),
                    "relative_tolerance": (
                        self.solve_policy.objective_comparison_relative_tolerance
                    ),
                }
            ),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "problem_id": self.problem_id,
            "semantics_version": self.semantics_version,
            "battery": self.battery.to_dict(),
            "time_contract": self.time_contract.to_dict(),
            "prices": self.prices.to_dict(),
            "uncertainty": self.uncertainty.to_dict(),
            "terminal_rule": self.terminal_rule.to_dict(),
            "solve_policy": self.solve_policy.to_dict(),
            "information_cutoff_utc": _utc_text(self.information_cutoff_utc),
            "producer_input_fingerprints": dict(self.producer_input_fingerprints),
            "provenance": _thaw(self.provenance),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "problem_fingerprint": self.problem_fingerprint,
            "comparison_problem_fingerprint": self.comparison_problem_fingerprint,
            "objective_comparison_policy_fingerprint": (
                self.objective_comparison_policy_fingerprint
            ),
        }


def build_robust_fcr_bidding_problem(
    *,
    problem_id: str,
    battery: RobustFCRBatteryParameters,
    time_contract: RobustFCRTimeContract,
    prices: RobustFCRPriceInputs,
    uncertainty: RobustFCRUncertaintyProfile,
    terminal_rule: TerminalStoredEnergyRule,
    solve_policy: RobustFCRSolvePolicy,
    information_cutoff_utc: datetime,
    producer_input_fingerprints: Mapping[str, str],
    provenance: Mapping[str, object],
    semantics_version: str = ROBUST_FCR_BIDDING_PROBLEM_VERSION,
) -> RobustFCRBiddingProblem:
    return RobustFCRBiddingProblem(
        problem_id=problem_id,
        battery=battery,
        time_contract=time_contract,
        prices=prices,
        uncertainty=uncertainty,
        terminal_rule=terminal_rule,
        solve_policy=solve_policy,
        information_cutoff_utc=information_cutoff_utc,
        producer_input_fingerprints=producer_input_fingerprints,
        provenance=provenance,
        semantics_version=semantics_version,
    )


@dataclass(frozen=True, slots=True)
class RobustFCRFormulationProfile:
    kind: str
    equation_version: str
    objective_sense: str
    deployability_role: str
    source_refs: tuple[str, ...]
    semantics_version: str = ROBUST_FCR_FORMULATION_PROFILE_VERSION
    formulation_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        roles = {
            "restriction": "candidate_plan",
            "relaxation": "upper_bound_only",
            "exact": "exact_evidence_only",
        }
        if self.kind not in roles:
            raise RobustFCRValidationError(
                "formulation kind must be restriction, relaxation, or exact"
            )
        if self.deployability_role != roles[self.kind]:
            raise RobustFCRValidationError(
                "formulation deployability role does not match its kind"
            )
        if self.objective_sense != "maximize":
            raise RobustFCRValidationError("formulation objective_sense must be maximize")
        object.__setattr__(
            self,
            "equation_version",
            _non_empty(self.equation_version, field_name="equation_version"),
        )
        object.__setattr__(
            self,
            "source_refs",
            _string_tuple(self.source_refs, field_name="source_refs"),
        )
        if not self.source_refs:
            raise RobustFCRValidationError("source_refs must not be empty")
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_FORMULATION_PROFILE_VERSION,
            ),
        )
        object.__setattr__(
            self,
            "formulation_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    @classmethod
    def for_kind(cls, kind: str) -> RobustFCRFormulationProfile:
        roles = {
            "restriction": "candidate_plan",
            "relaxation": "upper_bound_only",
            "exact": "exact_evidence_only",
        }
        if kind not in roles:
            raise RobustFCRValidationError(
                "formulation kind must be restriction, relaxation, or exact"
            )
        common = "baselines/robust_storage_bidding/code/02_model.jl:170-219,252-263"
        specific = {
            "restriction": (
                "baselines/robust_storage_bidding/code/02_model.jl:225-230"
            ),
            "relaxation": (
                "baselines/robust_storage_bidding/code/02_model.jl:205-219"
            ),
            "exact": "baselines/robust_storage_bidding/code/02_model.jl:220-224",
        }
        return cls(
            kind=kind,
            equation_version="robust-storage-bidding-non-intraday-milp-v1",
            objective_sense="maximize",
            deployability_role=roles[kind],
            source_refs=(common, specific[kind]),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "kind": self.kind,
            "equation_version": self.equation_version,
            "objective_sense": self.objective_sense,
            "deployability_role": self.deployability_role,
            "source_refs": list(self.source_refs),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "formulation_fingerprint": self.formulation_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RobustFCRDecisions:
    energy_baseline_charge_positive_kw: tuple[float, ...]
    fcr_capacity_kw: tuple[float, ...]
    canonicalization_id: str = DECISION_CANONICALIZATION_ID
    energy_decision_content_fingerprint: str = field(init=False)
    fcr_decision_content_fingerprint: str = field(init=False)
    decision_vector_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.canonicalization_id != DECISION_CANONICALIZATION_ID:
            raise RobustFCRValidationError("unsupported decision canonicalization")
        energy = _finite_tuple(
            self.energy_baseline_charge_positive_kw,
            field_name="energy_baseline_charge_positive_kw",
            count=24,
        )
        fcr = _finite_tuple(
            self.fcr_capacity_kw,
            field_name="fcr_capacity_kw",
            count=6,
        )
        if any(value < 0.0 for value in fcr):
            raise RobustFCRValidationError("fcr_capacity_kw must be non-negative")
        object.__setattr__(self, "energy_baseline_charge_positive_kw", energy)
        object.__setattr__(self, "fcr_capacity_kw", fcr)
        energy_payload = {
            "sign": "positive_is_charge",
            "unit": "kW",
            "resolution": "PT1H",
            "values": list(energy),
            "canonicalization_id": self.canonicalization_id,
        }
        fcr_payload = {
            "sign": "non_negative_symmetric_capacity",
            "unit": "kW",
            "resolution": "PT4H",
            "values": list(fcr),
            "canonicalization_id": self.canonicalization_id,
        }
        object.__setattr__(
            self,
            "energy_decision_content_fingerprint",
            _fingerprint(energy_payload),
        )
        object.__setattr__(
            self,
            "fcr_decision_content_fingerprint",
            _fingerprint(fcr_payload),
        )
        object.__setattr__(
            self,
            "decision_vector_fingerprint",
            _fingerprint({"energy": energy_payload, "fcr": fcr_payload}),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "energy_baseline_charge_positive_kw": list(
                self.energy_baseline_charge_positive_kw
            ),
            "fcr_capacity_kw": list(self.fcr_capacity_kw),
            "canonicalization_id": self.canonicalization_id,
            "energy_decision_content_fingerprint": (
                self.energy_decision_content_fingerprint
            ),
            "fcr_decision_content_fingerprint": self.fcr_decision_content_fingerprint,
            "decision_vector_fingerprint": self.decision_vector_fingerprint,
            "units": {"energy_baseline": "kW", "fcr_capacity": "kW"},
            "signs": {
                "energy_baseline": "positive_is_charge",
                "fcr_capacity": "non_negative_symmetric_capacity",
            },
        }


@dataclass(frozen=True, slots=True)
class ObjectiveBreakdown:
    day_ahead_energy_value_eur: float
    fcr_capacity_value_eur: float
    feasibility_slack_penalty_eur: float
    total_objective_eur: float
    reconciliation_residual_eur: float

    def __post_init__(self) -> None:
        for name in (
            "day_ahead_energy_value_eur",
            "fcr_capacity_value_eur",
            "feasibility_slack_penalty_eur",
            "total_objective_eur",
            "reconciliation_residual_eur",
        ):
            normalized = _finite(getattr(self, name), field_name=name)
            if name in {
                "feasibility_slack_penalty_eur",
                "reconciliation_residual_eur",
            } and normalized < 0.0:
                raise RobustFCRValidationError(f"{name} must be non-negative")
            object.__setattr__(self, name, normalized)

    def to_dict(self) -> dict[str, object]:
        components = {
            "day_ahead_energy_value": {
                "value": self.day_ahead_energy_value_eur,
                "unit": "EUR",
                "formula": "delta_t_hours * sum(day_ahead_price_eur_per_kwh * source_x0_kw)",
            },
            "fcr_capacity_value": {
                "value": self.fcr_capacity_value_eur,
                "unit": "EUR",
                "formula": "sum(fcr_capacity_price_eur_per_kw_block * xr_kw)",
            },
            "feasibility_slack_penalty": {
                "value": self.feasibility_slack_penalty_eur,
                "unit": "EUR",
                "formula": "shortfall_penalty_eur_per_kwh * sum(modeled_energy_slacks_kwh)",
            },
            "total": {
                "value": self.total_objective_eur,
                "unit": "EUR",
                "formula": "day_ahead_energy_value + fcr_capacity_value - feasibility_slack_penalty",
            },
        }
        return {
            "day_ahead_energy_value_eur": self.day_ahead_energy_value_eur,
            "fcr_capacity_value_eur": self.fcr_capacity_value_eur,
            "feasibility_slack_penalty_eur": self.feasibility_slack_penalty_eur,
            "total_objective_eur": self.total_objective_eur,
            "reconciliation_residual_eur": self.reconciliation_residual_eur,
            "unit": "EUR",
            "meaning": "ex_ante_optimization_objective",
            "components": components,
            "source_refs": [
                "baselines/robust_storage_bidding/code/02_model.jl:252-263"
            ],
            "excluded_realized_fields": [
                "activation_energy_revenue_eur",
                "realized_settlement_eur",
                "realized_profit_eur",
            ],
        }


@dataclass(frozen=True, slots=True)
class ConstraintFamilyResidual:
    family_id: str
    relation: str
    canonical_unit: str
    checked_count: int
    maximum_positive_violation: float
    witness_indices: tuple[tuple[int, ...], ...]
    source_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_id", _non_empty(self.family_id, field_name="family_id"))
        if self.relation not in {"<=", ">=", "==", "bounds", "integrality"}:
            raise RobustFCRValidationError("unsupported residual relation")
        if self.canonical_unit not in {"kW", "kWh", "EUR", "dimensionless"}:
            raise RobustFCRValidationError("unsupported residual canonical_unit")
        object.__setattr__(
            self,
            "checked_count",
            _integer(self.checked_count, field_name="checked_count", minimum=0),
        )
        violation = _non_negative(
            self.maximum_positive_violation,
            field_name="maximum_positive_violation",
        )
        object.__setattr__(self, "maximum_positive_violation", violation)
        indices: list[tuple[int, ...]] = []
        for raw in self.witness_indices:
            indices.append(
                tuple(
                    _integer(value, field_name="witness index", minimum=0)
                    for value in raw
                )
            )
        object.__setattr__(self, "witness_indices", tuple(indices))
        object.__setattr__(
            self,
            "source_refs",
            _string_tuple(self.source_refs, field_name="source_refs"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "relation": self.relation,
            "canonical_unit": self.canonical_unit,
            "checked_count": self.checked_count,
            "maximum_positive_violation": self.maximum_positive_violation,
            "witness_indices": [list(value) for value in self.witness_indices],
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class FeasibilityAudit:
    constraint_families: tuple[ConstraintFamilyResidual, ...]
    modeled_slacks: Mapping[str, float]
    raw_witness_fingerprint: str
    canonical_witness_fingerprint: str
    deployability_threshold: float
    passes_deployability_audit: bool
    audit_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        families = tuple(self.constraint_families)
        if any(not isinstance(value, ConstraintFamilyResidual) for value in families):
            raise RobustFCRValidationError(
                "constraint_families must contain ConstraintFamilyResidual values"
            )
        if tuple(value.family_id for value in families) != tuple(
            sorted(value.family_id for value in families)
        ):
            raise RobustFCRValidationError("constraint_families must be deterministically ordered")
        slacks: dict[str, float] = {}
        for name, value in self.modeled_slacks.items():
            slacks[_non_empty(name, field_name="modeled slack name")] = _non_negative(
                value,
                field_name=f"modeled_slacks.{name}",
            )
        threshold = _finite(
            self.deployability_threshold,
            field_name="deployability_threshold",
        )
        if threshold != DEPLOYABILITY_THRESHOLD:
            raise RobustFCRValidationError(
                f"deployability_threshold must equal {DEPLOYABILITY_THRESHOLD}"
            )
        object.__setattr__(self, "constraint_families", families)
        object.__setattr__(
            self,
            "modeled_slacks",
            MappingProxyType(dict(sorted(slacks.items()))),
        )
        object.__setattr__(
            self,
            "raw_witness_fingerprint",
            _sha256(self.raw_witness_fingerprint, field_name="raw_witness_fingerprint"),
        )
        object.__setattr__(
            self,
            "canonical_witness_fingerprint",
            _sha256(
                self.canonical_witness_fingerprint,
                field_name="canonical_witness_fingerprint",
            ),
        )
        if not isinstance(self.passes_deployability_audit, bool):
            raise RobustFCRValidationError(
                "passes_deployability_audit must be a boolean"
            )
        object.__setattr__(
            self,
            "audit_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "constraint_families": [value.to_dict() for value in self.constraint_families],
            "modeled_slacks": dict(self.modeled_slacks),
            "raw_witness_fingerprint": self.raw_witness_fingerprint,
            "canonical_witness_fingerprint": self.canonical_witness_fingerprint,
            "deployability_threshold": self.deployability_threshold,
            "passes_deployability_audit": self.passes_deployability_audit,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._semantic_payload(), "audit_fingerprint": self.audit_fingerprint}


@dataclass(frozen=True, slots=True)
class RobustFCRDiagnostic:
    code: str
    severity: str
    field_path: str | None
    message: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _non_empty(self.code, field_name="diagnostic code"))
        if self.severity not in {"info", "warning", "error"}:
            raise RobustFCRValidationError("diagnostic severity is unsupported")
        if self.field_path is not None:
            object.__setattr__(
                self,
                "field_path",
                _non_empty(self.field_path, field_name="diagnostic field_path"),
            )
        object.__setattr__(self, "message", _non_empty(self.message, field_name="diagnostic message"))
        object.__setattr__(
            self,
            "evidence_refs",
            _string_tuple(self.evidence_refs, field_name="diagnostic evidence_refs"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field_path": self.field_path,
            "message": self.message,
            "evidence_refs": list(self.evidence_refs),
        }


def _diagnostic_sort_key(value: RobustFCRDiagnostic) -> tuple[object, ...]:
    return (
        value.field_path or "",
        value.code,
        value.severity,
        value.evidence_refs,
        value.message,
    )


@dataclass(frozen=True, slots=True)
class _GapEvidence:
    absolute_gap_eur: float | None
    relative_gap: float | None
    normalized_negative_gap: bool
    inconsistent_bound: bool


def _normalize_maximization_gap(
    objective_value_eur: float | None,
    best_upper_bound_eur: float | None,
    policy: RobustFCRSolvePolicy,
) -> _GapEvidence:
    if objective_value_eur is None or best_upper_bound_eur is None:
        return _GapEvidence(None, None, False, False)
    objective = _finite(objective_value_eur, field_name="objective_value_eur")
    bound = _finite(best_upper_bound_eur, field_name="best_upper_bound_eur")
    raw_gap = bound - objective
    allowance = policy.objective_comparison_allowance(objective, bound)
    if raw_gap < -allowance:
        return _GapEvidence(None, None, False, True)
    normalized_negative = raw_gap < 0.0
    absolute = max(raw_gap, 0.0)
    relative = absolute / max(abs(objective), abs(bound), 1.0)
    return _GapEvidence(absolute, relative, normalized_negative, False)


@dataclass(frozen=True, slots=True)
class SolverEvidence:
    solve_status: str
    termination_status: str
    has_incumbent: bool
    incumbent_accepted: bool
    objective_value_eur: float | None
    best_upper_bound_eur: float | None
    absolute_gap_eur: float | None
    relative_gap: float | None
    solver_name: str
    solver_version: str | None
    pyomo_version: str | None
    highspy_version: str | None
    configured_options: Mapping[str, object]
    model_cardinality: Mapping[str, int]
    runtime_seconds: float | None

    def __post_init__(self) -> None:
        if self.solve_status not in {
            "optimal",
            "feasible",
            "no_solution",
            "infeasible",
            "unbounded",
            "failed",
            "unavailable",
        }:
            raise RobustFCRValidationError("unsupported solve_status")
        object.__setattr__(
            self,
            "termination_status",
            _non_empty(self.termination_status, field_name="termination_status"),
        )
        object.__setattr__(self, "solver_name", _non_empty(self.solver_name, field_name="solver_name"))
        for name in (
            "objective_value_eur",
            "best_upper_bound_eur",
            "absolute_gap_eur",
            "relative_gap",
            "runtime_seconds",
        ):
            value = getattr(self, name)
            if value is not None:
                normalized = _finite(value, field_name=name)
                if name in {"absolute_gap_eur", "relative_gap", "runtime_seconds"} and normalized < 0.0:
                    raise RobustFCRValidationError(f"{name} must be non-negative")
                object.__setattr__(self, name, normalized)
        object.__setattr__(
            self,
            "configured_options",
            _deep_freeze(self.configured_options, field_name="configured_options"),
        )
        object.__setattr__(
            self,
            "model_cardinality",
            MappingProxyType(dict(sorted(self.model_cardinality.items()))),
        )

    def semantic_dict(self) -> dict[str, object]:
        return {
            "solve_status": self.solve_status,
            "termination_status": self.termination_status,
            "has_incumbent": self.has_incumbent,
            "incumbent_accepted": self.incumbent_accepted,
            "objective_value_eur": self.objective_value_eur,
            "best_upper_bound_eur": self.best_upper_bound_eur,
            "absolute_gap_eur": self.absolute_gap_eur,
            "relative_gap": self.relative_gap,
            "solver_name": self.solver_name,
            "solver_version": self.solver_version,
            "pyomo_version": self.pyomo_version,
            "highspy_version": self.highspy_version,
            "configured_options": _thaw(self.configured_options),
            "model_cardinality": dict(self.model_cardinality),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.semantic_dict(), "runtime_seconds": self.runtime_seconds}


@dataclass(frozen=True, slots=True)
class RobustFCRSolveResult:
    problem_fingerprint: str
    comparison_problem_fingerprint: str
    objective_comparison_policy_fingerprint: str
    formulation: RobustFCRFormulationProfile
    solver: SolverEvidence
    raw_objective: ObjectiveBreakdown | None
    decisions: RobustFCRDecisions | None
    feasibility_audit: FeasibilityAudit | None
    deployability_status: str
    deployability_reasons: tuple[str, ...]
    deployable_plan: Any | None
    diagnostics: tuple[RobustFCRDiagnostic, ...]
    runtime_metadata: Mapping[str, object]
    semantics_version: str = ROBUST_FCR_SOLVE_RESULT_VERSION
    semantic_result_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "problem_fingerprint",
            _sha256(self.problem_fingerprint, field_name="problem_fingerprint"),
        )
        object.__setattr__(
            self,
            "comparison_problem_fingerprint",
            _sha256(
                self.comparison_problem_fingerprint,
                field_name="comparison_problem_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "objective_comparison_policy_fingerprint",
            _sha256(
                self.objective_comparison_policy_fingerprint,
                field_name="objective_comparison_policy_fingerprint",
            ),
        )
        if not isinstance(self.formulation, RobustFCRFormulationProfile):
            raise RobustFCRValidationError("formulation has the wrong contract type")
        if not isinstance(self.solver, SolverEvidence):
            raise RobustFCRValidationError("solver has the wrong contract type")
        if self.deployability_status not in {"eligible", "blocked", "not_applicable"}:
            raise RobustFCRValidationError("unsupported deployability_status")
        if self.formulation.kind == "restriction":
            if self.deployability_status == "not_applicable":
                raise RobustFCRValidationError(
                    "restriction deployability must be eligible or blocked"
                )
        elif self.deployability_status != "not_applicable":
            raise RobustFCRValidationError(
                f"{self.formulation.deployability_role} results are not deployable"
            )
        if self.deployability_status == "eligible":
            if self.deployable_plan is None:
                raise RobustFCRValidationError(
                    "eligible restriction result must contain a deployable plan"
                )
        elif self.deployable_plan is not None:
            raise RobustFCRValidationError(
                "only an eligible restriction result may contain a deployable plan"
            )
        reasons = tuple(
            _non_empty(value, field_name="deployability reason")
            for value in self.deployability_reasons
        )
        diagnostics = tuple(sorted(self.diagnostics, key=_diagnostic_sort_key))
        object.__setattr__(self, "deployability_reasons", reasons)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(
            self,
            "runtime_metadata",
            _deep_freeze(self.runtime_metadata, field_name="runtime_metadata"),
        )
        object.__setattr__(
            self,
            "semantics_version",
            _validate_semantics_version(
                self.semantics_version,
                expected=ROBUST_FCR_SOLVE_RESULT_VERSION,
            ),
        )
        object.__setattr__(
            self,
            "semantic_result_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "problem_fingerprint": self.problem_fingerprint,
            "comparison_problem_fingerprint": self.comparison_problem_fingerprint,
            "objective_comparison_policy_fingerprint": (
                self.objective_comparison_policy_fingerprint
            ),
            "formulation": self.formulation.to_dict(),
            "solver": self.solver.semantic_dict(),
            "raw_objective": (
                self.raw_objective.to_dict() if self.raw_objective is not None else None
            ),
            "decisions": self.decisions.to_dict() if self.decisions is not None else None,
            "feasibility_audit": (
                self.feasibility_audit.to_dict()
                if self.feasibility_audit is not None
                else None
            ),
            "deployability_status": self.deployability_status,
            "deployability_reasons": list(self.deployability_reasons),
            "diagnostics": [value.to_dict() for value in self.diagnostics],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "deployable_plan": (
                self.deployable_plan.to_dict()
                if self.deployable_plan is not None
                else None
            ),
            "semantic_result_fingerprint": self.semantic_result_fingerprint,
            "runtime_metadata": _thaw(self.runtime_metadata),
        }


@dataclass(frozen=True, slots=True)
class RobustFCRBoundInequality:
    lower_label: str
    upper_label: str
    lower_objective_eur: float
    upper_objective_eur: float
    allowance_eur: float
    delta_eur: float
    satisfied: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "lower_label",
            _non_empty(self.lower_label, field_name="lower_label"),
        )
        object.__setattr__(
            self,
            "upper_label",
            _non_empty(self.upper_label, field_name="upper_label"),
        )
        for name in (
            "lower_objective_eur",
            "upper_objective_eur",
            "allowance_eur",
            "delta_eur",
        ):
            normalized = _finite(getattr(self, name), field_name=name)
            if name == "allowance_eur" and normalized < 0.0:
                raise RobustFCRValidationError("allowance_eur must be non-negative")
            object.__setattr__(self, name, normalized)
        if not isinstance(self.satisfied, bool):
            raise RobustFCRValidationError("bound inequality satisfied must be boolean")

    def to_dict(self) -> dict[str, object]:
        return {
            "lower_label": self.lower_label,
            "upper_label": self.upper_label,
            "lower_objective_eur": self.lower_objective_eur,
            "upper_objective_eur": self.upper_objective_eur,
            "allowance_eur": self.allowance_eur,
            "delta_eur": self.delta_eur,
            "satisfied": self.satisfied,
            "relation": "lower <= upper + allowance",
            "unit": "EUR",
        }


@dataclass(frozen=True, slots=True)
class RobustFCRBoundComparison:
    comparison_problem_fingerprint: str
    objective_comparison_policy_fingerprint: str
    restriction_result_fingerprint: str
    relaxation_result_fingerprint: str
    exact_result_fingerprint: str | None
    restriction_le_relaxation: RobustFCRBoundInequality
    restriction_le_exact: RobustFCRBoundInequality | None
    exact_le_relaxation: RobustFCRBoundInequality | None
    exact_status: str
    overall_status: str
    comparison_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "comparison_problem_fingerprint",
            "objective_comparison_policy_fingerprint",
            "restriction_result_fingerprint",
            "relaxation_result_fingerprint",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), field_name=name),
            )
        if self.exact_result_fingerprint is not None:
            object.__setattr__(
                self,
                "exact_result_fingerprint",
                _sha256(
                    self.exact_result_fingerprint,
                    field_name="exact_result_fingerprint",
                ),
            )
        if self.exact_status not in {"satisfied", "violated", "unavailable"}:
            raise RobustFCRValidationError("unsupported exact_status")
        if self.overall_status not in {"satisfied", "violated", "unavailable"}:
            raise RobustFCRValidationError("unsupported bound comparison status")
        object.__setattr__(
            self,
            "comparison_fingerprint",
            _fingerprint(self._semantic_payload()),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "comparison_problem_fingerprint": self.comparison_problem_fingerprint,
            "objective_comparison_policy_fingerprint": (
                self.objective_comparison_policy_fingerprint
            ),
            "restriction_result_fingerprint": self.restriction_result_fingerprint,
            "relaxation_result_fingerprint": self.relaxation_result_fingerprint,
            "exact_result_fingerprint": self.exact_result_fingerprint,
            "restriction_le_relaxation": self.restriction_le_relaxation.to_dict(),
            "restriction_le_exact": (
                self.restriction_le_exact.to_dict()
                if self.restriction_le_exact is not None
                else None
            ),
            "exact_le_relaxation": (
                self.exact_le_relaxation.to_dict()
                if self.exact_le_relaxation is not None
                else None
            ),
            "exact_status": self.exact_status,
            "overall_status": self.overall_status,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "comparison_fingerprint": self.comparison_fingerprint,
        }


def _comparison_policy(result: RobustFCRSolveResult) -> tuple[float, float]:
    options = result.solver.configured_options
    try:
        absolute = _non_negative(
            options["objective_comparison_absolute_tolerance_eur"],
            field_name="objective comparison absolute tolerance",
        )
        relative = _non_negative(
            options["objective_comparison_relative_tolerance"],
            field_name="objective comparison relative tolerance",
        )
    except KeyError as exc:
        raise RobustFCRValidationError(
            "solve result is missing its objective comparison policy"
        ) from exc
    return absolute, relative


def _bound_inequality(
    lower_label: str,
    lower: float,
    upper_label: str,
    upper: float,
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> RobustFCRBoundInequality:
    allowance = max(
        absolute_tolerance,
        relative_tolerance * max(abs(lower), abs(upper), 1.0),
    )
    return RobustFCRBoundInequality(
        lower_label=lower_label,
        upper_label=upper_label,
        lower_objective_eur=lower,
        upper_objective_eur=upper,
        allowance_eur=allowance,
        delta_eur=lower - upper,
        satisfied=lower <= upper + allowance,
    )


def compare_robust_fcr_bounds(
    restriction: RobustFCRSolveResult,
    relaxation: RobustFCRSolveResult,
    *,
    exact: RobustFCRSolveResult | None = None,
) -> RobustFCRBoundComparison:
    """Check formulation roles, compatibility, and maximization objective order."""

    if restriction.formulation.kind != "restriction":
        raise RobustFCRValidationError("first result must use the restriction formulation")
    if relaxation.formulation.kind != "relaxation":
        raise RobustFCRValidationError("second result must use the relaxation formulation")
    if exact is not None and exact.formulation.kind != "exact":
        raise RobustFCRValidationError("exact result must use the exact formulation")
    results = (restriction, relaxation) + ((exact,) if exact is not None else ())
    if len({value.objective_comparison_policy_fingerprint for value in results}) != 1:
        raise RobustFCRValidationError(
            "bound comparison requires an identical objective comparison policy"
        )
    policies = {_comparison_policy(value) for value in results}
    if len(policies) != 1:
        raise RobustFCRValidationError(
            "bound comparison requires an identical objective comparison policy"
        )
    if restriction.problem_fingerprint != relaxation.problem_fingerprint:
        raise RobustFCRValidationError(
            "restriction and relaxation must solve the same complete problem"
        )
    if len({value.comparison_problem_fingerprint for value in results}) != 1:
        raise RobustFCRValidationError(
            "all formulations must solve the same decision problem"
        )
    if restriction.solver.objective_value_eur is None:
        raise RobustFCRValidationError("restriction objective is unavailable")
    if relaxation.solver.objective_value_eur is None:
        raise RobustFCRValidationError("relaxation objective is unavailable")
    absolute, relative = next(iter(policies))
    paired = _bound_inequality(
        "restriction",
        restriction.solver.objective_value_eur,
        "relaxation",
        relaxation.solver.objective_value_eur,
        absolute_tolerance=absolute,
        relative_tolerance=relative,
    )
    restriction_exact: RobustFCRBoundInequality | None = None
    exact_relaxation: RobustFCRBoundInequality | None = None
    if (
        exact is None
        or exact.solver.solve_status not in {"optimal", "feasible"}
        or exact.solver.objective_value_eur is None
    ):
        exact_status = "unavailable"
    else:
        restriction_exact = _bound_inequality(
            "restriction",
            restriction.solver.objective_value_eur,
            "exact",
            exact.solver.objective_value_eur,
            absolute_tolerance=absolute,
            relative_tolerance=relative,
        )
        exact_relaxation = _bound_inequality(
            "exact",
            exact.solver.objective_value_eur,
            "relaxation",
            relaxation.solver.objective_value_eur,
            absolute_tolerance=absolute,
            relative_tolerance=relative,
        )
        exact_status = (
            "satisfied"
            if restriction_exact.satisfied and exact_relaxation.satisfied
            else "violated"
        )
    overall_status = (
        "violated"
        if not paired.satisfied or exact_status == "violated"
        else "satisfied"
    )
    return RobustFCRBoundComparison(
        comparison_problem_fingerprint=restriction.comparison_problem_fingerprint,
        objective_comparison_policy_fingerprint=(
            restriction.objective_comparison_policy_fingerprint
        ),
        restriction_result_fingerprint=restriction.semantic_result_fingerprint,
        relaxation_result_fingerprint=relaxation.semantic_result_fingerprint,
        exact_result_fingerprint=(
            exact.semantic_result_fingerprint if exact is not None else None
        ),
        restriction_le_relaxation=paired,
        restriction_le_exact=restriction_exact,
        exact_le_relaxation=exact_relaxation,
        exact_status=exact_status,
        overall_status=overall_status,
    )


@dataclass(frozen=True, slots=True)
class _WitnessAuditComputation:
    objective: ObjectiveBreakdown
    constraint_families: tuple[ConstraintFamilyResidual, ...]
    modeled_slacks: Mapping[str, float]
    witness_fingerprint: str
    passes: bool


class _ResidualAccumulator:
    __slots__ = (
        "family_id",
        "relation",
        "canonical_unit",
        "source_refs",
        "checked_count",
        "maximum",
        "witness_indices",
    )

    def __init__(
        self,
        family_id: str,
        relation: str,
        canonical_unit: str,
        source_refs: tuple[str, ...],
    ) -> None:
        self.family_id = family_id
        self.relation = relation
        self.canonical_unit = canonical_unit
        self.source_refs = source_refs
        self.checked_count = 0
        self.maximum = 0.0
        self.witness_indices: tuple[tuple[int, ...], ...] = ()

    def add(self, violation: float, *indices: int) -> None:
        normalized = max(_finite(violation, field_name=self.family_id), 0.0)
        self.checked_count += 1
        if normalized > self.maximum:
            self.maximum = normalized
            self.witness_indices = (tuple(indices),)
        elif normalized > 0.0 and normalized == self.maximum:
            self.witness_indices = (*self.witness_indices, tuple(indices))

    def build(self) -> ConstraintFamilyResidual:
        return ConstraintFamilyResidual(
            family_id=self.family_id,
            relation=self.relation,
            canonical_unit=self.canonical_unit,
            checked_count=self.checked_count,
            maximum_positive_violation=self.maximum,
            witness_indices=self.witness_indices,
            source_refs=self.source_refs,
        )


def _witness_vector(
    witness: Mapping[str, object],
    name: str,
    count: int,
) -> tuple[float, ...]:
    if name not in witness:
        raise RobustFCRValidationError(f"solver witness is missing {name}")
    return _finite_tuple(witness[name], field_name=f"witness.{name}", count=count)


def _witness_triangle(
    witness: Mapping[str, object],
    name: str,
    count: int,
) -> tuple[tuple[float, ...], ...]:
    raw = witness.get(name)
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise RobustFCRValidationError(f"witness.{name} must be a triangular sequence")
    if len(raw) != count:
        raise RobustFCRValidationError(
            f"witness.{name} must contain {count} outer rows"
        )
    return tuple(
        _finite_tuple(
            row,
            field_name=f"witness.{name}[{outer}]",
            count=outer + 1,
        )
        for outer, row in enumerate(raw)
    )


def _audit_witness(
    problem: RobustFCRBiddingProblem,
    profile: RobustFCRFormulationProfile,
    witness: Mapping[str, object],
    *,
    reported_objective_eur: float,
) -> _WitnessAuditComputation:
    """Recompute every preserved equation without consulting Pyomo objects."""

    count = 96
    x0 = _witness_vector(witness, "x0", 24)
    xr = _witness_vector(witness, "xr", 6)
    xa = _witness_vector(witness, "xa", count)
    symin = _witness_vector(witness, "symin", count)
    symax = _witness_vector(witness, "symax", count)
    sy_k = _witness_vector(witness, "syK", 2)
    alpha = _witness_vector(witness, "alpha", count)
    beta = _witness_vector(witness, "beta", count)
    lambda_l = _witness_vector(witness, "lambda_l", count)
    lambda_h = _witness_vector(witness, "lambda_h", count)
    lambda_lower = _witness_triangle(witness, "Lambda_l", count)
    lambda_upper = _witness_triangle(witness, "Lambda_h", count)
    u1 = _witness_vector(witness, "u1", count - 1)
    u2 = _witness_vector(witness, "u2", count - 1)
    v_res = (
        _witness_vector(witness, "v_res", count - 1)
        if profile.kind == "restriction"
        else ()
    )

    battery = problem.battery
    x_min = battery.source_minimum_power_kw
    x_max = battery.source_maximum_power_kw
    y_min = battery.minimum_stored_energy_kwh
    y_max = battery.maximum_stored_energy_kwh
    y_initial = battery.initial_stored_energy_kwh
    eta_c = battery.charge_efficiency
    eta_d = battery.discharge_efficiency
    delta_eta = 1.0 / eta_d - eta_c
    gamma = problem.uncertainty.horizon_wide.horizon_activation_budget_hours
    terminal_minimum = problem.terminal_rule.minimum_terminal_stored_energy_kwh
    delta_t = 0.25
    e_of = tuple(index // 4 for index in range(count))
    b_of = tuple(index // 16 for index in range(count))
    source = "baselines/robust_storage_bidding/code/02_model.jl"

    accumulators = {
        "alpha_charge_epigraph": _ResidualAccumulator(
            "alpha_charge_epigraph", ">=", "kW", (f"{source}:191-194",)
        ),
        "alpha_discharge_epigraph": _ResidualAccumulator(
            "alpha_discharge_epigraph", ">=", "kW", (f"{source}:191-194",)
        ),
        "beta_charge_epigraph": _ResidualAccumulator(
            "beta_charge_epigraph", ">=", "kW", (f"{source}:195-197",)
        ),
        "beta_discharge_epigraph": _ResidualAccumulator(
            "beta_discharge_epigraph", ">=", "kW", (f"{source}:195-197",)
        ),
        "binary_integrality": _ResidualAccumulator(
            "binary_integrality", "integrality", "dimensionless", (f"{source}:122-128",)
        ),
        "fixed_intraday_adjustment": _ResidualAccumulator(
            "fixed_intraday_adjustment", "==", "kW", (f"{source}:88-99",)
        ),
        "lambda_h_diagonal_activation": _ResidualAccumulator(
            "lambda_h_diagonal_activation", ">=", "kW", (f"{source}:199-203",)
        ),
        "lambda_h_diagonal_discharge": _ResidualAccumulator(
            "lambda_h_diagonal_discharge", ">=", "kW", (f"{source}:199-203",)
        ),
        "lambda_h_diagonal_nonnegative": _ResidualAccumulator(
            "lambda_h_diagonal_nonnegative", ">=", "kW", (f"{source}:199-203",)
        ),
        "lambda_h_offdiag_charge_activation": _ResidualAccumulator(
            "lambda_h_offdiag_charge_activation", ">=", "kW", (f"{source}:215-219",)
        ),
        "lambda_h_offdiag_charge_baseline": _ResidualAccumulator(
            "lambda_h_offdiag_charge_baseline", ">=", "kW", (f"{source}:215-219",)
        ),
        "lambda_h_offdiag_discharge_activation": _ResidualAccumulator(
            "lambda_h_offdiag_discharge_activation", ">=", "kW", (f"{source}:215-219",)
        ),
        "lambda_h_offdiag_discharge_baseline": _ResidualAccumulator(
            "lambda_h_offdiag_discharge_baseline", ">=", "kW", (f"{source}:215-219",)
        ),
        "lower_coupling": _ResidualAccumulator(
            "lower_coupling", ">=", "kW", (f"{source}:183-188",)
        ),
        "lower_stored_energy": _ResidualAccumulator(
            "lower_stored_energy", ">=", "kWh", (f"{source}:183-188",)
        ),
        "pointwise_charge_headroom": _ResidualAccumulator(
            "pointwise_charge_headroom", ">=", "kW", (f"{source}:170-174",)
        ),
        "pointwise_discharge_headroom": _ResidualAccumulator(
            "pointwise_discharge_headroom", "<=", "kW", (f"{source}:170-174",)
        ),
        "terminal_stored_energy": _ResidualAccumulator(
            "terminal_stored_energy", ">=", "kWh", (f"{source}:254-263",)
        ),
        "u1_lower": _ResidualAccumulator(
            "u1_lower", ">=", "kW", (f"{source}:205-214",)
        ),
        "u1_upper": _ResidualAccumulator(
            "u1_upper", "<=", "kW", (f"{source}:205-214",)
        ),
        "u2_lower": _ResidualAccumulator(
            "u2_lower", ">=", "kW", (f"{source}:205-214",)
        ),
        "u2_upper": _ResidualAccumulator(
            "u2_upper", "<=", "kW", (f"{source}:205-214",)
        ),
        "upper_stored_energy": _ResidualAccumulator(
            "upper_stored_energy", "<=", "kWh", (f"{source}:183-188",)
        ),
        "variable_bounds": _ResidualAccumulator(
            "variable_bounds", "bounds", "dimensionless", (f"{source}:86-135",)
        ),
    }
    if profile.kind == "restriction":
        for name, relation in (
            ("restriction_classification_lower", ">="),
            ("restriction_classification_upper", "<="),
            ("restriction_tightening_charge", ">="),
            ("restriction_tightening_discharge", ">="),
        ):
            accumulators[name] = _ResidualAccumulator(
                name,
                relation,
                "kW",
                (f"{source}:225-230",),
            )
    elif profile.kind == "exact":
        accumulators["exact_bilinear"] = _ResidualAccumulator(
            "exact_bilinear", ">=", "kW", (f"{source}:220-224",)
        )

    for k in range(count):
        energy = x0[e_of[k]] + xa[k]
        reserve = xr[b_of[k]]
        accumulators["fixed_intraday_adjustment"].add(abs(xa[k]), k)
        accumulators["pointwise_charge_headroom"].add(
            x_min - (energy - reserve), k
        )
        accumulators["pointwise_discharge_headroom"].add(
            energy + reserve - x_max, k
        )
        lower_expression = (
            y_initial
            - gamma * lambda_l[k]
            - delta_t
            * sum(alpha[l] + lambda_lower[k][l] for l in range(k + 1))
        )
        accumulators["lower_stored_energy"].add(y_min - lower_expression, k)
        upper_expression = (
            y_initial
            + gamma * lambda_h[k]
            + delta_t * sum(lambda_upper[k][l] for l in range(k + 1))
        )
        accumulators["upper_stored_energy"].add(upper_expression - y_max, k)
        for l in range(k + 1):
            accumulators["lower_coupling"].add(
                -(lambda_lower[k][l] + lambda_l[k] + alpha[l] - beta[l]),
                k,
                l,
            )
        accumulators["alpha_charge_epigraph"].add(
            eta_c * energy - alpha[k], k
        )
        accumulators["alpha_discharge_epigraph"].add(
            energy / eta_d - alpha[k], k
        )
        accumulators["beta_charge_epigraph"].add(
            eta_c * (energy + reserve) - beta[k], k
        )
        accumulators["beta_discharge_epigraph"].add(
            (energy + reserve) / eta_d - beta[k], k
        )
        accumulators["lambda_h_diagonal_discharge"].add(
            -eta_c * energy - lambda_upper[k][k], k, k
        )
        accumulators["lambda_h_diagonal_activation"].add(
            eta_c * (reserve - energy) - lambda_h[k] - lambda_upper[k][k],
            k,
            k,
        )
        accumulators["lambda_h_diagonal_nonnegative"].add(
            -lambda_upper[k][k], k, k
        )

    lambda_h_limit = (x_max - x_min) / eta_d
    nonnegative_vectors = (xr, symin, symax, sy_k, lambda_l)
    for group_index, vector in enumerate(nonnegative_vectors):
        for index, value in enumerate(vector):
            accumulators["variable_bounds"].add(-value, group_index, index)
    for k, value in enumerate(lambda_h):
        accumulators["variable_bounds"].add(-value, 5, k)
        accumulators["variable_bounds"].add(value - lambda_h_limit, 6, k)
    for k, row in enumerate(lambda_lower):
        for l, value in enumerate(row):
            accumulators["variable_bounds"].add(-value, 7, k, l)
    for group_index, vector in enumerate((u1, u2, v_res), start=8):
        for index, value in enumerate(vector):
            accumulators["variable_bounds"].add(-value, group_index, index)
            accumulators["variable_bounds"].add(value - 1.0, group_index, index)
            accumulators["binary_integrality"].add(
                abs(value - round(value)), group_index, index
            )

    for l in range(count - 1):
        energy = x0[e_of[l]] + xa[l]
        reserve = xr[b_of[l]]
        accumulators["u1_upper"].add(
            energy - reserve - u1[l] * x_max, l
        )
        accumulators["u1_lower"].add(
            (1.0 - u1[l]) * x_min - (energy - reserve), l
        )
        accumulators["u2_lower"].add(u2[l] * x_min - energy, l)
        accumulators["u2_upper"].add(
            energy - (1.0 - u2[l]) * x_max, l
        )
        if profile.kind == "restriction":
            classification = (
                reserve - (1.0 - eta_c * eta_d) * energy - eta_d * lambda_h[l]
            )
            lower = -((2.0 - eta_c * eta_d) * x_max - x_min) * (
                1.0 - v_res[l]
            )
            upper = v_res[l] * (eta_c * eta_d * x_max - x_min)
            accumulators["restriction_classification_lower"].add(
                lower - classification, l
            )
            accumulators["restriction_classification_upper"].add(
                classification - upper, l
            )

    for k in range(count):
        for l in range(k):
            energy = x0[e_of[l]] + xa[l]
            reserve = xr[b_of[l]]
            actual = lambda_upper[k][l]
            accumulators["lambda_h_offdiag_discharge_activation"].add(
                (reserve - energy) / eta_d
                - lambda_h[k]
                + (1.0 - u1[l]) * delta_eta * x_min
                - actual,
                k,
                l,
            )
            accumulators["lambda_h_offdiag_discharge_baseline"].add(
                -energy / eta_d + u2[l] * delta_eta * x_min - actual,
                k,
                l,
            )
            accumulators["lambda_h_offdiag_charge_activation"].add(
                eta_c * (reserve - energy)
                - lambda_h[k]
                - u1[l] * delta_eta * x_max
                - actual,
                k,
                l,
            )
            accumulators["lambda_h_offdiag_charge_baseline"].add(
                -eta_c * energy
                - (1.0 - u2[l]) * delta_eta * x_max
                - actual,
                k,
                l,
            )
            if profile.kind == "restriction":
                accumulators["restriction_tightening_charge"].add(
                    -eta_c * energy
                    - (u1[l] + 1.0 - v_res[l]) * delta_eta * x_max
                    - actual,
                    k,
                    l,
                )
                accumulators["restriction_tightening_discharge"].add(
                    (reserve - energy) / eta_d
                    - lambda_h[k]
                    + (u2[l] + v_res[l]) * delta_eta * x_min
                    - actual,
                    k,
                    l,
                )
            elif profile.kind == "exact":
                left = actual * reserve + lambda_h[k] * energy
                right = (
                    u2[l] * x_min * (x_max - x_min) / eta_d
                    - u1[l] * x_max**2 / (4.0 * eta_d)
                )
                accumulators["exact_bilinear"].add(right - left, k, l)

    terminal_expression = y_initial - delta_t * sum(alpha)
    accumulators["terminal_stored_energy"].add(
        terminal_minimum - sy_k[1] - terminal_expression,
        count - 1,
    )
    day_ahead_value = delta_t * sum(
        problem.prices.day_ahead_energy_prices_eur_per_kwh[e_of[k]]
        * (x0[e_of[k]] + xa[k])
        for k in range(count)
    )
    fcr_value = sum(
        price * capacity
        for price, capacity in zip(
            problem.prices.fcr_capacity_prices_eur_per_kw_block,
            xr,
            strict=True,
        )
    )
    slack_penalty = problem.terminal_rule.shortfall_penalty_eur_per_kwh * (
        sum(sy_k) + sum(symin) + sum(symax)
    )
    total = day_ahead_value + fcr_value - slack_penalty
    reconciliation = abs(total - reported_objective_eur)
    objective = ObjectiveBreakdown(
        day_ahead_energy_value_eur=day_ahead_value,
        fcr_capacity_value_eur=fcr_value,
        feasibility_slack_penalty_eur=slack_penalty,
        total_objective_eur=total,
        reconciliation_residual_eur=reconciliation,
    )
    modeled_slacks = {
        **{f"stored_energy_lower_{index}_kwh": value for index, value in enumerate(symin)},
        **{f"stored_energy_upper_{index}_kwh": value for index, value in enumerate(symax)},
        "terminal_start_kwh": sy_k[0],
        "terminal_end_kwh": sy_k[1],
    }
    families = tuple(
        accumulators[name].build() for name in sorted(accumulators)
    )
    passes = (
        reconciliation <= DEPLOYABILITY_THRESHOLD
        and all(
            value.maximum_positive_violation <= DEPLOYABILITY_THRESHOLD
            for value in families
        )
        and all(value <= DEPLOYABILITY_THRESHOLD for value in modeled_slacks.values())
    )
    return _WitnessAuditComputation(
        objective=objective,
        constraint_families=families,
        modeled_slacks=MappingProxyType(dict(sorted(modeled_slacks.items()))),
        witness_fingerprint=_fingerprint(witness),
        passes=passes,
    )


def _canonicalize_kw(value: float) -> float:
    normalized = _finite(value, field_name="solver decision")
    quantized = Decimal(str(normalized)).quantize(
        Decimal("0.000000001"),
        rounding=ROUND_HALF_EVEN,
    )
    result = float(quantized)
    if not math.isfinite(result):  # pragma: no cover - guarded by finite input
        raise RobustFCRValidationError("canonical solver decision must remain finite")
    return 0.0 if result == 0.0 else result


def _canonicalize_witness_decisions(
    witness: Mapping[str, object],
) -> tuple[RobustFCRDecisions, Mapping[str, object]]:
    source_x0 = _witness_vector(witness, "x0", 24)
    source_xr = _witness_vector(witness, "xr", 6)
    public_energy = tuple(_canonicalize_kw(-value) for value in source_x0)
    public_fcr = tuple(_canonicalize_kw(value) for value in source_xr)
    decisions = RobustFCRDecisions(
        energy_baseline_charge_positive_kw=public_energy,
        fcr_capacity_kw=public_fcr,
    )
    canonical = dict(witness)
    canonical["x0"] = tuple(-value for value in public_energy)
    canonical["xr"] = public_fcr
    return decisions, MappingProxyType(canonical)


def _raw_diagnostics(raw: Any) -> list[RobustFCRDiagnostic]:
    diagnostics: list[RobustFCRDiagnostic] = []
    for value in raw.diagnostics:
        diagnostics.append(
            RobustFCRDiagnostic(
                code=str(value.get("code", "backend_diagnostic")),
                severity=str(value.get("severity", "info")),
                field_path=(
                    str(value["field_path"])
                    if value.get("field_path") is not None
                    else None
                ),
                message=str(value.get("message", "backend diagnostic")),
                evidence_refs=tuple(
                    str(item) for item in value.get("evidence_refs", ())
                ),
            )
        )
    return diagnostics


def _build_solver_evidence(
    problem: RobustFCRBiddingProblem,
    raw: Any,
    diagnostics: list[RobustFCRDiagnostic],
) -> SolverEvidence:
    gap = _normalize_maximization_gap(
        raw.objective_value_eur,
        raw.best_upper_bound_eur,
        problem.solve_policy,
    )
    if gap.normalized_negative_gap:
        diagnostics.append(
            RobustFCRDiagnostic(
                code="small_negative_gap_normalized",
                severity="info",
                field_path="solver.absolute_gap_eur",
                message=(
                    "best upper bound was below the incumbent only within the "
                    "declared objective-comparison allowance and was normalized to zero"
                ),
            )
        )
    if gap.inconsistent_bound:
        diagnostics.append(
            RobustFCRDiagnostic(
                code="solver_bound_inconsistent",
                severity="error",
                field_path="solver.best_upper_bound_eur",
                message=(
                    "maximization best bound is below the incumbent beyond the "
                    "declared objective-comparison allowance"
                ),
            )
        )
    return SolverEvidence(
        solve_status=raw.solve_status,
        termination_status=raw.termination_status,
        has_incumbent=raw.has_incumbent,
        incumbent_accepted=raw.has_incumbent
        and raw.solve_status in {"optimal", "feasible"},
        objective_value_eur=raw.objective_value_eur,
        best_upper_bound_eur=raw.best_upper_bound_eur,
        absolute_gap_eur=gap.absolute_gap_eur,
        relative_gap=gap.relative_gap,
        solver_name=raw.solver_name,
        solver_version=raw.solver_version,
        pyomo_version=raw.pyomo_version,
        highspy_version=raw.highspy_version,
        configured_options={
            **_thaw(raw.configured_options),
            "solve_policy": problem.solve_policy.to_dict(),
            "objective_comparison_absolute_tolerance_eur": (
                problem.solve_policy.objective_comparison_absolute_tolerance_eur
            ),
            "objective_comparison_relative_tolerance": (
                problem.solve_policy.objective_comparison_relative_tolerance
            ),
            "objective_comparison_policy_fingerprint": (
                problem.objective_comparison_policy_fingerprint
            ),
            "solve_policy_fingerprint": problem.solve_policy.solve_policy_fingerprint,
        },
        model_cardinality=raw.model_cardinality,
        runtime_seconds=raw.runtime_seconds,
    )


def _make_feasibility_audit(
    raw_audit: _WitnessAuditComputation,
    canonical_audit: _WitnessAuditComputation,
) -> FeasibilityAudit:
    return FeasibilityAudit(
        constraint_families=canonical_audit.constraint_families,
        modeled_slacks=canonical_audit.modeled_slacks,
        raw_witness_fingerprint=raw_audit.witness_fingerprint,
        canonical_witness_fingerprint=canonical_audit.witness_fingerprint,
        deployability_threshold=DEPLOYABILITY_THRESHOLD,
        passes_deployability_audit=raw_audit.passes and canonical_audit.passes,
    )


def _build_deployable_plan(
    problem: RobustFCRBiddingProblem,
    decisions: RobustFCRDecisions,
    solver: SolverEvidence,
    audit: FeasibilityAudit,
    diagnostics: Sequence[RobustFCRDiagnostic],
) -> Any:
    from open_energy_lab.control.fcr_bid_plan import (
        BidPlanProducer,
        OptimizationMetric,
        PlanDiagnostic,
        build_fixed_fcr_bid_plan,
    )
    from open_energy_lab.simulator.stacked_service import (
        build_energy_baseline_schedule,
        build_fcr_capacity_schedule,
    )

    period = problem.time_contract.delivery_period
    energy_schedule = build_energy_baseline_schedule(
        schedule_id=f"{problem.problem_id}-energy-v1",
        semantics_version="charge-positive-fixed-v1",
        covered_start_utc=period.start_utc,
        covered_end_utc=period.end_utc,
        intervals=tuple(
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "power_kw": value,
                "schedule_source": "fixed",
            }
            for interval, value in zip(
                problem.time_contract.energy_intervals,
                decisions.energy_baseline_charge_positive_kw,
                strict=True,
            )
        ),
    )
    fcr_schedule = build_fcr_capacity_schedule(
        schedule_id=f"{problem.problem_id}-fcr-v1",
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=period.start_utc,
        covered_end_utc=period.end_utc,
        intervals=tuple(
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "capacity_kw": value,
                "volume_observation_ref": f"robust_accepted_fcr_bid:{index}",
                "price_observation_ref": f"robust_fcr_capacity_price:{index}",
            }
            for index, (interval, value) in enumerate(
                zip(
                    problem.time_contract.fcr_intervals,
                    decisions.fcr_capacity_kw,
                    strict=True,
                )
            )
        ),
    )
    solve_evidence_fingerprint = _fingerprint(
        {
            "problem_fingerprint": problem.problem_fingerprint,
            "solver": solver.semantic_dict(),
            "decisions": decisions.to_dict(),
            "audit": audit.to_dict(),
            "diagnostics": [value.to_dict() for value in diagnostics],
        }
    )
    plan_diagnostics = tuple(
        [
            PlanDiagnostic(
                code="robust_fcr_solve_evidence",
                severity="info",
                field_path=None,
                message="plan passed the Feature 013 independent deployability audit",
                evidence_refs=(f"sha256:{solve_evidence_fingerprint}",),
            )
        ]
        + [
            PlanDiagnostic(
                code=value.code,
                severity=value.severity,
                field_path=value.field_path,
                message=value.message,
                evidence_refs=value.evidence_refs,
            )
            for value in diagnostics
            if value.severity != "error"
        ]
    )
    return build_fixed_fcr_bid_plan(
        plan_id=f"{problem.problem_id}-robust-plan-v1",
        producer=BidPlanProducer(
            producer_id="open-energy-lab-robust-fcr-bidder",
            producer_kind="robust",
            producer_version="feature-013-v1",
            configuration_fingerprint=problem.problem_fingerprint,
            configuration_unavailable_reason=None,
        ),
        information_cutoff_utc=problem.information_cutoff_utc,
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        producer_input_fingerprints={
            "robust_problem": problem.problem_fingerprint,
            "uncertainty_profile": (
                problem.uncertainty.uncertainty_profile_fingerprint
            ),
            "market_prices": problem.prices.price_input_fingerprint,
            "solve_policy": problem.solve_policy.solve_policy_fingerprint,
        },
        solve_status=solver.solve_status,
        objective=OptimizationMetric(
            availability="available",
            value=solver.objective_value_eur,
            unit="EUR",
            unavailable_reason=None,
            meaning="optimization_objective",
        ),
        objective_bound=OptimizationMetric(
            availability=(
                "available" if solver.best_upper_bound_eur is not None else "unavailable"
            ),
            value=solver.best_upper_bound_eur,
            unit="EUR" if solver.best_upper_bound_eur is not None else None,
            unavailable_reason=(
                None
                if solver.best_upper_bound_eur is not None
                else "same-solve best upper bound is unavailable"
            ),
            meaning="optimization_bound",
        ),
        diagnostics=plan_diagnostics,
    )


def _finalize_solve_result(
    problem: RobustFCRBiddingProblem,
    profile: RobustFCRFormulationProfile,
    raw: Any,
) -> RobustFCRSolveResult:
    """Audit one backend-neutral result and enforce deployability policy."""

    diagnostics = _raw_diagnostics(raw)
    solver = _build_solver_evidence(problem, raw, diagnostics)
    objective: ObjectiveBreakdown | None = None
    decisions: RobustFCRDecisions | None = None
    audit: FeasibilityAudit | None = None
    reasons: list[str] = []
    if not raw.has_incumbent or raw.witness is None:
        reasons.append("no_complete_incumbent")
    else:
        try:
            if raw.objective_value_eur is None:
                raise RobustFCRValidationError(
                    "complete incumbent is missing objective_value_eur"
                )
            raw_audit = _audit_witness(
                problem,
                profile,
                raw.witness,
                reported_objective_eur=raw.objective_value_eur,
            )
            decisions, canonical_witness = _canonicalize_witness_decisions(raw.witness)
            canonical_audit = _audit_witness(
                problem,
                profile,
                canonical_witness,
                reported_objective_eur=raw.objective_value_eur,
            )
            objective = raw_audit.objective
            audit = _make_feasibility_audit(raw_audit, canonical_audit)
            if objective.reconciliation_residual_eur > DEPLOYABILITY_THRESHOLD:
                diagnostics.append(
                    RobustFCRDiagnostic(
                        code="objective_reconciliation_failed",
                        severity="error",
                        field_path="raw_objective.reconciliation_residual_eur",
                        message="independent objective does not reconcile with the solver incumbent",
                    )
                )
            if not audit.passes_deployability_audit:
                reasons.append("feasibility_audit_failed")
        except RobustFCRValidationError as exc:
            diagnostics.append(
                RobustFCRDiagnostic(
                    code="incumbent_extraction_or_audit_failed",
                    severity="error",
                    field_path="solver.incumbent",
                    message=str(exc),
                )
            )
            reasons.append("incumbent_audit_unavailable")
            decisions = None
            audit = None

    if profile.kind != "restriction":
        reasons.append(f"{profile.deployability_role}_formulation")
    if raw.solve_status == "feasible" and not problem.solve_policy.allow_feasible_incumbent_plan:
        reasons.append("feasible_incumbent_not_opted_in")
    elif raw.solve_status not in {"optimal", "feasible"}:
        reasons.append(f"solve_status_{raw.solve_status}")
    if solver.absolute_gap_eur is None and solver.has_incumbent:
        reasons.append("solver_gap_unavailable_or_inconsistent")
    if any(value.severity == "error" for value in diagnostics):
        reasons.append("error_diagnostics_present")
    reasons = list(dict.fromkeys(reasons))
    eligible = (
        profile.kind == "restriction"
        and decisions is not None
        and audit is not None
        and audit.passes_deployability_audit
        and raw.solve_status in {"optimal", "feasible"}
        and (
            raw.solve_status == "optimal"
            or problem.solve_policy.allow_feasible_incumbent_plan
        )
        and not any(value.severity == "error" for value in diagnostics)
    )
    if eligible:
        reasons = []
        status = "eligible"
        plan = _build_deployable_plan(
            problem,
            decisions,
            solver,
            audit,
            diagnostics,
        )
    else:
        status = "not_applicable" if profile.kind != "restriction" else "blocked"
        plan = None
    return RobustFCRSolveResult(
        problem_fingerprint=problem.problem_fingerprint,
        comparison_problem_fingerprint=problem.comparison_problem_fingerprint,
        objective_comparison_policy_fingerprint=(
            problem.objective_comparison_policy_fingerprint
        ),
        formulation=profile,
        solver=solver,
        raw_objective=objective,
        decisions=decisions,
        feasibility_audit=audit,
        deployability_status=status,
        deployability_reasons=tuple(reasons),
        deployable_plan=plan,
        diagnostics=tuple(diagnostics),
        runtime_metadata={
            "runtime_seconds": raw.runtime_seconds,
            "backend": _thaw(raw.runtime_metadata),
        },
    )


def solve_robust_fcr_bid(
    problem: RobustFCRBiddingProblem,
    *,
    formulation: str = "restriction",
) -> RobustFCRSolveResult:
    """Solve one robust formulation through its explicit lazy backend boundary."""

    if not isinstance(problem, RobustFCRBiddingProblem):
        raise RobustFCRValidationError(
            "problem must be a validated RobustFCRBiddingProblem"
        )
    profile = RobustFCRFormulationProfile.for_kind(formulation)
    from ._robust_fcr_formulation import assemble_robust_fcr_model

    if profile.kind == "exact":
        from ._robust_fcr_solver import (
            load_optional_gurobi_backend,
            solve_exact_assembled_model,
            unavailable_exact_raw_result,
        )

        if problem.solve_policy.solver_name != "gurobi":
            raw = unavailable_exact_raw_result(
                (
                    "exact formulation requires the optional explicitly selected "
                    "Gurobi adapter; the configured solver is "
                    f"{problem.solve_policy.solver_name}"
                ),
                problem.solve_policy,
                code="exact_requires_explicit_gurobi",
            )
            return _finalize_solve_result(problem, profile, raw)
        backend, unavailable_reason = load_optional_gurobi_backend()
        if backend is None:
            raw = unavailable_exact_raw_result(
                unavailable_reason or "optional exact Gurobi evidence is unavailable",
                problem.solve_policy,
            )
            return _finalize_solve_result(problem, profile, raw)
        assembled = assemble_robust_fcr_model(
            problem,
            profile,
            pyomo_environ=backend.pyomo_environ,
        )
        raw = solve_exact_assembled_model(
            assembled,
            problem.solve_policy,
            backend=backend,
        )
        return _finalize_solve_result(problem, profile, raw)

    from ._robust_fcr_solver import require_highs_backend, solve_assembled_model

    backend = require_highs_backend()
    assembled = assemble_robust_fcr_model(
        problem,
        profile,
        pyomo_environ=backend.pyomo_environ,
    )
    raw = solve_assembled_model(assembled, problem.solve_policy, backend=backend)
    return _finalize_solve_result(problem, profile, raw)


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
    "HorizonWideActivationBudget",
    "RecoveryWindowActivationBudget",
    "RobustFCRBatteryParameters",
    "RobustFCRBoundComparison",
    "RobustFCRBiddingProblem",
    "RobustFCRDecisions",
    "RobustFCRDiagnostic",
    "RobustFCRFormulationProfile",
    "RobustFCRPriceInputs",
    "RobustFCRSolveResult",
    "RobustFCRSolvePolicy",
    "RobustFCRSolverDependencyUnavailableError",
    "RobustFCRSolverUnavailableError",
    "RobustFCRTimeContract",
    "RobustFCRUncertaintyProfile",
    "RobustFCRValidationError",
    "ConstraintFamilyResidual",
    "FeasibilityAudit",
    "ObjectiveBreakdown",
    "SolverEvidence",
    "TerminalStoredEnergyRule",
    "TERMINAL_STORED_ENERGY_RULE_VERSION",
    "build_robust_fcr_bidding_problem",
    "build_robust_fcr_time_contract",
    "compare_robust_fcr_bounds",
    "derive_non_intraday_horizon_budget",
]
