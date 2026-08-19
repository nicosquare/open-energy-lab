"""Unit coverage for TPM artifact fitting and lazy SPFlow loading."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from open_energy_lab.planning import load_planning_dataset
import open_energy_lab.tpm.optional_spflow as optional_spflow_module
from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.fit import (
    TPMArtifactBuildRequest,
    TPMFitConfig,
    fit_tpm_artifact,
    fit_tpm_artifact_from_rows,
)
from open_energy_lab.tpm.optional_spflow import (
    SPFlowDependencyUnavailableError,
    load_spflow_payload,
)
from tests.integration.planning.fixture_utils import PLANNING_DATASET_ARTIFACT_FIXTURE_PATH


def _planning_dataset():
    return load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)


class _FakeAdapter(SimpleNamespace):
    @property
    def adapter_name(self) -> str:
        return "fake-adapter"

    @property
    def backend_name(self) -> str:
        return "fake-spflow"

    @property
    def backend_version(self) -> str:
        return "0.test"

    @property
    def backend_module(self) -> object:
        return self

    def detect_capabilities(self) -> dict[str, object]:
        return {
            "installed_backend_module": self.backend_name,
            "installed_backend_version": self.backend_version,
            "backend_adapter_name": self.adapter_name,
            "legacy_spn_api_available": True,
            "supports_real_spn_training": True,
            "supports_real_spn_query": True,
            "supports_spn_mip_serialization": True,
            "fallback_query_strategy": None,
            "reason": "fake adapter available",
        }

    def fit_runtime_payload(self, runtime_payload):
        payload = dict(runtime_payload)
        payload["query_strategy"] = "table"
        payload["adapter_marker"] = "custom-fit"
        return payload


def test_fit_tpm_artifact_persists_training_configuration_with_injected_backend(
    tmp_path: Path,
) -> None:
    dataset = _planning_dataset()
    artifact_path = tmp_path / "tpm-artifact-v1.json"
    fake_backend = SimpleNamespace(__name__="spflow.testing", __version__="0.test")

    artifact = fit_tpm_artifact(
        dataset,
        output_path=artifact_path,
        fit_config=TPMFitConfig(
            training_random_seed=97,
            notes=("fixture-backed-fit",),
        ),
        spflow_backend=fake_backend,
    )
    reloaded = load_tpm_artifact(artifact_path)

    assert artifact_path.is_file()
    assert artifact.artifact_id == "tpm-artifact:planning-dataset-export-integration"
    assert reloaded.fit_configuration["backend_name"] == "spflow"
    assert reloaded.fit_configuration["training_random_seed"] == 97
    assert reloaded.spn_payload_format == "pickle-path"
    assert reloaded.spn_payload["backend"] == "spflow"
    assert reloaded.spn_payload["serialization"] == "pickle"
    assert reloaded.query_configuration["required_decision_features"] == [
        "battery_capacity_kwh",
        "solar_capacity_kw",
        "design_name",
    ]
    assert (artifact_path.parent / reloaded.spn_payload["locator"]).is_file()

    feature_roles = {
        entry["feature_name"]: entry["feature_role"] for entry in reloaded.feature_schema
    }
    assert feature_roles["battery_capacity_kwh"] == "decision"
    assert feature_roles["ghi_0"] == "context"
    assert feature_roles["shortfall"] == "metric_target"
    assert feature_roles["shortfall_exceeds_threshold"] == "target"

    payload = load_spflow_payload(reloaded)
    assert payload is not None
    assert "backend_capabilities" in payload


def test_fit_tpm_artifact_fails_lazily_when_spflow_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_path = tmp_path / "should-not-exist.json"

    def _raise_dependency_error(_backend=None):
        raise SPFlowDependencyUnavailableError("required 'spflow' dependency missing")

    monkeypatch.setattr(
        optional_spflow_module,
        "_resolve_spflow_backend_adapter",
        _raise_dependency_error,
    )

    with pytest.raises(SPFlowDependencyUnavailableError, match="required 'spflow' dependency"):
        fit_tpm_artifact(_planning_dataset(), output_path=artifact_path)

    assert not artifact_path.exists()


def test_fit_tpm_artifact_preserves_dataset_source_path_for_downstream_planning(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "planning-dataset.json"
    artifact_path = tmp_path / "tpm-artifact-v1.json"
    fake_backend = SimpleNamespace(__name__="spflow.testing", __version__="0.test")

    _planning_dataset().write_json(dataset_path)
    reloaded = fit_tpm_artifact(
        dataset_path,
        output_path=artifact_path,
        spflow_backend=fake_backend,
    )

    assert reloaded.provenance["training_dataset_path"] == dataset_path.as_posix()
    assert reloaded.provenance["training_dataset_fixture_path"] == dataset_path.as_posix()
    assert reloaded.provenance["dataset_fixture_path"] == dataset_path.as_posix()


def test_fit_tpm_artifact_can_use_an_injected_backend_adapter(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "tpm-artifact-v1.json"

    fit_tpm_artifact(
        _planning_dataset(),
        output_path=artifact_path,
        spflow_backend=_FakeAdapter(),
    )
    reloaded = load_tpm_artifact(artifact_path)
    payload = load_spflow_payload(reloaded)

    assert payload is not None
    assert payload["backend_adapter_name"] == "fake-adapter"
    assert payload["backend_capabilities"]["backend_adapter_name"] == "fake-adapter"
    assert payload["adapter_marker"] == "custom-fit"


def test_fit_tpm_artifact_from_rows_derives_a_binary_event_target_for_generic_data(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "generic-tpm-artifact.json"

    artifact = fit_tpm_artifact_from_rows(
        (
            {
                "generator_size_kw": 2.0,
                "tariff_plan": "flat",
                "ambient_band": "low",
                "loss_ratio": 0.01,
            },
            {
                "generator_size_kw": 6.0,
                "tariff_plan": "peak",
                "ambient_band": "high",
                "loss_ratio": 0.12,
            },
        ),
        output_path=artifact_path,
        build_request=TPMArtifactBuildRequest(
            artifact_id="generic-risk-artifact",
            dataset_reference="generic-risk-dataset",
            decision_features=("generator_size_kw", "tariff_plan"),
            target_name="loss_ratio",
            target_threshold=0.05,
        ),
        spflow_backend=SimpleNamespace(__name__="spflow.testing", __version__="0.test"),
    )

    assert artifact.artifact_id == "generic-risk-artifact"
    assert artifact.dataset_reference == "generic-risk-dataset"
    assert artifact.target_definition["target_name"] == "loss_ratio"
    assert artifact.target_definition["event_target_name"] == "loss_ratio_event"
    assert artifact.target_definition["threshold_default"] == pytest.approx(0.05)
    assert artifact.target_definition["event_threshold_source"] == "threshold_default"
    assert artifact.query_configuration["required_decision_features"] == [
        "generator_size_kw",
        "tariff_plan",
    ]

    feature_roles = {
        entry["feature_name"]: entry["feature_role"] for entry in artifact.feature_schema
    }
    assert feature_roles == {
        "generator_size_kw": "decision",
        "tariff_plan": "decision",
        "ambient_band": "context",
        "loss_ratio": "metric_target",
        "loss_ratio_event": "target",
    }

    payload = load_spflow_payload(load_tpm_artifact(artifact_path))
    assert payload is not None
    assert payload["raw_rows"][0]["loss_ratio_event"] == 0
    assert payload["raw_rows"][1]["loss_ratio_event"] == 1


def test_fit_tpm_artifact_from_rows_keeps_constant_event_targets_binary(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "constant-event-artifact.json"

    artifact = fit_tpm_artifact_from_rows(
        (
            {
                "generator_size_kw": 2.0,
                "tariff_plan": "flat",
                "loss_ratio": 0.01,
            },
            {
                "generator_size_kw": 6.0,
                "tariff_plan": "peak",
                "loss_ratio": 0.02,
            },
        ),
        output_path=artifact_path,
        build_request=TPMArtifactBuildRequest(
            artifact_id="constant-event-artifact",
            dataset_reference="constant-event-dataset",
            decision_features=("generator_size_kw", "tariff_plan"),
            target_name="loss_ratio",
            event_target_name="loss_event",
            target_threshold=0.05,
        ),
        spflow_backend=SimpleNamespace(__name__="spflow.testing", __version__="0.test"),
    )

    feature_schema = {
        entry["feature_name"]: entry for entry in artifact.feature_schema
    }
    assert feature_schema["loss_event"]["feature_role"] == "target"
    assert feature_schema["loss_event"]["feature_type"] == "binary"
    assert feature_schema["loss_event"]["discrete_values"] == [0.0, 1.0]
    assert feature_schema["loss_event"]["ordering"] == [0.0, 1.0]
