"""Shared US1 arbitrage helpers for visualization integration coverage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from open_energy_lab.core import ControllerContext, DispatchProposal
from open_energy_lab.simulator import (
    ArbitrageScenario,
    BatteryComponent,
    DispatchRequestSeries,
    PriceSignal,
    TimeGrid,
    evaluate_with_controller,
)
from open_energy_lab.simulator.pricing import ArbitrageObjectiveRepresentation
from open_energy_lab.simulator._units import POSITIVE_DISPATCH_MEANING


CONTROLLER_ARBITRAGE_FIXTURE_PATH = Path("tests/fixtures/simulator/controller_arbitrage_case.json")


def load_controller_arbitrage_fixture() -> dict[str, Any]:
    """Load the shared controller-arbitrage fixture used for US1 tests."""

    return json.loads(CONTROLLER_ARBITRAGE_FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_time_grid(fixture: dict[str, Any]) -> TimeGrid:
    time_grid_data = fixture["time_grid"]
    return TimeGrid(
        num_steps=time_grid_data["num_steps"],
        time_step_hours=time_grid_data["time_step_hours"],
    )


def _build_battery(fixture: dict[str, Any]) -> BatteryComponent:
    battery_data = fixture["battery"]
    return BatteryComponent(
        name=battery_data["name"],
        capacity_kwh=battery_data["capacity_kwh"],
        max_charge_kw=battery_data["max_charge_kw"],
        max_discharge_kw=battery_data["max_discharge_kw"],
        charge_efficiency=battery_data["charge_efficiency"],
        discharge_efficiency=battery_data["discharge_efficiency"],
        initial_soc=battery_data["initial_soc"],
        min_soc=battery_data["min_soc"],
        max_soc=battery_data["max_soc"],
    )


def _build_price_signal(fixture: dict[str, Any], grid: TimeGrid) -> PriceSignal:
    pricing = fixture["pricing"]
    return PriceSignal(
        currency=pricing["currency"],
        unit_rate_name=pricing["unit_rate_name"],
        import_prices=pricing["import_prices"],
        export_price_ratio=pricing["export_price_ratio"],
        interpretation=pricing["interpretation"],
        time_alignment=pricing["time_alignment"],
        time_grid=grid,
    )


def _build_objective(fixture: dict[str, Any]) -> ArbitrageObjectiveRepresentation:
    pricing = fixture["pricing"]
    return ArbitrageObjectiveRepresentation(
        objective_name="grid-settlement",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=pricing["export_price_ratio"],
    )


def build_direct_arbitrage_scenario() -> ArbitrageScenario:
    """Build the explicit-dispatch arbitrage scenario used for direct-trace coverage."""

    fixture = load_controller_arbitrage_fixture()
    grid = _build_time_grid(fixture)
    dispatch_requests = fixture["controller_stub"]["requested_power_kw"]
    return ArbitrageScenario(
        scenario_id=fixture["case_id"],
        time_grid=grid,
        battery=_build_battery(fixture),
        price_signal=_build_price_signal(fixture, grid),
        objective=_build_objective(fixture),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=dispatch_requests,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="visualization-us1-direct-trace",
        ),
    )


class SequenceController:
    """Deterministic sequence controller matching the shared arbitrage fixture."""

    def __init__(self, requested_power_kw: list[float]) -> None:
        self._requested_power_kw = requested_power_kw

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=self._requested_power_kw[context.step_index],
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name="sequence-controller",
        )


def build_controller_arbitrage_scenario() -> ArbitrageScenario:
    """Build the arbitrage scenario used for controller-driven evaluation coverage."""

    fixture = load_controller_arbitrage_fixture()
    grid = _build_time_grid(fixture)
    return ArbitrageScenario(
        scenario_id=fixture["case_id"],
        time_grid=grid,
        battery=_build_battery(fixture),
        price_signal=_build_price_signal(fixture, grid),
        objective=_build_objective(fixture),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=[0.0] * grid.num_steps,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="visualization-us1-controller-baseline",
        ),
    )


def build_direct_arbitrage_trace() -> tuple[ArbitrageScenario, object]:
    """Evaluate the explicit-dispatch arbitrage scenario once."""

    scenario = build_direct_arbitrage_scenario()
    return scenario, scenario.evaluate_trace()


def build_controller_arbitrage_result() -> tuple[ArbitrageScenario, object]:
    """Evaluate the fixture-equivalent arbitrage scenario through controller execution."""

    fixture = load_controller_arbitrage_fixture()
    scenario = build_controller_arbitrage_scenario()
    controller = SequenceController(fixture["controller_stub"]["requested_power_kw"])
    return scenario, evaluate_with_controller(scenario, controller)


def make_persisted_arbitrage_output(
    scenario: ArbitrageScenario,
    trace: object,
) -> dict[str, object]:
    """Build a supported persisted arbitrage payload from one evaluated trace."""

    step_labels = [f"step-{index}" for index in range(scenario.time_grid.num_steps)]
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_kind": type(scenario).__name__,
        "time_step_hours": scenario.time_grid.time_step_hours,
        "requested_power_kw": list(trace.requested_power_kw),
        "realized_power_kw": list(trace.realized_power_kw),
        "step_settlement": list(trace.step_settlement),
        "trace_payload": {
            "series": {
                "battery_soc": {
                    "values": [state.soc for state in trace.states],
                    "units": "fraction",
                    "source_field": "states.soc",
                    "display_category": "battery",
                    "step_labels": step_labels,
                },
                "requested_power_kw": {
                    "values": list(trace.requested_power_kw),
                    "units": "kw",
                    "source_field": "requested_power_kw",
                    "display_category": "dispatch",
                    "step_labels": step_labels,
                },
                "realized_power_kw": {
                    "values": list(trace.realized_power_kw),
                    "units": "kw",
                    "source_field": "realized_power_kw",
                    "display_category": "dispatch",
                    "step_labels": step_labels,
                },
                "import_price": {
                    "values": list(scenario.price_signal.import_prices),
                    "units": "usd_per_kwh",
                    "source_field": "price_signal.import_prices",
                    "display_category": "pricing",
                    "step_labels": step_labels,
                },
                "step_settlement": {
                    "values": list(trace.step_settlement),
                    "units": "usd",
                    "source_field": "step_settlement",
                    "display_category": "settlement",
                    "step_labels": step_labels,
                },
            },
            "available_sections": {
                "battery": True,
                "dispatch": True,
                "pricing": True,
                "settlement": True,
                "load": False,
                "pv": False,
                "net_grid": False,
                "weather": False,
            },
        },
        "summary_payload": {
            "total_settlement": {
                "value": trace.total_settlement,
                "units": "usd",
                "source_field": "total_settlement",
                "display_group": "settlement",
            }
        },
        "provenance_notes": [
            "Synthetic persisted arbitrage payload derived from the shared controller fixture.",
            "Used only for US1 visualization persisted-output integration coverage.",
        ],
    }
