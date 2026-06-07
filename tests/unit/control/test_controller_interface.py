"""ControllerInterface conformance coverage for shipped native controllers."""

from __future__ import annotations

import importlib

import pytest

from open_energy_lab.core.controller import (
    BatteryStateSnapshot,
    ControllerContext,
    ControllerInterface,
    DispatchProposal,
    PriceInput,
    validate_dispatch_proposal,
)


def _context(
    *,
    scenario_kind: str,
    step_inputs: dict[str, float] | None = None,
) -> ControllerContext:
    return ControllerContext(
        scenario_id="controller-pack-unit-test",
        scenario_kind=scenario_kind,
        step_index=1,
        time_step_hours=1.0,
        battery_state=BatteryStateSnapshot(
            soc_fraction=0.5,
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
        step_inputs={} if step_inputs is None else step_inputs,
    )


@pytest.mark.parametrize(
    ("controller_name", "config_name", "scenario_kind", "step_inputs"),
    (
        (
            "PriceThresholdController",
            "PriceThresholdConfig",
            "ArbitrageScenario",
            {},
        ),
        (
            "SocGuardrailController",
            "SocGuardrailConfig",
            "ArbitrageScenario",
            {},
        ),
        (
            "PVSelfConsumptionController",
            "PVSelfConsumptionConfig",
            "BatteryLoadPVScenario",
            {"load_kw": 1.0, "pv_generation_kw": 1.0},
        ),
    ),
)
def test_shipped_controllers_conform_to_controller_interface(
    controller_name: str,
    config_name: str,
    scenario_kind: str,
    step_inputs: dict[str, float],
) -> None:
    root_module = importlib.import_module("open_energy_lab.control")
    config_module = importlib.import_module("open_energy_lab.control._config")

    controller_type = getattr(root_module, controller_name)
    config_type = getattr(config_module, config_name)
    controller = controller_type(
        config_type(
            **{
                "PriceThresholdConfig": {
                    "charge_below_import_price": 0.15,
                    "discharge_above_import_price": 0.25,
                    "charge_request_kw": 5.0,
                    "discharge_request_kw": 4.0,
                },
                "SocGuardrailConfig": {
                    "target_min_soc": 0.25,
                    "target_max_soc": 0.75,
                    "charge_request_kw": 5.0,
                    "discharge_request_kw": 4.0,
                },
                "PVSelfConsumptionConfig": {
                    "reserve_min_soc": 0.20,
                    "reserve_max_soc": 0.80,
                    "charge_request_kw": 5.0,
                    "discharge_request_kw": 4.0,
                },
            }[config_name]
        )
    )

    assert isinstance(controller, ControllerInterface)

    proposal = controller.propose_dispatch(
        _context(scenario_kind=scenario_kind, step_inputs=step_inputs)
    )
    validated = validate_dispatch_proposal(
        _context(scenario_kind=scenario_kind, step_inputs=step_inputs),
        proposal,
    )

    assert isinstance(proposal, DispatchProposal)
    assert proposal.requested_power_kw == pytest.approx(0.0)
    assert proposal.sign_convention == "charge"
    assert proposal.controller_name == controller_name
    assert validated is proposal
