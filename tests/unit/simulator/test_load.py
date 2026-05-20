"""Contract tests for the deterministic load component."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator.load import LoadComponent
from open_energy_lab.simulator.scenario import TimeGrid


def test_load_component_accepts_exogenous_non_negative_profile() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    component = LoadComponent(
        name="load",
        demand_kw=[2.0, 1.5, 0.5],
        interpretation="exogenous-consumption",
        time_grid=grid,
        source="synthetic-fixture",
    )

    assert component.time_grid is grid
    assert component.demand_kw == [2.0, 1.5, 0.5]
    assert component.interpretation == "exogenous-consumption"


def test_load_component_rejects_negative_values() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    with pytest.raises(ValueError, match="load values must be non-negative"):
        LoadComponent(
            name="load",
            demand_kw=[2.0, -0.1, 0.5],
            interpretation="exogenous-consumption",
            time_grid=grid,
            source="synthetic-fixture",
        )


def test_load_component_requires_time_grid_alignment() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    with pytest.raises(ValueError, match="load profile length must match the time grid"):
        LoadComponent(
            name="load",
            demand_kw=[2.0, 1.5],
            interpretation="exogenous-consumption",
            time_grid=grid,
            source="synthetic-fixture",
        )
