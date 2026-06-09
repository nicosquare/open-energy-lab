# Feature Specification: Native Controller Pack

**Feature Branch**: `005-controller-pack`  
**Created**: 2026-06-07  
**Status**: Draft  
**Input**: User description: "Specify the next Open Energy Lab feature as a native controller pack under `src/open_energy_lab/control`."

## Purpose *(mandatory)*

Provide the first reusable native controllers in Open Energy Lab so library
consumers can run deterministic control policies through the stable controller
contract and simulator evaluation flow without writing ad hoc controller glue
or depending on legacy runtimes. This feature turns the controller boundary
work into a real library capability while preserving simulator-owned physics,
feasibility enforcement, settlement, and repeated deterministic execution.

## Clarifications

### Session 2026-06-07

- Q: Should the PV self-consumption controller ship in the initial controller pack? → A: Yes, it ships in the initial pack as a stable supported controller for `BatteryLoadPVScenario`.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability
- **Target surface**: Public library API for the native control package and controller-driven simulator evaluation
- **Legacy reference paths**:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/fed_trpo/src/custom/building.py`
  - `legacy/fed_trpo/src/custom/citylearn.py`
  - `legacy/fed_trpo/src/utils/cl_torchrl_helper.py`
- **New-code location**:
  - `src/open_energy_lab/control`
  - `src/open_energy_lab/control/__init__.py`
  - `tests/unit/control`
  - `tests/integration/control`
  - `tests/integration/simulator`
  - `docs/migration`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Shipped Arbitrage Controller (Priority: P1)

A library consumer wants to select a shipped deterministic controller for
battery arbitrage and evaluate it through the native simulator flow without
implementing a custom controller class.

**Why this priority**: This is the first real user-facing control-library
outcome from the controller-boundary work and establishes whether Open Energy
Lab can ship reusable control logic instead of only control scaffolding.

**Independent Test**: A deterministic arbitrage scenario with a documented
controller configuration proves that a shipped controller can be instantiated,
evaluated, and repeated with identical results through the public control
surface.

**Acceptance Scenarios**:

1. **Given** a deterministic arbitrage scenario and a price-threshold
   controller configuration, **When** the consumer evaluates the controller
   through the native control package, **Then** the simulator returns a
   complete controller-driven result without requiring user-authored dispatch
   glue.
2. **Given** the same arbitrage scenario inputs and the same controller
   configuration, **When** the evaluation is repeated, **Then** the requested
   dispatch sequence, realized dispatch sequence, and aggregate settlement are
   identical within the documented numeric tolerance.
3. **Given** a controller configuration that would request behavior beyond
   battery limits, **When** the controller is evaluated, **Then** the
   simulator remains responsible for feasibility enforcement and the result
   records deterministic realized behavior.

---

### User Story 2 - Reuse Guardrail Logic Across Supported Scenarios (Priority: P2)

A maintainer wants the first controller pack to include simple battery-state
heuristics that can protect battery state of charge and, where cleanly
supported by the existing boundary, improve self-consumption behavior for
battery-plus-PV scenarios.

**Why this priority**: Reusable guardrail-style controllers show that the
native control package can express more than one narrow rule while still
remaining deterministic, import-light, and aligned with the stable
current-step controller contract.

**Independent Test**: Scenario-level validation proves that the shipped SOC
guardrail controller works through the shared controller contract, and that any
controller claiming `BatteryLoadPVScenario` support either runs deterministically
through that scenario family or is explicitly documented as out of scope for
this release.

**Acceptance Scenarios**:

1. **Given** a supported scenario and a SOC guardrail configuration, **When**
   the controller is evaluated, **Then** its behavior reflects documented
   battery-state heuristics while leaving feasibility and settlement ownership
   with the simulator.
2. **Given** a `BatteryLoadPVScenario` and a controller advertised for PV-aware
   use, **When** it is evaluated, **Then** it uses only the stable current-step
   information already available at the controller boundary and produces
   deterministic results.
3. **Given** a controller that does not support a scenario family, **When** a
   consumer attempts to use it on that family, **Then** the non-support is
   explicit, deterministic, and documented rather than inferred from legacy
   behavior.

---

### User Story 3 - Keep the Control Package Lightweight and Bounded (Priority: P3)

A maintainer wants the native control package to stay small, dependency-light,
and independent of legacy runtime stacks so it can ship as a reliable library
surface rather than a research environment wrapper.

**Why this priority**: The value of a controller pack is reduced if ordinary
imports pull in optional research stacks or reintroduce CityLearn-shaped
integration goals that the controller-boundary work intentionally rejected.

**Independent Test**: Import-boundary checks and preserved-path regression
tests prove the native control package remains lightweight while existing
explicit-dispatch and built-in simulator rule paths continue to work for the
relevant scenarios.

**Acceptance Scenarios**:

1. **Given** the native control package is imported in a minimal environment,
   **When** the import completes, **Then** it does not require TorchRL,
   PyTorch, CityLearn, solver stacks, W&B, notebook tooling, GPU/SLURM
   tooling, external API clients, or runtime `legacy/*` imports.
2. **Given** controller-pack support is added, **When** existing explicit
   dispatch and built-in simulator rule validations are re-run, **Then** those
   preserved paths remain available and behaviorally unchanged for the
   scenarios they already cover.

### Edge Cases

- A controller receives current-step prices exactly on a configured threshold
  boundary and must resolve the tie deterministically.
- A battery starts at or near its minimum or maximum allowed state of charge,
  so controller heuristics must remain deterministic at boundary conditions.
- A controller configuration contains contradictory thresholds or guardrails
  and must be rejected deterministically before evaluation.
- A PV-aware controller is asked to operate on a scenario that lacks the
  current-step inputs it requires.
- A controller supports only one scenario family and is invoked with another.
- A controller requests power beyond feasible limits and the simulator must
  clamp realized behavior without changing controller determinism.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST define a native controller package under
  `src/open_energy_lab/control` as the first reusable library-owned controller
  surface for Open Energy Lab.
- **FR-002**: The feature MUST ship a deterministic price-threshold controller
  for arbitrage-oriented behavior.
- **FR-003**: The feature MUST ship a deterministic SOC guardrail controller
  that uses simple battery-state heuristics.
- **FR-004**: The feature MUST decide and document whether a PV
  self-consumption controller ships in the initial pack. This feature MUST ship
  a PV self-consumption controller in the initial pack, and it MUST support
  `BatteryLoadPVScenario` through the existing stable current-step controller
  contract.
- **FR-005**: Every shipped controller MUST implement
  `open_energy_lab.core.ControllerInterface`.
- **FR-006**: Every shipped controller MUST execute through
  `open_energy_lab.simulator.evaluate_with_controller`.
- **FR-007**: The feature MUST provide typed configuration inputs for each
  shipped controller, including deterministic validation of invalid
  configuration combinations.
- **FR-008**: The feature MUST define package exports in
  `src/open_energy_lab/control/__init__.py` so users can discover the shipped
  controller surface from the native control package.
- **FR-009**: The feature MUST preserve the stable controller contract in
  `open_energy_lab.core` and MUST NOT introduce a parallel controller protocol
  or alternate simulator entry point for shipped controllers.
- **FR-010**: The simulator MUST remain the sole owner of battery feasibility
  enforcement, state transitions, and settlement behavior for controller-driven
  runs.
- **FR-011**: The feature MUST validate every shipped controller against each
  scenario family it claims to support through `evaluate_with_controller`.
- **FR-012**: The feature MUST show deterministic repeated execution, meaning
  the same controller type, same configuration, and same scenario inputs yield
  the same requested dispatch sequence, realized dispatch sequence, and
  aggregate settlement within absolute tolerance `1e-6`.
- **FR-013**: The feature MUST validate controller behavior through
  deterministic fixtures, invariants, and scenario-level checks rather than
  broad legacy parity runs.
- **FR-014**: The feature MUST preserve and regression-test the existing
  explicit-dispatch path and the built-in simulator rule path wherever those
  paths remain relevant baselines for controller-supported scenarios.
- **FR-015**: The feature MUST include import-boundary checks proving
  `open_energy_lab.control` remains lightweight and does not require TorchRL,
  PyTorch, CityLearn, solver stacks, W&B, notebook tooling, GPU/SLURM tooling,
  external API clients, or runtime `legacy/*` imports.
- **FR-016**: The feature MUST document preserve, improve, and reject
  decisions for the native controller pack in migration-facing documentation.
- **FR-017**: The feature MUST cite exact legacy reference paths only where
  they provide evidence for preserved heuristics, preserved simulator
  semantics, or rejected abstraction directions.
- **FR-018**: The feature MUST publish explicit API maturity for the
  `open_energy_lab.control` package surface and each shipped controller so
  users can tell what is stable at release.
- **FR-019**: The feature MUST define deterministic behavior for unsupported
  scenario family usage and invalid controller configuration handling.
- **FR-020**: The feature MUST reject CityLearn integration or compatibility
  goals, RL training loops, replay buffers, policy networks, stochastic
  exploration logic, solver-backed optimization, multi-agent or federated
  control, full-horizon planning contracts, notebook-first workflows, and
  runtime `legacy/*` imports from the scope of the controller pack.
- **FR-021**: The feature MUST treat CityLearn as reference-only evidence and
  MUST NOT position it as a runtime dependency, adapter target, or compatibility
  promise for the native control package.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/fed_trpo/src/custom/building.py`
  - `legacy/fed_trpo/src/custom/citylearn.py`
  - `legacy/fed_trpo/src/utils/cl_torchrl_helper.py`
- **Behavior to preserve**:
  - stable current-step controller contract usage through the existing
    controller boundary
  - positive dispatch meaning charge, with simulator-owned realization of
    feasible behavior
  - deterministic timestep and settlement semantics already validated in the
    native simulator
  - preserved explicit-dispatch and built-in simulator rule baselines for
    regression coverage
- **Behavior to improve or drop**:
  - improve reusable native controllers, typed configuration surfaces, and
    explicit supported-scenario declarations
  - improve migration documentation for API maturity and bounded scope
  - drop broad legacy parity expectations for controller behavior
  - drop CityLearn-shaped compatibility, training-environment assumptions, and
    legacy runtime coupling
- **Parity evidence**:
  - deterministic scenario fixtures and invariants
  - repeated execution checks
  - preserved-path regression coverage
  - selective legacy citations used only as supporting evidence for heuristics
    or rejected abstraction directions

### Key Entities *(include if feature involves data or API design)*

- **Controller Definition**: A shipped deterministic controller identified by a
  public name, supported scenario families, documented behavior summary, and
  published maturity label.
- **Controller Configuration**: The typed set of thresholds, guardrails, and
  other deterministic settings that fully determine a controller's behavior for
  a scenario.
- **Controller Support Matrix**: The documented mapping between shipped
  controllers and scenario families, including whether a controller supports
  arbitrage, battery-load-PV, or both.
- **Deterministic Evaluation Case**: A scenario fixture, controller
  configuration, and expected invariants used to prove repeatable controller
  behavior.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Existing `open_energy_lab.core` and
  `open_energy_lab.simulator` library surfaces only
- **Optional dependencies**: Heavy research stacks remain excluded from
  ordinary `open_energy_lab.control` import and evaluation
- **External services**: None
- **Hardware assumptions**: CPU-only execution is sufficient for shipped
  controller validation

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Library users can evaluate at least two shipped native
  controllers, including the price-threshold controller and the SOC guardrail
  controller, without writing a custom controller class.
- **SC-002**: For every shipped controller and supported validation case, two
  consecutive runs with identical inputs produce identical requested dispatch
  sequences, identical realized dispatch sequences, and total settlement values
  matching within absolute tolerance `1e-6`.
- **SC-003**: Import-boundary validation shows that `open_energy_lab.control`
  imports successfully without requiring TorchRL, PyTorch, CityLearn, solver
  stacks, W&B, notebook tooling, GPU/SLURM tooling, external API clients, or
  runtime `legacy/*` imports.
- **SC-004**: Existing explicit-dispatch and built-in simulator rule baseline
  validations remain green for the scenarios relevant to the new controller
  pack.
- **SC-005**: Migration-facing documentation explicitly records what the first
  native controller pack preserves, improves, and rejects, and confirms that
  PV self-consumption shipped in the initial controller pack.

## Assumptions

- The stable current-step controller contract introduced in
  `open_energy_lab.core` remains the authoritative controller interface for
  this feature.
- The initial controller pack focuses on deterministic single-step heuristics
  rather than forecast-driven or planner-driven behavior.
- Supported scenario families at release are limited to those already supported
  by `evaluate_with_controller`.
- Selective legacy references are used only as evidence, not as runtime
  dependencies or compatibility targets.
- The existing stable current-step controller boundary already exposes the
  inputs needed for a shipped PV self-consumption controller on
  `BatteryLoadPVScenario`.
