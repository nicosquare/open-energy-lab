"""Unit coverage for optional SPFlow capability reporting."""

from __future__ import annotations

from types import SimpleNamespace

import open_energy_lab.tpm.optional_spflow as optional_spflow_module
from open_energy_lab.tpm import detect_spflow_backend_capabilities


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
        return dict(runtime_payload)


def test_detect_spflow_backend_capabilities_reports_current_runtime_state() -> None:
    capabilities = detect_spflow_backend_capabilities()

    assert set(capabilities) >= {
        "installed_backend_module",
        "installed_backend_version",
        "legacy_spn_api_available",
        "legacy_api_module_prefix",
        "supports_real_spn_training",
        "supports_real_spn_query",
        "supports_spn_mip_serialization",
        "fallback_query_strategy",
        "reason",
    }
    assert capabilities["supports_real_spn_training"] == capabilities["legacy_spn_api_available"]
    assert capabilities["supports_real_spn_query"] == capabilities["legacy_spn_api_available"]
    assert capabilities["supports_spn_mip_serialization"] == capabilities["legacy_spn_api_available"]

    if capabilities["installed_backend_module"] == "spflow":
        assert capabilities["legacy_spn_api_available"] is False
        assert capabilities["legacy_api_module_prefix"] is None
        assert capabilities["fallback_query_strategy"] == "table"
        assert "spn.*" in str(capabilities["reason"])
        assert "spflow.*" in str(capabilities["reason"])


def test_detect_spflow_backend_capabilities_can_use_an_injected_adapter() -> None:
    capabilities = detect_spflow_backend_capabilities(_FakeAdapter())

    assert capabilities["backend_adapter_name"] == "fake-adapter"
    assert capabilities["installed_backend_module"] == "fake-spflow"
    assert capabilities["supports_real_spn_training"] is True


def test_detect_spflow_backend_capabilities_accepts_legacy_api_under_spflow_prefix(
    monkeypatch,
) -> None:
    fake_bindings = optional_spflow_module._LegacySpflowApiBindings(
        module_prefix="spflow",
        context_class=object,
        leaf_class=object,
        product_class=object,
        sum_class=object,
        get_topological_order=lambda *_args, **_kwargs: (),
        meta_type=SimpleNamespace(REAL="REAL", DISCRETE="DISCRETE", BINARY="BINARY"),
        learn_mspn=lambda *_args, **_kwargs: None,
        marginalize=lambda *_args, **_kwargs: None,
        log_likelihood=lambda *_args, **_kwargs: ((0.0,),),
    )
    monkeypatch.setattr(
        optional_spflow_module,
        "_load_legacy_spflow_api",
        lambda: fake_bindings,
    )

    capabilities = detect_spflow_backend_capabilities(
        SimpleNamespace(__name__="spflow", __version__="legacy-test")
    )

    assert capabilities["legacy_spn_api_available"] is True
    assert capabilities["legacy_api_module_prefix"] == "spflow"
    assert capabilities["fallback_query_strategy"] is None
