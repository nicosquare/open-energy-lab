# Feature Specification: External Controller Boundary MVP

**Feature Branch**: `004-name-controller-boundary`  
**Created**: 2026-05-20  
**Status**: Draft  
**Input**: User description: "Specify the next simulator migration for Open Energy Lab as an external controller boundary MVP under src/open_energy_lab/simulator."

## Purpose *(mandatory)*

Define a clean controller-facing boundary around the deterministic simulator
core so future MPC, heuristic, and RL systems can propose dispatch without
moving control, training, or optimizer concerns into `open_energy_lab.simulator`.
This feature strengthens the unified library architecture by making the
separation between simulator responsibilities and controller responsibilities
explicit, typed, and testable.

## Scope Classification *(mandatory)*

- **Feature type**: Migration
- **Target surface**: Public library API and internal simulator evaluation boundary
- **Legacy reference paths**:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/fed_trpo/src/custom/building.py`
  - `legacy/fed_trpo/src/utils/`
  - `legacy/fed_trpo/src/algos/`
- **New-code location**: `src/open_energy_lab/simulator`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define a Controller-Facing Boundary (Priority: P1)

A library consumer wants a typed way to provide controller-produced dispatch to
the simulator without directly depending on scenario internals or reimplementing
simulator sign conventions.

**Why this priority**: Without a stable controller boundary, future controller
work risks coupling directly to scenario internals and undermining the clean
simulator core established by the previous migrations.

**Independent Test**: A focused unit test proves that a controller receives a
typed context object, returns a typed dispatch proposal, and that proposal can
be validated for sign convention and time alignment before scenario evaluation.

**Acceptance Scenarios**:

1. **Given** a deterministic simulator context for a valid horizon, **When** a
   controller produces a dispatch proposal, **Then** the proposal is represented
   through a typed controller-output surface that preserves the established
   positive-means-charge convention.
2. **Given** a controller proposal with the wrong horizon length or mismatched
   alignment, **When** it is submitted to the simulator boundary, **Then** the
   boundary rejects it before simulation begins.

---

### User Story 2 - Evaluate Controller-Driven Simulation Deterministically (Priority: P2)

A maintainer wants to evaluate controller-driven dispatch through the simulator
using the same deterministic battery, PV, load, and settlement semantics that
already exist for explicit dispatch and built-in rule execution.

**Why this priority**: A controller boundary is only useful if it feeds the
existing simulator behavior without changing responsibility for feasibility,
physics, or settlement.

**Independent Test**: An integration case proves that the same controller and
scenario inputs reproduce the same dispatch trace, realized simulator trace,
and aggregate result across repeated runs.

**Acceptance Scenarios**:

1. **Given** a deterministic battery-arbitrage or battery-load-PV scenario and
   a controller that returns a dispatch proposal, **When** the simulator
   evaluates that proposal, **Then** battery feasibility enforcement remains in
   simulator core and the result is deterministic.
2. **Given** a controller proposal that exceeds feasible battery behavior,
   **When** the simulator evaluates it, **Then** the simulator clamps or
   constrains the realized behavior using the same physics rules already
   established by the current core.

---

### User Story 3 - Preserve a Lightweight Core While Enabling Future Adapters (Priority: P3)

A maintainer wants the controller boundary to remain generic enough for later
MPC or RL adapters while keeping the simulator import path free of training,
optimizer, or research-stack dependencies.

**Why this priority**: This feature is intended to unlock future control work
without collapsing the boundary between core simulation and optional research
systems.

**Independent Test**: Import-boundary and legacy-isolation tests prove that the
new controller-facing surface can be imported without TorchRL, PyTorch,
CityLearn, solver stacks, or runtime `legacy/*` dependencies.

**Acceptance Scenarios**:

1. **Given** the controller-boundary modules are imported from
   `open_energy_lab.simulator`, **When** the import completes, **Then** no heavy
   optional research stacks are loaded.
2. **Given** the controller boundary cites legacy references as evidence,
   **When** the new modules are scanned, **Then** they do not import `legacy/*`
   at runtime.

### Edge Cases

- A controller returns fewer or more dispatch steps than the scenario horizon.
- A controller returns a proposal using the wrong sign convention.
- A controller receives a context for one scenario type and tries to emit a
  proposal incompatible with that scenario horizon.
- A controller proposal is valid in shape but infeasible in energy or power,
  requiring simulator-side clamping.
- A controller result is deterministic but built from incomplete scenario
  context, and the boundary must reject missing required inputs.
- Legacy control code may exist in `legacy/fed_trpo`, but behavior that depends
  on training loops, replay buffers, or CityLearn runtime must not be preserved
  in core.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST define a typed controller-facing surface for the
  deterministic simulator core under `src/open_energy_lab/simulator`.
- **FR-002**: The feature MUST define typed controller input describing the
  state and context needed for dispatch proposal generation.
- **FR-003**: The feature MUST define typed controller output representing a
  dispatch proposal or dispatch proposal series using the existing positive
  means charge convention.
- **FR-004**: The feature MUST define a simulator evaluation entry point that
  accepts controller-produced dispatch without requiring controllers to bypass
  or duplicate simulator physics enforcement.
- **FR-005**: The feature MUST preserve the existing deterministic simulator
  behavior, including timestep semantics, battery feasibility enforcement, and
  settlement behavior.
- **FR-006**: The feature MUST preserve the existing explicit dispatch path and
  MUST NOT replace it with controller-specific logic.
- **FR-007**: The feature MUST preserve the built-in deterministic rule path as
  an available baseline where it remains relevant to deterministic validation.
- **FR-008**: The feature MUST define where controller responsibility ends and
  simulator responsibility begins, with controllers proposing dispatch and the
  simulator enforcing physics and settlement.
- **FR-009**: The feature MUST reject controller proposals with invalid horizon
  length, invalid alignment, or invalid sign semantics before evaluation.
- **FR-010**: The feature MUST define a deterministic controller evaluation
  result or episode result that records the controller proposal and the realized
  simulator outcome.
- **FR-011**: The feature MUST support deterministic repeated execution from
  the same controller inputs, scenario inputs, and configuration.
- **FR-012**: The feature MUST define a small synthetic fixture or fixtures
  covering scenario inputs, controller inputs, controller outputs, and expected
  result behavior.
- **FR-013**: The feature MUST remain compatible with at least one already
  migrated simulator scenario and SHOULD support both battery-arbitrage and
  battery-load-PV scenarios if that can be done without widening scope.
- **FR-014**: The feature MUST keep controller-boundary imports lightweight and
  MUST NOT require TorchRL, PyTorch, CityLearn, solver stacks, notebook
  tooling, W&B, GPU/SLURM tooling, external API clients, or Rust toolchains at
  import time.
- **FR-015**: The feature MUST identify exact legacy reference files used as
  evidence for preserved controller-boundary or dispatch semantics.
- **FR-016**: The feature MUST document which controller-boundary semantics are
  preserved from current explicit dispatch behavior, which are improved, and
  which are rejected.
- **FR-017**: The feature MUST state the public API maturity expectation for
  the new controller-facing surface, including whether concrete controller types
  remain experimental.
- **FR-018**: The feature MUST avoid introducing training loops, replay
  buffers, policy networks, stochastic exploration logic, solver-backed
  optimization, or runtime adapters for MPC, TorchRL, or CityLearn into
  simulator core.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/fed_trpo/src/custom/building.py`
  - additional files under `legacy/fed_trpo/src/utils/` or
    `legacy/fed_trpo/src/algos/` only if they provide interface evidence rather
    than runtime behavior to migrate
- **Behavior to preserve**:
  - explicit dispatch sign convention and alignment semantics
  - simulator-owned battery feasibility enforcement
  - deterministic timestep and settlement behavior already migrated into core
- **Behavior to improve or drop**:
  - controller coupling to broad training/runtime stacks
  - hidden scenario-specific dispatch assumptions
  - any legacy control surface that requires CityLearn, TorchRL, PyTorch, or
    training workflow state at simulator-core import time
- **Parity evidence**:
  - deterministic fixtures
  - typed controller boundary tests
  - repeated execution checks
  - documented invariants rather than broad end-to-end legacy controller replay

### Key Entities *(include if feature involves data or API design)*

- **Controller Context**: A typed view of scenario state and aligned
  controller-relevant inputs for one step or one horizon, including time
  alignment and any scenario data the controller is allowed to inspect.
- **Dispatch Proposal**: A typed controller output describing requested battery
  dispatch over one step or a full horizon using the established sign
  convention.
- **Controller Interface**: A typed boundary that consumes Controller Context
  and produces a Dispatch Proposal without assuming responsibility for physics
  or settlement.
- **Controller Evaluation Result**: A deterministic record linking controller
  input, controller proposal, realized simulator behavior, and aggregate trace
  or settlement outcomes.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**:
  - Python standard library
  - existing `open_energy_lab.simulator` modules
- **Optional dependencies**:
  - TorchRL
  - PyTorch
  - CityLearn
  - solver stacks
  - notebook tooling
  - W&B
- **External services**: None
- **Hardware assumptions**: CPU-only local validation in the existing minimal
  conda plus uv workflow

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can evaluate at least one deterministic
  controller-driven simulation path from typed controller input to deterministic
  simulator result without accessing scenario internals directly.
- **SC-002**: Repeated evaluation of the same controller inputs and scenario
  inputs yields identical dispatch proposals, realized traces, and aggregate
  results within the documented numeric tolerance.
- **SC-003**: Controller proposals with invalid shape, alignment, or sign
  semantics are rejected consistently before simulation in 100% of validation
  cases that exercise those failures.
- **SC-004**: Importing the controller-facing simulator surface does not load
  heavy optional research stacks and does not introduce runtime `legacy/*`
  imports.

## Assumptions

- The target users are researchers and maintainers integrating external control
  logic with the deterministic simulator from Python.
- Controller boundary work should extend the current simulator core rather than
  replace existing explicit dispatch or built-in rule behavior.
- Legacy code remains reference-only evidence unless a future migration
  explicitly promotes additional control behavior.
- Synthetic deterministic fixtures remain the right evidence standard for this
  feature because the goal is interface clarity and deterministic simulator
  evaluation, not controller training quality.
- The first controller-boundary MVP can remain generic and light without
  choosing MPC or RL abstractions yet.
