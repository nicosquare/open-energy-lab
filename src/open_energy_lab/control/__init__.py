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
}

__all__ = [
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "SocGuardrailConfig",
    "SocGuardrailController",
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
    return sorted(list(globals().keys()) + __all__)
