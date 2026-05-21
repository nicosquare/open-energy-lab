# Contract: Scenario Compatibility for Controller Evaluation

This contract defines the minimum compatibility guarantees across the currently
migrated simulator scenario families.

## Supported Scenarios

The MVP must support controller-driven evaluation for:

- `ArbitrageScenario`
- `BatteryLoadPVScenario`

Both are first-class support targets for release, not optional stretch goals.

## Shared Guarantees

Across both scenarios, the controller boundary must preserve:

- one-step controller invocation
- positive dispatch meaning charge
- simulator-owned feasibility enforcement
- deterministic repeated execution
- a stable public controller contract in `open_energy_lab.core`
- a stable simulator evaluation entry point in `open_energy_lab.simulator`

## Scenario-Specific Context Rules

For `ArbitrageScenario`, the controller context must expose at least:

- current battery state
- current-step pricing information
- timestep metadata

For `BatteryLoadPVScenario`, the controller context must expose at least:

- current battery state
- current-step pricing information
- current-step load input
- current-step PV-available input or equivalent current-step exogenous value
- timestep metadata

The stable contract may express missing scenario-specific values as absent or
optional fields, but it must not change the fundamental controller method
shape.

## Compatibility Failure Rules

The simulator boundary must reject:

- any attempt to evaluate an unsupported scenario family
- any attempt to require scenario internals in the public core contract
- any controller path that silently changes sign conventions or timestep
  alignment between scenarios

## Deferred Compatibility

This MVP explicitly defers:

- multi-building controller contracts
- federated or multi-agent interfaces
- full-horizon forecast surfaces
- CityLearn runtime compatibility
- RL training-environment wrappers
