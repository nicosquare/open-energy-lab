# Stochastic Weather Migration Note

Status: User Story 1 geolocation-to-artifact workflow implemented

Spec `007-stochastic-weather` now ships the first stable weather-package slice:
geolocation input, PVGIS-style TMY normalization, deterministic artifact
fitting, JSON persistence, and offline artifact loading. Sampling and
simulator-family evaluation remain later-story work, but the package root now
exports the fit and load entry points behind the same import-light lazy-loading
boundary.

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

The weather package root now exposes the implemented US1 fit and load
workflow, while leaving the planned sampler export in place for later work:

```python
from open_energy_lab.weather import (
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
- weather submodules remain free of runtime `legacy/*` imports
- `sample_weather_family` remains a later-story placeholder
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

## Current US1 Fixtures

The weather fixture set is now active for the fit workflow:

- `tests/fixtures/weather/recorded_pvgis_tmy_response.json`
- `tests/fixtures/weather/missing_required_field_response.json`
- `tests/fixtures/weather/location_unavailable_response.json`
- `tests/fixtures/weather/fitted_weather_artifact_v1.json`
- `tests/fixtures/weather/fitted_weather_artifact_unsupported_version.json`

Current expectations:

- positive-path and fail-fast provider responses remain small and deterministic
- the supported artifact remains human-reviewable by using a synthetic daily
  timestep payload
- artifact fixtures include full schema, provenance, and offline load metadata
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

## Planned Public Surface

The stable first-release weather direction remains:

```python
from open_energy_lab.weather import (
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)
```

Simulator-side stochastic evaluation remains a separate surface:

```python
from open_energy_lab.simulator.stochastic_weather import evaluate_weather_family
```

The fit and load imports are implemented now. The sampling import remains part
of the planned surface for later stories.

## API Maturity And Dependency Boundary

Supporting policy updates for this feature live in:

- `docs/migration/api-maturity.md`
- `docs/migration/dependency-policy.md`

Current posture:

- `open_energy_lab.weather` root exports stable fit and load behavior today
- `open_energy_lab.simulator.stochastic_weather` is a focused simulator-side
  placeholder module, not a package-root simulator export
- `pvlib`, `pandas`, and `timezonefinder` remain isolated fit/fetch
  dependencies and are not required for committed recorded-fixture validation

## Working Rule

Extend this note incrementally as sampling and simulator-family behavior land.
Record exact legacy references, preserved deterministic behavior, dependency
boundaries, and validation outcomes rather than broad stochastic-weather
claims.
