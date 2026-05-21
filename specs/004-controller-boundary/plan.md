# Implementation Plan: External Controller Boundary MVP

**Branch**: `004-name-controller-boundary` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-controller-boundary/spec.md`

## Summary

Implement the first stable external controller boundary for Open Energy Lab by
splitting responsibilities across two existing library packages: controller
contracts live in `src/open_energy_lab/core`, while deterministic step-by-step
controller evaluation lives in `src/open_energy_lab/simulator`. The feature
must preserve the current battery, timestep, feasibility, settlement, and
import-light guarantees already established in the simulator migrations, while
making controller inputs, controller outputs, and episode evaluation explicit,
typed, and reusable.

Legacy evidence remains reference-only. Battery and timestep semantics continue
to come from `legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`,
`legacy/old_tpm/src_py/simulator/common/pricing.py`, and
`legacy/old_tpm/src_py/simulator/common/time.py`. Control-boundary evidence is
drawn selectively from `legacy/fed_trpo/src/custom/building.py`,
`legacy/fed_trpo/src/custom/citylearn.py`, and
`legacy/fed_trpo/src/utils/cl_torchrl_helper.py` only to justify what is
preserved or rejected at the boundary. The MVP keeps RL, CityLearn, action
space wrappers, reward functions, training loops, and TorchRL-specific
structures out of the stable core contract.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`  
**Primary Dependencies**: Python standard library, existing `open_energy_lab.core` and `open_energy_lab.simulator` modules; `pytest` for validation. Heavy research stacks remain optional and excluded from import-time requirements.  
**Storage/Data**: Markdown design artifacts plus one or two tiny JSON-compatible deterministic controller fixtures under `tests/fixtures/simulator`; default numeric tolerance remains absolute `1e-6`.  
**Testing**: `pytest` for `tests/unit/core`, `tests/unit/simulator`, `tests/integration/simulator`, import-boundary checks, and legacy-isolation scans. Legacy checks may be cited but are not required to pass in the default environment.  
**Target Platform**: Local CPU-only research workstation using the existing minimal conda plus uv workflow  
**Project Type**: Unified research library migration with stable public API in `src/open_energy_lab` and legacy submodules as reference-only evidence  
**Performance Goals**: One deterministic controller-driven episode over a short horizon such as 6-24 steps should execute in normal unit-test time on CPU. Repeated runs from the same inputs must produce identical controller proposals, realized traces, and aggregate settlement results within absolute tolerance `1e-6`.  
**Constraints**: No new code in `legacy/*`; controller contracts are current-step only; `open_energy_lab.simulator` owns the episode loop; both `ArbitrageScenario` and `BatteryLoadPVScenario` must be supported; import paths for `open_energy_lab.core` and `open_energy_lab.simulator` must remain free of TorchRL, PyTorch, CityLearn, solver stacks, W&B, notebook tooling, GPU/SLURM helpers, external API clients, and Rust toolchains.  
**Scale/Scope**: One stable controller contract, one stable simulator evaluation entry point, one controller instance per episode, one dispatch request per simulator step, and deterministic validation for both migrated scenario families. No training, exploration, multi-agent control, stochastic policies, or full-horizon optimizer interfaces are included.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable code stays under `src/open_energy_lab/core` and `src/open_energy_lab/simulator`, with tests under `tests`.
- **Legacy reference boundary**: Legacy files are cited as evidence only and will not be edited for this feature.
- **Validation before migration**: The feature is defined around typed controller contracts, deterministic fixtures, repeated execution checks, import-boundary tests, and explicit `1e-6` tolerance.
- **Dependency isolation**: RL, CityLearn, TorchRL, reward, and training helpers remain outside the stable controller contract and simulator import paths.
- **Reproducibility**: Controller context shape, dispatch sign conventions, per-step evaluation loop ownership, scenario coverage, and validation evidence are documented before implementation.

**Post-design status**: PASS

- Design artifacts define a narrow stable controller contract in `open_energy_lab.core`, a simulator-owned deterministic evaluation boundary in `open_energy_lab.simulator`, and a fixture-first validation strategy across both migrated scenario families.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/004-controller-boundary/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── controller-contract.md
│   ├── simulator-evaluation-contract.md
│   ├── scenario-compatibility-contract.md
│   └── validation-case.md
└── tasks.md
```

### Current Reference Sources

```text
legacy/
├── old_tpm/
│   └── src_py/
│       ├── legacy/
│       │   └── storage.py
│       └── simulator/common/
│           ├── battery.py
│           ├── pricing.py
│           └── time.py
└── fed_trpo/
    └── src/
        ├── custom/
        │   ├── building.py
        │   └── citylearn.py
        └── utils/
            └── cl_torchrl_helper.py
```

### Target Library Structure

```text
src/
└── open_energy_lab/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   └── controller.py          # stable controller contracts and typed context/proposal/result models
    ├── control/
    │   └── __init__.py            # remains deferred scaffold for broader future control work
    └── simulator/
        ├── __init__.py
        ├── scenario.py            # existing scenario types remain authoritative for physics inputs
        ├── battery.py             # existing battery transition rules reused unchanged
        ├── pricing.py             # existing price and built-in rule semantics reused unchanged
        └── controller_runner.py   # simulator-owned controller evaluation loop and validation entry point

tests/
├── unit/
│   ├── core/
│   └── simulator/
├── integration/
│   └── simulator/
├── parity/
└── fixtures/
    └── simulator/
```

**Structure Decision**: Introduce the stable controller contract in
`open_energy_lab.core` rather than in `open_energy_lab.control` or directly in
`open_energy_lab.simulator`. `core` already exists as the intended home for
reusable methods and interfaces, and this MVP needs a narrow stable contract
without committing yet to the broader `control` package surface. The simulator
keeps ownership of the deterministic episode loop in a focused
`controller_runner.py` module so controller authors do not duplicate time
alignment, context assembly, battery feasibility enforcement, or settlement
recording. The existing explicit-dispatch and built-in `price_threshold` paths
remain intact alongside the new controller-driven path.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- why stable controller contracts belong in `open_energy_lab.core` while the
  evaluation loop stays in `open_energy_lab.simulator`
- why the controller surface should be a lightweight typed protocol and
  current-step dataclasses instead of RL action-space wrappers or training
  agent abstractions
- how one evaluation runner should support both `ArbitrageScenario` and
  `BatteryLoadPVScenario` without exposing scenario internals directly
- what existing simulator semantics remain preserved versus what broader
  control-stack behavior is explicitly rejected
- why deterministic fixtures, import-boundary tests, and legacy-isolation
  checks remain the right validation standard for this migration

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): controller contract entities, simulator
  evaluation result shape, validation rules, and scenario compatibility notes
- [contracts/controller-contract.md](./contracts/controller-contract.md):
  required public surface for `open_energy_lab.core`
- [contracts/simulator-evaluation-contract.md](./contracts/simulator-evaluation-contract.md):
  simulator-owned evaluation loop, validation, and result guarantees
- [contracts/scenario-compatibility-contract.md](./contracts/scenario-compatibility-contract.md):
  compatibility rules across `ArbitrageScenario` and `BatteryLoadPVScenario`
- [contracts/validation-case.md](./contracts/validation-case.md):
  deterministic fixture and evidence requirements
- [quickstart.md](./quickstart.md): review, implementation, and validation
  commands for the feature

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate implementation tasks in this
order:

- add contract and import-boundary tests first for `open_energy_lab.core` and
  the new simulator evaluation path
- add deterministic controller fixtures and provenance notes under
  `tests/fixtures/simulator`
- implement `open_energy_lab.core.controller` with typed context, proposal,
  interface, and evaluation-result models
- implement simulator-side controller evaluation in
  `open_energy_lab.simulator.controller_runner`
- extend package-root exports for `open_energy_lab.core` and
  `open_energy_lab.simulator` while keeping imports lightweight
- add scenario compatibility tests for both `ArbitrageScenario` and
  `BatteryLoadPVScenario`
- update migration notes, parity documentation, and quickstart validation
  commands to reflect the new stable boundary

## Complexity Tracking

No constitution violations currently require justification.
