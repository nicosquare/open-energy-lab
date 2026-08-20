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

if TYPE_CHECKING:
    from .battery import BatteryState
    from .load import CoolingServiceBalance, LoadComponent
    from .pv import PVComponent
    from .pricing import (
        ArbitrageObjectiveRepresentation,
        DeterministicRulePolicy,
        PriceSignal,
    )
    from .weather import WeatherComponent


class _ControllerContextInputError(ValueError):
    """Raised when required current-step controller inputs are incomplete."""

    def __init__(self, *, step_index: int, missing_inputs: list[str], reason: str) -> None:
        super().__init__(reason)
        self.step_index = step_index
        self.missing_inputs = missing_inputs
        self.reason = reason


def _require_controller_numeric_step_value(
    value: object,
    *,
    field_name: str,
    step_index: int,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _ControllerContextInputError(
            step_index=step_index,
            missing_inputs=[field_name],
            reason=(
                "controller evaluation requires complete numeric current-step inputs; "
                f"{field_name} is unavailable at step {step_index}"
            ),
        )
    return float(value)


def _validate_price_signal_for_controller(
    scenario: "ArbitrageScenario | BatteryLoadPVScenario",
) -> None:
    for step_index, value in enumerate(scenario.price_signal.import_prices):
        _require_controller_numeric_step_value(
            value,
            field_name="import_price",
            step_index=step_index,
        )


def prepare_controller_context_inputs(
    scenario: "ArbitrageScenario | BatteryLoadPVScenario",
) -> dict[str, list[float]]:
    """Validate and cache aligned controller inputs for one scenario horizon."""

    _validate_price_signal_for_controller(scenario)

    if isinstance(scenario, ArbitrageScenario):
        return {}

    load_kw = [
        _require_controller_numeric_step_value(
            value,
            field_name="load_kw",
            step_index=step_index,
        )
        for step_index, value in enumerate(scenario.load.demand_kw)
    ]
    local_cooling_electric_kw = [
        _require_controller_numeric_step_value(
            value,
            field_name="site_electric_load_kw",
            step_index=step_index,
        )
        for step_index, value in enumerate(scenario._local_cooling_electric_kw())
    ]
    site_electric_load_kw = [
        base_load_kw + cooling_kw
        for base_load_kw, cooling_kw in zip(
            load_kw,
            local_cooling_electric_kw,
            strict=True,
        )
    ]

    for step_index in range(scenario.time_grid.num_steps):
        _require_controller_numeric_step_value(
            scenario.weather.dry_bulb_air_temperature_c[step_index],
            field_name="pv_generation_kw",
            step_index=step_index,
        )
        for field_name in scenario.pv.irradiance_field_names:
            _require_controller_numeric_step_value(
                scenario.weather.field_values(field_name)[step_index],
                field_name="pv_generation_kw",
                step_index=step_index,
            )

    try:
        pv_generation_kw = [
            _require_controller_numeric_step_value(
                value,
                field_name="pv_generation_kw",
                step_index=step_index,
            )
            for step_index, value in enumerate(scenario.pv.derive_generation_kw(scenario.weather))
        ]
    except (TypeError, ValueError) as exc:
        raise _ControllerContextInputError(
            step_index=0,
            missing_inputs=["pv_generation_kw"],
            reason=(
                "controller evaluation requires complete numeric current-step inputs; "
                "pv_generation_kw could not be derived from the active scenario"
            ),
        ) from exc

    return {
        "load_kw": load_kw,
        "site_electric_load_kw": site_electric_load_kw,
        "pv_generation_kw": pv_generation_kw,
    }


def _grid_feasible_battery_request_kw(
    *,
    requested_power_kw: float,
    site_electric_load_kw: float,
    pv_generation_kw: float,
    grid_available: bool,
) -> float:
    """Limit battery power to the local residual while the grid is unavailable."""

    if grid_available:
        return float(requested_power_kw)

    residual_load_kw = float(site_electric_load_kw) - float(pv_generation_kw)
    if requested_power_kw > 0.0:
        local_surplus_kw = max(0.0, -residual_load_kw)
        return min(float(requested_power_kw), local_surplus_kw)
    if requested_power_kw < 0.0:
        local_deficit_kw = max(0.0, residual_load_kw)
        return -min(abs(float(requested_power_kw)), local_deficit_kw)
    return 0.0


def build_controller_context_for_step(
    scenario: "ArbitrageScenario | BatteryLoadPVScenario",
    *,
    battery_state: "BatteryState",
    step_index: int,
    prepared_inputs: dict[str, list[float]],
):
    """Build the stable controller context for one supported simulator step."""

    from open_energy_lab.core.controller import (
        BatteryStateSnapshot,
        ControllerContext,
        PriceInput,
    )

    step_inputs = {
        name: values[step_index]
        for name, values in prepared_inputs.items()
    }
    return ControllerContext(
        scenario_id=scenario.scenario_id,
        scenario_kind=type(scenario).__name__,
        step_index=step_index,
        time_step_hours=scenario.time_grid.time_step_hours,
        battery_state=BatteryStateSnapshot(
            soc_fraction=battery_state.soc,
            min_soc=scenario.battery.min_soc,
            max_soc=scenario.battery.max_soc,
            max_charge_kw=scenario.battery.max_charge_kw,
            max_discharge_kw=scenario.battery.max_discharge_kw,
        ),
        price_input=PriceInput(
            import_price=scenario.price_signal.price_at_step(step_index),
            export_price=scenario.price_signal.export_price_at_step(step_index),
            currency=scenario.price_signal.currency,
            time_alignment=scenario.price_signal.time_alignment,
        ),
        step_inputs=step_inputs,
    )


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
class BatteryLoadPVTrace:
    """Deterministic trace for the battery + load + weather + PV MVP."""

    states: list["BatteryState"]
    requested_power_kw: list[float]
    realized_power_kw: list[float]
    energy_delta_kwh: list[float]
    load_kw: list[float]
    site_electric_load_kw: list[float]
    local_cooling_electric_kw: list[float]
    served_cooling_rt: list[float]
    unserved_cooling_rt: list[float]
    district_cooling_settlement: list[float]
    pv_generation_kw: list[float]
    net_grid_power_kw: list[float]
    net_grid_energy_kwh: list[float]
    direction: list[str]
    unmet_load_kw: list[float]
    blackout_active: list[bool]
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


@dataclass(slots=True)
class BatteryLoadPVScenario:
    """Aggregate root for the deterministic battery + load + weather + PV MVP."""

    scenario_id: str
    time_grid: TimeGrid
    battery: BatteryComponent
    load: "LoadComponent"
    weather: "WeatherComponent"
    pv: "PVComponent"
    price_signal: PriceSignal
    objective: ArbitrageObjectiveRepresentation
    dispatch_requests: DispatchRequestSeries | None = None
    rule_policy: DeterministicRulePolicy | None = None
    blackout_grid_available: list[bool] | None = None
    cooling_service_balance: "CoolingServiceBalance | None" = None
    numeric_tolerance: float = DEFAULT_ABSOLUTE_TOLERANCE

    def validate(self) -> ComponentGraph:
        if (self.dispatch_requests is None) == (self.rule_policy is None):
            raise ValueError("exactly one of dispatch_requests or rule_policy must be provided")

        if self.load.time_grid != self.time_grid:
            raise ValueError("load component must align to the scenario time grid")
        if self.weather.time_grid != self.time_grid:
            raise ValueError("weather component must align to the scenario time grid")
        if self.price_signal.time_grid != self.time_grid:
            raise ValueError("price signal must align to the scenario time grid")
        if self.dispatch_requests is not None:
            if len(self.dispatch_requests.requested_power_kw) != self.time_grid.num_steps:
                raise ValueError("dispatch request length must match the time grid")
        if self.blackout_grid_available is not None:
            if len(self.blackout_grid_available) != self.time_grid.num_steps:
                raise ValueError("blackout_grid_available length must match the time grid")
            if any(not isinstance(value, bool) for value in self.blackout_grid_available):
                raise ValueError("blackout_grid_available values must be booleans")
        if self.cooling_service_balance is not None:
            if self.cooling_service_balance.time_grid != self.time_grid:
                raise ValueError("cooling service balance must align to the scenario time grid")

        if self.objective.allow_export and (
            self.objective.export_price_ratio != self.price_signal.export_price_ratio
        ):
            raise ValueError("objective export discount must match the price signal")
        missing_irradiance = [
            field_name
            for field_name in self.pv.consumed_weather_field_names()
            if field_name not in self.weather.included_field_names()
        ]
        if missing_irradiance:
            formatted = ", ".join(missing_irradiance)
            raise ValueError(f"weather inputs required by the PV derivation are missing: {formatted}")

        graph = ComponentGraph()
        graph.add_component(ComponentRef(name="time_grid", kind="time-grid"))
        graph.add_component(ComponentRef(name="battery", kind="battery"))
        graph.add_component(ComponentRef(name="load", kind="load"))
        graph.add_component(ComponentRef(name="weather", kind="weather"))
        graph.add_component(ComponentRef(name="pv", kind="pv"))
        graph.add_component(ComponentRef(name="price_signal", kind="price-signal"))
        graph.add_component(ComponentRef(name="objective", kind="objective"))
        graph.add_component(ComponentRef(name="simulation_trace", kind="simulation-trace"))
        graph.add_component(ComponentRef(name="net_grid_trace", kind="net-grid-trace"))

        graph.add_connection(Connection("time_grid", "load", Relation.ALIGNS))
        graph.add_connection(Connection("time_grid", "weather", Relation.ALIGNS))
        graph.add_connection(Connection("time_grid", "price_signal", Relation.ALIGNS))
        graph.add_connection(Connection("weather", "pv", Relation.DERIVES))
        graph.add_connection(Connection("battery", "simulation_trace", Relation.PRODUCES))
        graph.add_connection(Connection("load", "net_grid_trace", Relation.FEEDS))
        graph.add_connection(Connection("pv", "net_grid_trace", Relation.FEEDS))
        graph.add_connection(Connection("simulation_trace", "net_grid_trace", Relation.FEEDS))
        graph.add_connection(Connection("price_signal", "net_grid_trace", Relation.PRICES))
        graph.add_connection(Connection("net_grid_trace", "objective", Relation.SETTLES))
        if self.blackout_grid_available is not None:
            graph.add_component(ComponentRef(name="blackout_trace", kind="blackout-trace"))
            graph.add_connection(Connection("time_grid", "blackout_trace", Relation.ALIGNS))
            graph.add_connection(Connection("blackout_trace", "net_grid_trace", Relation.DRIVES))
        if self.cooling_service_balance is not None:
            graph.add_component(
                ComponentRef(name="cooling_service_balance", kind="cooling-service-balance")
            )
            graph.add_connection(
                Connection("time_grid", "cooling_service_balance", Relation.ALIGNS)
            )
            graph.add_connection(
                Connection("cooling_service_balance", "net_grid_trace", Relation.FEEDS)
            )

        if self.dispatch_requests is not None:
            graph.add_component(ComponentRef(name="dispatch_requests", kind="dispatch"))
            graph.add_connection(Connection("time_grid", "dispatch_requests", Relation.ALIGNS))
            graph.add_connection(Connection("dispatch_requests", "battery", Relation.REQUESTS))
        else:
            graph.add_component(ComponentRef(name="rule_policy", kind="policy"))
            graph.add_connection(Connection("time_grid", "rule_policy", Relation.ALIGNS))
            graph.add_connection(Connection("price_signal", "rule_policy", Relation.DRIVES))
            graph.add_connection(Connection("rule_policy", "battery", Relation.REQUESTS))

        return graph

    def evaluate_trace(self) -> BatteryLoadPVTrace:
        """Evaluate one deterministic multi-component scenario trace."""

        from .battery import apply_power_request, build_initial_state
        from .objective import evaluate_net_grid_settlement

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

        pv_generation_kw = self.pv.derive_generation_kw(self.weather)
        local_cooling_electric_kw = self._local_cooling_electric_kw()
        site_electric_load_kw = [
            base_load_kw + cooling_kw
            for base_load_kw, cooling_kw in zip(
                self.load.demand_kw,
                local_cooling_electric_kw,
                strict=True,
            )
        ]
        blackout_active = self._blackout_active_series()

        current_state = build_initial_state(self.battery)
        states: list[BatteryState] = []
        realized_power_kw: list[float] = []
        energy_delta_kwh: list[float] = []
        constraint_events: list[str] = []

        for step_index, requested_power in enumerate(requested_power_kw):
            feasible_request_kw = _grid_feasible_battery_request_kw(
                requested_power_kw=requested_power,
                site_electric_load_kw=site_electric_load_kw[step_index],
                pv_generation_kw=pv_generation_kw[step_index],
                grid_available=not blackout_active[step_index],
            )
            transition = apply_power_request(
                component=self.battery,
                state=current_state,
                requested_power_kw=feasible_request_kw,
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

        settlement = evaluate_net_grid_settlement(
            load_kw=site_electric_load_kw,
            pv_generation_kw=pv_generation_kw,
            realized_battery_power_kw=realized_power_kw,
            time_step_hours=self.time_grid.time_step_hours,
            price_signal=self.price_signal,
            objective=self.objective,
        )
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
            unmet_load_kw = [0.0] * self.time_grid.num_steps
        return BatteryLoadPVTrace(
            states=states,
            requested_power_kw=requested_power_kw,
            realized_power_kw=realized_power_kw,
            energy_delta_kwh=energy_delta_kwh,
            load_kw=list(self.load.demand_kw),
            site_electric_load_kw=site_electric_load_kw,
            local_cooling_electric_kw=local_cooling_electric_kw,
            served_cooling_rt=self._served_cooling_rt(),
            unserved_cooling_rt=self._unserved_cooling_rt(),
            district_cooling_settlement=self._district_cooling_settlement(),
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

    def _blackout_active_series(self) -> list[bool]:
        if self.blackout_grid_available is None:
            return [False] * self.time_grid.num_steps
        return [not value for value in self.blackout_grid_available]

    def _local_cooling_electric_kw(self) -> list[float]:
        if self.cooling_service_balance is None:
            return [0.0] * self.time_grid.num_steps
        return list(self.cooling_service_balance.local_cooling_electric_kw)

    def _served_cooling_rt(self) -> list[float]:
        if self.cooling_service_balance is None:
            return [0.0] * self.time_grid.num_steps
        return list(self.cooling_service_balance.served_cooling_rt)

    def _unserved_cooling_rt(self) -> list[float]:
        if self.cooling_service_balance is None:
            return [0.0] * self.time_grid.num_steps
        return list(self.cooling_service_balance.unserved_cooling_rt)

    def _district_cooling_settlement(self) -> list[float]:
        if self.cooling_service_balance is None:
            return [0.0] * self.time_grid.num_steps
        return list(self.cooling_service_balance.district_cooling_settlement)


__all__ = [
    "ArbitrageScenario",
    "BatteryLoadPVTrace",
    "BatteryLoadPVScenario",
    "BatteryComponent",
    "DispatchRequestSeries",
    "SimulationTrace",
    "TimeGrid",
]
