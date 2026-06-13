"""Integration coverage for plotting weather-backed battery-load-PV traces."""

from __future__ import annotations

import importlib

import pytest

from open_energy_lab.simulator import BatteryLoadPVScenario
from tests.integration.visualization.battery_load_pv_result_utils import (
    build_controller_battery_load_pv_result,
    build_direct_battery_load_pv_trace,
    make_persisted_battery_load_pv_output,
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


def test_plotting_accepts_weather_backed_inspection_views_without_resimulation() -> None:
    inspection = _inspection_module()
    plotting = _plotting_module()

    _, controller_result = build_controller_battery_load_pv_result()
    inspection_view = inspection.build_inspection_view(controller_result)
    backend = RecordingPlotBackend()

    plot_result = plotting.plot_inspection_view(
        inspection_view,
        series_names=[
            "load_kw",
            "pv_generation_kw",
            "net_grid_power_kw",
            "dry_bulb_air_temperature_c",
            "global_horizontal_irradiance_w_per_m2",
        ],
        backend=backend,
    )

    assert plot_result["backend"] == "recording"
    assert [series["series_name"] for series in backend.calls[0]["series"]] == [
        "load_kw",
        "pv_generation_kw",
        "net_grid_power_kw",
        "dry_bulb_air_temperature_c",
        "global_horizontal_irradiance_w_per_m2",
    ]
    assert backend.calls[0]["scenario_kind"] == "BatteryLoadPVScenario"
    assert backend.calls[0]["source_kind"] == "controller_evaluation"
    assert backend.calls[0]["available_sections"]["weather"] is True


def test_plotting_from_persisted_battery_load_pv_output_does_not_rerun_the_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence = _persistence_module()
    plotting = _plotting_module()

    scenario, trace = build_direct_battery_load_pv_trace()
    persisted_output = make_persisted_battery_load_pv_output(scenario, trace)
    loaded_output = persistence.load_persisted_run_output(persisted_output)
    backend = RecordingPlotBackend()

    def fail_if_rerun(self: BatteryLoadPVScenario) -> object:
        raise AssertionError("plotting must not rerun the simulator")

    monkeypatch.setattr(BatteryLoadPVScenario, "evaluate_trace", fail_if_rerun)

    plot_result = plotting.plot_inspection_view(
        loaded_output,
        series_names=[
            "pv_generation_kw",
            "net_grid_power_kw",
            "dry_bulb_air_temperature_c",
        ],
        backend=backend,
    )

    assert plot_result["backend"] == "recording"
    assert [series["series_name"] for series in backend.calls[0]["series"]] == [
        "pv_generation_kw",
        "net_grid_power_kw",
        "dry_bulb_air_temperature_c",
    ]
    assert backend.calls[0]["source_kind"] == "persisted_output"
    assert backend.calls[0]["available_sections"]["weather"] is True
