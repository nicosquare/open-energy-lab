# Contract: Same-Family Run Comparison

This contract defines the allowed comparison behavior for the visualization
MVP.

## Purpose

Comparison must help maintainers review controller changes, scenario changes,
and preserved-path regressions without introducing misleading cross-family
alignment rules.

## Supported Scope

The MVP comparison surface supports only:

- two runs from the same supported scenario family
- deterministic trace-level and summary-level comparison over aligned timesteps

## Required Comparison Behavior

For supported same-family comparisons, the surface must:

- align shared timestep order deterministically
- compare available shared series consistently
- expose summary-level differences such as settlement deltas
- preserve explicit unsupported handling when a requested series is not
  available in one of the inputs

## Unsupported Cases

The comparison surface must reject:

- cross-family comparison requests
- inputs with incompatible timestep counts when no deterministic alignment rule
  exists
- requests that depend on series absent from one or both inputs

Unsupported-case responses must be:

- immediate
- deterministic
- attributable to comparison scope rather than to simulation failure

## Deferred Directions

This MVP does not require:

- cross-family comparison
- rendered comparison plots
- best-effort heuristic alignment across unrelated run families
