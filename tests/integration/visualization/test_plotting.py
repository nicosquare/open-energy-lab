"""Integration coverage for experimental static single-run plotting."""

from __future__ import annotations

import importlib

import pytest

from open_energy_lab.simulator import ArbitrageScenario
from tests.integration.visualization.arbitrage_result_utils import (
    build_controller_arbitrage_result,
    build_direct_arbitrage_trace,
    make_persisted_arbitrage_output,
)


class RecordingPlotBackend:
    """Tiny backend double for deterministic plotting integration tests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def render_static_plot(self, plot_spec: dict[str, object]) -> dict[str, object]:
        self.calls.append(plot_spec)
        return {
            "backend": "recording",
            "plot_spec": plot_spec,
        }


def _inspection_module():
    return importlib.import_module("open_energy_lab.visualization.inspection")


def _plotting_module():
    return importlib.import_module("open_energy_lab.visualization.plotting")


def _persistence_module():
    return importlib.import_module("open_energy_lab.visualization._persistence")


def test_plotting_accepts_an_existing_inspection_view_without_resimulation() -> None:
    inspection = _inspection_module()
    plotting = _plotting_module()

    _, controller_result = build_controller_arbitrage_result()
    inspection_view = inspection.build_inspection_view(controller_result)
    backend = RecordingPlotBackend()

    plot_result = plotting.plot_inspection_view(
        inspection_view,
        series_names=["requested_power_kw", "realized_power_kw"],
        backend=backend,
    )

    assert plot_result["backend"] == "recording"
    assert [series["series_name"] for series in backend.calls[0]["series"]] == [
        "requested_power_kw",
        "realized_power_kw",
    ]
    assert backend.calls[0]["scenario_kind"] == "ArbitrageScenario"
    assert backend.calls[0]["source_kind"] == "controller_evaluation"


def test_plotting_from_persisted_output_does_not_rerun_the_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence = _persistence_module()
    plotting = _plotting_module()

    scenario, trace = build_direct_arbitrage_trace()
    persisted_output = make_persisted_arbitrage_output(scenario, trace)
    loaded_output = persistence.load_persisted_run_output(persisted_output)
    backend = RecordingPlotBackend()

    def fail_if_rerun(self: ArbitrageScenario) -> object:
        raise AssertionError("plotting must not rerun the simulator")

    monkeypatch.setattr(ArbitrageScenario, "evaluate_trace", fail_if_rerun)

    plot_result = plotting.plot_inspection_view(
        loaded_output,
        series_names=["battery_soc", "step_settlement"],
        backend=backend,
    )

    assert plot_result["backend"] == "recording"
    assert [series["series_name"] for series in backend.calls[0]["series"]] == [
        "battery_soc",
        "step_settlement",
    ]
    assert backend.calls[0]["source_kind"] == "persisted_output"
