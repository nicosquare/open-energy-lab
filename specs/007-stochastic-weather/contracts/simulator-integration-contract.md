# Contract: Simulator Integration For Stochastic Weather Families

This contract defines how sampled weather and caller-configured blackouts enter
the simulator while preserving the existing deterministic path.

## Purpose

The feature must let the simulator explore weather-driven scenario families
without making stochastic weather a prerequisite for the existing deterministic
`BatteryLoadPVScenario`.

## Preserved Deterministic Path

The current deterministic single-run path remains supported:

- `BatteryLoadPVScenario` stays the deterministic single-scenario surface
- callers may continue to pass direct fixed-weather inputs without a fitted
  artifact
- deterministic regression fixtures remain valid without stochastic weather

## Stable Stochastic Family Surface

The simulator integration layer must provide a stable scenario-family surface
that:

- binds one base deterministic simulator configuration to many sampled weather
  traces
- optionally binds caller-configured blackout traces for the same family
- evaluates each scenario instance independently
- returns both per-scenario results and built-in family summaries

## Blackout Semantics

The first-release blackout mode is fixed:

- grid outage only
- no grid import during blackout intervals
- no grid export during blackout intervals
- local PV and battery may continue serving load
- remaining shortfall must be explicit unmet load

Blackouts are not weather attenuation events and are not fitted from TMY data.

## Stable Family Summaries

Built-in stable family summaries must cover documented core simulator outputs
only:

- PV generation
- net-grid power
- unmet load
- settlement metrics

For each supported field, summaries must include:

- minimum
- mean
- maximum
- 5th percentile
- 50th percentile
- 95th percentile

Raw weather-variable summaries are out of scope for the stable simulator
surface.

## Guarantees

The simulator integration contract guarantees:

- deterministic-path preservation
- scenario-indexed stochastic family evaluation
- explicit outage-aware result traces
- reproducible family summaries from the same family seed and ordering
- no hidden downgrade of blackout semantics into weather attenuation
