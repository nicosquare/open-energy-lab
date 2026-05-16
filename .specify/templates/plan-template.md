# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See
`.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary library/research requirement, legacy
reference sources if any, and the technical approach.]

## Technical Context

**Language/Version**: [Python target version TBD by foundation spec; Rust 2024 detected in `legacy/old_tpm`; NEEDS CLARIFICATION if adding target code]  
**Primary Dependencies**: [Core library deps plus optional research deps; distinguish required vs optional]  
**Storage/Data**: [CSV, parquet, JSON, YAML, pickle/model artifacts, generated experiment outputs, or N/A]  
**Testing**: [pytest or chosen test runner for target library; `cargo test` for legacy Rust parity; specific validation scripts if used]  
**Target Platform**: [Local research workstation, CPU/GPU, SLURM/HPC, or NEEDS CLARIFICATION]  
**Project Type**: Unified research library with optional CLIs/scripts; legacy submodules are reference inputs  
**Performance Goals**: [Simulation throughput, training runtime, optimization solve time, memory, or NEEDS CLARIFICATION]  
**Constraints**: [Reproducibility, deterministic seeds, solver licenses, GPU availability, optional deps, no new code in `legacy/*` by default]  
**Scale/Scope**: [Datasets, number of buildings, simulation horizon, experiment count, feature set]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Unified library first**: Does the plan place new reusable code in the target library, or explicitly justify why the target path is not ready?
- **Legacy reference boundary**: Are all `legacy/*` source paths used only as references unless the spec explicitly allows migration edits?
- **Validation before migration**: Are tests, parity fixtures, deterministic configs, or reproducible validation cases defined before migrating behavior?
- **Dependency isolation**: Are heavy dependencies optional or isolated from core import paths unless explicitly justified?
- **Reproducibility**: Are seeds, configs, datasets, solver assumptions, and tolerances documented?

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Current Reference Sources

```text
legacy/
├── old_tpm/
│   ├── src/                  # Rust simulation/storage/optimizer reference
│   ├── src_py/               # Python simulator, SPN/MIO, weather, experiments
│   ├── data/                 # Legacy fixtures and generated/reference data
│   └── scripts/              # Legacy validation and benchmark scripts
└── fed_trpo/
    ├── src/algos/            # PPO/TRPO training references
    ├── src/custom/           # CityLearn customizations
    ├── src/utils/            # Rewards, logging, TorchRL helpers, trust-region code
    ├── config/               # W&B sweep YAML configs
    └── scripts/              # SLURM sweep launchers
```

### Target Library Structure

```text
# Foundation feature must replace this with real paths.
[target-package]/
├── [public-api-modules]/
├── [optional-adapters]/
└── [internal-modules]/

tests/
├── unit/
├── integration/
├── parity/
└── fixtures/
```

**Structure Decision**: [Document the selected target paths. If this feature is
the foundation feature, this is a required decision. If not, reference the
foundation feature decision.]

## Phase 0: Research

- Identify legacy source files and configs that define the desired behavior.
- Decide what behavior is preserved, improved, or intentionally dropped.
- Identify required vs optional dependencies.
- Define validation/parity strategy and expected tolerances.
- Record unresolved package/API decisions as NEEDS CLARIFICATION.

## Phase 1: Design

- Define public API contracts, data models, config schemas, or command
  interfaces affected by this feature.
- Define fixtures and validation data provenance.
- Define dependency boundaries and optional extras/adapters.
- Update quickstart with exact commands, environment assumptions, and checks.

## Complexity Tracking

> Fill only if Constitution Check has violations that must be justified.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., edit in legacy/*] | [specific migration need] | [why reference-only is insufficient] |
| [e.g., heavy core dependency] | [specific API need] | [why optional adapter is insufficient] |
