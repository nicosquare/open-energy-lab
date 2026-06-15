# Contract: Offline Weather-Conditioned Demand Sampling

This contract defines the stable first-release sampling surface for persisted
demand artifacts.

## Purpose

The sampler turns one fitted demand artifact and one aligned sampled weather
family into many stochastic demand instances for one requested horizon without
refitting or live services.

## Stable Inputs

The stable first-release sampling request includes:

- one loaded fitted demand artifact
- one sampled weather family or equivalent per-scenario weather reference
- one positive `num_steps`
- one positive scenario count
- one shared paired-family seed

## Stable Sampling Semantics

The sampler must:

- derive each demand scenario instance deterministically from the shared
  paired-family seed plus scenario index
- preserve exact scenario ordering with the referenced weather family
- use the artifact's stored timestep resolution
- support arbitrary positive `num_steps`
- return explicit non-thermal electric demand and cooling demand in `RT` for
  every sampled trace
- preserve local-civil-time semantics while remaining aligned to canonical
  `timestamp_utc` weather traces through the weather reference

## Conditioning Rules

- every sampled demand trace must reference one weather trace of the same
  scenario index
- the referenced weather trace must satisfy the artifact's required weather
  fields
- the sampler must keep demand outputs separate even when both respond to the
  same weather inputs

## Daily-Block And Horizon Rules

The first-release sampler may sample whole local-day blocks internally and trim
the concatenated result to the requested `num_steps`, as long as the caller
receives exactly the requested horizon length and exact weather-trace
alignment.

## Fail-Fast Conditions

The sampler must fail fast when:

- the artifact schema version is unsupported
- the referenced weather family timestep differs from the artifact timestep
- `num_steps` or scenario count is not positive
- the weather family seed or scenario ordering does not satisfy the paired
  contract
- the artifact lacks required model parameters or required weather drivers

## Guarantees

The stable first-release sampling surface guarantees:

- offline operation
- reproducibility from the same paired-family seed and scenario ordering
- exact horizon length in every returned trace
- explicit non-thermal electric and cooling output series
- preserved demand-to-weather trace alignment
