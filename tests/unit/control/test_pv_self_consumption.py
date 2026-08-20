"""Behavior coverage for the native PV self-consumption controller."""

from __future__ import annotations

import importlib

import pytest

from open_energy_lab.core.controller import (
    BatteryStateSnapshot,
    ControllerContext,
    PriceInput,
)


def _controller(*, controller_name: str | None = None):
    module = importlib.import_module("open_energy_lab.control")
    return module.PVSelfConsumptionController(
        module.PVSelfConsumptionConfig(
            reserve_min_soc=0.20,
            reserve_max_soc=0.80,
            charge_request_kw=5.0,
            discharge_request_kw=4.0,
            controller_name=controller_name,
        )
    )


def _context(
    *,
    soc_fraction: float,
    load_kw: float,
    pv_generation_kw: float,
    site_electric_load_kw: float | None = None,
) -> ControllerContext:
    step_inputs = {
        "load_kw": load_kw,
        "pv_generation_kw": pv_generation_kw,
    }
    if site_electric_load_kw is not None:
        step_inputs["site_electric_load_kw"] = site_electric_load_kw
    return ControllerContext(
        scenario_id="pv-self-consumption-unit",
        scenario_kind="BatteryLoadPVScenario",
        step_index=0,
        time_step_hours=1.0,
        battery_state=BatteryStateSnapshot(
            soc_fraction=soc_fraction,
            min_soc=0.0,
            max_soc=1.0,
            max_charge_kw=5.0,
            max_discharge_kw=5.0,
        ),
        price_input=PriceInput(
            import_price=0.20,
            export_price=0.16,
            currency="USD",
            time_alignment="step-start",
        ),
        step_inputs=step_inputs,
    )


def test_pv_self_consumption_controller_matches_pv_surplus_up_to_charge_limit() -> None:
    proposal = _controller().propose_dispatch(
        _context(soc_fraction=0.50, load_kw=1.0, pv_generation_kw=3.0)
    )

    assert proposal.requested_power_kw == pytest.approx(2.0)

    limited = _controller().propose_dispatch(
        _context(soc_fraction=0.50, load_kw=1.0, pv_generation_kw=9.0)
    )
    assert limited.requested_power_kw == pytest.approx(5.0)


def test_pv_self_consumption_controller_matches_load_deficit_up_to_discharge_limit() -> None:
    proposal = _controller().propose_dispatch(
        _context(soc_fraction=0.50, load_kw=3.0, pv_generation_kw=1.0)
    )

    assert proposal.requested_power_kw == pytest.approx(-2.0)

    limited = _controller().propose_dispatch(
        _context(soc_fraction=0.50, load_kw=9.0, pv_generation_kw=1.0)
    )
    assert limited.requested_power_kw == pytest.approx(-4.0)


def test_pv_self_consumption_controller_uses_total_site_electric_load_when_available() -> None:
    proposal = _controller().propose_dispatch(
        _context(
            soc_fraction=0.50,
            load_kw=1.0,
            site_electric_load_kw=3.5,
            pv_generation_kw=2.0,
        )
    )

    assert proposal.requested_power_kw == pytest.approx(-1.5)


@pytest.mark.parametrize(
    ("soc_fraction", "load_kw", "pv_generation_kw"),
    (
        (0.50, 2.0, 2.0),
        (0.80, 1.0, 3.0),
        (0.20, 3.0, 1.0),
    ),
)
def test_pv_self_consumption_controller_idles_at_balance_and_reserve_boundaries(
    soc_fraction: float,
    load_kw: float,
    pv_generation_kw: float,
) -> None:
    proposal = _controller().propose_dispatch(
        _context(
            soc_fraction=soc_fraction,
            load_kw=load_kw,
            pv_generation_kw=pv_generation_kw,
        )
    )

    assert proposal.requested_power_kw == pytest.approx(0.0)


def test_pv_self_consumption_controller_preserves_the_configured_controller_name() -> None:
    proposal = _controller(controller_name="pv-self-consumption-custom").propose_dispatch(
        _context(soc_fraction=0.50, load_kw=1.0, pv_generation_kw=3.0)
    )

    assert proposal.controller_name == "pv-self-consumption-custom"
