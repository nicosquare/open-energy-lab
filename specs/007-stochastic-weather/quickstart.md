# Quickstart: Stochastic Weather Generation And Simulator Integration

Use this quickstart to review the plan and exercise the implemented User Story
1 fit workflow, User Story 2 offline sampling workflow, and User Story 3
simulator family-evaluation workflow. The feature adds a reusable
`open_energy_lab.weather` capability for geolocation fetch, stochastic
fitting, persisted artifacts, and offline sampled weather families, then
integrates those sampled families into `open_energy_lab.simulator` without
replacing the current deterministic path.

## Review the Feature

```bash
sed -n '1,360p' specs/007-stochastic-weather/spec.md
sed -n '1,360p' specs/007-stochastic-weather/plan.md
sed -n '1,360p' specs/007-stochastic-weather/research.md
sed -n '1,360p' specs/007-stochastic-weather/data-model.md
```

Confirm the intended boundary:

- target code stays under `src/open_energy_lab/weather` and
  `src/open_energy_lab/simulator`
- fetch, fit, artifact persistence, and offline sampling belong to the weather
  package
- deterministic `BatteryLoadPVScenario` remains supported for direct debugging
- stochastic simulator integration adds a family surface rather than replacing
  the current deterministic trace path
- blackouts are caller-configured grid outages, not weather-fit behavior

## Review the Contracts

```bash
sed -n '1,240p' specs/007-stochastic-weather/contracts/weather-workflow-contract.md
sed -n '1,240p' specs/007-stochastic-weather/contracts/fitted-weather-artifact-contract.md
sed -n '1,240p' specs/007-stochastic-weather/contracts/weather-sampling-contract.md
sed -n '1,240p' specs/007-stochastic-weather/contracts/simulator-integration-contract.md
sed -n '1,240p' specs/007-stochastic-weather/contracts/validation-contract.md
```

Before implementation, make sure the contracts agree on:

- one complete canonical weather schema
- local-civil-time fitting and sampling semantics
- canonical `timestamp_utc` in returned traces
- one fixed timestep per persisted artifact
- fail-fast handling for missing fields, unsupported versions, and timestep
  mismatches
- one family seed plus scenario index derivation
- blackout semantics as grid outage only
- family summaries over core simulator outputs only

## Review the Legacy Evidence

```bash
sed -n '1,240p' legacy/old_tpm/src_py/weather/fetch.py
sed -n '1,260p' legacy/old_tpm/src_py/weather/pipeline.py
sed -n '1,220p' legacy/old_tpm/src_py/weather/models/gaussian.py
sed -n '1,220p' legacy/old_tpm/src_py/weather/models/enhanced.py
sed -n '1,220p' legacy/old_tpm/src_py/weather/analysis/drops.py
sed -n '1,220p' legacy/old_tpm/src_py/simulator/common/weather.py
sed -n '1,220p' legacy/old_tpm/src_py/simulator/common/pv.py
```

Use these sources to confirm:

- the geolocation-to-TMY workflow direction
- daily-block weather modeling direction
- irradiance-event modeling direction
- current simulator weather-to-PV coupling direction

Do not copy legacy runtime structure or preserve legacy per-variable fitting as
the stable contract without the documented improvements.

## Review the Current Upstream Library Surfaces

```bash
sed -n '1,220p' src/open_energy_lab/simulator/__init__.py
sed -n '1,220p' src/open_energy_lab/simulator/_weather_schema.py
sed -n '1,220p' src/open_energy_lab/simulator/weather.py
sed -n '1,240p' src/open_energy_lab/simulator/pv.py
sed -n '1,240p' src/open_energy_lab/simulator/stochastic_weather.py
sed -n '360,560p' src/open_energy_lab/simulator/scenario.py
sed -n '1,260p' tests/fixtures/simulator/README.md
```

Confirm from these files that:

- the current simulator already owns deterministic weather-backed PV behavior
- the canonical first-release field set already exists in `_weather_schema.py`
- the package root now exports the stable stochastic family-evaluation entry
  points lazily
- the sampled weather artifact keeps the full canonical field set while the
  current simulator PV path consumes only the deterministic fields it needs
- dependency isolation and fixture provenance rules are already documented

## Environment

The feature uses the same base environment as the current library:

```bash
conda activate open-energy-lab
uv sync --dev
```

The fit/fetch workflow may use isolated weather-specific dependencies, but
default artifact-load, sampling, and simulator-family validation remain usable
in the base development environment.

## Use The Implemented US1 Workflow

Run the current geolocation-to-artifact workflow from the committed recorded
fixture:

```bash
uv run python -c '
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
    output_path=Path("/tmp/us1-weather-artifact.json"),
)

reloaded = load_weather_artifact(
    Path("/tmp/us1-weather-artifact.json"),
    expected_timestep_hours=1.0,
)

print(artifact.artifact_id)
print(reloaded.schema_version)
'
```

Expected result:

- the fit workflow writes a JSON artifact without contacting a live weather
  service
- the reload step succeeds offline
- the artifact preserves local-civil-time semantics, canonical field order,
  and provenance

Exercise the committed failure-path fixtures:

```bash
uv run pytest tests/integration/weather/test_fit_workflow.py
uv run pytest tests/integration/weather/test_fixture_schema.py
```

These checks cover:

- missing canonical field rejection
- location-unavailable rejection
- supported artifact offline reload
- unsupported artifact version rejection

## Use The Implemented US2 Offline Sampling Workflow

Run the current artifact-to-family sampling workflow from the committed
artifact and request fixtures:

```bash
uv run python -c '
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

request_payload = json.loads(
    Path("tests/fixtures/weather/sampling_request_case.json").read_text()
)

family = sample_weather_family(
    artifact,
    request=WeatherSamplingRequest(
        num_steps=request_payload["num_steps"],
        scenario_count=request_payload["scenario_count"],
        family_seed=request_payload["family_seed"],
    ),
    expected_timestep_hours=request_payload["expected_timestep_hours"],
)

print(family.family_id)
print(len(family.sampled_traces))
print(len(family.sampled_traces[0].timestamp_utc))
print(len(family.sampled_traces[1].cloud_event_annotations))
'
```

Expected result:

- the family loads and samples entirely offline from the committed artifact
- both scenarios preserve the full canonical field set
- each sampled trace returns exactly `3` timestamps from the paired request
  fixture
- replay from the same `family_seed` reproduces the committed family fixture
- cloud-event annotations remain explicit even when a trace has no events

Exercise the committed US2 validation paths:

```bash
uv run pytest tests/unit/weather/test_sampling.py tests/integration/weather/test_offline_sampling.py
uv run pytest tests/integration/weather/test_sampling_statistics.py tests/integration/weather/test_fixture_schema.py
```

These checks cover:

- exact-horizon family sampling for arbitrary positive `num_steps`
- deterministic replay from one family seed and scenario ordering
- physical-bounds enforcement and cloud-event overlays
- stochastic acceptance thresholds for lag-1 autocorrelation, pairwise
  correlation, and event contiguity
- replay of the committed sampling request and sampled-family fixtures

## Use The Implemented US3 Simulator Family Workflow

Run the current sampled-weather simulator family workflow from the committed
artifact and sampling fixtures:

```bash
uv run python -c '
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
    SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    TimeGrid,
    WeatherComponent,
    WeatherFamilyEvaluationRequest,
    evaluate_weather_family,
)
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    load_weather_artifact,
    sample_weather_family,
)

artifact = load_weather_artifact(
    json.loads(Path("tests/fixtures/weather/fitted_weather_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)
request_payload = json.loads(
    Path("tests/fixtures/weather/sampling_request_case.json").read_text()
)
family = sample_weather_family(
    artifact,
    request=WeatherSamplingRequest(
        num_steps=request_payload["num_steps"],
        scenario_count=request_payload["scenario_count"],
        family_seed=request_payload["family_seed"],
    ),
    expected_timestep_hours=request_payload["expected_timestep_hours"],
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
        source="quickstart",
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
        source="quickstart",
    ),
)
result = evaluate_weather_family(
    WeatherFamilyEvaluationRequest(
        base_scenario_reference=base_scenario,
        weather_family=family,
        summary_output_fields=SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    )
)

print(result.family_id)
print([item.scenario_index for item in result.scenario_results])
print(tuple(result.summary_statistics))
print(result.scenario_results[0].blackout_active)
'
```

Expected result:

- the simulator evaluates both sampled scenarios without changing the
  deterministic `BatteryLoadPVScenario` API
- the scenario ordering stays `[0, 1]`
- the built-in summary keys stay limited to the documented core simulator
  outputs
- the no-blackout path returns `False` for every element in the
  `blackout_active` series

Exercise the committed US3 validation paths:

```bash
uv run pytest tests/unit/simulator/test_stochastic_weather.py
uv run pytest tests/integration/simulator/test_stochastic_weather_family.py tests/integration/simulator/test_blackout_semantics.py
uv run pytest tests/integration/simulator/test_weather_family_fixture_schema.py
```

These checks cover:

- preserved deterministic debugging through the existing fixed-weather path
- scenario-indexed simulator results from the committed sampled family
- explicit grid-outage blackout semantics with unmet-load tracking
- committed simulator family-fixture provenance and baseline result shape

## Expected Implementation Targets

After implementation, the main touched areas should be:

```text
src/open_energy_lab/weather/
src/open_energy_lab/simulator/
tests/unit/weather/
tests/unit/simulator/
tests/integration/weather/
tests/integration/simulator/
tests/fixtures/weather/
tests/fixtures/simulator/
docs/migration/
```

The implementation should stay narrow. One or a few small deterministic and
recorded fixtures are enough if they prove:

- canonical fetch normalization is correct
- fitted artifacts preserve the documented schema and provenance
- offline artifact loading works without network access
- sampled weather traces preserve the full canonical field set
- family sampling is reproducible from one family seed
- blackout-aware simulator results expose unmet load explicitly
- family summaries are limited to documented core simulator outputs

Current committed fixture choices:

- provider responses use three hourly records to keep the normalization review
  surface small
- artifact fixtures use a synthetic daily timestep payload so the committed
  covariance matrix stays reviewable
- sampled-family fixtures keep only two scenarios across three steps
- simulator family fixtures record one no-blackout baseline and one explicit
  grid-outage baseline

## Stable And Experimental Surface

Stable first-release behavior:

- `open_energy_lab.weather` fit workflow
- canonical weather normalization
- versioned fitted-artifact persistence and loading
- `WeatherSamplingRequest` plus offline fixed-timestep family sampling from
  one family seed
- simulator scenario-family evaluation with grid-outage blackouts
- built-in min/mean/max/5th/50th/95th summaries for core simulator outputs

Experimental or deferred behavior:

- alternative model backends
- caller-configurable percentile sets
- raw-weather-variable family summaries
- artifact auto-migration
- blackout fitting or calibration from weather data

## Public Entry Points

The stable weather package direction is:

```python
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)
```

Stable sampling controls today:

- `WeatherSamplingRequest.num_steps`
- `WeatherSamplingRequest.scenario_count`
- `WeatherSamplingRequest.family_seed`
- `expected_timestep_hours` validation against the artifact timestep

Simulator-side integration remains distinct from the deterministic path, for
example:

```python
from open_energy_lab.simulator import (
    BatteryLoadPVScenario,
    WeatherFamilyEvaluationRequest,
    evaluate_weather_family,
)
```

The artifact-versus-simulator-consumed field boundary is explicit:

- the weather artifact and sampled traces preserve the full first-release
  canonical weather field set
- the current simulator PV path consumes dry-bulb temperature and the
  irradiance fields named on `PVComponent.irradiance_field_names`
- other canonical fields remain available for future simulator or analysis
  consumers but are not silently required by the current deterministic PV path

## Dependency Boundary Notes

Current dependency classification for the shipped implementation:

- core weather capability:
  - Python standard library
  - `pvlib`
  - `pandas`
  - `timezonefinder`
- optional validation tooling:
  - `pytest`
- legacy-only evidence:
  - all cited legacy weather and simulator reference files

Heavy research stacks remain outside the base import path:
TorchRL, PyTorch, solver stacks, notebooks, W&B, GPU/SLURM tooling, Rust
toolchains, and CityLearn runtime.

Default review and validation stay offline unless a reviewer explicitly opts
into live PVGIS fetch checks. Recorded fixtures are the primary evidence for
the fit workflow.

## Validation Commands

```bash
uv run pytest tests/unit/weather tests/integration/weather tests/integration/simulator
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/weather src/open_energy_lab/simulator tests/unit/weather tests/unit/simulator tests/integration/weather tests/integration/simulator docs/migration
```

## Migration Documentation Review

Use the migration docs in this order when reviewing the shipped feature:

1. `docs/migration/stochastic-weather.md`
2. `docs/migration/api-maturity.md`
3. `docs/migration/dependency-policy.md`
4. `docs/migration/fixture-provenance.md`
5. `docs/migration/environment-assumptions.md`

## Focused Validation Commands

```bash
uv run pytest tests/unit/weather/test_canonical_schema.py tests/unit/weather/test_artifact_schema.py tests/unit/weather/test_sampling.py
uv run pytest tests/integration/weather/test_fit_workflow.py tests/integration/weather/test_fixture_schema.py tests/integration/weather/test_offline_sampling.py
uv run pytest tests/unit/simulator/test_stochastic_weather.py tests/integration/simulator/test_stochastic_weather_family.py tests/integration/simulator/test_blackout_semantics.py tests/integration/simulator/test_weather_family_fixture_schema.py
```

Routine local review should prefer recorded fixtures over live network fetches.

## Recorded Validation Outcomes

Recorded on `2026-06-14` from the default local conda plus `uv` environment:

- `uv run pytest tests/unit/weather tests/integration/weather tests/integration/simulator`
  passed with `96 passed`
- `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py`
  passed with `32 passed`
- `uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.simulator"`
  passed without output
- `rg "from legacy|import legacy" src/open_energy_lab/weather src/open_energy_lab/simulator tests/unit/weather tests/unit/simulator tests/integration/weather tests/integration/simulator docs/migration`
  returned no matches after migration-doc wording was tightened to avoid a
  false positive in documentation text

Validation notes:

- the first broad simulator validation run exposed a controller-runner
  regression where controller-driven `BatteryLoadPVScenario` traces no longer
  populated `unmet_load_kw` and `blackout_active`; the shipped implementation
  now aligns controller evaluation with the deterministic blackout-aware trace
  contract and the suite passes
- live PVGIS fetch behavior was intentionally not exercised in the default
  validation subset
- live PVGIS fetch was intentionally not part of the recorded default
  validation path even though the base environment now includes the weather
  fit/fetch dependencies
- no solver, GPU, SLURM, W&B, notebook, Rust, or external-service setup was
  required for the executed subset

## Preserve / Improve / Reject Summary

Preserve:

- geolocation as the stable fit input
- deterministic simulator debugging through the existing fixed-weather path
- offline default validation using committed fixtures

Improve:

- full ten-field canonical normalization in local civil time
- persisted JSON artifacts with explicit provenance and timestep lock
- committed simulator family fixtures with explicit blackout semantics and
  bounded summary fields

Reject:

- partial artifacts with missing canonical fields
- implicit version migration on load
- hidden simulator consumption of undocumented weather fields
- any requirement to hit a live provider for routine validation

## Checks Intentionally Out of Scope

This feature should not require or run as part of default validation:

- notebooks or dashboards
- W&B workflows
- GPU or SLURM execution
- live network fetches for every routine test run
- solver-backed planning
- RL training loops
- Rust builds
- legacy runtime execution as a feature gate
