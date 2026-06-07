# Implementation Plan: Unified Library Foundation

**Branch**: `001-library-foundation` | **Date**: 2026-05-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-library-foundation/spec.md`

**Note**: This plan covers the unified library foundation only. It does not
migrate simulator, TPM, RL, optimization, weather, control, notebook, or Rust
algorithm behavior.

## Summary

Establish Open Energy Lab as a Python-first research library with a target
package namespace of `open_energy_lab`, reusable code under `src/open_energy_lab`,
tests under `tests`, and documented governance for public APIs, optional
dependencies, fixtures, provenance, and future brownfield migrations.

Legacy projects under `legacy/old_tpm` and `legacy/fed_trpo` remain
reference-only inputs. This plan defines how future migration specs should
select behavior from those references, validate it with reproducible
reference-backed evidence, and keep heavyweight research workflows isolated
from core imports without forcing broad simulator-level legacy parity.

## Technical Context

**Language/Version**: Python 3.11+ for the target library scaffold. Rust in
`legacy/old_tpm` remains reference material for parity/performance comparison
and possible future bindings, but Rust is not required for ordinary Python
imports.

**Primary Dependencies**: The foundation should keep the import scaffold
runtime-light. Conda defines the minimal base research environment with Python,
uv, and bootstrapping tools only. uv manages Python project dependencies,
editable installs, locking, and command execution. No scientific, solver, RL,
logging, GPU, SLURM, notebook, or Rust dependency becomes core in this feature.
Future migrations must classify each dependency as core, optional,
external-service-backed, hardware-bound, or legacy-only before adding it.

**Storage/Data**: Markdown governance artifacts, Python packaging metadata,
test fixtures, and fixture provenance notes. Future data ingestion uses
template-based specifications and optional adapters; small curated generated
artifacts may live only under `tests/fixtures` with provenance and regeneration
instructions.

**Testing**: `pytest` is the target test runner for the unified Python library.
The target layout is `tests/unit`, `tests/integration`, `tests/parity`, and
`tests/fixtures`. Legacy checks such as `cargo test` and old TPM validation
scripts may be cited by future migration specs when their prerequisites exist.

**Target Platform**: Local research workstation by default, using a minimal
conda environment and uv-managed Python project. GPU, SLURM, commercial solver,
W&B, ENTSO-E/API-backed data access, and notebook execution are optional
environments for specific future capabilities, not foundation requirements.

**Project Type**: Python research library with optional adapters, examples, and
research workflow entry points. Legacy submodules are reference inputs rather
than target architecture.

**Performance Goals**: No algorithm throughput, solve-time, or training-runtime
goal is set in this foundation feature. The import-time goal is that importing
`open_energy_lab` must not require heavyweight optional stacks or external
services.

**Constraints**: Do not add new reusable code to `legacy/*` by default. Do not
migrate algorithms in this feature. Keep public API promotion explicit. Require
future migrations to cite legacy paths, validation evidence, dependency class,
fixture provenance, environment assumptions, and acceptable tolerances.

**Scale/Scope**: Foundation scaffold and governance only. Future simulator
migration preparation should cover battery arbitrage as the first validation
target and should describe the component-graph direction, but implementation is
deferred to a later simulator spec.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: Target new reusable code path is
  `src/open_energy_lab`, with tests under `tests`.
- **Legacy reference boundary**: `legacy/old_tpm` and `legacy/fed_trpo` are
  reference-only unless a later migration spec explicitly authorizes changes.
- **Validation before migration**: This plan defines fixtures, deterministic
  configs, documented equations, snapshots, smoke checks, and optional focused
  parity cases as migration prerequisites.
- **Dependency isolation**: Heavy dependencies are classified per migration and
  isolated behind optional capabilities, adapters, extras, or workflow entry
  points.
- **Reproducibility**: Future specs must document seeds, configs, datasets,
  solver assumptions, hardware assumptions, metrics, provenance, and tolerances.

**Post-design status**: PASS

- Design artifacts define API maturity, dependency classification, migration
  validation contracts, fixture provenance, and simulator preparation without
  introducing algorithm migration or heavyweight core dependencies.
- No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-library-foundation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dependency-classification.md
│   ├── fixture-provenance.md
│   ├── migration-spec.md
│   ├── public-api.md
│   └── simulator-preparation.md
└── checklists/
    └── requirements.md
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
environment.yml
pyproject.toml
uv.lock                    # generated by uv once dependencies are resolved
src/
└── open_energy_lab/
    ├── __init__.py           # stable public package boundary
    ├── py.typed              # typing marker once typed code exists
    ├── experimental/         # immature migrations and incubating APIs
    ├── simulator/            # first planned migration area; no implementation now
    ├── core/                 # future TPM, RL, MPC, optimization, rule-based methods
    ├── planning/             # future planning interfaces/contracts only
    ├── control/              # future control interfaces/contracts only
    └── visualization/        # lower-priority future inspection tools

tests/
├── unit/
├── integration/
├── parity/
└── fixtures/
    └── README.md             # provenance and regeneration conventions

docs/
├── architecture/
│   ├── README.md
│   └── foundation.md
└── migration/
    ├── README.md
    ├── api-maturity.md
    ├── dependency-policy.md
    ├── environment-assumptions.md
    ├── fixture-provenance.md
    ├── migration-spec-template.md
    ├── parity-validation.md
    └── simulator-preparation.md
```

**Structure Decision**: Use a `src` layout with `src/open_energy_lab` as the
only target package namespace for reusable library code. Create empty or
documentation-only module scaffolds only when useful for import and governance
checks. Do not migrate algorithm internals in this feature. Keep future
simulation energy primitives inside `open_energy_lab.simulator` unless a later
spec changes that boundary.

## Phase 0: Research

Research decisions are captured in [research.md](./research.md). They resolve:

- Python package namespace and source/test layout.
- Public API maturity rules.
- Optional dependency classification and import-boundary policy.
- Migration validation evidence requirements, including when focused parity
  checks are appropriate.
- Fixture and provenance policy.
- Notebook, generated artifact, W&B, GPU/SLURM, solver, and Rust reference
  handling.
- Simulator migration preparation, including component graph direction,
  synthetic-first data, optional TorchRL adapter, and battery arbitrage as the
  first validation target.

## Phase 1: Design

Design artifacts are captured in:

- [data-model.md](./data-model.md): conceptual entities and validation rules for
  the foundation.
- [contracts/public-api.md](./contracts/public-api.md): public, experimental,
  and private API boundaries.
- [contracts/dependency-classification.md](./contracts/dependency-classification.md):
  required dependency review record for future migrations.
- [contracts/migration-spec.md](./contracts/migration-spec.md): minimum content
  for future brownfield migration specs.
- [contracts/fixture-provenance.md](./contracts/fixture-provenance.md): fixture,
  generated artifact, and provenance rules.
- [contracts/simulator-preparation.md](./contracts/simulator-preparation.md):
  preparation contract for the next simulator migration spec.
- [quickstart.md](./quickstart.md): how maintainers should review and apply the
  foundation before implementation and future migrations.

## Phase 2: Task Planning Guidance

The later `/speckit-tasks` step should generate tasks for foundation scaffold
and documentation only:

- Add packaging metadata and the `src/open_energy_lab` scaffold without
  algorithm implementations.
- Add a minimal `environment.yml` for conda plus uv and keep heavy research
  dependencies out of the base environment.
- Add `tests/unit`, `tests/integration`, `tests/parity`, and `tests/fixtures`
  directories with provenance guidance.
- Add documentation for API maturity, dependency classification, validation
  and selective-preservation policy, fixture provenance, and future simulator
  migration preparation.
- Add minimal import/scaffold tests that verify the package imports without
  optional research dependencies.
- Avoid tasks that migrate simulator, weather, TPM, RL, optimization, planning,
  control, notebook, W&B, GPU/SLURM, or Rust behavior.

## Quality Gates

Before this plan is considered complete:

- No unresolved clarification markers remain in the plan or design artifacts.
- The target package path, test layout, public API boundary, dependency
  policy, validation/selective-preservation policy, and fixture policy are
  documented.
- Contracts do not require algorithm migration.
- `AGENTS.md` points to this plan as the active Spec Kit context.

Expected implementation-stage checks after scaffold tasks exist:

```bash
conda env create -f environment.yml
conda activate open-energy-lab
uv sync --dev
uv run pytest tests/unit
uv run python -c "import open_energy_lab"
```

Legacy parity checks are not required for this foundation feature because no
legacy behavior is migrated.

## Complexity Tracking

No constitution violations are introduced by this plan.
