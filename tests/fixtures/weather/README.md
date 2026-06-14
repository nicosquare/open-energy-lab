# Weather Fixtures

This directory now holds the committed User Story 1 and User Story 2
validation fixtures for the `open_energy_lab.weather` geolocation-to-artifact
and offline sampling workflows. They are small, deterministic, and explicit
about provenance so default validation can stay offline and reviewable.

## Active Fixture Set

- `recorded_pvgis_tmy_response.json`
- `missing_required_field_response.json`
- `location_unavailable_response.json`
- `fitted_weather_artifact_v1.json`
- `fitted_weather_artifact_unsupported_version.json`
- `sampling_request_case.json`
- `sampled_weather_family_case.json`

## Provenance Fields

Every committed fixture in this directory keeps these top-level metadata
fields:

```text
fixture_status
fixture_path
purpose
origin
legacy_reference_paths
notes
```

Provider-response fixtures also keep `source_service` plus any recorded
provider payload fields. Artifact fixtures keep the full artifact payload so
they can be loaded directly by `load_weather_artifact`. Sampling fixtures keep
the stable request or returned-family payload fields needed for deterministic
offline replay.

## Fixture Records

`recorded_pvgis_tmy_response.json`

- fixture path: `tests/fixtures/weather/recorded_pvgis_tmy_response.json`
- purpose: recorded positive-path PVGIS-style response for fitting
- status: active
- origin: current-library US1 contract fixture
- source service or artifact: trimmed PVGIS-style hourly response
- exact legacy reference paths consulted:
  - `legacy/old_tpm/src_py/weather/fetch.py`
  - `legacy/old_tpm/src_py/weather/pipeline.py`
- generation command: committed manually from the current library contract
- random seed: none
- expected validation target: recorded fetch-to-artifact workflow coverage
- canonical field coverage: full ten-field canonical mapping via provider
  labels
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: only three hourly records are
  retained
- access, license, or network notes: replaces routine live PVGIS fetches in
  default validation
- refresh policy: update only when the documented provider mapping or
  normalization contract intentionally changes

`missing_required_field_response.json`

- fixture path: `tests/fixtures/weather/missing_required_field_response.json`
- purpose: fail-fast missing-field provider response
- status: active
- origin: derived from the recorded positive-path response
- source service or artifact: trimmed PVGIS-style hourly response with
  `Gb(n) [W/m2]` removed from one record
- exact legacy reference paths consulted:
  - `legacy/old_tpm/src_py/weather/fetch.py`
  - `legacy/old_tpm/src_py/weather/pipeline.py`
- generation command: committed manually from the current library contract
- random seed: none
- expected validation target: `MissingCanonicalWeatherFieldError` coverage
- canonical field coverage: intentionally incomplete
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: reuses the three-record shape of
  the recorded response
- access, license, or network notes: avoids routine live negative-path fetches
- refresh policy: update only when the missing-field fail-fast contract
  intentionally changes

`location_unavailable_response.json`

- fixture path: `tests/fixtures/weather/location_unavailable_response.json`
- purpose: fail-fast unsupported-location provider response
- status: active
- origin: current-library `WeatherLocationUnavailableError` contract fixture
- source service or artifact: provider-style failure envelope with empty
  records
- exact legacy reference paths consulted:
  - `legacy/old_tpm/src_py/weather/fetch.py`
- generation command: committed manually from the current library contract
- random seed: none
- expected validation target: explicit location-unavailable failure coverage
- canonical field coverage: not applicable
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: minimal response body
- access, license, or network notes: avoids routine live provider failures
- refresh policy: update only when the provider-failure handling contract
  intentionally changes

`fitted_weather_artifact_v1.json`

- fixture path: `tests/fixtures/weather/fitted_weather_artifact_v1.json`
- purpose: supported offline load artifact fixture
- status: active
- origin: synthetic current-library artifact fixture
- source service or artifact: committed JSON artifact with a daily timestep
- exact legacy reference paths consulted:
  - `legacy/old_tpm/src_py/weather/models/gaussian.py`
  - `legacy/old_tpm/src_py/weather/models/enhanced.py`
- generation command: committed manually from the current library contract
- random seed: none
- expected validation target: supported artifact schema and offline load
  coverage
- canonical field coverage: full first-release canonical order
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: uses `intervals_per_day = 1` so
  the covariance matrix remains reviewable
- access, license, or network notes: entirely offline
- refresh policy: update only when the documented artifact schema or
  provenance contract intentionally changes

`fitted_weather_artifact_unsupported_version.json`

- fixture path: `tests/fixtures/weather/fitted_weather_artifact_unsupported_version.json`
- purpose: unsupported-version artifact fixture
- status: active
- origin: copy of the supported artifact with only the schema version changed
- source service or artifact: committed JSON artifact with `schema_version:
  v999`
- exact legacy reference paths consulted:
  - `legacy/old_tpm/src_py/weather/models/gaussian.py`
  - `legacy/old_tpm/src_py/weather/models/enhanced.py`
- generation command: committed manually from the current library contract
- random seed: none
- expected validation target: unsupported-version fail-fast coverage
- canonical field coverage: full first-release canonical order
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: reuses the supported daily
  artifact shape
- access, license, or network notes: entirely offline
- refresh policy: update only when the explicit schema compatibility contract
  intentionally changes

`sampling_request_case.json`

- fixture path: `tests/fixtures/weather/sampling_request_case.json`
- purpose: deterministic offline sampling request paired with the supported
  artifact fixture
- status: active
- origin: current-library US2 request-contract fixture
- source service or artifact: uses
  `tests/fixtures/weather/fitted_weather_artifact_v1.json`
- exact legacy reference paths consulted:
  - `legacy/old_tpm/src_py/weather/models/gaussian.py`
  - `legacy/old_tpm/src_py/weather/models/enhanced.py`
- generation command: committed manually from the documented US2 request
  contract
- random seed: family seed `13`
- expected validation target: offline family replay and fixture-schema
  coverage
- canonical field coverage: implied by the paired sampled-family fixture
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: only requests `3` daily steps
  across `2` scenarios
- access, license, or network notes: entirely offline
- refresh policy: update only when the stable request controls intentionally
  change

`sampled_weather_family_case.json`

- fixture path: `tests/fixtures/weather/sampled_weather_family_case.json`
- purpose: deterministic sampled-family result paired with the committed US2
  request fixture
- status: active
- origin: synthetic current-library US2 family-result fixture
- source service or artifact: generated from
  `tests/fixtures/weather/fitted_weather_artifact_v1.json` and
  `tests/fixtures/weather/sampling_request_case.json`
- exact legacy reference paths consulted:
  - `legacy/old_tpm/src_py/weather/models/gaussian.py`
  - `legacy/old_tpm/src_py/weather/models/enhanced.py`
  - `legacy/old_tpm/src_py/weather/analysis/drops.py`
- generation command: committed manually from the current library sampler
- random seed: family seed `13`
- expected validation target: deterministic offline family replay, exact
  horizon length, and cloud-event annotation coverage
- canonical field coverage: full first-release canonical sampled-field set
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: uses the reviewable daily
  artifact fixture and trims the family to `3` steps
- access, license, or network notes: entirely offline
- refresh policy: update only when the stable offline sampling contract or
  deterministic seed derivation intentionally changes

## Working Rule

Keep weather fixtures synthetic or tightly trimmed, explicit about network
assumptions, and reviewable in git. Prefer committed deterministic fixtures
over live fetches for default validation.
