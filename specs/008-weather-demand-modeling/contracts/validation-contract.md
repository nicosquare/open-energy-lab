# Contract: Validation Evidence For Weather-Conditioned Demand And Simulator Integration

This contract defines the minimum evidence needed to trust the feature.

## Deterministic Fixture Requirements

The feature must provide deterministic fixture coverage for:

- aligned historical demand-plus-weather training-record shape
- missing cooling-history failure
- missing non-thermal electric-history failure
- fitted-demand-artifact schema and provenance
- unsupported artifact-version failure
- paired weather-and-demand family ordering and seed replay
- local electric versus district-cooling accounting shape
- invalid mixed cooling-path configuration

Committed fixtures may live under:

- `tests/fixtures/demand`
- `tests/fixtures/simulator`

Each committed fixture must include provenance and refresh expectations.

## Offline Validation Requirements

Default validation must prove that:

- demand artifact loading works without network access
- sampling from a persisted demand artifact works without refitting or live
  data sources
- paired scenario-family evaluation works from loaded weather and demand
  artifacts plus simulator-side cooling configuration alone

## Accounting And Reproducibility Requirements

Documented validation checks must cover:

- exact replay from one paired-family seed and scenario ordering
- timestep and horizon alignment between weather and demand families
- explicit prevention of electric and thermal double counting
- local-electric cooling contribution to site electric load
- absence of served district cooling from site electric load
- explicit unserved cooling reporting when full service is unavailable

## Import-Boundary And Dependency Checks

Default validation must also prove:

- `open_energy_lab` base imports stay import-light
- `open_energy_lab.demand` imports do not require CityLearn, building
  simulation, solver, notebook, GPU, or cluster tooling
- `open_energy_lab.demand` and paired simulator imports do not eagerly load
  isolated weather fit or live-service dependencies
- runtime library paths do not import from `legacy/*`

## Environment Assumptions

Default validation must run:

- on CPU
- in the minimal conda plus uv environment
- without CityLearn installs, solver licenses, GPU or SLURM access, live
  weather fetches, W&B, or notebook execution

Notebook review or optional external validations, if exercised at all, should
be isolated from the default validation subset and documented as optional.
