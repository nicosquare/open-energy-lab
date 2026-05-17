# Quickstart: Deterministic Battery Load PV Scenario MVP

Use this quickstart to review the plan and guide the later implementation. This
feature extends the battery-arbitrage simulator with deterministic load,
minimal weather-driven PV, and one-net grid settlement.

## Review the Feature

```bash
sed -n '1,320p' specs/003-battery-load-pv/spec.md
sed -n '1,320p' specs/003-battery-load-pv/plan.md
sed -n '1,260p' specs/003-battery-load-pv/research.md
sed -n '1,260p' specs/003-battery-load-pv/data-model.md
```

Confirm the intended boundary:

- target code stays under `src/open_energy_lab/simulator`
- the new case adds load, minimal weather inputs, PV derivation, and net-grid
  accounting
- the included weather fields keep exact TMY-style names instead of a renamed
  internal schema
- battery physics, timestep rules, export discount semantics, and the
  `price_threshold` rule remain aligned with the completed battery-arbitrage MVP
- optimization, MPC, RL, CityLearn runtime, broader weather migration,
  notebooks, W&B, GPU/SLURM, and Rust-bound behavior remain out of scope

## Review the Contracts

```bash
sed -n '1,220p' specs/003-battery-load-pv/contracts/scenario-contract.md
sed -n '1,220p' specs/003-battery-load-pv/contracts/weather-pv-contract.md
sed -n '1,220p' specs/003-battery-load-pv/contracts/grid-settlement-contract.md
sed -n '1,220p' specs/003-battery-load-pv/contracts/validation-case.md
```

Before implementation, make sure the contracts agree on:

- energy in `kWh`
- power in `kW`
- timestep duration in hours
- exact TMY-style names for the included weather fields
- positive battery dispatch request meaning charge
- positive net-grid value meaning import
- one signed net-grid value per step only
- default absolute tolerance `1e-6`
- the built-in deterministic battery rule remaining price-only
- the weather scope staying limited to the PV derivation path

## Review the Legacy Evidence

```bash
sed -n '1,260p' legacy/old_tpm/src_py/legacy/storage.py
sed -n '1,260p' legacy/old_tpm/src_py/simulator/common/battery.py
sed -n '1,220p' legacy/old_tpm/src_py/simulator/common/pricing.py
sed -n '1,120p' legacy/old_tpm/src_py/simulator/common/time.py
sed -n '1,260p' legacy/old_tpm/src_py/simulator/common/specs.py
sed -n '1888,1924p' legacy/fed_trpo/src/custom/building.py
```

Use these sources to validate preserved battery and settlement semantics, the
PV metadata direction, the single-net electricity accounting pattern, and the
TMY-style weather naming expectation. Do not copy broad building or CityLearn
structure into the new package.

## Environment

The feature uses the same base environment as the completed simulator MVP:

```bash
conda activate open-energy-lab
uv sync --dev
```

If the environment is not present yet, review the foundation quickstart first:

```bash
sed -n '1,200p' specs/001-library-foundation/quickstart.md
```

## Expected Implementation Targets

After implementation, the main touched areas should be:

```text
src/open_energy_lab/simulator/
tests/unit/simulator/
tests/integration/simulator/
tests/fixtures/simulator/
tests/parity/
docs/migration/
```

The implementation should stay narrow. One or two deterministic scenarios are
enough if they prove:

- battery constraints still hold
- weather drives PV deterministically
- included weather fields preserve their exact TMY-style names
- load, PV, and realized battery power produce the documented net-grid trace
- settlement follows the documented one-net import/export rule
- both execution modes remain supported if both are implemented in the fixture

## Planned Extended Surface

The stable import location remains `open_energy_lab.simulator`. This feature is
expected to add experimental multi-component types alongside the existing
battery-arbitrage surface, for example:

```python
from open_energy_lab.simulator import (
    BatteryComponent,
    DeterministicRulePolicy,
    DispatchRequestSeries,
    PriceSignal,
    TimeGrid,
)
from open_energy_lab.simulator.load import LoadComponent
from open_energy_lab.simulator.pv import PVComponent
from open_energy_lab.simulator.weather import WeatherComponent
```

The exact exported names can still evolve during implementation, but the
feature should avoid relocating the package or breaking the existing
battery-arbitrage entry points without cause.

## Expected Checks After Tasks Exist

```bash
uv run pytest tests/unit/simulator tests/integration/simulator tests/unit/test_optional_dependency_boundaries.py
uv run python -c "import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit/simulator tests/integration/simulator
```

Focused validation commands should include:

```bash
uv run pytest tests/unit/simulator/test_load.py tests/unit/simulator/test_weather.py tests/unit/simulator/test_pv.py
uv run pytest tests/unit/simulator/test_grid_settlement.py tests/integration/simulator/test_battery_load_pv_trace.py
```

Expected result for the legacy-import scan: no matches in new library modules
or their runtime tests.

## Checks Intentionally Out of Scope

This feature should not require or run:

- CityLearn environment execution
- RL training loops
- MPC or solver-backed planning
- notebook or W&B workflows
- GPU or SLURM execution
- real weather downloads
- real tariff or external API ingestion
- Rust builds or Rust parity checks

## Task Planning Reminder

When `/speckit-tasks` is generated, make sure it includes:

- tests first for load, weather, PV, and net-grid accounting
- one or two deterministic multi-component fixtures with provenance notes
- simulator module creation or extension for load, weather, PV, and the new
  scenario trace
- integration tests for both explicit dispatch and `price_threshold` behavior
  if both modes are represented
- import-boundary and legacy-isolation checks
- docs covering preserved, improved, and rejected semantics for load, weather,
  PV, and net-grid behavior
