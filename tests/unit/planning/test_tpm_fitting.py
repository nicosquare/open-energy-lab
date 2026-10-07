"""Unit coverage for TPM artifact fitting and lazy SPFlow loading."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from open_energy_lab.planning import load_planning_dataset
import tpm.fit as fit_module
from tpm.artifact import load_tpm_artifact
from tpm.domains import TPMFeatureDomain
from open_energy_lab.planning import fit_tpm_artifact, fit_tpm_artifact_from_study_manifest
from tpm.fit import (
    TPMArtifactBuildRequest,
    TPMFitConfig,
    fit_tpm_artifact_from_rows,
)
from tpm.spflow_backend import load_spflow_payload, stabilize_spflow_leaf_parameters
from tests.integration.planning.fixture_utils import PLANNING_DATASET_ARTIFACT_FIXTURE_PATH


def _planning_dataset():
    return load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)


def test_fit_tpm_artifact_persists_training_configuration(
    tmp_path: Path,
) -> None:
    dataset = _planning_dataset()
    artifact_path = tmp_path / "tpm-artifact-v1.json"

    artifact = fit_tpm_artifact(
        dataset,
        output_path=artifact_path,
        fit_config=TPMFitConfig(
            training_random_seed=97,
            notes=("fixture-backed-fit",),
        ),
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
    assert payload["query_strategy"] == "spflow"
    assert payload["model"] is not None


def test_fit_tpm_artifact_fails_lazily_when_spflow_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_path = tmp_path / "should-not-exist.json"

    def _missing_spflow():
        raise ModuleNotFoundError("No module named 'spflow'")

    monkeypatch.setattr(fit_module, "require_spflow_backend", _missing_spflow)

    with pytest.raises(ModuleNotFoundError, match="spflow"):
        fit_tpm_artifact(_planning_dataset(), output_path=artifact_path)

    assert not artifact_path.exists()


def test_fit_tpm_artifact_preserves_dataset_source_path_for_downstream_planning(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "planning-dataset.json"
    artifact_path = tmp_path / "tpm-artifact-v1.json"

    _planning_dataset().write_json(dataset_path)
    reloaded = fit_tpm_artifact(
        dataset_path,
        output_path=artifact_path,
    )

    assert reloaded.provenance["training_dataset_path"] == dataset_path.as_posix()
    assert reloaded.provenance["training_dataset_fixture_path"] == dataset_path.as_posix()
    assert reloaded.provenance["dataset_fixture_path"] == dataset_path.as_posix()


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
    )

    feature_schema = {
        entry["feature_name"]: entry for entry in artifact.feature_schema
    }
    assert feature_schema["loss_event"]["feature_role"] == "target"
    assert feature_schema["loss_event"]["feature_type"] == "binary"
    assert feature_schema["loss_event"]["discrete_values"] == [0.0, 1.0]
    assert feature_schema["loss_event"]["ordering"] == [0.0, 1.0]


def test_rdc_partition_guard_treats_an_empty_spectrum_as_independent_features(
    monkeypatch,
) -> None:
    import torch

    learn_module = importlib.import_module("spflow.learn.learn_spn")

    def _empty_spectrum_failure(_data, **_kwargs):
        raise RuntimeError(
            "max(): Expected reduction dim to be specified for input.numel() == 0"
        )

    monkeypatch.setattr(learn_module, "partition_by_rdc", _empty_spectrum_failure)
    partition_ids = fit_module.partition_by_rdc_with_degenerate_fallback(
        torch.ones((20, 4), dtype=torch.float64)
    )

    assert partition_ids.tolist() == [0, 1, 2, 3]


def test_rdc_partition_guard_does_not_hide_unrelated_runtime_errors(monkeypatch) -> None:
    import torch

    learn_module = importlib.import_module("spflow.learn.learn_spn")

    def _unrelated_failure(_data, **_kwargs):
        raise RuntimeError("unexpected partition failure")

    monkeypatch.setattr(learn_module, "partition_by_rdc", _unrelated_failure)

    with pytest.raises(RuntimeError, match="unexpected partition failure"):
        fit_module.partition_by_rdc_with_degenerate_fallback(
            torch.ones((20, 4), dtype=torch.float64)
        )


def test_kmeans_guard_forces_progress_when_backend_returns_one_cluster(monkeypatch) -> None:
    import torch

    learn_module = importlib.import_module("spflow.learn.learn_spn")
    monkeypatch.setattr(
        learn_module,
        "cluster_by_kmeans",
        lambda data, **_kwargs: torch.zeros(data.shape[0], dtype=torch.int),
    )

    labels = fit_module.cluster_by_kmeans_with_degenerate_fallback(
        torch.ones((10, 3), dtype=torch.float64),
        n_clusters=2,
    )

    assert labels.tolist() == [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]


def test_leaf_parameter_stabilization_keeps_constant_binary_slices_finite() -> None:
    import torch
    from spflow.meta.data import Scope
    from spflow.modules.leaves import Bernoulli, Normal

    leaf = Bernoulli(scope=Scope(0), probs=torch.zeros((1, 1, 1)))
    normal = Normal(
        scope=Scope(1),
        loc=torch.zeros((1, 1, 1)),
        scale=torch.ones((1, 1, 1)),
    )
    normal.scale = torch.full((1, 1, 1), float("nan"))
    root = torch.nn.ModuleList((leaf, normal))
    stabilize_spflow_leaf_parameters(root)

    assert bool(torch.isfinite(leaf.logits).all())
    assert 0.0 < float(leaf.probs.detach().reshape(-1)[0]) < 1.0
    assert bool(torch.isfinite(normal.scale).all())
    assert bool((normal.scale > 0.0).all())


def _declared_generic_rows() -> tuple[dict[str, object], ...]:
    return (
        {
            "x": 60.0,
            "tariff_plan": "flat",
            "demand": 72.0,
        },
        {
            "x": 140.0,
            "tariff_plan": "peak",
            "demand": 134.0,
        },
    )


def _declared_generic_domains() -> dict[str, TPMFeatureDomain]:
    return {
        "x": TPMFeatureDomain(
            feature_name="x",
            feature_kind="continuous",
            purpose="decision-domain",
            shape="finite",
            lower=40.0,
            upper=160.0,
        ),
        "demand": TPMFeatureDomain(
            feature_name="demand",
            feature_kind="continuous",
            purpose="distribution-support",
            shape="unbounded",
        ),
    }


def _declared_generic_request(
    *,
    feature_domains: dict[str, TPMFeatureDomain] | None = None,
) -> TPMArtifactBuildRequest:
    return TPMArtifactBuildRequest(
        artifact_id="declared-generic-artifact",
        dataset_reference="declared-generic-dataset",
        decision_features=("x", "tariff_plan"),
        target_name="demand",
        target_threshold=100.0,
        feature_domains=(
            _declared_generic_domains()
            if feature_domains is None
            else feature_domains
        ),
    )


def test_build_request_preserves_one_shared_feature_domain_mapping_type() -> None:
    request = _declared_generic_request()

    assert tuple(request.feature_domains) == ("x", "demand")
    assert request.feature_domains["x"].shape == "finite"
    assert request.feature_domains["demand"].shape == "unbounded"


def test_generic_fit_uses_declarations_and_classifies_omitted_features(
    tmp_path: Path,
) -> None:
    artifact = fit_tpm_artifact_from_rows(
        _declared_generic_rows(),
        build_request=_declared_generic_request(),
        output_path=tmp_path / "declared-generic.json",
    )
    specs = {spec.feature_name: spec for spec in artifact.feature_specs}

    assert artifact.schema_version == "v3"
    assert specs["x"].mathematical_domain.shape == "finite"
    assert specs["x"].bounds == (40.0, 160.0)
    assert specs["demand"].mathematical_domain.shape == "unbounded"
    assert specs["demand"].normalization.kind == "identity"
    assert specs["tariff_plan"].mathematical_domain.shape == "unknown"
    assert specs["tariff_plan"].mathematical_domain.origin == "omitted"
    assert specs["tariff_plan"].training_support.observed_values == ("flat", "peak")
    assert specs["tariff_plan"].ordering == ("flat", "peak")
    assert specs["tariff_plan"].normalization.origin == "legacy-inferred"
    assert "unobserved" not in specs["tariff_plan"].ordering

    reloaded = load_tpm_artifact(artifact.source_path)
    reloaded_tariff = {
        spec.feature_name: spec for spec in reloaded.feature_specs
    }["tariff_plan"]
    assert reloaded.schema_version == "v3"
    assert reloaded_tariff.mathematical_domain.origin == "omitted"
    assert reloaded_tariff.training_support.observed_values == ("flat", "peak")


def test_planning_fit_accepts_optional_feature_domains_without_reading_dataset_metadata_as_domains(
    tmp_path: Path,
) -> None:
    artifact = fit_tpm_artifact(
        _planning_dataset(),
        output_path=tmp_path / "declared-planning.json",
        feature_domains={
            "battery_capacity_kwh": TPMFeatureDomain(
                feature_name="battery_capacity_kwh",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="finite",
                lower=0.0,
                upper=20.0,
            )
        },
    )
    specs = {spec.feature_name: spec for spec in artifact.feature_specs}

    assert artifact.schema_version == "v3"
    assert specs["battery_capacity_kwh"].mathematical_domain.shape == "finite"
    assert specs["solar_capacity_kw"].mathematical_domain.shape == "unknown"
    assert specs["solar_capacity_kw"].mathematical_domain.origin == "omitted"


def test_all_public_fit_carriers_expose_keyword_only_feature_domains() -> None:
    assert "feature_domains" in inspect.signature(fit_tpm_artifact).parameters
    study_parameter = inspect.signature(
        fit_tpm_artifact_from_study_manifest
    ).parameters["feature_domains"]

    assert study_parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert study_parameter.default is None


def test_build_request_rejects_mapping_key_owned_by_another_feature() -> None:
    with pytest.raises(ValueError, match="mapping key|feature_name"):
        _declared_generic_request(
            feature_domains={"other": _declared_generic_domains()["x"]}
        )


@pytest.mark.parametrize(
    "feature_domains",
    [
        {
            "unknown": TPMFeatureDomain(
                feature_name="unknown",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="finite",
                lower=0.0,
                upper=1.0,
            )
        },
        {
            "demand": TPMFeatureDomain(
                feature_name="demand",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="finite",
                lower=0.0,
                upper=200.0,
            )
        },
    ],
)
def test_generic_fit_rejects_unknown_or_role_ambiguous_declarations_before_backend_use(
    feature_domains: dict[str, TPMFeatureDomain],
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        fit_module,
        "_fit_and_persist_spflow_model",
        lambda *_args, **_kwargs: pytest.fail("backend must not be invoked"),
    )

    with pytest.raises(ValueError, match="unknown|unselected|purpose|role"):
        fit_tpm_artifact_from_rows(
            _declared_generic_rows(),
            build_request=_declared_generic_request(feature_domains=feature_domains),
            output_path=tmp_path / "must-not-publish.json",
        )


@pytest.mark.parametrize(
    "feature_domains",
    [
        {
            "x": TPMFeatureDomain(
                feature_name="x",
                feature_kind="continuous",
                purpose="decision-domain",
                shape="finite",
                lower=80.0,
                upper=160.0,
            ),
            "demand": _declared_generic_domains()["demand"],
        },
        {
            "x": _declared_generic_domains()["x"],
            "demand": TPMFeatureDomain(
                feature_name="demand",
                feature_kind="continuous",
                purpose="distribution-support",
                shape="finite",
                lower=0.0,
                upper=100.0,
            ),
        },
    ],
)
def test_invalid_declared_physical_rows_fail_before_backend_and_publish_nothing(
    feature_domains: dict[str, TPMFeatureDomain],
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "invalid-declared-fit.json"
    backend_calls: list[object] = []

    def _unexpected_backend(*args, **kwargs):
        backend_calls.append((args, kwargs))
        pytest.fail("backend must not be invoked for invalid physical evidence")

    monkeypatch.setattr(
        fit_module,
        "_fit_and_persist_spflow_model",
        _unexpected_backend,
    )

    with pytest.raises(ValueError, match="decision-domain|distribution-support|outside"):
        fit_tpm_artifact_from_rows(
            _declared_generic_rows(),
            build_request=_declared_generic_request(feature_domains=feature_domains),
            output_path=output_path,
        )

    assert backend_calls == []
    assert not output_path.exists()
    assert not output_path.with_name(
        f"{output_path.stem}.spn_payload.pkl"
    ).exists()
