"""Controller contract validation tests for the stable core boundary."""

from __future__ import annotations

from dataclasses import fields, is_dataclass

import pytest

from open_energy_lab.core.controller import (
    BatteryStateSnapshot,
    ControllerContext,
    ControllerInterface,
    DispatchProposal,
    PriceInput,
    validate_dispatch_proposal,
)


def _battery_state() -> BatteryStateSnapshot:
    return BatteryStateSnapshot(
        soc_fraction=0.5,
        min_soc=0.1,
        max_soc=0.9,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
    )


def _price_input() -> PriceInput:
    return PriceInput(
        import_price=0.20,
        export_price=0.16,
        currency="USD",
        time_alignment="step-start",
    )


def _context(
    *,
    scenario_kind: str = "ArbitrageScenario",
    step_inputs: dict[str, float] | None = None,
) -> ControllerContext:
    return ControllerContext(
        scenario_id="scenario-001",
        scenario_kind=scenario_kind,
        step_index=2,
        time_step_hours=1.0,
        battery_state=_battery_state(),
        price_input=_price_input(),
        step_inputs={} if step_inputs is None else step_inputs,
        notes={"origin": "unit-test"},
    )


class _DeterministicController:
    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=1.25,
            sign_convention="charge",
            controller_name="deterministic-controller",
        )


def test_controller_context_exposes_current_step_contract_shape() -> None:
    context = _context(step_inputs={"load_kw": 3.0, "pv_generation_kw": 1.0})

    assert is_dataclass(context)
    assert [field.name for field in fields(ControllerContext)] == [
        "scenario_id",
        "scenario_kind",
        "step_index",
        "time_step_hours",
        "battery_state",
        "price_input",
        "step_inputs",
        "notes",
    ]
    assert context.step_index == 2
    assert context.time_step_hours == 1.0
    assert context.step_inputs == {"load_kw": 3.0, "pv_generation_kw": 1.0}


def test_controller_protocol_returns_a_typed_single_step_dispatch_proposal() -> None:
    context = _context()
    controller: ControllerInterface = _DeterministicController()

    assert isinstance(controller, ControllerInterface)

    proposal = controller.propose_dispatch(context)
    validated = validate_dispatch_proposal(context, proposal)

    assert isinstance(proposal, DispatchProposal)
    assert proposal.requested_power_kw == 1.25
    assert proposal.sign_convention == "charge"
    assert validated is proposal


def test_dispatch_proposal_rejects_wrong_sign_convention() -> None:
    with pytest.raises(ValueError, match="sign_convention"):
        DispatchProposal(
            step_index=0,
            requested_power_kw=1.0,
            sign_convention="discharge",
            controller_name="invalid-sign",
        )


def test_dispatch_proposal_rejects_multi_step_request_shape() -> None:
    with pytest.raises((TypeError, ValueError), match="single-step|numeric"):
        DispatchProposal(
            step_index=0,
            requested_power_kw=[1.0, -1.0],  # type: ignore[arg-type]
            sign_convention="charge",
            controller_name="invalid-shape",
        )


def test_dispatch_validation_rejects_step_misalignment() -> None:
    context = _context()
    proposal = DispatchProposal(
        step_index=context.step_index + 1,
        requested_power_kw=1.0,
        sign_convention="charge",
        controller_name="misaligned-step",
    )

    with pytest.raises(ValueError, match="step_index"):
        validate_dispatch_proposal(context, proposal)
