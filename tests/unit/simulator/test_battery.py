"""Battery state-transition tests for the battery arbitrage MVP."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE
from open_energy_lab.simulator.battery import BatteryState, apply_power_request, build_initial_state
from open_energy_lab.simulator.scenario import BatteryComponent


def _battery(*, initial_soc: float = 0.5) -> BatteryComponent:
    return BatteryComponent(
        name="battery",
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=initial_soc,
    )


def test_build_initial_state_uses_component_capacity_and_initial_soc() -> None:
    state = build_initial_state(_battery(initial_soc=0.5))

    assert state.step_index == 0
    assert state.soc == pytest.approx(0.5, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert state.stored_energy_kwh == pytest.approx(5.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert state.available_charge_kwh == pytest.approx(5.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert state.available_discharge_kwh == pytest.approx(5.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)


def test_apply_power_request_clamps_charge_to_power_limit_and_uses_efficiency() -> None:
    component = _battery(initial_soc=0.5)
    initial_state = build_initial_state(component)

    result = apply_power_request(
        component=component,
        state=initial_state,
        requested_power_kw=7.0,
        time_step_hours=1.0,
        step_index=0,
    )

    assert result.requested_power_kw == pytest.approx(7.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert result.realized_power_kw == pytest.approx(5.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert result.energy_delta_kwh == pytest.approx(4.75, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert result.state.soc == pytest.approx(0.975, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert result.state.stored_energy_kwh == pytest.approx(
        9.75,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_apply_power_request_clamps_discharge_to_available_energy() -> None:
    component = _battery(initial_soc=0.1)
    initial_state = build_initial_state(component)

    result = apply_power_request(
        component=component,
        state=initial_state,
        requested_power_kw=-5.0,
        time_step_hours=1.0,
        step_index=0,
    )

    assert result.realized_power_kw == pytest.approx(-0.95, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert result.energy_delta_kwh == pytest.approx(-1.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert result.state.soc == pytest.approx(0.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)
    assert result.state.stored_energy_kwh == pytest.approx(0.0, abs=DEFAULT_ABSOLUTE_TOLERANCE)


def test_apply_power_request_treats_near_full_state_with_default_tolerance() -> None:
    component = _battery(initial_soc=1.0)
    near_full_state = BatteryState(
        step_index=0,
        soc=0.99999995,
        stored_energy_kwh=9.9999995,
        available_charge_kwh=0.0000005,
        available_discharge_kwh=9.9999995,
    )

    result = apply_power_request(
        component=component,
        state=near_full_state,
        requested_power_kw=0.01,
        time_step_hours=1.0,
        step_index=1,
    )

    assert result.state.stored_energy_kwh == pytest.approx(
        10.0,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert result.state.available_charge_kwh == pytest.approx(
        0.0,
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )
    assert result.state.soc <= 1.0 + DEFAULT_ABSOLUTE_TOLERANCE
