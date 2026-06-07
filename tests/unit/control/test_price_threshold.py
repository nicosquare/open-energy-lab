"""Behavior coverage for the native price-threshold controller."""

from __future__ import annotations

import importlib

import pytest

from open_energy_lab.core.controller import (
    BatteryStateSnapshot,
    ControllerContext,
    PriceInput,
)


def _controller():
    module = importlib.import_module("open_energy_lab.control")
    return module.PriceThresholdController(
        module.PriceThresholdConfig(
            charge_below_import_price=0.15,
            discharge_above_import_price=0.25,
            charge_request_kw=5.0,
            discharge_request_kw=4.0,
        )
    )


def _context(*, import_price: float) -> ControllerContext:
    return ControllerContext(
        scenario_id="price-threshold-unit",
        scenario_kind="ArbitrageScenario",
        step_index=0,
        time_step_hours=1.0,
        battery_state=BatteryStateSnapshot(
            soc_fraction=0.5,
            min_soc=0.0,
            max_soc=1.0,
            max_charge_kw=5.0,
            max_discharge_kw=5.0,
        ),
        price_input=PriceInput(
            import_price=import_price,
            export_price=import_price * 0.8,
            currency="USD",
            time_alignment="step-start",
        ),
        step_inputs={},
    )


def test_price_threshold_controller_requests_charge_below_the_charge_threshold() -> None:
    proposal = _controller().propose_dispatch(_context(import_price=0.10))

    assert proposal.requested_power_kw == pytest.approx(5.0)


def test_price_threshold_controller_requests_discharge_above_the_discharge_threshold() -> None:
    proposal = _controller().propose_dispatch(_context(import_price=0.30))

    assert proposal.requested_power_kw == pytest.approx(-4.0)


@pytest.mark.parametrize("import_price", (0.20, 0.15, 0.25))
def test_price_threshold_controller_idles_inside_the_neutral_band_and_at_equal_thresholds(
    import_price: float,
) -> None:
    proposal = _controller().propose_dispatch(_context(import_price=import_price))

    assert proposal.requested_power_kw == pytest.approx(0.0)


def test_price_threshold_controller_preserves_the_configured_controller_name() -> None:
    module = importlib.import_module("open_energy_lab.control")
    controller = module.PriceThresholdController(
        module.PriceThresholdConfig(
            charge_below_import_price=0.15,
            discharge_above_import_price=0.25,
            charge_request_kw=5.0,
            discharge_request_kw=4.0,
            controller_name="price-threshold-custom",
        )
    )

    proposal = controller.propose_dispatch(_context(import_price=0.10))

    assert proposal.controller_name == "price-threshold-custom"
