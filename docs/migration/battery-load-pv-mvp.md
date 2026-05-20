# Battery Load PV MVP Migration Note

This note records the selected legacy evidence and intended migration boundary
for the deterministic battery + load + weather + PV simulator MVP under
`src/open_energy_lab/simulator`.

## Target

- Target module path: `src/open_energy_lab/simulator`
- Initial validation paths:
  - `tests/unit/simulator/`
  - `tests/integration/simulator/`
  - `tests/fixtures/simulator/battery_load_pv_case.json`

## Exact Legacy Reference Files

- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/scripts/test_battery_consistency.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`
- `legacy/old_tpm/src_py/simulator/common/specs.py`
- `legacy/fed_trpo/src/custom/building.py`

## Intended Preserved Scope

- battery capacity, power-limit, efficiency, and SOC-bound semantics already
  established by the battery arbitrage MVP
- timestep-in-hours treatment and step-aligned pricing semantics
- discounted export settlement relative to import prices
- deterministic validation with absolute tolerance `1e-6` unless a stricter
  case is explicitly documented
- one signed net-grid value per step rather than simultaneous import and export
- selective PV metadata direction and one-net electricity-accounting evidence
  from the cited legacy references

## Intended Improved Scope

- explicit typed simulator components for load, weather, PV, and net-grid
  accounting instead of hiding them in broader building abstractions
- a documented deterministic weather-to-PV derivation inside simulator core
- human-readable weather field names with explicit mappings to canonical TMY
  source labels for the included MVP subset
- small committed synthetic fixtures with provenance notes and exact legacy
  evidence lists
- a clean explicit-dispatch boundary that remains compatible with future
  external controllers while preserving a built-in deterministic rule baseline

## Intended Rejected Scope

- wholesale copying of legacy simulator or building modules
- mandatory CityLearn, TorchRL, PyTorch, solver, notebook, W&B, GPU/SLURM, or
  Rust dependencies in simulator-core imports
- real weather downloads, real tariff ingestion, or external API adapters in
  the MVP
- broad weather-subsystem migration unrelated to the PV derivation path
- feeder/network physics, outage logic, or multi-building composition in the
  MVP

## Shared Fixture Direction

`tests/fixtures/simulator/battery_load_pv_case.json` is now the active shared
validation case for this migration. It contains:

- one explicit-dispatch execution path
- one built-in `price_threshold` execution path
- weather inputs using human-readable field names plus TMY label mappings
- derived PV output checked against the current implementation
- one-net grid traces and discounted settlement expectations

The fixture remains synthetic and intentionally small so reviewers can inspect
all inputs and expected traces directly.

## Implemented US1 Assembly Semantics

The current US1 implementation now provides:

- a stable package location at `open_energy_lab.simulator`
- experimental multi-component types available from that package:
  - `BatteryLoadPVScenario`
  - `LoadComponent`
  - `WeatherComponent`
  - `PVComponent`
- explicit time-grid alignment checks for load, weather, price, and dispatch
- one required irradiance-backed weather subset using human-readable field
  names with canonical TMY source labels such as:
  - `timestamp_utc` -> `Date & time (UTC)`
  - `dry_bulb_air_temperature_c` -> `T2m [°C]`
  - `global_horizontal_irradiance_w_per_m2` -> `G(h) [W/m2]`
- deferred standard weather fields recorded explicitly rather than treated as
  implicit runtime requirements
- deterministic PV derivation from one or more documented irradiance fields,
  with temperature adjustment relative to the configured reference temperature
- explicit component-graph wiring for:
  - `TimeGrid -> LoadComponent`
  - `TimeGrid -> WeatherComponent`
  - `WeatherComponent -> PVComponent`
  - `LoadComponent/PVComponent/SimulationTrace -> NetGridTrace`
  - `PriceSignal -> NetGridTrace`
  - `NetGridTrace -> Settlement objective`
- both execution-path boundaries preserved:
  - explicit `DispatchRequestSeries`, or
  - built-in deterministic `price_threshold` rule

These types remain experimental even though `open_energy_lab.simulator` is the
stable package location.

The package root now resolves these exported symbols lazily. That keeps
`import open_energy_lab.simulator` lighter while preserving the same stable
import location for callers.

## Implemented US2 Trace and Fixture Semantics

The current US2 implementation finalizes deterministic trace evaluation and the
shared fixture around the following trusted invariants:

- `pv_generation_kw` is derived deterministically from the configured weather
  inputs and PV metadata
- `net_grid_power_kw = load_kw + realized_battery_power_kw - pv_generation_kw`
- `net_grid_energy_kwh = net_grid_power_kw * time_step_hours`
- positive net-grid values mean import and negative values mean export
- `total_settlement == sum(step_settlement)` within absolute tolerance `1e-6`
- export settlement uses the same discounted export-price ratio already
  established by the battery-arbitrage MVP
- repeated evaluation from the same inputs reproduces the same trace

The finalized fixture was manually authored and then checked against the
current implementation with `uv run python -c` trace calculations. It is not a
legacy replay artifact.

## Tolerance Rationale

The default absolute tolerance remains `1e-6`.

This is still the right boundary for the battery + load + PV MVP because:

- it matches the completed battery-arbitrage MVP
- it remains aligned with the cited legacy battery-consistency evidence
- it comfortably absorbs ordinary floating-point round-off from battery
  efficiency math, discounted settlement arithmetic, and temperature-adjusted
  PV derivation without hiding meaningful behavioral drift

## Final Dependency Classification

The final simulator-core dependency boundary for this MVP is:

- core:
  - Python standard library
  - `open_energy_lab.simulator` modules under `src/open_energy_lab/simulator`
- optional:
  - no optional runtime dependency is required for simulator-core imports in
    this MVP
- external-service-backed:
  - none
- hardware-bound:
  - none
- legacy-only evidence:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/scripts/test_battery_consistency.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/old_tpm/src_py/simulator/common/specs.py`
  - `legacy/fed_trpo/src/custom/building.py`

Heavy research stacks remain explicitly outside the simulator-core import path:
TorchRL, PyTorch, CityLearn, solver stacks, notebooks, W&B, GPU/SLURM tooling,
and Rust toolchains.

## Final Experimental API Boundary

For this MVP:

- stable package location:
  - `open_energy_lab.simulator`
- stable import intent:
  - callers may continue importing from `open_energy_lab.simulator`
- experimental concrete multi-component surface:
  - `BatteryLoadPVScenario`
  - `LoadComponent`
  - `WeatherComponent`
  - `PVComponent`

These symbols are exported from the stable package root, but their concrete
multi-component semantics are still experimental and may be refined by later
simulator migrations.

## Deferred Weather-Field Scope

The MVP keeps weather intentionally narrow.

Included runtime weather fields:

- `timestamp_utc`
- `dry_bulb_air_temperature_c`
- one or more irradiance fields needed by the chosen PV derivation

Deferred standard TMY-backed weather fields remain documented but are not
required runtime inputs in this migration:

- `relative_humidity_pct`
- `infrared_radiation_downwards_w_per_m2`
- `windspeed_10m_m_per_s`
- `wind_direction_10m_deg`
- `surface_air_pressure_pa`

Broader weather consumers, real weather ingestion, forecast handling, and
non-PV weather use cases remain future migration work.

## Explicit Non-Goals

This feature does not add:

- planning or MPC implementations
- RL training loops or federated workflows
- CityLearn runtime integration
- solver-backed optimization
- notebook-first workflows
- W&B integrations
- GPU or SLURM execution paths
- Rust bindings
