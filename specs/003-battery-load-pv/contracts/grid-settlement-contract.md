# Contract: Net-Grid Accounting and Settlement

This contract defines how the extended simulator computes and settles net-grid
behavior for the battery + load + PV MVP.

## Purpose

The simulator must make grid accounting explicit enough that a reviewer can
recompute each step from the trace without relying on undocumented conventions.

## Net-Grid Equation

For each time step, the simulator must compute one signed net-grid power value:

```text
net_grid_power_kw = load_kw + realized_battery_power_kw - pv_generation_kw
```

Where:

- `load_kw` is non-negative exogenous consumption
- positive `realized_battery_power_kw` means the battery is charging and adds
  demand to the grid balance
- negative `realized_battery_power_kw` means the battery is discharging and
  offsets demand or contributes to export
- `pv_generation_kw` is non-negative local generation that offsets demand

## Per-Step Direction Rules

- `net_grid_power_kw > 0` means grid import
- `net_grid_power_kw < 0` means grid export
- `net_grid_power_kw == 0` means neutral exchange

The MVP may not track simultaneous import and export in the same time step.
One signed value is the whole grid exchange surface.

## Settlement Rules

Per-step settlement must:

- convert power to energy using `time_step_hours`
- apply the import price when net-grid energy is positive
- apply the discounted export price when net-grid energy is negative
- preserve the existing export discount semantics from the battery-arbitrage
  MVP
- satisfy `total_settlement == sum(step_settlement)` within configured
  tolerance

## Invariants

The implementation and tests must check:

- per-step energy balance matches the documented equation
- PV generation, load, and battery trace lengths all match the time grid
- no step violates the battery power or SOC limits
- repeated evaluation from the same inputs produces the same net-grid and
  settlement outputs
- sign conventions stay consistent across scenario assembly, trace generation,
  and validation fixtures

## Out of Scope

This contract explicitly excludes:

- simultaneous import/export modeling
- feeder/network physics
- outage logic
- carbon accounting
- real tariff downloads or live API pricing
- solver-backed dispatch optimization
