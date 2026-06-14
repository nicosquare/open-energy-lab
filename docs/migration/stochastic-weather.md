# Stochastic Weather Migration Note

Status: User Story 1 geolocation-to-artifact workflow and User Story 2
offline family sampling implemented

Spec `007-stochastic-weather` now ships the first stable weather-package slice:
geolocation input, PVGIS-style TMY normalization, deterministic artifact
fitting, JSON persistence, offline artifact loading, and seeded offline family
sampling. Simulator-family evaluation remains later-story work, and the
package root keeps the shipped weather workflow behind the same import-light
lazy-loading boundary.

## Target Module Paths

- `src/open_energy_lab/weather/__init__.py`
- `src/open_energy_lab/weather/_canonical.py`
- `src/open_energy_lab/weather/tmy.py`
- `src/open_energy_lab/weather/fit.py`
- `src/open_energy_lab/weather/artifact.py`
- `src/open_energy_lab/weather/sampling.py`
- `src/open_energy_lab/weather/events.py`
- `src/open_energy_lab/simulator/stochastic_weather.py`

## Current Package Boundary

The weather package root now exposes the implemented fit, load, and sampling
workflow:

```python
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)

from open_energy_lab.simulator.stochastic_weather import evaluate_weather_family
```

Current expectation:

- package-root weather exports stay lazy and import-light
- `fit_weather_model` performs the geolocation-to-artifact workflow
- `load_weather_artifact` works from committed JSON without network access
- `WeatherSamplingRequest` is the stable first-release request type for seeded
  offline family sampling
- `sample_weather_family` and `WeatherArtifact.sample_family(...)` both sample
  reproducible arbitrary-horizon weather families from a loaded artifact
- weather submodules remain free of runtime `legacy/*` imports
- simulator stochastic evaluation remains separate from the deterministic
  `BatteryLoadPVScenario` path

## Planned Validation Paths

- `tests/unit/weather/`
- `tests/integration/weather/`
- `tests/integration/simulator/test_stochastic_weather_family.py`
- `tests/integration/simulator/test_blackout_semantics.py`
- `tests/fixtures/weather/`
- `tests/fixtures/simulator/stochastic_weather_family_case.json`
- `tests/fixtures/simulator/blackout_weather_family_case.json`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/test_import_contract.py`
- `tests/unit/test_no_legacy_imports.py`

## Legacy Source Paths

Weather fetch, normalization, and stochastic-model evidence:

- `legacy/old_tpm/src_py/weather/fetch.py`
- `legacy/old_tpm/src_py/weather/pipeline.py`
- `legacy/old_tpm/src_py/weather/models/gaussian.py`
- `legacy/old_tpm/src_py/weather/models/enhanced.py`
- `legacy/old_tpm/src_py/weather/analysis/drops.py`

Simulator weather and PV coupling evidence:

- `legacy/old_tpm/src_py/simulator/common/weather.py`
- `legacy/old_tpm/src_py/simulator/common/pv.py`

## Geolocation-To-Artifact Decisions

### Preserve

- Geolocation remains the stable caller input for fitting.
- `BatteryLoadPVScenario` remains the deterministic single-scenario simulator
  path for direct debugging.
- Legacy repositories remain reference-only evidence, not runtime imports.
- Default validation stays CPU-local and uses recorded fixtures rather than
  routine live weather fetches.

### Improve

- Add a library-owned `open_energy_lab.weather` package that cleanly separates
  geolocation fetch, canonical normalization, artifact persistence, and
  offline sampling from simulator execution ownership.
- Normalize the full ten-field canonical weather schema in local civil time
  while preserving `timestamp_utc` and provider-label provenance.
- Persist human-inspectable JSON artifacts that fail fast on unsupported schema
  versions or timestep mismatches.
- Commit deterministic positive-path and failure-path fixtures so the fit
  workflow can be reviewed without live network access.
- Document blackout semantics as explicit simulator-side grid outages rather
  than implicit weather degradation.

### Reject

- New runtime code under `legacy/*`
- Base-import dependence on network-backed fetch tooling
- Partial artifacts with missing canonical weather fields
- Silent fallback from unsupported artifact versions to auto-migrated payloads
- Blackout semantics inferred from irradiance attenuation alone

## Current Weather Fixtures

The weather fixture set is now active for the fit workflow:

- `tests/fixtures/weather/recorded_pvgis_tmy_response.json`
- `tests/fixtures/weather/missing_required_field_response.json`
- `tests/fixtures/weather/location_unavailable_response.json`
- `tests/fixtures/weather/fitted_weather_artifact_v1.json`
- `tests/fixtures/weather/fitted_weather_artifact_unsupported_version.json`
- `tests/fixtures/weather/sampling_request_case.json`
- `tests/fixtures/weather/sampled_weather_family_case.json`

Current expectations:

- positive-path and fail-fast provider responses remain small and deterministic
- the supported artifact remains human-reviewable by using a synthetic daily
  timestep payload
- artifact fixtures include full schema, provenance, and offline load metadata
- sampling fixtures prove exact horizon trimming, family-seed replay, and
  explicit cloud-event annotations
- default validation never requires live weather fetches

## Fit Workflow Usage

The current fit workflow is:

```python
from pathlib import Path
import json

from open_energy_lab.weather import fit_weather_model, load_weather_artifact
from open_energy_lab.weather.fit import WeatherFitConfig

recorded_response = json.loads(
    Path("tests/fixtures/weather/recorded_pvgis_tmy_response.json").read_text()
)

artifact = fit_weather_model(
    33.4484,
    -112.0740,
    recorded_response=recorded_response,
    fit_config=WeatherFitConfig(timestep_hours=1.0),
    output_path="tmp/weather-artifact.json",
)

reloaded = load_weather_artifact("tmp/weather-artifact.json", expected_timestep_hours=1.0)
```

This preserves the intended workflow boundary:

- live fetch tooling remains isolated to the fit path
- canonical normalization happens before artifact creation
- offline reload depends only on the committed JSON artifact
- unsupported versions and missing canonical fields fail fast

## Offline Sampling Usage

The current offline sampling workflow is:

```python
from pathlib import Path
import json

from open_energy_lab.weather import (
    WeatherSamplingRequest,
    load_weather_artifact,
    sample_weather_family,
)

artifact = load_weather_artifact(
    json.loads(Path("tests/fixtures/weather/fitted_weather_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)

request = WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=13)

family = sample_weather_family(
    artifact,
    request=request,
    expected_timestep_hours=24.0,
)
```

Equivalent loaded-artifact usage is also stable:

```python
family = artifact.sample_family(
    request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=13),
    expected_timestep_hours=24.0,
)
```

This preserves the intended US2 boundary:

- sampling remains fully offline once the artifact exists
- the artifact timestep stays locked and explicit
- the same `family_seed` plus scenario ordering reproduces the same sampled
  family
- every sampled trace preserves the full canonical weather field set and
  explicit cloud-event annotations

## Stable Versus Experimental Sampling Controls

Stable first-release sampling controls:

- `WeatherSamplingRequest.num_steps`
- `WeatherSamplingRequest.scenario_count`
- `WeatherSamplingRequest.family_seed`
- `expected_timestep_hours` validation against the loaded artifact
- returned `timestamp_utc`, canonical field series, and cloud-event
  annotations in each sampled trace

Experimental or deferred controls:

- alternative stochastic backends beyond the current joint daily-block model
- caller-configured percentile sets or family-summary surfaces
- artifact auto-migration across schema versions
- blackout-aware simulator evaluation and summary outputs
- weather-derived blackout fitting or calibration

## Stochastic Validation Expectations

The current committed validation path for US2 is:

- `tests/unit/weather/test_sampling.py`
- `tests/integration/weather/test_offline_sampling.py`
- `tests/integration/weather/test_sampling_statistics.py`
- `tests/integration/weather/test_fixture_schema.py`

Expectation summary:

- replay from the same artifact and `family_seed` is exact
- every sampled trace returns exactly the requested `num_steps`
- physical-bounds enforcement keeps weather variables in documented ranges
- stochastic acceptance checks compare lag-1 autocorrelation, pairwise
  correlation, and cloud-event contiguity against deterministic synthetic
  training data

## Planned Public Surface

The stable first-release weather direction remains:

```python
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)
```

Simulator-side stochastic evaluation remains a separate surface:

```python
from open_energy_lab.simulator.stochastic_weather import evaluate_weather_family
```

The fit, load, and sampling request/entry point imports are implemented now.
Simulator-side family evaluation remains a later story.

## API Maturity And Dependency Boundary

Supporting policy updates for this feature live in:

- `docs/migration/api-maturity.md`
- `docs/migration/dependency-policy.md`

Current posture:

- `open_energy_lab.weather` root exports stable fit, load, and offline
  sampling behavior today
- `open_energy_lab.simulator.stochastic_weather` is a focused simulator-side
  placeholder module, not a package-root simulator export
- `pvlib`, `pandas`, and `timezonefinder` remain isolated fit/fetch
  dependencies and are not required for committed recorded-fixture validation

## Working Rule

Extend this note incrementally as sampling and simulator-family behavior land.
Record exact legacy references, preserved deterministic behavior, dependency
boundaries, and validation outcomes rather than broad stochastic-weather
claims.
