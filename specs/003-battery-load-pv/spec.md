# Feature Specification: Deterministic Battery Load PV Scenario MVP

**Feature Branch**: `003-battery-load-pv`  
**Created**: 2026-05-17  
**Status**: Draft  
**Input**: User description: "Specify the next simulator migration for Open Energy Lab as a deterministic battery + load + PV scenario MVP under `src/open_energy_lab/simulator`."

## Purpose *(mandatory)*

Extend the simulator from a battery-plus-price-only case into a deterministic
multi-component scenario that also represents exogenous demand, weather-driven
PV behavior, and resulting net-grid import or export behavior. This moves Open
Energy Lab from a single-component storage example toward a more realistic but
still reviewable simulator core.

The outcome is a typed, deterministic scenario MVP that can express battery,
load, PV, and grid settlement interactions with small synthetic fixtures and
without expanding the simulator core into planning, optimization, RL, or
external data integration.

## Clarifications

### Session 2026-05-17

- Q: For the battery + load + PV MVP, how should grid settlement treat per-step net-grid behavior? → A: Use one net-grid value per timestep: import if net is positive, export if net is negative, never both at once.
- Q: For the battery + load + PV MVP, where should the battery charge/discharge decisions come from? → A: Support both explicit dispatch requests and one built-in deterministic battery rule in this MVP.
- Q: Should weather remain out of scope for the battery + load + PV MVP? → A: No. This spec should migrate the weather model needed for PV behavior.
- Q: How broad should the weather-model migration be in this spec? → A: Migrate only the minimal weather model needed to generate deterministic PV output for the MVP scenarios.
- Q: In this spec, what inputs should the built-in deterministic battery rule use? → A: The built-in deterministic battery rule still uses price only; load and PV affect the resulting net-grid trace, not the rule itself.

## Scope Classification *(mandatory)*

- **Feature type**: Migration
- **Target surface**: Public library simulator surface plus internal simulator
  module behavior needed for deterministic multi-component validation
- **Legacy reference paths**:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/old_tpm/src_py/simulator/common/specs.py`
  - `legacy/fed_trpo/src/custom/building.py`
- **New-code location**:
  - `src/open_energy_lab/simulator`
  - matching validation under `tests/unit`, `tests/integration`,
    `tests/parity`, and `tests/fixtures` as needed

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Assemble a Multi-Component Scenario (Priority: P1)

As a maintainer, I need a deterministic scenario that combines battery, load,
PV, and grid accounting so that the simulator core can represent a realistic
energy-balance case without leaving the lightweight library boundary.

**Why this priority**: The current simulator proves battery arbitrage only. The
next meaningful step is to add the smallest multi-component case that exercises
component composition and net-grid accounting.

**Independent Test**: A reviewer can assemble a typed scenario containing a
time grid, battery, load profile, PV profile, price profile, and grid
accounting rules, then verify that the scenario structure makes all component
relationships explicit.

**Acceptance Scenarios**:

1. **Given** a deterministic time grid, battery, load profile, PV profile, and
   price profile, **When** a scenario is assembled, **Then** the resulting
   scenario expresses battery, load, PV, and grid relationships through typed
   simulator concepts and explicit component links.
2. **Given** a reviewer inspecting the composed scenario, **When** they trace
   component relationships, **Then** they can identify how load, PV, battery,
   and net-grid accounting interact without inferring hidden behavior from
   hard-coded case logic.

---

### User Story 2 - Validate Net-Grid Energy Balance and Settlement (Priority: P2)

As a researcher, I need deterministic validation evidence for battery, load,
PV, and net-grid outcomes so that the extended simulator behavior can be
trusted before broader simulator growth.

**Why this priority**: The feature is only useful if the new component
interactions are verified through explicit energy-balance and settlement
invariants rather than by intuition.

**Independent Test**: A reviewer can run or inspect one or more small
synthetic scenarios and confirm expected net-grid import or export behavior,
settlement totals, battery state bounds, and repeated deterministic execution.

**Acceptance Scenarios**:

1. **Given** a fixed synthetic scenario with battery, load, PV, and price
   inputs, **When** the scenario is evaluated repeatedly, **Then** it produces
   the same component traces, net-grid trace, and settlement totals each time.
2. **Given** a documented validation fixture, **When** net-grid behavior is
   derived from load, PV, and battery traces, **Then** the observed energy
   balance and settlement outputs satisfy documented invariants and tolerance
   checks.

---

### User Story 3 - Preserve the Lightweight Simulator Core (Priority: P3)

As a library consumer, I need the extended simulator to remain importable
without research-only stacks or service dependencies so that richer scenarios
do not break the simulator-core boundary established by the earlier specs.

**Why this priority**: Load, PV, and grid accounting are a natural place for
scope creep into data adapters, weather models, CityLearn, or optimization. The
feature must make that boundary explicit.

**Independent Test**: A reviewer can verify that the extended simulator core
still imports in the baseline environment and does not require TorchRL,
PyTorch, CityLearn, solver stacks, notebook tooling, W&B, GPU or SLURM
workflows, external tariff APIs, or legacy runtime imports.

**Acceptance Scenarios**:

1. **Given** the baseline local environment, **When** the extended simulator is
   imported and validated, **Then** it does not require heavy optional stacks,
   external services, or legacy package imports.
2. **Given** future ideas such as weather-driven PV, CityLearn adapters, or
   optimization, **When** they are referenced by this feature, **Then** they
   are clearly framed as deferred optional follow-on work rather than simulator
   core requirements.

### Edge Cases

- PV generation exceeds load during some steps, causing net export even without
  battery discharge.
- Load remains positive while PV is zero, causing pure import periods.
- Battery dispatch requests or deterministic rules would imply infeasible
  charge/discharge behavior once load, PV, and battery constraints are combined.
- Grid import/export totals appear numerically balanced but violate per-step
  energy-balance relationships.
- A proposed PV representation depends on weather-model migration instead of a
  simple deterministic exogenous profile.
- A future adapter concern such as CityLearn, ENTSO-E, or notebook execution is
  accidentally introduced into simulator-core imports or fixtures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST extend the simulator MVP under
  `src/open_energy_lab/simulator` to represent a deterministic scenario with
  battery storage, exogenous load, exogenous PV, and net-grid accounting.
- **FR-002**: The feature MUST define typed simulator concepts for load or
  demand, PV or generation, weather behavior needed to drive PV, and net-grid
  import/export behavior on the same time grid used by the battery and price
  signal.
- **FR-003**: The feature MUST preserve the explicit component-graph direction
  of the simulator so that scenarios are composed from typed components and
  explicit relationships rather than one-off case logic.
- **FR-004**: The feature MUST define how net-grid behavior is derived from
  load, PV, and battery traces for every simulation step.
- **FR-004a**: The feature MUST settle each timestep on one net-grid value
  only: import when net grid is positive, export when net grid is negative, and
  never both within the same timestep for this MVP.
- **FR-005**: The feature MUST preserve deterministic execution and define at
  least one synthetic validation fixture for the extended multi-component case.
- **FR-005a**: The feature MUST support both explicit battery dispatch requests
  and one built-in deterministic battery rule so that future external
  controllers can drive the simulator through the explicit-dispatch boundary
  while the MVP still retains a self-contained deterministic baseline.
- **FR-005b**: The built-in deterministic battery rule in this feature MUST use
  price only. Load and PV affect the resulting battery environment and net-grid
  trace, but they MUST NOT change the built-in rule inputs for this MVP.
- **FR-006**: The feature MUST define expected invariants for energy balance,
  battery state-of-charge bounds, realized battery power limits, net-grid
  import/export consistency, settlement totals, and deterministic repeated
  execution.
- **FR-007**: The feature MUST preserve the current battery physical
  constraints, timestep-in-hours semantics, and discounted or otherwise
  explicit grid settlement semantics already established by the battery
  arbitrage MVP.
- **FR-008**: The feature MUST require future implementation work to cite exact
  legacy files actually used as evidence for load, PV, battery, pricing, time,
  and grid-accounting behavior.
- **FR-009**: The feature MUST identify which legacy semantics are preserved,
  improved, or explicitly rejected for load, PV, and grid behavior.
- **FR-010**: The feature MUST keep simulator-core imports lightweight and MUST
  NOT require TorchRL, CityLearn, PyTorch, solver-backed optimization, W&B,
  notebook execution, GPU or SLURM tooling, external API clients, or Rust
  toolchain support as core requirements.
- **FR-011**: The feature MUST classify any new dependency as core, optional,
  external-service-backed, hardware-bound, or legacy-only.
- **FR-012**: The feature MUST define the required fixture shape for time grid,
  battery, load profile, PV profile, price profile, expected net-grid behavior,
  and settlement or invariant checks.
- **FR-013**: The feature MUST keep fixtures small, deterministic, reviewable,
  and committed with provenance and refresh notes.
- **FR-014**: The feature MUST state the public API maturity expectation for
  the extended simulator surface, including which exported concrete types remain
  experimental even though `open_energy_lab.simulator` is the stable package
  location.
- **FR-015**: The feature MUST explicitly defer planning implementations,
  control implementations beyond deterministic scenario execution, RL training
  loops, federated workflows, TorchRL adapter implementation, CityLearn runtime
  integration, solver-backed optimization, notebook-first workflows, W&B
  logging integrations, GPU or SLURM execution paths, Rust bindings, and broad
  migration of unrelated simulator modules.
- **FR-016**: The feature MUST keep real-world tariff downloads and ENTSO-E or
  similar external adapters out of scope.
- **FR-017**: The feature MUST define the weather-model scope required for PV
  behavior and keep that scope limited to the parts necessary for deterministic
  simulator validation in this feature.
- **FR-017a**: The weather migration in this feature MUST include only the
  weather inputs and transformation logic needed to generate deterministic PV
  output for the MVP scenarios, and MUST defer unrelated weather consumers and
  broader weather-system behavior to later migrations.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/old_tpm/src_py/simulator/common/specs.py`
  - `legacy/fed_trpo/src/custom/building.py`
- **Behavior to preserve**: Battery physical constraints, timestep semantics,
  explicit pricing semantics, weather-driven PV semantics, and any
  load/PV/grid-accounting behavior that is supported by clear deterministic
  evidence.
- **Behavior to improve or drop**: Hidden assumptions about net-grid behavior,
  coupling to broader building or CityLearn abstractions, undocumented load/PV
  semantics, and any reliance on heavyweight runtime stacks for the simulator
  core.
- **Parity evidence**: Small deterministic fixtures, expected component traces,
  expected net-grid traces, energy-balance invariants, settlement checks, and
  explicit rationale where broad legacy replay is not the right standard.

### Key Entities *(include if feature involves data or API design)*

- **Load Component**: Exogenous demand profile aligned to the time grid,
  representing consumption that contributes to net-grid import or reduces
  available export.
- **PV Component**: Exogenous deterministic generation profile aligned to the
  time grid, representing available local generation that offsets load or
  creates export.
- **Weather Component**: Time-aligned weather inputs and derived behavior
  needed to produce deterministic PV generation in the migrated simulator
  scenario, limited to the smallest weather scope required by this MVP.
- **Net Grid Trace**: Per-step import/export results derived from load, PV, and
  battery behavior, expressed as one net-grid value per timestep plus any
  associated settlement values or invariants.
- **Extended Scenario**: A composed simulator scenario that ties time grid,
  battery, load, PV, pricing, and grid accounting into one deterministic case,
  using either explicit dispatch requests or one built-in deterministic battery
  rule. The built-in rule remains price-driven even when load and PV are
  present.
- **Validation Fixture**: A small synthetic artifact defining component inputs,
  expected net-grid behavior, and tolerance-backed invariant checks.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Only dependencies compatible with the baseline
  simulator-core environment and justified by deterministic scenario execution.
- **Optional dependencies**: Future TorchRL, PyTorch, CityLearn, solver,
  notebook, logging, GPU/SLURM, or external-data adapters remain optional and
  outside simulator core.
- **External services**: None are required for default imports, fixtures, or
  validation of this feature.
- **Hardware assumptions**: CPU-only local validation remains the default
  expectation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can identify the added simulator behavior for battery,
  load, PV, and net-grid accounting in under 10 minutes from the specification
  and validation artifacts alone.
- **SC-002**: The feature defines at least one deterministic synthetic scenario
  where repeated execution from the same fixed inputs yields the same battery,
  load, PV, net-grid, and settlement outputs.
- **SC-003**: The extended scenario defines explicit energy-balance and
  settlement checks such that a reviewer can verify whether net-grid behavior
  is correct without relying on undocumented assumptions.
- **SC-004**: The simulator-core boundary remains intact: the feature can be
  reviewed and validated without requiring heavy research stacks, external
  tariff/data services, or legacy runtime imports.

## Assumptions

- Researchers and maintainers will use this feature from Python inside the
  unified library rather than through legacy scripts.
- Load is represented initially as a deterministic exogenous profile.
- PV behavior in this feature depends on a migrated weather component rather
  than a standalone fixed profile.
- The weather component migrated here is intentionally limited to the PV
  generation path and is expected to be extended by later dedicated weather
  migrations if broader weather behavior is needed.
- The existing battery-arbitrage semantics for battery constraints, timestep
  handling, and explicit settlement remain the baseline unless this feature
  documents a specific extension.
- Small synthetic fixtures are sufficient evidence for the first multi-component
  scenario and are preferable to real-world data ingestion at this stage.
- Legacy code remains reference-only unless a future migration explicitly moves
  behavior into the unified library.
