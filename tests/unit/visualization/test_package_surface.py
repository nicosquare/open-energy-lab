"""Package-surface maturity checks for visualization scaffolding."""

from __future__ import annotations

import importlib
import importlib.util
import sys


EXPERIMENTAL_PLOTTING_MODULE = "open_energy_lab.visualization.plotting"


def test_visualization_root_stays_explicit_about_surface_maturity() -> None:
    module = importlib.import_module("open_energy_lab.visualization")

    if hasattr(module, "__all__"):
        assert isinstance(module.__all__, list)
        for name in module.__all__:
            exported_value = getattr(module, name)
            assert exported_value.__module__ != EXPERIMENTAL_PLOTTING_MODULE
    else:
        assert module.__doc__ is not None
        assert "Future visualization module scaffold" in module.__doc__


def test_visualization_root_does_not_reexport_plotting_symbols() -> None:
    module = importlib.import_module("open_energy_lab.visualization")

    if not hasattr(module, "__all__"):
        assert importlib.util.find_spec(EXPERIMENTAL_PLOTTING_MODULE) is None
        return

    for name in module.__all__:
        assert "plot" not in name.lower()
        assert "render" not in name.lower()


def test_visualization_root_import_keeps_experimental_plotting_optional() -> None:
    loaded_before_import = set(sys.modules)

    importlib.import_module("open_energy_lab.visualization")

    loaded_by_import = set(sys.modules) - loaded_before_import
    assert EXPERIMENTAL_PLOTTING_MODULE not in loaded_by_import
