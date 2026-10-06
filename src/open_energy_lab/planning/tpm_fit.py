"""Fit TPM artifacts from planning datasets and planning-study manifests.

Both entry points translate planning data into the generic
:func:`tpm.fit_tpm_artifact_from_rows` request, so the TPM
package never needs to know planning formats.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from tpm import (
    TPMArtifact,
    TPMArtifactBuildRequest,
    TPMFitConfig,
    TPMFitMemoryError,
    fit_tpm_artifact_from_rows,
)
from tpm.domains import TPMFeatureDomain
from tpm.fit import CANONICAL_TPM_RANDOM_SEED

from .dataset import PlanningDatasetArtifact, load_planning_dataset
from .study_dataset import (
    PlanningStudyDatasetManifest,
    iter_study_rows,
    load_study_dataset_manifest,
)


def _planning_dataset(source: object) -> PlanningDatasetArtifact:
    if isinstance(source, PlanningDatasetArtifact):
        return source
    to_dict = getattr(source, "to_dict", None)
    if callable(to_dict) and not isinstance(source, str | Path | Mapping):
        # Import-boundary tests deliberately reload the planning module. Rebuild
        # an artifact created by the previous module instance so public in-memory
        # handoff does not depend on dataclass identity surviving that reload.
        return PlanningDatasetArtifact.from_dict(to_dict())
    return load_planning_dataset(source)  # type: ignore[arg-type]


def fit_tpm_artifact(
    source: object,
    *,
    output_path: str | Path | None = None,
    fit_config: TPMFitConfig | None = None,
    feature_domains: Mapping[str, TPMFeatureDomain] | None = None,
) -> TPMArtifact:
    """Fit and optionally persist a TPM artifact from one planning dataset."""

    dataset = _planning_dataset(source)
    provenance = dict(dataset.provenance)
    if isinstance(source, str | Path):
        source_text = Path(source).as_posix()
        provenance["training_dataset_path"] = source_text
        provenance["training_dataset_fixture_path"] = source_text
        provenance["dataset_fixture_path"] = source_text
    decision_features = tuple(
        str(feature["feature_name"]) for feature in dataset.design_feature_schema
    )
    return fit_tpm_artifact_from_rows(
        dataset.rows,
        build_request=TPMArtifactBuildRequest(
            artifact_id=f"tpm-artifact:{dataset.dataset_id}",
            dataset_reference=dataset.dataset_id,
            decision_features=decision_features,
            target_name=str(dataset.target_metadata["target_name"]),
            event_target_name=str(dataset.target_metadata["event_target_name"]),
            target_threshold=float(dataset.target_metadata["threshold_default"]),
            numeric_tolerance=float(dataset.export_configuration["numeric_tolerance"]),
            feature_domains=dict(feature_domains or {}),
            provenance=provenance,
            target_definition=dict(dataset.target_metadata),
            declared_feature_types={
                str(feature["feature_name"]): str(feature["feature_type"])
                for feature in dataset.design_feature_schema
            },
        ),
        output_path=output_path,
        fit_config=fit_config,
    )


def fit_tpm_artifact_from_study_manifest(
    manifest: object,
    *,
    output_path: str | Path,
    fit_feature_names: Sequence[str] | None = None,
    max_tensor_bytes: int = 1_073_741_824,
    fit_config: TPMFitConfig | None = None,
    feature_domains: Mapping[str, TPMFeatureDomain] | None = None,
) -> TPMArtifact:
    """Fit a compact TPM from a file-backed schema-v2 planning-study manifest."""

    resolved = (
        manifest
        if isinstance(manifest, PlanningStudyDatasetManifest)
        else load_study_dataset_manifest(manifest)  # type: ignore[arg-type]
    )
    if not resolved.source_path:
        raise ValueError("study TPM fitting requires a file-backed manifest")
    metadata = dict(resolved.metadata)
    request_metadata = metadata.get("study_request")
    if not isinstance(request_metadata, Mapping):
        raise ValueError("study manifest metadata must include study_request")
    event_metadata = request_metadata.get("adequacy_event")
    if not isinstance(event_metadata, Mapping):
        raise ValueError("study_request must include adequacy_event metadata")
    target_name = str(event_metadata.get("kind", ""))
    event_target_name = str(metadata.get("active_event_target", ""))
    if not target_name or not event_target_name:
        raise ValueError("study manifest must identify the adequacy target and event")

    selected = tuple(
        str(name)
        for name in (
            fit_feature_names
            if fit_feature_names is not None
            else metadata.get("default_fit_feature_names", ())
        )
    )
    required = ("battery_option_id", "solar_option_id", target_name, event_target_name)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("fit_feature_names must be non-empty and unique")
    missing_required = [name for name in required if name not in selected]
    if missing_required:
        raise ValueError(
            "compact study fit must include decision, target, and event features: "
            + ", ".join(missing_required)
        )
    unknown = [name for name in selected if name not in resolved.column_order]
    if unknown:
        raise ValueError("fit_feature_names reference unknown columns: " + ", ".join(unknown))
    if isinstance(max_tensor_bytes, bool) or int(max_tensor_bytes) <= 0:
        raise ValueError("max_tensor_bytes must be a positive integer")
    estimated_tensor_bytes = resolved.row_count * len(selected) * 8
    if estimated_tensor_bytes > int(max_tensor_bytes):
        raise TPMFitMemoryError(
            "selected TPM tensor requires "
            f"{estimated_tensor_bytes} bytes, exceeding max_tensor_bytes={int(max_tensor_bytes)}"
        )

    compact_rows = tuple(
        {name: row[name] for name in selected}
        for row in iter_study_rows(resolved)
    )
    seed = int(request_metadata.get("random_seed", CANONICAL_TPM_RANDOM_SEED))
    configured = (
        replace(fit_config, persist_training_rows=False)
        if fit_config is not None
        else TPMFitConfig(
            training_random_seed=seed,
            spn_payload_format="spflow-model-sidecar",
            persist_training_rows=False,
        )
    )
    return fit_tpm_artifact_from_rows(
        compact_rows,
        build_request=TPMArtifactBuildRequest(
            artifact_id=f"tpm-study:{resolved.dataset_id}",
            dataset_reference=resolved.dataset_id,
            decision_features=("battery_option_id", "solar_option_id"),
            target_name=target_name,
            event_target_name=event_target_name,
            target_threshold=float(event_metadata["threshold"]),
            feature_roles={
                "battery_option_id": "decision",
                "solar_option_id": "decision",
                target_name: "target",
                event_target_name: "target",
            },
            feature_domains=dict(feature_domains or {}),
            provenance={
                "study_manifest_path": resolved.source_path.as_posix(),
                "study_semantic_sha256": resolved.semantic_sha256,
                "study_request_fingerprint": resolved.request_fingerprint,
                "study_row_count": resolved.row_count,
                "fit_feature_names": list(selected),
                "estimated_tensor_bytes": estimated_tensor_bytes,
                "training_random_seed": seed,
            },
        ),
        output_path=Path(output_path),
        fit_config=configured,
    )


__all__ = ["fit_tpm_artifact", "fit_tpm_artifact_from_study_manifest"]
