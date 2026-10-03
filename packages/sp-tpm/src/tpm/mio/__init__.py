"""Mixed-integer optimization (MIO) encodings of SPFlow circuits.

Compile (``compiler``), evaluate, condition, and encode compiled circuits, and
build serialized-SPN chance models (``chance_model``).
"""

from __future__ import annotations

# The two `name as name` imports are private helpers tpm_for_sp reads from
# tpm.mio; B5 decides whether they become public.
from ._common import (
    SPNSolverDependencyUnavailableError,
)
from .compiler import (
    UnsupportedSPFlowModuleError,
    _spflow_operation_children as _spflow_operation_children,
    compile_spflow_model_to_mio,
)
from .condition import (
    condition_compiled_spflow_mio,
)
from .evaluate import (
    evaluate_compiled_spflow_probability,
)
from .encode import (
    _bound_piecewise_auxiliaries as _bound_piecewise_auxiliaries,
    build_compiled_spflow_decision_link_model,
    encode_conditioned_spflow_circuit,
)
from .chance_model import (
    SPNModelingTerms,
    SPNPiecewiseCurveSpec,
    SPNSolveConfig,
    SPNSolveSummary,
    SPNSolverUnavailableError,
    build_spn_chance_model,
    build_spn_modeling_terms,
    extract_spn_solution,
    infer_max_sum_terms,
    require_pyomo_backend,
    solve_spn_chance_model,
)

__all__ = [
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_compiled_spflow_decision_link_model",
    "build_spn_modeling_terms",
    "build_spn_chance_model",
    "compile_spflow_model_to_mio",
    "condition_compiled_spflow_mio",
    "evaluate_compiled_spflow_probability",
    "encode_conditioned_spflow_circuit",
    "extract_spn_solution",
    "infer_max_sum_terms",
    "require_pyomo_backend",
    "solve_spn_chance_model",
]
