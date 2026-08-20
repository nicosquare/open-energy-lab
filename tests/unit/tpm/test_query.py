"""Unit contracts for explicit TPM production and fixture-replay queries."""

from __future__ import annotations

import hashlib
import math

import pytest

from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.query import TPMQueryRequest, query_tpm_artifact


def _artifact_payload(*, execution_mode: str = "fixture_replay") -> dict[str, object]:
    return {
        "artifact_id": "tpm-artifact-query-unit",
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
                "feature_name": "design_name",
                "feature_role": "decision",
                "feature_type": "categorical",
                "discrete_values": ["baseline-a", "baseline-b"],
                "modifiable": True,
            },
            {
                "feature_name": "solar_has_tracking",
                "feature_role": "context",
                "feature_type": "binary",
                "discrete_values": ["disabled", "enabled"],
                "modifiable": False,
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
        "fit_configuration": {"backend_name": "spflow"},
        "backend_generation": "current-spflow",
        "backend_api_version": "1.1.0",
        "execution_mode": execution_mode,
        "spn_payload": {
            "locator": "sidecars/tpm-artifact-query-unit.spflow",
            "serialization": "spflow-model-sidecar",
        },
        "spn_payload_format": "spflow-model-sidecar",
        "payload_hash": hashlib.sha256(b"fixture-replay-not-loaded").hexdigest(),
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
                "legacy/old_tpm/src_py/tpm/spn/main.py",
            ],
        },
    }


def _query_request(
    *,
    execution_mode: str = "fixture_replay",
    output_mode: str = "conditional_probability",
) -> TPMQueryRequest:
    return TPMQueryRequest(
        decision_assignments={
            "battery_capacity_kwh": 8.0,
            "design_name": "baseline-a",
        },
        marginalized_features=("solar_has_tracking",),
        output_mode=output_mode,
        target_name="shortfall",
        execution_mode=execution_mode,
    )


def test_tpm_query_request_defaults_to_production() -> None:
    request = TPMQueryRequest(
        decision_assignments={
            "battery_capacity_kwh": 8.0,
            "design_name": "baseline-a",
        },
        marginalized_features=("solar_has_tracking",),
    )

    assert request.output_mode == "conditional_probability"
    assert request.target_name == ""
    assert request.execution_mode == "production"


def test_tpm_query_request_rejects_implicit_or_unknown_fallback_modes() -> None:
    with pytest.raises(ValueError, match=r"execution_mode.*production.*fixture_replay"):
        TPMQueryRequest(execution_mode="automatic")


def test_explicit_fixture_replay_is_deterministic_and_identifies_its_source() -> None:
    artifact = load_tpm_artifact(_artifact_payload())
    request = _query_request()

    first = query_tpm_artifact(artifact, request)
    second = query_tpm_artifact(artifact, request)

    assert first == second
    assert first["source"] == "empirical_fixture"
    assert first["target_name"] == "shortfall"
    assert first["resolved_target_name"] == "shortfall_exceeds_threshold"
    assert first["output_mode"] == "conditional_probability"
    assert first["marginalized_features"] == ("solar_has_tracking",)
    assert 0.0 <= first["value"] <= 1.0


def test_production_mode_does_not_automatically_use_empirical_fixture_data() -> None:
    artifact = load_tpm_artifact(_artifact_payload(execution_mode="production"))

    with pytest.raises(
        RuntimeError,
        match=r"(?i)production.*spflow.*payload|payload.*required",
    ):
        query_tpm_artifact(artifact, _query_request(execution_mode="production"))


def test_production_mode_does_not_return_metadata_only_fallback() -> None:
    payload = _artifact_payload(execution_mode="production")
    payload["provenance"] = {}
    artifact = load_tpm_artifact(payload)

    with pytest.raises(
        RuntimeError,
        match=r"(?i)production.*spflow.*payload|payload.*required",
    ):
        query_tpm_artifact(artifact, _query_request(execution_mode="production"))


def test_query_rejects_request_and_artifact_execution_mode_mismatch() -> None:
    artifact = load_tpm_artifact(_artifact_payload(execution_mode="fixture_replay"))

    with pytest.raises(ValueError, match=r"execution_mode.*fixture_replay.*production"):
        query_tpm_artifact(artifact, _query_request(execution_mode="production"))


def test_query_tpm_artifact_rejects_missing_required_decision_feature() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    with pytest.raises(ValueError, match="required decision feature|design_name"):
        query_tpm_artifact(
            artifact,
            TPMQueryRequest(
                decision_assignments={"battery_capacity_kwh": 8.0},
                marginalized_features=("solar_has_tracking",),
                execution_mode="fixture_replay",
            ),
        )


def test_query_tpm_artifact_rejects_incompatible_target_requests() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    with pytest.raises(ValueError, match="target|shortfall|unsupported"):
        query_tpm_artifact(
            artifact,
            TPMQueryRequest(
                decision_assignments={
                    "battery_capacity_kwh": 8.0,
                    "design_name": "baseline-a",
                },
                target_name="blackout_probability",
                execution_mode="fixture_replay",
            ),
        )


def test_fixture_replay_supports_log_likelihood_output() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    result = query_tpm_artifact(
        artifact,
        _query_request(output_mode="log_likelihood"),
    )

    assert result["source"] == "empirical_fixture"
    assert result["output_mode"] == "log_likelihood"
    assert isinstance(result["value"], float)


def test_fixture_replay_uses_query_tolerance_for_zero_match_log_likelihood() -> None:
    payload = _artifact_payload()
    payload["approximation_metadata"] = {
        **dict(payload["approximation_metadata"]),
        "query_numeric_tolerance": 1e-6,
    }
    artifact = load_tpm_artifact(payload)

    result = query_tpm_artifact(
        artifact,
        TPMQueryRequest(
            decision_assignments={
                "battery_capacity_kwh": 20.0,
                "design_name": "baseline-a",
            },
            marginalized_features=("solar_has_tracking",),
            output_mode="log_likelihood",
            execution_mode="fixture_replay",
        ),
    )

    assert result["source"] == "empirical_fixture"
    assert result["matched_row_count"] == 0
    assert result["value"] == pytest.approx(math.log(1e-6))
