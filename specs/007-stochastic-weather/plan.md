# Implementation Plan: Stochastic Weather Generation And Simulator Integration

**Branch**: `007-stochastic-weather` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/007-stochastic-weather/spec.md`

## Summary

Implement a new public weather capability under `src/open_energy_lab/weather`
that owns geolocation-driven TMY fetch, canonical weather normalization,
stochastic model fitting, persisted artifact loading, and offline weather
sampling. Integrate that capability with `open_energy_lab.simulator` through a
stochastic scenario-family surface that preserves the current deterministic
`BatteryLoadPVScenario` path, adds explicit caller-configured blackout
semantics, and returns both per-scenario traces and built-in family summaries
over documented core simulator outputs.

Legacy evidence remains selective and reference-only. TMY fetch and weather
preprocessing direction come from
`legacy/old_tpm/src_py/weather/fetch.py` and
`legacy/old_tpm/src_py/weather/pipeline.py`. Legacy stochastic modeling and
irradiance-event direction come from
`legacy/old_tpm/src_py/weather/models/gaussian.py`,
`legacy/old_tpm/src_py/weather/models/enhanced.py`, and
`legacy/old_tpm/src_py/weather/analysis/drops.py`. Existing simulator weather
and PV coupling evidence comes from
`legacy/old_tpm/src_py/simulator/common/weather.py` and
`legacy/old_tpm/src_py/simulator/common/pv.py`. The new feature preserves the
library-owned workflow direction while improving the model boundary with one
joint canonical schema, local-civil-time fitting semantics, versioned JSON
artifacts, offline sampling, and simulator-side outage semantics that are
explicitly distinct from weather attenuation.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`  
**Primary Dependencies**: Python standard library plus existing
`open_energy_lab.simulator` result types. The promoted weather fit/fetch
workflow also ships with `pvlib`, `pandas`, and `timezonefinder` in the base
project environment, but offline artifact loading and sampling must still not
require network access.  
**Storage/Data**: Markdown design artifacts, versioned JSON weather-model
artifacts, recorded fetch-normalization fixtures, and small committed JSON
fixtures under `tests/fixtures/weather` and `tests/fixtures/simulator`.  
**Testing**: `pytest` for `tests/unit/weather`, `tests/integration/weather`,
`tests/integration/simulator`, import-boundary checks, no-legacy-import
checks, deterministic fixture-schema validation, offline sampling validation,
and focused stochastic acceptance checks documented in this plan.  
**Target Platform**: Local CPU-only research workstation using the existing
conda plus uv environment. No GPU, SLURM, notebook, or service UI assumption.  
**Project Type**: Unified Python research library with stable public APIs under
`src/open_energy_lab`; legacy submodules remain reference inputs only.  
**Performance Goals**: Fit one location-specific artifact and sample local
scenario families in ordinary CPU review workflows without refetching or
refitting per scenario. The design should comfortably support tens to low
hundreds of sampled scenarios over horizons from 24 steps to roughly one week
at the artifact timestep, with no formal benchmark target required for this
planning phase.  
**Constraints**: Preserve the deterministic simulator weather path; keep
`import open_energy_lab` and `import open_energy_lab.simulator` import-light;
fail fast on unsupported artifact versions, missing canonical weather fields,
and timestep mismatches; fit and sample in location-local civil time while
materializing canonical `timestamp_utc`; keep blackout semantics separate from
weather fitting; avoid runtime `legacy/*` imports, notebooks, dashboards, W&B,
GPU/SLURM tooling, and broad scientific stacks in core import paths.  
**Scale/Scope**: Full canonical first-release weather schema of ten fields,
one fixed-timestep artifact per location, one stable offline sampling surface,
one stable simulator scenario-family integration surface, caller-configured
grid-only blackout disturbances, fixed 5th/50th/95th percentile summaries for
core simulator outputs only, and deterministic fixture coverage for schema,
loading, and simulator contracts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable code is planned under
  `src/open_energy_lab/weather` and `src/open_energy_lab/simulator`, with tests
  under `tests` and no new runtime code in `legacy/*`.
- **Legacy reference boundary**: All cited legacy files are evidence only and
  the plan does not require edits or runtime imports from legacy repositories.
- **Validation before migration**: The design is grounded in committed JSON
  fixtures, deterministic artifact schemas, offline sampling checks,
  import-boundary tests, and explicit stochastic acceptance criteria.
- **Dependency isolation**: Network-backed fetch tooling and TMY normalization
  dependencies remain isolated to the fit/fetch workflow; offline artifact
  loading and deterministic simulator imports remain service-free.
- **Reproducibility**: The spec already fixes family-seed behavior, local-civil
  time semantics, timestep locking, artifact version policy, blackout source,
  and numeric validation expectations.

**Post-design status**: PASS

- Design artifacts define a stable package split between
  `open_energy_lab.weather` and `open_energy_lab.simulator`, explicit artifact
  and sampling contracts, caller-configured blackout semantics, and a bounded
  summary surface over core simulator outputs only.
- Dependency classification keeps network-backed and heavier fit-time tooling
  outside ordinary base-library imports while preserving an offline sampling
  path.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/007-stochastic-weather/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── fitted-weather-artifact-contract.md
    ├── simulator-integration-contract.md
    ├── validation-contract.md
    ├── weather-sampling-contract.md
    └── weather-workflow-contract.md
```

### Current Reference Sources

```text
legacy/old_tpm/src_py/
├── weather/
│   ├── fetch.py
│   ├── pipeline.py
│   ├── analysis/drops.py
│   └── models/
│       ├── enhanced.py
│       └── gaussian.py
└── simulator/common/
    ├── pv.py
    └── weather.py

src/open_energy_lab/
├── simulator/
│   ├── __init__.py
│   ├── _weather_schema.py
│   ├── controller_runner.py
│   ├── pv.py
│   ├── scenario.py
│   └── weather.py
└── visualization/
    └── ...                    # current family-summary precedent is documentation only

tests/
├── fixtures/simulator/
├── integration/simulator/
└── unit/simulator/
```

### Target Library Structure

```text
src/
└── open_energy_lab/
    ├── __init__.py
    ├── simulator/
    │   ├── __init__.py
    │   ├── scenario.py
    │   ├── weather.py
    │   ├── pv.py
    │   └── stochastic_weather.py
    └── weather/
        ├── __init__.py
        ├── _canonical.py
        ├── tmy.py
        ├── fit.py
        ├── artifact.py
        ├── sampling.py
        └── events.py

tests/
├── unit/
│   ├── simulator/
│   └── weather/
├── integration/
│   ├── simulator/
│   └── weather/
├── parity/
└── fixtures/
    ├── simulator/
    └── weather/

docs/
└── migration/
    └── stochastic-weather.md
```

**Structure Decision**: Add a dedicated public `open_energy_lab.weather`
package rather than expanding `open_energy_lab.simulator.weather` into a mixed
fetch/fit/sampling module. The simulator remains the consumer of deterministic
or sampled weather inputs and the owner of execution semantics. New stochastic
family evaluation logic belongs in a focused simulator-side module such as
`stochastic_weather.py`, while canonical schema, fitting, artifact persistence,
and sampling belong in `open_energy_lab.weather`. The stable package root
remains `open_energy_lab`, and both the new weather package and the existing
simulator package should preserve lazy or narrow import behavior.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- where the stable public weather workflow should live and how it should stay
  separate from simulator execution ownership
- which fetch workflow and dependency classification should be adopted for
  TMY-based fitting
- how canonical weather variables and local-civil-time normalization should be
  represented
- which stochastic model structure best satisfies cross-variable and temporal
  requirements without preserving legacy factorization as the stable contract
- how multi-step cloud-event behavior should be modeled for irradiance fields
- what persisted artifact format, version policy, and timestep-lock behavior
  should be used
- how blackout disturbances remain separate from weather artifacts and how they
  surface in simulator results
- what stable scenario-family summaries the simulator must provide

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): canonical weather data, fitted artifact,
  cloud-event parameters, sampling request/result, blackout trace, and
  simulator family-result entities
- [contracts/weather-workflow-contract.md](./contracts/weather-workflow-contract.md):
  geolocation input, TMY fetch, canonical normalization, local-civil-time
  basis, and fail-fast rules
- [contracts/fitted-weather-artifact-contract.md](./contracts/fitted-weather-artifact-contract.md):
  artifact schema, versioning, timestep lock, provenance, and load behavior
- [contracts/weather-sampling-contract.md](./contracts/weather-sampling-contract.md):
  family-seed semantics, arbitrary-horizon sampling, cloud-event overlay, and
  returned sampled weather traces
- [contracts/simulator-integration-contract.md](./contracts/simulator-integration-contract.md):
  deterministic-path preservation, scenario-family evaluation, blackout
  semantics, and family summaries
- [contracts/validation-contract.md](./contracts/validation-contract.md):
  deterministic fixture shape, stochastic acceptance criteria, offline checks,
  and dependency-boundary evidence
- [quickstart.md](./quickstart.md): review, implementation, and validation
  commands for the feature

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate implementation tasks in this
order:

- add import-boundary and no-legacy-import tests for the new
  `open_energy_lab.weather` package and simulator stochastic integration entry
  points before public exports are introduced
- add deterministic fixture scaffolding and provenance notes for canonical
  weather normalization, invalid-source cases, invalid artifact-version cases,
  fixed-timestep artifact loading, and blackout scenario-family outputs
- add unit tests for canonical schema normalization, local-civil-time
  conversion, artifact schema validation, family-seed derivation, fixed
  percentile summaries, and fail-fast behavior for partial fetches or timestep
  mismatches
- add focused stochastic tests for joint weather sampling, multi-step
  irradiance cloud-event behavior, and physical-bounds enforcement
- implement `open_energy_lab.weather` fitting, artifact, and sampling modules
  with network-backed fetch isolated from offline artifact loading
- implement simulator-side stochastic scenario-family evaluation and
  caller-configured blackout semantics without breaking deterministic
  `BatteryLoadPVScenario`
- add integration tests for recorded fetch-to-artifact workflows, offline
  artifact sampling, family-result summaries, and blackout unmet-load behavior
- update migration notes, dependency classification docs, AGENTS context, and
  quickstart commands to reflect the shipped stable versus experimental
  surfaces

## Complexity Tracking

No constitution violations currently require justification.
