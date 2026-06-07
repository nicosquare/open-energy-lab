"""Native SOC guardrail controller."""

from __future__ import annotations

from dataclasses import dataclass

from open_energy_lab.core import ControllerContext, DispatchProposal
from open_energy_lab.core.controller import POSITIVE_DISPATCH_MEANING

from ._config import SocGuardrailConfig, require_supported_scenario


@dataclass(slots=True)
class SocGuardrailController:
    """Deterministic controller that keeps SOC inside a configured band."""

    config: SocGuardrailConfig

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        require_supported_scenario(self.__class__.__name__, context.scenario_kind)
        soc_fraction = context.battery_state.soc_fraction

        if soc_fraction < self.config.target_min_soc:
            requested_power_kw = self.config.charge_request_kw
        elif soc_fraction > self.config.target_max_soc:
            requested_power_kw = -self.config.discharge_request_kw
        else:
            requested_power_kw = 0.0

        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=requested_power_kw,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name=self.config.controller_name,
        )


__all__ = ["SocGuardrailController"]
