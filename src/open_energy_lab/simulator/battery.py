"""Battery state and transition helpers for the battery arbitrage MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._units import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    is_close,
    validate_positive_time_step_hours,
)

if TYPE_CHECKING:
    from .scenario import BatteryComponent


@dataclass(slots=True)
class BatteryState:
    """Per-step battery state derived from a battery component."""

    step_index: int
    soc: float
    stored_energy_kwh: float
    available_charge_kwh: float
    available_discharge_kwh: float


@dataclass(slots=True)
class BatteryTransition:
    """Result of applying one requested power value to the battery."""

    requested_power_kw: float
    realized_power_kw: float
    energy_delta_kwh: float
    state: BatteryState


def _normalize_energy(value: float, capacity_kwh: float) -> float:
    if is_close(value, 0.0, tolerance=DEFAULT_ABSOLUTE_TOLERANCE):
        return 0.0
    if is_close(value, capacity_kwh, tolerance=DEFAULT_ABSOLUTE_TOLERANCE):
        return capacity_kwh
    return value


def _build_state(*, step_index: int, component: BatteryComponent, stored_energy_kwh: float) -> BatteryState:
    normalized_energy = _normalize_energy(stored_energy_kwh, component.capacity_kwh)
    soc = normalized_energy / component.capacity_kwh
    return BatteryState(
        step_index=step_index,
        soc=soc,
        stored_energy_kwh=normalized_energy,
        available_charge_kwh=_normalize_energy(
            component.capacity_kwh - normalized_energy,
            component.capacity_kwh,
        ),
        available_discharge_kwh=_normalize_energy(
            normalized_energy,
            component.capacity_kwh,
        ),
    )


def build_initial_state(component: BatteryComponent) -> BatteryState:
    """Create the initial battery state from the component specification."""

    return _build_state(
        step_index=0,
        component=component,
        stored_energy_kwh=component.initial_soc * component.capacity_kwh,
    )


def apply_power_request(
    *,
    component: BatteryComponent,
    state: BatteryState,
    requested_power_kw: float,
    time_step_hours: float,
    step_index: int,
) -> BatteryTransition:
    """Clamp and apply a requested battery power value for one time step."""

    duration_hours = validate_positive_time_step_hours(time_step_hours)

    if requested_power_kw >= 0.0:
        clamped_power_kw = min(requested_power_kw, component.max_charge_kw)
        requested_energy_kwh = clamped_power_kw * duration_hours
        max_charge_energy_kwh = state.available_charge_kwh / component.charge_efficiency
        realized_input_energy_kwh = min(requested_energy_kwh, max_charge_energy_kwh)
        realized_power_kw = realized_input_energy_kwh / duration_hours
        energy_delta_kwh = realized_input_energy_kwh * component.charge_efficiency
    else:
        discharge_request_kw = min(abs(requested_power_kw), component.max_discharge_kw)
        requested_output_energy_kwh = discharge_request_kw * duration_hours
        max_output_energy_kwh = state.available_discharge_kwh * component.discharge_efficiency
        realized_output_energy_kwh = min(requested_output_energy_kwh, max_output_energy_kwh)
        realized_power_kw = -(realized_output_energy_kwh / duration_hours)
        energy_delta_kwh = -(realized_output_energy_kwh / component.discharge_efficiency)

    next_state = _build_state(
        step_index=step_index + 1,
        component=component,
        stored_energy_kwh=state.stored_energy_kwh + energy_delta_kwh,
    )
    return BatteryTransition(
        requested_power_kw=requested_power_kw,
        realized_power_kw=realized_power_kw,
        energy_delta_kwh=energy_delta_kwh,
        state=next_state,
    )


__all__ = [
    "BatteryState",
    "BatteryTransition",
    "apply_power_request",
    "build_initial_state",
]
