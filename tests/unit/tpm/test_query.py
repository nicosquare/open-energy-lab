"""Unit contracts for TPM query request validation and outputs."""

from __future__ import annotations

import math

import pytest

from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.query import TPMQueryRequest, query_tpm_artifact


def _artifact_payload() -> dict[str, object]:
    return {
        "artifact_id": "tpm-artifact-query-unit",
        "schema_version": "v1",
        "created_at": "2026-06-24T00:00:00Z",
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
        "spn_payload": {"payload_kind": "inline-json-placeholder"},
        "spn_payload_format": "json-inline",
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
            "tolerance": 1e-9,
        },
        "provenance": {
            "dataset_fixture_path": "tests/fixtures/tpm/planning_dataset_v1.json",
            "legacy_evidence_paths": [
                "legacy/old_tpm/src_py/tpm/spn/main.py",
            ],
        },
    }


def test_tpm_query_request_defaults_to_conditional_probability_and_artifact_target() -> None:
    request = TPMQueryRequest(
        decision_assignments={
            "battery_capacity_kwh": 8.0,
            "design_name": "baseline-a",
        },
        marginalized_features=("solar_has_tracking",),
    )

    assert request.decision_assignments == {
        "battery_capacity_kwh": 8.0,
        "design_name": "baseline-a",
    }
    assert request.marginalized_features == ("solar_has_tracking",)
    assert request.output_mode == "conditional_probability"
    assert request.target_name == ""


def test_query_tpm_artifact_supports_conditional_queries_with_marginalization() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    result = query_tpm_artifact(
        artifact,
        TPMQueryRequest(
            decision_assignments={
                "battery_capacity_kwh": 8.0,
                "design_name": "baseline-a",
            },
            marginalized_features=("solar_has_tracking",),
            output_mode="conditional_probability",
            target_name="shortfall",
        ),
    )

    assert result["target_name"] == "shortfall"
    assert result["resolved_target_name"] == "shortfall_exceeds_threshold"
    assert result["output_mode"] == "conditional_probability"
    assert result["marginalized_features"] == ("solar_has_tracking",)
    assert result["value"] >= 0.0
    assert result["value"] <= 1.0


def test_query_tpm_artifact_rejects_missing_required_decision_feature() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    with pytest.raises(ValueError, match="required decision feature|design_name"):
        query_tpm_artifact(
            artifact,
            TPMQueryRequest(
                decision_assignments={"battery_capacity_kwh": 8.0},
                marginalized_features=("solar_has_tracking",),
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
            ),
        )


def test_query_tpm_artifact_supports_log_likelihood_output() -> None:
    artifact = load_tpm_artifact(_artifact_payload())

    result = query_tpm_artifact(
        artifact,
        TPMQueryRequest(
            decision_assignments={
                "battery_capacity_kwh": 8.0,
                "design_name": "baseline-a",
            },
            marginalized_features=("solar_has_tracking",),
            output_mode="log_likelihood",
        ),
    )

    assert result["target_name"] == "shortfall"
    assert result["resolved_target_name"] == "shortfall_exceeds_threshold"
    assert result["output_mode"] == "log_likelihood"
    assert isinstance(result["value"], float)


def test_query_tpm_artifact_uses_piecewise_query_tolerance_for_zero_match_log_likelihood() -> None:
    payload = _artifact_payload()
    payload["approximation_metadata"] = {
        "approximation_kind": "piecewise",
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
        ),
    )

    assert result["matched_row_count"] == 0
    assert result["value"] == pytest.approx(math.log(1e-6))
