"""Typed scenario entities and assembly validation for the battery arbitrage MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._graph import ComponentGraph, ComponentRef, Connection, Relation
from ._units import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    POSITIVE_DISPATCH_MEANING,
    validate_positive_time_step_hours,
    validate_soc_fraction,
)
from .pricing import (
    ArbitrageObjectiveRepresentation,
    DeterministicRulePolicy,
    PriceSignal,
)

if TYPE_CHECKING:
    from .battery import BatteryState


@dataclass(slots=True)
class TimeGrid:
    """Discrete time grid expressed in hours."""

    num_steps: int
    time_step_hours: float
    start_step: int = 0
    step_labels: list[str] | None = None
    horizon_hours: float = field(init=False)

    def __post_init__(self) -> None:
        if self.num_steps <= 0:
            raise ValueError("num_steps must be positive")
        self.time_step_hours = validate_positive_time_step_hours(self.time_step_hours)
        self.horizon_hours = self.num_steps * self.time_step_hours


@dataclass(slots=True)
class BatteryComponent:
    """Battery specification for the MVP scenario surface."""

    name: str
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    charge_efficiency: float
    discharge_efficiency: float
    initial_soc: float
    min_soc: float = 0.0
    max_soc: float = 1.0

    def __post_init__(self) -> None:
        if self.capacity_kwh <= 0:
            raise ValueError("capacity_kwh must be positive")
        if self.max_charge_kw <= 0 or self.max_discharge_kw <= 0:
            raise ValueError("battery power limits must be positive")
        if not 0.0 < self.charge_efficiency <= 1.0:
            raise ValueError("charge_efficiency must be in (0.0, 1.0]")
        if not 0.0 < self.discharge_efficiency <= 1.0:
            raise ValueError("discharge_efficiency must be in (0.0, 1.0]")
        self.min_soc = validate_soc_fraction(self.min_soc)
        self.max_soc = validate_soc_fraction(self.max_soc)
        self.initial_soc = validate_soc_fraction(self.initial_soc)
        if self.min_soc > self.initial_soc or self.initial_soc > self.max_soc:
            raise ValueError("min_soc <= initial_soc <= max_soc must hold")


@dataclass(slots=True)
class DispatchRequestSeries:
    """Explicit per-step dispatch requests."""

    requested_power_kw: list[float]
    sign_convention: str
    source: str

    def __post_init__(self) -> None:
        if self.sign_convention != POSITIVE_DISPATCH_MEANING:
            raise ValueError("sign_convention must document that positive dispatch means charge")
        if not self.source:
            raise ValueError("source must be provided for dispatch requests")


@dataclass(slots=True)
class SimulationTrace:
    """Deterministic trace produced from one scenario execution path."""

    states: list["BatteryState"]
    requested_power_kw: list[float]
    realized_power_kw: list[float]
    energy_delta_kwh: list[float]
    step_settlement: list[float]
    total_settlement: float
    constraint_events: list[str]


@dataclass(slots=True)
class ArbitrageScenario:
    """Aggregate root for the first arbitrage scenario surface."""

    scenario_id: str
    time_grid: TimeGrid
    battery: BatteryComponent
    price_signal: PriceSignal
    objective: ArbitrageObjectiveRepresentation
    dispatch_requests: DispatchRequestSeries | None = None
    rule_policy: DeterministicRulePolicy | None = None
    numeric_tolerance: float = DEFAULT_ABSOLUTE_TOLERANCE

    def validate(self) -> ComponentGraph:
        if (self.dispatch_requests is None) == (self.rule_policy is None):
            raise ValueError("exactly one of dispatch_requests or rule_policy must be provided")

        if self.dispatch_requests is not None:
            if len(self.dispatch_requests.requested_power_kw) != self.time_grid.num_steps:
                raise ValueError("dispatch request length must match the time grid")

        if self.price_signal.time_grid != self.time_grid:
            raise ValueError("price signal must align to the scenario time grid")

        if self.objective.allow_export and (
            self.objective.export_price_ratio != self.price_signal.export_price_ratio
        ):
            raise ValueError("objective export discount must match the price signal")

        graph = ComponentGraph()
        graph.add_component(ComponentRef(name="time_grid", kind="time-grid"))
        graph.add_component(ComponentRef(name="battery", kind="battery"))
        graph.add_component(ComponentRef(name="price_signal", kind="price-signal"))
        graph.add_component(ComponentRef(name="objective", kind="objective"))
        graph.add_component(ComponentRef(name="simulation_trace", kind="simulation-trace"))

        graph.add_connection(Connection("time_grid", "price_signal", Relation.ALIGNS))
        graph.add_connection(Connection("battery", "simulation_trace", Relation.PRODUCES))
        graph.add_connection(Connection("price_signal", "objective", Relation.PRICES))
        graph.add_connection(Connection("simulation_trace", "objective", Relation.SETTLES))

        if self.dispatch_requests is not None:
            graph.add_component(ComponentRef(name="dispatch_requests", kind="dispatch"))
            graph.add_connection(
                Connection("time_grid", "dispatch_requests", Relation.ALIGNS)
            )
            graph.add_connection(
                Connection("dispatch_requests", "battery", Relation.REQUESTS)
            )
        else:
            graph.add_component(ComponentRef(name="rule_policy", kind="policy"))
            graph.add_connection(Connection("time_grid", "rule_policy", Relation.ALIGNS))
            graph.add_connection(Connection("price_signal", "rule_policy", Relation.DRIVES))
            graph.add_connection(Connection("rule_policy", "battery", Relation.REQUESTS))

        return graph

    def evaluate_trace(self) -> SimulationTrace:
        """Evaluate one deterministic dispatch or built-in policy trace."""

        from .battery import apply_power_request, build_initial_state
        from .objective import evaluate_arbitrage_settlement

        self.validate()
        if self.dispatch_requests is not None:
            requested_power_kw = list(self.dispatch_requests.requested_power_kw)
        else:
            assert self.rule_policy is not None
            requested_power_kw = []
            for price in self.price_signal.import_prices:
                action = self.rule_policy.action_for_price(price)
                if action == "charge":
                    requested_power_kw.append(self.battery.max_charge_kw)
                elif action == "discharge":
                    requested_power_kw.append(-self.battery.max_discharge_kw)
                else:
                    requested_power_kw.append(0.0)

        current_state = build_initial_state(self.battery)
        states: list[BatteryState] = []
        realized_power_kw: list[float] = []
        energy_delta_kwh: list[float] = []
        constraint_events: list[str] = []

        for step_index, requested_power in enumerate(requested_power_kw):
            transition = apply_power_request(
                component=self.battery,
                state=current_state,
                requested_power_kw=requested_power,
                time_step_hours=self.time_grid.time_step_hours,
                step_index=step_index,
            )
            if abs(transition.realized_power_kw - requested_power) > self.numeric_tolerance:
                constraint_events.append(
                    f"step {step_index}: requested {requested_power} kW, realized {transition.realized_power_kw} kW"
                )
            current_state = transition.state
            states.append(current_state)
            realized_power_kw.append(transition.realized_power_kw)
            energy_delta_kwh.append(transition.energy_delta_kwh)

        settlement = evaluate_arbitrage_settlement(
            realized_power_kw=realized_power_kw,
            time_step_hours=self.time_grid.time_step_hours,
            price_signal=self.price_signal,
            objective=self.objective,
        )

        return SimulationTrace(
            states=states,
            requested_power_kw=requested_power_kw,
            realized_power_kw=realized_power_kw,
            energy_delta_kwh=energy_delta_kwh,
            step_settlement=settlement.step_settlement,
            total_settlement=settlement.total_settlement,
            constraint_events=constraint_events,
        )


__all__ = [
    "ArbitrageScenario",
    "BatteryComponent",
    "DispatchRequestSeries",
    "SimulationTrace",
    "TimeGrid",
]
