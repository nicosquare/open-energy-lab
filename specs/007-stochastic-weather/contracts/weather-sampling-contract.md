# Contract: Offline Weather Sampling

This contract defines the stable first-release sampling surface for persisted
weather artifacts.

## Purpose

The sampler turns one fitted weather artifact into many stochastic weather
instances for one requested horizon without refetching or refitting.

## Stable Inputs

The stable first-release sampling request includes:

- one loaded fitted weather artifact
- one positive `num_steps`
- one positive scenario count
- one family-level seed
- optional caller-configured blackout scenario configuration

## Stable Sampling Semantics

The sampler must:

- derive each scenario instance deterministically from the family seed plus
  scenario index
- use the artifact's stored timestep resolution
- support arbitrary positive `num_steps`
- preserve the complete canonical weather field set in every sampled trace
- sample in local-civil-time semantics while materializing canonical
  `timestamp_utc` values in the returned traces

## Daily-Block And Horizon Rules

The first-release sampler may sample whole local-day blocks internally and trim
the concatenated result to the requested `num_steps`, as long as the caller
receives exactly the requested horizon length.

## Cloud-Event Rules

- cloud or irradiance attenuation events must be modeled as weather-side
  stochastic behavior
- cloud events may span multiple contiguous timesteps
- the first release applies cloud events only to irradiance variables
- cloud-event annotations must be explicit in returned sampled weather traces

## Fail-Fast Conditions

The sampler must fail fast when:

- the artifact schema version is unsupported
- the requested timestep differs from the artifact timestep
- `num_steps` or scenario count is not positive
- the artifact lacks required canonical fields or required model parameters

## Guarantees

The stable first-release sampling surface guarantees:

- offline operation
- reproducibility from the same family seed and scenario ordering
- exact horizon length in every returned trace
- explicit cloud-event metadata
- preserved canonical field ordering in all sampled traces
