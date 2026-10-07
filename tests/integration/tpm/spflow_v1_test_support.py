"""Shared deterministic inputs for current-SPFlow corrective integration tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from time import perf_counter

from tpm.artifact import TPMArtifact, load_tpm_artifact
from tpm.fit import (
    TPMArtifactBuildRequest,
    TPMFitConfig,
    fit_tpm_artifact_from_rows,
)
from tpm.spflow_backend import load_spflow_payload
from tpm.query import TPMQueryRequest


CANONICAL_SEED = 13
ROBUSTNESS_SEEDS = (37, 101)
FIT_BUDGET_SECONDS = 30.0
QUERY_BUDGET_SECONDS = 30.0


def mixed_feature_rows() -> tuple[Mapping[str, object], ...]:
    """Return deterministic continuous, binary, and categorical training rows."""

    rows: list[Mapping[str, object]] = []
    design_classes = ("compact", "balanced", "resilient")
    for index in range(36):
        battery_capacity_kwh = 2.0 + 2.0 * (index % 6)
        solar_enabled = index % 2
        design_class = design_classes[index % len(design_classes)]
        ambient_temperature_c = 20.0 + 2.0 * (index % 4)
        shortfall = max(
            0.0,
            0.18
            - 0.008 * battery_capacity_kwh
            - 0.04 * solar_enabled
            + (0.025 if design_class == "compact" else 0.0)
            + 0.002 * (ambient_temperature_c - 20.0),
        )
        rows.append(
            {
                "battery_capacity_kwh": battery_capacity_kwh,
                "solar_enabled": solar_enabled,
                "design_class": design_class,
                "ambient_temperature_c": ambient_temperature_c,
                "shortfall": shortfall,
            }
        )
    return tuple(rows)


def artifact_build_request() -> TPMArtifactBuildRequest:
    return TPMArtifactBuildRequest(
        artifact_id="current-spflow-mixed-artifact",
        dataset_reference="current-spflow-mixed-dataset",
        decision_features=(
            "battery_capacity_kwh",
            "solar_enabled",
            "design_class",
        ),
        target_name="shortfall",
        event_target_name="shortfall_event",
        target_threshold=0.08,
        provenance={"random_seed": CANONICAL_SEED},
    )


def current_spflow_fit_config(seed: int) -> TPMFitConfig:
    return TPMFitConfig(
        training_random_seed=seed,
        spn_payload_format="spflow-model-sidecar",
        learn_mspn_kwargs={
            "threshold": 0.3,
            "min_features_slice": 2,
            "min_instances_slice": 100,
            "n_clusters": 2,
        },
        notes=("current-spflow-contract-test",),
    )


def fit_real_artifact(
    directory: Path,
    *,
    seed: int = CANONICAL_SEED,
    artifact_name: str | None = None,
) -> tuple[TPMArtifact, Path, float]:
    """Fit, persist, and reload one real current-SPFlow artifact."""

    output_path = directory / f"{artifact_name or f'current-spflow-{seed}'}.json"
    started = perf_counter()
    fit_tpm_artifact_from_rows(
        mixed_feature_rows(),
        build_request=artifact_build_request(),
        output_path=output_path,
        fit_config=current_spflow_fit_config(seed),
    )
    elapsed = perf_counter() - started
    return load_tpm_artifact(output_path), output_path, elapsed


def load_current_model_payload(artifact: TPMArtifact) -> dict[str, object]:
    payload = load_spflow_payload(artifact)
    assert payload is not None
    assert payload.get("backend_generation") == "current-spflow"
    assert payload.get("backend_api_version") == "1.1.0"
    assert payload.get("model") is not None
    return payload


def normalized_training_tensor(artifact: TPMArtifact):
    import torch

    rows = []
    for raw_row in mixed_feature_rows():
        row = dict(raw_row)
        row["shortfall_event"] = int(float(row["shortfall"]) > 0.08)
        rows.append(row)
    return torch.tensor(
        [
            [spec.normalize_value(row[spec.feature_name]) for spec in artifact.feature_specs]
            for row in rows
        ],
        dtype=torch.float64,
    )


def valid_query_request() -> TPMQueryRequest:
    return TPMQueryRequest(
        decision_assignments={
            "battery_capacity_kwh": 4.0,
            "solar_enabled": 1,
            "design_class": "balanced",
        },
        marginalized_features=("ambient_temperature_c",),
        target_name="shortfall",
    )
