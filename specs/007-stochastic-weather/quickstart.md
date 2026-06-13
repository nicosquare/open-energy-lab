# Quickstart: Stochastic Weather Generation And Simulator Integration

Use this quickstart to review the plan and guide later implementation. This
feature adds a reusable `open_energy_lab.weather` capability for geolocation
fetch, stochastic fitting, persisted artifacts, and offline sampling, then
integrates sampled weather into `open_energy_lab.simulator` without replacing
the current deterministic path.

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
sed -n '1,220p' src/open_energy_lab/simulator/_weather_schema.py
sed -n '1,220p' src/open_energy_lab/simulator/weather.py
sed -n '1,240p' src/open_energy_lab/simulator/pv.py
sed -n '360,560p' src/open_energy_lab/simulator/scenario.py
sed -n '1,220p' docs/migration/dependency-policy.md
sed -n '1,220p' docs/architecture/foundation.md
sed -n '1,260p' tests/fixtures/simulator/README.md
```

Confirm from these files that:

- the current simulator already owns deterministic weather-backed PV behavior
- the canonical first-release field set already exists in `_weather_schema.py`
- dependency isolation and fixture provenance rules are already documented
- the new feature must preserve simulator ownership of execution semantics

## Environment

The feature uses the same base environment as the current library:

```bash
conda activate open-energy-lab
uv sync --dev
```

The planned fit/fetch workflow may add isolated weather-specific dependencies
later, but default artifact-load and simulator validation should remain usable
in the base development environment.

## Expected Implementation Targets

After implementation, the main touched areas should be:

```text
src/open_energy_lab/weather/
src/open_energy_lab/simulator/
tests/unit/weather/
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

## Planned Stable And Experimental Surface

Stable first-release behavior:

- `open_energy_lab.weather` fit workflow
- canonical weather normalization
- versioned fitted-artifact persistence and loading
- offline fixed-timestep sampling from one family seed
- simulator scenario-family evaluation with grid-outage blackouts
- built-in min/mean/max/5th/50th/95th summaries for core simulator outputs

Experimental or deferred behavior:

- alternative model backends
- caller-configurable percentile sets
- raw-weather-variable family summaries
- artifact auto-migration
- blackout fitting or calibration from weather data

## Planned Public Entry Points

The exact exported names can still evolve during implementation, but the stable
weather package direction should look like:

```python
from open_energy_lab.weather import (
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)
```

Simulator-side integration is expected to remain distinct from the
deterministic path, for example:

```python
from open_energy_lab.simulator import BatteryLoadPVScenario
from open_energy_lab.simulator.stochastic_weather import evaluate_weather_family
```

## Dependency Boundary Notes

Planned dependency classification for implementation:

- core weather capability:
  - Python standard library
  - `numpy`
- isolated fit/fetch workflow dependencies:
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

## Expected Checks After Tasks Exist

```bash
uv run pytest tests/unit/weather tests/integration/weather tests/integration/simulator
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/weather src/open_energy_lab/simulator tests/unit/weather tests/integration/weather tests/integration/simulator
```

Focused validation commands should include:

```bash
uv run pytest tests/unit/weather/test_canonical_schema.py tests/unit/weather/test_artifact_schema.py tests/unit/weather/test_sampling.py
uv run pytest tests/integration/weather/test_fit_workflow.py tests/integration/weather/test_offline_sampling.py
uv run pytest tests/integration/simulator/test_stochastic_weather_family.py tests/integration/simulator/test_blackout_semantics.py
```

Routine local review should prefer recorded fixtures over live network fetches.

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

## Task Planning Reminder

When `/speckit-tasks` is generated, make sure it includes:

- tests first for canonical schema, artifacts, sampling, and simulator family
  integration
- deterministic and recorded fixtures with provenance notes
- explicit import-boundary and legacy-isolation checks
- simulator tests that preserve the deterministic weather path
- documentation tasks for dependency classification and migration notes
