# Battery Arbitrage MVP Migration Note

This note records the selected legacy evidence and intended migration boundary
for the first simulator capability under `src/open_energy_lab/simulator`.

## Target

- Target module path: `src/open_energy_lab/simulator`
- Initial validation paths:
  - `tests/unit/simulator/`
  - `tests/integration/simulator/`
  - `tests/fixtures/simulator/battery_arbitrage_case.json`

## Exact Legacy Reference Files

- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/scripts/test_battery_consistency.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`
- `legacy/old_tpm/src_py/simulator/common/specs.py`
- `legacy/fed_trpo/src/custom/building.py`

## Behavior To Preserve

- battery capacity bounds
- battery charge and discharge power limits
- charge and discharge efficiency semantics
- explicit timestep-in-hours treatment
- step-start tariff alignment
- deterministic validation with documented numeric tolerance

## Behavior To Improve

- one explicit SOC convention based on fractions in `[0.0, 1.0]`
- explicit discounted export settlement relative to import prices
- a typed scenario surface with explicit component relationships
- support for explicit dispatch requests and one built-in deterministic
  `price_threshold` rule
- test-local synthetic fixtures with provenance notes

## Implemented Scenario-Assembly Semantics

The current US1 implementation provides:

- a stable package location at `open_energy_lab.simulator`
- experimental concrete arbitrage types exported from that package:
  - `TimeGrid`
  - `BatteryComponent`
  - `DispatchRequestSeries`
  - `PriceSignal`
  - `DeterministicRulePolicy`
  - `ArbitrageObjectiveRepresentation`
  - `ArbitrageScenario`
- a required scenario core of time grid, battery, price signal, and objective
- exactly one execution input per scenario validation path:
  - explicit `DispatchRequestSeries`, or
  - built-in deterministic `price_threshold` policy
- fail-fast validation for:
  - non-positive timestep duration
  - invalid battery bounds or efficiency values
  - dispatch length mismatches
  - missing or duplicated execution-path inputs
  - missing discounted-export semantics
  - mismatched objective versus price-signal export ratios
- explicit component-graph wiring with validated relation vocabulary:
  - `aligns`
  - `requests`
  - `drives`
  - `prices`
  - `settles`
  - `produces`

## Behavior To Reject

- wholesale copying of legacy simulator structure
- mandatory TorchRL, CityLearn, solver, W&B, notebook, GPU/SLURM, or Rust
  dependencies in simulator-core imports
- broad building, weather, or full-city simulation scope in the MVP
- undocumented assumptions about signs, units, tolerances, or settlement rules

## Explicit Non-Goals

This MVP does not implement planning, control, RL training, solver-backed
optimization, notebook workflows, W&B integrations, GPU/SLURM execution,
weather migration, ENTSO-E adapters, or Rust bindings.

The current scenario assembly also does not implement:

- automatic dispatch optimization
- planning APIs
- closed-loop control policies beyond the deterministic `price_threshold` rule
- multi-battery or multi-building composition
- weather, PV, or demand-model components
