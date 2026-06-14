"""Simulator-owned controller evaluation for supported scenario families."""

from __future__ import annotations

from open_energy_lab.core import (
    ControllerContext,
    ControllerEvaluationResult,
    ControllerInterface,
    DispatchProposal,
)
from open_energy_lab.core.controller import (
    BatteryStateSnapshot,
    ControllerRejectionRecord,
    ControllerStepRecord,
    validate_dispatch_proposal,
)

from .battery import apply_power_request, build_initial_state
from .objective import evaluate_arbitrage_settlement, evaluate_net_grid_settlement
from .scenario import (
    ArbitrageScenario,
    BatteryLoadPVScenario,
    BatteryLoadPVTrace,
    SimulationTrace,
    _ControllerContextInputError,
    build_controller_context_for_step,
    prepare_controller_context_inputs,
)


SupportedControllerScenario = ArbitrageScenario | BatteryLoadPVScenario


def _controller_name_from_instance(controller: ControllerInterface) -> str:
    return controller.__class__.__name__


def _request_dispatch(
    controller: ControllerInterface,
    context: ControllerContext,
) -> DispatchProposal:
    return controller.propose_dispatch(context)


def _build_final_battery_state_snapshot(
    scenario: SupportedControllerScenario,
    *,
    soc_fraction: float,
) -> BatteryStateSnapshot:
    return BatteryStateSnapshot(
        soc_fraction=soc_fraction,
        min_soc=scenario.battery.min_soc,
        max_soc=scenario.battery.max_soc,
        max_charge_kw=scenario.battery.max_charge_kw,
        max_discharge_kw=scenario.battery.max_discharge_kw,
    )


def _build_incomplete_context_result(
    scenario: SupportedControllerScenario,
    controller: ControllerInterface,
    *,
    step_index: int,
    missing_inputs: list[str],
    reason: str,
) -> ControllerEvaluationResult:
    return ControllerEvaluationResult(
        scenario_id=scenario.scenario_id,
        scenario_kind=type(scenario).__name__,
        controller_name=_controller_name_from_instance(controller),
        step_records=[],
        requested_power_kw=[],
        realized_power_kw=[],
        total_settlement=0.0,
        final_battery_state=None,
        source_scenario=scenario,
        rejection=ControllerRejectionRecord(
            scenario_id=scenario.scenario_id,
            scenario_kind=type(scenario).__name__,
            failure_name="incomplete_controller_context",
            reason=reason,
            step_index=step_index,
            missing_inputs=missing_inputs,
        ),
    )


def evaluate_with_controller(
    scenario: SupportedControllerScenario,
    controller: ControllerInterface,
) -> ControllerEvaluationResult:
    """Evaluate one controller-driven episode using existing simulator semantics."""

    if not isinstance(scenario, (ArbitrageScenario, BatteryLoadPVScenario)):
        raise TypeError(
            "evaluate_with_controller supports ArbitrageScenario and BatteryLoadPVScenario"
        )

    scenario.validate()
    try:
        prepared_inputs = prepare_controller_context_inputs(scenario)
    except _ControllerContextInputError as exc:
        return _build_incomplete_context_result(
            scenario,
            controller,
            step_index=exc.step_index,
            missing_inputs=list(exc.missing_inputs),
            reason=str(exc),
        )

    current_state = build_initial_state(scenario.battery)
    contexts = []
    proposals = []
    states = []
    requested_power_kw = []
    realized_power_kw = []
    energy_delta_kwh = []
    constraint_events = []
    step_constraint_events: list[list[str]] = []

    for step_index in range(scenario.time_grid.num_steps):
        context = build_controller_context_for_step(
            scenario,
            battery_state=current_state,
            step_index=step_index,
            prepared_inputs=prepared_inputs,
        )
        proposal = validate_dispatch_proposal(context, _request_dispatch(controller, context))
        transition = apply_power_request(
            component=scenario.battery,
            state=current_state,
            requested_power_kw=proposal.requested_power_kw,
            time_step_hours=scenario.time_grid.time_step_hours,
            step_index=step_index,
        )

        step_events: list[str] = []
        if (
            abs(transition.realized_power_kw - proposal.requested_power_kw)
            > scenario.numeric_tolerance
        ):
            event = (
                f"step {step_index}: requested {proposal.requested_power_kw} kW, "
                f"realized {transition.realized_power_kw} kW"
            )
            constraint_events.append(event)
            step_events.append(event)

        contexts.append(context)
        proposals.append(proposal)
        states.append(transition.state)
        requested_power_kw.append(proposal.requested_power_kw)
        realized_power_kw.append(transition.realized_power_kw)
        energy_delta_kwh.append(transition.energy_delta_kwh)
        step_constraint_events.append(step_events)
        current_state = transition.state

    if isinstance(scenario, ArbitrageScenario):
        settlement = evaluate_arbitrage_settlement(
            realized_power_kw=realized_power_kw,
            time_step_hours=scenario.time_grid.time_step_hours,
            price_signal=scenario.price_signal,
            objective=scenario.objective,
        )
        underlying_trace = SimulationTrace(
            states=states,
            requested_power_kw=requested_power_kw,
            realized_power_kw=realized_power_kw,
            energy_delta_kwh=energy_delta_kwh,
            step_settlement=settlement.step_settlement,
            total_settlement=settlement.total_settlement,
            constraint_events=constraint_events,
        )
    else:
        load_kw = prepared_inputs["load_kw"]
        pv_generation_kw = prepared_inputs["pv_generation_kw"]
        settlement = evaluate_net_grid_settlement(
            load_kw=load_kw,
            pv_generation_kw=pv_generation_kw,
            realized_battery_power_kw=realized_power_kw,
            time_step_hours=scenario.time_grid.time_step_hours,
            price_signal=scenario.price_signal,
            objective=scenario.objective,
        )
        blackout_active = scenario._blackout_active_series()
        unmet_load_kw: list[float] = []
        net_grid_power_kw = list(settlement.net_grid_power_kw)
        net_grid_energy_kwh = list(settlement.net_grid_energy_kwh)
        direction = list(settlement.direction)
        step_settlement = list(settlement.step_settlement)
        if any(blackout_active):
            for step_index, is_active in enumerate(blackout_active):
                if is_active:
                    unmet_load_kw.append(max(0.0, net_grid_power_kw[step_index]))
                    net_grid_power_kw[step_index] = 0.0
                    net_grid_energy_kwh[step_index] = 0.0
                    direction[step_index] = "neutral"
                    step_settlement[step_index] = 0.0
                else:
                    unmet_load_kw.append(0.0)
        else:
            unmet_load_kw = [0.0] * scenario.time_grid.num_steps
        underlying_trace = BatteryLoadPVTrace(
            states=states,
            requested_power_kw=requested_power_kw,
            realized_power_kw=realized_power_kw,
            energy_delta_kwh=energy_delta_kwh,
            load_kw=load_kw,
            pv_generation_kw=pv_generation_kw,
            net_grid_power_kw=net_grid_power_kw,
            net_grid_energy_kwh=net_grid_energy_kwh,
            direction=direction,
            unmet_load_kw=unmet_load_kw,
            blackout_active=blackout_active,
            step_settlement=step_settlement,
            total_settlement=sum(step_settlement),
            constraint_events=constraint_events,
        )

    step_records = [
        ControllerStepRecord(
            step_index=step_index,
            context=contexts[step_index],
            proposal=proposals[step_index],
            realized_power_kw=realized_power_kw[step_index],
            energy_delta_kwh=energy_delta_kwh[step_index],
            step_settlement=underlying_trace.step_settlement[step_index],
            constraint_events=step_constraint_events[step_index],
        )
        for step_index in range(scenario.time_grid.num_steps)
    ]

    return ControllerEvaluationResult(
        scenario_id=scenario.scenario_id,
        scenario_kind=type(scenario).__name__,
        controller_name=(
            proposals[0].controller_name
            if proposals
            else _controller_name_from_instance(controller)
        ),
        step_records=step_records,
        requested_power_kw=requested_power_kw,
        realized_power_kw=realized_power_kw,
        total_settlement=underlying_trace.total_settlement,
        final_battery_state=_build_final_battery_state_snapshot(
            scenario,
            soc_fraction=current_state.soc,
        ),
        source_scenario=scenario,
        underlying_trace=underlying_trace,
    )


__all__ = ["evaluate_with_controller"]
