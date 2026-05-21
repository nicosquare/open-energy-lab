# Contract: Simulator-Owned Controller Evaluation

This contract defines how `open_energy_lab.simulator` evaluates a controller
against the deterministic simulator core.

## Purpose

The simulator evaluation boundary must let callers run a controller through the
existing simulator semantics without bypassing physics, duplicating time
alignment logic, or rebuilding settlement traces themselves.

## Required Entry Point

The simulator must expose a stable controller-evaluation entry point that:

- accepts a supported simulator scenario
- accepts a controller implementing the stable core contract
- runs one controller step per simulator step
- validates proposals before step evaluation
- returns a typed controller evaluation result

## Execution Rules

For each simulator step, the runner must:

1. derive a current-step `ControllerContext` from the active scenario
2. call the controller once
3. validate the returned `DispatchProposal`
4. evaluate the step using existing simulator battery and settlement semantics
5. record both requested and realized behavior

The runner owns sequencing. The controller does not.

## Preserved Simulator Semantics

The controller-driven path must preserve:

- battery feasibility enforcement from the existing simulator core
- timestep semantics and alignment rules
- discounted export settlement semantics
- deterministic repeated execution from the same inputs
- the existing explicit-dispatch path and built-in rule path as separate
  validation baselines

## Failure Rules

The evaluation boundary must reject before execution begins when:

- the controller context cannot be built for the active scenario
- the controller proposal is not single-step
- the proposal’s sign semantics are invalid
- the supported scenario’s aligned data are incomplete

The evaluation boundary must record a constraint event rather than fail the
entire episode when:

- the requested battery power is valid in shape but infeasible in physics and
  therefore must be clamped by the simulator

## Result Guarantees

The returned evaluation result must make available:

- the controller identity
- the ordered sequence of controller proposals
- the ordered sequence of realized simulator power values
- per-step settlement or trace linkage
- aggregate settlement outcome
- any constraint events produced by simulator enforcement

The result must be inspectable without requiring direct access to simulator
internal state classes beyond the documented trace or result fields.

## Dependency Boundary

The simulator runner must not import:

- TorchRL
- PyTorch
- CityLearn
- solver libraries
- W&B
- notebook tooling
- GPU or SLURM helpers
- `legacy/*` modules at runtime
