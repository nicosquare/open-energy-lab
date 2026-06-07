"""Behavior coverage for the native SOC guardrail controller."""

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
    return module.SocGuardrailController(
        module.SocGuardrailConfig(
            target_min_soc=0.25,
            target_max_soc=0.75,
            charge_request_kw=5.0,
            discharge_request_kw=4.0,
            controller_name=controller_name,
        )
    )


def _context(*, soc_fraction: float, scenario_kind: str) -> ControllerContext:
    step_inputs = (
        {}
        if scenario_kind == "ArbitrageScenario"
        else {"load_kw": 1.0, "pv_generation_kw": 1.0}
    )
    return ControllerContext(
        scenario_id="soc-guardrail-unit",
        scenario_kind=scenario_kind,
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


@pytest.mark.parametrize("scenario_kind", ("ArbitrageScenario", "BatteryLoadPVScenario"))
def test_soc_guardrail_controller_requests_charge_below_the_minimum_guardrail(
    scenario_kind: str,
) -> None:
    proposal = _controller().propose_dispatch(
        _context(soc_fraction=0.20, scenario_kind=scenario_kind)
    )

    assert proposal.requested_power_kw == pytest.approx(5.0)


@pytest.mark.parametrize("scenario_kind", ("ArbitrageScenario", "BatteryLoadPVScenario"))
def test_soc_guardrail_controller_requests_discharge_above_the_maximum_guardrail(
    scenario_kind: str,
) -> None:
    proposal = _controller().propose_dispatch(
        _context(soc_fraction=0.80, scenario_kind=scenario_kind)
    )

    assert proposal.requested_power_kw == pytest.approx(-4.0)


@pytest.mark.parametrize(
    ("scenario_kind", "soc_fraction"),
    (
        ("ArbitrageScenario", 0.50),
        ("ArbitrageScenario", 0.25),
        ("ArbitrageScenario", 0.75),
        ("BatteryLoadPVScenario", 0.50),
        ("BatteryLoadPVScenario", 0.25),
        ("BatteryLoadPVScenario", 0.75),
    ),
)
def test_soc_guardrail_controller_idles_inside_the_band_and_at_satisfied_boundaries(
    scenario_kind: str,
    soc_fraction: float,
) -> None:
    proposal = _controller().propose_dispatch(
        _context(soc_fraction=soc_fraction, scenario_kind=scenario_kind)
    )

    assert proposal.requested_power_kw == pytest.approx(0.0)


def test_soc_guardrail_controller_preserves_the_configured_controller_name() -> None:
    proposal = _controller(controller_name="soc-guardrail-custom").propose_dispatch(
        _context(soc_fraction=0.20, scenario_kind="ArbitrageScenario")
    )

    assert proposal.controller_name == "soc-guardrail-custom"
