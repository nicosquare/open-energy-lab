"""Lazy SPFlow dependency boundary for TPM fit, query, and planning workflows."""

from __future__ import annotations

import math
import pickle
import random
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .artifact import TPMArtifact
    from .data import TPMTrainingData
    from .features import TPMFeatureSpec


class SPFlowDependencyUnavailableError(ImportError):
    """Raised when a TPM workflow requires SPFlow but it is unavailable."""


_BACKEND_ADAPTER_REGISTRY: dict[
    str,
    Callable[[Mapping[str, object]], object],
] = {}


@dataclass(frozen=True, slots=True)
class _LegacySpflowApiBindings:
    """Resolved legacy SPFlow API bindings used by the migrated TPM path."""

    module_prefix: str
    context_class: Any
    leaf_class: Any
    product_class: Any
    sum_class: Any
    get_topological_order: Callable[..., object]
    meta_type: Any
    learn_mspn: Callable[..., object]
    marginalize: Callable[..., object]
    log_likelihood: Callable[..., object]


@dataclass(frozen=True, slots=True)
class _LegacySpnBackendAdapter:
    """Adapter for the legacy SPFlow `spn.*` API used by `legacy/old_tpm`."""

    backend_module: Any

    @property
    def adapter_name(self) -> str:
        return "legacy-spn-api"

    @property
    def backend_name(self) -> str:
        return getattr(self.backend_module, "__name__", type(self.backend_module).__name__)

    @property
    def backend_version(self) -> str | None:
        version = getattr(self.backend_module, "__version__", None)
        return None if version is None else str(version)

    def detect_capabilities(self) -> dict[str, object]:
        bindings = _load_legacy_spflow_api()
        legacy_api_available = bindings is not None
        if legacy_api_available:
            return {
                "installed_backend_module": self.backend_name,
                "installed_backend_version": self.backend_version,
                "backend_adapter_name": self.adapter_name,
                "legacy_spn_api_available": legacy_api_available,
                "legacy_api_module_prefix": bindings.module_prefix,
                "supports_real_spn_training": legacy_api_available,
                "supports_real_spn_query": legacy_api_available,
                "supports_spn_mip_serialization": legacy_api_available,
                "fallback_query_strategy": None,
                "reason": (
                    "legacy SPFlow backend available via "
                    f"{bindings.module_prefix}.* modules"
                ),
            }
        reason = (
            "installed backend does not expose a supported legacy SPFlow API layout "
            "under 'spn.*' or 'spflow.*'"
        )
        return {
            "installed_backend_module": self.backend_name,
            "installed_backend_version": self.backend_version,
            "backend_adapter_name": self.adapter_name,
            "legacy_spn_api_available": False,
            "legacy_api_module_prefix": None,
            "supports_real_spn_training": False,
            "supports_real_spn_query": False,
            "supports_spn_mip_serialization": False,
            "fallback_query_strategy": "table",
            "reason": reason,
        }

    def fit_runtime_payload(self, runtime_payload: Mapping[str, object]) -> dict[str, object]:
        payload = {str(key): value for key, value in runtime_payload.items()}
        if hasattr(self.backend_module, "fit_tpm_model"):
            custom_payload = self.backend_module.fit_tpm_model(payload)
            if not isinstance(custom_payload, Mapping):
                raise TypeError("backend fit_tpm_model must return a mapping payload")
            return {str(key): value for key, value in custom_payload.items()}

        if not _legacy_spn_api_is_available():
            return payload

        import numpy as np

        api = _require_legacy_spflow_api()
        _set_training_seed(payload.get("training_random_seed"))
        context = _build_spflow_context(payload, api=api)
        matrix = np.asarray(payload["matrix"], dtype=float)
        model = api.learn_mspn(matrix, context, **dict(payload["learn_mspn_kwargs"]))
        payload["query_strategy"] = "spflow"
        payload["spn_model"] = model
        payload["conditional_models"] = _build_conditional_models(payload, model, api=api)
        return payload

    def evaluate_runtime_query(
        self,
        runtime_payload: Mapping[str, object],
        *,
        feature_specs: Mapping[str, TPMFeatureSpec],
        decision_assignments: Mapping[str, object],
        marginalized_features: tuple[str, ...],
        event_target_name: str,
        output_mode: str,
        numeric_tolerance: float,
    ) -> dict[str, object]:
        return _evaluate_runtime_spflow_query(
            runtime_payload,
            feature_specs=feature_specs,
            decision_assignments=decision_assignments,
            marginalized_features=marginalized_features,
            event_target_name=event_target_name,
            output_mode=output_mode,
            numeric_tolerance=numeric_tolerance,
        )


def detect_spflow_backend_capabilities(backend: Any | None = None) -> dict[str, object]:
    """Report whether one configured backend can execute the real legacy SPFlow path."""

    adapter = _resolve_spflow_backend_adapter(backend)
    return adapter.detect_capabilities()


def register_spflow_backend_adapter(
    adapter_name: str,
    factory: Callable[[Mapping[str, object]], object],
) -> None:
    """Register one persisted-runtime adapter factory by adapter_name."""

    normalized_name = str(adapter_name)
    if not normalized_name:
        raise ValueError("adapter_name must be non-empty")
    if not callable(factory):
        raise TypeError("factory must be callable")
    _BACKEND_ADAPTER_REGISTRY[normalized_name] = factory


def unregister_spflow_backend_adapter(adapter_name: str) -> None:
    """Remove one persisted-runtime adapter factory if it exists."""

    _BACKEND_ADAPTER_REGISTRY.pop(str(adapter_name), None)



def require_spflow_backend() -> Any:
    """Import SPFlow only when a TPM fit or backend-backed query is invoked."""

    try:
        return import_module("spn")
    except ImportError:
        try:
            return import_module("spflow")
        except ImportError as exc:  # pragma: no cover - depends on optional install state
            raise SPFlowDependencyUnavailableError(
                "SPFlow-backed TPM workflows require the optional 'spflow' dependency. "
                "This import boundary is intentionally lazy so open_energy_lab.tpm "
                "stays import-light until the backend is used."
            ) from exc


def _resolve_spflow_backend_adapter(backend: Any | None) -> _LegacySpnBackendAdapter:
    if backend is not None and hasattr(backend, "fit_runtime_payload") and hasattr(
        backend,
        "detect_capabilities",
    ):
        return backend

    if backend is not None:
        return _LegacySpnBackendAdapter(backend_module=backend)

    spn_spec = find_spec("spn")
    if spn_spec is not None:
        try:
            return _LegacySpnBackendAdapter(backend_module=import_module("spn"))
        except ImportError as exc:  # pragma: no cover - defensive import failure
            raise SPFlowDependencyUnavailableError(
                "Configured legacy SPFlow backend could not be imported."
            ) from exc

    spflow_spec = find_spec("spflow")
    if spflow_spec is not None:
        return _LegacySpnBackendAdapter(backend_module=import_module("spflow"))

    raise SPFlowDependencyUnavailableError(
        "SPFlow-backed TPM workflows require the optional 'spflow' dependency. "
        "This import boundary is intentionally lazy so open_energy_lab.tpm "
        "stays import-light until the backend is used."
    )


def _adapter_from_runtime_payload(runtime_payload: Mapping[str, object]) -> _LegacySpnBackendAdapter:
    adapter_name = str(runtime_payload.get("backend_adapter_name", "legacy-spn-api"))
    factory = _BACKEND_ADAPTER_REGISTRY.get(adapter_name)
    if factory is None:
        raise ValueError(f"unsupported persisted backend_adapter_name {adapter_name!r}")
    adapter = factory(runtime_payload)
    if not hasattr(adapter, "evaluate_runtime_query"):
        raise TypeError(
            f"adapter factory for {adapter_name!r} must return an object with evaluate_runtime_query()"
        )
    return adapter


def fit_spflow_model(
    training_data: TPMTrainingData,
    *,
    feature_schema: tuple[TPMFeatureSpec, ...],
    canonical_target_name: str,
    event_target_name: str,
    target_threshold: float,
    training_random_seed: int | None,
    learn_mspn_kwargs: Mapping[str, object] | None = None,
    backend: Any | None = None,
    payload_path: str | Path | None = None,
    payload_format: str = "pickle-path",
) -> tuple[object, str]:
    """Fit one TPM sidecar payload or inline summary for the configured backend."""

    normalized_kwargs = {
        str(key): value for key, value in dict(learn_mspn_kwargs or {}).items()
    }
    adapter = _resolve_spflow_backend_adapter(backend)
    backend_module = adapter.backend_module

    if payload_format == "json-inline":
        return (
            {
                "payload_kind": "spflow-fit-summary",
                "backend_module": getattr(
                    backend_module,
                    "__name__",
                    type(backend_module).__name__,
                ),
                "backend_version": getattr(backend_module, "__version__", None),
                "canonical_target_name": canonical_target_name,
                "event_target_name": event_target_name,
                "training_random_seed": training_random_seed,
                "row_count": len(training_data.rows),
                "column_order": list(training_data.column_order),
                "normalized_matrix_shape": [
                    len(training_data.normalized_rows),
                    len(training_data.column_order),
                ],
                "learn_mspn_kwargs": normalized_kwargs,
            },
            "json-inline",
        )

    resolved_payload_path = _resolved_payload_path(payload_path)
    runtime_payload = _build_runtime_payload(
        training_data,
        feature_schema=feature_schema,
        canonical_target_name=canonical_target_name,
        event_target_name=event_target_name,
        target_threshold=target_threshold,
        training_random_seed=training_random_seed,
        learn_mspn_kwargs=normalized_kwargs,
        adapter=adapter,
    )
    pickle_payload = adapter.fit_runtime_payload(runtime_payload)
    resolved_payload_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_payload_path.write_bytes(pickle.dumps(pickle_payload))

    return (
        {
            "locator": resolved_payload_path.name if payload_path is not None else resolved_payload_path.as_posix(),
            "serialization": "pickle",
            "backend": "spflow",
        },
        "pickle-path",
    )


def has_spflow_payload(artifact: TPMArtifact) -> bool:
    """Return whether the artifact points at a persisted backend sidecar payload."""

    return (
        artifact.spn_payload_format == "pickle-path"
        and bool(_payload_locator(artifact.spn_payload))
    )


def load_spflow_payload(artifact: TPMArtifact) -> dict[str, object] | None:
    """Load one persisted backend payload from a TPM artifact locator."""

    payload_path = resolve_spflow_payload_path(artifact)
    if payload_path is None or not payload_path.is_file():
        return None
    payload = pickle.loads(payload_path.read_bytes())
    if not isinstance(payload, Mapping):
        raise TypeError("persisted SPFlow payload must deserialize to a mapping")
    return {str(key): value for key, value in payload.items()}


def resolve_spflow_payload_path(artifact: TPMArtifact) -> Path | None:
    """Resolve the persisted sidecar path relative to the TPM artifact location."""

    locator = _payload_locator(artifact.spn_payload)
    if not locator:
        return None

    locator_path = Path(locator)
    if locator_path.is_absolute():
        return locator_path
    if artifact.source_path:
        return Path(artifact.source_path).resolve().parent / locator_path
    return locator_path


def evaluate_spflow_query(
    artifact: TPMArtifact,
    *,
    feature_specs: Mapping[str, TPMFeatureSpec],
    decision_assignments: Mapping[str, object],
    marginalized_features: tuple[str, ...],
    canonical_target_name: str,
    event_target_name: str,
    output_mode: str,
    numeric_tolerance: float,
) -> dict[str, object] | None:
    """Evaluate one persisted sidecar-backed TPM query."""

    runtime_payload = load_spflow_payload(artifact)
    if runtime_payload is None:
        return None

    raw_rows = runtime_payload.get("raw_rows")
    if not isinstance(raw_rows, tuple | list):
        raise TypeError("persisted SPFlow payload must include raw_rows")

    query_strategy = str(runtime_payload.get("query_strategy", "table"))
    if query_strategy == "spflow":
        return _adapter_from_runtime_payload(runtime_payload).evaluate_runtime_query(
            runtime_payload,
            feature_specs=feature_specs,
            decision_assignments=decision_assignments,
            marginalized_features=marginalized_features,
            event_target_name=event_target_name,
            output_mode=output_mode,
            numeric_tolerance=numeric_tolerance,
        )

    matched_rows = [
        row
        for row in raw_rows
        if _row_matches_assignments(
            row,
            assignments=decision_assignments,
            feature_specs=feature_specs,
            numeric_tolerance=numeric_tolerance,
        )
    ]
    total_row_count = len(raw_rows)
    matched_row_count = len(matched_rows)
    if output_mode == "conditional_probability":
        value = (
            0.0
            if matched_row_count == 0
            else sum(int(row[event_target_name]) for row in matched_rows) / matched_row_count
        )
    else:
        evidence_probability = matched_row_count / total_row_count if total_row_count else 0.0
        value = math.log(max(evidence_probability, numeric_tolerance))

    return {
        "matched_row_count": matched_row_count,
        "total_row_count": total_row_count,
        "source": "spflow_sidecar_table",
        "value": float(value),
        "resolved_target_name": event_target_name,
        "canonical_target_name": canonical_target_name,
    }


def build_spn_mip_payload(
    artifact: TPMArtifact,
    *,
    decision_features: tuple[str, ...],
    chance_limit_epsilon: float,
    target_threshold: float | None = None,
    shortfall_threshold: float | None = None,
) -> dict[str, object] | None:
    """Build one solver-facing SPN handoff payload from a persisted sidecar."""

    if target_threshold is None and shortfall_threshold is None:
        raise ValueError("target_threshold must be provided")
    if target_threshold is not None and shortfall_threshold is not None:
        if float(target_threshold) != float(shortfall_threshold):
            raise ValueError(
                "target_threshold and shortfall_threshold must match when both are provided"
            )
    resolved_target_threshold = float(
        target_threshold if target_threshold is not None else shortfall_threshold
    )

    runtime_payload = load_spflow_payload(artifact)
    if runtime_payload is None:
        return None
    if not _runtime_payload_supports_spn_mip(runtime_payload):
        return None

    raw_rows = runtime_payload.get("raw_rows")
    if not isinstance(raw_rows, tuple | list):
        raise TypeError("persisted SPFlow payload must include raw_rows")

    decision_domains = {
        feature_name: list(
            dict.fromkeys(row[feature_name] for row in raw_rows if feature_name in row)
        )
        for feature_name in decision_features
    }
    conditional_models = runtime_payload.get("conditional_models")
    if (
        runtime_payload.get("query_strategy") == "spflow"
        and runtime_payload.get("spn_model") is not None
    ):
        conditional_models = _build_conditional_models(
            runtime_payload,
            runtime_payload["spn_model"],
            api=_require_legacy_spflow_api(),
            decision_feature_names=decision_features,
        )
    return {
        "source": "spflow_backend",
        "payload_locator": (
            resolve_spflow_payload_path(artifact).as_posix()
            if resolve_spflow_payload_path(artifact) is not None
            else None
        ),
        "decision_features": list(decision_features),
        "decision_domains": decision_domains,
        "chance_limit_epsilon": float(chance_limit_epsilon),
        "target_threshold": resolved_target_threshold,
        "shortfall_threshold": resolved_target_threshold,
        "canonical_target_name": runtime_payload["canonical_target_name"],
        "event_target_name": runtime_payload["event_target_name"],
        "feature_schema": list(runtime_payload["feature_schema"]),
        "sum_encoding_mode": str(
            artifact.approximation_metadata.get("sum_encoding_mode", "piecewise")
        ),
        "query_strategy": runtime_payload["query_strategy"],
        "row_count": len(raw_rows),
        "conditional_models": conditional_models,
    }


def supports_spn_mip(artifact: TPMArtifact) -> bool:
    """Return whether one artifact exposes a serialized SPN MIO payload."""

    runtime_payload = load_spflow_payload(artifact)
    return runtime_payload is not None and _runtime_payload_supports_spn_mip(runtime_payload)


__all__ = [
    "detect_spflow_backend_capabilities",
    "SPFlowDependencyUnavailableError",
    "build_spn_mip_payload",
    "evaluate_spflow_query",
    "fit_spflow_model",
    "has_spflow_payload",
    "load_spflow_payload",
    "register_spflow_backend_adapter",
    "require_spflow_backend",
    "resolve_spflow_payload_path",
    "supports_spn_mip",
    "unregister_spflow_backend_adapter",
]


def _resolved_payload_path(payload_path: str | Path | None) -> Path:
    if payload_path is not None:
        return Path(payload_path)
    temp_dir = Path(tempfile.mkdtemp(prefix="open-energy-lab-tpm-"))
    return temp_dir / "spn_payload.pkl"


def _build_runtime_payload(
    training_data: TPMTrainingData,
    *,
    feature_schema: tuple[TPMFeatureSpec, ...],
    canonical_target_name: str,
    event_target_name: str,
    target_threshold: float,
    training_random_seed: int | None,
    learn_mspn_kwargs: Mapping[str, object],
    adapter: _LegacySpnBackendAdapter,
) -> dict[str, object]:
    event_target_index = training_data.column_order.index(event_target_name)
    capability_report = adapter.detect_capabilities()
    return {
        "payload_kind": "spflow-runtime-payload",
        "backend_module": adapter.backend_name,
        "backend_version": adapter.backend_version,
        "backend_adapter_name": adapter.adapter_name,
        "backend_capabilities": capability_report,
        "legacy_api_module_prefix": capability_report.get("legacy_api_module_prefix"),
        "canonical_target_name": canonical_target_name,
        "event_target_name": event_target_name,
        "target_threshold": float(target_threshold),
        "training_random_seed": training_random_seed,
        "learn_mspn_kwargs": dict(learn_mspn_kwargs),
        "column_order": list(training_data.column_order),
        "feature_schema": [spec.to_dict() for spec in feature_schema],
        "normalized_rows": [dict(row) for row in training_data.normalized_rows],
        "raw_rows": [dict(row) for row in training_data.rows],
        "matrix": [list(row) for row in training_data.matrix],
        "event_target_index": event_target_index,
        "query_strategy": "table",
    }


def _legacy_spn_api_is_available() -> bool:
    return _load_legacy_spflow_api() is not None


@lru_cache(maxsize=1)
def _load_legacy_spflow_api() -> _LegacySpflowApiBindings | None:
    for module_prefix in ("spn", "spflow"):
        try:
            _patch_legacy_networkx_aliases()
            _patch_legacy_scipy_aliases()
            base_module = import_module(f"{module_prefix}.structure.Base")
            statistical_types_module = import_module(
                f"{module_prefix}.structure.StatisticalTypes"
            )
            learning_module = import_module(
                f"{module_prefix}.algorithms.LearningWrappers"
            )
            marginalization_module = import_module(
                f"{module_prefix}.algorithms.Marginalization"
            )
            inference_module = import_module(f"{module_prefix}.algorithms.Inference")
        except ImportError:
            continue
        return _LegacySpflowApiBindings(
            module_prefix=module_prefix,
            context_class=base_module.Context,
            leaf_class=base_module.Leaf,
            product_class=base_module.Product,
            sum_class=base_module.Sum,
            get_topological_order=base_module.get_topological_order,
            meta_type=statistical_types_module.MetaType,
            learn_mspn=learning_module.learn_mspn,
            marginalize=marginalization_module.marginalize,
            log_likelihood=inference_module.log_likelihood,
        )
    return None


def _require_legacy_spflow_api() -> _LegacySpflowApiBindings:
    bindings = _load_legacy_spflow_api()
    if bindings is None:
        raise SPFlowDependencyUnavailableError(
            "SPFlow-backed TPM workflows require a legacy-compatible SPFlow API "
            "layout under 'spn.*' or 'spflow.*'."
        )
    return bindings


def _patch_legacy_networkx_aliases() -> None:
    """Provide import-time aliases expected by older SPFlow releases."""

    try:
        networkx = import_module("networkx")
    except ImportError:  # pragma: no cover - networkx is required by legacy SPFlow
        return
    if hasattr(networkx, "from_numpy_matrix"):
        from_numpy_matrix = getattr(networkx, "from_numpy_matrix")
    else:
        from_numpy_array = getattr(networkx, "from_numpy_array", None)
        if not callable(from_numpy_array):
            return
        setattr(networkx, "from_numpy_matrix", from_numpy_array)
        from_numpy_matrix = from_numpy_array

    try:
        convert_matrix = import_module("networkx.convert_matrix")
    except ImportError:  # pragma: no cover - depends on networkx layout
        return
    if not hasattr(convert_matrix, "from_numpy_matrix"):
        setattr(convert_matrix, "from_numpy_matrix", from_numpy_matrix)


def _patch_legacy_scipy_aliases() -> None:
    """Provide module attributes expected by older SPFlow releases."""

    try:
        scipy = import_module("scipy")
    except ImportError:  # pragma: no cover - scipy is required by legacy SPFlow
        return
    if not hasattr(scipy, "NINF"):
        setattr(scipy, "NINF", float("-inf"))


def _set_training_seed(seed: object) -> None:
    if seed is None:
        return

    normalized_seed = int(seed)
    random.seed(normalized_seed)
    try:
        import numpy as np

        np.random.seed(normalized_seed)
    except ImportError:  # pragma: no cover - numpy is present in the base environment
        return


def _build_spflow_context(
    runtime_payload: Mapping[str, object],
    *,
    api: _LegacySpflowApiBindings | None = None,
) -> object:
    import numpy as np

    bindings = api if api is not None else _require_legacy_spflow_api()
    context_class = bindings.context_class
    meta_type = bindings.meta_type

    feature_schema = runtime_payload["feature_schema"]
    matrix = np.asarray(runtime_payload["matrix"], dtype=float)
    meta_types: list[object] = []
    domains: list[object] = []
    feature_names: list[str] = []
    for index, feature_payload in enumerate(feature_schema):
        feature_name = str(feature_payload["feature_name"])
        feature_type = str(feature_payload["feature_type"])
        feature_names.append(feature_name)
        if feature_type == "continuous":
            meta_types.append(meta_type.REAL)
            domains.append(_observed_real_domain(matrix[:, index]))
            continue
        if feature_type == "mixed":
            meta_types.append(meta_type.REAL)
            domains.append(_observed_real_domain(matrix[:, index]))
            continue
        if feature_type == "binary":
            binary_type = getattr(meta_type, "BINARY", getattr(meta_type, "DISCRETE"))
            meta_types.append(binary_type)
            domains.append(np.asarray([0.0, 1.0], dtype=float))
            continue
        meta_types.append(meta_type.DISCRETE)
        discrete_values = feature_payload.get("ordering") or feature_payload["discrete_values"]
        domains.append(np.asarray(range(len(discrete_values)), dtype=float))

    return context_class(
        meta_types=meta_types,
        domains=domains,
        feature_names=feature_names,
    )


def _observed_real_domain(column: object) -> object:
    import numpy as np

    values = np.asarray(column, dtype=float)
    lower = float(np.nanmin(values))
    upper = float(np.nanmax(values))
    if math.isclose(lower, upper, rel_tol=0.0, abs_tol=1e-12):
        upper = lower + 1e-6
    return np.asarray([lower, upper], dtype=float)


def _build_conditional_models(
    runtime_payload: Mapping[str, object],
    spn_model: object,
    *,
    api: _LegacySpflowApiBindings | None = None,
    decision_feature_names: Sequence[str] | None = None,
) -> dict[str, object]:
    bindings = api if api is not None else _require_legacy_spflow_api()

    column_order = tuple(str(item) for item in runtime_payload["column_order"])
    feature_schema = _sequence_of_mappings(
        runtime_payload["feature_schema"],
        field_name="feature_schema",
    )
    event_target_name = str(runtime_payload["event_target_name"])
    resolved_decision_feature_names = (
        tuple(str(name) for name in decision_feature_names)
        if decision_feature_names is not None
        else tuple(
            str(item["feature_name"])
            for item in feature_schema
            if str(item.get("feature_role", "")) == "decision"
        )
    )
    keep_for_denominator = {
        index
        for index, name in enumerate(column_order)
        if name in resolved_decision_feature_names
    }
    keep_for_numerator = {
        index
        for index, name in enumerate(column_order)
        if name in {event_target_name, *resolved_decision_feature_names}
    }

    denominator_model = bindings.marginalize(spn_model, keep_for_denominator)
    numerator_model = bindings.marginalize(spn_model, keep_for_numerator)
    return {
        "numerator_model": _serialize_spn_model(
            numerator_model,
            feature_schema=feature_schema,
            fixed_assignments={event_target_name: 1.0},
            api=bindings,
        ),
        "denominator_model": _serialize_spn_model(
            denominator_model,
            feature_schema=feature_schema,
            fixed_assignments={},
            api=bindings,
        ),
    }


def _serialize_spn_model(
    spn_model: object,
    *,
    feature_schema: tuple[Mapping[str, object], ...],
    fixed_assignments: Mapping[str, object],
    api: _LegacySpflowApiBindings | None = None,
) -> dict[str, object]:
    bindings = api if api is not None else _require_legacy_spflow_api()
    feature_by_index = {
        index: feature_payload for index, feature_payload in enumerate(feature_schema)
    }

    nodes: list[dict[str, object]] = []
    for node in bindings.get_topological_order(spn_model):
        scope = getattr(node, "scope", None)
        if isinstance(node, bindings.leaf_class):
            if isinstance(scope, Sequence):
                if len(scope) != 1:
                    raise NotImplementedError("serialized TPM payloads do not support multivariate leaves")
                feature_index = int(scope[0])
            else:
                feature_index = int(scope)
            feature_payload = feature_by_index[feature_index]
            feature_name = str(feature_payload["feature_name"])
            feature_type = str(feature_payload["feature_type"])
            serialized_leaf = {
                "id": int(node.id),
                "feature_name": feature_name,
                "densities": [float(value) for value in node.densities],
            }
            if feature_name in fixed_assignments:
                fixed_value = fixed_assignments[feature_name]
                serialized_leaf["fixed_value"] = _normalized_fixed_value(
                    feature_payload,
                    fixed_value,
                )
            if feature_type == "binary":
                serialized_leaf["type"] = "leaf_binary"
            elif feature_type == "categorical":
                serialized_leaf["type"] = "leaf_categorical"
            else:
                serialized_leaf["type"] = "leaf_histogram"
                serialized_leaf["breaks"] = [float(value) for value in node.breaks]
            nodes.append(serialized_leaf)
            continue

        if isinstance(node, bindings.product_class):
            nodes.append(
                {
                    "id": int(node.id),
                    "type": "product",
                    "children": [int(child.id) for child in node.children],
                }
            )
            continue

        if isinstance(node, bindings.sum_class):
            nodes.append(
                {
                    "id": int(node.id),
                    "type": "sum",
                    "children": [int(child.id) for child in node.children],
                    "weights": [float(weight) for weight in node.weights],
                }
            )
            continue

        raise ValueError(f"unsupported SPFlow node type {type(node).__name__!r}")

    return {
        "root_id": int(spn_model.id),
        "nodes": nodes,
    }


def _normalized_fixed_value(
    feature_payload: Mapping[str, object],
    fixed_value: object,
) -> float:
    from .features import TPMFeatureSpec

    feature_spec = TPMFeatureSpec.from_dict(feature_payload)
    return feature_spec.normalize_value(fixed_value)


def _evaluate_runtime_spflow_query(
    runtime_payload: Mapping[str, object],
    *,
    feature_specs: Mapping[str, TPMFeatureSpec],
    decision_assignments: Mapping[str, object],
    marginalized_features: tuple[str, ...],
    event_target_name: str,
    output_mode: str,
    numeric_tolerance: float,
) -> dict[str, object]:
    import numpy as np

    api = _require_legacy_spflow_api()
    spn_model = runtime_payload.get("spn_model")
    if spn_model is None:
        raise ValueError("SPFlow runtime payload is missing its trained model")

    denominator_evidence = np.asarray(
        [
            _build_spflow_evidence_row(
                feature_specs,
                column_order=tuple(str(item) for item in runtime_payload["column_order"]),
                decision_assignments=decision_assignments,
                marginalized_features=marginalized_features,
                event_target_name=event_target_name,
                target_value=None,
            )
        ],
        dtype=float,
    )
    denominator_log_likelihood = float(api.log_likelihood(spn_model, denominator_evidence)[0][0])

    raw_rows = runtime_payload["raw_rows"]
    matched_row_count = sum(
        _row_matches_assignments(
            row,
            assignments=decision_assignments,
            feature_specs=feature_specs,
            numeric_tolerance=numeric_tolerance,
        )
        for row in raw_rows
    )
    total_row_count = len(raw_rows)

    if output_mode == "log_likelihood":
        return {
            "matched_row_count": matched_row_count,
            "total_row_count": total_row_count,
            "source": "spflow_backend",
            "value": denominator_log_likelihood,
            "resolved_target_name": event_target_name,
        }

    numerator_evidence = np.asarray(
        [
            _build_spflow_evidence_row(
                feature_specs,
                column_order=tuple(str(item) for item in runtime_payload["column_order"]),
                decision_assignments=decision_assignments,
                marginalized_features=marginalized_features,
                event_target_name=event_target_name,
                target_value=1.0,
            )
        ],
        dtype=float,
    )
    numerator_log_likelihood = float(api.log_likelihood(spn_model, numerator_evidence)[0][0])
    if not math.isfinite(denominator_log_likelihood):
        probability = 0.0
    else:
        probability = math.exp(numerator_log_likelihood - denominator_log_likelihood)
    probability = min(max(probability, 0.0), 1.0)

    return {
        "matched_row_count": matched_row_count,
        "total_row_count": total_row_count,
        "source": "spflow_backend",
        "value": probability,
        "resolved_target_name": event_target_name,
    }


def _build_spflow_evidence_row(
    feature_specs: Mapping[str, TPMFeatureSpec],
    *,
    column_order: tuple[str, ...],
    decision_assignments: Mapping[str, object],
    marginalized_features: tuple[str, ...],
    event_target_name: str,
    target_value: float | None,
) -> list[float]:
    evidence: list[float] = []
    marginalized_set = set(marginalized_features)
    for feature_name in column_order:
        if feature_name == event_target_name:
            if target_value is None:
                evidence.append(float("nan"))
            else:
                evidence.append(target_value)
            continue
        if feature_name in decision_assignments:
            evidence.append(
                feature_specs[feature_name].normalize_value(decision_assignments[feature_name])
            )
            continue
        if feature_name in marginalized_set or feature_specs[feature_name].feature_role != "decision":
            evidence.append(float("nan"))
            continue
        evidence.append(float("nan"))
    return evidence


def _payload_locator(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Mapping):
        locator = payload.get("locator", payload.get("path", ""))
        if isinstance(locator, str):
            return locator
    return ""


def _runtime_payload_supports_spn_mip(runtime_payload: Mapping[str, object]) -> bool:
    if str(runtime_payload.get("query_strategy", "")) != "spflow":
        return False
    conditional_models = runtime_payload.get("conditional_models")
    if not isinstance(conditional_models, Mapping):
        return False
    return isinstance(conditional_models.get("numerator_model"), Mapping) and isinstance(
        conditional_models.get("denominator_model"),
        Mapping,
    )


def _sequence_of_mappings(value: object, *, field_name: str) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of mappings")
    result: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field_name} must contain only mappings")
        result.append(item)
    return tuple(result)


register_spflow_backend_adapter(
    "legacy-spn-api",
    lambda _runtime_payload: _LegacySpnBackendAdapter(backend_module=require_spflow_backend()),
)


def _row_matches_assignments(
    row: Mapping[str, object],
    *,
    assignments: Mapping[str, object],
    feature_specs: Mapping[str, TPMFeatureSpec],
    numeric_tolerance: float,
) -> bool:
    for feature_name, expected_value in assignments.items():
        actual_value = row.get(feature_name)
        feature_spec = feature_specs[feature_name]
        if feature_spec.feature_type == "continuous":
            if abs(float(actual_value) - float(expected_value)) > numeric_tolerance:
                return False
            continue
        if actual_value != expected_value:
            return False
    return True
