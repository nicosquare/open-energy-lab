# Tasks: TPM-Backed Planning And Simulator Dataset Export

**Input**: Design documents from `/specs/009-tpm-planning/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The feature requires focused unit, integration, fixture-validation,
import-boundary, no-legacy-import, and deterministic assembly checks because
it promotes a stable simulator export workflow, a new `open_energy_lab.tpm`
package, and a planning surface with explicit artifact contracts, canonical
SPFlow and Pyomo workflow backends, and lazy dependency boundaries.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Path Conventions

- **Spec Kit**: `.specify/`, `.agents/`
- **Legacy references**: `legacy/old_tpm/`, `legacy/fed_trpo/`
- **Target library**: `src/open_energy_lab/simulator`, `src/open_energy_lab/tpm`, `src/open_energy_lab/planning`
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/fixtures/`

## Phase 1: Setup

**Purpose**: Establish TPM, planning, fixture, and migration-note scaffolding
without introducing runtime legacy dependencies.

- [X] T001 Create TPM and planning package scaffolds in `src/open_energy_lab/tpm/__init__.py`, `tests/unit/tpm/__init__.py`, `tests/unit/planning/__init__.py`, and `tests/integration/planning/__init__.py`
- [X] T002 [P] Create planning and TPM fixture scaffolds in `tests/fixtures/planning/planning_dataset_export_case.json`, `tests/fixtures/planning/planning_problem_case.json`, `tests/fixtures/tpm/planning_dataset_v1.json`, `tests/fixtures/tpm/tpm_artifact_v1.json`, `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`, and `tests/fixtures/tpm/tpm_query_case.json`
- [X] T003 [P] Add fixture provenance placeholders in `tests/fixtures/planning/README.md` and `tests/fixtures/tpm/README.md`
- [X] T004 [P] Create the TPM-planning migration note scaffold in `docs/migration/tpm-planning.md`

---

## Phase 2: Foundational

**Purpose**: Add shared validation infrastructure, package boundaries, and
module scaffolding that block all user-story work.

- [X] T005 [P] Add import-boundary coverage for `open_energy_lab.tpm` and `open_energy_lab.planning` in `tests/unit/tpm/test_import_boundary.py` and `tests/unit/planning/test_import_boundary.py`
- [X] T006 [P] Add no-legacy-import coverage for TPM and planning modules in `tests/unit/tpm/test_no_legacy_imports.py` and `tests/unit/planning/test_no_legacy_imports.py`
- [X] T007 [P] Extend root dependency-boundary coverage so `open_energy_lab.tpm`, `open_energy_lab.planning`, and `open_energy_lab.simulator.planning_export` remain import-safe until SPFlow-backed or Pyomo-backed workflows are invoked in `tests/unit/test_optional_dependency_boundaries.py`
- [X] T008 [P] Extend stable package-surface and import-contract coverage for new TPM and planning exports in `tests/unit/tpm/test_package_surface.py`, `tests/unit/planning/test_package_surface.py`, and `tests/unit/test_import_contract.py`
- [X] T009 [P] Add shared fixture loading helpers for planning datasets, TPM artifacts, and planning problems in `tests/integration/planning/fixture_utils.py`
- [X] T010 [P] Add fixture-schema and provenance validation for planning and TPM artifacts in `tests/integration/planning/test_fixture_schema.py` and `tests/integration/planning/test_tpm_fixture_schema.py`
- [X] T010a [P] Add end-to-end reproducibility contract validation for export, TPM query, and planning assembly or solve behavior in `tests/integration/planning/test_reproducibility_contract.py`
- [X] T011 Create foundational module scaffolds and lazy export placeholders in `src/open_energy_lab/simulator/planning_export.py`, `src/open_energy_lab/tpm/artifact.py`, `src/open_energy_lab/tpm/data.py`, `src/open_energy_lab/tpm/features.py`, `src/open_energy_lab/tpm/fit.py`, `src/open_energy_lab/tpm/query.py`, `src/open_energy_lab/tpm/piecewise.py`, `src/open_energy_lab/tpm/optional_spflow.py`, `src/open_energy_lab/planning/dataset.py`, `src/open_energy_lab/planning/problem.py`, `src/open_energy_lab/planning/piecewise.py`, and `src/open_energy_lab/planning/optional_solver.py`
- [X] T012 [P] Add feature-scope and dependency-boundary placeholders in `docs/migration/tpm-planning.md`, `docs/migration/api-maturity.md`, and `docs/migration/dependency-policy.md`

**Checkpoint**: Shared scaffolding, boundary checks, and fixture utilities are
in place.

---

## Phase 3: User Story 1 - Export TPM-Ready Planning Datasets From Simulator Families (Priority: P1)

**Goal**: Let a library user export deterministic, persisted planning datasets
from evaluated simulator families with explicit flattened series fields and a
canonical `shortfall` target.

**Independent Test**: A reviewer can load committed simulator-family fixtures
plus design metadata, export a planning dataset offline, and verify row count,
column ordering, `ghi_<step>` and `load_<step>` fields, `shortfall`
derivation, and provenance metadata.

### Tests for User Story 1

- [X] T013 [P] [US1] Add unit coverage for export request validation, scenario alignment failures, and unsupported flattened fields in `tests/unit/simulator/test_planning_export.py`
- [X] T014 [P] [US1] Add unit coverage for planning dataset schema versioning, row ordering, `shortfall` aggregation semantics, and export reproducibility metadata in `tests/unit/planning/test_dataset_schema.py`
- [X] T015 [P] [US1] Add offline simulator-family-to-dataset integration coverage in `tests/integration/planning/test_dataset_export.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement export request models, flattened column naming, and horizon-level `shortfall` derivation in `src/open_energy_lab/simulator/planning_export.py`
- [X] T016a [US1] Document and preserve the selected simulator feature-flattening and planning-target derivation behavior from `legacy/old_tpm/src_py/simulator/feature_engineering.py` in `src/open_energy_lab/simulator/planning_export.py` and `docs/migration/tpm-planning.md`
- [ ] T017 [US1] Implement planning dataset artifact models, versioned persistence, reload helpers, seed lineage, numeric tolerances, and export reproducibility metadata in `src/open_energy_lab/planning/dataset.py`
- [ ] T017a [US1] Define and validate the canonical persisted planning-dataset payload shape, including whether JSON stores rows directly or wraps tabular content with metadata, in `src/open_energy_lab/planning/dataset.py` and `tests/unit/planning/test_dataset_schema.py`
- [ ] T018 [US1] Export the planning-dataset workflow from `src/open_energy_lab/simulator/__init__.py` and `src/open_energy_lab/planning/__init__.py`
- [ ] T019 [US1] Populate committed planning-dataset export fixtures and provenance in `tests/fixtures/planning/planning_dataset_export_case.json`, `tests/fixtures/tpm/planning_dataset_v1.json`, `tests/fixtures/planning/README.md`, and `tests/fixtures/tpm/README.md`
- [ ] T020 [US1] Document dataset export usage, target semantics, and preserve/improve/reject notes in `docs/migration/tpm-planning.md` and `specs/009-tpm-planning/quickstart.md`

**Checkpoint**: User Story 1 is functional and independently testable through
`tests/integration/planning/test_dataset_export.py`.

---

## Phase 4: User Story 2 - Fit, Reload, And Query TPM Artifacts (Priority: P2)

**Goal**: Let a researcher fit a TPM artifact from exported planning datasets,
reload it offline, and evaluate conditional risk or likelihood queries with
typed feature metadata and preserved piecewise approximation metadata.

**Independent Test**: A reviewer can fit a TPM artifact from a committed
planning dataset fixture, reload it offline, and verify deterministic feature
typing, schema metadata, marginalization behavior, conditional-query outputs,
and fixture-backed piecewise metadata behavior.

### Tests for User Story 2

- [ ] T021 [P] [US2] Add typed-feature and data-handler unit coverage for continuous, binary, categorical, and mixed feature schemas in `tests/unit/tpm/test_features.py` and `tests/unit/tpm/test_data_handler.py`
- [ ] T022 [P] [US2] Add TPM artifact schema, unsupported-version, unseen categorical value, and out-of-bounds feature assignment unit coverage in `tests/unit/tpm/test_artifact_schema.py`
- [ ] T023 [P] [US2] Add conditional-query, marginalization, missing required decision-feature, and incompatible target-request unit coverage in `tests/unit/tpm/test_query.py`
- [ ] T024 [P] [US2] Add fit-reload-query integration coverage for exported planning datasets in `tests/integration/planning/test_tpm_fit_workflow.py`

### Implementation for User Story 2

- [ ] T025 [US2] Migrate typed feature metadata, normalization, and schema helpers from `legacy/old_tpm/src_py/tpm/data/datahandler.py`, `legacy/old_tpm/src_py/tpm/data/features/feature.py`, `legacy/old_tpm/src_py/tpm/data/features/binary.py`, `legacy/old_tpm/src_py/tpm/data/features/categorical.py`, `legacy/old_tpm/src_py/tpm/data/features/contiguous.py`, `legacy/old_tpm/src_py/tpm/data/features/mixed.py`, and `legacy/old_tpm/src_py/tpm/data/types.py` into `src/open_energy_lab/tpm/features.py` and `src/open_energy_lab/tpm/data.py`
- [ ] T026 [US2] Implement versioned TPM artifact models, JSON metadata persistence, supported-version loading, and documented SPN payload representation handling in `src/open_energy_lab/tpm/artifact.py`
- [ ] T027 [US2] Implement SPFlow-backed fit adapters, lazy backend loading, and training configuration capture in `src/open_energy_lab/tpm/fit.py` and `src/open_energy_lab/tpm/optional_spflow.py`
- [ ] T028 [US2] Implement conditional probability, log-likelihood, and marginalization queries in `src/open_energy_lab/tpm/query.py`
- [ ] T029 [US2] Implement canonical piecewise-approximation metadata, fit/query tolerance capture, and preserved solver-facing encoding helpers in `src/open_energy_lab/tpm/piecewise.py` using `legacy/old_tpm/src_py/tpm/spn/main.py`, `legacy/old_tpm/src_py/tpm/spn/encoding.py`, `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`, and `legacy/old_tpm/src_py/utils/densities.py` as selective migration evidence
- [ ] T030 [US2] Export TPM public APIs from `src/open_energy_lab/tpm/__init__.py`
- [ ] T031 [US2] Populate TPM artifact, unsupported-version, and query fixtures with provenance in `tests/fixtures/tpm/tpm_artifact_v1.json`, `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`, `tests/fixtures/tpm/tpm_query_case.json`, and `tests/fixtures/tpm/README.md`
- [ ] T032 [US2] Document typed-feature migration, lazy SPFlow backend boundary, and query workflow in `docs/migration/tpm-planning.md` and `specs/009-tpm-planning/quickstart.md`

**Checkpoint**: User Story 2 is functional and independently testable through
`tests/integration/planning/test_tpm_fit_workflow.py`.

---

## Phase 5: User Story 3 - Solve Chance-Constrained Planning Problems From TPM Artifacts (Priority: P3)

**Goal**: Let a planner assemble and optionally solve a first-release
piecewise MILP that chooses battery and solar decision variables subject to a
direct `shortfall` chance constraint.

**Independent Test**: A reviewer can load committed TPM and planning-problem
fixtures, assemble the planning model offline without a solver, validate
decision-scope and constraint semantics, and optionally solve the model with a
supported backend to confirm reproducible cost and risk summaries.

### Tests for User Story 3

- [ ] T033 [P] [US3] Add planning-problem validation unit coverage for battery-and-solar scope, threshold semantics, and chance-limit validation in `tests/unit/planning/test_problem.py`
- [ ] T033a [P] [US3] Add unit coverage for the exact first-release decision-variable types supported by battery and solar planning in `tests/unit/planning/test_problem.py`
- [ ] T034 [P] [US3] Add piecewise-assembly, reproducibility-metadata, and optional-solver boundary unit coverage in `tests/unit/planning/test_piecewise.py` and `tests/unit/planning/test_optional_solver.py`
- [ ] T035 [P] [US3] Add offline planning-model assembly integration coverage in `tests/integration/planning/test_problem_assembly.py`
- [ ] T036 [P] [US3] Add repeated-run optional solve coverage that compares selected design, objective value, estimated risk, or infeasibility diagnostics, and deterministic skip coverage in `tests/integration/planning/test_optional_solve.py`

### Implementation for User Story 3

- [ ] T037 [US3] Implement planning problem definitions, decision validation, chance-constraint metadata, solver-configuration reproducibility fields, and deterministic fixture baseline handling in `src/open_energy_lab/planning/problem.py`
- [ ] T038 [US3] Implement solver-facing piecewise assembly helpers that consume TPM approximation metadata in `src/open_energy_lab/planning/piecewise.py`
- [ ] T038a [US3] Document and enforce the supported first-release planning decision-variable set in `src/open_energy_lab/planning/problem.py` and `src/open_energy_lab/planning/piecewise.py`
- [ ] T039 [US3] Implement Pyomo-backed solver-model handoff, lazy backend loading, unavailable-backend diagnostics, and solve-summary handling in `src/open_energy_lab/planning/optional_solver.py`
- [ ] T040 [US3] Export planning assembly and optional solve APIs from `src/open_energy_lab/planning/__init__.py`
- [ ] T041 [US3] Populate planning-problem and optional-solve fixtures with provenance, solver-configuration metadata, and deterministic baseline expectations in `tests/fixtures/planning/planning_problem_case.json` and `tests/fixtures/planning/README.md`
- [ ] T042 [US3] Document planning model assembly, Pyomo-backed solve behavior, direct chance-constraint semantics, solver reproducibility expectations, and explicit backend-specific follow-up validation guidance for SPFlow and Pyomo in `docs/migration/tpm-planning.md` and `specs/009-tpm-planning/quickstart.md`
- [ ] T042a [US3] Document the unified reproducibility contract in `specs/009-tpm-planning/quickstart.md` and `docs/migration/tpm-planning.md`

**Checkpoint**: User Story 3 is functional and independently testable through
`tests/integration/planning/test_problem_assembly.py`, with solve checks
remaining optional when solver dependencies are unavailable.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Finalize migration guidance, repository notes, and validation
commands that apply across all stories.

- [ ] T043 [P] Update public API maturity and dependency classification for `open_energy_lab.tpm`, `open_energy_lab.planning`, and simulator dataset export, including SPFlow and Pyomo as canonical workflow backends with lazy import boundaries, in `docs/migration/api-maturity.md` and `docs/migration/dependency-policy.md`
- [ ] T044 [P] Update fixture provenance, environment assumptions, and parity guidance for TPM-planning validation in `docs/migration/fixture-provenance.md`, `docs/migration/environment-assumptions.md`, and `docs/migration/parity-validation.md`
- [ ] T045 [P] Update migration index and repository guidance for the TPM-planning feature in `docs/migration/README.md` and `AGENTS.md`
- [ ] T046 Run the validation commands documented in `specs/009-tpm-planning/quickstart.md`: `uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning`, `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py`, `uv run pytest tests/unit/demand tests/unit/simulator tests/integration/demand tests/integration/simulator`, `uv run python -c "import open_energy_lab; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"`, and `rg "from legacy|import legacy" src/open_energy_lab/tpm src/open_energy_lab/planning src/open_energy_lab/simulator tests/unit/planning tests/unit/tpm tests/integration/planning docs/migration`
- [ ] T047 Document final validation outcomes and any skipped optional checks in `specs/009-tpm-planning/quickstart.md`

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story implementation begins.
- US1 is the MVP and must complete before US2 because TPM fitting depends on
  the stable planning dataset contract.
- US2 must complete before US3 because planning assembly depends on the TPM
  artifact schema, query semantics, and piecewise approximation metadata.
- Phase 6 depends on the completion of the selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 -> US2 -> US3 -> Polish
```

## Parallel Execution Examples

### Setup

```text
T002 tests/fixtures/planning/planning_dataset_export_case.json
T003 tests/fixtures/planning/README.md
T004 docs/migration/tpm-planning.md
```

### Foundational

```text
T005 tests/unit/tpm/test_import_boundary.py
T006 tests/unit/tpm/test_no_legacy_imports.py
T009 tests/integration/planning/fixture_utils.py
T010 tests/integration/planning/test_fixture_schema.py
T010a tests/integration/planning/test_reproducibility_contract.py
T012 docs/migration/tpm-planning.md
```

### User Story 1

```text
T013 tests/unit/simulator/test_planning_export.py
T014 tests/unit/planning/test_dataset_schema.py
T015 tests/integration/planning/test_dataset_export.py
```

### User Story 2

```text
T021 tests/unit/tpm/test_features.py
T022 tests/unit/tpm/test_artifact_schema.py
T023 tests/unit/tpm/test_query.py
T024 tests/integration/planning/test_tpm_fit_workflow.py
```

### User Story 3

```text
T033 tests/unit/planning/test_problem.py
T033a tests/unit/planning/test_problem.py
T034 tests/unit/planning/test_piecewise.py
T035 tests/integration/planning/test_problem_assembly.py
T036 tests/integration/planning/test_optional_solve.py
```

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Deliver US1 to establish the stable simulator-to-dataset workflow.
3. Validate `tests/integration/planning/test_dataset_export.py` before
   expanding scope.

### Incremental Delivery

1. Add US2 to deliver typed-feature TPM fit, reload, and query behavior from
   persisted planning datasets.
2. Add US3 to deliver planning model assembly and optional solve behavior from
   persisted TPM artifacts.
3. Finish Phase 6 to align migration docs, repository guidance, and
   validation commands with the shipped surface.

### Final Verification

1. Run the validation commands listed in
   `specs/009-tpm-planning/quickstart.md`.
2. Update migration, fixture, and repository guidance with final outcomes and
   any skipped optional checks.
3. Keep all new product code out of `legacy/*`.

## Notes

- [P] tasks are safe to run in parallel because they touch different files and
  have no dependency on unfinished work.
- Every task names exact files or directories to keep execution unambiguous.
- All checklist entries follow the required `- [ ] T### [P?] [Story?] ...`
  format.
