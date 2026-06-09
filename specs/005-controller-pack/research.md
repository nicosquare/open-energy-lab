# Research: Native Controller Pack

## Decision: Promote `open_energy_lab.control` to the First Native Controller Package

**Decision**: Use `src/open_energy_lab/control` as the public package for the
first shipped controller implementations, while keeping
`open_energy_lab.core` as the stable contract owner and
`open_energy_lab.simulator` as the execution owner.

**Rationale**: The previous feature established a stable controller contract
and deterministic runner. This feature needs a reusable library-facing home
for actual controller implementations, and `open_energy_lab.control` was
already reserved as the natural package for that surface. Promoting it now
keeps responsibilities clear: `core` defines the contract, `simulator`
executes episodes, and `control` ships controller logic.

**Alternatives considered**: Keeping concrete controllers inside
`open_energy_lab.simulator` would blur the boundary between execution and
policy logic. Keeping them in `open_energy_lab.core` would mix reusable
contracts with opinionated controller implementations. Deferring
`open_energy_lab.control` again would leave the library without any native
controller offering.

## Decision: Ship Three Deterministic Controllers in the First Pack

**Decision**: Ship:

- a price-threshold controller for `ArbitrageScenario`
- an SOC guardrail controller for both `ArbitrageScenario` and
  `BatteryLoadPVScenario`
- a PV self-consumption controller for `BatteryLoadPVScenario`

**Rationale**: The spec requires price-threshold and SOC guardrail behavior at
minimum, and the current controller boundary already exposes `load_kw` and
derived `pv_generation_kw` as current-step `step_inputs`. That means PV
self-consumption behavior fits the existing stable contract without widening
the boundary or introducing forecasts. The three-controller set yields a clean
support matrix that covers both migrated scenario families with native
controllers while keeping behavior simple and deterministic.

**Alternatives considered**: Deferring PV self-consumption would be acceptable
only if the current-step boundary lacked the required exogenous inputs, but
the existing `BatteryLoadPVScenario` context already provides them. Making the
price-threshold controller support every scenario family would add scope
without increasing coverage, because the guardrail and PV controllers already
cover the battery-plus-PV case more directly.

## Decision: Use Typed Per-Controller Configurations With Explicit Validation

**Decision**: Define one typed configuration surface per shipped controller:

- `PriceThresholdConfig`
- `SocGuardrailConfig`
- `PVSelfConsumptionConfig`

Each configuration defines only deterministic thresholds, limits, and
controller metadata needed for one-step behavior.

**Rationale**: The feature is about reusable library controllers, so callers
need clear, typed configuration rather than ad hoc dictionaries or
constructor-only conventions. Per-controller config types keep validation
close to the public surface, make unsupported combinations explicit, and
support documentation and tests without introducing global schemas or optional
dependency stacks.

**Alternatives considered**: A single generic controller-config dictionary
would weaken validation and make the public surface harder to document.
Scenario-specific free-form keyword arguments would be lightweight initially
but make compatibility and deterministic behavior less reviewable.

## Decision: Keep Controller Implementations Deterministic, Stateless, and Current-Step

**Decision**: Shipped controllers should make one decision from the provided
`ControllerContext`, based only on their configuration and current-step
inputs. They should not depend on mutable training state, replay buffers,
random exploration, or hidden cross-step state.

**Rationale**: Deterministic repeated execution is a core requirement, and the
stable controller contract is current-step only. Stateless configuration-driven
controllers make that guarantee easy to validate and keep the package import
surface minimal.

**Alternatives considered**: Stateful controllers with hidden memory would
complicate reproducibility and make fixture expectations harder to reason
about. Training-oriented agents would violate the feature’s explicit reject
list.

## Decision: Make Scenario Support Explicit Per Controller

**Decision**: Each shipped controller must publish the scenario families it
supports, and unsupported scenario usage must fail immediately and
deterministically.

The initial support matrix is:

- `PriceThresholdController`: `ArbitrageScenario`
- `SocGuardrailController`: `ArbitrageScenario`, `BatteryLoadPVScenario`
- `PVSelfConsumptionController`: `BatteryLoadPVScenario`

**Rationale**: Explicit support declarations keep scope bounded and avoid
accidental compatibility claims. They also let tests verify the public package
surface without inferring support from partial behavior or legacy precedent.

**Alternatives considered**: Silent best-effort behavior across all scenarios
would hide boundary errors. Documenting support only in prose without a stable
declaration would make import-time discovery and test coverage weaker.

## Decision: Use Deterministic Tie-Breaking Rules Instead of Ambiguous Heuristics

**Decision**: Each shipped controller must document deterministic neutral-zone
rules:

- exact price-threshold equality resolves to idle
- exact SOC boundary equality does not trigger corrective action beyond the
  boundary it already satisfies
- exact load/PV balance resolves to idle for the PV self-consumption
  controller

**Rationale**: Threshold-driven controllers often become ambiguous at
boundaries. Explicit tie rules eliminate hidden nondeterminism and make
fixtures simpler to review.

**Alternatives considered**: Leaving tie behavior implicit would still be
implementable, but reviewers would have to infer boundary semantics from code
or floating-point accidents.

## Decision: Promote `open_energy_lab.control` Package-Root Exports to Stable Public API

**Decision**: Treat the package-root imports for shipped controllers and typed
configs in `open_energy_lab.control` as stable public API for this feature,
and document that promotion in `docs/migration/api-maturity.md`.

**Rationale**: The feature’s main value is a reusable native controller
surface. Shipping it only as an undocumented experimental namespace would
undercut the point of the work. The package can meet the repository’s stable
API criteria by combining focused tests, explicit dependency boundaries,
documented support semantics, and migration notes.

**Alternatives considered**: Marking the entire control package experimental
would reduce commitment risk, but the project would still need to promote some
public controller surface later. Stable root-level exports now are more
coherent with the user’s stated goal.

## Decision: Validate With Controller-Specific Fixtures and Preserved-Path Regressions

**Decision**: Add small deterministic validation cases for each shipped
controller and keep the current explicit-dispatch and built-in simulator rule
paths as preserved regression baselines.

**Rationale**: The control pack should prove native controller behavior, not
simulate broad legacy parity. Controller-specific fixtures provide direct
evidence that the shipped controllers behave as documented, while preserved
baseline checks ensure the new package does not break existing simulator entry
paths.

**Alternatives considered**: Reusing only the existing sequence-controller
fixtures would validate the runner but not the shipped control logic. Broad
CityLearn or RL replay is outside scope and would add heavy dependencies.

## Decision: Keep CityLearn and RL Code as Negative-Boundary Evidence Only

**Decision**: Continue treating `legacy/fed_trpo/src/custom/citylearn.py` and
`legacy/fed_trpo/src/utils/cl_torchrl_helper.py` as evidence for what the
native controller pack must reject: environment wrappers, reward coupling,
multi-agent shapes, policy-network assumptions, and heavy runtime
dependencies.

**Rationale**: The user explicitly rejected CityLearn integration and RL
training goals. The value of those files here is to show why the library needs
small deterministic controller implementations instead of environment adapters.

**Alternatives considered**: Positioning CityLearn compatibility as a future
direction would muddy the feature boundary. Ignoring the legacy RL references
entirely would lose useful justification for the narrowed native surface.
