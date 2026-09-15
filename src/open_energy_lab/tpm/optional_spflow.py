"""Lazy SPFlow dependency boundary for TPM fit, query, and planning workflows."""

from __future__ import annotations

import math
import pickle
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .artifact import TPMArtifact
    from .data import TPMTrainingData
    from .features import TPMFeatureSpec


class SPFlowDependencyUnavailableError(ImportError):
    """Raised when a TPM workflow requires SPFlow but it is unavailable."""


class SPFlowBackendCompatibilityError(ImportError):
    """Raised when the installed SPFlow backend is not the required API version."""

    def __init__(
        self,
        *,
        required_version: str,
        installed_version: str | None,
        reason: str,
    ) -> None:
        self.required_version = required_version
        self.installed_version = installed_version
        self.reason = str(reason)
        installed = installed_version if installed_version is not None else "unknown"
        super().__init__(
            "Incompatible required SPFlow installation: "
            f"required version {required_version}, installed version {installed}. "
            f"{self.reason}"
        )


REQUIRED_SPFLOW_VERSION = "1.1.0"
CURRENT_SPFLOW_BACKEND_GENERATION = "current-spflow"
CURRENT_SPFLOW_ADAPTER_NAME = "current-spflow-api"


_BACKEND_ADAPTER_REGISTRY: dict[
    str,
    Callable[[Mapping[str, object]], object],
] = {}


@dataclass(frozen=True, slots=True)
class CurrentSPFlowCapabilities:
    """Resolved SPFlow 1.1 symbols needed by the corrective TPM workflows."""

    backend_module: Any
    module_class: Any
    scope_class: Any
    normal_leaf_class: Any
    bernoulli_leaf_class: Any
    categorical_leaf_class: Any
    learn_spn: Callable[..., object]


@dataclass(frozen=True, slots=True)
class _CurrentSPFlowBackendAdapter:
    """Lazy adapter for the required PyTorch-backed SPFlow 1.1 API."""

    backend_module: Any

    @property
    def adapter_name(self) -> str:
        return CURRENT_SPFLOW_ADAPTER_NAME

    @property
    def backend_name(self) -> str:
        return getattr(self.backend_module, "__name__", type(self.backend_module).__name__)

    @property
    def backend_version(self) -> str | None:
        version = getattr(self.backend_module, "__version__", None)
        return None if version is None else str(version)

    def detect_capabilities(self) -> dict[str, object]:
        installed_version = self.backend_version
        version_compatible = installed_version == REQUIRED_SPFLOW_VERSION
        bindings, missing_symbols = _load_current_spflow_capabilities()
        current_api_available = bindings is not None
        backend_compatible = version_compatible and current_api_available

        if backend_compatible:
            reason = (
                f"required SPFlow {REQUIRED_SPFLOW_VERSION} API is available "
                "through current PyTorch-backed modules"
            )
        elif not version_compatible:
            installed = installed_version if installed_version is not None else "unknown"
            reason = (
                f"incompatible SPFlow version: required {REQUIRED_SPFLOW_VERSION}, "
                f"installed {installed}"
            )
        else:
            reason = "required SPFlow 1.1 API symbols are unavailable: " + ", ".join(
                missing_symbols
            )

        return {
            "installed_backend_module": self.backend_name,
            "installed_backend_version": installed_version,
            "required_backend_module": "spflow",
            "required_backend_version": REQUIRED_SPFLOW_VERSION,
            "backend_generation": CURRENT_SPFLOW_BACKEND_GENERATION,
            "backend_api_version": installed_version,
            "backend_adapter_name": self.adapter_name,
            "version_compatible": version_compatible,
            "current_api_available": current_api_available,
            "current_api_module_prefix": "spflow" if current_api_available else None,
            "missing_api_symbols": list(missing_symbols),
            "backend_compatible": backend_compatible,
            # Retained as explicit migration diagnostics for older callers. These
            # values never trigger legacy module discovery or runtime imports.
            "legacy_spn_api_available": False,
            "legacy_api_module_prefix": None,
            "supports_real_spn_training": backend_compatible,
            "supports_real_spn_query": backend_compatible,
            "supports_spn_mip_serialization": False,
            "fallback_query_strategy": None,
            "reason": reason,
        }

    def fit_runtime_payload(self, runtime_payload: Mapping[str, object]) -> dict[str, object]:
        payload = {str(key): value for key, value in runtime_payload.items()}
        if hasattr(self.backend_module, "fit_tpm_model"):
            custom_payload = self.backend_module.fit_tpm_model(payload)
            if not isinstance(custom_payload, Mapping):
                raise TypeError("backend fit_tpm_model must return a mapping payload")
            return {str(key): value for key, value in custom_payload.items()}

        # Typed-scope fitting is supplied by the focused fit layer; this adapter
        # keeps injected fixture backends operational without reviving old APIs.
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
        raise RuntimeError(
            "current SPFlow query evaluation requires a supported current-model "
            "sidecar; legacy runtime payload evaluation is not supported"
        )


def detect_spflow_backend_capabilities(backend: Any | None = None) -> dict[str, object]:
    """Report required-version and current-API compatibility for SPFlow 1.1."""

    adapter = _resolve_spflow_backend_adapter(backend)
    return adapter.detect_capabilities()


def _backend_version(backend: Any) -> str | None:
    version = getattr(backend, "__version__", None)
    return None if version is None else str(version)


def _load_current_spflow_capabilities(
) -> tuple[CurrentSPFlowCapabilities | None, tuple[str, ...]]:
    """Resolve the supported current API only when backend diagnostics run."""

    required_symbols = (
        ("spflow", None, "backend module"),
        ("spflow.modules.module", "Module", "Module"),
        ("spflow.modules.module", "Scope", "Scope"),
        ("spflow.modules.leaves", "Normal", "Normal"),
        ("spflow.modules.leaves", "Bernoulli", "Bernoulli"),
        ("spflow.modules.leaves", "Categorical", "Categorical"),
        ("spflow.learn", "learn_spn", "learn_spn"),
    )
    resolved: dict[str, object] = {}
    missing: list[str] = []

    for module_name, attribute_name, diagnostic_name in required_symbols:
        try:
            module = import_module(module_name)
        except ImportError:
            missing.append(module_name)
            continue
        if attribute_name is None:
            resolved[diagnostic_name] = module
            continue
        attribute = getattr(module, attribute_name, None)
        if attribute is None:
            missing.append(f"{module_name}.{attribute_name}")
            continue
        resolved[diagnostic_name] = attribute

    module_class = resolved.get("Module")
    if module_class is not None:
        for method_name in ("log_likelihood", "marginalize"):
            if not callable(getattr(module_class, method_name, None)):
                missing.append(f"spflow.modules.module.Module.{method_name}")

    learn_spn = resolved.get("learn_spn")
    if learn_spn is not None and not callable(learn_spn):
        missing.append("spflow.learn.learn_spn (not callable)")

    if missing:
        return None, tuple(dict.fromkeys(missing))

    return (
        CurrentSPFlowCapabilities(
            backend_module=resolved["backend module"],
            module_class=resolved["Module"],
            scope_class=resolved["Scope"],
            normal_leaf_class=resolved["Normal"],
            bernoulli_leaf_class=resolved["Bernoulli"],
            categorical_leaf_class=resolved["Categorical"],
            learn_spn=resolved["learn_spn"],
        ),
        (),
    )


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
    """Load and validate required SPFlow only at a TPM workflow boundary."""

    try:
        backend = import_module("spflow")
    except ImportError as exc:  # pragma: no cover - depends on installation state
        raise SPFlowDependencyUnavailableError(
            f"SPFlow is a required project dependency at version "
            f"{REQUIRED_SPFLOW_VERSION}; install the locked project environment. "
            "Loading remains lazy so ordinary open_energy_lab imports stay light."
        ) from exc

    installed_version = _backend_version(backend)
    if installed_version != REQUIRED_SPFLOW_VERSION:
        raise SPFlowBackendCompatibilityError(
            required_version=REQUIRED_SPFLOW_VERSION,
            installed_version=installed_version,
            reason="Use the project lock file to restore the required backend API.",
        )
    _, missing_symbols = _load_current_spflow_capabilities()
    if missing_symbols:
        raise SPFlowBackendCompatibilityError(
            required_version=REQUIRED_SPFLOW_VERSION,
            installed_version=installed_version,
            reason=(
                "The installed distribution is missing required current API symbols: "
                + ", ".join(missing_symbols)
            ),
        )
    return backend


def _resolve_spflow_backend_adapter(backend: Any | None) -> _CurrentSPFlowBackendAdapter:
    if backend is not None and hasattr(backend, "fit_runtime_payload") and hasattr(
        backend,
        "detect_capabilities",
    ):
        return backend

    if backend is not None:
        return _CurrentSPFlowBackendAdapter(backend_module=backend)

    return _CurrentSPFlowBackendAdapter(backend_module=require_spflow_backend())


def _adapter_from_runtime_payload(runtime_payload: Mapping[str, object]) -> object:
    adapter_name = str(
        runtime_payload.get("backend_adapter_name", CURRENT_SPFLOW_ADAPTER_NAME)
    )
    factory = _BACKEND_ADAPTER_REGISTRY.get(adapter_name)
    if factory is None:
        raise ValueError(f"unsupported persisted backend_adapter_name {adapter_name!r}")
    adapter = factory(runtime_payload)
    if not hasattr(adapter, "evaluate_runtime_query"):
        raise TypeError(
            f"adapter factory for {adapter_name!r} must return an object with "
            "evaluate_runtime_query()"
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
            "locator": (
                resolved_payload_path.name
                if payload_path is not None
                else resolved_payload_path.as_posix()
            ),
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
    serialization = artifact.spn_payload.get('serialization') if isinstance(artifact.spn_payload, Mapping) else None
    if serialization == 'torch-weights-only-v1':
        payload = load_supported_spflow_checkpoint(payload_path)
        required = {'payload_kind', 'artifact_schema_version', 'backend_generation', 'backend_api_version',
                    'query_strategy', 'feature_schema', 'model'}
        if (not isinstance(payload, dict) or set(payload) != required
                or payload['payload_kind'] != 'current-spflow-model-sidecar'
                or payload['backend_generation'] != CURRENT_SPFLOW_BACKEND_GENERATION
                or payload['backend_api_version'] != REQUIRED_SPFLOW_VERSION or payload['query_strategy'] != 'spflow'):
            raise ValueError('unsupported restricted SPFlow sidecar schema')
        from .refinement import validate_refinement_spn
        validate_refinement_spn(payload['model'], feature_count=len(artifact.feature_specs))
    else:
        payload = pickle.loads(payload_path.read_bytes())
    if not isinstance(payload, Mapping):
        raise TypeError("persisted SPFlow payload must deserialize to a mapping")
    normalized = {str(key): value for key, value in payload.items()}
    _validate_sidecar_feature_schema(artifact, normalized)
    return normalized


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

    raw_rows = runtime_payload.get("raw_rows")
    if not isinstance(raw_rows, tuple | list):
        raise TypeError("table-backed SPFlow payload must include raw_rows")
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

    from .features import load_feature_schema

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

    feature_specs = {
        spec.feature_name: spec
        for spec in load_feature_schema(
            runtime_payload["feature_schema"],
            schema_version=str(
                runtime_payload.get(
                    "artifact_schema_version",
                    artifact.schema_version,
                )
            ),
        )
    }
    decision_domains = {
        feature_name: list(
            feature_specs[feature_name].ordering
            or feature_specs[feature_name].discrete_values
        )
        for feature_name in decision_features
    }
    conditional_models = runtime_payload.get("conditional_models")
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
        "row_count": int(
            runtime_payload.get(
                "training_row_count",
                len(runtime_payload.get("raw_rows", ())),
            )
        ),
        "conditional_models": conditional_models,
    }


def supports_spn_mip(artifact: TPMArtifact) -> bool:
    """Return whether one artifact exposes a serialized SPN MIO payload."""

    runtime_payload = load_spflow_payload(artifact)
    return runtime_payload is not None and _runtime_payload_supports_spn_mip(runtime_payload)


def load_supported_spflow_checkpoint(path):
    """Load only the declared supported Torch/SPFlow checkpoint classes on CPU.

    This is separate from legacy artifact sidecar loading. There is deliberately
    no unrestricted pickle fallback; refinement validates the returned schema.
    """
    import pickle
    import threading
    import torch
    from .refinement import _supported_types

    modules, records = _supported_types()
    allowed = (*modules, *records)
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('restricted checkpoint loading belongs in the fitting worker main thread')
    previous = torch.serialization.get_safe_globals()
    try:
        # Torch and imported libraries may register unrelated tensor classes.
        # This isolated worker boundary admits only this operation's exact list.
        torch.serialization.clear_safe_globals()
        with torch.serialization.safe_globals(allowed):
            return torch.load(path, map_location='cpu', weights_only=True)
    except (pickle.UnpicklingError, RuntimeError, EOFError, TypeError, AttributeError) as exc:
        raise ValueError('restricted supported-SPN checkpoint loading failed') from exc
    finally:
        torch.serialization.clear_safe_globals()
        torch.serialization.add_safe_globals(previous)


def stabilize_spflow_leaf_parameters(
    module: object,
    *,
    minimum_value: float = 1e-9,
) -> None:
    """Regularize learned degenerate leaves without changing training evidence."""

    import torch
    from spflow.modules.leaves import Bernoulli, Categorical, Normal

    with torch.no_grad():
        for child in module.modules():
            if isinstance(child, Normal):
                child.scale = torch.clamp(
                    torch.nan_to_num(
                        child.scale,
                        nan=float(minimum_value),
                        posinf=float(minimum_value),
                        neginf=float(minimum_value),
                    ),
                    min=float(minimum_value),
                )
            elif isinstance(child, Bernoulli):
                child.probs = torch.clamp(
                    torch.nan_to_num(
                        child.probs,
                        nan=0.5,
                        posinf=1.0 - float(minimum_value),
                        neginf=float(minimum_value),
                    ),
                    min=float(minimum_value),
                    max=1.0 - float(minimum_value),
                )
            elif isinstance(child, Categorical):
                probabilities = torch.clamp(
                    torch.nan_to_num(
                        child.probs,
                        nan=1.0 / float(child.K),
                        posinf=1.0,
                        neginf=0.0,
                    ),
                    min=float(minimum_value),
                )
                child.probs = probabilities / probabilities.sum(
                    dim=-1,
                    keepdim=True,
                )


__all__ = [
    "CURRENT_SPFLOW_ADAPTER_NAME",
    "CURRENT_SPFLOW_BACKEND_GENERATION",
    "CurrentSPFlowCapabilities",
    "REQUIRED_SPFLOW_VERSION",
    "SPFlowBackendCompatibilityError",
    "SPFlowDependencyUnavailableError",
    "detect_spflow_backend_capabilities",
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
    adapter: _CurrentSPFlowBackendAdapter,
) -> dict[str, object]:
    event_target_index = training_data.column_order.index(event_target_name)
    capability_report = adapter.detect_capabilities()
    return {
        "payload_kind": "spflow-runtime-payload",
        "artifact_schema_version": "v3",
        "backend_module": adapter.backend_name,
        "backend_version": adapter.backend_version,
        "backend_adapter_name": adapter.adapter_name,
        "backend_capabilities": capability_report,
        "backend_generation": CURRENT_SPFLOW_BACKEND_GENERATION,
        "backend_api_version": adapter.backend_version,
        "canonical_target_name": canonical_target_name,
        "event_target_name": event_target_name,
        "target_threshold": float(target_threshold),
        "training_random_seed": training_random_seed,
        "learn_mspn_kwargs": dict(learn_mspn_kwargs),
        "column_order": list(training_data.column_order),
        "feature_schema": [
            spec.to_dict(schema_version="v3") for spec in feature_schema
        ],
        "normalized_rows": [dict(row) for row in training_data.normalized_rows],
        "raw_rows": [dict(row) for row in training_data.rows],
        "matrix": [list(row) for row in training_data.matrix],
        "event_target_index": event_target_index,
        "query_strategy": "table",
    }


def _validate_sidecar_feature_schema(
    artifact: TPMArtifact,
    runtime_payload: Mapping[str, object],
) -> None:
    sidecar_schema = runtime_payload.get("feature_schema")
    sidecar_version = runtime_payload.get("artifact_schema_version")
    if artifact.schema_version == "v2" and sidecar_version is None:
        return
    if str(sidecar_version) != artifact.schema_version:
        raise ValueError(
            "SPFlow sidecar artifact_schema_version disagrees with the manifest"
        )
    if not isinstance(sidecar_schema, tuple | list):
        raise TypeError("SPFlow sidecar feature_schema must be a sequence")

    from .features import dump_feature_schema, load_feature_schema

    manifest_schema = dump_feature_schema(
        artifact.feature_specs,
        schema_version=artifact.schema_version,
    )
    resolved_sidecar_schema = dump_feature_schema(
        load_feature_schema(
            sidecar_schema,
            schema_version=artifact.schema_version,
        ),
        schema_version=artifact.schema_version,
    )
    if resolved_sidecar_schema != manifest_schema:
        raise ValueError("SPFlow sidecar feature_schema semantics disagree with the manifest")


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


register_spflow_backend_adapter(
    CURRENT_SPFLOW_ADAPTER_NAME,
    lambda _runtime_payload: _CurrentSPFlowBackendAdapter(
        backend_module=require_spflow_backend()
    ),
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
