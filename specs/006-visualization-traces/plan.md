# Implementation Plan: Visualization And Trace Inspection MVP

**Branch**: `006-visualization-traces` | **Date**: 2026-06-09 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/006-visualization-traces/spec.md`

## Summary

Implement the first reusable inspection and visualization library surface under
`src/open_energy_lab/visualization` on top of the existing deterministic
simulator outputs in `open_energy_lab.simulator` and controller-driven results
from `open_energy_lab.core` plus `open_energy_lab.simulator`. The feature will
ship one stable inspection and reporting surface, same-scenario comparison
support, and one experimental optional plotting layer for basic static
single-run plots, while preserving simulator ownership of execution semantics
and keeping plotting decoupled from re-simulation.

This feature uses current library surfaces rather than legacy migration
evidence. The relevant input shapes come from
`src/open_energy_lab/simulator/scenario.py`,
`src/open_energy_lab/simulator/controller_runner.py`,
`src/open_energy_lab/simulator/weather.py`, and
`src/open_energy_lab/simulator/pv.py`. Existing migration notes under
`docs/migration` remain the documentation baseline for API maturity,
dependency policy, and fixture provenance.

## Technical Context

**Language/Version**: Python 3.11+ in `src/open_energy_lab`  
**Primary Dependencies**: Python standard library plus existing `open_energy_lab.simulator` and `open_energy_lab.core` result types; `pytest` for validation. No new required runtime dependencies for the stable inspection/reporting surface. Any static plotting backend must remain optional and isolated from base visualization imports.  
**Storage/Data**: Markdown design artifacts plus small committed JSON fixtures under `tests/fixtures/simulator` or `tests/fixtures/visualization`; migration notes under `docs/migration`; supported persisted run outputs must be loadable without rerunning simulation.  
**Testing**: `pytest` for `tests/unit/visualization`, `tests/integration/visualization`, relevant import-boundary scans, no-legacy-import checks, and deterministic simulator/controller regression tests proving visualization consumes existing results correctly.  
**Target Platform**: Local CPU-only research workstation using the repository's uv-managed Python environment  
**Project Type**: Unified research library with stable public APIs under `src/open_energy_lab`; legacy submodules remain reference inputs only  
**Performance Goals**: Inspection, comparison, and basic static plotting for short deterministic runs such as 3-24 timesteps should remain lightweight enough for ordinary unit and integration test workflows on CPU. No formal benchmark target is required for this MVP.  
**Constraints**: No new code in `legacy/*`; no runtime `legacy/*` imports; no dashboards, notebook-first workflows, W&B integrations, external API clients, GPU/SLURM helpers, or mandatory plotting dependencies for ordinary `open_energy_lab.visualization` imports; comparison is same-scenario-family only; weather reporting is limited to simulator-exposed weather variables.  
**Scale/Scope**: Two supported scenario families, one stable inspection/reporting surface, one experimental optional plotting layer, same-family comparison only, supported persisted-output loading for later inspection/plotting, and one migration note describing preserve/improve/defer outcomes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: New reusable code is planned under
  `src/open_energy_lab/visualization` with matching tests and migration docs
  in the unified library structure.
- **Legacy reference boundary**: No legacy behavior is being migrated at
  runtime. Current simulator and controller outputs are the only required
  upstream inputs.
- **Validation before migration**: The plan requires deterministic inspection,
  comparison, persisted-output, and plotting validation before the new surface
  is trusted.
- **Dependency isolation**: Stable inspection/reporting remains import-light,
  and any plotting backend must be optional.
- **Reproducibility**: The spec fixes deterministic result consumption,
  same-family comparison scope, persisted-output reuse, CPU-only defaults, and
  numeric tolerance expectations.

**Post-design status**: PASS

- Design artifacts define stable inspection/reporting boundaries, an explicit
  API-maturity split between stable reporting and experimental plotting,
  deterministic same-family comparison rules, and persisted-output handling
  without expanding simulator execution ownership.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/006-visualization-traces/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── comparison-contract.md
│   ├── inspection-view-contract.md
│   ├── plotting-contract.md
│   ├── validation-case.md
│   └── visualization-package-contract.md
└── tasks.md
```

### Current Reference Sources

```text
src/open_energy_lab/
├── core/
│   └── controller.py
├── simulator/
│   ├── controller_runner.py
│   ├── pv.py
│   ├── scenario.py
│   └── weather.py
└── visualization/
    └── __init__.py

docs/migration/
├── api-maturity.md
├── dependency-policy.md
├── fixture-provenance.md
└── README.md
```

### Target Library Structure

```text
src/
└── open_energy_lab/
    ├── __init__.py
    ├── core/
    ├── simulator/
    └── visualization/
        ├── __init__.py
        ├── inspection.py
        ├── comparison.py
        ├── plotting.py
        └── _persistence.py

tests/
├── unit/
│   └── visualization/
├── integration/
│   └── visualization/
├── parity/
└── fixtures/
    ├── simulator/
    └── visualization/

docs/
└── migration/
    ├── api-maturity.md
    └── visualization-traces.md
```

**Structure Decision**: Keep `open_energy_lab.simulator` and
`open_energy_lab.core` as the sole owners of execution and controller result
generation, then add `open_energy_lab.visualization` as a consumer-facing
inspection layer on top of those outputs. The package root should expose only
the stable inspection/reporting surface, while comparison helpers and the
optional plotting layer remain reviewable in focused modules and never trigger
simulation by themselves.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- why `open_energy_lab.visualization` should adapt existing deterministic
  result objects instead of widening simulator ownership
- how stable inspection/reporting and experimental plotting should split at
  the package boundary
- how plotting and inspection should consume in-memory and persisted outputs
  without rerunning simulation
- how same-family comparison stays deterministic and bounded in the MVP
- how weather reporting remains limited to simulator-exposed fields
- how validation should rely on deterministic fixtures, import-boundary checks,
  and focused integration tests rather than notebooks or dashboards

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): inspection, comparison, plotting, and
  persisted-output entities plus their validation rules
- [contracts/visualization-package-contract.md](./contracts/visualization-package-contract.md):
  required public package surface, maturity split, and import-boundary rules
- [contracts/inspection-view-contract.md](./contracts/inspection-view-contract.md):
  canonical single-run inspection behavior for supported scenario families
- [contracts/comparison-contract.md](./contracts/comparison-contract.md):
  same-scenario comparison rules and unsupported-case behavior
- [contracts/plotting-contract.md](./contracts/plotting-contract.md):
  optional plotting-layer expectations, no-resimulation rule, and persisted-output support
- [contracts/validation-case.md](./contracts/validation-case.md):
  deterministic evidence, fixture provenance, and import-boundary requirements
- [quickstart.md](./quickstart.md): review, implementation, and validation
  commands for the feature

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate implementation tasks in this
order:

- add import-boundary and no-legacy-import tests for
  `open_energy_lab.visualization` before introducing public exports
- add unit tests for stable inspection views over arbitrage and
  battery-load-PV results
- add focused tests proving simulator-exposed weather variables appear only for
  supported weather-backed runs
- add persisted-output loading tests for supported stored run outputs
- add same-family comparison tests and explicit unsupported cross-family
  comparison tests
- add optional plotting-layer tests for supported single-run static plots and
  no-resimulation behavior
- add committed visualization fixtures only where existing simulator fixtures
  are insufficient for deterministic inspection or plotting validation
- implement visualization inspection, comparison, plotting, and persistence
  modules plus package-root exports
- update migration notes, API maturity documentation, and quickstart commands
  to reflect the shipped inspection surface and experimental plotting layer

## Complexity Tracking

No constitution violations currently require justification.
