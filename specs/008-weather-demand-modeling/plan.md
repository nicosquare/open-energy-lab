# Implementation Plan: Weather-Conditioned Demand Modeling And Simulator Integration

**Branch**: `008-weather-demand-modeling` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/008-weather-demand-modeling/spec.md`

## Summary

Implement a new public demand capability under `src/open_energy_lab/demand`
that owns aligned historical demand-plus-weather fitting, persisted artifact
loading, and offline sampling of weather-conditioned demand traces. Integrate
that capability with `open_energy_lab.simulator` through a paired
weather-and-demand scenario-family surface that preserves the current
deterministic `BatteryLoadPVScenario` path, adds explicit cooling-service
accounting, and compares local electric cooling against district cooling
without double counting.

Legacy evidence remains selective and reference-only. Deterministic tariff and
step-aligned settlement direction come from
`legacy/old_tpm/src_py/simulator/common/pricing.py`. Conceptual demand and
cooling separation direction comes from
`legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`,
`legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`,
`legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb`, and
`legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`.
Existing canonical weather artifacts and stochastic weather-family direction
come from the already-promoted `src/open_energy_lab/weather` package and
`src/open_energy_lab/simulator/stochastic_weather.py`. The new feature keeps
weather and demand as separate producer-side artifacts, requires explicit
historical non-thermal electric and cooling-demand series for fitting, uses
one shared paired-family seed, and leaves blackout semantics entirely
simulator-side.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`  
**Primary Dependencies**: Python standard library plus existing
`open_energy_lab.weather` and `open_energy_lab.simulator` types. The current
base environment already ships `pandas`, `pvlib`, and `timezonefinder`, but
the demand feature must keep routine artifact loading, offline sampling, and
simulator imports clear of live-service assumptions and heavy building or RL
stacks.  
**Storage/Data**: Markdown planning artifacts, versioned JSON demand-model
artifacts, aligned demand-plus-weather training fixtures, and committed JSON
or CSV fixtures under `tests/fixtures/demand` and `tests/fixtures/simulator`.  
**Testing**: `pytest` for `tests/unit/demand`, `tests/integration/demand`,
paired simulator integration tests, import-boundary checks, no-legacy-import
checks, deterministic fixture-schema validation, and paired reproducibility
checks.  
**Target Platform**: Local CPU-only research workstation using the existing
conda plus uv environment. No GPU, SLURM, notebook, or service UI assumption.  
**Project Type**: Unified Python research library with stable public APIs
under `src/open_energy_lab`; legacy submodules remain reference inputs only.  
**Performance Goals**: Fit one location- and timestep-specific demand artifact
from aligned historical fixtures, then sample and evaluate tens to low
hundreds of paired weather-and-demand scenarios over horizons from 24 steps to
roughly one week at the artifact timestep without refitting or live data
access in the ordinary review path.  
**Constraints**: Preserve the deterministic simulator path; keep
`import open_energy_lab`, `import open_energy_lab.demand`, and
`import open_energy_lab.simulator` import-light; keep non-thermal electric
demand and cooling demand explicitly separate through fit, artifact, sampling,
and simulator integration; require explicit historical cooling-demand series in
`RT` and explicit historical non-thermal electric demand for fitting; keep
weather and demand artifacts separate; derive local electric cooling from one
documented `kW`-per-`RT` conversion factor; treat district cooling settlement
as a deterministic simulator-side tariff; keep blackout semantics separate
from weather and demand fitting; avoid runtime `legacy/*` imports, CityLearn,
building simulators, solver stacks, notebooks, W&B, and GPU or SLURM tooling
in core import paths.  
**Scale/Scope**: First-release dual-output demand artifact, one fixed-timestep
artifact per training dataset, one stable offline demand-family sampling
surface conditioned on sampled weather traces, one stable paired simulator
integration surface, exactly one configured cooling service path per scenario,
explicit cooling-service-balance outputs, deterministic fixture coverage for
artifact, sampling, and simulator contracts, and heating excluded as a future
extension point.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable code is planned under
  `src/open_energy_lab/demand` and `src/open_energy_lab/simulator`, with tests
  under `tests` and no new runtime code in `legacy/*`.
- **Legacy reference boundary**: All cited legacy files remain evidence only.
  The plan does not require edits to legacy repositories or runtime imports
  from them.
- **Validation before migration**: The design is grounded in committed
  aligned-history fixtures, demand-artifact schema fixtures, paired
  weather-and-demand sampling fixtures, simulator accounting invariants, and
  import-boundary tests.
- **Dependency isolation**: Demand fitting can reuse existing base-environment
  weather tooling and lightweight data processing, but offline artifact
  loading, package imports, and simulator evaluation remain service-free and
  isolated from CityLearn, building-simulation, solver, and RL stacks.
- **Reproducibility**: The spec already fixes paired-family seed semantics,
  timestep locking, separate electric and thermal outputs, deterministic local
  electric cooling conversion, district-cooling tariff ownership, and the
  offline review path.

**Post-design status**: PASS

- Design artifacts define a stable split between producer-side
  `open_energy_lab.demand` workflows and simulator-side execution semantics,
  with demand traces conditioned on explicit weather references rather than a
  merged artifact.
- The design keeps double-counting prevention contractual by requiring
  explicit non-thermal electric and cooling training data and by maintaining
  separate sampled outputs through simulator accounting.
- The simulator design preserves deterministic `BatteryLoadPVScenario`
  workflows while adding a new cooling-aware surface and stable paired-family
  summaries only for documented comparison outputs.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/008-weather-demand-modeling/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── demand-workflow-contract.md
    ├── fitted-demand-artifact-contract.md
    ├── demand-sampling-contract.md
    ├── simulator-integration-contract.md
    └── validation-contract.md
```

### Current Reference Sources

```text
legacy/
├── old_tpm/
│   └── src_py/simulator/common/
│       └── pricing.py
└── fed_trpo/
    └── src/notebooks/
        ├── ML_817_topic_I_lab_1.ipynb
        ├── ML_817_topic_I_lab_2.ipynb
        ├── citylearn_ccai_tutorial.ipynb
        └── data_generation/naive_data_generation.ipynb

src/open_energy_lab/
├── weather/
│   ├── __init__.py
│   ├── artifact.py
│   ├── fit.py
│   └── sampling.py
└── simulator/
    ├── __init__.py
    ├── load.py
    ├── objective.py
    ├── pricing.py
    ├── scenario.py
    └── stochastic_weather.py
```

### Target Library Structure

```text
src/
└── open_energy_lab/
    ├── __init__.py
    ├── demand/
    │   ├── __init__.py
    │   ├── fit.py
    │   ├── artifact.py
    │   ├── sampling.py
    │   ├── _aligned_history.py
    │   └── _weather_response.py
    ├── simulator/
    │   ├── __init__.py
    │   ├── demand.py
    │   ├── pricing.py
    │   ├── scenario.py
    │   ├── objective.py
    │   └── stochastic_demand.py
    └── weather/
        └── ...                  # existing canonical weather producer surface

tests/
├── unit/
│   ├── demand/
│   └── simulator/
├── integration/
│   ├── demand/
│   └── simulator/
├── parity/
└── fixtures/
    ├── demand/
    └── simulator/

docs/
└── migration/
    └── weather-demand-modeling.md
```

**Structure Decision**: Add a dedicated public `open_energy_lab.demand`
package rather than widening `open_energy_lab.weather` or overloading the
existing simulator `load` module with producer-side artifact concerns. The
weather package remains the owner of canonical weather traces and weather
artifacts. The new demand package owns aligned-history fitting, persisted
artifacts, and offline demand-family sampling conditioned on weather traces.
The simulator remains the consumer of deterministic or sampled exogenous
inputs and gains a focused cooling-aware family-evaluation surface under a new
module such as `stochastic_demand.py`. Existing deterministic
`LoadComponent` and `BatteryLoadPVScenario` remain supported and unchanged as
the regression surface.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- where the stable public demand workflow should live and how it should stay
  separate from simulator execution ownership
- which historical inputs are mandatory for first-release fitting and how the
  design prevents electric and thermal double counting by contract
- which first-release conditional demand model structure best balances
  reproducibility, explicit weather conditioning, and lightweight validation
- how paired weather-and-demand family seeds and scenario ordering should be
  coordinated while preserving separate artifacts
- how local electric cooling conversion and district-cooling settlement remain
  simulator-side accounting concerns
- which outputs and validation evidence the paired simulator family surface
  must expose for credible cooling-path comparison

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): aligned training data, fitted artifact,
  conditional model parameters, sampled demand traces, cooling-service
  configuration, and paired simulator-family result entities
- [contracts/demand-workflow-contract.md](./contracts/demand-workflow-contract.md):
  aligned historical inputs, fit workflow, double-counting prevention, and
  fail-fast rules
- [contracts/fitted-demand-artifact-contract.md](./contracts/fitted-demand-artifact-contract.md):
  artifact schema, versioning, timestep lock, provenance, and separate output
  guarantees
- [contracts/demand-sampling-contract.md](./contracts/demand-sampling-contract.md):
  shared paired-family seed semantics, weather-conditioned sampling,
  arbitrary-horizon support, and returned sampled demand traces
- [contracts/simulator-integration-contract.md](./contracts/simulator-integration-contract.md):
  deterministic-path preservation, cooling service-path validation,
  local-electric versus district-cooling accounting, and paired family
  summaries
- [contracts/validation-contract.md](./contracts/validation-contract.md):
  deterministic fixture shape, paired reproducibility checks, accounting
  invariants, offline validation, and import-boundary evidence
- [quickstart.md](./quickstart.md): review, implementation, and validation
  commands for the feature

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate implementation tasks in this
order:

- add import-boundary, package-surface, and no-legacy-import tests for the new
  `open_energy_lab.demand` package and its simulator integration entry points
  before public exports are introduced
- add deterministic fixture scaffolding and provenance notes for aligned
  demand-plus-weather history, fitted demand artifacts, sampled demand
  families, paired weather-and-demand families, and cooling-path settlement
  cases
- add unit tests for artifact schema validation, mandatory aligned historical
  inputs, explicit double-counting rejection, paired seed derivation,
  arbitrary-horizon sampling, and fail-fast timestep or ordering mismatches
- implement producer-side demand fitting, artifact loading, and weather-aware
  demand sampling with separate non-thermal electric and cooling outputs
- implement simulator-side cooling service configuration, district tariff
  accounting, explicit unserved cooling reporting, and paired family
  evaluation without breaking deterministic `BatteryLoadPVScenario`
- add integration tests for offline artifact fit and reload, paired
  weather-and-demand sampling replay, local electric versus district-cooling
  comparisons, and accounting invariants that prevent double counting
- update migration notes, repository guidance, AGENTS context, and quickstart
  commands to reflect the new stable package location and experimental concrete
  types

## Complexity Tracking

No constitution violations currently require justification.
