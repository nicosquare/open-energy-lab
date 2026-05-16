# Feature Specification: Battery Arbitrage Simulator MVP

**Feature Branch**: `002-battery-arbitrage-mvp`  
**Created**: 2026-05-16  
**Status**: Draft  
**Input**: User description: "Specify the first simulator migration for Open Energy Lab as a battery-arbitrage MVP under `src/open_energy_lab/simulator`."

## Purpose *(mandatory)*

Define the first minimal simulator capability that Open Energy Lab can trust as
new library behavior rather than legacy reference material. The feature focuses
on battery arbitrage because it is narrow, economically meaningful, and
sufficient to validate the simulator direction established by the foundation.

The outcome is a reviewable simulator MVP that can represent a simple battery
arbitrage scenario, validate its behavior with deterministic evidence, and keep
future planning, control, RL, and data-adapter work out of the simulator core
until later specs deliberately expand scope.

## Clarifications

### Session 2026-05-16

- Q: For the first battery-arbitrage MVP, how should the arbitrage objective settle discharged energy? → A: Use a discounted export price relative to the import price.
- Q: For the first validation case, where should the battery charge/discharge decisions come from? → A: Support both explicit dispatch requests and one built-in deterministic rule policy in the MVP.
- Q: What API maturity should the initial simulator surface have? → A: Keep `open_energy_lab.simulator` as the stable module location, but treat the first concrete arbitrage types as experimental.
- Q: What numeric tolerance policy should the MVP use for battery state and objective validation? → A: Use one global absolute tolerance of `1e-6` for numeric validation unless a case documents a stricter need.
- Q: If the MVP includes one built-in deterministic rule policy, what should that policy be? → A: Built-in policy is a simple price-threshold rule: charge below threshold, discharge above threshold, otherwise hold.

## Scope Classification *(mandatory)*

- **Feature type**: Migration
- **Target surface**: Public library simulator surface plus internal simulator
  module behavior needed for deterministic validation
- **Legacy reference paths**:
  - `legacy/old_tpm/src_py/simulator`
  - `legacy/old_tpm/src_py/weather`
  - `legacy/old_tpm/src`
  - `legacy/fed_trpo/src/custom`
- **New-code location**:
  - `src/open_energy_lab/simulator`
  - matching validation under `tests/unit`, `tests/integration`,
    `tests/parity`, and `tests/fixtures` as needed

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Assemble a Minimal Arbitrage Scenario (Priority: P1)

As a maintainer, I need a minimal simulator surface for battery arbitrage so
that future simulator work has a concrete starting point inside the unified
library.

**Why this priority**: The project cannot validate simulator migration quality
without first agreeing on the smallest useful scenario shape, component set,
and simulator-core boundary.

**Independent Test**: A reviewer can inspect the scenario definition and verify
that the simulator MVP supports time progression, battery state tracking, price
signals, and market-facing arbitrage behavior without requiring unrelated
subsystems.

**Acceptance Scenarios**:

1. **Given** a deterministic scenario configuration with a time grid, battery,
   and price signal, **When** the simulator scenario is assembled, **Then** the
   resulting scenario is expressed through typed simulator concepts rather than
   hard-coded one-off case logic.
2. **Given** a future reader reviewing the MVP boundary, **When** they inspect
   the feature outputs, **Then** they can identify which concepts are in scope
   for simulator core and which are deferred to later planning, control, RL, or
   adapter specs.

---

### User Story 2 - Validate Deterministic Battery Arbitrage Behavior (Priority: P2)

As a researcher, I need deterministic validation evidence for the first
simulator case so that migrated simulator behavior can be trusted before the
library grows wider.

**Why this priority**: The simulator migration should establish reproducible
validation habits immediately rather than migrate behavior first and justify it
later.

**Independent Test**: A reviewer can run or inspect a synthetic battery
arbitrage case and confirm expected state transitions, energy-balance
properties, and objective-related properties from fixed inputs.

**Acceptance Scenarios**:

1. **Given** a fixed synthetic battery arbitrage configuration, **When** the
   scenario is evaluated repeatedly, **Then** it produces the same outputs and
   state trajectory each time.
2. **Given** a documented validation case, **When** the battery responds to the
   supplied price signal, **Then** the observed behavior satisfies documented
   invariants, expected outputs, or tolerance-based checks.

---

### User Story 3 - Preserve a Lightweight Simulator Core (Priority: P3)

As a library consumer, I need the simulator core to stay importable without
research-only stacks so that ordinary simulator use does not depend on training
frameworks, service accounts, or specialized execution environments.

**Why this priority**: The foundation explicitly separates core library use from
optional research workflows. The first simulator migration is the first real
chance to either preserve or violate that boundary.

**Independent Test**: A reviewer can verify that the simulator MVP does not
make TorchRL, solver stacks, W&B, notebook workflows, GPU/SLURM execution,
external data APIs, or Rust tooling mandatory for simulator-core imports or
default validation.

**Acceptance Scenarios**:

1. **Given** a local environment containing only the foundation baseline,
   **When** the simulator MVP is imported or validated, **Then** it does not
   require TorchRL, solver stacks, W&B, notebooks, GPU/SLURM tooling, or Rust.
2. **Given** future adapter or workflow ideas, **When** they are mentioned in
   the simulator MVP specification, **Then** they are framed as optional
   follow-on work rather than core simulator requirements.

---

### Edge Cases

- The minimal arbitrage case exposes ambiguous conventions for power, energy,
  sign direction, or timestep treatment.
- A legacy simulator pattern depends on weather, external data, or broad
  scenario machinery that is not necessary for the battery arbitrage MVP.
- A useful legacy behavior cannot be reproduced exactly without undocumented
  assumptions, in which case the migration must record what is preserved,
  improved, or rejected.
- A proposed validation case implicitly depends on optional stacks such as
  TorchRL, solver-backed optimization, notebooks, W&B, GPU/SLURM, or Rust.
- A scenario appears deterministic at the API level but still allows hidden
  nondeterminism through omitted initial conditions, missing seeds, or
  unspecified tolerances.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST define a minimal simulator MVP under
  `src/open_energy_lab/simulator` for battery arbitrage scenarios.
- **FR-002**: The feature MUST define typed simulator concepts for time grid or
  timestep handling, units or clearly documented energy/power conventions,
  battery or storage behavior, price signal or tariff behavior, market
  interaction or arbitrage objective representation, and scenario configuration
  or assembly.
- **FR-003**: The feature MUST treat simulator scenarios as component-graph
  compositions rather than hard-coded single-case logic.
- **FR-003a**: The feature MUST support explicit per-step dispatch requests for
  deterministic validation and MAY also provide one built-in deterministic rule
  policy for MVP scenario execution, provided that this policy remains clearly
  separate from future planning and control capabilities.
- **FR-003b**: If a built-in deterministic rule policy is provided, it MUST be
  a simple price-threshold policy that charges below a configured threshold,
  discharges above that threshold, and otherwise holds state.
- **FR-004**: The feature MUST define at least one deterministic synthetic
  battery arbitrage validation case and document the evidence used to trust it.
- **FR-005**: The feature MUST define expected invariants, outputs, tolerances,
  or parity rationale for the battery arbitrage MVP.
- **FR-005a**: The arbitrage objective MUST settle discharged energy using an
  export price that is discounted relative to the import price, and the
  discount rule MUST be explicit in the validation case.
- **FR-005b**: Battery-state, energy-accounting, and objective-validation
  checks MUST use a default absolute numeric tolerance of `1e-6` unless a
  specific validation case documents a stricter requirement.
- **FR-006**: The feature MUST require future implementation work to cite exact
  legacy paths actually used as evidence.
- **FR-007**: The feature MUST identify which legacy behavior is preserved,
  improved, or rejected for the first simulator migration.
- **FR-008**: The feature MUST keep simulator-core imports lightweight and MUST
  NOT require TorchRL, solver-backed optimization, W&B, notebook execution,
  GPU/SLURM workflows, CityLearn runtime, external data APIs, or Rust toolchain
  support as core requirements.
- **FR-009**: The feature MUST classify any new dependency as core, optional,
  external-service-backed, hardware-bound, or legacy-only.
- **FR-010**: The feature MUST define fixtures and committed artifacts using the
  established provenance and regeneration rules from the foundation.
- **FR-011**: The feature MUST state the public API maturity expectation for
  the initial simulator surface, including which parts are stable, experimental,
  or internal-only.
- **FR-011a**: `open_energy_lab.simulator` MUST be the stable module location
  for this migration, while the first concrete battery-arbitrage types and
  helpers remain experimental until a later migration explicitly promotes them.
- **FR-012**: The feature MUST explicitly defer planning implementations,
  control implementations, RL training loops, federated workflows, TorchRL
  adapter implementation, notebook-first workflows, W&B integrations, GPU or
  SLURM execution paths, commercial solver integration, Rust bindings, full
  city-scale simulation, and broad migration of unrelated simulator modules.
- **FR-013**: The feature MUST keep real-data ingestion and source adapters
  such as ENTSO-E out of scope for the simulator MVP, except as future
  non-goals or extension notes.
- **FR-014**: The feature MUST not make weather-model migration part of the MVP
  unless the feature can justify that it is strictly required for the minimal
  battery arbitrage validation case.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**:
  - `legacy/old_tpm/src_py/simulator`
  - `legacy/old_tpm/src_py/weather`
  - `legacy/old_tpm/src`
  - `legacy/fed_trpo/src/custom`
- **Behavior to preserve**: Legacy battery arbitrage semantics that are
  supported by explicit validation evidence, documented assumptions, and a
  coherent simulator-core boundary.
- **Behavior to improve or drop**: Coupling to legacy directory structure,
  undocumented assumptions, notebook-first behavior, unconditional heavyweight
  dependencies, and broad scenario machinery that is not needed for the MVP.
- **Parity evidence**: Deterministic synthetic fixture, expected state
  transitions, energy-balance properties, documented invariants, tolerance-based
  checks, or explicit rationale when direct parity is not the right standard.

### Key Entities *(include if feature involves data or API design)*

- **Time Grid**: Ordered simulation steps and timestep semantics used to
  evaluate scenario progression.
- **Battery Component**: Storage behavior including state, energy movement, and
  constraints relevant to arbitrage.
- **Price Signal**: Time-varying tariff or market-price input that drives the
  arbitrage decision context.
- **Arbitrage Scenario**: A composed scenario that binds battery behavior,
  prices, timing, and market-facing evaluation into one deterministic case,
  using either an explicit dispatch-request series or one built-in
  deterministic rule policy. The built-in rule policy, if present, is a simple
  price-threshold policy.
- **Arbitrage Objective Representation**: The documented way the MVP expresses
  the scenario’s value or market-facing outcome without requiring solver-backed
  optimization, including an explicit discounted export-settlement rule
  relative to import prices.
- **Validation Fixture**: A small synthetic configuration or artifact used to
  reproduce and verify expected arbitrage behavior.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Only dependencies justified by the simulator MVP and
  compatible with the foundation’s minimal conda plus uv workflow.
- **Optional dependencies**: TorchRL and any future adapter, solver, logging,
  notebook, GPU/SLURM, or external-data workflows remain optional and outside
  simulator core.
- **External services**: None are required for default simulator-core imports
  or MVP validation.
- **Hardware assumptions**: CPU-only local validation is the default
  expectation for the MVP.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can identify the first supported simulator use case,
  target module boundary, and validation path in under 10 minutes from the spec
  alone.
- **SC-002**: The battery arbitrage MVP defines at least one deterministic
  validation case whose repeated execution from the same fixed inputs yields the
  same state trajectory and outcome.
- **SC-003**: The simulator MVP can be reviewed for correctness without
  requiring solver licenses, W&B access, notebook execution, GPU/SLURM
  infrastructure, external data credentials, or Rust tooling.
- **SC-004**: Future implementation work can identify exact legacy references,
  preserved/improved/rejected behavior, and tolerance-backed validation
  expectations before code migration begins.
- **SC-004a**: Default deterministic validation checks use a documented
  absolute tolerance of `1e-6`, so reviewers can tell whether numeric drift is
  acceptable or a regression.
- **SC-005**: The simulator MVP boundary remains narrow enough that planning,
  control, RL, TorchRL adapter work, and broad simulator expansion are clearly
  excluded from the first migration.

## Assumptions

- The battery arbitrage MVP is the first simulator migration because it is
  narrow, testable, and aligned with the completed foundation documents.
- The first validation case can rely on synthetic data and deterministic
  configuration rather than real-data ingestion.
- The MVP should express arbitrage behavior and objective-related properties
  without requiring solver-backed optimization as a default path.
- Exact legacy source files will be chosen during planning and implementation,
  but the listed legacy areas are the review starting points.
- Initial simulator surface may include experimental or internal-only parts
  while `open_energy_lab.simulator` remains the stable package location for
  later promotion.
