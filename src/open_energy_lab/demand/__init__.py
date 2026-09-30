"""Public demand package surface for weather-conditioned demand modeling.

The stable demand root stays import-light by resolving documented exports from
focused submodules only when callers access them.
"""

from __future__ import annotations

from .artifact import (
    load_demand_artifact,
)
from .fit import (
    fit_demand_model,
)
from .sampling import (
    DemandSamplingRequest,
    sample_demand_family,
)
from .study_inputs import (
    SyntheticCommercialDemandConfig,
    build_measured_demand_training_payload,
    build_synthetic_demand_training_payload,
)

__all__ = [
    "fit_demand_model",
    "load_demand_artifact",
    "DemandSamplingRequest",
    "sample_demand_family",
    "SyntheticCommercialDemandConfig",
    "build_measured_demand_training_payload",
    "build_synthetic_demand_training_payload",
]
