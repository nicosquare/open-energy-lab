"""Unit contracts for TPM artifact schema-v2 persistence and loading."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from pathlib import Path
from copy import deepcopy

import pytest

from tpm.artifact import (
    SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS,
    UnsupportedTPMArtifactVersionError,
    load_tpm_artifact,
)
from tpm.spflow_backend import load_spflow_payload


SIDECAR_BYTES = b"deterministic-spflow-1.1-sidecar\n"


def _sidecar_hash(payload: bytes = SIDECAR_BYTES) -> str:
    return hashlib.sha256(payload).hexdigest()


def _artifact_payload(
    *,
    execution_mode: str = "production",
    locator: str = "sidecars/tpm-artifact-unit.spflow",
    payload_hash: str | None = None,
) -> dict[str, object]:
    return {
        "artifact_id": "tpm-artifact-unit",
        "schema_version": "v2",
        "created_at": "2026-08-18T00:00:00Z",
        "dataset_reference": "planning-dataset-export-integration",
        "feature_schema": [
            {
                "feature_name": "battery_capacity_kwh",
                "feature_role": "decision",
                "feature_type": "continuous",
                "bounds": [0.0, 20.0],
                "modifiable": True,
            },
            {
                "feature_name": "solar_has_tracking",
                "feature_role": "decision",
                "feature_type": "binary",
                "discrete_values": ["disabled", "enabled"],
                "modifiable": True,
            },
            {
                "feature_name": "design_name",
                "feature_role": "decision",
                "feature_type": "categorical",
                "discrete_values": ["baseline-a", "baseline-b"],
                "modifiable": True,
            },
            {
                "feature_name": "solar_tilt_choice",
                "feature_role": "decision",
                "feature_type": "mixed",
                "bounds": [0.0, 45.0],
                "discrete_values": ["roof-flat", "roof-pitched"],
                "modifiable": True,
            },
            {
                "feature_name": "shortfall",
                "feature_role": "metric_target",
                "feature_type": "continuous",
                "bounds": [0.0, 1.0],
                "modifiable": False,
            },
            {
                "feature_name": "shortfall_exceeds_threshold",
                "feature_role": "target",
                "feature_type": "binary",
                "discrete_values": [0.0, 1.0],
                "modifiable": False,
            },
        ],
        "target_definition": {
            "target_name": "shortfall",
            "event_target_name": "shortfall_exceeds_threshold",
            "threshold_default": 0.05,
            "supported_query_mode": "exceedance-probability",
        },
        "fit_configuration": {
            "backend_name": "spflow",
            "training_random_seed": 13,
        },
        "backend_generation": "current-spflow",
        "backend_api_version": "1.1.0",
        "execution_mode": execution_mode,
        "spn_payload": {
            "locator": locator,
            "serialization": "spflow-model-sidecar",
        },
        "spn_payload_format": "spflow-model-sidecar",
        "payload_hash": payload_hash or _sidecar_hash(),
        "query_configuration": {
            "supported_output_modes": [
                "conditional_probability",
                "log_likelihood",
            ],
            "required_decision_features": [
                "battery_capacity_kwh",
                "design_name",
            ],
        },
        "approximation_metadata": {
            "approximation_kind": "piecewise",
            "compiler_version": "spflow-v1-mio-v1",
            "breakpoint_policy": {
                "policy_name": "canonical-five-breakpoint-v1",
                "breakpoint_count": 5,
            },
            "mio_epsilon": 1e-6,
            "tolerance": 1e-9,
        },
        "provenance": {
            "dataset_fixture_path": "tests/fixtures/tpm/planning_dataset_v1.json",
            "legacy_evidence_paths": [
                "legacy/old_tpm/src_py/tpm/data/datahandler.py",
                "legacy/old_tpm/src_py/tpm/spn/main.py",
            ],
            "training_random_seed": 13,
        },
    }


def _v3_feature_schema() -> list[dict[str, object]]:
    return [
        {
            "feature_name": "x",
            "feature_role": "decision",
            "feature_type": "continuous",
            "bounds": [40.0, 160.0],
            "modifiable": True,
            "normalization_rule": "minmax",
            "mathematical_domain": {
                "feature_name": "x",
                "feature_kind": "continuous",
                "purpose": "decision-domain",
                "shape": "finite",
                "lower": 40.0,
                "upper": 160.0,
                "origin": "caller-declared",
            },
            "training_support": {
                "feature_name": "x",
                "feature_kind": "continuous",
                "minimum": 60.0,
                "maximum": 140.0,
                "origin": "physical-training-rows",
            },
            "normalization": {
                "feature_name": "x",
                "feature_kind": "continuous",
                "kind": "min-max",
                "origin": "caller-declared",
                "lower": 40.0,
                "upper": 160.0,
            },
        },
        {
            "feature_name": "demand",
            "feature_role": "metric_target",
            "feature_type": "continuous",
            "modifiable": False,
            "normalization_rule": "identity",
            "mathematical_domain": {
                "feature_name": "demand",
                "feature_kind": "continuous",
                "purpose": "distribution-support",
                "shape": "unbounded",
                "origin": "caller-declared",
            },
            "training_support": {
                "feature_name": "demand",
                "feature_kind": "continuous",
                "minimum": 72.0,
                "maximum": 134.0,
                "origin": "physical-training-rows",
            },
            "normalization": {
                "feature_name": "demand",
                "feature_kind": "continuous",
                "kind": "identity",
                "origin": "caller-declared",
            },
        },
        {
            "feature_name": "demand_event",
            "feature_role": "target",
            "feature_type": "binary",
            "modifiable": False,
            "discrete_values": [0.0, 1.0],
            "ordering": [0.0, 1.0],
            "normalization_rule": "binary_index",
            "mathematical_domain": {
                "feature_name": "demand_event",
                "feature_kind": "binary",
                "purpose": "distribution-support",
                "values": [0.0, 1.0],
                "ordering": [0.0, 1.0],
                "origin": "internal-exact-target",
            },
            "training_support": {
                "feature_name": "demand_event",
                "feature_kind": "binary",
                "observed_values": [0.0, 1.0],
                "origin": "physical-training-rows",
            },
            "normalization": {
                "feature_name": "demand_event",
                "feature_kind": "binary",
                "kind": "ordered-index",
                "origin": "internal-exact-target",
                "ordering": [0.0, 1.0],
            },
        },
    ]


def _v3_artifact_payload(
    *,
    locator: str = "sidecars/tpm-artifact-unit.spflow",
    payload_hash: str | None = None,
) -> dict[str, object]:
    payload = _artifact_payload(locator=locator, payload_hash=payload_hash)
    payload["artifact_id"] = "tpm-artifact-domains-v3-unit"
    payload["schema_version"] = "v3"
    payload["feature_schema"] = _v3_feature_schema()
    payload["target_definition"] = {
        "target_name": "demand",
        "event_target_name": "demand_event",
        "threshold_default": 100.0,
        "supported_query_mode": "exceedance-probability",
    }
    payload["query_configuration"] = {
        "supported_output_modes": ["conditional_probability", "log_likelihood"],
        "required_decision_features": ["x"],
    }
    return payload


def _write_manifest(
    tmp_path: Path,
    *,
    sidecar_payload: bytes = SIDECAR_BYTES,
    payload: dict[str, object] | None = None,
) -> Path:
    artifact_payload = dict(
        payload or _artifact_payload(payload_hash=_sidecar_hash(sidecar_payload))
    )
    manifest_path = tmp_path / "artifacts" / "tpm-artifact.json"
    locator = str(dict(artifact_payload["spn_payload"])["locator"])
    sidecar_path = manifest_path.parent / locator
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_bytes(sidecar_payload)
    manifest_path.write_text(
        json.dumps(artifact_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def test_supported_tpm_artifact_versions_include_v2_compatibility_and_v3_semantics() -> None:
    assert SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS == ("v2", "v3")


def test_load_schema_v2_preserves_backend_mode_and_sidecar_metadata(tmp_path: Path) -> None:
    artifact = load_tpm_artifact(_write_manifest(tmp_path))

    assert artifact.schema_version == "v2"
    assert artifact.backend_generation == "current-spflow"
    assert artifact.backend_api_version == "1.1.0"
    assert artifact.execution_mode == "production"
    assert artifact.spn_payload["locator"] == "sidecars/tpm-artifact-unit.spflow"
    assert artifact.spn_payload_format == "spflow-model-sidecar"
    assert artifact.payload_hash == _sidecar_hash()
    assert artifact.approximation_metadata["compiler_version"] == "spflow-v1-mio-v1"


@pytest.mark.parametrize(
    "field_name",
    ("backend_generation", "backend_api_version", "execution_mode", "payload_hash"),
)
def test_schema_v2_requires_backend_and_execution_metadata(field_name: str) -> None:
    payload = _artifact_payload()
    payload.pop(field_name)

    with pytest.raises(ValueError, match=field_name):
        load_tpm_artifact(payload)


def test_schema_v2_rejects_unknown_execution_mode() -> None:
    with pytest.raises(ValueError, match=r"execution_mode must be 'production'"):
        load_tpm_artifact(_artifact_payload(execution_mode="automatic-fallback"))


def test_schema_v2_rejects_removed_fixture_replay_mode() -> None:
    with pytest.raises(ValueError, match="fixture_replay' was removed"):
        load_tpm_artifact(_artifact_payload(execution_mode="fixture_replay"))


@pytest.mark.parametrize(
    "locator",
    (
        "/tmp/tpm-artifact-unit.spflow",
        "../outside-project.spflow",
        "sidecars/../../outside-project.spflow",
    ),
)
def test_schema_v2_rejects_non_project_relative_sidecar_locators(locator: str) -> None:
    with pytest.raises(ValueError, match=r"spn_payload.*locator.*relative|project-relative"):
        load_tpm_artifact(_artifact_payload(locator=locator))


def test_load_schema_v2_verifies_sidecar_sha256_integrity(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)

    artifact = load_tpm_artifact(manifest_path)
    assert artifact.payload_hash == _sidecar_hash()

    sidecar_path = manifest_path.parent / str(dict(artifact.spn_payload)["locator"])
    sidecar_path.write_bytes(b"corrupt-sidecar\n")

    with pytest.raises(ValueError, match=r"(?i)sha-256|integrity|payload hash"):
        load_tpm_artifact(manifest_path)


def test_write_json_atomically_replaces_through_a_sibling_temp_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = load_tpm_artifact(_write_manifest(tmp_path))
    output_path = tmp_path / "published" / "tpm-artifact.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("stale manifest\n", encoding="utf-8")
    replace_calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def _record_replace(
        source: str | bytes | os.PathLike[str],
        destination: str | bytes | os.PathLike[str],
    ) -> None:
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", _record_replace)

    artifact.write_json(output_path)

    assert replace_calls
    temporary_path, destination_path = replace_calls[-1]
    assert destination_path == output_path
    assert temporary_path != destination_path
    assert temporary_path.parent == destination_path.parent
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == "v2"


def test_schema_v1_legacy_payload_is_rejected_with_refit_guidance() -> None:
    payload = _artifact_payload()
    payload["schema_version"] = "v1"

    with pytest.raises(
        UnsupportedTPMArtifactVersionError,
        match=r"(?i)schema.?v?1|legacy|refit",
    ):
        load_tpm_artifact(payload)


def test_load_tpm_artifact_rejects_unknown_schema_version() -> None:
    payload = _artifact_payload()
    payload["schema_version"] = "v999"

    with pytest.raises(
        UnsupportedTPMArtifactVersionError,
        match="unsupported tpm artifact schema_version 'v999'",
    ):
        load_tpm_artifact(payload)


def test_loaded_tpm_artifact_rejects_invalid_feature_assignments(tmp_path: Path) -> None:
    artifact = load_tpm_artifact(_write_manifest(tmp_path))

    with pytest.raises(ValueError, match="design_name|categorical|baseline-z"):
        artifact.validate_feature_assignments({"design_name": "baseline-z"})

    with pytest.raises(ValueError, match="battery_capacity_kwh|bounds|21"):
        artifact.validate_feature_assignments({"battery_capacity_kwh": 21.0})


@pytest.mark.parametrize(
    ("shape", "lower", "upper", "support", "normalization_kind"),
    [
        ("finite", 40.0, 160.0, (60.0, 140.0), "min-max"),
        ("finite", 100.0, 100.0, (100.0, 100.0), "fixed-zero"),
        ("lower-bounded", 40.0, None, (60.0, 140.0), "identity"),
        ("upper-bounded", None, 160.0, (60.0, 140.0), "identity"),
        ("unbounded", None, None, (60.0, 140.0), "identity"),
        ("unknown", None, None, (60.0, 140.0), "identity"),
    ],
)
def test_schema_v3_round_trips_every_continuous_domain_shape(
    shape: str,
    lower: float | None,
    upper: float | None,
    support: tuple[float, float],
    normalization_kind: str,
) -> None:
    payload = _v3_artifact_payload()
    x_feature = payload["feature_schema"][0]
    domain = x_feature["mathematical_domain"]
    domain["shape"] = shape
    domain.pop("lower", None)
    domain.pop("upper", None)
    if lower is not None:
        domain["lower"] = lower
    if upper is not None:
        domain["upper"] = upper
    x_feature["training_support"]["minimum"] = support[0]
    x_feature["training_support"]["maximum"] = support[1]
    normalization = x_feature["normalization"]
    normalization["kind"] = normalization_kind
    normalization.pop("lower", None)
    normalization.pop("upper", None)
    x_feature.pop("bounds", None)
    x_feature["normalization_rule"] = {
        "min-max": "minmax",
        "fixed-zero": "minmax",
        "identity": "identity",
    }[normalization_kind]
    if normalization_kind != "identity":
        normalization["lower"] = lower
        normalization["upper"] = upper
        x_feature["bounds"] = [lower, upper]

    artifact = load_tpm_artifact(payload)
    reloaded = load_tpm_artifact(artifact.to_dict())
    spec = reloaded.feature_specs[0]

    assert spec.mathematical_domain.shape == shape
    assert spec.mathematical_domain.lower == lower
    assert spec.mathematical_domain.upper == upper
    assert spec.training_support.minimum == support[0]
    assert spec.training_support.maximum == support[1]
    assert spec.normalization.kind == normalization_kind


def test_schema_v3_rejects_non_finite_semantic_numeric_values() -> None:
    payload = _v3_artifact_payload()
    payload["feature_schema"][0]["mathematical_domain"]["lower"] = float("inf")

    with pytest.raises(ValueError, match="finite numeric"):
        load_tpm_artifact(payload)


def test_schema_v2_adapter_exposes_unknown_domain_and_legacy_operational_meaning() -> None:
    artifact = load_tpm_artifact(_artifact_payload())
    continuous = artifact.feature_specs[0]
    discrete = artifact.feature_specs[1]

    assert continuous.mathematical_domain.shape == "unknown"
    assert continuous.mathematical_domain.origin == "omitted"
    assert continuous.training_support.minimum == pytest.approx(0.0)
    assert continuous.training_support.maximum == pytest.approx(20.0)
    assert continuous.normalization.origin == "legacy-inferred"
    assert continuous.normalization.kind == "min-max"
    assert discrete.mathematical_domain.shape == "unknown"
    assert discrete.mathematical_domain.origin == "omitted"
    assert discrete.training_support.observed_values == ("disabled", "enabled")
    assert discrete.normalization.origin == "legacy-inferred"

    serialized = artifact.to_dict()
    assert serialized["schema_version"] == "v2"
    assert all(
        "mathematical_domain" not in feature
        and "training_support" not in feature
        and "normalization" not in feature
        for feature in serialized["feature_schema"]
    )


def test_schema_v2_mixed_feature_and_repeated_reserialization_remain_v2_only() -> None:
    original_payload = _artifact_payload()
    artifact = load_tpm_artifact(original_payload)
    mixed = {
        spec.feature_name: spec for spec in artifact.feature_specs
    }["solar_tilt_choice"]

    assert mixed.feature_type == "mixed"
    assert mixed.bounds == (0.0, 45.0)
    assert mixed.discrete_values == ("roof-flat", "roof-pitched")
    assert mixed.mathematical_domain is None
    first = artifact.to_dict()
    second = load_tpm_artifact(first).to_dict()
    third = load_tpm_artifact(second).to_dict()

    assert first == second == third
    assert third["schema_version"] == "v2"
    mixed_payload = third["feature_schema"][3]
    assert mixed_payload == original_payload["feature_schema"][3] | {
        "monotonicity": "none",
        "normalization_rule": "mixed_index_minmax",
        "ordering": ["roof-flat", "roof-pitched"],
    }
    assert "legacy_mixed_semantics" not in mixed_payload


def test_loading_v2_manifest_and_sidecar_is_byte_stable(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    sidecar_path = manifest_path.parent / "sidecars/tpm-artifact-unit.spflow"
    manifest_before = manifest_path.read_bytes()
    sidecar_before = sidecar_path.read_bytes()

    first = load_tpm_artifact(manifest_path)
    second = load_tpm_artifact(manifest_path)

    assert first.to_dict() == second.to_dict()
    assert manifest_path.read_bytes() == manifest_before
    assert sidecar_path.read_bytes() == sidecar_before


def test_schema_v3_sidecar_feature_semantics_match_manifest_after_reload(
    tmp_path: Path,
) -> None:
    runtime_payload = {
        "artifact_schema_version": "v3",
        "feature_schema": _v3_feature_schema(),
        "query_strategy": "spflow",
        "raw_rows": [],
    }
    sidecar_payload = pickle.dumps(runtime_payload)
    manifest_path = _write_manifest(
        tmp_path,
        sidecar_payload=sidecar_payload,
        payload=_v3_artifact_payload(payload_hash=_sidecar_hash(sidecar_payload)),
    )

    loaded = load_spflow_payload(load_tpm_artifact(manifest_path))

    assert loaded is not None
    assert loaded["artifact_schema_version"] == "v3"


def test_schema_v3_rejects_manifest_and_sidecar_feature_semantic_disagreement(
    tmp_path: Path,
) -> None:
    sidecar_schema = deepcopy(_v3_feature_schema())
    sidecar_schema[0]["bounds"] = [20.0, 160.0]
    sidecar_schema[0]["mathematical_domain"]["lower"] = 20.0
    sidecar_schema[0]["normalization"]["lower"] = 20.0
    runtime_payload = {
        "artifact_schema_version": "v3",
        "feature_schema": sidecar_schema,
        "query_strategy": "spflow",
        "raw_rows": [],
    }
    sidecar_payload = pickle.dumps(runtime_payload)
    manifest_path = _write_manifest(
        tmp_path,
        sidecar_payload=sidecar_payload,
        payload=_v3_artifact_payload(payload_hash=_sidecar_hash(sidecar_payload)),
    )
    artifact = load_tpm_artifact(manifest_path)

    with pytest.raises(ValueError, match="sidecar.*feature_schema|disagree"):
        load_spflow_payload(artifact)
