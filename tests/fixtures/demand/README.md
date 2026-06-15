# Demand Fixtures

Fixtures in this directory are reserved for spec
`008-weather-demand-modeling`.

Phase 1 establishes committed scaffold files only. Later tasks populate them
with deterministic data for aligned-history fitting, offline artifact loading,
and paired weather-conditioned demand sampling.

## Planned Fixture Set

- `aligned_training_case.json`
- `aligned_training_case_missing_cooling.json`
- `aligned_training_case_missing_non_thermal.json`
- `fitted_demand_artifact_v1.json`
- `fitted_demand_artifact_unsupported_version.json`
- `sampling_request_case.json`
- `sampled_demand_family_case.json`

## Provenance Requirements

Each committed fixture should record:

- origin and author
- exact legacy evidence paths when any are cited
- generation command or manual construction note
- random seed when applicable
- expected validation target or invariant
- numeric tolerance when value-level comparison matters
- refresh policy

## Scaffold Status

Current placeholder files are intentionally minimal and should not be treated
as finished contract fixtures. They exist to reserve stable paths for:

- aligned training data and fail-fast input cases in T020
- supported and unsupported artifact payloads in T020
- offline sampling request and replay fixtures in T029
