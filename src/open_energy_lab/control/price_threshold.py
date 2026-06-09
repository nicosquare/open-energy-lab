"""Native price-threshold controller."""

from __future__ import annotations

from dataclasses import dataclass

from open_energy_lab.core import ControllerContext, DispatchProposal
from open_energy_lab.core.controller import POSITIVE_DISPATCH_MEANING

from ._config import PriceThresholdConfig, require_supported_scenario


@dataclass(slots=True)
class PriceThresholdController:
    """Deterministic arbitrage controller driven by current-step import prices."""

    config: PriceThresholdConfig

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        require_supported_scenario(self.__class__.__name__, context.scenario_kind)
        import_price = context.price_input.import_price

        if import_price < self.config.charge_below_import_price:
            requested_power_kw = self.config.charge_request_kw
        elif import_price > self.config.discharge_above_import_price:
            requested_power_kw = -self.config.discharge_request_kw
        else:
            requested_power_kw = 0.0

        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=requested_power_kw,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name=self.config.controller_name,
        )


__all__ = ["PriceThresholdController"]
