"""Stable controller-facing contracts for the external controller boundary MVP."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


POSITIVE_DISPATCH_MEANING = "charge"


def _require_non_empty_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_numeric_scalar(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a numeric single-step value")
    return float(value)


def _validate_soc_fraction(value: float, *, field_name: str) -> float:
    normalized = _require_numeric_scalar(value, field_name=field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be a fraction in [0.0, 1.0]")
    return normalized


def _validate_time_step_hours(value: float) -> float:
    normalized = _require_numeric_scalar(value, field_name="time_step_hours")
    if normalized <= 0.0:
        raise ValueError("time_step_hours must be positive")
    return normalized


def _normalize_metadata_mapping(
    value: Mapping[str, object] | None,
    *,
    field_name: str,
) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping when provided")
    return {
        _require_non_empty_text(key, field_name=f"{field_name} key"): item
        for key, item in value.items()
    }


@dataclass(slots=True)
class BatteryStateSnapshot:
    """Controller-facing snapshot of the battery state for one simulator step."""

    soc_fraction: float
    min_soc: float
    max_soc: float
    max_charge_kw: float
    max_discharge_kw: float

    def __post_init__(self) -> None:
        self.soc_fraction = _validate_soc_fraction(
            self.soc_fraction,
            field_name="soc_fraction",
        )
        self.min_soc = _validate_soc_fraction(self.min_soc, field_name="min_soc")
        self.max_soc = _validate_soc_fraction(self.max_soc, field_name="max_soc")
        self.max_charge_kw = _require_numeric_scalar(
            self.max_charge_kw,
            field_name="max_charge_kw",
        )
        self.max_discharge_kw = _require_numeric_scalar(
            self.max_discharge_kw,
            field_name="max_discharge_kw",
        )
        if self.max_charge_kw <= 0.0 or self.max_discharge_kw <= 0.0:
            raise ValueError("battery power limits must be positive")
        if not self.min_soc <= self.soc_fraction <= self.max_soc:
            raise ValueError("min_soc <= soc_fraction <= max_soc must hold")


@dataclass(slots=True)
class PriceInput:
    """Controller-facing current-step import and export prices."""

    import_price: float
    export_price: float
    currency: str
    time_alignment: str

    def __post_init__(self) -> None:
        self.import_price = _require_numeric_scalar(
            self.import_price,
            field_name="import_price",
        )
        self.export_price = _require_numeric_scalar(
            self.export_price,
            field_name="export_price",
        )
        self.currency = _require_non_empty_text(self.currency, field_name="currency")
        self.time_alignment = _require_non_empty_text(
            self.time_alignment,
            field_name="time_alignment",
        )


@dataclass(slots=True)
class ControllerContext:
    """Current-step context supplied to a controller by the simulator."""

    scenario_id: str
    scenario_kind: str
    step_index: int
    time_step_hours: float
    battery_state: BatteryStateSnapshot
    price_input: PriceInput
    step_inputs: dict[str, float] = field(default_factory=dict)
    notes: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        self.scenario_id = _require_non_empty_text(self.scenario_id, field_name="scenario_id")
        self.scenario_kind = _require_non_empty_text(
            self.scenario_kind,
            field_name="scenario_kind",
        )
        if self.step_index < 0:
            raise ValueError("step_index must be non-negative")
        self.time_step_hours = _validate_time_step_hours(self.time_step_hours)

        normalized_step_inputs: dict[str, float] = {}
        for key, value in self.step_inputs.items():
            normalized_key = _require_non_empty_text(key, field_name="step_inputs key")
            normalized_step_inputs[normalized_key] = _require_numeric_scalar(
                value,
                field_name=f"step_inputs[{normalized_key!r}]",
            )
        self.step_inputs = normalized_step_inputs

        self.notes = _normalize_metadata_mapping(self.notes, field_name="notes")


@dataclass(slots=True)
class DispatchProposal:
    """One-step dispatch request proposed by a controller."""

    step_index: int
    requested_power_kw: float
    sign_convention: str
    controller_name: str
    metadata: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if self.step_index < 0:
            raise ValueError("step_index must be non-negative")
        self.requested_power_kw = _require_numeric_scalar(
            self.requested_power_kw,
            field_name="requested_power_kw",
        )
        if self.sign_convention != POSITIVE_DISPATCH_MEANING:
            raise ValueError("sign_convention must document that positive dispatch means charge")
        self.controller_name = _require_non_empty_text(
            self.controller_name,
            field_name="controller_name",
        )
        self.metadata = _normalize_metadata_mapping(
            self.metadata,
            field_name="metadata",
        )


@runtime_checkable
class ControllerInterface(Protocol):
    """Stable one-step controller protocol."""

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        """Return one dispatch request for the supplied current-step context."""


@dataclass(slots=True)
class ControllerStepRecord:
    """Per-step record produced by controller-driven simulator evaluation."""

    step_index: int
    context: ControllerContext
    proposal: DispatchProposal
    realized_power_kw: float
    energy_delta_kwh: float
    step_settlement: float
    constraint_events: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.step_index < 0:
            raise ValueError("step_index must be non-negative")
        if self.context.step_index != self.step_index:
            raise ValueError("context.step_index must match the record step_index")
        if self.proposal.step_index != self.step_index:
            raise ValueError("proposal.step_index must match the record step_index")
        self.realized_power_kw = _require_numeric_scalar(
            self.realized_power_kw,
            field_name="realized_power_kw",
        )
        self.energy_delta_kwh = _require_numeric_scalar(
            self.energy_delta_kwh,
            field_name="energy_delta_kwh",
        )
        self.step_settlement = _require_numeric_scalar(
            self.step_settlement,
            field_name="step_settlement",
        )


@dataclass(slots=True)
class ControllerRejectionRecord:
    """Named pre-evaluation rejection for invalid controller execution inputs."""

    scenario_id: str
    scenario_kind: str
    failure_name: str
    reason: str
    step_index: int | None = None
    missing_inputs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.scenario_id = _require_non_empty_text(self.scenario_id, field_name="scenario_id")
        self.scenario_kind = _require_non_empty_text(
            self.scenario_kind,
            field_name="scenario_kind",
        )
        self.failure_name = _require_non_empty_text(
            self.failure_name,
            field_name="failure_name",
        )
        self.reason = _require_non_empty_text(self.reason, field_name="reason")
        if self.step_index is not None and self.step_index < 0:
            raise ValueError("step_index must be non-negative when provided")
        self.missing_inputs = [
            _require_non_empty_text(item, field_name="missing_inputs item")
            for item in self.missing_inputs
        ]


@dataclass(slots=True)
class ControllerEvaluationResult:
    """Typed result surface for simulator-owned controller evaluation."""

    scenario_id: str
    scenario_kind: str
    controller_name: str
    step_records: list[ControllerStepRecord]
    requested_power_kw: list[float]
    realized_power_kw: list[float]
    total_settlement: float
    final_battery_state: BatteryStateSnapshot | None
    underlying_trace: object | None = None
    rejection: ControllerRejectionRecord | None = None

    def __post_init__(self) -> None:
        self.scenario_id = _require_non_empty_text(self.scenario_id, field_name="scenario_id")
        self.scenario_kind = _require_non_empty_text(
            self.scenario_kind,
            field_name="scenario_kind",
        )
        self.controller_name = _require_non_empty_text(
            self.controller_name,
            field_name="controller_name",
        )
        self.requested_power_kw = [
            _require_numeric_scalar(value, field_name="requested_power_kw item")
            for value in self.requested_power_kw
        ]
        self.realized_power_kw = [
            _require_numeric_scalar(value, field_name="realized_power_kw item")
            for value in self.realized_power_kw
        ]
        if len(self.requested_power_kw) != len(self.realized_power_kw):
            raise ValueError("requested_power_kw and realized_power_kw must have matching lengths")
        if self.step_records and len(self.step_records) != len(self.requested_power_kw):
            raise ValueError("step_records length must match requested_power_kw length")
        self.total_settlement = _require_numeric_scalar(
            self.total_settlement,
            field_name="total_settlement",
        )


def validate_dispatch_proposal(
    context: ControllerContext,
    proposal: DispatchProposal,
) -> DispatchProposal:
    """Validate proposal semantics that must match the active current-step context."""

    if proposal.step_index != context.step_index:
        raise ValueError("proposal step_index must match the controller context step_index")
    if proposal.sign_convention != POSITIVE_DISPATCH_MEANING:
        raise ValueError("proposal sign_convention must document that positive dispatch means charge")
    return proposal


__all__ = [
    "BatteryStateSnapshot",
    "ControllerContext",
    "ControllerEvaluationResult",
    "ControllerInterface",
    "ControllerRejectionRecord",
    "ControllerStepRecord",
    "DispatchProposal",
    "POSITIVE_DISPATCH_MEANING",
    "PriceInput",
    "validate_dispatch_proposal",
]
