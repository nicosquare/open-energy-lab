# Contract: Arbitrage Scenario Assembly

This contract defines the minimum simulator scenario surface for the first
battery arbitrage MVP.

## Purpose

The scenario contract must let a maintainer assemble a deterministic arbitrage
case from typed components instead of from one-off procedural code. It is a
simulator contract, not a control or optimization contract.

## Required Components

Every MVP scenario must include:

- `TimeGrid`
- `BatteryComponent`
- `PriceSignal`
- `ArbitrageObjectiveRepresentation`

Every MVP scenario must also include one of:

- `DispatchRequestSeries`
- `DeterministicRulePolicy`

Optional components are allowed only when they do not widen the dependency
boundary. Weather, PV, load, building, and CityLearn-facing components are out
of scope for the first MVP unless the spec is amended.

## Graph Shape

The composed scenario must make the following relationships explicit:

```text
TimeGrid -> PriceSignal
BatteryComponent -> SimulationTrace
PriceSignal -> ArbitrageObjectiveRepresentation
SimulationTrace -> ArbitrageObjectiveRepresentation
```

When dispatch requests are used:

```text
TimeGrid -> DispatchRequestSeries
DispatchRequestSeries -> BatteryComponent
```

When the built-in rule policy is used:

```text
TimeGrid -> DeterministicRulePolicy
PriceSignal -> DeterministicRulePolicy
DeterministicRulePolicy -> BatteryComponent
```

The graph may be represented with simple typed objects and documented
connections. It does not need a general-purpose graph library.

## Required Inputs

At minimum, the assembled scenario must declare:

- timestep duration in hours
- number of steps
- battery capacity and power limits
- battery efficiency assumptions
- initial state of charge
- explicit price series aligned to the time grid
- explicit dispatch requests aligned to the time grid or one built-in
  deterministic rule policy
- export price discount rule relative to import price
- objective settlement rules

## Sign and Unit Conventions

The scenario contract must document:

- energy in `kWh`
- power in `kW`
- state of charge as fraction in `[0.0, 1.0]`
- timestep duration in hours
- positive dispatch request = charge request
- negative dispatch request = discharge request

Any deviation from these conventions must be rejected or explicitly translated
at the assembly boundary.

## Deterministic Policy Rule

If the built-in MVP policy is used, it must be:

- a simple `price_threshold` rule
- charge when price is below threshold
- discharge when price is above threshold
- hold when price equals threshold

No forecast, optimization, or learned behavior is allowed in this policy.

## Assembly Guarantees

Scenario assembly must fail fast when:

- aligned series lengths differ from the time grid
- timestep duration is non-positive
- battery efficiencies are outside valid range
- state-of-charge bounds are invalid
- objective rules are underspecified
- both dispatch inputs and rule policy are absent
- both dispatch inputs and rule policy are present for the same execution path
- export discount semantics are missing

Scenario assembly must not import:

- TorchRL
- PyTorch
- CityLearn
- solver libraries
- W&B
- notebook/runtime tooling
- GPU or SLURM helpers
- Rust bindings

## API Maturity

The package location `open_energy_lab.simulator` is stable. The first concrete
scenario assembly types and helpers are experimental until broader simulator
use cases are migrated and promoted.
