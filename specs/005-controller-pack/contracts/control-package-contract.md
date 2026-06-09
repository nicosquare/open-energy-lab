# Contract: Native Control Package Surface

This contract defines the public package surface for the first reusable native
controllers in `open_energy_lab.control`.

## Purpose

The control package must let a library consumer import, configure, and run
shipped deterministic controllers without writing a custom controller class or
depending on legacy runtimes.

## Required Public Surface

The package-root surface must export:

- `PriceThresholdController`
- `PriceThresholdConfig`
- `SocGuardrailController`
- `SocGuardrailConfig`
- `PVSelfConsumptionController`
- `PVSelfConsumptionConfig`

Equivalent names are acceptable only if the migration note and API maturity
documentation promote them explicitly as the stable public surface for this
feature.

## Layering Rules

The control package must:

- implement `open_energy_lab.core.ControllerInterface`
- execute through `open_energy_lab.simulator.evaluate_with_controller`
- depend only on current-step `ControllerContext` inputs
- leave feasibility enforcement, state transitions, and settlement to the
  simulator

The control package must not:

- define a replacement controller contract
- bypass `evaluate_with_controller`
- import `legacy/*` at runtime
- require optional research stacks for ordinary import

## Import Boundary

Ordinary imports of `open_energy_lab.control` must not require:

- TorchRL
- PyTorch
- CityLearn
- Pyomo, Gurobi, CPLEX, or other solver stacks
- W&B
- Jupyter or notebook tooling
- GPU or SLURM tooling
- external API clients

## API Maturity

For this feature, the package-root control exports are stable public API once
they are documented in migration notes and protected by focused tests.

Supporting private helpers, internal modules, and module-private utilities may
change without promotion as long as the package-root surface remains stable.
