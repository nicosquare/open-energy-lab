# Stochastic Weather Migration Note

Status: User Stories 1 through 3 implemented

Spec `007-stochastic-weather` now ships the first stable weather-package slice:
geolocation input, PVGIS-style TMY normalization, deterministic artifact
fitting, JSON persistence, offline artifact loading, and seeded offline family
sampling. It also now ships simulator family evaluation from loaded sampled
weather, explicit grid-outage blackout semantics, and package-root simulator
exports for the stochastic family-evaluation entry points while preserving the
existing deterministic `BatteryLoadPVScenario` debugging path.

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
workflow, and the simulator package root now exposes the shipped family
evaluation surface:

```python
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)

from open_energy_lab.simulator import (
    SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    WeatherFamilyEvaluationRequest,
    evaluate_weather_family,
)
```

Current expectation:

- package-root weather exports stay lazy and import-light
- package-root simulator exports stay lazy and import-light
- `fit_weather_model` performs the geolocation-to-artifact workflow
- `load_weather_artifact` works from committed JSON without network access
- `WeatherSamplingRequest` is the stable first-release request type for seeded
  offline family sampling
- `sample_weather_family` and `WeatherArtifact.sample_family(...)` both sample
  reproducible arbitrary-horizon weather families from a loaded artifact
- `WeatherFamilyEvaluationRequest` binds one deterministic base scenario to
  one sampled weather family plus optional blackout traces
- `evaluate_weather_family` returns per-scenario simulator traces plus built-in
  min/mean/max/5th/50th/95th summaries for supported core simulator outputs
- weather submodules remain free of runtime `legacy/*` imports
- simulator stochastic evaluation remains separate from, and does not replace,
  the deterministic `BatteryLoadPVScenario` path

## Current Validation Paths

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

## Current Simulator Fixtures

The simulator fixture set is now active for the family-evaluation workflow:

- `tests/fixtures/simulator/stochastic_weather_family_case.json`
- `tests/fixtures/simulator/blackout_weather_family_case.json`

Current expectations:

- the no-blackout fixture preserves scenario ordering and deterministic
  no-outage results from the same sampled weather family
- the blackout fixture keeps outage semantics explicit through zeroed
  grid-exchange, zero settlement, and unmet-load series
- both fixtures point back to the committed weather artifact and sampled-family
  fixtures rather than requiring live fitting or sampling during review
- both fixtures keep fixed summary fields, numeric tolerance, and baseline
  scenario inputs reviewable in git

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

`WeatherFitConfig(timestep_hours=..., monthly=True)` fits one day-vector
Gaussian per local calendar month instead of one for the whole year
(`base_model_kind="monthly-daily-block-summary"`, components in
`base_model_parameters["monthly_components"]`). Sampling draws one month per
scenario, weighted by its training days, and samples all of that scenario's
days from it. A single all-year Gaussian mixes seasons, so its tails can
produce days hotter or sunnier than any training day; on the Abu Dhabi TMY the
all-year model put 4.5% of sampled days above the warmest training day and
the monthly model 0.3%. Each month needs at least two complete local days.
Monthly components also store each irradiance field's observed per-step
maximum (`maximum_by_step`), and sampled GHI, direct and diffuse irradiance are
capped at it, since the Gaussian otherwise exceeds clear-sky levels
(Abu Dhabi: days sunnier than any training day fell from 2.9% to 0.2%).
Temperature is not capped.
The default (`monthly=False`) is unchanged, including its random stream.

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

## Simulator Family Evaluation Usage

The current simulator family workflow is:

```python
from pathlib import Path
import json

from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    BatteryComponent,
    BatteryLoadPVScenario,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    TimeGrid,
    WeatherComponent,
    WeatherFamilyEvaluationRequest,
    evaluate_weather_family,
)
from open_energy_lab.weather import WeatherSamplingRequest, load_weather_artifact, sample_weather_family

artifact = load_weather_artifact(
    json.loads(Path("tests/fixtures/weather/fitted_weather_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)
family = sample_weather_family(
    artifact,
    request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=13),
    expected_timestep_hours=24.0,
)
trace = family.sampled_traces[0]
grid = TimeGrid(num_steps=len(trace.timestamp_utc), time_step_hours=trace.timestep_hours)
weather = WeatherComponent(
    name="sampled-weather-0",
    time_grid=grid,
    timestamp_utc=list(trace.timestamp_utc),
    dry_bulb_air_temperature_c=list(trace.canonical_field_series["dry_bulb_air_temperature_c"]),
    global_horizontal_irradiance_w_per_m2=list(
        trace.canonical_field_series["global_horizontal_irradiance_w_per_m2"]
    ),
    direct_beam_irradiance_w_per_m2=list(
        trace.canonical_field_series["direct_beam_irradiance_w_per_m2"]
    ),
    diffuse_horizontal_irradiance_w_per_m2=list(
        trace.canonical_field_series["diffuse_horizontal_irradiance_w_per_m2"]
    ),
    deferred_fields=(
        "relative_humidity_pct",
        "infrared_radiation_downwards_w_per_m2",
        "windspeed_10m_m_per_s",
        "wind_direction_10m_deg",
        "surface_air_pressure_pa",
    ),
    source=trace.derived_identity,
)
base_scenario = BatteryLoadPVScenario(
    scenario_id="stochastic-weather-base",
    time_grid=grid,
    battery=BatteryComponent(
        name="battery",
        capacity_kwh=8.0,
        max_charge_kw=3.0,
        max_discharge_kw=3.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=0.25,
    ),
    load=LoadComponent(
        name="load",
        demand_kw=[3.0, 1.0, 4.0],
        interpretation="exogenous-consumption",
        time_grid=grid,
        source="migration-note",
    ),
    weather=weather,
    pv=PVComponent(
        name="pv",
        rated_power_kw=4.0,
        temperature_coefficient_pct_per_c=-0.4,
        reference_irradiance_w_per_m2=1000.0,
        reference_temperature_c=25.0,
        derivation_name="ghi-linear-temperature-adjusted",
        irradiance_field_names=("global_horizontal_irradiance_w_per_m2",),
    ),
    price_signal=PriceSignal(
        currency="USD",
        unit_rate_name="energy-price",
        import_prices=[0.10, 0.20, 0.30],
        export_price_ratio=0.8,
        interpretation="discounted export relative to import prices",
        time_alignment="step-start",
        time_grid=grid,
    ),
    objective=ArbitrageObjectiveRepresentation(
        objective_name="grid-settlement",
        settlement_basis="grid-settlement",
        allow_export=True,
        export_price_ratio=0.8,
    ),
    dispatch_requests=DispatchRequestSeries(
        requested_power_kw=[0.0, 0.0, 0.0],
        sign_convention="charge",
        source="migration-note",
    ),
)

result = evaluate_weather_family(
    WeatherFamilyEvaluationRequest(
        base_scenario_reference=base_scenario,
        weather_family=family,
        summary_output_fields=SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    )
)
```

This preserves the intended US3 boundary:

- the simulator still owns execution semantics and settlement behavior
- the sampled weather artifact keeps the full canonical weather field set, but
  the current PV path consumes only the deterministic weather fields it needs:
  dry-bulb temperature plus the irradiance series configured on the PV
  component
- blackout traces remain caller-configured simulator inputs, never fitted
  weather behavior
- repeated evaluation from the same artifact, family seed, and scenario
  ordering reproduces both scenario results and family summaries

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
- caller-configured percentile sets or alternate family-summary surfaces
- artifact auto-migration across schema versions
- weather-derived blackout fitting or calibration

## Stochastic Validation Expectations

The current committed validation path for US2 and US3 is:

- `tests/unit/weather/test_sampling.py`
- `tests/integration/weather/test_offline_sampling.py`
- `tests/integration/weather/test_sampling_statistics.py`
- `tests/integration/weather/test_fixture_schema.py`
- `tests/unit/simulator/test_stochastic_weather.py`
- `tests/integration/simulator/test_stochastic_weather_family.py`
- `tests/integration/simulator/test_blackout_semantics.py`
- `tests/integration/simulator/test_weather_family_fixture_schema.py`

Expectation summary:

- replay from the same artifact and `family_seed` is exact
- every sampled trace returns exactly the requested `num_steps`
- physical-bounds enforcement keeps weather variables in documented ranges
- stochastic acceptance checks compare lag-1 autocorrelation, pairwise
  correlation, and cloud-event contiguity against deterministic synthetic
  training data
- deterministic simulator debugging remains available through the existing
  fixed-weather path
- simulator family evaluation preserves scenario indices and bounded summary
  fields
- blackout validation keeps grid-outage semantics explicit and separate from
  irradiance attenuation

## Stable Public Surface

The stable first-release weather direction is:

```python
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)
```

The stable simulator family-evaluation direction is:

```python
from open_energy_lab.simulator import (
    SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    WeatherFamilyEvaluationRequest,
    WeatherFamilyEvaluationResult,
    WeatherScenarioEvaluationResult,
    evaluate_weather_family,
)
```

These shipped imports preserve a narrow stable boundary:

- weather fit/load/sample behavior at `open_energy_lab.weather`
- simulator family evaluation at `open_energy_lab.simulator`
- implementation-facing modeling details still live in focused submodules

## API Maturity And Dependency Boundary

Supporting policy updates for this feature live in:

- `docs/migration/api-maturity.md`
- `docs/migration/dependency-policy.md`

Current posture:

- `open_energy_lab.weather` root exports stable fit, load, and offline
  sampling behavior today
- `open_energy_lab.simulator` root now exports the stable stochastic family
  evaluation request, result, and entry-point symbols lazily
- `open_energy_lab.simulator.stochastic_weather` remains the focused
  implementation module behind that stable root surface
- `pvlib`, `pandas`, and `timezonefinder` remain isolated fit/fetch
  dependencies and are not required for committed recorded-fixture validation

## Working Rule

Extend this note incrementally as later polish and validation tasks land.
Record exact legacy references, preserved deterministic behavior, the
artifact-versus-simulator-consumed field boundary, blackout semantics, and
validation outcomes rather than broad stochastic-weather claims.
