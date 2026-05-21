# Research: External Controller Boundary MVP

## Decision: Put Stable Controller Contracts in `open_energy_lab.core`

**Decision**: Define the stable controller-facing contract types under
`src/open_energy_lab/core` and reserve `src/open_energy_lab/simulator` for the
deterministic evaluation loop and physics-backed execution path.

**Rationale**: The clarified feature boundary separates controller authorship
from simulator internals. `open_energy_lab.core` is the right stable home for
lightweight reusable contracts, while `open_energy_lab.simulator` already owns
deterministic execution semantics. This split lets future rule-based, MPC, or
RL adapters depend on the same stable contract without forcing them to import
scenario internals.

**Alternatives considered**: Putting the controller contract directly in
`open_energy_lab.simulator` would make the simulator package do double duty as
both interface and execution owner. Using `open_energy_lab.control` now would
create a second public surface before this project has defined the broader
control package shape.

## Decision: Use a Typed Current-Step Protocol Instead of Action-Space Abstractions

**Decision**: Represent the controller API as a small typed protocol plus
dataclasses for `ControllerContext`, `DispatchProposal`, and evaluation
results. The contract is current-step only and uses the established positive
means charge convention.

**Rationale**: The spec explicitly fixed the interface at one step and limited
visible inputs to current-step aligned simulator data. A protocol and standard
library dataclasses fit the existing package style, stay import-light, and do
not pull in Gym, TorchRL, tensor specs, or policy-network assumptions.

**Alternatives considered**: Full-horizon series contracts would widen the
surface and duplicate explicit-dispatch behavior. RL-style action spaces from
`legacy/fed_trpo/src/custom/citylearn.py` and
`legacy/fed_trpo/src/utils/cl_torchrl_helper.py` are useful evidence for what
to reject, not for what the stable core should preserve.

## Decision: Expose Scenario-Relevant Inputs Without Exposing Scenario Internals

**Decision**: Build the controller context from canonical current-step values
that are stable across supported scenario families: battery state, step index,
timestep metadata, current pricing, and current-step exogenous simulator
inputs that are available for the active scenario.

**Rationale**: The user wants controllers to avoid depending on scenario
internals while still being usable for both arbitrage and battery-load-PV.
Canonical current-step values give controllers enough information to act
without tying them to scenario assembly graphs, internal trace classes, or
full-horizon series.

**Alternatives considered**: Passing raw scenario objects would couple callers
to simulator internals. Exposing full future forecasts would violate the
clarified current-step-only boundary. Requiring different public controller
types per scenario would weaken the stable API goal.

## Decision: Let the Simulator Own the Episode Loop

**Decision**: The simulator should own the step-by-step controller evaluation
loop and call the controller once per simulator step.

**Rationale**: Time alignment, context assembly, proposal validation, battery
feasibility enforcement, and trace/result assembly are simulator concerns. A
simulator-owned runner provides one deterministic execution path that works the
same way for both `ArbitrageScenario` and `BatteryLoadPVScenario`.

**Alternatives considered**: A caller-owned loop would force every integrator
to reimplement sequencing and validation around simulator physics. Supporting
both loop owners in the MVP would widen the public surface before the first
stable boundary is proven.

## Decision: Preserve Current Simulator Physics and Explicit Dispatch Semantics

**Decision**: Reuse the existing deterministic simulator battery, timestep,
price, and settlement semantics unchanged and layer controller evaluation on
top of them.

**Rationale**: The boundary feature should add control integration, not reopen
the simulator physics migration. Preserving behavior grounded in
`legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`,
`legacy/old_tpm/src_py/simulator/common/pricing.py`, and
`legacy/old_tpm/src_py/simulator/common/time.py` keeps validation focused on
the new boundary.

**Alternatives considered**: Replacing explicit dispatch with controller-only
logic would break existing validation paths. Reworking battery feasibility or
settlement at the same time would make failures harder to attribute.

## Decision: Reject RL Training, CityLearn Action Parsing, and TorchRL Specs from the Stable Core

**Decision**: Treat `legacy/fed_trpo/src/custom/citylearn.py` and
`legacy/fed_trpo/src/utils/cl_torchrl_helper.py` as negative-boundary
evidence. Preserve only the idea that a controller consumes observations and
produces actions in a repeated loop, while rejecting their training-oriented
types, multi-agent wrappers, reward coupling, and environment dependencies.

**Rationale**: Those legacy files show patterns that are useful later for
optional adapters, but they are too broad for the import-light stable library
boundary required here. The MVP should not inherit `spaces.Box`, tensor specs,
reward metadata, or building-level CityLearn parsing rules.

**Alternatives considered**: Copying their abstractions would lock the library
into a research-stack-specific interface too early. Ignoring them entirely
would miss concrete evidence for why the boundary must stay narrower.

## Decision: Validate the Boundary with Deterministic Fixtures and Import Checks

**Decision**: Validate the feature with one or two tiny deterministic
controller-driven fixtures, repeated-run checks, import-boundary tests, and
legacy-isolation scans.

**Rationale**: The feature’s value is interface clarity plus deterministic
simulator evaluation, not training performance. Focused fixtures are enough to
prove the controller contract, simulator-owned runner, and scenario coverage
without importing optional stacks or reproducing full RL experiments.

**Alternatives considered**: Broad legacy controller replay would depend on
CityLearn and training environments. Performance benchmarking or live external
integrations would add noise without strengthening the contract.
