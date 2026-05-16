# Simulator Preparation

This document prepares the next simulator migration spec without implementing
simulator behavior in the foundation feature.

## Target Boundary

```text
Target module: src/open_energy_lab/simulator
First validation use case: battery arbitrage
Composition model: component graph
Core compatibility requirement: no TorchRL dependency in simulator core imports
```

## Candidate Components

The first simulator spec should evaluate only the components needed for
battery arbitrage:

- Time grid and units.
- Battery or storage component.
- Price signal or tariff component.
- Market interaction or arbitrage objective representation.
- Minimal load and PV components only if required by the validation case.
- Scenario configuration format.

Future components such as buildings, cooling loads, thermal storage, district
cooling systems, generators, markets, and networks may be noted, but they
should not be implemented unless the first validation case needs them.

## Data Policy

- Synthetic data is first-class and should be enough for sanity checks.
- Real data ingestion must use simulator-compatible templates.
- Source adapters such as ENTSO-E are optional capabilities, not simulator
  core requirements.
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
directories. This preparation document does not select or migrate behavior by
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

## Migration Spec Notes

When the first simulator migration is written, it should still include the
general migration contract fields: `target module path`, `validation/test path`, `legacy paths`, `behavior to preserve`, `behavior to improve`, `behavior to reject`, and `validation evidence`. That keeps `out-of-scope algorithm migration` explicit even though the detailed simulator preparation already narrows the target to battery arbitrage.
