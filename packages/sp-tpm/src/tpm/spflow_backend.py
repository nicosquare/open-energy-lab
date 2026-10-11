"""SPFlow 1.1 backend boundary: version check and persisted model sidecars.

SPFlow is a required dependency. It is imported lazily so that ``import tpm``
stays light; a missing installation raises the plain ``ImportError``.
"""

from __future__ import annotations

import math
import pickle
from collections.abc import Mapping
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .artifact import TPMArtifact


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


def require_spflow_backend() -> Any:
    """Import SPFlow and check that it is the required version."""

    backend = import_module("spflow")
    version = getattr(backend, "__version__", None)
    installed_version = None if version is None else str(version)
    if installed_version != REQUIRED_SPFLOW_VERSION:
        raise SPFlowBackendCompatibilityError(
            required_version=REQUIRED_SPFLOW_VERSION,
            installed_version=installed_version,
            reason="Use the project lock file to restore the required backend API.",
        )
    return backend


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
                # Clamp logits, not probabilities: 1 - 1e-9 rounds to 1 in float32.
                bound = math.log((1.0 - float(minimum_value)) / float(minimum_value))
                child.logits = torch.clamp(
                    torch.nan_to_num(child.logits, nan=0.0, posinf=bound, neginf=-bound),
                    min=-bound,
                    max=bound,
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
    "CURRENT_SPFLOW_BACKEND_GENERATION",
    "REQUIRED_SPFLOW_VERSION",
    "SPFlowBackendCompatibilityError",
    "has_spflow_payload",
    "load_spflow_payload",
    "load_supported_spflow_checkpoint",
    "require_spflow_backend",
    "resolve_spflow_payload_path",
    "stabilize_spflow_leaf_parameters",
]


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
