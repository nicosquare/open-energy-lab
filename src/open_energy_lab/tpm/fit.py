"""Scaffolding for SPFlow-backed TPM fitting."""

from __future__ import annotations

import random
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from numbers import Real
from pathlib import Path
from typing import Any

from .artifact import FEATURE_NAME, TPMArtifact, write_tpm_model_sidecar
from .data import TPMTrainingData, normalize_training_data
from .features import (
    TPMFeatureSpec,
    build_spflow_leaf_modules,
    build_spflow_training_tensor,
    dump_feature_schema,
)
from .optional_spflow import (
    CURRENT_SPFLOW_ADAPTER_NAME,
    CURRENT_SPFLOW_BACKEND_GENERATION,
    REQUIRED_SPFLOW_VERSION,
    detect_spflow_backend_capabilities,
    fit_spflow_model,
    require_spflow_backend,
)
from .piecewise import (
    CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS,
    DEFAULT_QUERY_NUMERIC_TOLERANCE,
    build_piecewise_metadata,
)


CANONICAL_OUTPUT_MODES = (
    "conditional_probability",
    "log_likelihood",
)
CANONICAL_TPM_RANDOM_SEED = 13
TPM_ROBUSTNESS_RANDOM_SEEDS = (37, 101)
FIT_LEGACY_EVIDENCE_PATHS = (
    "legacy/old_tpm/src_py/tpm/data/datahandler.py",
    "legacy/old_tpm/src_py/tpm/spn/main.py",
)
PIECEWISE_LEGACY_EVIDENCE_PATHS = CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS
_LEARN_SPN_DIRECT_ARGUMENTS = (
    "out_channels",
    "min_features_slice",
    "min_instances_slice",
    "scope",
    "clustering_method",
    "partitioning_method",
    "full_data",
)
_LEARN_SPN_NESTED_ARGUMENTS = (
    "clustering_args",
    "partitioning_args",
)
_LEGACY_LEARN_SPN_ARGUMENTS = (
    "threshold",
    "n_clusters",
)


@dataclass(frozen=True, slots=True)
class TPMFitConfig:
    """SPFlow-backed TPM fit configuration captured in persisted artifacts."""

    backend_name: str = "spflow"
    training_random_seed: int | None = None
    spn_payload_format: str = "pickle-path"
    supported_output_modes: tuple[str, ...] = CANONICAL_OUTPUT_MODES
    learn_mspn_kwargs: Mapping[str, object] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)
    execution_mode: str = "production"

    def __post_init__(self) -> None:
        backend_name = str(self.backend_name)
        if not backend_name:
            raise ValueError("backend_name must be non-empty")
        if backend_name != "spflow":
            raise ValueError("TPMFitConfig currently supports only the 'spflow' backend")
        object.__setattr__(self, "backend_name", backend_name)

        spn_payload_format = str(self.spn_payload_format)
        if not spn_payload_format:
            raise ValueError("spn_payload_format must be non-empty")
        if spn_payload_format == "json-inline":
            raise ValueError(
                "schema-v2 production fitting requires a persisted model sidecar"
            )
        object.__setattr__(self, "spn_payload_format", spn_payload_format)

        if self.training_random_seed is not None:
            training_random_seed = int(self.training_random_seed)
            if training_random_seed < 0 or training_random_seed > 2**32 - 1:
                raise ValueError("training_random_seed must be between 0 and 2**32 - 1")
            object.__setattr__(self, "training_random_seed", training_random_seed)

        supported_output_modes = tuple(str(mode) for mode in self.supported_output_modes)
        if not supported_output_modes:
            raise ValueError("supported_output_modes must not be empty")
        object.__setattr__(self, "supported_output_modes", supported_output_modes)

        learn_mspn_kwargs = {
            str(key): value for key, value in dict(self.learn_mspn_kwargs).items()
        }
        object.__setattr__(self, "learn_mspn_kwargs", learn_mspn_kwargs)

        notes = tuple(str(note) for note in self.notes)
        if any(not note for note in notes):
            raise ValueError("notes must not contain empty strings")
        object.__setattr__(self, "notes", notes)

        execution_mode = str(self.execution_mode)
        if execution_mode not in {"production", "fixture_replay"}:
            raise ValueError(
                "execution_mode must be 'production' or 'fixture_replay'"
            )
        object.__setattr__(self, "execution_mode", execution_mode)


@dataclass(frozen=True, slots=True)
class TPMArtifactBuildRequest:
    """Generic TPM artifact-construction metadata for arbitrary tabular rows."""

    artifact_id: str
    dataset_reference: str
    decision_features: tuple[str, ...] = field(default_factory=tuple)
    target_name: str = ""
    event_target_name: str = ""
    target_threshold: float | None = None
    supported_query_mode: str = "exceedance-probability"
    numeric_tolerance: float = 1e-9
    feature_roles: Mapping[str, str] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        artifact_id = str(self.artifact_id)
        if not artifact_id:
            raise ValueError("artifact_id must be non-empty")
        object.__setattr__(self, "artifact_id", artifact_id)

        dataset_reference = str(self.dataset_reference)
        if not dataset_reference:
            raise ValueError("dataset_reference must be non-empty")
        object.__setattr__(self, "dataset_reference", dataset_reference)

        decision_features = tuple(str(name) for name in self.decision_features)
        if any(not name for name in decision_features):
            raise ValueError("decision_features must contain non-empty names")
        if len(set(decision_features)) != len(decision_features):
            raise ValueError("decision_features must be unique")
        object.__setattr__(self, "decision_features", decision_features)

        target_name = str(self.target_name)
        if not target_name:
            raise ValueError("target_name must be non-empty")
        object.__setattr__(self, "target_name", target_name)

        event_target_name = str(self.event_target_name or f"{target_name}_event")
        if not event_target_name:
            raise ValueError("event_target_name must be non-empty")
        if event_target_name == target_name:
            raise ValueError("event_target_name must differ from target_name")
        object.__setattr__(self, "event_target_name", event_target_name)

        if self.target_threshold is not None:
            target_threshold = float(self.target_threshold)
            object.__setattr__(self, "target_threshold", target_threshold)

        supported_query_mode = str(self.supported_query_mode)
        if not supported_query_mode:
            raise ValueError("supported_query_mode must be non-empty")
        object.__setattr__(self, "supported_query_mode", supported_query_mode)

        numeric_tolerance = float(self.numeric_tolerance)
        if numeric_tolerance <= 0.0:
            raise ValueError("numeric_tolerance must be positive")
        object.__setattr__(self, "numeric_tolerance", numeric_tolerance)

        feature_roles = {
            str(name): str(role) for name, role in dict(self.feature_roles).items()
        }
        if any(not name for name in feature_roles):
            raise ValueError("feature_roles must not contain empty feature names")
        if any(not role for role in feature_roles.values()):
            raise ValueError("feature_roles must not contain empty role names")
        object.__setattr__(self, "feature_roles", feature_roles)

        provenance = {str(key): value for key, value in dict(self.provenance).items()}
        object.__setattr__(self, "provenance", provenance)


@dataclass(frozen=True, slots=True)
class _SPFlowFitResult:
    spn_payload: Mapping[str, object]
    spn_payload_format: str
    payload_hash: str
    backend_generation: str
    backend_api_version: str
    learn_spn_kwargs: Mapping[str, object]
    leaf_families: tuple[str, ...]
    determinism_configuration: Mapping[str, object]
    fit_summary: Mapping[str, object]
    source_path: str


def translate_spflow_fit_configuration(
    configuration: Mapping[str, object] | None,
) -> dict[str, object]:
    """Translate legacy ``learn_mspn`` options to SPFlow 1.1 ``learn_spn``.

    SPFlow 1.1 moved RDC's ``threshold`` and k-means' ``n_clusters`` into
    dedicated argument dictionaries. Current ``learn_spn`` options are also
    accepted so callers can migrate incrementally without ambiguous keyword
    forwarding.
    """

    normalized = {str(key): value for key, value in dict(configuration or {}).items()}
    supported = set(
        _LEARN_SPN_DIRECT_ARGUMENTS
        + _LEARN_SPN_NESTED_ARGUMENTS
        + _LEGACY_LEARN_SPN_ARGUMENTS
    )
    unsupported = sorted(set(normalized) - supported)
    if unsupported:
        raise ValueError(
            "unsupported SPFlow fit configuration keys: " + ", ".join(unsupported)
        )

    translated = {
        key: normalized[key]
        for key in _LEARN_SPN_DIRECT_ARGUMENTS
        if key in normalized
    }
    clustering_args = _fit_argument_mapping(
        normalized.get("clustering_args"),
        argument_name="clustering_args",
    )
    partitioning_args = _fit_argument_mapping(
        normalized.get("partitioning_args"),
        argument_name="partitioning_args",
    )

    _merge_legacy_fit_argument(
        source=normalized,
        source_name="threshold",
        destination=partitioning_args,
    )
    _merge_legacy_fit_argument(
        source=normalized,
        source_name="n_clusters",
        destination=clustering_args,
    )

    if partitioning_args:
        translated["partitioning_args"] = partitioning_args
    if clustering_args:
        translated["clustering_args"] = clustering_args
    return translated


def learn_current_spflow_structure(
    rows: Sequence[Mapping[str, object]],
    *,
    feature_schema: Sequence[TPMFeatureSpec],
    fit_configuration: Mapping[str, object] | None = None,
) -> object:
    """Learn one SPFlow 1.1 structure from typed rows at a lazy boundary."""

    model, _, _, _ = _learn_current_spflow_structure(
        rows,
        feature_schema=feature_schema,
        fit_configuration=fit_configuration,
    )
    return model


def fit_tpm_artifact(
    source: object,
    *,
    output_path: str | Path | None = None,
    fit_config: TPMFitConfig | None = None,
    spflow_backend: Any | None = None,
) -> TPMArtifact:
    """Fit and optionally persist a first-release TPM artifact."""

    dataset = _load_planning_dataset_artifact(source)
    dataset_source_path = _source_dataset_path(source)
    config = fit_config or TPMFitConfig()
    training_data = normalize_training_data(dataset.rows)
    canonical_target_name = str(dataset.target_metadata["target_name"])
    event_target_name = str(dataset.target_metadata["event_target_name"])
    training_random_seed = _resolved_training_random_seed(
        dataset.provenance,
        configured_seed=config.training_random_seed,
    )
    feature_schema = _build_feature_schema(
        dataset=dataset,
        training_data=training_data,
        canonical_target_name=canonical_target_name,
        event_target_name=event_target_name,
    )
    fit_result = _fit_and_persist_spflow_model(
        training_data,
        feature_schema=feature_schema,
        canonical_target_name=canonical_target_name,
        event_target_name=event_target_name,
        target_threshold=float(dataset.target_metadata["threshold_default"]),
        training_random_seed=training_random_seed,
        config=config,
        backend=spflow_backend,
        output_path=output_path,
    )

    piecewise_metadata = build_piecewise_metadata(
        fit_numeric_tolerance=float(dataset.export_configuration["numeric_tolerance"]),
        query_numeric_tolerance=DEFAULT_QUERY_NUMERIC_TOLERANCE,
        legacy_reference_paths=PIECEWISE_LEGACY_EVIDENCE_PATHS,
    )

    artifact = TPMArtifact(
        artifact_id=f"tpm-artifact:{dataset.dataset_id}",
        schema_version="v2",
        created_at=_created_at_utc(),
        dataset_reference=dataset.dataset_id,
        feature_schema=dump_feature_schema(feature_schema),
        target_definition=dict(dataset.target_metadata),
        fit_configuration=_persisted_fit_configuration(
            config=config,
            result=fit_result,
            training_random_seed=training_random_seed,
            input_row_count=dataset.row_count,
            input_column_order=dataset.column_order,
        ),
        backend_generation=fit_result.backend_generation,
        backend_api_version=fit_result.backend_api_version,
        execution_mode=config.execution_mode,
        spn_payload=fit_result.spn_payload,
        spn_payload_format=fit_result.spn_payload_format,
        payload_hash=fit_result.payload_hash,
        query_configuration={
            "supported_output_modes": list(config.supported_output_modes),
            "required_decision_features": [
                str(feature["feature_name"]) for feature in dataset.design_feature_schema
            ],
        },
        approximation_metadata=piecewise_metadata.to_dict(),
        provenance=_artifact_provenance(
            dataset=dataset,
            training_random_seed=training_random_seed,
            training_data=training_data,
            dataset_source_path=dataset_source_path,
        ),
        source_path=fit_result.source_path,
    )
    if output_path is not None:
        artifact.write_json(output_path)
    return artifact


def fit_tpm_artifact_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    build_request: TPMArtifactBuildRequest,
    output_path: str | Path | None = None,
    fit_config: TPMFitConfig | None = None,
    spflow_backend: Any | None = None,
) -> TPMArtifact:
    """Fit a TPM artifact from arbitrary rows plus explicit target/decision metadata."""

    prepared_rows, event_was_derived = _prepare_generic_rows(
        rows,
        build_request=build_request,
    )
    config = fit_config or TPMFitConfig()
    training_data = normalize_training_data(prepared_rows)
    training_random_seed = _resolved_training_random_seed(
        build_request.provenance,
        configured_seed=config.training_random_seed,
    )
    feature_schema = _build_generic_feature_schema(
        training_data=training_data,
        build_request=build_request,
    )
    fit_result = _fit_and_persist_spflow_model(
        training_data,
        feature_schema=feature_schema,
        canonical_target_name=build_request.target_name,
        event_target_name=build_request.event_target_name,
        target_threshold=float(build_request.target_threshold or 0.0),
        training_random_seed=training_random_seed,
        config=config,
        backend=spflow_backend,
        output_path=output_path,
    )
    piecewise_metadata = build_piecewise_metadata(
        fit_numeric_tolerance=build_request.numeric_tolerance,
        query_numeric_tolerance=DEFAULT_QUERY_NUMERIC_TOLERANCE,
        legacy_reference_paths=PIECEWISE_LEGACY_EVIDENCE_PATHS,
    )
    artifact = TPMArtifact(
        artifact_id=build_request.artifact_id,
        schema_version="v2",
        created_at=_created_at_utc(),
        dataset_reference=build_request.dataset_reference,
        feature_schema=dump_feature_schema(feature_schema),
        target_definition=_generic_target_definition(
            build_request=build_request,
            event_was_derived=event_was_derived,
        ),
        fit_configuration=_persisted_fit_configuration(
            config=config,
            result=fit_result,
            training_random_seed=training_random_seed,
            input_row_count=len(prepared_rows),
            input_column_order=training_data.column_order,
        ),
        backend_generation=fit_result.backend_generation,
        backend_api_version=fit_result.backend_api_version,
        execution_mode=config.execution_mode,
        spn_payload=fit_result.spn_payload,
        spn_payload_format=fit_result.spn_payload_format,
        payload_hash=fit_result.payload_hash,
        query_configuration={
            "supported_output_modes": list(config.supported_output_modes),
            "required_decision_features": list(build_request.decision_features),
        },
        approximation_metadata=piecewise_metadata.to_dict(),
        provenance=_generic_artifact_provenance(
            build_request=build_request,
            training_random_seed=training_random_seed,
            training_data=training_data,
        ),
        source_path=fit_result.source_path,
    )
    if output_path is not None:
        artifact.write_json(output_path)
    return artifact


__all__ = [
    "CANONICAL_OUTPUT_MODES",
    "CANONICAL_TPM_RANDOM_SEED",
    "FEATURE_NAME",
    "FIT_LEGACY_EVIDENCE_PATHS",
    "PIECEWISE_LEGACY_EVIDENCE_PATHS",
    "TPMArtifactBuildRequest",
    "TPMFitConfig",
    "TPM_ROBUSTNESS_RANDOM_SEEDS",
    "fit_tpm_artifact",
    "fit_tpm_artifact_from_rows",
    "learn_current_spflow_structure",
    "translate_spflow_fit_configuration",
]


def _fit_argument_mapping(
    value: object,
    *,
    argument_name: str,
) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{argument_name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _merge_legacy_fit_argument(
    *,
    source: Mapping[str, object],
    source_name: str,
    destination: dict[str, object],
) -> None:
    if source_name not in source:
        return
    if source_name in destination and destination[source_name] != source[source_name]:
        raise ValueError(
            f"conflicting {source_name!r} values in legacy and nested fit configuration"
        )
    destination[source_name] = source[source_name]


def _fit_and_persist_spflow_model(
    training_data: TPMTrainingData,
    *,
    feature_schema: tuple[TPMFeatureSpec, ...],
    canonical_target_name: str,
    event_target_name: str,
    target_threshold: float,
    training_random_seed: int,
    config: TPMFitConfig,
    backend: Any | None,
    output_path: str | Path | None,
) -> _SPFlowFitResult:
    sidecar_path = _spn_payload_output_path(output_path=output_path)
    source_path = _artifact_source_path(
        output_path=output_path,
        sidecar_path=sidecar_path,
    )
    translated_kwargs = translate_spflow_fit_configuration(config.learn_mspn_kwargs)
    determinism_configuration: Mapping[str, object] = {}
    fit_summary: Mapping[str, object] = {}
    leaf_families: tuple[str, ...] = ()
    current_payload: Mapping[str, object] | None = None

    if _uses_current_spflow_backend(backend):
        backend_module = require_spflow_backend()
        backend_capabilities = detect_spflow_backend_capabilities(backend_module)
        determinism_configuration = _configure_torch_determinism(training_random_seed)
        import torch

        previous_default_dtype = torch.get_default_dtype()
        torch.set_default_dtype(torch.float64)
        try:
            model, tensor, leaves, translated_kwargs = _learn_current_spflow_structure(
                training_data.rows,
                feature_schema=feature_schema,
                fit_configuration=config.learn_mspn_kwargs,
            )
        finally:
            torch.set_default_dtype(previous_default_dtype)

        fit_summary = _build_stable_fit_summary(model=model, tensor=tensor)
        leaf_families = tuple(
            dict.fromkeys(_canonical_leaf_family_name(leaf) for leaf in leaves)
        )
        current_payload = {
            "payload_kind": "current-spflow-model-sidecar",
            "backend_module": "spflow",
            "backend_version": REQUIRED_SPFLOW_VERSION,
            "backend_adapter_name": CURRENT_SPFLOW_ADAPTER_NAME,
            "backend_capabilities": backend_capabilities,
            "backend_generation": CURRENT_SPFLOW_BACKEND_GENERATION,
            "backend_api_version": REQUIRED_SPFLOW_VERSION,
            "canonical_target_name": canonical_target_name,
            "event_target_name": event_target_name,
            "target_threshold": float(target_threshold),
            "training_random_seed": training_random_seed,
            "determinism_configuration": dict(determinism_configuration),
            "learn_spn_kwargs": dict(translated_kwargs),
            "column_order": list(training_data.column_order),
            "feature_schema": [spec.to_dict() for spec in feature_schema],
            "normalized_rows": [dict(row) for row in training_data.normalized_rows],
            "raw_rows": [dict(row) for row in training_data.rows],
            "event_target_index": training_data.column_order.index(event_target_name),
            "query_strategy": "spflow",
            "fit_summary": dict(fit_summary),
            "model": model,
        }
    spn_payload: object = {}
    if current_payload is not None:
        deserialized_payload = current_payload
    else:
        import pickle

        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=sidecar_path.parent,
            prefix=f".{sidecar_path.name}.",
            suffix=".adapter-stage",
            delete=False,
        ) as staging_file:
            staging_path = Path(staging_file.name)
        try:
            spn_payload, _ = fit_spflow_model(
                training_data,
                feature_schema=feature_schema,
                canonical_target_name=canonical_target_name,
                event_target_name=event_target_name,
                target_threshold=target_threshold,
                training_random_seed=training_random_seed,
                learn_mspn_kwargs=config.learn_mspn_kwargs,
                backend=backend,
                payload_path=staging_path,
                payload_format=config.spn_payload_format,
            )
            deserialized_payload = pickle.loads(staging_path.read_bytes())
        finally:
            staging_path.unlink(missing_ok=True)
        if not isinstance(deserialized_payload, Mapping):
            raise TypeError("persisted SPFlow sidecar payload must be a mapping")
    _, payload_hash = write_tpm_model_sidecar(sidecar_path, deserialized_payload)

    normalized_payload = dict(spn_payload) if isinstance(spn_payload, Mapping) else {}
    normalized_payload.update(
        {
            "locator": sidecar_path.name,
            "serialization": (
                "pickle"
                if config.spn_payload_format == "pickle-path"
                else config.spn_payload_format
            ),
            "backend": "spflow",
        }
    )
    persisted_backend_generation = str(
        deserialized_payload.get(
            "backend_generation",
            CURRENT_SPFLOW_BACKEND_GENERATION,
        )
    )
    persisted_backend_api_version = str(
        deserialized_payload.get(
            "backend_api_version",
            deserialized_payload.get("backend_version", "unknown"),
        )
    )
    return _SPFlowFitResult(
        spn_payload=normalized_payload,
        spn_payload_format=config.spn_payload_format,
        payload_hash=payload_hash,
        backend_generation=persisted_backend_generation,
        backend_api_version=persisted_backend_api_version,
        learn_spn_kwargs=translated_kwargs,
        leaf_families=leaf_families,
        determinism_configuration=determinism_configuration,
        fit_summary=fit_summary,
        source_path=source_path.as_posix(),
    )


def _learn_current_spflow_structure(
    rows: Sequence[Mapping[str, object]],
    *,
    feature_schema: Sequence[TPMFeatureSpec],
    fit_configuration: Mapping[str, object] | None,
) -> tuple[object, object, tuple[object, ...], dict[str, object]]:
    from spflow.learn import learn_spn

    schema = tuple(feature_schema)
    effective_configuration = dict(fit_configuration or {})
    if len(rows) < 3 and "min_features_slice" not in effective_configuration:
        # SPFlow 1.1's RDC implementation cannot form a covariance spectrum
        # from two observations. A concrete typed-leaf product is the stable
        # maximum-likelihood structure for this fixture-sized edge case.
        effective_configuration["min_features_slice"] = len(schema) + 1
    tensor = build_spflow_training_tensor(rows, feature_schema=schema)
    leaves = build_spflow_leaf_modules(schema)
    translated = translate_spflow_fit_configuration(effective_configuration)
    model = learn_spn(tensor, leaf_modules=list(leaves), **translated)
    model = _materialize_native_categorical_leaves(model)
    return model, tensor, leaves, translated


def _materialize_native_categorical_leaves(module: object) -> object:
    """Replace transient learning templates with native categorical leaves."""

    from spflow.modules.leaves import Categorical

    if isinstance(module, Categorical) and type(module) is not Categorical:
        replacement = Categorical(
            scope=module.scope,
            out_channels=module.out_shape.channels,
            num_repetitions=module.out_shape.repetitions,
            K=module.K,
            logits=module.logits.detach().clone(),
        )
        replacement.train(module.training)
        return replacement

    for child_name, child in tuple(module.named_children()):
        replacement = _materialize_native_categorical_leaves(child)
        if replacement is not child:
            module._modules[child_name] = replacement
    return module


def _configure_torch_determinism(seed: int) -> dict[str, object]:
    import numpy
    import torch

    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    return {
        "canonical_random_seed": CANONICAL_TPM_RANDOM_SEED,
        "selected_random_seed": seed,
        "robustness_random_seeds": list(TPM_ROBUSTNESS_RANDOM_SEEDS),
        "python_random_seed": seed,
        "numpy_random_seed": seed,
        "torch_random_seed": seed,
        "torch_version": str(torch.__version__),
        "torch_device": "cpu",
        "torch_dtype": "float64",
        "torch_num_threads": torch.get_num_threads(),
        "torch_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
    }


def _build_stable_fit_summary(*, model: object, tensor: object) -> dict[str, object]:
    import torch

    modules: list[dict[str, object]] = []
    for module_path, module in model.named_modules():
        scope = getattr(module, "scope", None)
        modules.append(
            {
                "path": module_path or "<root>",
                "module_type": f"{type(module).__module__}.{type(module).__qualname__}",
                "query_scope": list(getattr(scope, "query", ())),
                "evidence_scope": list(getattr(scope, "evidence", ())),
            }
        )

    parameter_tensors: list[dict[str, object]] = []
    parameter_count = 0
    for name, parameter in sorted(model.named_parameters(), key=lambda item: item[0]):
        values = parameter.detach().cpu().to(dtype=torch.float64).reshape(-1)
        parameter_count += values.numel()
        parameter_tensors.append(
            {
                "name": name,
                "shape": list(parameter.shape),
                "values": [float(value) for value in values.tolist()],
            }
        )

    with torch.no_grad():
        likelihood = model.log_likelihood(tensor).detach().cpu().to(dtype=torch.float64)
    if not bool(torch.isfinite(likelihood).all()):
        raise RuntimeError("current SPFlow fit produced non-finite training likelihoods")
    flat_likelihood = likelihood.reshape(-1)
    likelihood_values = [float(value) for value in flat_likelihood.tolist()]

    return {
        "structure": {
            "module_count": len(modules),
            "modules": modules,
        },
        "parameters": {
            "parameter_count": parameter_count,
            "tensors": parameter_tensors,
        },
        "likelihood": {
            "shape": list(likelihood.shape),
            "value_count": len(likelihood_values),
            "minimum": min(likelihood_values),
            "maximum": max(likelihood_values),
            "mean": sum(likelihood_values) / len(likelihood_values),
            "values": likelihood_values,
        },
    }


def _canonical_leaf_family_name(leaf: object) -> str:
    for family_name in ("Normal", "Bernoulli", "Categorical"):
        if any(base.__name__ == family_name for base in type(leaf).__mro__):
            return family_name
    return type(leaf).__name__


def _persisted_fit_configuration(
    *,
    config: TPMFitConfig,
    result: _SPFlowFitResult,
    training_random_seed: int,
    input_row_count: int,
    input_column_order: Sequence[str],
) -> dict[str, object]:
    payload = {
        "backend_name": config.backend_name,
        "backend_generation": result.backend_generation,
        "backend_api_version": result.backend_api_version,
        "training_random_seed": training_random_seed,
        "input_row_count": input_row_count,
        "input_column_order": list(input_column_order),
        "learn_mspn_kwargs": dict(config.learn_mspn_kwargs),
        "learn_spn_kwargs": dict(result.learn_spn_kwargs),
        "leaf_families": list(result.leaf_families),
        "notes": list(config.notes),
        "execution_mode": config.execution_mode,
    }
    if result.determinism_configuration:
        payload["determinism_configuration"] = dict(
            result.determinism_configuration
        )
    if result.fit_summary:
        payload["fit_summary"] = dict(result.fit_summary)
    return payload


def _uses_current_spflow_backend(backend: Any | None) -> bool:
    if backend is None:
        return True
    return (
        getattr(backend, "__name__", None) == "spflow"
        and str(getattr(backend, "__version__", "")) == REQUIRED_SPFLOW_VERSION
        and not hasattr(backend, "fit_runtime_payload")
    )


def _load_planning_dataset_artifact(
    source: object,
) -> object:
    from open_energy_lab.planning.dataset import PlanningDatasetArtifact, load_planning_dataset

    if isinstance(source, PlanningDatasetArtifact):
        return source
    to_dict = getattr(source, "to_dict", None)
    if callable(to_dict) and not isinstance(source, str | Path | Mapping):
        # Import-boundary tests deliberately reload the planning module. Rebuild
        # an artifact created by the previous module instance so public in-memory
        # handoff does not depend on dataclass identity surviving that reload.
        return PlanningDatasetArtifact.from_dict(to_dict())
    return load_planning_dataset(source)


def _source_dataset_path(
    source: object,
) -> Path | None:
    if isinstance(source, str | Path):
        return Path(source)
    return None


def _resolved_training_random_seed(
    provenance: Mapping[str, object],
    *,
    configured_seed: int | None,
) -> int:
    if configured_seed is not None:
        return int(configured_seed)

    for key in ("random_seed", "family_seed", "paired_family_seed"):
        value = provenance.get(key)
        if value is not None:
            return int(value)
    return CANONICAL_TPM_RANDOM_SEED


def _build_feature_schema(
    *,
    dataset: object,
    training_data: TPMTrainingData,
    canonical_target_name: str,
    event_target_name: str,
) -> tuple[TPMFeatureSpec, ...]:
    design_feature_schema = {
        str(feature["feature_name"]): feature for feature in dataset.design_feature_schema
    }
    feature_specs: list[TPMFeatureSpec] = []
    for inferred_spec in training_data.feature_schema:
        feature_name = inferred_spec.feature_name
        feature_role = "context"
        modifiable = False
        if feature_name in design_feature_schema:
            declared_feature = design_feature_schema[feature_name]
            declared_type = str(declared_feature["feature_type"])
            if declared_type != inferred_spec.feature_type:
                raise ValueError(
                    "design feature schema type mismatch for "
                    f"{feature_name!r}: expected {declared_type!r}, "
                    f"inferred {inferred_spec.feature_type!r}"
                )
            feature_role = str(declared_feature.get("feature_role", "decision"))
            modifiable = feature_role == "decision"
        elif feature_name == event_target_name:
            feature_specs.append(
                _binary_event_target_spec(
                    feature_name=feature_name,
                    inferred_spec=inferred_spec,
                    rows=training_data.rows,
                )
            )
            continue
        elif feature_name == canonical_target_name:
            feature_role = "metric_target"
            modifiable = False

        feature_specs.append(
            TPMFeatureSpec(
                feature_name=feature_name,
                feature_type=inferred_spec.feature_type,
                feature_role=feature_role,
                modifiable=modifiable,
                monotonicity=inferred_spec.monotonicity,
                bounds=inferred_spec.bounds,
                discrete_values=inferred_spec.discrete_values,
                ordering=inferred_spec.ordering,
                normalization_rule=inferred_spec.normalization_rule,
            )
        )

    feature_names = {spec.feature_name for spec in feature_specs}
    if canonical_target_name not in feature_names:
        raise ValueError(
            "training data does not include the canonical target feature "
            f"{canonical_target_name!r}"
        )
    if event_target_name not in feature_names:
        raise ValueError(
            "training data does not include the SPN event target feature "
            f"{event_target_name!r}"
        )
    return tuple(feature_specs)


def _artifact_provenance(
    *,
    dataset: PlanningDatasetArtifact,
    training_random_seed: int | None,
    training_data: TPMTrainingData,
    dataset_source_path: Path | None,
) -> dict[str, object]:
    provenance = dict(dataset.provenance)
    provenance["training_dataset_id"] = dataset.dataset_id
    provenance["training_row_count"] = dataset.row_count
    provenance["training_column_order"] = list(training_data.column_order)
    if dataset_source_path is not None:
        dataset_source_text = dataset_source_path.as_posix()
        provenance["training_dataset_path"] = dataset_source_text
        provenance["training_dataset_fixture_path"] = dataset_source_text
        provenance["dataset_fixture_path"] = dataset_source_text
    provenance["legacy_evidence_paths"] = list(
        _merge_legacy_evidence_paths(
            provenance.get("legacy_evidence_paths"),
            FIT_LEGACY_EVIDENCE_PATHS,
            PIECEWISE_LEGACY_EVIDENCE_PATHS,
        )
    )
    if training_random_seed is not None:
        provenance["training_random_seed"] = training_random_seed
    return provenance


def _merge_legacy_evidence_paths(*groups: object) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        if group is None:
            continue
        if isinstance(group, str):
            candidates = (group,)
        else:
            candidates = tuple(group)
        for candidate in candidates:
            path = str(candidate)
            if path and path not in merged:
                merged.append(path)
    return tuple(merged)


def _created_at_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _spn_payload_output_path(
    *,
    output_path: str | Path | None,
) -> Path:
    if output_path is not None:
        artifact_path = Path(output_path)
        return artifact_path.with_name(f"{artifact_path.stem}.spn_payload.pkl")
    temporary_directory = Path(tempfile.mkdtemp(prefix="open-energy-lab-tpm-fit-"))
    return temporary_directory / "tpm-artifact.spn_payload.pkl"


def _artifact_source_path(
    *,
    output_path: str | Path | None,
    sidecar_path: Path,
) -> Path:
    if output_path is not None:
        return Path(output_path)
    return sidecar_path.with_name("tpm-artifact.json")


def _prepare_generic_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    build_request: TPMArtifactBuildRequest,
) -> tuple[tuple[Mapping[str, object], ...], bool]:
    if isinstance(rows, Mapping) or isinstance(rows, (str, bytes)):
        raise TypeError("rows must be a sequence of row mappings")
    if not rows:
        raise ValueError("rows must not be empty")

    first_row = rows[0]
    if not isinstance(first_row, Mapping):
        raise TypeError("rows must contain only mappings")

    row_keys = tuple(str(key) for key in first_row.keys())
    if build_request.target_name not in row_keys:
        raise ValueError(
            f"rows do not include canonical target column {build_request.target_name!r}"
        )
    decision_features = set(build_request.decision_features)
    missing_decision_features = [
        feature_name for feature_name in build_request.decision_features if feature_name not in row_keys
    ]
    if missing_decision_features:
        raise ValueError(
            "rows do not include decision feature columns: "
            + ", ".join(missing_decision_features)
        )

    event_was_derived = build_request.event_target_name not in row_keys
    if event_was_derived and build_request.target_threshold is None:
        raise ValueError(
            "target_threshold is required when event_target_name is not present in rows"
        )

    prepared_rows: list[Mapping[str, object]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError("rows must contain only mappings")
        normalized_row_keys = tuple(str(key) for key in row.keys())
        if normalized_row_keys != row_keys:
            raise ValueError(
                f"rows[{index}] must preserve the same keys and order as the first row"
            )
        normalized_row = {str(key): value for key, value in row.items()}
        if event_was_derived:
            target_value = normalized_row[build_request.target_name]
            if not isinstance(target_value, Real) or isinstance(target_value, bool):
                raise ValueError(
                    f"rows[{index}].{build_request.target_name} must be numeric to derive the event target"
                )
            normalized_row[build_request.event_target_name] = int(
                float(target_value) > float(build_request.target_threshold)
            )
        prepared_rows.append(normalized_row)
    return tuple(prepared_rows), event_was_derived


def _build_generic_feature_schema(
    *,
    training_data: TPMTrainingData,
    build_request: TPMArtifactBuildRequest,
) -> tuple[TPMFeatureSpec, ...]:
    feature_specs: list[TPMFeatureSpec] = []
    for inferred_spec in training_data.feature_schema:
        feature_name = inferred_spec.feature_name
        feature_role = build_request.feature_roles.get(feature_name, "context")
        modifiable = False
        if feature_name in build_request.decision_features:
            feature_role = build_request.feature_roles.get(feature_name, "decision")
            modifiable = feature_role == "decision"
        elif feature_name == build_request.event_target_name:
            feature_specs.append(
                _binary_event_target_spec(
                    feature_name=feature_name,
                    inferred_spec=inferred_spec,
                    rows=training_data.rows,
                )
            )
            continue
        elif feature_name == build_request.target_name:
            feature_role = "metric_target"

        feature_specs.append(
            TPMFeatureSpec(
                feature_name=feature_name,
                feature_type=inferred_spec.feature_type,
                feature_role=feature_role,
                modifiable=modifiable,
                monotonicity=inferred_spec.monotonicity,
                bounds=inferred_spec.bounds,
                discrete_values=inferred_spec.discrete_values,
                ordering=inferred_spec.ordering,
                normalization_rule=inferred_spec.normalization_rule,
            )
        )

    feature_names = {spec.feature_name for spec in feature_specs}
    if build_request.target_name not in feature_names:
        raise ValueError(
            "training data does not include the canonical target feature "
            f"{build_request.target_name!r}"
        )
    if build_request.event_target_name not in feature_names:
        raise ValueError(
            "training data does not include the SPN event target feature "
            f"{build_request.event_target_name!r}"
        )
    return tuple(feature_specs)


def _generic_target_definition(
    *,
    build_request: TPMArtifactBuildRequest,
    event_was_derived: bool,
) -> dict[str, object]:
    payload = {
        "target_name": build_request.target_name,
        "event_target_name": build_request.event_target_name,
        "threshold_default": float(build_request.target_threshold or 0.0),
        "supported_query_mode": build_request.supported_query_mode,
    }
    if build_request.target_threshold is not None:
        payload["event_threshold_source"] = "threshold_default"
        payload["event_threshold_comparison"] = ">"
    else:
        payload["event_threshold_source"] = (
            "derived_from_rows"
            if event_was_derived
            else "artifact_rows"
        )
    return payload


def _generic_artifact_provenance(
    *,
    build_request: TPMArtifactBuildRequest,
    training_random_seed: int | None,
    training_data: TPMTrainingData,
) -> dict[str, object]:
    provenance = dict(build_request.provenance)
    provenance["training_dataset_id"] = build_request.dataset_reference
    provenance["training_row_count"] = len(training_data.rows)
    provenance["training_column_order"] = list(training_data.column_order)
    provenance["legacy_evidence_paths"] = list(
        _merge_legacy_evidence_paths(
            provenance.get("legacy_evidence_paths"),
            FIT_LEGACY_EVIDENCE_PATHS,
            PIECEWISE_LEGACY_EVIDENCE_PATHS,
        )
    )
    if training_random_seed is not None:
        provenance["training_random_seed"] = training_random_seed
    return provenance


def _binary_event_target_spec(
    *,
    feature_name: str,
    inferred_spec: TPMFeatureSpec,
    rows: Sequence[Mapping[str, object]],
) -> TPMFeatureSpec:
    observed_values = {
        float(row[feature_name])
        for row in rows
        if isinstance(row.get(feature_name), Real) and not isinstance(row.get(feature_name), bool)
    }
    if not observed_values:
        raise ValueError(f"event target {feature_name!r} must contain numeric values")
    if not observed_values.issubset({0.0, 1.0}):
        raise ValueError(
            f"event target {feature_name!r} must use the binary domain {{0.0, 1.0}}"
        )
    return TPMFeatureSpec(
        feature_name=feature_name,
        feature_type="binary",
        feature_role="target",
        modifiable=False,
        monotonicity=inferred_spec.monotonicity,
        discrete_values=(0.0, 1.0),
        ordering=(0.0, 1.0),
    )
