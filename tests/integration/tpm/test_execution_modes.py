"""Integration contracts for explicit production and fixture-replay execution."""

from __future__ import annotations

import pytest

from tpm.artifact import load_tpm_artifact
from tpm.query import TPMQueryRequest, query_tpm_artifact
from tests.integration.planning.fixture_utils import (
    TPM_ARTIFACT_FIXTURE_PATH,
    TPM_QUERY_FIXTURE_PATH,
    load_planning_fixture,
)


def _request_from_fixture(*, execution_mode: str) -> TPMQueryRequest:
    payload = load_planning_fixture(TPM_QUERY_FIXTURE_PATH)["query_request"]
    return TPMQueryRequest(
        decision_assignments=payload["decision_assignments"],
        marginalized_features=tuple(payload["marginalized_features"]),
        output_mode=payload["output_mode"],
        target_name=payload["target_name"],
        execution_mode=execution_mode,
    )


def test_explicit_fixture_replay_is_deterministic_and_matches_committed_evidence() -> None:
    artifact = load_tpm_artifact(TPM_ARTIFACT_FIXTURE_PATH)
    request = _request_from_fixture(execution_mode="fixture_replay")
    expected = dict(load_planning_fixture(TPM_QUERY_FIXTURE_PATH)["expected_result"])
    expected["marginalized_features"] = tuple(expected["marginalized_features"])

    first = query_tpm_artifact(artifact, request)
    second = query_tpm_artifact(artifact, request)

    assert first == second
    assert first == expected
    assert first["source"] == "empirical_fixture"


def test_production_mode_fails_without_a_valid_current_model_payload() -> None:
    payload = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)
    payload["execution_mode"] = "production"
    payload["spn_payload"] = {
        "locator": "sidecars/missing-current-spflow-model.pt",
        "serialization": "spflow-model-sidecar",
    }
    payload["spn_payload_format"] = "spflow-model-sidecar"
    artifact = load_tpm_artifact(payload)

    with pytest.raises(
        RuntimeError,
        match=r"(?i)production.*current.*spflow.*payload|valid.*payload.*required",
    ):
        query_tpm_artifact(
            artifact,
            _request_from_fixture(execution_mode="production"),
        )


def test_production_mode_never_falls_back_to_committed_empirical_rows() -> None:
    payload = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)
    payload["execution_mode"] = "production"
    artifact = load_tpm_artifact(payload)

    with pytest.raises(RuntimeError, match=r"(?i)production.*payload"):
        query_tpm_artifact(
            artifact,
            _request_from_fixture(execution_mode="production"),
        )
