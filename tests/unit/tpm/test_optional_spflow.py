"""Unit coverage for required current-SPFlow capability reporting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import tpm.optional_spflow as optional_spflow_module
from tpm import detect_spflow_backend_capabilities


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
            "fallback_query_strategy": None,
            "reason": "fake adapter available",
        }

    def fit_runtime_payload(self, runtime_payload):
        return dict(runtime_payload)


def test_detect_spflow_backend_capabilities_reports_current_runtime_state() -> None:
    capabilities = detect_spflow_backend_capabilities()

    assert set(capabilities) >= {
        "installed_backend_module",
        "installed_backend_version",
        "required_backend_version",
        "backend_generation",
        "backend_api_version",
        "version_compatible",
        "current_api_available",
        "current_api_module_prefix",
        "missing_api_symbols",
        "backend_compatible",
        "legacy_spn_api_available",
        "legacy_api_module_prefix",
        "supports_real_spn_training",
        "supports_real_spn_query",
        "fallback_query_strategy",
        "reason",
    }
    assert capabilities["installed_backend_module"] == "spflow"
    assert capabilities["installed_backend_version"] == "1.1.0"
    assert capabilities["required_backend_version"] == "1.1.0"
    assert capabilities["backend_generation"] == "current-spflow"
    assert capabilities["backend_api_version"] == "1.1.0"
    assert capabilities["version_compatible"] is True
    assert capabilities["current_api_available"] is True
    assert capabilities["current_api_module_prefix"] == "spflow"
    assert capabilities["missing_api_symbols"] == []
    assert capabilities["backend_compatible"] is True
    assert capabilities["legacy_spn_api_available"] is False
    assert capabilities["legacy_api_module_prefix"] is None
    assert capabilities["supports_real_spn_training"] is True
    assert capabilities["supports_real_spn_query"] is True
    assert capabilities["fallback_query_strategy"] is None
    assert "current" in str(capabilities["reason"])


def test_detect_spflow_backend_capabilities_can_use_an_injected_adapter() -> None:
    capabilities = detect_spflow_backend_capabilities(_FakeAdapter())

    assert capabilities["backend_adapter_name"] == "fake-adapter"
    assert capabilities["installed_backend_module"] == "fake-spflow"
    assert capabilities["supports_real_spn_training"] is True


def test_detect_spflow_backend_capabilities_reports_missing_current_api_symbols(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        optional_spflow_module,
        "_load_current_spflow_capabilities",
        lambda: (None, ("spflow.learn.learn_spn",)),
    )

    capabilities = detect_spflow_backend_capabilities(
        SimpleNamespace(__name__="spflow", __version__="1.1.0")
    )

    assert capabilities["version_compatible"] is True
    assert capabilities["current_api_available"] is False
    assert capabilities["backend_compatible"] is False
    assert capabilities["missing_api_symbols"] == ["spflow.learn.learn_spn"]
    assert capabilities["supports_real_spn_training"] is False
    assert capabilities["fallback_query_strategy"] is None


def test_backend_only_stabilization_regularizes_unobserved_categorical_values() -> None:
    import torch
    from spflow.meta.data import Scope
    from spflow.modules.leaves import Categorical

    leaf = Categorical(
        scope=Scope(0),
        K=3,
        probs=torch.tensor([[[[1.0, 0.0, 0.0]]]], dtype=torch.float64),
    )

    optional_spflow_module.stabilize_spflow_leaf_parameters(leaf)
    probabilities = leaf.probs.detach()

    assert bool(torch.isfinite(probabilities).all())
    assert bool((probabilities > 0.0).all())
    assert float(probabilities.sum(dim=-1).reshape(-1)[0]) == pytest.approx(1.0)
