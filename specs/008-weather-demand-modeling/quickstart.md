# Quickstart: Weather-Conditioned Demand Modeling And Simulator Integration

Use this quickstart to review the planned demand feature and to prepare the
implementation and validation workflow. The feature adds a reusable
`open_energy_lab.demand` capability for aligned-history fitting, persisted
artifacts, and offline weather-conditioned demand sampling, then integrates
those sampled demand families into `open_energy_lab.simulator` without
replacing the current deterministic path.

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

## After Implementation: Exercise The Planned US2 Offline Sampling Workflow

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

## After Implementation: Exercise The Planned US3 Simulator Workflow

Run the planned local-electric and district-cooling comparison workflow from
committed paired family fixtures:

```bash
uv run pytest tests/integration/simulator -k "demand or cooling"
```

Expected result:

- local electric cooling adds derived `kW` to site electric load
- district cooling serves thermal demand directly in `RT`
- served district cooling does not appear in site electric load
- settlement reflects both electric and district-cooling accounting paths

## Planned Default Validation Commands

Run the checks relevant to this feature after implementation:

```bash
uv run pytest tests/unit/demand tests/integration/demand tests/integration/simulator
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.demand; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/demand src/open_energy_lab/simulator tests/unit/demand tests/integration/demand tests/integration/simulator docs/migration
```

If optional checks outside the default review path are ever added, document
them separately rather than widening the base environment requirements.
