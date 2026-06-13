# Contract: Validation Evidence For Stochastic Weather And Simulator Integration

This contract defines the minimum evidence needed to trust the feature.

## Deterministic Fixture Requirements

The feature must provide deterministic fixture coverage for:

- canonical weather normalization shape and source-label mapping
- missing-field fetch failure
- fitted-artifact schema and provenance
- unsupported artifact-version failure
- fixed-timestep sampling failure
- deterministic-path simulator preservation
- blackout-aware scenario-family result shape

Committed fixtures may live under:

- `tests/fixtures/weather`
- `tests/fixtures/simulator`

Each committed fixture must include provenance and refresh expectations.

## Offline Validation Requirements

Default validation must prove that:

- artifact loading works without network access
- sampling from a persisted artifact works without refetching or refitting
- scenario-family evaluation works from loaded artifacts and caller-supplied
  blackout configuration alone

## Stochastic Acceptance Requirements

Documented stochastic checks must cover:

- physical bounds for all supported fields
- cross-variable relationship preservation against the fitted TMY baseline
- lagged temporal continuity
- multi-step cloud-event behavior
- reproducibility from one family seed plus scenario ordering

The feature does not need to prove perfect realism. It needs explicit,
documented stochastic evidence that the stable contract behaves as designed.

## Import-Boundary And Dependency Checks

Default validation must also prove:

- `open_energy_lab` base imports stay import-light
- `open_energy_lab.simulator` imports do not require network-backed fit/fetch
  tooling
- runtime library paths do not import from `legacy/*`

## Environment Assumptions

Default validation must run:

- on CPU
- in the minimal conda plus uv environment
- without live weather API credentials for artifact-load or sampling tests
- without W&B, notebooks, GPU/SLURM, solver licenses, or Rust builds

Live network fetches, if exercised at all, should be isolated from the default
validation subset and replaced by recorded fixtures for routine review.
