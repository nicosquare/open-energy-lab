"""Smoke coverage for the stable-versus-experimental visualization split."""

from __future__ import annotations

import importlib
import sys

import pytest


def _clear_visualization_modules() -> None:
    for module_name in tuple(sys.modules):
        if module_name == "open_energy_lab.visualization" or module_name.startswith(
            "open_energy_lab.visualization."
        ):
            sys.modules.pop(module_name, None)


def test_root_visualization_import_does_not_load_experimental_plotting() -> None:
    _clear_visualization_modules()

    module = importlib.import_module("open_energy_lab.visualization")

    assert module.__all__ == [
        "build_inspection_view",
        "load_persisted_run_output",
        "summarize_inspection_view",
    ]
    assert "open_energy_lab.visualization.plotting" not in sys.modules


def test_stable_visualization_exports_resolve_without_plotting_imports() -> None:
    _clear_visualization_modules()

    module = importlib.import_module("open_energy_lab.visualization")

    assert module.build_inspection_view.__module__ == "open_energy_lab.visualization.inspection"
    assert (
        module.load_persisted_run_output.__module__
        == "open_energy_lab.visualization._persistence"
    )
    assert (
        module.summarize_inspection_view.__module__
        == "open_energy_lab.visualization.inspection"
    )
    assert "open_energy_lab.visualization.plotting" not in sys.modules


def test_plotting_helpers_require_direct_module_import() -> None:
    _clear_visualization_modules()

    module = importlib.import_module("open_energy_lab.visualization")

    with pytest.raises(AttributeError):
        module.plot_inspection_view

    plotting_module = importlib.import_module("open_energy_lab.visualization.plotting")

    assert plotting_module.__all__ == ["plot_inspection_view"]
    assert plotting_module.plot_inspection_view.__module__ == plotting_module.__name__
    with pytest.raises(AttributeError):
        module.plot_inspection_view
