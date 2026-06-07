# Contract: Next Simulator Migration Preparation

The next simulator migration spec should use this contract. It should prepare
`open_energy_lab.simulator` without relying on CityLearn, real data, or legacy
directory structure as the target architecture. CityLearn is legacy reference
material only, not a compatibility or integration target.

## Target Boundary

```text
Target module: src/open_energy_lab/simulator
First validation use case: battery arbitrage
Composition model: component graph
Core compatibility requirement: no TorchRL dependency in simulator core imports
```

## Candidate Components

The first simulator spec should evaluate a minimal set of components needed for
battery arbitrage:

- Time grid and units.
- Battery or storage component.
- Price signal or tariff component.
- Market interaction or arbitrage objective representation.
- Minimal load and PV components only if required by the validation case.
- Scenario configuration format.

The spec may note future components such as buildings, cooling loads, thermal
storage, district cooling systems, generators, markets, and networks, but it
should not implement them unless they are required by the first validation
case.

## Data Policy

- Synthetic data is first-class and should be enough for sanity checks.
- Real data ingestion must use simulator-compatible templates.
- Source adapters such as ENTSO-E are optional capabilities, not simulator core
  requirements.
- Generated data used for tests must follow the fixture provenance contract.

## Legacy References to Review

Candidate references include:

```text
legacy/old_tpm/src_py/simulator
legacy/old_tpm/src_py/weather
legacy/old_tpm/src
legacy/fed_trpo/src/custom
```

The simulator migration spec must cite exact files after reviewing these
directories. This preparation contract does not select or migrate behavior by
itself.

## TorchRL Boundary

TorchRL compatibility should be implemented as an optional wrapper or adapter
around simulator scenarios. The simulator core should expose enough structured
state/action information for a later adapter, but importing the simulator core
must not require TorchRL.

## Validation Expectations

The first simulator migration should define:

- Deterministic battery arbitrage fixture or synthetic config.
- Expected state transitions, energy balance, and objective properties.
- Tolerances for floating-point comparisons.
- Parity or rationale against selected legacy behavior.
- Local smoke checks that run without solver licenses, W&B, GPU, SLURM, or
  external data APIs.

## Explicitly Out of Scope

Do not implement TPM, RL, MPC, planning models, control algorithms, weather
models, ENTSO-E adapters, Rust bindings, visualization, or full city-scale
simulation in the first simulator migration unless a later spec changes scope.
