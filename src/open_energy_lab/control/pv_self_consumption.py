"""Native PV self-consumption controller."""

from __future__ import annotations

from dataclasses import dataclass

from open_energy_lab.core import ControllerContext, DispatchProposal
from open_energy_lab.core.controller import POSITIVE_DISPATCH_MEANING

from ._config import PVSelfConsumptionConfig, require_supported_scenario


@dataclass(slots=True)
class PVSelfConsumptionController:
    """Deterministic controller that biases battery use toward local PV consumption."""

    config: PVSelfConsumptionConfig

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        require_supported_scenario(self.__class__.__name__, context.scenario_kind)
        soc_fraction = context.battery_state.soc_fraction
        load_kw = context.step_inputs["load_kw"]
        pv_generation_kw = context.step_inputs["pv_generation_kw"]

        if pv_generation_kw > load_kw and soc_fraction < self.config.reserve_max_soc:
            requested_power_kw = self.config.charge_request_kw
        elif load_kw > pv_generation_kw and soc_fraction > self.config.reserve_min_soc:
            requested_power_kw = -self.config.discharge_request_kw
        else:
            requested_power_kw = 0.0

        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=requested_power_kw,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name=self.config.controller_name,
        )


__all__ = ["PVSelfConsumptionController"]
