"""Stable package-root public surface for shipped native controllers.

Ordinary ``open_energy_lab.control`` imports stay import-light by resolving the
documented controller exports lazily.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._config import (
        PVSelfConsumptionConfig,
        PriceThresholdConfig,
        SocGuardrailConfig,
    )
    from .price_threshold import PriceThresholdController
    from .pv_self_consumption import PVSelfConsumptionController
    from .soc_guardrail import SocGuardrailController
    from .stacked_service import (
        ArbitrageOnlyBaselineConfig,
        BaselineScheduleBundle,
        RegulationOnlyBaselineConfig,
        StackedBaselineValidationError,
        StackedHeuristicConfig,
        build_arbitrage_only_baseline,
        build_regulation_only_baseline,
        build_stacked_heuristic_baseline,
    )
    from .restoration_service import (
        AFRRBaselineConfig,
        AFRRBaselineMode,
        DirectionalCapacityCommitmentInterval,
        DirectionalCapacitySchedule,
        MFRRBaselineConfig,
        MFRRBaselineMode,
        RestorationBaselineBundle,
        RestorationCapability,
        RestorationControlValidationError,
        RestorationEnergyBaselineInterval,
        RestorationEnergyBaselineSchedule,
        build_afrr_baseline,
        build_afrr_baseline_config,
        build_afrr_directional_capacity_schedule,
        build_mfrr_baseline,
        build_mfrr_baseline_config,
        build_mfrr_directional_capacity_schedule,
        build_restoration_capability,
    )


_EXPORT_MAP = {
    "PVSelfConsumptionConfig": ("._config", "PVSelfConsumptionConfig"),
    "PVSelfConsumptionController": (
        ".pv_self_consumption",
        "PVSelfConsumptionController",
    ),
    "PriceThresholdConfig": ("._config", "PriceThresholdConfig"),
    "PriceThresholdController": (".price_threshold", "PriceThresholdController"),
    "SocGuardrailConfig": ("._config", "SocGuardrailConfig"),
    "SocGuardrailController": (".soc_guardrail", "SocGuardrailController"),
    "ArbitrageOnlyBaselineConfig": (
        ".stacked_service",
        "ArbitrageOnlyBaselineConfig",
    ),
    "BaselineScheduleBundle": (".stacked_service", "BaselineScheduleBundle"),
    "RegulationOnlyBaselineConfig": (
        ".stacked_service",
        "RegulationOnlyBaselineConfig",
    ),
    "StackedBaselineValidationError": (
        ".stacked_service",
        "StackedBaselineValidationError",
    ),
    "StackedHeuristicConfig": (".stacked_service", "StackedHeuristicConfig"),
    "build_arbitrage_only_baseline": (
        ".stacked_service",
        "build_arbitrage_only_baseline",
    ),
    "build_regulation_only_baseline": (
        ".stacked_service",
        "build_regulation_only_baseline",
    ),
    "build_stacked_heuristic_baseline": (
        ".stacked_service",
        "build_stacked_heuristic_baseline",
    ),
    "RestorationControlValidationError": (
        ".restoration_service",
        "RestorationControlValidationError",
    ),
    "DirectionalCapacityCommitmentInterval": (
        ".restoration_service",
        "DirectionalCapacityCommitmentInterval",
    ),
    "DirectionalCapacitySchedule": (
        ".restoration_service",
        "DirectionalCapacitySchedule",
    ),
    "RestorationEnergyBaselineInterval": (
        ".restoration_service",
        "RestorationEnergyBaselineInterval",
    ),
    "RestorationEnergyBaselineSchedule": (
        ".restoration_service",
        "RestorationEnergyBaselineSchedule",
    ),
    "RestorationCapability": (
        ".restoration_service",
        "RestorationCapability",
    ),
    "AFRRBaselineMode": (".restoration_service", "AFRRBaselineMode"),
    "AFRRBaselineConfig": (".restoration_service", "AFRRBaselineConfig"),
    "MFRRBaselineMode": (".restoration_service", "MFRRBaselineMode"),
    "MFRRBaselineConfig": (".restoration_service", "MFRRBaselineConfig"),
    "RestorationBaselineBundle": (
        ".restoration_service",
        "RestorationBaselineBundle",
    ),
    "build_restoration_capability": (
        ".restoration_service",
        "build_restoration_capability",
    ),
    "build_afrr_directional_capacity_schedule": (
        ".restoration_service",
        "build_afrr_directional_capacity_schedule",
    ),
    "build_afrr_baseline_config": (
        ".restoration_service",
        "build_afrr_baseline_config",
    ),
    "build_afrr_baseline": (".restoration_service", "build_afrr_baseline"),
    "build_mfrr_directional_capacity_schedule": (
        ".restoration_service",
        "build_mfrr_directional_capacity_schedule",
    ),
    "build_mfrr_baseline_config": (
        ".restoration_service",
        "build_mfrr_baseline_config",
    ),
    "build_mfrr_baseline": (".restoration_service", "build_mfrr_baseline"),
}

__all__ = [
    "AFRRBaselineConfig",
    "AFRRBaselineMode",
    "ArbitrageOnlyBaselineConfig",
    "BaselineScheduleBundle",
    "DirectionalCapacityCommitmentInterval",
    "DirectionalCapacitySchedule",
    "MFRRBaselineConfig",
    "MFRRBaselineMode",
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "RegulationOnlyBaselineConfig",
    "RestorationBaselineBundle",
    "RestorationCapability",
    "RestorationControlValidationError",
    "RestorationEnergyBaselineInterval",
    "RestorationEnergyBaselineSchedule",
    "SocGuardrailConfig",
    "SocGuardrailController",
    "StackedBaselineValidationError",
    "StackedHeuristicConfig",
    "build_afrr_baseline",
    "build_afrr_baseline_config",
    "build_afrr_directional_capacity_schedule",
    "build_arbitrage_only_baseline",
    "build_mfrr_baseline",
    "build_mfrr_baseline_config",
    "build_mfrr_directional_capacity_schedule",
    "build_regulation_only_baseline",
    "build_restoration_capability",
    "build_stacked_heuristic_baseline",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the stable control package exports."""

    try:
        module_name, attribute_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
