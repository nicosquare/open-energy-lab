# Implementation Plan: Native Controller Pack

**Branch**: `005-controller-pack` | **Date**: 2026-06-07 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/005-controller-pack/spec.md`

## Summary

Implement the first reusable native controller library under
`src/open_energy_lab/control` on top of the completed controller boundary in
`open_energy_lab.core` and the deterministic evaluation runner in
`open_energy_lab.simulator`. The feature will ship a small deterministic
controller pack with typed configuration surfaces, explicit scenario support,
and import-light package exports, while preserving simulator-owned feasibility
enforcement, settlement behavior, and preserved-path regression coverage for
existing explicit-dispatch and built-in simulator rule flows.

Legacy evidence remains reference-only. Battery and settlement semantics stay
grounded in `legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`,
`legacy/old_tpm/src_py/simulator/common/pricing.py`, and
`legacy/old_tpm/src_py/simulator/common/time.py`. CityLearn-facing reference
material from `legacy/fed_trpo/src/custom/building.py`,
`legacy/fed_trpo/src/custom/citylearn.py`, and
`legacy/fed_trpo/src/utils/cl_torchrl_helper.py` is used only to justify
supported current-step inputs, native controller scope, and rejected
integration directions.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`  
**Primary Dependencies**: Python standard library plus existing `open_energy_lab.core` and `open_energy_lab.simulator` modules; `pytest` for validation. No new required runtime dependencies.  
**Storage/Data**: Markdown design artifacts plus small committed JSON fixtures under `tests/fixtures/simulator`; migration notes under `docs/migration`; default numeric tolerance remains absolute `1e-6`.  
**Testing**: `pytest` for `tests/unit/control`, `tests/integration/control`, `tests/integration/simulator`, preserved-path regression checks, import-boundary scans, and no-legacy-import checks. Existing core and simulator contract tests remain relevant guardrails.  
**Target Platform**: Local CPU-only research workstation using the repository’s uv-managed Python environment  
**Project Type**: Unified research library with stable public APIs under `src/open_energy_lab`; legacy submodules remain reference inputs only  
**Performance Goals**: A deterministic controller-driven episode over short horizons such as 3-24 steps should run in ordinary unit/integration test time on CPU. Repeated runs from the same inputs must produce identical requested dispatch, realized dispatch, and settlement totals within absolute tolerance `1e-6`.  
**Constraints**: No new code in `legacy/*`; no runtime `legacy/*` imports; no TorchRL, PyTorch, CityLearn, solver stacks, W&B, notebook tooling, GPU/SLURM helpers, or external API clients required for ordinary `open_energy_lab.control` imports; controllers stay current-step and deterministic; simulator keeps ownership of feasibility enforcement and settlement.  
**Scale/Scope**: Three shipped native controllers, one typed configuration type per shipped controller, two supported scenario families, one controller instance per episode, deterministic fixtures and invariants for every shipped controller, and one migration note describing preserve/improve/reject outcomes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable code is planned under
  `src/open_energy_lab/control` with supporting docs and tests in the unified
  library structure.
- **Legacy reference boundary**: All cited `legacy/*` files remain
  reference-only evidence.
- **Validation before migration**: The plan requires typed configuration
  validation, deterministic controller fixtures, repeated-run checks,
  preserved-path regression coverage, and import-boundary tests before
  controller behavior is trusted.
- **Dependency isolation**: The control package remains import-light and uses
  the existing core contract plus simulator runner instead of optional research
  stacks.
- **Reproducibility**: The spec fixes deterministic execution, CPU-only
  defaults, current-step controller semantics, explicit scenario support, and
  numeric tolerance.

**Post-design status**: PASS

- Design artifacts define a stable native control package surface, explicit
  shipped controller support matrix, typed configuration validation rules,
  deterministic tie-breaking behavior, and fixture-backed validation evidence.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/005-controller-pack/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── configuration-contract.md
│   ├── control-package-contract.md
│   ├── controller-support-contract.md
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
    ├── control/
    │   ├── __init__.py
    │   ├── price_threshold.py
    │   ├── soc_guardrail.py
    │   ├── pv_self_consumption.py
    │   └── _config.py
    ├── core/
    │   ├── __init__.py
    │   └── controller.py
    └── simulator/
        ├── __init__.py
        ├── controller_runner.py
        └── scenario.py

tests/
├── unit/
│   ├── control/
│   ├── core/
│   └── simulator/
├── integration/
│   ├── control/
│   └── simulator/
├── parity/
└── fixtures/
    └── simulator/

docs/
└── migration/
    ├── api-maturity.md
    └── controller-pack.md
```

**Structure Decision**: Keep `open_energy_lab.core` as the stable contract
owner and `open_energy_lab.simulator` as the deterministic execution owner,
then add `open_energy_lab.control` as the first library-native controller
package that depends on both without widening their responsibilities. The
control package will export shipped controllers and typed configs at its
package root, while controller-specific modules keep the internal
implementation reviewable and import-light.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- why `open_energy_lab.control` is now the right stable home for shipped
  controller implementations after the controller-boundary MVP
- which controller set ships in the first pack and why PV self-consumption is
  included rather than deferred
- how typed configuration surfaces should stay deterministic and lightweight
- how support declarations and unsupported-scenario behavior remain explicit
- how preserved simulator baselines and new controller-pack validation fit
  together without broad legacy controller parity
- how API maturity should be documented for the new control package surface

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): controller-pack entities, configuration
  models, support declarations, and deterministic validation cases
- [contracts/control-package-contract.md](./contracts/control-package-contract.md):
  required public package surface and import-boundary guarantees
- [contracts/controller-support-contract.md](./contracts/controller-support-contract.md):
  shipped controller support matrix, behavior rules, and unsupported-scenario
  handling
- [contracts/configuration-contract.md](./contracts/configuration-contract.md):
  typed configuration expectations and validation rules
- [contracts/validation-case.md](./contracts/validation-case.md):
  deterministic evidence, preserved-path regression requirements, and fixture
  provenance expectations
- [quickstart.md](./quickstart.md): review, implementation, and validation
  commands for the feature

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate implementation tasks in this
order:

- add import-boundary and no-legacy-import tests for `open_energy_lab.control`
  before adding controller implementations
- add unit tests for typed controller configurations and deterministic
  unsupported-scenario handling
- add controller-specific deterministic fixture cases under
  `tests/fixtures/simulator`
- add unit tests for the price-threshold controller and its tie-breaking rules
- add unit tests for the SOC guardrail controller across low-SOC, high-SOC,
  and in-band behavior
- add unit and integration tests for the PV self-consumption controller on
  `BatteryLoadPVScenario`
- add integration tests proving each shipped controller runs through
  `evaluate_with_controller` and produces deterministic repeated results
- add preserved-path regression checks for existing explicit-dispatch and
  built-in simulator rule paths alongside the new controller-pack coverage
- implement `open_energy_lab.control` modules and package exports
- update migration notes, API maturity documentation, and quickstart commands
  to reflect the shipped native controller surface

## Complexity Tracking

No constitution violations currently require justification.
