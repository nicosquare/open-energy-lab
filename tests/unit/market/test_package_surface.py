"""Public package-surface contracts for canonical market consumers."""

from __future__ import annotations

import importlib
import sys

import pytest


RELOADED_MARKET_MODULES = (
    "open_energy_lab.market.rte",
    "open_energy_lab.market.entsoe",
    "open_energy_lab.market.entsoe_restoration",
    "open_energy_lab.market.restoration_artifact",
    "open_energy_lab.market.restoration_activation",
    "open_energy_lab.market.activation",
    "open_energy_lab.market.artifact",
    "open_energy_lab.market.time",
    "open_energy_lab.market",
)


@pytest.fixture(autouse=True)
def _restore_market_module_identity_after_fresh_surface_check():
    """Fresh-root checks must not replace types held by collected test modules."""

    before = {
        name: sys.modules[name]
        for name in RELOADED_MARKET_MODULES
        if name in sys.modules
    }
    root = sys.modules.get("open_energy_lab")
    root_market = getattr(root, "market", None) if root is not None else None
    yield
    for name in RELOADED_MARKET_MODULES:
        sys.modules.pop(name, None)
    sys.modules.update(before)
    if root is not None:
        if root_market is None:
            root.__dict__.pop("market", None)
        else:
            root.market = root_market


def _fresh_market_root():
    for module_name in RELOADED_MARKET_MODULES:
        sys.modules.pop(module_name, None)
    return importlib.import_module("open_energy_lab.market")


def test_unknown_market_root_attribute_fails_without_adapter_import():
    market = _fresh_market_root()

    with pytest.raises(AttributeError, match="no attribute 'unknown_contract'"):
        getattr(market, "unknown_contract")
    assert "open_energy_lab.market.entsoe" not in sys.modules
    assert "open_energy_lab.market.entsoe_restoration" not in sys.modules
    assert "open_energy_lab.market.rte" not in sys.modules
