# Implementation Plan: Deterministic Battery Load PV Scenario MVP

**Branch**: `003-battery-load-pv` | **Date**: 2026-05-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-battery-load-pv/spec.md`

**Note**: This plan extends the completed battery-arbitrage MVP. It adds a
deterministic multi-component simulator case with load, minimal weather-driven
PV, and net-grid settlement, but it does not add optimization, MPC, RL,
CityLearn runtime, notebook, W&B, GPU/SLURM, solver, or Rust-bound behavior to
the simulator core.

## Summary

Implement the next simulator migration under `src/open_energy_lab/simulator` as
a typed deterministic scenario that composes the existing battery-arbitrage
surface with three new concerns: exogenous load, minimal weather inputs for PV
derivation, and explicit net-grid import or export accounting. The feature
should preserve the prior battery, timestep, pricing, export-discount, and
price-threshold semantics while improving the simulator design by making
multi-component energy balance explicit and testable.

Legacy evidence remains selective and reference-only. Battery, time, and price
semantics continue to come from
`legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/scripts/test_battery_consistency.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`,
`legacy/old_tpm/src_py/simulator/common/pricing.py`, and
`legacy/old_tpm/src_py/simulator/common/time.py`. Minimal PV and weather
semantics are informed by `legacy/old_tpm/src_py/simulator/common/specs.py`
and the broader grid-balance framing in
`legacy/fed_trpo/src/custom/building.py`. The new MVP keeps those references as
evidence only, defines a small explicit weather-to-PV derivation suitable for
deterministic fixtures, uses human-readable weather field names with explicit
TMY source-label mappings, and rejects broad building, CityLearn, and
research-stack coupling.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`. Existing legacy
Python and Rust remain reference-only and are not required for simulator-core
imports.

**Primary Dependencies**: Core runtime should remain on the Python standard
library plus the existing `open_energy_lab.simulator` modules. `pytest` remains
the primary development dependency for validation. TorchRL, PyTorch, CityLearn,
solver stacks, W&B, notebook tooling, GPU/SLURM helpers, and Rust toolchains
remain non-core and must stay unimported by simulator-core modules.

**Storage/Data**: Markdown design artifacts plus one or two tiny synthetic
JSON-compatible fixtures under `tests/fixtures/simulator`. Weather fixture keys
should use human-readable names plus explicit TMY source-label metadata.
Default numeric comparison tolerance remains absolute `1e-6` unless a stricter
case is documented.

**Testing**: `pytest` for focused `tests/unit/simulator` and
`tests/integration/simulator` coverage, plus simulator import-boundary tests.
`tests/parity` should document why targeted deterministic invariants are the
right evidence standard. Legacy checks may be cited for context but are not
required to pass in the default environment.

**Target Platform**: Local CPU-only research workstation using the existing
minimal conda plus uv workflow.

**Project Type**: Python research library migration inside `src/open_energy_lab`
with reference-only legacy sources.

**Performance Goals**: Deterministic correctness is primary. A short synthetic
horizon such as 6-24 steps should execute in normal unit-test time on CPU. The
same fixed inputs must reproduce the same weather, PV, battery, net-grid, and
settlement traces within absolute tolerance `1e-6`.

**Constraints**: Keep `import open_energy_lab.simulator` lightweight. Preserve
the prior battery-arbitrage sign conventions, timestep-hours semantics, export
discount semantics, and price-only built-in rule semantics. Add weather only to
the extent needed to derive deterministic PV output. Any weather variables
included in the MVP must use human-readable field names with explicit TMY
source-label mappings. Do not add new code to `legacy/*`. Cite exact legacy
files for all migrated or explicitly rejected behavior.

**Scale/Scope**: One time grid, one battery, one load profile, one weather
series using a small human-readable subset mapped to canonical TMY labels, one
PV component, one price signal, one net-grid accounting path, and one or two
deterministic validation fixtures. The feature supports both explicit dispatch
requests and the existing built-in `price_threshold` rule policy. Net-grid
settlement is one signed value per step, not simultaneous import and export
channels.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable simulator code remains under
  `src/open_energy_lab/simulator` and tests remain under `tests`.
- **Legacy reference boundary**: Exact legacy files are cited as evidence and
  will not be edited for this feature.
- **Validation before migration**: The feature is defined around deterministic
  fixtures, energy-balance invariants, typed component relationships, explicit
  `1e-6` tolerance, and explicit weather field mappings.
- **Dependency isolation**: Weather, PV, load, and net-grid behavior are
  designed without pulling in CityLearn, TorchRL, PyTorch, solver, or notebook
  stacks.
- **Reproducibility**: Dispatch modes, net-grid sign conventions, settlement
  rules, weather-to-PV derivation inputs, TMY source-label mappings, and
  fixture provenance are documented before implementation.

**Post-design status**: PASS

- Design artifacts define a narrow multi-component scenario contract, a minimal
  weather-to-PV contract, human-readable weather names with explicit TMY
  mappings, and explicit
  net-grid settlement rules without
  widening the control or dependency boundary.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-battery-load-pv/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── grid-settlement-contract.md
│   ├── scenario-contract.md
│   ├── validation-case.md
│   └── weather-pv-contract.md
└── checklists/
    └── requirements.md
```

### Current Reference Sources

```text
legacy/
├── old_tpm/
│   ├── scripts/test_battery_consistency.py
│   └── src_py/
│       ├── legacy/storage.py
│       └── simulator/common/
│           ├── battery.py
│           ├── pricing.py
│           ├── specs.py
│           └── time.py
└── fed_trpo/
    └── src/custom/
        └── building.py

src/open_energy_lab/simulator/
├── __init__.py
├── _graph.py
├── _units.py
├── battery.py
├── objective.py
├── pricing.py
└── scenario.py
```

### Target Library Structure

```text
src/
└── open_energy_lab/
    ├── __init__.py
    └── simulator/
        ├── __init__.py
        ├── _graph.py              # internal component graph helpers
        ├── _units.py              # shared units, tolerance, and sign helpers
        ├── battery.py             # existing battery component and transitions
        ├── pricing.py             # existing price signal and rule policy types
        ├── objective.py           # settlement and accounting helpers
        ├── scenario.py            # existing arbitrage scenario plus new multi-component scenario root
        ├── _weather_schema.py     # human-readable weather fields and TMY label mappings
        ├── load.py                # new deterministic load profile types
        ├── weather.py             # new minimal weather inputs and PV-driving helpers
        └── pv.py                  # new PV component and deterministic generation helpers

tests/
├── unit/
│   ├── simulator/
│   └── test_optional_dependency_boundaries.py
├── integration/
│   └── simulator/
├── parity/
└── fixtures/
    └── simulator/
```

**Structure Decision**: Extend the current simulator package instead of
replacing it. Keep the original battery-arbitrage types intact and add a
sibling multi-component scenario surface that reuses `TimeGrid`,
`BatteryComponent`, `PriceSignal`, `DispatchRequestSeries`, and
`DeterministicRulePolicy`. New focused modules for load, weather, and PV keep
the public surface understandable and keep net-grid logic out of the battery
module. The package location `open_energy_lab.simulator` remains stable while
new concrete multi-component types remain experimental until later migrations
promote them.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- how to extend the simulator without breaking the prior battery-arbitrage
  boundary or import-light guarantees
- which battery and settlement semantics remain unchanged from the completed
  MVP
- how load should be represented as deterministic exogenous demand rather than
  as a building or CityLearn abstraction
- how minimal weather inputs should drive deterministic PV generation for this
  feature while preserving human-readable field names plus explicit TMY
  source-label mappings for the included subset
- how one signed net-grid value per step should be computed and settled
- why the built-in deterministic rule remains price-only even in a richer
  environment
- why targeted deterministic invariants remain the correct validation standard
  instead of broad legacy replay

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): entities, relationships, and state
  transitions for the battery + load + PV simulator MVP.
- [contracts/scenario-contract.md](./contracts/scenario-contract.md): required
  scenario inputs, explicit component relationships, and execution modes.
- [contracts/weather-pv-contract.md](./contracts/weather-pv-contract.md):
  minimal weather inputs, human-readable field naming plus TMY mappings, PV derivation rules,
  and deferred weather scope.
- [contracts/grid-settlement-contract.md](./contracts/grid-settlement-contract.md):
  net-grid sign conventions, energy-balance equation, and settlement rules.
- [contracts/validation-case.md](./contracts/validation-case.md): deterministic
  fixture shape, invariant checks, tolerances, and provenance expectations.
- [quickstart.md](./quickstart.md): review and implementation commands for the
  feature.

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate implementation tasks in this
order:

- add or extend simulator-core tests first for load, weather, PV, net-grid
  accounting, and the extended scenario contract
- add fixture scaffolding and provenance notes for the new deterministic
  battery + load + PV cases, including human-readable weather fields and TMY
  source-label mappings
- implement focused simulator modules for `load.py`, `weather.py`, and `pv.py`
  plus the multi-component scenario and settlement extensions
- keep the prior battery transition semantics unchanged except where shared
  helpers are reused
- add unit tests for one-net settlement, energy-balance invariants, weather to
  PV derivation, weather-field mapping preservation, and the price-only
  deterministic rule behavior in the richer environment
- add integration tests for both explicit-dispatch and `price_threshold`
  execution paths over the same multi-component balance rules
- update import-boundary tests, migration docs, quickstart notes, and parity
  documentation to reflect the new feature boundary
- avoid tasks that introduce CityLearn-derived runtime compatibility, broader weather
  subsystem migration, real data ingestion, MPC, RL, solver-backed planning, or
  notebook and W&B workflows

## Quality Gates

Before this plan is considered complete:

- No unresolved clarification markers remain in the plan or design artifacts.
- The feature documents exact legacy references, preserved/improved/rejected
  behavior, dependency boundaries, and validation expectations.
- The scenario, weather/PV, grid-settlement, and validation contracts agree on
  sign conventions, timestep rules, default tolerance, one-net settlement,
  price-only built-in rule behavior, and human-readable weather-field names
  plus TMY mappings for included inputs.
- `AGENTS.md` points to this plan as the active Spec Kit context.

Expected implementation-stage checks after tasks exist:

```bash
uv run pytest tests/unit/simulator tests/integration/simulator tests/unit/test_optional_dependency_boundaries.py
uv run python -c "import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit/simulator tests/integration/simulator
```

Optional legacy-reference checks when local prerequisites are satisfied:

```bash
cd legacy/old_tpm && python scripts/test_battery_consistency.py
```

## Complexity Tracking

No constitution violations are currently expected. Keep this section empty
unless later task planning introduces a justified exception.
