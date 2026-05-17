# Contract: Battery Load PV Scenario Assembly

This contract defines the minimum simulator scenario surface for the
deterministic battery + load + PV MVP.

## Purpose

The scenario contract must let a maintainer assemble a deterministic
multi-component case from typed simulator components and explicit component
relationships. It is a simulator contract, not a planning, optimization, or RL
contract.

## Required Components

Every MVP scenario must include:

- `TimeGrid`
- `BatteryComponent`
- `LoadComponent`
- `WeatherComponent`
- `PVComponent`
- `PriceSignal`
- settlement or objective metadata for net-grid accounting

Every MVP scenario must also include one of:

- `DispatchRequestSeries`
- `DeterministicRulePolicy`

Optional components are allowed only when they do not widen the simulator-core
dependency boundary. Building envelopes, CityLearn-facing abstractions, RL
state, and external data adapters remain out of scope.

## Graph Shape

The composed scenario must make at least these relationships explicit:

```text
TimeGrid -> LoadComponent
TimeGrid -> WeatherComponent
WeatherComponent -> PVComponent
TimeGrid -> PriceSignal
BatteryComponent -> ExtendedSimulationTrace
LoadComponent -> NetGridTrace
PVComponent -> NetGridTrace
ExtendedSimulationTrace -> NetGridTrace
PriceSignal -> NetGridTrace
NetGridTrace -> SettlementResult
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

The graph may be represented with simple typed objects and a small documented
relationship vocabulary. It does not need a general-purpose graph library.

## Required Inputs

At minimum, the assembled scenario must declare:

- timestep duration in hours
- number of steps
- battery capacity, power limits, efficiencies, and initial SOC
- load profile aligned to the time grid
- weather inputs aligned to the time grid
- weather inputs that preserve exact TMY-style names for whichever subset is
  included in the MVP
- PV metadata and derivation rule
- price series aligned to the time grid
- explicit dispatch requests aligned to the time grid or one built-in
  deterministic rule policy
- export discount rule relative to import price
- net-grid settlement rules

## Sign and Unit Conventions

The scenario contract must document:

- energy in `kWh`
- power in `kW`
- SOC as fraction in `[0.0, 1.0]`
- timestep duration in hours
- positive battery dispatch request = charge request
- positive net-grid value = grid import
- negative net-grid value = grid export

Any deviation from these conventions must be rejected or explicitly translated
at the assembly boundary.

## Execution Modes

The MVP must support both of these execution paths:

- explicit battery dispatch requests
- one built-in deterministic `price_threshold` battery rule

The built-in rule:

- remains price-driven only
- may not consume load or PV inputs directly
- must remain deterministic from the same price series and battery state

## Assembly Guarantees

Scenario assembly must fail fast when:

- any aligned series length differs from the time grid
- timestep duration is non-positive
- battery invariants are invalid
- load or PV inputs are underspecified
- weather inputs required by the chosen PV derivation are missing
- included weather fields are renamed away from their exact TMY-style names
- both dispatch inputs and rule policy are absent
- both dispatch inputs and rule policy are present for the same execution path
- export discount semantics are missing
- the scenario hides load, PV, or grid accounting inside one-off procedural
  logic instead of typed components

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

The package location `open_energy_lab.simulator` remains stable. The new
multi-component scenario types added by this feature are still experimental
until later migrations promote them with broader simulator coverage.
