# Contract: Visualization Package Surface

This contract defines the public package surface for the first reusable
inspection and visualization tools in `open_energy_lab.visualization`.

## Purpose

The package must let a library consumer inspect supported deterministic run
outputs through one canonical reporting surface while keeping plotting
optional, bounded, and separate from simulator execution.

## Required Public Surface

The package-root stable surface must export inspection and reporting helpers
for supported deterministic run outputs.

Equivalent names are acceptable only if the migration note and API-maturity
documentation promote them explicitly as the stable public surface for this
feature.

## Maturity Split

For this feature:

- core inspection and reporting are stable public API
- the plotting layer is experimental

The stable root contract must not require users to import optional plotting
tooling just to inspect or compare runs.

## Layering Rules

The visualization package must:

- consume outputs from `open_energy_lab.simulator` and controller-driven
  evaluation results
- preserve simulator and controller ownership of execution semantics
- operate on in-memory or supported persisted outputs without rerunning a
  scenario
- keep same-family comparison as the only supported comparison mode in the MVP

The visualization package must not:

- define a second simulator execution path
- trigger a fresh simulation run to produce plots
- change controller behavior, weather semantics, or settlement semantics
- import `legacy/*` at runtime
- require notebook-first or dashboard-first workflows

## Import Boundary

Ordinary imports of `open_energy_lab.visualization` must not require:

- notebook tooling
- dashboards or GUI frameworks
- W&B
- GPU or SLURM tooling
- external API clients
- runtime `legacy/*` imports

Optional plotting-specific imports may require an optional backend, but base
inspection imports must remain available without it.
