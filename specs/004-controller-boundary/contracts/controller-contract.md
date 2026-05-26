# Contract: Stable Controller Surface

This contract defines the stable controller-facing API introduced under
`open_energy_lab.core`.

## Purpose

The controller contract must let a library consumer implement a deterministic
or heuristic battery controller without depending on simulator internals,
CityLearn wrappers, TorchRL objects, or training-loop abstractions.

## Required Public Surface

The stable controller surface must include:

- a typed `ControllerContext`
- a typed `DispatchProposal`
- a typed controller interface or protocol
- a typed evaluation-result model that downstream code can inspect without
  reading simulator internals directly

The stable import location is `open_energy_lab.core`.

## Controller Method Shape

The minimum interface must support one-step evaluation:

```text
DispatchProposal propose_dispatch(ControllerContext context)
```

Equivalent protocol or callable shapes are acceptable if they preserve the
same semantics and stable public API.

## Context Semantics

The controller context must provide:

- the active scenario identifier and scenario kind
- the current step index
- the timestep duration in hours
- the current battery state snapshot
- the current-step price inputs
- the current-step exogenous simulator inputs relevant to the active scenario

The context must not provide:

- full-horizon forecast series
- raw scenario objects
- training metadata
- reward state
- solver objects
- tensor-spec or action-space wrappers

## Proposal Semantics

The dispatch proposal must document:

- requested battery power in `kW`
- positive value means charge request
- negative value means discharge request
- controller source or name

The proposal is a request, not a guarantee. Feasibility remains enforced by
the simulator.

## Failure Rules

The controller contract or simulator boundary must reject:

- a proposal that is not single-step
- a proposal with missing or wrong sign-convention metadata
- a proposal built from incomplete required current-step context
- any contract shape that requires optional research dependencies at import
  time

Incomplete required current-step context must be reported as a named
pre-evaluation failure mode so validation can distinguish it from ordinary
controller proposal errors or simulator-side clamping.

## Explicitly Rejected Surface

This MVP does not include:

- multi-agent action arrays
- Gym or TorchRL action spaces
- reward functions
- policy-network modules
- replay buffers
- training or rollout abstractions
- full-horizon optimization contracts

Those patterns remain optional future adapter concerns, not stable core API.
