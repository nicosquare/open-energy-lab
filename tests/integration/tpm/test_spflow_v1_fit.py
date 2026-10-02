"""Required real SPFlow 1.1 structure-learning and repeatability contracts."""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from numbers import Real

import pytest

import tpm.fit as fit_module
from tests.integration.tpm.spflow_v1_test_support import (
    CANONICAL_SEED,
    FIT_BUDGET_SECONDS,
    ROBUSTNESS_SEEDS,
    fit_real_artifact,
    load_current_model_payload,
)


def _assert_nested_close(actual: object, expected: object) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        assert actual.keys() == expected.keys()
        for key in actual:
            _assert_nested_close(actual[key], expected[key])
        return
    if (
        isinstance(actual, Sequence)
        and isinstance(expected, Sequence)
        and not isinstance(actual, str | bytes)
        and not isinstance(expected, str | bytes)
    ):
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected, strict=True):
            _assert_nested_close(actual_item, expected_item)
        return
    if isinstance(actual, Real) and isinstance(expected, Real):
        assert float(actual) == pytest.approx(float(expected), abs=1e-9, rel=0.0)
        return
    assert actual == expected


def test_real_fit_uses_torch_and_typed_leaf_scopes(monkeypatch, tmp_path) -> None:
    import torch
    from spflow.modules.leaves import Bernoulli, Categorical, Normal

    learn_package = importlib.import_module("spflow.learn")
    learn_module = importlib.import_module("spflow.learn.learn_spn")
    real_learn_spn = learn_module.learn_spn
    captured: dict[str, object] = {}

    def _capturing_learn_spn(data, leaf_modules, *args, **kwargs):
        captured["data"] = data
        captured["leaf_modules"] = tuple(leaf_modules)
        captured["kwargs"] = dict(kwargs)
        return real_learn_spn(data, leaf_modules, *args, **kwargs)

    monkeypatch.setattr(learn_package, "learn_spn", _capturing_learn_spn)
    monkeypatch.setattr(learn_module, "learn_spn", _capturing_learn_spn)

    artifact, _, elapsed = fit_real_artifact(tmp_path, seed=CANONICAL_SEED)

    assert elapsed < FIT_BUDGET_SECONDS
    assert artifact.schema_version == "v3"
    assert artifact.backend_generation == "current-spflow"
    assert artifact.backend_api_version == "1.1.0"
    assert artifact.execution_mode == "production"

    tensor = captured["data"]
    assert isinstance(tensor, torch.Tensor)
    assert tensor.dtype == torch.float64
    assert tensor.device.type == "cpu"
    assert tensor.shape == (36, 6)
    assert callable(captured["kwargs"]["partitioning_method"])
    assert callable(captured["kwargs"]["clustering_method"])

    leaf_modules = captured["leaf_modules"]
    normal_scopes = {
        index for leaf in leaf_modules if isinstance(leaf, Normal) for index in leaf.scope.query
    }
    bernoulli_scopes = {
        index for leaf in leaf_modules if isinstance(leaf, Bernoulli) for index in leaf.scope.query
    }
    categorical_leaves = [leaf for leaf in leaf_modules if isinstance(leaf, Categorical)]

    assert normal_scopes == {0, 3, 4}
    assert bernoulli_scopes == {1, 5}
    assert len(categorical_leaves) == 1
    assert categorical_leaves[0].scope.query == (2,)
    assert categorical_leaves[0].K == 3

    payload = load_current_model_payload(artifact)
    assert payload["training_random_seed"] == CANONICAL_SEED
    assert payload["model"].scope.query == (0, 1, 2, 3, 4, 5)


def test_legacy_fit_configuration_is_translated_to_learn_spn() -> None:
    translate = getattr(fit_module, "translate_spflow_fit_configuration")

    translated = translate(
        {
            "threshold": 0.42,
            "min_features_slice": 2,
            "min_instances_slice": 12,
            "n_clusters": 3,
        }
    )

    assert translated == {
        "min_features_slice": 2,
        "min_instances_slice": 12,
        "partitioning_args": {"threshold": 0.42},
        "clustering_args": {"n_clusters": 3},
    }


def test_canonical_fit_is_repeatable_and_robustness_seeds_are_recorded(tmp_path) -> None:
    first, _, first_elapsed = fit_real_artifact(
        tmp_path,
        seed=CANONICAL_SEED,
        artifact_name="canonical-first",
    )
    second, _, second_elapsed = fit_real_artifact(
        tmp_path,
        seed=CANONICAL_SEED,
        artifact_name="canonical-second",
    )

    first_summary = first.fit_configuration["fit_summary"]
    second_summary = second.fit_configuration["fit_summary"]
    assert set(first_summary) == {"structure", "parameters", "likelihood"}
    _assert_nested_close(first_summary, second_summary)
    assert first_elapsed < FIT_BUDGET_SECONDS
    assert second_elapsed < FIT_BUDGET_SECONDS

    for seed in ROBUSTNESS_SEEDS:
        artifact, _, elapsed = fit_real_artifact(tmp_path, seed=seed)
        payload = load_current_model_payload(artifact)

        assert artifact.fit_configuration["training_random_seed"] == seed
        assert artifact.provenance["training_random_seed"] == seed
        assert payload["training_random_seed"] == seed
        assert set(artifact.fit_configuration["fit_summary"]) == {
            "structure",
            "parameters",
            "likelihood",
        }
        assert elapsed < FIT_BUDGET_SECONDS
