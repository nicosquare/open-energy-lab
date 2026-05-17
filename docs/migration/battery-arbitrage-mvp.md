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

## Deterministic Fixture and Invariants

The current US2 validation fixture is
`tests/fixtures/simulator/battery_arbitrage_case.json`.

It captures two deterministic execution paths over the same 3-step synthetic
scenario:

- explicit dispatch: `[1.0, 0.0, -1.0]` kW
- built-in `price_threshold` rule with threshold `0.2`, yielding
  `[5.0, 0.0, -5.0]` kW requests

The fixture preserves targeted evidence from:

- `legacy/old_tpm/scripts/test_battery_consistency.py`
- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`

The current deterministic invariants are:

- SOC remains inside `[0.0, 1.0]`
- realized power does not exceed configured charge/discharge limits
- charge and discharge efficiency losses are reflected in stored-energy changes
- total settlement equals the sum of the step-settlement values
- export settlement uses the discounted export-price ratio
- repeated `price_threshold` evaluation from the same inputs produces the same
  trace

The numeric comparison policy remains absolute tolerance `1e-6`. That value is
strict enough to catch drift in the battery and settlement math while still
matching the small floating-point tolerance expected by the selected legacy
battery consistency evidence.

## Final Dependency Boundary

The current simulator-core dependency classification is:

- core:
  - `src/open_energy_lab/simulator/__init__.py`
  - `src/open_energy_lab/simulator/_units.py`
  - `src/open_energy_lab/simulator/_graph.py`
  - `src/open_energy_lab/simulator/pricing.py`
  - `src/open_energy_lab/simulator/scenario.py`
  - `src/open_energy_lab/simulator/battery.py`
  - `src/open_energy_lab/simulator/objective.py`
- optional:
  - future TorchRL, PyTorch, CityLearn, or notebook-facing adapters
- external-service-backed:
  - future tariff/data adapters such as ENTSO-E integrations
- hardware-bound:
  - future GPU, SLURM, or solver-backed execution paths
- legacy-only:
  - `legacy/old_tpm/*`
  - `legacy/fed_trpo/*`

The stable package boundary is `open_energy_lab.simulator`.

The following exported concrete types remain experimental even though the
package location is stable:

- `TimeGrid`
- `BatteryComponent`
- `DispatchRequestSeries`
- `PriceSignal`
- `DeterministicRulePolicy`
- `ArbitrageObjectiveRepresentation`
- `ArbitrageScenario`

The simulator-core modules are now audited to keep imports limited to the
standard library plus local simulator modules. Optional research stacks and
legacy modules are excluded from default import paths and are covered by
boundary tests.

## Adapter Non-Goals

This feature still does not add:

- TorchRL adapters
- PyTorch-native tensor execution paths
- CityLearn environment wrappers
- solver-backed optimization adapters
- notebook execution helpers
- W&B instrumentation adapters
- GPU or SLURM runtime integration
- real-data tariff ingestion adapters
- Rust bindings or Rust-backed execution surfaces
