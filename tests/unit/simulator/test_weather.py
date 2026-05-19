"""Contract tests for the minimal weather component."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator.scenario import TimeGrid
from open_energy_lab.simulator.weather import WeatherComponent


def test_weather_component_tracks_required_subset_and_tmy_mappings() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    component = WeatherComponent(
        name="weather",
        time_grid=grid,
        timestamp_utc=[
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T02:00:00Z",
        ],
        dry_bulb_air_temperature_c=[25.0, 26.0, 27.0],
        global_horizontal_irradiance_w_per_m2=[0.0, 300.0, 800.0],
    )

    assert component.included_field_names() == (
        "timestamp_utc",
        "dry_bulb_air_temperature_c",
        "global_horizontal_irradiance_w_per_m2",
    )
    assert component.tmy_label_for("timestamp_utc") == "Date & time (UTC)"
    assert component.tmy_label_for("dry_bulb_air_temperature_c") == "T2m [°C]"
    assert (
        component.tmy_label_for("global_horizontal_irradiance_w_per_m2")
        == "G(h) [W/m2]"
    )


def test_weather_component_requires_an_irradiance_field() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    with pytest.raises(ValueError, match="at least one irradiance field must be provided"):
        WeatherComponent(
            name="weather",
            time_grid=grid,
            timestamp_utc=[
                "2026-01-01T00:00:00Z",
                "2026-01-01T01:00:00Z",
                "2026-01-01T02:00:00Z",
            ],
            dry_bulb_air_temperature_c=[25.0, 26.0, 27.0],
        )


def test_weather_component_rejects_length_mismatches_and_negative_irradiance() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    with pytest.raises(ValueError, match="weather field 'timestamp_utc' length must match the time grid"):
        WeatherComponent(
            name="weather",
            time_grid=grid,
            timestamp_utc=["2026-01-01T00:00:00Z"],
            dry_bulb_air_temperature_c=[25.0, 26.0, 27.0],
            global_horizontal_irradiance_w_per_m2=[0.0, 300.0, 800.0],
        )

    with pytest.raises(
        ValueError,
        match="irradiance field 'global_horizontal_irradiance_w_per_m2' must be non-negative",
    ):
        WeatherComponent(
            name="weather",
            time_grid=grid,
            timestamp_utc=[
                "2026-01-01T00:00:00Z",
                "2026-01-01T01:00:00Z",
                "2026-01-01T02:00:00Z",
            ],
            dry_bulb_air_temperature_c=[25.0, 26.0, 27.0],
            global_horizontal_irradiance_w_per_m2=[0.0, -1.0, 800.0],
        )


def test_weather_component_exposes_deferred_standard_fields() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    component = WeatherComponent(
        name="weather",
        time_grid=grid,
        timestamp_utc=[
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T02:00:00Z",
        ],
        dry_bulb_air_temperature_c=[25.0, 26.0, 27.0],
        direct_beam_irradiance_w_per_m2=[0.0, 200.0, 500.0],
        deferred_fields=("relative_humidity_pct", "surface_air_pressure_pa"),
    )

    assert component.deferred_field_names == (
        "relative_humidity_pct",
        "surface_air_pressure_pa",
    )
