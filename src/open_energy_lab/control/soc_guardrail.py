"""Scaffolded native SOC guardrail controller."""

from __future__ import annotations

from dataclasses import dataclass

from open_energy_lab.core import ControllerContext, DispatchProposal
from open_energy_lab.core.controller import POSITIVE_DISPATCH_MEANING

from ._config import SocGuardrailConfig, require_supported_scenario


@dataclass(slots=True)
class SocGuardrailController:
    """Import-light controller scaffold that already conforms to the stable contract."""

    config: SocGuardrailConfig

    def propose_dispatch(self, context: ControllerContext) -> DispatchProposal:
        require_supported_scenario(self.__class__.__name__, context.scenario_kind)
        return DispatchProposal(
            step_index=context.step_index,
            requested_power_kw=0.0,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            controller_name=self.config.controller_name,
        )


__all__ = ["SocGuardrailController"]
