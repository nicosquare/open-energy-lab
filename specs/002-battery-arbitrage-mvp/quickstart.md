# Quickstart: Battery Arbitrage Simulator MVP

Use this quickstart to review the plan and to guide the later simulator MVP
implementation. This feature migrates a narrow simulator slice only.

## Review the Feature

```bash
sed -n '1,260p' specs/002-battery-arbitrage-mvp/spec.md
sed -n '1,260p' specs/002-battery-arbitrage-mvp/plan.md
sed -n '1,240p' specs/002-battery-arbitrage-mvp/research.md
sed -n '1,240p' specs/002-battery-arbitrage-mvp/data-model.md
```

Confirm the intended boundary:

- target code stays under `src/open_energy_lab/simulator`
- the first case is deterministic battery arbitrage only
- battery, time-grid, tariff, dispatch, and settlement behavior are in scope
- planning, control, RL, solver, CityLearn-runtime, notebook, W&B, GPU/SLURM,
  and Rust-bound behavior are out of scope

## Review the Contracts

```bash
sed -n '1,220p' specs/002-battery-arbitrage-mvp/contracts/scenario-contract.md
sed -n '1,220p' specs/002-battery-arbitrage-mvp/contracts/battery-component.md
sed -n '1,220p' specs/002-battery-arbitrage-mvp/contracts/validation-case.md
```

Before implementation, make sure the contracts agree on:

- energy in `kWh`
- power in `kW`
- SOC as fraction in `[0.0, 1.0]`
- positive dispatch request meaning charge
- timestep duration expressed in hours
- discounted export settlement relative to import price
- default absolute tolerance `1e-6`
- the only built-in rule policy being `price_threshold`

## Review the Legacy Evidence

```bash
sed -n '1,260p' legacy/old_tpm/src_py/legacy/storage.py
sed -n '1,260p' legacy/old_tpm/src_py/simulator/common/battery.py
sed -n '1,220p' legacy/old_tpm/src_py/simulator/common/pricing.py
sed -n '1,120p' legacy/old_tpm/src_py/simulator/common/time.py
sed -n '1,220p' legacy/old_tpm/scripts/test_battery_consistency.py
```

Use these sources to validate the chosen battery, tariff, and tolerance
semantics. Do not copy broad legacy structure into the new package.

## Environment

The simulator MVP uses the same base environment as the foundation:

```bash
conda activate open-energy-lab
uv sync --dev
```

If the environment is not present yet, follow the foundation quickstart first:

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
docs/migration/
```

The implementation should stay narrow. A single deterministic scenario is
enough if it proves the contracts. That scenario may use explicit dispatch
requests or the built-in `price_threshold` policy, but the validation path must
state which mode it is using.

## Current US1 Scenario Assembly Usage

The stable import location is `open_energy_lab.simulator`. The concrete
battery-arbitrage types exported there are still experimental.

```python
from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    ArbitrageScenario,
    BatteryComponent,
    DispatchRequestSeries,
    PriceSignal,
    TimeGrid,
)

grid = TimeGrid(num_steps=3, time_step_hours=1.0)
scenario = ArbitrageScenario(
    scenario_id="example-dispatch-scenario",
    time_grid=grid,
    battery=BatteryComponent(
        name="battery",
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=0.5,
    ),
    price_signal=PriceSignal(
        currency="USD",
        unit_rate_name="energy-price",
        import_prices=[0.10, 0.20, 0.30],
        export_price_ratio=0.8,
        interpretation="discounted export relative to import prices",
        time_alignment="step-start",
        time_grid=grid,
    ),
    dispatch_requests=DispatchRequestSeries(
        requested_power_kw=[1.0, 0.0, -1.0],
        sign_convention="charge",
        source="quickstart",
    ),
    objective=ArbitrageObjectiveRepresentation(
        objective_name="arbitrage",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=0.8,
    ),
)

graph = scenario.validate()
assert graph.has_connection("time_grid", "price_signal", "aligns")
```

The alternative US1 execution path is the built-in deterministic
`price_threshold` rule policy. A scenario must provide exactly one of explicit
dispatch requests or the rule policy.

## Expected Checks After Tasks Exist

```bash
uv run pytest tests/unit/simulator tests/integration/simulator
uv run python -c "import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit tests/integration
```

Expected result for the legacy-import scan: no matches in new library modules
or their default tests.

The focused US1 validation command is:

```bash
uv run pytest tests/unit/simulator/test_scenario.py tests/unit/simulator/test_pricing.py
```

The focused US3 boundary validation commands are:

```bash
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/simulator/test_import_boundary.py tests/unit/simulator/test_no_legacy_imports.py
uv run python -c "import open_energy_lab.simulator"
```

## Final Package Boundary

`open_energy_lab.simulator` is now the stable import location for simulator
work, but the concrete arbitrage-facing types exported there are still
experimental.

Current simulator-core modules are limited to the standard library plus local
simulator imports:

- `open_energy_lab.simulator`
- `open_energy_lab.simulator._units`
- `open_energy_lab.simulator._graph`
- `open_energy_lab.simulator.pricing`
- `open_energy_lab.simulator.scenario`
- `open_energy_lab.simulator.battery`
- `open_energy_lab.simulator.objective`

Optional adapters remain out of scope for this feature:

- TorchRL or PyTorch integrations
- CityLearn wrappers
- solver-backed optimizers
- notebook or W&B workflows
- GPU or SLURM execution helpers
- external tariff/data ingestion adapters
- Rust bindings

Optional reference check when the legacy environment is locally runnable:

```bash
cd legacy/old_tpm && python scripts/test_battery_consistency.py
```

## Final Validation Outcomes

Phase 6 validation for this feature is:

```bash
uv run pytest tests/unit/simulator tests/integration/simulator tests/unit/test_optional_dependency_boundaries.py
uv run python -c "import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit/simulator tests/integration/simulator -g '!tests/unit/simulator/test_no_legacy_imports.py'
```

Observed outcome at feature completion:

- the pytest command passed
- `import open_energy_lab.simulator` passed
- the legacy-import scan returned no matches in simulator source or runtime
  tests when excluding the guard test file that intentionally contains the scan
  strings

Legacy reference check outcome:

- `cd legacy/old_tpm && python scripts/test_battery_consistency.py` did not run
  successfully in the default workspace environment
- current failure: `ModuleNotFoundError: No module named 'storage'`
- interpretation: the legacy script still depends on local import-path setup
  that is outside this MVP's required environment
- status for this feature: documented skip, not a blocker

## Checks Intentionally Out of Scope

This feature should not require or run:

- solver-backed optimization
- TorchRL or PyTorch adapter flows
- CityLearn environment execution
- W&B or notebook workflows
- GPU or SLURM execution
- real-data tariff ingestion
- Rust builds or Rust parity checks

## Task Planning Reminder

When `/speckit-tasks` is generated, make sure it includes:

- simulator module creation
- battery invariant tests
- timestep/tariff alignment tests
- discounted-export settlement tests
- optional built-in `price_threshold` policy tests
- one deterministic arbitrage integration case with `1e-6` tolerance-backed
  assertions
- fixture provenance updates when fixtures are committed
- docs covering preserved, improved, and rejected legacy behavior
