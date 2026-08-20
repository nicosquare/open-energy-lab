"""Public demand package surface for weather-conditioned demand modeling.

The stable demand root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .artifact import load_demand_artifact
    from .fit import fit_demand_model
    from .sampling import DemandSamplingRequest, sample_demand_family
    from .study_inputs import (
        SyntheticCommercialDemandConfig,
        build_measured_demand_training_payload,
        build_synthetic_demand_training_payload,
    )

_EXPORT_MAP = {
    "fit_demand_model": (".fit", "fit_demand_model"),
    "load_demand_artifact": (".artifact", "load_demand_artifact"),
    "DemandSamplingRequest": (".sampling", "DemandSamplingRequest"),
    "sample_demand_family": (".sampling", "sample_demand_family"),
    "SyntheticCommercialDemandConfig": (
        ".study_inputs",
        "SyntheticCommercialDemandConfig",
    ),
    "build_measured_demand_training_payload": (
        ".study_inputs",
        "build_measured_demand_training_payload",
    ),
    "build_synthetic_demand_training_payload": (
        ".study_inputs",
        "build_synthetic_demand_training_payload",
    ),
}

__all__ = [
    "fit_demand_model",
    "load_demand_artifact",
    "DemandSamplingRequest",
    "sample_demand_family",
    "SyntheticCommercialDemandConfig",
    "build_measured_demand_training_payload",
    "build_synthetic_demand_training_payload",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the reserved demand package exports."""

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
