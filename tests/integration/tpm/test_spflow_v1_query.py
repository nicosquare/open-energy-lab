"""Required SPFlow 1.1 likelihood, marginalization, and query contracts."""

from __future__ import annotations

from time import perf_counter

import pytest

import tpm.features as features_module
import tpm.query as query_module
from tpm import load_tpm_artifact
from tpm.query import TPMQueryRequest, query_tpm_artifact
from tests.integration.tpm.spflow_v1_test_support import (
    QUERY_BUDGET_SECONDS,
    fit_real_artifact,
    load_current_model_payload,
    normalized_training_tensor,
    valid_query_request,
)
from tests.integration.planning.fixture_utils import (
    TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH,
)


@pytest.fixture(scope="module")
def fitted_artifact(tmp_path_factory):
    artifact, _, _ = fit_real_artifact(tmp_path_factory.mktemp("spflow-v1-query"))
    return artifact


def test_nan_evidence_matches_structural_removal_and_reduces_tensor_output(
    fitted_artifact,
) -> None:
    import torch

    payload = load_current_model_payload(fitted_artifact)
    model = payload["model"]
    evidence = normalized_training_tensor(fitted_artifact)[0:1].clone()
    ambient_index = tuple(spec.feature_name for spec in fitted_artifact.feature_specs).index(
        "ambient_temperature_c"
    )
    evidence[0, ambient_index] = torch.nan

    native_output = model.log_likelihood(evidence)
    reduced = getattr(query_module, "reduce_spflow_log_likelihood")(native_output)
    structurally_marginalized = model.marginalize([ambient_index])
    structural_output = structurally_marginalized.log_likelihood(evidence)
    structural_reduced = getattr(query_module, "reduce_spflow_log_likelihood")(
        structural_output
    )

    assert isinstance(native_output, torch.Tensor)
    assert native_output.shape == (1, 1, 1, 1)
    assert isinstance(reduced, float)
    assert torch.isfinite(native_output).all()
    assert ambient_index not in structurally_marginalized.scope.query
    assert reduced == pytest.approx(structural_reduced, abs=1e-9, rel=0.0)


def test_production_query_returns_conditional_probability_within_budget(
    fitted_artifact,
) -> None:
    started = perf_counter()
    result = query_tpm_artifact(fitted_artifact, valid_query_request())
    elapsed = perf_counter() - started

    assert elapsed < QUERY_BUDGET_SECONDS
    assert result["source"] == "spflow_backend"
    assert result["output_mode"] == "conditional_probability"
    assert result["target_name"] == "shortfall"
    assert result["resolved_target_name"] == "shortfall_event"
    assert 0.0 <= result["conditional_probability"] <= 1.0


def test_committed_production_v2_query_preserves_legacy_numeric_behavior() -> None:
    artifact = load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH)
    request = valid_query_request()

    first = query_tpm_artifact(artifact, request)
    second = query_tpm_artifact(
        load_tpm_artifact(TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH),
        request,
    )

    assert artifact.schema_version == "v2"
    assert first["source"] == "spflow_backend"
    assert first["conditional_probability"] == pytest.approx(
        second["conditional_probability"],
        abs=1e-12,
        rel=0.0,
    )


@pytest.mark.parametrize(
    ("assignments", "expected_feature", "expected_reason"),
    (
        (
            {"battery_capacity_kwh": 4.0, "design_class": "balanced"},
            "solar_enabled",
            "missing",
        ),
        (
            {
                "battery_capacity_kwh": 100.0,
                "solar_enabled": 1,
                "design_class": "balanced",
            },
            "battery_capacity_kwh",
            "out_of_bounds",
        ),
        (
            {
                "battery_capacity_kwh": 4.0,
                "solar_enabled": 1,
                "design_class": "unsupported",
            },
            "design_class",
            "unseen_category",
        ),
        (
            {
                "battery_capacity_kwh": 4.0,
                "solar_enabled": 2,
                "design_class": "balanced",
            },
            "solar_enabled",
            "invalid_binary",
        ),
    ),
)
def test_invalid_query_values_fail_before_spflow_evaluation(
    fitted_artifact,
    monkeypatch,
    assignments,
    expected_feature,
    expected_reason,
) -> None:
    validation_error = getattr(features_module, "TPMFeatureValidationError")

    def _unexpected_backend_call(*args, **kwargs):
        raise AssertionError("SPFlow evaluation must not run for invalid feature values")

    monkeypatch.setattr(query_module, "evaluate_spflow_query", _unexpected_backend_call)

    with pytest.raises(validation_error) as exc_info:
        query_tpm_artifact(
            fitted_artifact,
            TPMQueryRequest(
                decision_assignments=assignments,
                marginalized_features=("ambient_temperature_c",),
                target_name="shortfall",
                execution_mode="production",
            ),
        )

    details = exc_info.value.to_dict()
    assert details["feature_name"] == expected_feature
    assert details["reason"] == expected_reason
    assert details["expected_domain"]
