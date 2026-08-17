# Contract: Simulator Integration For Paired Weather-And-Demand Families

This contract defines how sampled weather and sampled demand enter the
simulator while preserving the existing deterministic path.

## Purpose

The feature must let the simulator explore cooling-aware scenario families
without making stochastic demand or cooling service configuration a
prerequisite for the existing deterministic `BatteryLoadPVScenario`.

## Preserved Deterministic Path

The current deterministic single-run path remains supported:

- `BatteryLoadPVScenario` stays the deterministic single-scenario surface
- callers may continue to pass direct fixed load and weather inputs without a
  demand artifact
- deterministic regression fixtures remain valid without stochastic demand

## Stable Paired Family Surface

The simulator integration layer must provide a stable scenario-family surface
that:

- binds one base deterministic simulator configuration to many sampled weather
  traces and many aligned sampled demand traces
- validates one shared paired-family seed, scenario ordering, timestep, and
  horizon
- applies exactly one cooling service path per scenario family
- evaluates each scenario instance independently
- returns both per-scenario results and built-in family summaries

## Cooling Service Semantics

The first-release cooling-path rules are fixed:

- each scenario chooses exactly one path: local electric cooling or district
  cooling
- local electric cooling converts served cooling demand in `RT` to site
  electric demand in `kW` using the configured conversion factor
- district cooling satisfies thermal demand directly in `RT`
- served district cooling does not appear as site electric load
- district cooling uses its own deterministic tariff based on served
  `RT-hour`
- unserved cooling demand must be explicit whenever full service is
  unavailable

## Blackout Semantics

Blackouts remain simulator-side and unchanged from the weather feature:

- grid outage only
- no grid import during blackout intervals
- no grid export during blackout intervals
- local PV and battery may continue serving site electric load
- blackout semantics do not modify fitted weather or demand artifacts

## Stable Family Summaries

Built-in stable family summaries must cover documented comparison outputs only:

- site electric load
- local cooling electric demand
- served cooling demand
- unserved cooling demand
- net-grid power
- electric settlement and district-cooling settlement outputs needed for case
  comparison

For each supported field, summaries must include:

- minimum
- mean
- maximum
- 5th percentile
- 50th percentile
- 95th percentile

Raw weather variables and raw artifact internals remain out of scope for the
stable simulator surface.

## Guarantees

The simulator integration contract guarantees:

- deterministic-path preservation
- scenario-indexed paired family evaluation
- explicit electric and thermal service accounting
- reproducible family summaries from the same paired-family seed and ordering
- no hidden double counting between sampled non-thermal electric and cooling
  demand
