# Weather Fixtures

This directory is reserved for deterministic stochastic-weather validation
cases that support the planned `open_energy_lab.weather` package without
adding new runtime behavior to `legacy/*`.

## Scaffolded Fixture Set

Phase 1 reserves these placeholder fixture paths:

- `recorded_pvgis_tmy_response.json`
- `location_unavailable_response.json`
- `fitted_weather_artifact_v1.json`

These files are scaffolds only in Phase 1. They establish committed paths,
provenance expectations, and future validation intent before the weather
workflow is implemented.

## Required Provenance Record

Each committed weather fixture should keep a nearby record with at least these
fields:

```text
Fixture path:
Purpose:
Status:
Origin:
Source service, dataset, or current-library artifact:
Exact legacy reference paths consulted, if any:
Generation command:
Random seed:
Expected validation target:
Canonical field coverage:
Numeric tolerance:
Why the fixture is small enough to commit:
Access, license, or network notes:
Refresh policy:
```

## Phase 1 Placeholder Records

`recorded_pvgis_tmy_response.json`

- fixture path: `tests/fixtures/weather/recorded_pvgis_tmy_response.json`
- purpose: reserved recorded PVGIS TMY response for the geolocation-to-fit
  workflow
- status: scaffold
- origin: Phase 1 setup scaffold for spec `007-stochastic-weather`
- source service or artifact: PVGIS TMY response to be recorded later
- exact legacy reference paths consulted, if any:
  - `legacy/old_tpm/src_py/weather/fetch.py`
  - `legacy/old_tpm/src_py/weather/pipeline.py`
- generation command: none yet
- random seed: none
- expected validation target: recorded fetch-to-normalization integration
  coverage for User Story 1
- canonical field coverage: not populated yet
- numeric tolerance: not applicable until populated
- why the fixture is small enough to commit: the final recorded response must
  stay trimmed and reviewable
- access, license, or network notes: replace routine live fetches with this
  recorded response for default validation
- refresh policy: update only when the documented fetch workflow or provider
  response assumptions intentionally change

`location_unavailable_response.json`

- fixture path: `tests/fixtures/weather/location_unavailable_response.json`
- purpose: reserved fail-fast provider response for unsupported or unavailable
  geolocations
- status: scaffold
- origin: Phase 1 setup scaffold for spec `007-stochastic-weather`
- source service or artifact: PVGIS failure response to be recorded later
- exact legacy reference paths consulted, if any:
  - `legacy/old_tpm/src_py/weather/fetch.py`
- generation command: none yet
- random seed: none
- expected validation target: explicit location-unavailable workflow failure
- canonical field coverage: not applicable
- numeric tolerance: not applicable
- why the fixture is small enough to commit: the final failure payload should
  remain minimal and reviewable
- access, license, or network notes: intended to avoid live provider failures
  in routine tests
- refresh policy: update only when the documented provider-error handling
  contract intentionally changes

`fitted_weather_artifact_v1.json`

- fixture path: `tests/fixtures/weather/fitted_weather_artifact_v1.json`
- purpose: reserved deterministic fitted-artifact shell for offline load and
  sampling validation
- status: scaffold
- origin: Phase 1 setup scaffold for spec `007-stochastic-weather`
- source service or artifact: current-library artifact to be committed later
- exact legacy reference paths consulted, if any:
  - `legacy/old_tpm/src_py/weather/models/gaussian.py`
  - `legacy/old_tpm/src_py/weather/models/enhanced.py`
- generation command: none yet
- random seed: none until final fixture generation is documented
- expected validation target: artifact schema, provenance, and offline reload
  checks for User Story 1
- canonical field coverage: not populated yet
- numeric tolerance: `1e-6` unless the final artifact contract documents a
  stricter case
- why the fixture is small enough to commit: the final artifact must remain
  inspectable JSON rather than an opaque binary
- access, license, or network notes: final reload and sampling validation must
  stay offline
- refresh policy: update only when the documented artifact schema, timestep
  contract, or provenance expectations intentionally change

## Working Rule

Keep weather fixtures synthetic or tightly trimmed, explicit about network
assumptions, and reviewable in git. Replace placeholders only when the
corresponding workflow or sampling contract has focused tests.
