# Implementation Plan: Battery Arbitrage Simulator MVP

**Branch**: `002-battery-arbitrage-mvp` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-battery-arbitrage-mvp/spec.md`

**Note**: This plan covers the first simulator migration only. It does not add
planning, control, RL, notebook, W&B, GPU/SLURM, solver, CityLearn-runtime, or
Rust-bound behavior to the simulator core.

## Summary

Implement the first battery-arbitrage simulator MVP under
`src/open_energy_lab/simulator` as a typed, lightweight, component-graph
scenario surface. The MVP should model time steps, battery physics, price
signals, explicit dispatch requests, an optional built-in deterministic
price-threshold policy, and discounted-export arbitrage settlement well enough
to validate deterministic battery behavior without adding optimizer or
controller logic as a core dependency.

Legacy behavior is drawn selectively from
`legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/scripts/test_battery_consistency.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`,
`legacy/old_tpm/src_py/simulator/common/pricing.py`,
`legacy/old_tpm/src_py/simulator/common/time.py`,
`legacy/old_tpm/src_py/simulator/common/specs.py`, and
`legacy/fed_trpo/src/custom/building.py`. These files are evidence only. The
new MVP keeps the validated battery and tariff semantics, adds explicit
discounted export settlement and one deterministic rule-policy path, improves
type and fixture clarity, and rejects heavyweight environment coupling.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`. Legacy Rust and
legacy Python remain reference-only and are not required for ordinary simulator
imports.

**Primary Dependencies**: Core simulator runtime should stay on the Python
standard library (`dataclasses`, `typing`, `math`, `enum` if needed) plus the
existing package scaffold. `pytest` remains the primary dev dependency for
validation. TorchRL, PyTorch, CityLearn, solver stacks, W&B, notebook tooling,
GPU/SLURM helpers, and Rust toolchains remain non-core and unimported by
simulator-core modules.

**Storage/Data**: Small markdown design artifacts plus synthetic deterministic
scenario fixtures stored as Python test fixtures or tiny JSON-compatible data
under `tests/fixtures` if committed. No external datasets, network APIs, or
generated experiment artifacts are required. Validation defaults to an absolute
numeric tolerance of `1e-6` unless a stricter case is documented.

**Testing**: `pytest` for `tests/unit` and targeted `tests/integration` around
scenario assembly and deterministic simulation traces. `tests/parity` may hold
documented reference checks if a small parity case is justified. Legacy
reference validation may cite `cd legacy/old_tpm && python scripts/test_battery_consistency.py`
when its local import path is available, but that script is supporting evidence
rather than a required default check.

**Target Platform**: Local CPU-only research workstation using the minimal
conda plus uv workflow established by the foundation.

**Project Type**: Python research library migration inside `src/open_energy_lab`
with reference-only legacy inputs.

**Performance Goals**: Deterministic correctness is the primary goal. A single
synthetic arbitrage scenario over a short horizon such as 6-24 time steps
should execute in ordinary unit-test time on CPU with no specialized runtime.
The same fixed inputs must reproduce the same state trace and settlement within
absolute tolerance `1e-6`.

**Constraints**: Keep simulator-core imports lightweight. Do not add new code
to `legacy/*`. Do not require weather, PV, load, CityLearn, solver, TorchRL,
W&B, notebooks, GPUs, SLURM, or Rust to import or validate the MVP. Cite exact
legacy files for migrated behavior. Document units, sign conventions, initial
conditions, floating-point tolerances, and export discount semantics before
implementation.

**Scale/Scope**: One battery, one time grid, one import-price signal, one
arbitrage objective representation with discounted export settlement, and one
deterministic validation fixture. The MVP supports explicit dispatch requests
and one optional built-in deterministic price-threshold policy. Objective
evaluation is accounting over a feasible dispatch trace, not optimization.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable simulator code targets
  `src/open_energy_lab/simulator` and tests target `tests`.
- **Legacy reference boundary**: Exact legacy files are cited as references and
  will not be edited for this feature.
- **Validation before migration**: The MVP is defined around deterministic
  fixtures, battery invariants, explicit discounted-settlement rules, explicit
  `1e-6` default tolerance, and reviewable traces.
- **Dependency isolation**: Heavy research stacks remain optional and outside
  simulator-core imports.
- **Reproducibility**: Time-step conventions, dispatch inputs, rule-policy
  semantics, export discount semantics, tolerance rules, and fixture
  provenance are documented before implementation.

**Post-design status**: PASS

- Design artifacts define the scenario contract, battery contract, and
  validation contract without introducing control loops beyond the explicitly
  allowed deterministic price-threshold policy, solver requirements, or
  external-service assumptions.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-battery-arbitrage-mvp/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── battery-component.md
│   ├── scenario-contract.md
│   └── validation-case.md
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
```

### Target Library Structure

```text
src/
└── open_energy_lab/
    ├── __init__.py
    ├── simulator/
    │   ├── __init__.py
    │   ├── _graph.py              # internal component graph helpers
    │   ├── _units.py              # internal unit/sign conventions
    │   ├── battery.py             # battery component and state transitions
    │   ├── pricing.py             # import/export price signal representation
    │   ├── scenario.py            # scenario assembly and evaluation
    │   └── objective.py           # arbitrage settlement/accounting
    └── experimental/              # optional incubation if implementation needs it

tests/
├── unit/
│   ├── simulator/
│   └── test_import_contract.py
├── integration/
│   └── simulator/
├── parity/
│   └── README.md
└── fixtures/
    └── simulator/
```

**Structure Decision**: Keep the simulator MVP inside
`src/open_energy_lab/simulator`. Use small focused modules for battery, pricing,
objective settlement, and scenario assembly. Graph helpers and unit/sign
conventions stay internal unless later promotion is justified. The package
location `open_energy_lab.simulator` is stable, while the first concrete
arbitrage-specific types remain experimental. No separate control or
optimization module is introduced by this feature.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- Which legacy battery semantics are preserved from the legacy storage model
  and battery consistency script.
- Which time-grid and tariff semantics are preserved from the legacy simulator
  utilities.
- How to model arbitrage as scenario evaluation plus discounted-export
  settlement instead of as a solver or controller while still allowing one
  deterministic price-threshold rule policy.
- Which legacy building and CityLearn-adjacent references are explicitly
  deferred.
- Which units, signs, `1e-6` default tolerance, and fixture conventions are
  required for a trustworthy deterministic MVP.

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): entities, relationships, and state
  transitions for the battery arbitrage MVP.
- [contracts/scenario-contract.md](./contracts/scenario-contract.md): required
  scenario inputs, component graph shape, and assembly rules.
- [contracts/battery-component.md](./contracts/battery-component.md): battery
  fields, invariants, units, and state-transition contract.
- [contracts/validation-case.md](./contracts/validation-case.md): deterministic
  fixture, expected trace checks, tolerances, and provenance expectations.
- [quickstart.md](./quickstart.md): review and implementation commands for the
  simulator MVP.

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate implementation tasks in this
order:

- Add simulator-core modules for time grid, battery, pricing, objective
  settlement, and scenario assembly under `src/open_energy_lab/simulator`.
- Add support for both explicit dispatch-request evaluation and the single
  built-in deterministic price-threshold policy without widening the control
  boundary.
- Add unit tests for battery constraints, timestep handling, price-signal
  alignment, discounted export settlement, deterministic policy behavior, and
  import boundaries.
- Add one deterministic integration case for a synthetic arbitrage trace with
  explicit expected states, discounted-export settlement properties, and
  `1e-6` tolerance-backed assertions.
- Add fixture provenance notes for any committed simulator fixture.
- Add documentation updates describing preserved, improved, and rejected legacy
  behavior plus the dependency boundary for simulator core.
- Avoid tasks that introduce controllers, optimizers, TorchRL adapters,
  notebooks, W&B, GPU/SLURM flows, weather migration, or broad CityLearn
  integration.

## Quality Gates

Before this plan is considered complete:

- No unresolved clarification markers remain in the plan or design artifacts.
- The MVP documents exact legacy references, preserved/improved/rejected
  behavior, dependency boundaries, and validation expectations.
- The scenario, battery, and validation contracts agree on units, signs,
  timestep rules, discounted export settlement, API maturity, and `1e-6`
  default tolerance.
- `AGENTS.md` points to this plan as the active Spec Kit context.

Expected implementation-stage checks after tasks exist:

```bash
uv run pytest tests/unit/simulator tests/integration/simulator
uv run python -c "import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit tests/integration
```

Optional legacy-reference check when local prerequisites are satisfied:

```bash
cd legacy/old_tpm && python scripts/test_battery_consistency.py
```

## Complexity Tracking

No constitution violations are introduced by this plan.
