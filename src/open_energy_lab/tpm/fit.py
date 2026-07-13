"""Scaffolding for SPFlow-backed TPM fitting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from open_energy_lab.planning.dataset import PlanningDatasetArtifact, load_planning_dataset

from .artifact import FEATURE_NAME, TPMArtifact
from .data import TPMTrainingData, normalize_training_data
from .features import TPMFeatureSpec, dump_feature_schema
from .optional_spflow import fit_spflow_model


CANONICAL_OUTPUT_MODES = (
    "conditional_probability",
    "log_likelihood",
)
FIT_LEGACY_EVIDENCE_PATHS = (
    "legacy/old_tpm/src_py/tpm/data/datahandler.py",
    "legacy/old_tpm/src_py/tpm/spn/main.py",
)
PIECEWISE_LEGACY_EVIDENCE_PATHS = (
    "legacy/old_tpm/src_py/tpm/spn/encoding.py",
    "legacy/old_tpm/src_py/tpm/spn/utils_tangent.py",
    "legacy/old_tpm/src_py/utils/densities.py",
)


@dataclass(frozen=True, slots=True)
class TPMFitConfig:
    """SPFlow-backed TPM fit configuration captured in persisted artifacts."""

    backend_name: str = "spflow"
    training_random_seed: int | None = None
    spn_payload_format: str = "json-inline"
    supported_output_modes: tuple[str, ...] = CANONICAL_OUTPUT_MODES
    learn_mspn_kwargs: Mapping[str, object] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)

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
        object.__setattr__(self, "spn_payload_format", spn_payload_format)

        if self.training_random_seed is not None:
            object.__setattr__(self, "training_random_seed", int(self.training_random_seed))

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


def fit_tpm_artifact(
    source: PlanningDatasetArtifact | str | Path | Mapping[str, Any],
    *,
    output_path: str | Path | None = None,
    fit_config: TPMFitConfig | None = None,
    spflow_backend: Any | None = None,
) -> TPMArtifact:
    """Fit and optionally persist a first-release TPM artifact."""

    dataset = _load_planning_dataset_artifact(source)
    config = fit_config or TPMFitConfig()
    training_data = normalize_training_data(dataset.rows)
    target_name = str(dataset.target_metadata["target_name"])
    training_random_seed = _resolved_training_random_seed(
        dataset.provenance,
        configured_seed=config.training_random_seed,
    )
    feature_schema = _build_feature_schema(
        dataset=dataset,
        training_data=training_data,
        target_name=target_name,
    )
    spn_payload = fit_spflow_model(
        training_data,
        target_name=target_name,
        training_random_seed=training_random_seed,
        learn_mspn_kwargs=config.learn_mspn_kwargs,
        backend=spflow_backend,
    )

    artifact = TPMArtifact(
        artifact_id=f"tpm-artifact:{dataset.dataset_id}",
        schema_version="v1",
        created_at=_created_at_utc(),
        dataset_reference=dataset.dataset_id,
        feature_schema=dump_feature_schema(feature_schema),
        target_definition=dict(dataset.target_metadata),
        fit_configuration={
            "backend_name": config.backend_name,
            "training_random_seed": training_random_seed,
            "input_row_count": dataset.row_count,
            "input_column_order": list(dataset.column_order),
            "learn_mspn_kwargs": dict(config.learn_mspn_kwargs),
            "notes": list(config.notes),
        },
        spn_payload=spn_payload,
        spn_payload_format=config.spn_payload_format,
        query_configuration={
            "supported_output_modes": list(config.supported_output_modes),
            "required_decision_features": [
                str(feature["feature_name"]) for feature in dataset.design_feature_schema
            ],
        },
        approximation_metadata={
            "approximation_kind": "piecewise",
            "tolerance": float(dataset.export_configuration["numeric_tolerance"]),
            "legacy_reference_paths": list(PIECEWISE_LEGACY_EVIDENCE_PATHS),
        },
        provenance=_artifact_provenance(
            dataset=dataset,
            training_random_seed=training_random_seed,
            training_data=training_data,
        ),
    )
    if output_path is not None:
        artifact.write_json(output_path)
    return artifact


__all__ = [
    "CANONICAL_OUTPUT_MODES",
    "FEATURE_NAME",
    "FIT_LEGACY_EVIDENCE_PATHS",
    "PIECEWISE_LEGACY_EVIDENCE_PATHS",
    "TPMFitConfig",
    "fit_tpm_artifact",
]


def _load_planning_dataset_artifact(
    source: PlanningDatasetArtifact | str | Path | Mapping[str, Any],
) -> PlanningDatasetArtifact:
    if isinstance(source, PlanningDatasetArtifact):
        return source
    return load_planning_dataset(source)


def _resolved_training_random_seed(
    provenance: Mapping[str, object],
    *,
    configured_seed: int | None,
) -> int | None:
    if configured_seed is not None:
        return int(configured_seed)

    for key in ("random_seed", "family_seed", "paired_family_seed"):
        value = provenance.get(key)
        if value is not None:
            return int(value)
    return None


def _build_feature_schema(
    *,
    dataset: PlanningDatasetArtifact,
    training_data: TPMTrainingData,
    target_name: str,
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
        elif feature_name == target_name:
            feature_role = "target"

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

    if target_name not in {spec.feature_name for spec in feature_specs}:
        raise ValueError(f"training data does not include the target feature {target_name!r}")
    return tuple(feature_specs)


def _artifact_provenance(
    *,
    dataset: PlanningDatasetArtifact,
    training_random_seed: int | None,
    training_data: TPMTrainingData,
) -> dict[str, object]:
    provenance = dict(dataset.provenance)
    provenance["training_dataset_id"] = dataset.dataset_id
    provenance["training_row_count"] = dataset.row_count
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
