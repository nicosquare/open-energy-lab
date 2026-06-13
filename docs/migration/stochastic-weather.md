# Stochastic Weather Migration Note

Status: Phase 2 foundational scaffolding only

Spec `007-stochastic-weather` now reserves the target library paths, fixture
records, and migration-documentation boundary for a new
`open_energy_lab.weather` capability plus simulator-side stochastic weather
evaluation. This foundational slice still does not ship fit, sampling, or
simulator family behavior, but it now adds import-light module scaffolding and
documented package-root placeholder exports that later tasks will populate and
validate.

## Target Module Paths

- `src/open_energy_lab/weather/__init__.py`
- `src/open_energy_lab/weather/_canonical.py`
- `src/open_energy_lab/weather/tmy.py`
- `src/open_energy_lab/weather/fit.py`
- `src/open_energy_lab/weather/artifact.py`
- `src/open_energy_lab/weather/sampling.py`
- `src/open_energy_lab/weather/events.py`
- `src/open_energy_lab/simulator/stochastic_weather.py`

## Foundational Package Boundary

The new reserved package surface now exists in source control with import-light
placeholders:

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
- weather submodules remain free of runtime `legacy/*` imports
- placeholder call sites raise `NotImplementedError` until user-story tasks
  add tested behavior
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

## Preserve / Improve / Reject

### Preserve

- `BatteryLoadPVScenario` remains the deterministic single-scenario simulator
  path for direct debugging.
- Legacy repositories remain reference-only evidence, not runtime imports.
- Default validation stays CPU-local and uses recorded fixtures rather than
  routine live weather fetches.

### Improve

- Add a library-owned `open_energy_lab.weather` package that cleanly separates
  geolocation fetch, canonical normalization, artifact persistence, and
  offline sampling from simulator execution ownership.
- Commit reviewable weather and simulator fixture paths early so later user
  stories can populate deterministic evidence instead of inventing paths late.
- Document blackout semantics as explicit simulator-side grid outages rather
  than implicit weather degradation.

### Reject

- New runtime code under `legacy/*`
- Base-import dependence on network-backed fetch tooling
- Partial artifacts with missing canonical weather fields
- Blackout semantics inferred from irradiance attenuation alone

## Fixture Record

Foundational scaffolding currently creates these placeholders only:

- `tests/fixtures/weather/recorded_pvgis_tmy_response.json`
- `tests/fixtures/weather/location_unavailable_response.json`
- `tests/fixtures/weather/fitted_weather_artifact_v1.json`
- `tests/fixtures/simulator/stochastic_weather_family_case.json`
- `tests/fixtures/simulator/blackout_weather_family_case.json`

Current expectations:

- placeholders establish committed paths and provenance intent
- final fixture payloads remain small, reviewable, and deterministic
- weather fixtures document provider provenance, canonical field coverage, and
  offline-use expectations
- simulator fixtures document scenario ordering, summary fields, blackout
  semantics, and numeric tolerance

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

These imports are now reserved in source control, but the underlying behavior
is not implemented by this foundational slice yet.

## API Maturity And Dependency Boundary

Supporting policy updates for this foundational slice live in:

- `docs/migration/api-maturity.md`
- `docs/migration/dependency-policy.md`

Current posture:

- `open_energy_lab.weather` root exports are reserved but not yet promoted to
  stable shipped behavior
- `open_energy_lab.simulator.stochastic_weather` is a focused simulator-side
  placeholder module, not a package-root simulator export
- `pvlib`, `pandas`, and `timezonefinder` remain isolated future fit/fetch
  dependencies and are not imported by the current scaffolding

## Working Rule

Populate the scaffolded files incrementally with focused tests first. Any
later migration note updates should record exact legacy references, preserved
deterministic behavior, dependency boundaries, and validation outcomes rather
than broad stochastic-weather claims.
