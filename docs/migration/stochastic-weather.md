# Stochastic Weather Migration Note

Status: Phase 1 setup scaffolding only

Spec `007-stochastic-weather` reserves the target library paths, fixture
records, and migration-documentation boundary for a new
`open_energy_lab.weather` capability plus simulator-side stochastic weather
evaluation. This Phase 1 slice does not ship fit, sampling, or simulator
family behavior yet. It establishes the committed scaffolding that later tasks
will populate and validate.

## Target Module Paths

- `src/open_energy_lab/weather/__init__.py`
- `src/open_energy_lab/weather/_canonical.py`
- `src/open_energy_lab/weather/tmy.py`
- `src/open_energy_lab/weather/fit.py`
- `src/open_energy_lab/weather/artifact.py`
- `src/open_energy_lab/weather/sampling.py`
- `src/open_energy_lab/weather/events.py`
- `src/open_energy_lab/simulator/stochastic_weather.py`

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

Phase 1 creates these scaffold placeholders only:

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

These imports are design targets only in Phase 1. They are not implemented by
this setup slice.

## Working Rule

Populate the scaffolded files incrementally with focused tests first. Any
later migration note updates should record exact legacy references, preserved
deterministic behavior, dependency boundaries, and validation outcomes rather
than broad stochastic-weather claims.
