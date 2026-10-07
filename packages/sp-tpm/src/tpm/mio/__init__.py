"""Mixed-integer optimization (MIO) encodings of SPFlow circuits.

Compile (``compiler``), evaluate, condition, and encode compiled circuits, and
build serialized-SPN chance models (``chance_model``).
"""

from __future__ import annotations

from ._common import (
    SPNSolverDependencyUnavailableError,
)
from .compiler import (
    UnsupportedSPFlowModuleError,
    spflow_operation_children,
    compile_spflow_model_to_mio,
)
from .condition import (
    condition_compiled_spflow_mio,
)
from .evaluate import (
    evaluate_compiled_spflow_probability,
)
from .encode import (
    bound_piecewise_auxiliaries,
    build_compiled_spflow_decision_link_model,
    encode_conditioned_spflow_circuit,
)
from .chance_model import (
    build_spn_chance_model,
    extract_spn_solution,
    infer_max_sum_terms,
    require_pyomo_backend,
)

__all__ = [
    "SPNSolverDependencyUnavailableError",
    "UnsupportedSPFlowModuleError",
    "bound_piecewise_auxiliaries",
    "build_compiled_spflow_decision_link_model",
    "build_spn_chance_model",
    "compile_spflow_model_to_mio",
    "condition_compiled_spflow_mio",
    "evaluate_compiled_spflow_probability",
    "encode_conditioned_spflow_circuit",
    "extract_spn_solution",
    "infer_max_sum_terms",
    "require_pyomo_backend",
    "spflow_operation_children",
]
