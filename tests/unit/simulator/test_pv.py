"""Contract tests for deterministic PV derivation."""

from __future__ import annotations

from open_energy_lab.simulator.pv import PVComponent
from open_energy_lab.simulator.scenario import TimeGrid
from open_energy_lab.simulator.weather import WeatherComponent


def _weather(
    grid: TimeGrid,
    *,
    ghi: list[float] | None = None,
    direct: list[float] | None = None,
    diffuse: list[float] | None = None,
    temperature: list[float] | None = None,
) -> WeatherComponent:
    return WeatherComponent(
        name="weather",
        time_grid=grid,
        timestamp_utc=[
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T02:00:00Z",
        ],
        dry_bulb_air_temperature_c=temperature or [25.0, 25.0, 25.0],
        global_horizontal_irradiance_w_per_m2=ghi,
        direct_beam_irradiance_w_per_m2=direct,
        diffuse_horizontal_irradiance_w_per_m2=diffuse,
    )


def test_pv_component_derives_generation_from_single_irradiance_field() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    weather = _weather(grid, ghi=[0.0, 500.0, 1000.0])
    pv = PVComponent(
        name="pv",
        rated_power_kw=4.0,
        temperature_coefficient_pct_per_c=-0.4,
        reference_irradiance_w_per_m2=1000.0,
        reference_temperature_c=25.0,
        derivation_name="ghi-linear",
        irradiance_field_names=("global_horizontal_irradiance_w_per_m2",),
    )

    assert pv.derive_generation_kw(weather) == [0.0, 2.0, 4.0]


def test_pv_component_supports_documented_irradiance_combinations() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    weather = _weather(
        grid,
        direct=[0.0, 300.0, 600.0],
        diffuse=[0.0, 100.0, 200.0],
    )
    pv = PVComponent(
        name="pv",
        rated_power_kw=5.0,
        temperature_coefficient_pct_per_c=0.0,
        reference_irradiance_w_per_m2=1000.0,
        reference_temperature_c=25.0,
        derivation_name="direct-plus-diffuse",
        irradiance_field_names=(
            "direct_beam_irradiance_w_per_m2",
            "diffuse_horizontal_irradiance_w_per_m2",
        ),
    )

    assert pv.derive_generation_kw(weather) == [0.0, 2.0, 4.0]


def test_pv_component_applies_temperature_adjustment_and_non_negative_clamp() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    weather = _weather(
        grid,
        ghi=[1000.0, 1000.0, 1000.0],
        temperature=[25.0, 35.0, 400.0],
    )
    pv = PVComponent(
        name="pv",
        rated_power_kw=4.0,
        temperature_coefficient_pct_per_c=-1.0,
        reference_irradiance_w_per_m2=1000.0,
        reference_temperature_c=25.0,
        derivation_name="temperature-adjusted",
        irradiance_field_names=("global_horizontal_irradiance_w_per_m2",),
    )

    assert pv.derive_generation_kw(weather) == [4.0, 3.6, 0.0]
