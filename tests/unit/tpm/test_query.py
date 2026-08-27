"""Unit contracts for explicit TPM production and fixture-replay queries."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import open_energy_lab.tpm.query as query_module
from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.data import normalize_training_data
from open_energy_lab.tpm.domains import TPMFeatureDomain
from open_energy_lab.tpm.features import (
    TPMFeatureValidationError,
    validate_spflow_feature_assignments,
)
from open_energy_lab.tpm.fit import TPMArtifactBuildRequest, fit_tpm_artifact_from_rows
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


def _stub_production_result(*_args, **_kwargs) -> dict[str, object]:
    return {
        "matched_row_count": 0,
        "total_row_count": 2,
        "source": "spflow_backend",
        "value": 0.5,
        "resolved_target_name": "demand_event",
    }


def _fit_scalar_query_artifact(
    tmp_path: Path,
    *,
    domain: TPMFeatureDomain,
    x_values: tuple[float, float],
):
    return fit_tpm_artifact_from_rows(
        (
            {"x": x_values[0], "demand": 72.0},
            {"x": x_values[1], "demand": 134.0},
        ),
        build_request=TPMArtifactBuildRequest(
            artifact_id=f"query-{domain.shape}",
            dataset_reference=f"query-{domain.shape}-rows",
            decision_features=("x",),
            target_name="demand",
            target_threshold=100.0,
            feature_domains={
                "x": domain,
                "demand": TPMFeatureDomain(
                    feature_name="demand",
                    feature_kind="continuous",
                    purpose="distribution-support",
                    shape="unbounded",
                ),
            },
        ),
        output_path=tmp_path / f"query-{domain.shape}.json",
        spflow_backend=SimpleNamespace(
            __name__="spflow.testing",
            __version__="0.test",
        ),
    )


@pytest.mark.parametrize(
    ("shape", "lower", "upper", "x_values", "valid_value", "invalid_value"),
    [
        ("finite", 40.0, 160.0, (60.0, 140.0), 40.0, math.nextafter(40.0, -math.inf)),
        ("finite", 100.0, 100.0, (100.0, 100.0), 100.0, math.nextafter(100.0, math.inf)),
        ("lower-bounded", 0.0, None, (10.0, 20.0), 0.0, math.nextafter(0.0, -math.inf)),
        ("upper-bounded", None, 100.0, (10.0, 20.0), 100.0, math.nextafter(100.0, math.inf)),
    ],
)
def test_native_query_accepts_declared_endpoints_outside_training_and_rejects_adjacent_values(
    shape: str,
    lower: float | None,
    upper: float | None,
    x_values: tuple[float, float],
    valid_value: float,
    invalid_value: float,
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = _fit_scalar_query_artifact(
        tmp_path,
        domain=TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape=shape,
            lower=lower,
            upper=upper,
        ),
        x_values=x_values,
    )
    monkeypatch.setattr(
        query_module,
        "_evaluate_current_spflow_query",
        _stub_production_result,
    )

    result = query_tpm_artifact(
        artifact,
        TPMQueryRequest(decision_assignments={"x": valid_value}),
    )

    assert result["value"] == pytest.approx(0.5)
    with pytest.raises(TPMFeatureValidationError) as exc_info:
        query_tpm_artifact(
            artifact,
            TPMQueryRequest(decision_assignments={"x": invalid_value}),
        )
    assert exc_info.value.reason == "decision_domain_violation"


def test_native_query_accepts_unobserved_declared_binary_and_category_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = fit_tpm_artifact_from_rows(
        (
            {
                "activation": "off",
                "service_tier": "economy",
                "demand": 72.0,
            },
            {
                "activation": "off",
                "service_tier": "standard",
                "demand": 134.0,
            },
        ),
        build_request=TPMArtifactBuildRequest(
            artifact_id="query-unobserved-discrete",
            dataset_reference="query-unobserved-discrete-rows",
            decision_features=("activation", "service_tier"),
            target_name="demand",
            target_threshold=100.0,
            feature_domains={
                "activation": TPMFeatureDomain(
                    feature_name="activation",
                    feature_kind="binary",
                    purpose="decision-domain",
                    values=("off", "on"),
                ),
                "service_tier": TPMFeatureDomain(
                    feature_name="service_tier",
                    feature_kind="categorical",
                    purpose="decision-domain",
                    values=("economy", "standard", "priority"),
                ),
                "demand": TPMFeatureDomain(
                    feature_name="demand",
                    feature_kind="continuous",
                    purpose="distribution-support",
                    shape="unbounded",
                ),
            },
        ),
        output_path=tmp_path / "query-unobserved-discrete.json",
        spflow_backend=SimpleNamespace(
            __name__="spflow.testing",
            __version__="0.test",
        ),
    )
    monkeypatch.setattr(
        query_module,
        "_evaluate_current_spflow_query",
        _stub_production_result,
    )

    result = query_tpm_artifact(
        artifact,
        TPMQueryRequest(
            decision_assignments={
                "activation": "on",
                "service_tier": "priority",
            }
        ),
    )

    assert result["value"] == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("invalid_value", "expected_reason"),
    [
        (math.inf, "non_finite"),
        (math.nextafter(40.0, -math.inf), "decision_domain_violation"),
    ],
)
def test_native_query_reports_source_specific_declared_domain_failures(
    invalid_value: float,
    expected_reason: str,
    tmp_path: Path,
) -> None:
    artifact = _fit_scalar_query_artifact(
        tmp_path,
        domain=TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape="finite",
            lower=40.0,
            upper=160.0,
        ),
        x_values=(60.0, 140.0),
    )

    with pytest.raises(TPMFeatureValidationError) as exc_info:
        query_tpm_artifact(
            artifact,
            TPMQueryRequest(decision_assignments={"x": invalid_value}),
        )

    assert exc_info.value.reason == expected_reason
    assert exc_info.value.semantic_source == "decision-domain"


def test_assignment_diagnostics_distinguish_support_discrete_and_legacy_sources() -> None:
    distribution_spec = normalize_training_data(
        ({"demand": 20.0}, {"demand": 80.0}),
        feature_domains={
            "demand": TPMFeatureDomain(
                feature_name="demand",
                feature_kind="continuous",
                purpose="distribution-support",
                shape="finite",
                lower=0.0,
                upper=100.0,
            )
        },
        feature_roles={"demand": "metric_target"},
    ).feature_schema[0]
    discrete_spec = normalize_training_data(
        ({"activation": "off"}, {"activation": "off"}),
        feature_domains={
            "activation": TPMFeatureDomain(
                feature_name="activation",
                feature_kind="binary",
                purpose="decision-domain",
                values=("off", "on"),
            )
        },
        feature_roles={"activation": "decision"},
    ).feature_schema[0]
    legacy_spec = normalize_training_data(
        ({"x": 60.0}, {"x": 140.0}),
        feature_roles={"x": "decision"},
    ).feature_schema[0]

    cases = (
        (
            distribution_spec,
            {"demand": 101.0},
            "distribution_support_violation",
            "distribution-support",
        ),
        (
            discrete_spec,
            {"activation": "invalid"},
            "declared_discrete_violation",
            "decision-domain",
        ),
        (legacy_spec, {"x": 160.0}, "out_of_bounds", "legacy-inferred"),
    )
    for spec, assignments, reason, semantic_source in cases:
        with pytest.raises(TPMFeatureValidationError) as exc_info:
            validate_spflow_feature_assignments((spec,), assignments)
        assert exc_info.value.reason == reason
        assert exc_info.value.semantic_source == semantic_source


def test_explicit_unknown_native_assignment_accepts_any_finite_physical_value() -> None:
    spec = normalize_training_data(
        ({"x": 60.0}, {"x": 140.0}),
        feature_domains={
            "x": TPMFeatureDomain(
                feature_name="x",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="unknown",
            )
        },
        feature_roles={"x": "decision"},
    ).feature_schema[0]

    validate_spflow_feature_assignments((spec,), {"x": -1_000_000.0})
    assert spec.normalize_value(-1_000_000.0) == pytest.approx(-1_000_000.0)
