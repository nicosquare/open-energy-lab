# Implementation Plan: TPM-Backed Planning And Simulator Dataset Export

**Branch**: `009-tpm-planning` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/009-tpm-planning/spec.md`

## Summary

Promote a first reusable TPM-backed planning slice into the unified library by
adding a simulator-owned planning-dataset export workflow, migrating the
validated typed-feature and SPN-training/query surfaces from
`legacy/old_tpm/src_py/tpm`, and defining an optional planning surface under
`open_energy_lab.planning` that assembles a piecewise MILP for direct battery
and solar design decisions. The feature keeps default review offline and
fixture-backed, treats heavy solver and SPFlow dependencies as optional, and
uses explicit versioned dataset and TPM artifact contracts instead of
notebook-only or pickle-only workflows.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`  
**Primary Dependencies**: Python standard library plus existing
`open_energy_lab.simulator`, `open_energy_lab.weather`, and
`open_energy_lab.demand` surfaces; `pandas` already ships in the base
environment; SPFlow, Pyomo, and MILP solver backends remain optional and must
stay outside ordinary imports.  
**Storage/Data**: Markdown planning artifacts, versioned JSON planning-dataset
artifacts, versioned TPM artifacts with JSON metadata plus a documented SPN
payload representation or payload locator defined by the artifact schema,
committed fixture datasets under `tests/fixtures/planning` or
`tests/fixtures/tpm`, and optional solver-assembly fixtures.  
**Testing**: `pytest` for new `tests/unit/tpm`, `tests/unit/planning`,
`tests/integration/planning`, import-boundary checks, no-legacy-import
checks, deterministic dataset-export fixtures, query fixtures, and offline
model-assembly checks; optional legacy-parity or solver-backed checks remain
documented but non-routine.  
**Target Platform**: Local CPU-only research workstation using the existing
uv-managed environment; no GPU, SLURM, notebook runtime, or external service
assumptions.  
**Project Type**: Unified Python research library with stable public APIs
under `src/open_energy_lab`; legacy repositories remain reference material
only.  
**Performance Goals**: Export tens to low hundreds of scenario rows from one
simulator family deterministically, fit and reload one TPM artifact from a
fixture-backed planning dataset offline, and assemble a first-release
piecewise planning model for battery and solar decisions without requiring a
solver in the routine review path.  
**Constraints**: Preserve import-light package roots; avoid runtime imports
from `legacy/*`; keep SPFlow, Pyomo, and solver dependencies optional; define
`shortfall` canonically as horizon-level unmet electric energy ratio; bound
first-release planning to battery and solar decisions; document solver
reproducibility assumptions and tolerances; keep routine validation offline
and fixture-backed.  
**Scale/Scope**: One horizon-flattened planning dataset contract per artifact,
one explicit planning target (`shortfall`), typed feature support for
continuous/binary/categorical/mixed features where validated by migrated
legacy behavior, one optional piecewise MILP path, and no inverter or broader
equipment decisions in the first release.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable code is planned under
  `src/open_energy_lab/tpm`, `src/open_energy_lab/planning`, and
  `src/open_energy_lab/simulator`, with tests under `tests`.
- **Legacy reference boundary**: Exact legacy TPM source paths are cited in the
  spec, and the plan keeps them as migration evidence only. No runtime
  `legacy/*` imports are required.
- **Validation before migration**: The plan defines fixture-backed validation
  for dataset export, feature typing, TPM artifact reload, conditional query
  behavior, piecewise approximation assembly, and import boundaries before
  broad migration claims.
- **Dependency isolation**: SPFlow, Pyomo, and solver backends stay optional
  and outside `open_energy_lab`, `open_energy_lab.tpm`, and
  `open_energy_lab.planning` root imports.
- **Reproducibility**: Dataset provenance, seeds, solver configuration notes,
  shortfall derivation, artifact schema versions, and approximation tolerances
  are all part of the planned contracts.

**Post-design status**: PASS

- The design artifacts keep simulator export, TPM training/query, and planning
  assembly as distinct public contracts with explicit artifact boundaries.
- Heavy dependencies are isolated behind optional modules and documented
  follow-up checks rather than becoming base-environment requirements.
- The planning target and chance-constraint semantics are explicit and library
  owned, not inherited from notebook conventions.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/009-tpm-planning/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── simulator-export-contract.md
    ├── planning-dataset-contract.md
    ├── tpm-artifact-contract.md
    ├── planning-solve-contract.md
    └── validation-contract.md
```

### Current Reference Sources

```text
legacy/old_tpm/
├── src_py/tpm/data/
│   ├── datahandler.py
│   ├── encoding.py
│   ├── features/
│   │   ├── feature.py
│   │   ├── binary.py
│   │   ├── categorical.py
│   │   ├── contiguous.py
│   │   └── mixed.py
│   └── types.py
├── src_py/tpm/spn/
│   ├── main.py
│   ├── encoding.py
│   ├── utils_tangent.py
│   └── test_tangent_lower_bound.py
├── src_py/utils/densities.py
└── src_py/simulator/
    ├── data_generation.py
    └── feature_engineering.py

src/open_energy_lab/
├── demand/
│   ├── artifact.py
│   ├── fit.py
│   └── sampling.py
├── planning/
│   └── __init__.py
└── simulator/
    ├── __init__.py
    ├── scenario.py
    ├── stochastic_demand.py
    └── stochastic_weather.py
```

### Target Library Structure

```text
src/
└── open_energy_lab/
    ├── __init__.py
    ├── planning/
    │   ├── __init__.py
    │   ├── dataset.py
    │   ├── problem.py
    │   ├── piecewise.py
    │   └── optional_solver.py
    ├── simulator/
    │   ├── __init__.py
    │   ├── planning_export.py
    │   ├── scenario.py
    │   ├── stochastic_demand.py
    │   └── stochastic_weather.py
    └── tpm/
        ├── __init__.py
        ├── artifact.py
        ├── data.py
        ├── features.py
        ├── fit.py
        ├── query.py
        ├── piecewise.py
        └── optional_spflow.py

tests/
├── unit/
│   ├── planning/
│   └── tpm/
├── integration/
│   └── planning/
└── fixtures/
    ├── planning/
    └── tpm/
```

**Structure Decision**: Put the simulator-to-dataset export entry point in
`open_energy_lab.simulator` because it derives directly from simulator family
results, create a dedicated `open_energy_lab.tpm` package for migrated typed
feature and SPN artifact/query behavior, and expand `open_energy_lab.planning`
from scaffold to a stable planning-assembly surface. This preserves the
existing producer/consumer boundaries already used by the weather and demand
features while avoiding notebook-owned glue code.

## Phase 0: Research

Research outcomes are captured in [research.md](./research.md). They resolve:

- where simulator export should live and how it should map current
  `DemandFamilyEvaluationResult` and `WeatherFamilyEvaluationResult` data into
  a stable planning dataset
- which legacy TPM behaviors are preserved closely versus replaced with new
  artifact contracts
- how optional SPFlow and Pyomo integrations remain isolated from ordinary
  imports and routine review
- what the canonical first-release piecewise solver-facing path is and how its
  validation should be bounded
- how first-release planning should consume a fitted TPM artifact while keeping
  battery and solar design variables direct and typed

## Phase 1: Design

Design artifacts are captured in [data-model.md](./data-model.md),
[quickstart.md](./quickstart.md), and the files under
[contracts/](./contracts/). They define:

- the simulator export request/result contract, flattened dataset schema, and
  shortfall derivation rule
- the versioned planning dataset and TPM artifact contracts, including
  provenance and reproducibility fields
- the planning problem definition, direct chance-constraint contract, and
  optional solver boundary
- fixture provenance and the exact review commands for offline validation

## Phase 2: Implementation Strategy

1. Add simulator export primitives that accept evaluated family results,
   validate horizon and scenario alignment, flatten configured series fields,
   derive `shortfall`, and persist versioned planning datasets.
2. Migrate the typed-feature metadata, normalization, and encoding surface from
   legacy TPM sources into a native `open_energy_lab.tpm` package with JSON
   artifact contracts and no runtime legacy imports.
3. Add optional SPFlow-backed fit and query adapters that produce deterministic
   metadata artifacts, support marginalization of non-decision variables, and
   preserve fixture-backed conditional-query behavior.
4. Expand `open_energy_lab.planning` with a stable problem-definition and
   model-assembly surface that consumes TPM artifacts, encodes battery and
   solar decisions directly, and uses the canonical piecewise approximation
   path for the first release.
5. Add unit, integration, import-boundary, and optional-dependency tests plus
   committed planning and TPM fixtures before claiming fixture-backed
   migration validation.

## Complexity Tracking

No constitution exceptions are required for this plan.
