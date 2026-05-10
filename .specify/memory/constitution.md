# Open Energy Lab Constitution

## Project Identity

Open Energy Lab is a research software unification project. Its purpose is to
turn prior energy-systems research code into a coherent library with stable
interfaces, reproducible workflows, and migration checks against selected
legacy behavior.

Detected reference code currently lives in git submodules under `legacy/`:

- `legacy/old_tpm`: Rust/Python energy storage simulation, SPN/MIO, weather,
  and experiment code.
- `legacy/fed_trpo`: Python federated RL, PPO/TRPO, CityLearn customization,
  experiment configuration, and SLURM/W&B sweep scripts.

The target library package, package namespace, dependency manager, and public
API are intentionally not fixed by this constitution. They must be defined by
the first foundation feature spec.

## Core Principles

### I. Unified Library First

New product code must move the project toward a single library instead of
expanding the legacy projects. Until the foundation spec defines the package
layout, new implementation work should be limited to specs, tests,
documentation, or explicitly scoped scaffolding. After the foundation spec,
new reusable code belongs in the target library package, not in `legacy/*`.

### II. Legacy Is Reference Material

`legacy/*` is reference-only by default. A feature may copy or adapt legacy
behavior only when the spec names the source paths, explains the behavior to
preserve, and defines what will be improved. Whole-file migration without
analysis is not acceptable. Legacy conventions are evidence, not law.

### III. Reproducible Research Contracts

Simulation, optimization, weather generation, SPN, RL, and experiment features
must specify the inputs needed to reproduce results: config files, datasets,
random seeds, solver assumptions, hardware assumptions when relevant, metrics,
and acceptable tolerances. Generated artifacts must have documented provenance
and should not be treated as source unless the spec explicitly says so.

### IV. Dependency Boundaries

The future core library must not require heavyweight research dependencies at
import time unless the foundation spec explicitly chooses that tradeoff. Heavy
or environment-sensitive dependencies detected in legacy code include TorchRL,
PyTorch, CityLearn, Pyomo, Gurobi, CPLEX/docplex, SPFlow, W&B, Jupyter, and
GPU/SLURM tooling. Features that need them must isolate them behind optional
modules, extras, adapters, or command entry points as defined by the spec.

### V. Migration Requires Validation

Migrated behavior must be protected by tests or reproducible validation cases.
Validation may compare against legacy outputs, documented equations, known
fixtures, deterministic seeds, or published experiment configurations. If a
check cannot be run locally because of commercial solvers, GPU requirements,
networked services, or unavailable data, the limitation must be documented in
the plan and quickstart.

## Code Boundaries

- `.specify/` contains Spec Kit workflow files, templates, scripts, and memory.
- `.agents/` contains local agent skills and command implementations.
- `legacy/old_tpm` and `legacy/fed_trpo` are imported reference repositories.
- New target-library code location is not yet defined. The foundation feature
  must choose the package path, test path, dependency manager, and public API
  conventions before substantial library implementation begins.
- Changes inside `legacy/*` require an explicit migration, reference-fix, or
  submodule-maintenance reason in the relevant spec or task.

## Naming and Style

Detected naming in legacy Python and Rust is mostly `snake_case` for files and
functions, with `PascalCase` for Python classes and Rust structs/enums. Future
library code should keep these conventional language norms unless the
foundation spec establishes a different documented standard.

No consistent project-wide commit style was detected. Conventional Commits are
not required by this constitution unless a later governance update adopts them.

## Testing and Quality Gates

Every feature plan must list the checks that apply to the files it changes.
Detected checks include:

- `cd legacy/old_tpm && cargo test` for Rust simulation/storage changes.
- `cd legacy/old_tpm && python scripts/test_battery_consistency.py` for legacy
  battery behavior checks when the legacy Python import path is available.
- `cd legacy/old_tpm && pytest src_py/tpm/spn/test_tangent_lower_bound.py` for
  SPN/Pyomo tangent behavior when solver dependencies are available.
- `cd legacy/old_tpm && ./scripts/test_data_validation.sh --test-type <type>`
  for legacy cross-language validation when its prerequisites are available.

Fed TRPO has no dedicated test suite detected. Features migrating PPO/TRPO,
CityLearn, or sweep behavior must first define focused validation fixtures or
smoke tests rather than relying only on long-running training jobs.

No CI, linter, formatter, or coverage standard was detected. Specs may add
these, but must not claim they already exist.

## Governance

This constitution governs Spec Kit planning and migration decisions. It
supersedes legacy repository habits when creating the new unified library.
Amendments must explain why the rule changed, what existing specs or templates
are affected, and how migration work should adapt.

The first feature should define the unified research library foundation:
package namespace, public API boundaries, dependency policy, test layout,
migration/parity strategy, and initial quality gates.

**Version**: 0.1.0 | **Ratified**: 2026-05-10 | **Last Amended**: 2026-05-10
