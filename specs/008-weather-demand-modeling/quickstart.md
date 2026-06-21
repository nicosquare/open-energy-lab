# Quickstart: Weather-Conditioned Demand Modeling And Simulator Integration

Use this quickstart to review the planned demand feature and to prepare the
implementation and validation workflow. The feature adds a reusable
`open_energy_lab.demand` capability for aligned-history fitting, persisted
artifacts, and offline weather-conditioned demand sampling, then integrates
those sampled demand families into `open_energy_lab.simulator` without
replacing the current deterministic path. The current implementation now
includes the simulator-side cooling-aware family surface and committed
reviewable fixtures for both local-electric and district-cooling service.

## Preserve / Improve / Reject

Keep these migration decisions in mind while reviewing or extending the
feature:

- Preserve: separate weather and demand artifacts, explicit non-thermal and
  cooling outputs, offline default validation, and simulator-side ownership of
  blackout and cooling-service semantics.
- Improve: a stable `open_energy_lab.demand` root surface, committed active
  US1 fixtures, and a fully offline aligned-history-to-artifact workflow.
- Reject: merged weather-and-demand artifacts, total-load-only training input,
  live-service assumptions in routine review, and partial artifact creation
  after fail-fast input validation.

## Review The Feature

```bash
sed -n '1,360p' specs/008-weather-demand-modeling/spec.md
sed -n '1,360p' specs/008-weather-demand-modeling/plan.md
sed -n '1,360p' specs/008-weather-demand-modeling/research.md
sed -n '1,360p' specs/008-weather-demand-modeling/data-model.md
```

Confirm the intended boundary:

- target code stays under `src/open_energy_lab/demand` and
  `src/open_energy_lab/simulator`
- demand fitting, artifact persistence, and offline sampling belong to the new
  demand package
- deterministic `BatteryLoadPVScenario` remains supported for direct debugging
- paired simulator integration adds a cooling-aware family surface rather than
  replacing the deterministic trace path
- blackout semantics remain simulator-side and separate from both weather and
  demand fitting

## Review The Contracts

```bash
sed -n '1,240p' specs/008-weather-demand-modeling/contracts/demand-workflow-contract.md
sed -n '1,240p' specs/008-weather-demand-modeling/contracts/fitted-demand-artifact-contract.md
sed -n '1,240p' specs/008-weather-demand-modeling/contracts/demand-sampling-contract.md
sed -n '1,240p' specs/008-weather-demand-modeling/contracts/simulator-integration-contract.md
sed -n '1,240p' specs/008-weather-demand-modeling/contracts/validation-contract.md
```

Before implementation, make sure the contracts agree on:

- explicit aligned historical non-thermal electric demand and cooling demand
  in `RT`
- separate producer-side weather and demand artifacts
- one shared paired-family seed and scenario ordering
- exact one-path cooling service validation per scenario
- local electric cooling as `kW` per `RT` conversion
- district cooling as deterministic served-`RT-hour` settlement
- explicit unserved cooling outputs
- offline default validation with fixture-backed evidence

## Review The Legacy Evidence

```bash
sed -n '1,240p' legacy/old_tpm/src_py/simulator/common/pricing.py
rg -n "non_shiftable_load|cool|thermal|district|weather|temperature|demand" \
  legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb \
  legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb \
  legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb \
  legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb
```

Use these sources to confirm:

- deterministic tariff direction remains relevant to simulator settlement
- district-cooling settlement in the new simulator path is an inference from
  that same step-start tariff discipline rather than a copied legacy runtime
  district-cooling module
- notebook material motivates weather-sensitive demand and explicit thermal
  load concepts
- non-shiftable electric load and cooling-like thermal loads should not be
  merged into one stable library output
- CityLearn-specific runtime behavior is conceptual evidence, not a runtime
  dependency or parity target

## Review The Current Upstream Library Surfaces

```bash
sed -n '1,220p' src/open_energy_lab/weather/__init__.py
sed -n '1,260p' src/open_energy_lab/weather/artifact.py
sed -n '1,260p' src/open_energy_lab/weather/sampling.py
sed -n '1,220p' src/open_energy_lab/simulator/__init__.py
sed -n '1,260p' src/open_energy_lab/simulator/load.py
sed -n '240,520p' src/open_energy_lab/simulator/scenario.py
sed -n '1,260p' src/open_energy_lab/simulator/stochastic_weather.py
sed -n '1,220p' tests/unit/test_optional_dependency_boundaries.py
```

Confirm from these files that:

- the current simulator already owns deterministic load, weather, PV, and
  blackout-aware evaluation semantics
- the weather package already owns canonical weather artifacts and offline
  weather-family sampling
- the stable package roots are lazy and import-light
- weather fit and live-fetch dependencies stay isolated from routine imports
- the new demand package needs to follow the same boundary discipline

## Environment

The feature uses the same base environment as the current library:

```bash
conda activate open-energy-lab
uv sync --dev
```

Default validation for this feature must remain offline and fixture-backed. No
CityLearn install, solver license, notebook runtime, GPU, SLURM access, or
live weather fetch is required for routine review.

## After Implementation: Exercise The Planned US1 Workflow

Run the planned aligned-history-to-artifact workflow from committed fixtures:

```bash
uv run python -c '
from pathlib import Path
import json

from open_energy_lab.demand import fit_demand_model, load_demand_artifact

training_payload = json.loads(
    Path("tests/fixtures/demand/aligned_training_case.json").read_text()
)

artifact = fit_demand_model(
    training_payload,
    output_path=Path("/tmp/us1-demand-artifact.json"),
)

reloaded = load_demand_artifact(
    Path("/tmp/us1-demand-artifact.json"),
    expected_timestep_hours=training_payload["timestep_hours"],
)

print(artifact.artifact_id)
print(reloaded.schema_version)
'
```

Expected result:

- the fit workflow writes a JSON artifact without using live services
- the reload step succeeds offline
- the artifact preserves separate non-thermal electric and cooling outputs,
  required weather drivers, and provenance

## After Implementation: Reload The Committed US1 Artifact Offline

Use the committed artifact fixture directly when reviewing the stable reload
surface without refitting:

```bash
uv run python -c '
from pathlib import Path
import json

from open_energy_lab.demand import load_demand_artifact

artifact = load_demand_artifact(
    json.loads(Path("tests/fixtures/demand/fitted_demand_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)

print(artifact.artifact_id)
print(tuple(artifact.required_weather_field_order))
print(artifact.double_counting_policy)
'
```

Expected result:

- artifact reload succeeds entirely offline from the committed JSON fixture
- the timestep lock remains explicit
- the required weather drivers and double-counting policy stay reviewable
  without re-running the fit step

## After Implementation: Exercise The Planned US2 Offline Sampling Workflow

The first-release paired-family contract is strict:

- the weather family seed and `DemandSamplingRequest.paired_family_seed` must
  match exactly
- demand sampling preserves the weather family scenario ordering exactly
- replaying the same weather family plus demand request reproduces the same
  per-step demand outputs without refitting

For a committed review path, the repository now includes:

- `tests/fixtures/demand/sampling_request_case.json`
- `tests/fixtures/demand/sampled_demand_family_case.json`
- `tests/fixtures/weather/sampled_weather_family_case.json`

Run the planned artifact-to-family sampling workflow from committed artifact
and weather-family fixtures:

```bash
uv run python -c '
from pathlib import Path
import json

from open_energy_lab.demand import (
    DemandSamplingRequest,
    load_demand_artifact,
    sample_demand_family,
)
from open_energy_lab.weather import WeatherSamplingRequest, load_weather_artifact, sample_weather_family

weather_artifact = load_weather_artifact(
    json.loads(Path("tests/fixtures/weather/fitted_weather_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)
weather_family = sample_weather_family(
    weather_artifact,
    request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=91),
    expected_timestep_hours=24.0,
)
demand_artifact = load_demand_artifact(
    json.loads(Path("tests/fixtures/demand/fitted_demand_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)
demand_family = sample_demand_family(
    demand_artifact,
    request=DemandSamplingRequest(
        weather_family_reference=weather_family,
        num_steps=3,
        scenario_count=2,
        paired_family_seed=91,
    ),
)

print(demand_family.family_id)
print(len(demand_family.sampled_traces))
print(demand_family.sampled_traces[0].scenario_index)
'
```

Expected result:

- the family loads and samples entirely offline from committed artifacts and
  weather fixtures
- both scenarios preserve explicit non-thermal electric and cooling demand
  outputs
- replay from the same paired-family seed reproduces the same ordering and
  sampled values
- the committed demand request and sampled-family fixtures remain auditable
  examples of the exact shared-seed contract

## After Implementation: Exercise The Implemented US3 Cooling-Aware Simulator Workflow

The first-release simulator contract now adds one stable paired-family
evaluation surface with exactly one configured cooling service path per family.

Committed review fixtures include:

- `tests/fixtures/simulator/demand_local_electric_family_case.json`
- `tests/fixtures/simulator/demand_district_cooling_family_case.json`
- `tests/fixtures/simulator/demand_invalid_mixed_cooling_case.json`

Run the implemented cooling-aware family workflow from the committed weather
and demand family fixtures:

```bash
uv run python -c '
from pathlib import Path
import json

from open_energy_lab.demand import DemandSamplingRequest, load_demand_artifact, sample_demand_family
from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    BatteryComponent,
    BatteryLoadPVScenario,
    DemandFamilyEvaluationRequest,
    DispatchRequestSeries,
    LoadComponent,
    PVComponent,
    PriceSignal,
    evaluate_demand_family,
)
from open_energy_lab.simulator._units import POSITIVE_DISPATCH_MEANING
from open_energy_lab.simulator.demand import (
    CoolingServiceConfiguration,
    DistrictCoolingTariff,
    LocalElectricCoolingConfiguration,
)
from open_energy_lab.simulator.weather import weather_component_from_sampled_trace
from open_energy_lab.weather import WeatherSamplingRequest, load_weather_artifact, sample_weather_family

weather_artifact = load_weather_artifact(
    json.loads(Path("tests/fixtures/weather/fitted_weather_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)
weather_family = sample_weather_family(
    weather_artifact,
    request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=13),
    expected_timestep_hours=24.0,
)
demand_artifact = load_demand_artifact(
    json.loads(Path("tests/fixtures/demand/fitted_demand_artifact_v1.json").read_text()),
    expected_timestep_hours=24.0,
)
demand_family = sample_demand_family(
    demand_artifact,
    request=DemandSamplingRequest(
        weather_family_reference=weather_family,
        num_steps=3,
        scenario_count=2,
        paired_family_seed=13,
    ),
)

weather = weather_component_from_sampled_trace(weather_family.sampled_traces[0])
grid = weather.time_grid
base_scenario = BatteryLoadPVScenario(
    scenario_id="quickstart-demand-family",
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
        name="placeholder-load",
        demand_kw=[0.0] * grid.num_steps,
        interpretation="exogenous-consumption",
        time_grid=grid,
        source="quickstart-placeholder",
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
        sign_convention=POSITIVE_DISPATCH_MEANING,
        source="quickstart",
    ),
)

local_result = evaluate_demand_family(
    DemandFamilyEvaluationRequest(
        base_scenario_reference=base_scenario,
        weather_family=weather_family,
        demand_family=demand_family,
        cooling_service_configuration=CoolingServiceConfiguration(
            service_path="local-electric",
            local_electric_cooling=LocalElectricCoolingConfiguration(
                source_name="quickstart-local-cooling",
                electric_kw_per_rt=1.15,
                valid_for_feature_version="008-weather-demand-modeling",
            ),
            source="quickstart",
        ),
    )
)

district_result = evaluate_demand_family(
    DemandFamilyEvaluationRequest(
        base_scenario_reference=base_scenario,
        weather_family=weather_family,
        demand_family=demand_family,
        cooling_service_configuration=CoolingServiceConfiguration(
            service_path="district-cooling",
            district_cooling_tariff=DistrictCoolingTariff(
                currency="USD",
                rate_per_rt_hour=0.22,
                time_alignment="step-start",
                tariff_name="quickstart-district",
            ),
            source="quickstart",
        ),
    )
)

print(local_result.cooling_service_path, local_result.scenario_results[0].site_electric_load_kw)
print(district_result.cooling_service_path, district_result.scenario_results[0].district_cooling_settlement)
'
```

Expected result:

- the simulator root import exposes `evaluate_demand_family` and the demand-
  family request/result types without widening the import boundary
- local-electric cooling adds only the converted cooling electric load to site
  electric demand
- district-cooling service leaves site electric demand equal to non-thermal
  electric demand and settles served cooling separately in served `RT-hour`
  units
- replay from the same paired-family seed and scenario ordering remains exact

## Planned Default Validation Commands

Run the checks relevant to this feature after implementation:

```bash
uv run pytest tests/unit/demand tests/integration/demand tests/integration/simulator
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.demand; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/demand src/open_energy_lab/simulator tests/unit/demand tests/integration/demand tests/integration/simulator docs/migration
```

## Recorded Validation Outcome (2026-06-20)

The default offline validation subset was run on 2026-06-20 with these
results:

- `uv run pytest tests/unit/demand tests/integration/demand tests/integration/simulator`:
  passed (`91 passed`)
- `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py`:
  passed (`38 passed`)
- `uv run python -c "import open_energy_lab; import open_energy_lab.demand; import open_energy_lab.simulator"`:
  passed
- `rg "from legacy|import legacy" ...`:
  returned no matches for the demand, simulator, test, or migration paths in
  the default review subset

No optional live weather fetches, notebook execution, legacy runtime checks,
solver-backed checks, or GPU/SLURM validations were run as part of this
feature’s default review path. Those checks remain outside the committed
offline subset and should be documented separately if they are ever added.

If optional checks outside the default review path are ever added, document
them separately rather than widening the base environment requirements.
