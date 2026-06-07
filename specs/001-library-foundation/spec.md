# Feature Specification: Unified Library Foundation

**Feature Branch**: `001-library-foundation`  
**Created**: 2026-05-10  
**Status**: Draft  
**Input**: User description: "Define the unified Open Energy Lab research library foundation. The project currently contains legacy/old_tpm and legacy/fed_trpo as reference-only submodules. Define the target Python library package namespace, source layout, test layout, public API boundaries, optional dependency policy, migration/validation strategy, and rules for notebooks, generated data, solver-backed optimization, W&B logging, GPU/SLURM workflows, and Rust reference code. The spec should not migrate algorithms yet; it should establish the architecture and governance needed for future migrations."

## Purpose *(mandatory)*

Establish the foundation for Open Energy Lab as a unified research library. The
feature defines the target library shape, migration rules, validation strategy,
and governance needed before any algorithms or workflows are migrated from
legacy references.

The outcome is a documented, reviewable foundation that lets future migration
features move selected behavior out of `legacy/old_tpm` and `legacy/fed_trpo`
without copying legacy structure or preserving known bad practices by default.

## Clarifications

### Session 2026-05-10

- Q: What public API maturity model should the foundation use? -> A: Stable public API plus experimental area: documented `open_energy_lab.*` imports are public; immature migrations start under `open_energy_lab.experimental` or private modules until promoted.
- Q: What core dependency baseline should the foundation set? -> A: Decide per migration; no core dependency baseline is fixed now, and each migration proposes and justifies what it needs.
- Q: What should the first migration priority be? -> A: Simulation module first; energy primitives are components of the simulator module.
- Q: What artifact policy should the foundation use? -> A: Fixtures allowed; small curated generated artifacts may live under `tests/fixtures` with provenance and regeneration notes, while notebooks remain examples or references.
- Q: What planning/control scope boundary should the foundation use? -> A: Interfaces only; define future planning/control concepts as interfaces or contracts, with implementations coming in later migrations.
- Q: How much of the long-term module roadmap should the foundation capture? -> A: Add roadmap modules: simulator first, then core methods, planning, control, and visualization as future module areas.
- Q: What simulator composition model should the foundation prefer? -> A: Component graph; simulator scenarios are composed from typed components and connections such as buildings, loads, storage, generators, markets, and networks.
- Q: What data source policy should the foundation use? -> A: Synthetic plus adapters; synthetic data is first-class, and real data comes through template-based ingestion plus optional source adapters such as ENTSO-E.
- Q: What TorchRL environment boundary should the foundation use? -> A: Optional adapter; simulator core stays independent, and TorchRL compatibility is provided through an optional wrapper or adapter.
- Q: What is the CityLearn roadmap stance? -> A: CityLearn remains reference-only evidence from `legacy/fed_trpo`; Open Energy Lab does not plan CityLearn integration and should build its own alternative surfaces instead.
- Q: What near-term use case should drive the first simulator validation target? -> A: Battery arbitrage; prioritize battery, price signal, and market arbitrage scenarios.
- Q: What environment and package-management policy should the foundation use? -> A: Conda defines the minimal base research environment with Python and uv; uv manages Python project dependencies, dev dependencies, editable installs, locking, and command execution.

## Scope Classification *(mandatory)*

- **Feature type**: Foundation
- **Target surface**: Public library API, source layout, test layout, dependency policy, migration governance, validation strategy, and research artifact handling
- **Environment strategy**: Minimal conda environment plus uv-managed Python project dependencies
- **Legacy reference paths**: `legacy/old_tpm`, `legacy/fed_trpo`
- **New-code location**: `src/open_energy_lab` for the unified library package, with tests under `tests`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose Library Shape (Priority: P1)

As the project maintainer, I need a single agreed target library shape so that
future work has one place for reusable code, tests, and public interfaces.

**Why this priority**: No migration can be judged cleanly until the project has
a target package namespace, source layout, test layout, and boundary between
public and internal interfaces.

**Independent Test**: A reviewer can inspect the foundation documents and
verify that new code has an unambiguous target package path, test path, public
API boundary, and legacy-reference boundary.

**Acceptance Scenarios**:

1. **Given** a future feature that adds reusable library behavior, **When** the maintainer checks the foundation, **Then** the feature has a defined package path under `src/open_energy_lab` and a matching test location under `tests`.
2. **Given** a future feature that cites legacy behavior, **When** the maintainer checks the foundation, **Then** the legacy path is treated as a reference source and not as the default destination for new code.

---

### User Story 2 - Govern Dependency Boundaries (Priority: P2)

As a library consumer, I need the core package to remain importable without
research-only tools, solver licenses, experiment tracking accounts, GPU
hardware, or cluster tooling.

**Why this priority**: The legacy projects include heavy and environment-bound
dependencies. If they become unconditional dependencies, the unified library
will be difficult to install, test, and use for basic workflows.

**Independent Test**: A reviewer can classify every dependency named in a
future migration as core, optional, external-service-backed, hardware-bound, or
legacy-only, and can verify that core imports do not require optional research
stacks.

**Acceptance Scenarios**:

1. **Given** a future feature using solver-backed optimization, **When** the dependency policy is applied, **Then** solver requirements are isolated from the core library and documented as optional or environment-specific.
2. **Given** a future feature using W&B, GPU, or SLURM workflows, **When** the dependency policy is applied, **Then** local library use remains possible without those services or hardware.

---

### User Story 3 - Validate Future Migrations (Priority: P3)

As a researcher, I need future migrations to preserve selected legacy behavior
only when there is reproducible evidence that the new library behaves
correctly, while still allowing the new simulator to adopt cleaner logic when
legacy structure is not worth preserving.

**Why this priority**: The legacy repositories contain valuable research work
but also notebooks, generated files, environment-specific scripts, and
inconsistent practices. Migrations need validation rules before code is moved.

**Independent Test**: A future migration spec can identify legacy source paths,
the behavior to preserve or reject, the validation evidence, reproducibility
inputs, and acceptable tolerances before implementation begins.

**Acceptance Scenarios**:

1. **Given** a future migration from `legacy/old_tpm`, **When** the migration is specified, **Then** it includes reference paths, input fixtures or configs, expected outputs or properties, and tolerances.
2. **Given** a future migration from `legacy/fed_trpo`, **When** long-running training behavior is involved, **Then** the migration defines focused smoke checks or selective reference-backed comparisons instead of relying only on full training runs.

---

### Edge Cases

- Legacy behavior depends on missing datasets, generated artifacts, notebooks, commercial solvers, W&B access, GPU hardware, or SLURM scheduling.
- A legacy workflow is useful but too coupled to scripts, notebooks, or environment variables to migrate directly.
- Two legacy modules solve related problems with incompatible names, units, assumptions, or data shapes.
- A future feature proposes adding an optional research stack as an unconditional core dependency.
- Rust reference behavior is valuable for parity, but the target foundation is a Python library and should not require Rust for ordinary imports.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The foundation MUST define `open_energy_lab` as the Python package namespace for the unified library.
- **FR-002**: The foundation MUST define `src/open_energy_lab` as the target source layout for new reusable library code.
- **FR-003**: The foundation MUST define `tests/unit`, `tests/integration`, `tests/parity`, and `tests/fixtures` as the target validation layout.
- **FR-004**: The foundation MUST define a public API maturity model where documented `open_energy_lab.*` imports are public, immature migrations start under `open_energy_lab.experimental` or private modules, and promotion to stable public API requires explicit review.
- **FR-005**: The foundation MUST state that `legacy/old_tpm` and `legacy/fed_trpo` are reference-only by default and are not default destinations for new product code.
- **FR-006**: The foundation MUST require every migration feature to cite exact legacy source paths and state which behavior is preserved, improved, or rejected.
- **FR-007**: The foundation MUST define a validation policy requiring each migration to name the behavior to preserve, improve, and reject, and to back the migrated behavior with tests, fixtures, deterministic configs, documented equations, snapshots, reproducible smoke checks, or other reviewable evidence before implementation; focused parity checks are optional and should be used only for explicitly preserved behavior.
- **FR-008**: The foundation MUST define a per-migration dependency policy: no core dependency baseline is fixed now, and each migration must propose and justify whether needed dependencies are core, optional, external-service-backed, hardware-bound, or legacy-only.
- **FR-009**: The foundation MUST define rules for notebooks: notebooks may be references, examples, or exploratory material, but reusable behavior must be migrated into library modules before it is treated as product code.
- **FR-010**: The foundation MUST define rules for generated data and model artifacts: small curated generated artifacts may live under `tests/fixtures` only when they include provenance and regeneration notes.
- **FR-011**: The foundation MUST define rules for solver-backed optimization, including how unavailable commercial solvers are handled in validation and documentation.
- **FR-012**: The foundation MUST define rules for W&B logging, GPU/SLURM workflows, and other environment-specific research workflows so they remain optional and documented.
- **FR-013**: The foundation MUST define how Rust reference code may be used for parity, performance comparison, or future bindings without making Rust mandatory for ordinary Python library imports.
- **FR-014**: The foundation MUST not migrate algorithms, training loops, optimization models, simulator internals, or notebooks as part of this feature.
- **FR-015**: The foundation MUST identify the simulator module as the first likely migration area, with energy primitives such as batteries, PV, load, tariffs, time grids, units, and scenarios treated as simulator components unless a future spec changes that boundary.
- **FR-016**: The foundation MUST define planning/control scope as interfaces or contracts only; concrete planners, controllers, RL agents, optimization models, and training loops must be introduced by later migration or capability specs.
- **FR-017**: The foundation MUST record a non-binding module roadmap with simulator first, followed by future core methods, planning, control, and visualization module areas; roadmap order may change through later specs.
- **FR-018**: The foundation MUST define the simulator composition direction as a component graph where scenarios are composed from typed components and connections, including buildings, loads, storage, generators, markets, and networks.
- **FR-019**: The foundation MUST define data sources as synthetic-first with adapters: synthetic data generation is first-class, and real data ingestion must use template specifications and optional source adapters such as ENTSO-E.
- **FR-020**: The foundation MUST define TorchRL compatibility as an optional simulator adapter or wrapper; simulator core imports must not require TorchRL.
- **FR-020a**: The foundation MUST treat CityLearn as reference-only legacy evidence and MUST NOT define CityLearn integration, compatibility, or adapter support as part of the product roadmap.
- **FR-021**: The foundation MUST identify battery arbitrage as the near-term use-case driver for the first simulator validation target, focusing on battery, price signal, and market arbitrage scenarios.
- **FR-022**: The foundation MUST define a minimal conda environment and uv-based Python package-management workflow where conda provides the interpreter/base environment and uv manages project dependencies, dev dependencies, locking, editable installation, and command execution.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**: `legacy/old_tpm`, `legacy/fed_trpo`
- **Behavior to preserve**: Only behavior named by future migration specs, backed by validation evidence, and judged suitable for the unified library.
- **Behavior to improve or drop**: Ad hoc import-path setup, notebook-only logic, generated-output coupling, unconditional heavyweight dependencies, full-training-only validation, and environment-specific assumptions that are not documented.
- **Validation evidence**: Future migrations must provide at least one of: fixture-based test, deterministic seed/config, documented equation, legacy command output, snapshot, focused smoke run, or explicit reason why an exact parity comparison is not the right standard or cannot be fully automated.

### Key Entities *(include if feature involves data or API design)*

- **Library Package**: The unified Python package namespace and source tree for reusable Open Energy Lab behavior.
- **Simulator Module**: The future library area responsible for simulation concepts and energy primitives, including batteries, PV, load, tariffs, time grids, units, and scenarios.
- **Component Graph**: A simulator scenario model composed from typed components and their connections, such as buildings, loads, storage, generators, markets, and networks.
- **Data Source Adapter**: An optional integration that converts external or real-world data into simulator-compatible templates. ENTSO-E is a future adapter example, not a core dependency.
- **TorchRL Adapter**: An optional wrapper that exposes simulator scenarios as TorchRL-compatible environments for control tasks without making TorchRL a simulator-core dependency.
- **Battery Arbitrage Case**: The near-term validation use case for the simulator roadmap, centered on battery operation against price signals and market arbitrage objectives.
- **Core Methods Module**: A future area for reusable task methods such as TPM, RL, MPC, optimization-based methods, and rule-based approaches. It is a roadmap area and does not imply a fixed dependency baseline.
- **Planning Module**: A future area for investment planning and capacity expansion experiments, including TPM-based planning and scenario-enumeration approaches.
- **Control Module**: A future area for energy management, demand response, battery arbitrage, frequency regulation, and individual or federated control tasks.
- **Planning/Control Interface**: A future contract for policies, controllers, planners, environments, or optimization entry points. The foundation may name these concepts, but implementations are out of scope.
- **Visualization Module**: A lower-priority future area for inspecting simulator and control-task behavior.
- **Public API Surface**: The documented `open_energy_lab.*` imports, functions, classes, commands, and schemas that users may rely on across migrations. Experimental or private modules are not stable until explicitly promoted.
- **Optional Capability**: A feature area that may require extra dependencies, external services, solver licenses, GPU hardware, SLURM, or experiment tracking.
- **Legacy Reference**: A source path under `legacy/old_tpm` or `legacy/fed_trpo` used as evidence for behavior, data shape, equations, commands, or experiment practice.
- **Parity Case**: A focused reproducible comparison used only for explicitly preserved behavior; it may compare the new library behavior to a legacy reference, documented equation, fixture, or expected invariant, but it does not force broad architectural or control-flow parity.
- **Research Artifact**: Notebook, generated dataset, model file, sweep config, run output, or plot used as input, fixture, example, cache, or output. Small curated artifacts used for validation may be fixtures when they include provenance and regeneration notes.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: No core dependency baseline is fixed by this foundation. Each migration must propose and justify any dependency it needs before that dependency is treated as core.
- **Optional dependencies**: Solver-backed optimization, SPN/MIO, RL training, W&B logging, notebooks, GPU workflows, and Rust parity tooling must be isolated as optional capabilities unless a future spec explicitly promotes one to core.
- **Legacy-only environment references**: CityLearn and similar legacy runtime surfaces may be cited as evidence, but they are not optional capabilities to be integrated into `open_energy_lab`.
- **External services**: W&B and any data APIs must be optional and documented with offline or disabled behavior where practical.
- **Hardware assumptions**: GPU and SLURM workflows must be treated as execution environments for selected research workflows, not requirements for using the core library.
- **Environment tooling**: The foundation uses conda for the minimal base research environment and uv for Python project dependency management. Heavy optional stacks must not be added to the base environment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can determine the target package namespace, source layout, and test layout for future library work in under 5 minutes.
- **SC-002**: A future migration spec can be checked against documented required fields for legacy source paths, preserved/improved/rejected behavior, validation evidence, tolerances, target API maturity, and API-promotion status.
- **SC-003**: Core library import expectations are documented so that optional solver, training, logging, notebook, GPU, and cluster workflows can be identified before they become mandatory dependencies.
- **SC-004**: At least 90% of future migration tasks can cite a target library path and a validation path without adding code to `legacy/*`.
- **SC-005**: The foundation explicitly identifies that no algorithms are migrated by this feature, preventing scope creep into simulator, SPN, optimization, or RL implementation work.

## Assumptions

- Primary users are researchers and maintainers who need a clean Python library for energy-system simulation, optimization, learning, and analysis workflows.
- `legacy/old_tpm` and `legacy/fed_trpo` remain reference-only unless a future migration or maintenance spec explicitly says otherwise.
- `open_energy_lab` is the default package namespace because it matches the repository name in conventional Python form.
- `src/open_energy_lab` and `tests` are acceptable target paths for a Python library foundation.
- The first migration is expected to define a simulator module, with energy primitives housed inside that module rather than as independent top-level package areas.
- Simulator scenarios are expected to be represented as component graphs rather than hard-coded single-case structures.
- Synthetic data generation is first-class; real data is incorporated through documented templates and optional adapters rather than direct dependency on a specific external data source.
- TorchRL compatibility should be provided through an optional adapter so simulator core remains usable without TorchRL installed.
- CityLearn is reference-only input from `legacy/fed_trpo`, not a target integration or compatibility surface for the unified library.
- Battery arbitrage is the first intended simulator validation use case; cooling demand response, frequency regulation, federated microgrid control, and investment planning remain future roadmap use cases.
- The long-term roadmap includes simulator, core methods, planning, control, and visualization modules, but this foundation does not require implementing them all immediately.
- Planning/control concepts should be defined as future-facing interfaces or contracts before concrete planners, controllers, RL agents, or optimization models are migrated.
- Small curated generated artifacts may be committed as test fixtures when they are needed for validation and include provenance plus regeneration notes.
- Some legacy validation may not run in every local environment because of solver licenses, GPU/SLURM requirements, W&B access, or missing generated datasets.
- Rust code in `legacy/old_tpm` is useful reference material, but the initial unified library foundation is Python-first.
- The base development environment should stay minimal: Python, uv, and only foundation development dependencies such as pytest.
