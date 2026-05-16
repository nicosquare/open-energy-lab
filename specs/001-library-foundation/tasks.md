# Tasks: Unified Library Foundation

**Input**: Design documents from `/specs/001-library-foundation/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks are included because the feature requires minimal import/scaffold checks and validation gates. These tests verify package shape, dependency isolation, environment setup, and policy documentation only.

**Organization**: Tasks are grouped by user story so each story can be implemented and reviewed independently. No task migrates simulator, TPM, RL, optimization, weather, planning, control, notebook, W&B, GPU/SLURM, Rust binding, or legacy algorithm behavior.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Establish conda/uv environment, packaging, source, test, and documentation locations for the foundation scaffold.

- [X] T001 Create `environment.yml` with conda environment name `open-energy-lab`, Python `3.11`, uv, pip, conda-forge channel, and no heavy research dependencies
- [X] T002 Create `pyproject.toml` with uv-compatible project metadata, project name, Python `>=3.11`, `src` package discovery, pytest dev dependency group, pytest settings, and no runtime dependencies
- [X] T003 [P] Create package typing marker `src/open_energy_lab/py.typed`
- [X] T004 [P] Create test layout marker READMEs in `tests/unit/README.md`, `tests/integration/README.md`, and `tests/parity/README.md`
- [X] T005 [P] Create documentation layout marker READMEs in `docs/architecture/README.md` and `docs/migration/README.md`

---

## Phase 2: Foundational

**Purpose**: Add shared guardrails used by all user stories before package behavior is added.

**Critical**: These tasks must complete before user-story implementation because they define repository-wide artifact and generated-output boundaries.

- [X] T006 Create fixture provenance template and allowed/disallowed artifact rules in `tests/fixtures/README.md`
- [X] T007 [P] Update `.gitignore` to exclude local research outputs such as W&B runs, checkpoints, solver caches, notebook checkpoints, generated data dumps, and local conda/uv environment directories

**Checkpoint**: Repository has the target directories and artifact guardrails needed by all stories.

---

## Phase 3: User Story 1 - Choose Library Shape (Priority: P1)

**Goal**: Create the Python package scaffold, public API boundary, target layout documentation, and tests that make the agreed library shape inspectable.

**Independent Test**: `uv run pytest tests/unit/test_import_contract.py tests/unit/test_module_scaffold.py tests/unit/test_no_legacy_imports.py` verifies that the package imports, roadmap modules exist as scaffold only, and target library code does not import from `legacy/*`.

### Tests for User Story 1

- [X] T008 [P] [US1] Add root import contract test in `tests/unit/test_import_contract.py` verifying `import open_energy_lab` works through `uv run` and does not import optional research stacks
- [X] T009 [P] [US1] Add module scaffold test in `tests/unit/test_module_scaffold.py` verifying `src/open_energy_lab/experimental`, `src/open_energy_lab/simulator`, `src/open_energy_lab/core`, `src/open_energy_lab/planning`, `src/open_energy_lab/control`, and `src/open_energy_lab/visualization` are importable scaffold packages
- [ ] T010 [P] [US1] Add legacy isolation test in `tests/unit/test_no_legacy_imports.py` verifying `src/open_energy_lab` contains no imports from `legacy/*`

### Implementation for User Story 1

- [X] T011 [US1] Implement stable package metadata and public boundary docstring in `src/open_energy_lab/__init__.py`
- [X] T012 [P] [US1] Implement experimental API boundary docstring in `src/open_energy_lab/experimental/__init__.py`
- [X] T013 [P] [US1] Create docstring-only roadmap module scaffolds in `src/open_energy_lab/simulator/__init__.py`, `src/open_energy_lab/core/__init__.py`, `src/open_energy_lab/planning/__init__.py`, `src/open_energy_lab/control/__init__.py`, and `src/open_energy_lab/visualization/__init__.py`
- [X] T014 [US1] Create foundation architecture documentation in `docs/architecture/foundation.md` covering `src/open_energy_lab`, `tests`, conda/uv environment strategy, roadmap modules, planning/control as future interface-only areas, and `legacy/*` reference boundaries
- [X] T015 [US1] Create public API maturity documentation in `docs/migration/api-maturity.md` covering stable, experimental, private, promotion, and deprecation rules
- [X] T016 [US1] Update `README.md` with the target layout, conda/uv setup commands, foundation documentation links, legacy-reference boundary, and local scaffold validation commands

**Checkpoint**: User Story 1 is complete when the package scaffold imports without optional dependencies and reviewers can locate target source/test paths in documentation.

---

## Phase 4: User Story 2 - Govern Dependency Boundaries (Priority: P2)

**Goal**: Document and test dependency classification so the core package remains importable without solvers, experiment tracking, GPU/SLURM tooling, notebooks, Rust tooling, or RL stacks.

**Independent Test**: `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_dependency_policy_docs.py tests/unit/test_environment_policy_docs.py` verifies root imports avoid heavy optional stacks and dependency/environment policy docs contain the required classifications.

### Tests for User Story 2

- [X] T017 [P] [US2] Add optional dependency boundary test in `tests/unit/test_optional_dependency_boundaries.py` checking that `import open_energy_lab` does not load known heavy optional Python modules such as `torch`, `torchrl`, `citylearn`, `pyomo`, `gurobipy`, `docplex`, `spflow`, `wandb`, or `jupyter`
- [X] T018 [P] [US2] Add dependency policy documentation test in `tests/unit/test_dependency_policy_docs.py` checking `docs/migration/dependency-policy.md` contains `core`, `optional`, `external-service-backed`, `hardware-bound`, and `legacy-only`
- [X] T019 [P] [US2] Add environment policy documentation test in `tests/unit/test_environment_policy_docs.py` checking `environment.yml`, `pyproject.toml`, and `docs/migration/environment-assumptions.md` document conda as the base environment and uv as the Python package manager

### Implementation for User Story 2

- [X] T020 [US2] Create dependency classification documentation in `docs/migration/dependency-policy.md` from `specs/001-library-foundation/contracts/dependency-classification.md`
- [X] T021 [US2] Update `pyproject.toml` to keep runtime dependencies empty or minimal, define pytest as a dev dependency, and defer optional extras until a future implemented capability spec requires them
- [X] T022 [P] [US2] Create environment assumptions documentation in `docs/migration/environment-assumptions.md` for conda/uv usage, solver-backed optimization, W&B logging, GPU/SLURM workflows, external data APIs, notebooks, and Rust reference tooling
- [X] T023 [US2] Update `README.md` to state that foundation imports do not require optional research dependencies or external services

**Checkpoint**: User Story 2 is complete when dependency and environment policy documentation exists and import tests prove the core scaffold does not load optional stacks.

---

## Phase 5: User Story 3 - Validate Future Migrations (Priority: P3)

**Goal**: Provide migration, parity, fixture, and simulator-preparation documentation so later specs can migrate selected legacy behavior only with reproducible evidence.

**Independent Test**: `uv run pytest tests/unit/test_migration_policy_docs.py tests/unit/test_fixture_provenance_docs.py` verifies future migration and fixture policies include legacy references, evidence types, provenance fields, tolerances, and environment limitations.

### Tests for User Story 3

- [X] T024 [P] [US3] Add migration policy documentation test in `tests/unit/test_migration_policy_docs.py` checking `docs/migration/parity-validation.md`, `docs/migration/migration-spec-template.md`, and `docs/migration/simulator-preparation.md` cover target module path, validation/test path, legacy paths, behavior to preserve/improve/reject, validation evidence, tolerances, and out-of-scope algorithm migration
- [X] T025 [P] [US3] Add fixture provenance documentation test in `tests/unit/test_fixture_provenance_docs.py` checking `docs/migration/fixture-provenance.md` and `tests/fixtures/README.md` include origin, generation command, seed, input data, expected output or invariant, tolerance, license/access notes, and refresh policy

### Implementation for User Story 3

- [X] T026 [US3] Create parity validation documentation in `docs/migration/parity-validation.md` from `specs/001-library-foundation/contracts/migration-spec.md`
- [X] T027 [US3] Create fixture provenance documentation in `docs/migration/fixture-provenance.md` from `specs/001-library-foundation/contracts/fixture-provenance.md` and align it with `tests/fixtures/README.md`
- [ ] T028 [P] [US3] Create reusable migration spec template in `docs/migration/migration-spec-template.md` with required sections from `specs/001-library-foundation/contracts/migration-spec.md`, including target module path and validation/test path
- [ ] T029 [P] [US3] Create next simulator migration preparation documentation in `docs/migration/simulator-preparation.md` from `specs/001-library-foundation/contracts/simulator-preparation.md` without adding simulator implementation
- [X] T028 [P] [US3] Create reusable migration spec template in `docs/migration/migration-spec-template.md` with required sections from `specs/001-library-foundation/contracts/migration-spec.md`, including target module path and validation/test path
- [X] T029 [P] [US3] Create next simulator migration preparation documentation in `docs/migration/simulator-preparation.md` from `specs/001-library-foundation/contracts/simulator-preparation.md` without adding simulator implementation
- [ ] T030 [US3] Update `tests/parity/README.md` with the future parity strategy, legacy-reference policy, and statement that no migrated parity cases exist in this foundation feature

**Checkpoint**: User Story 3 is complete when future migrations have documented templates and validation policies but no legacy algorithm behavior has been migrated.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Validate the complete foundation scaffold and align the Spec Kit quickstart with implemented commands.

- [ ] T031 Run `conda env create -f environment.yml` only if the `open-energy-lab` environment does not already exist, then run `conda activate open-energy-lab`
- [ ] T032 Run `uv sync --dev` to resolve the foundation dev environment and create or update `uv.lock`
- [ ] T033 Run `uv run pytest tests/unit` to validate all foundation unit tests under `tests/unit`
- [ ] T034 Run `uv run python -c "import open_energy_lab"` from the repository root to verify `src/open_energy_lab` imports without optional dependencies
- [ ] T035 Run `rg "from legacy|import legacy" src/open_energy_lab tests/unit` and confirm no target package or unit test imports from `legacy/*`
- [ ] T036 Review `docs/architecture/foundation.md` and `docs/migration/simulator-preparation.md` to confirm planning/control remain interface-only and no simulator, TPM, RL, optimization, weather, notebook, W&B, GPU/SLURM, Rust binding, or legacy algorithm implementation scope is introduced
- [ ] T037 Update `specs/001-library-foundation/quickstart.md` with final conda/uv scaffold verification commands and any checks intentionally not run

---

## Dependencies

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story.
- User Story 1 is the MVP and should complete before User Stories 2 and 3 because it creates the importable package scaffold.
- User Story 2 can proceed after User Story 1 package files exist and `pyproject.toml` plus `environment.yml` exist.
- User Story 3 can proceed after Phase 2 and may run in parallel with User Story 2 once documentation directories exist.
- Phase 6 runs after all selected user stories are complete.

### User Story Dependencies

- **US1**: Depends on Phase 1 and Phase 2 only.
- **US2**: Depends on US1 import scaffold, `pyproject.toml`, and `environment.yml`.
- **US3**: Depends on Phase 2 and documentation directories; does not depend on US2 implementation.

---

## Parallel Execution Examples

### User Story 1

After Phase 2, these can run together:

```text
T008 test import contract in tests/unit/test_import_contract.py
T009 test module scaffold in tests/unit/test_module_scaffold.py
T010 test legacy isolation in tests/unit/test_no_legacy_imports.py
T012 create experimental scaffold in src/open_energy_lab/experimental/__init__.py
T013 create roadmap scaffolds under src/open_energy_lab/
```

### User Story 2

After US1 creates the importable package, these can run together:

```text
T017 test optional dependency boundaries in tests/unit/test_optional_dependency_boundaries.py
T018 test dependency policy documentation in tests/unit/test_dependency_policy_docs.py
T019 test environment policy documentation in tests/unit/test_environment_policy_docs.py
T022 document environment assumptions in docs/migration/environment-assumptions.md
```

### User Story 3

After Phase 2, these can run together:

```text
T024 test migration policy docs in tests/unit/test_migration_policy_docs.py
T025 test fixture provenance docs in tests/unit/test_fixture_provenance_docs.py
T028 create migration spec template in docs/migration/migration-spec-template.md
T029 create simulator preparation docs in docs/migration/simulator-preparation.md
```

---

## Implementation Strategy

### MVP First

Complete Phases 1 and 2, then deliver User Story 1. This establishes the conda/uv foundation workflow, importable `open_energy_lab` scaffold, package/test layout, public API maturity docs, and legacy-reference boundary.

### Incremental Delivery

1. Deliver US1 and verify package shape with `uv run pytest tests/unit/test_import_contract.py tests/unit/test_module_scaffold.py tests/unit/test_no_legacy_imports.py`.
2. Deliver US2 and verify dependency isolation with `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_dependency_policy_docs.py tests/unit/test_environment_policy_docs.py`.
3. Deliver US3 and verify future migration governance with `uv run pytest tests/unit/test_migration_policy_docs.py tests/unit/test_fixture_provenance_docs.py`.
4. Run Phase 6 checks for the complete foundation.

### Scope Guard

If any task appears to require copying legacy simulator, weather, TPM, RL, optimization, control, notebook, W&B, GPU/SLURM, Rust, or training behavior into `src/open_energy_lab`, stop and create a later migration spec instead.
