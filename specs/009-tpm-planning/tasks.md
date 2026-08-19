# Tasks: TPM-Backed Planning And Simulator Dataset Export

**Input**: Design documents from `/specs/009-tpm-planning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Curation policy**: Checked tasks consolidate implementation completed under
the original 009 plan. Unchecked tasks are the corrective delta introduced by
the 2026-08-17/18 dependency and backend clarifications. A checked baseline
task does not imply that its old optional-backend assumptions remain valid;
the unchecked follow-up tasks supersede those assumptions.

**Tests**: The specification requires test-first corrective work, including
real current-SPFlow fit/query, current-SPFlow-to-piecewise-MIO parity, real Pyomo/HiGHS
optimal and infeasible solves, explicit fixture replay, lazy-import checks, and
008+009 regression validation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes different files and does not
  depend on another incomplete task.
- **[Story]**: Maps the task to US1, US2, or US3.
- Checked entries are curated completed baseline work; unchecked entries are
  immediately actionable corrective work.

## Phase 1: Setup And Dependency Policy

**Purpose**: Preserve the completed package/fixture setup and establish the
required modern backend environment before backend implementation changes.

- [X] T001 Consolidate the completed TPM and planning package/test scaffolds in `src/open_energy_lab/tpm/`, `src/open_energy_lab/planning/`, `tests/unit/tpm/`, `tests/unit/planning/`, and `tests/integration/planning/`
- [X] T002 Consolidate the completed planning/TPM fixture and migration-note scaffolds in `tests/fixtures/planning/`, `tests/fixtures/tpm/`, and `docs/migration/tpm-planning.md`
- [X] T003 Declare initial required pins for `spflow==1.1.0`, `pyomo==6.10.1`, and `highspy==1.15.1`, attempt locked resolution on Python 3.11, 3.12, 3.13, and 3.14, and either retain all four versions or record dependency-specific incompatibility evidence while updating `requires-python` and regenerating `uv.lock` in `pyproject.toml`, `uv.lock`, and `specs/009-tpm-planning/quickstart.md`
- [X] T004 Add required-backend CI jobs matching the supported Python result from T003, initially covering Python 3.11, 3.12, 3.13, and 3.14, enforce a 120-second focused-suite timeout, and forbid allowed-failure or skipped required-backend jobs in `.github/workflows/ci.yml`
- [X] T005 [P] Replace optional-install terminology with required-install/lazy-import terminology in `README.md`, `docs/migration/dependency-policy.md`, and `docs/migration/environment-assumptions.md`

---

## Phase 2: Foundational Corrective Contracts

**Purpose**: Establish artifact modes, compatibility diagnostics, and lazy
boundaries shared by the modern SPFlow and HiGHS story work.

- [X] T006 Consolidate completed lazy import, package surface, and no-legacy-import coverage in `tests/unit/tpm/test_import_boundary.py`, `tests/unit/planning/test_import_boundary.py`, `tests/unit/test_import_contract.py`, and `tests/unit/test_no_legacy_imports.py`
- [X] T007 Consolidate completed planning/TPM fixture schema and provenance helpers in `tests/integration/planning/fixture_utils.py`, `tests/integration/planning/test_fixture_schema.py`, and `tests/integration/planning/test_tpm_fixture_schema.py`
- [X] T008 Consolidate completed typed feature, dataset, artifact, and planning definition models in `src/open_energy_lab/tpm/`, `src/open_energy_lab/planning/`, and `src/open_energy_lab/simulator/planning_export.py`
- [X] T009 [P] Replace `tests/unit/test_optional_dependency_boundaries.py` with lazy-import coverage proving required `spflow`, `torch`, `pyomo`, and `highspy` remain absent from `sys.modules` until their workflows run, and update references in `tests/unit/test_lazy_dependency_boundaries.py`, `AGENTS.md`, and `specs/009-tpm-planning/quickstart.md`
- [X] T010 [P] Add required-install compatibility diagnostic tests, including incompatible backend versions and missing required installations, in `tests/unit/tpm/test_backend_compatibility.py` and `tests/unit/planning/test_backend_compatibility.py`
- [X] T011 [P] Add TPM artifact schema-v2 tests for backend generation, API version, execution mode, project-relative sidecar locator, SHA-256 integrity, atomic replacement, and schema-v1 legacy payload rejection in `tests/unit/tpm/test_artifact_schema.py`
- [X] T012 [P] Add query contract tests that distinguish default `production` from explicit `fixture_replay` and forbid automatic empirical/metadata fallback in `tests/unit/tpm/test_query.py`
- [X] T013 Implement TPM artifact schema v2, project-relative sidecar locators, SHA-256 verification, atomic sibling-file replacement, production/fixture execution modes, and schema-v1 incompatibility errors in `src/open_energy_lab/tpm/artifact.py`
- [X] T014 Create current-SPFlow `tests/fixtures/tpm/tpm_artifact_v2.json`, retain `tests/fixtures/tpm/tpm_artifact_v1.json` for legacy rejection, and update `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`, `tests/fixtures/tpm/tpm_query_case.json`, and `tests/fixtures/tpm/README.md`

**Checkpoint**: Required dependencies are reproducibly installable, imports
remain lazy, and artifacts cannot silently cross backend generations or modes.

---

## Phase 3: User Story 1 - Export TPM-Ready Planning Datasets (Priority: P1)

**Goal**: Preserve the completed simulator-owned export and prove it remains
stable after required backend and artifact changes.

**Independent Test**: Export the committed simulator family twice and verify
identical row/column ordering, flattened fields, `shortfall`, and provenance
without importing SPFlow, Pyomo, or HiGHS during export.

- [X] T015 [US1] Consolidate completed export request validation, alignment failure, and flattened field tests in `tests/unit/simulator/test_planning_export.py`
- [X] T016 [US1] Consolidate completed planning dataset schema, ordering, shortfall, and reproducibility tests in `tests/unit/planning/test_dataset_schema.py` and `tests/integration/planning/test_dataset_export.py`
- [X] T017 [US1] Consolidate completed planning export and dataset persistence implementation in `src/open_energy_lab/simulator/planning_export.py` and `src/open_energy_lab/planning/dataset.py`
- [X] T018 [US1] Consolidate completed export public APIs in `src/open_energy_lab/simulator/__init__.py` and `src/open_energy_lab/planning/__init__.py`
- [X] T019 [US1] Consolidate completed export fixtures and provenance in `tests/fixtures/planning/planning_dataset_export_case.json`, `tests/fixtures/tpm/planning_dataset_v1.json`, and `tests/fixtures/planning/README.md`
- [X] T020 [US1] Add a regression asserting dataset export/reload does not import required TPM or solver backends in `tests/integration/planning/test_dataset_export.py`

**Checkpoint**: US1 remains independently complete and import-light.

---

## Phase 4: User Story 2 - Fit, Reload, And Query Current-SPFlow Artifacts (Priority: P2)

**Goal**: Port validated TPM behavior to SPFlow 1.1, persist current model
sidecars, and make real production queries the default while retaining only an
explicit fixture replay mode.

**Independent Test**: Fit a real SPFlow 1.1 model from the committed planning
dataset, persist and reload it, evaluate conditional likelihood/probability
with explicit marginalization, and reproduce the result within tolerance with
fixed preprocessing and Torch seeds.

### Completed Baseline For User Story 2

- [X] T021 [US2] Consolidate completed continuous, binary, categorical, and mixed feature schema behavior in `src/open_energy_lab/tpm/features.py`, `src/open_energy_lab/tpm/data.py`, `tests/unit/tpm/test_features.py`, and `tests/unit/tpm/test_data_handler.py`
- [X] T022 [US2] Consolidate completed versioned TPM JSON metadata and reload baseline in `src/open_energy_lab/tpm/artifact.py` and `tests/unit/tpm/test_artifact_schema.py`
- [X] T023 [US2] Consolidate completed legacy-generation fit adapter baseline in `src/open_energy_lab/tpm/fit.py` and `src/open_energy_lab/tpm/optional_spflow.py`
- [X] T024 [US2] Consolidate completed conditional query and marginalization baseline in `src/open_energy_lab/tpm/query.py` and `tests/unit/tpm/test_query.py`
- [X] T025 [US2] Consolidate completed piecewise metadata and encoding helper baseline in `src/open_energy_lab/tpm/piecewise.py` and `tests/unit/tpm/test_piecewise.py`
- [X] T026 [US2] Consolidate completed TPM root API and fixture-backed workflow coverage in `src/open_energy_lab/tpm/__init__.py` and `tests/integration/planning/test_tpm_fit_workflow.py`

### Corrective Tests For User Story 2

- [X] T027 [P] [US2] Add real SPFlow 1.1 structure-learning tests for Normal, Bernoulli, and Categorical typed leaf scopes, Torch tensors, canonical seed 13, robustness seeds 37 and 101, fit configuration translation, a 30-second fixture-fit budget, and repeated canonical fits whose stable structure, parameter, and likelihood summaries agree within `1e-9` in `tests/integration/tpm/test_spflow_v1_fit.py`
- [X] T028 [P] [US2] Add real SPFlow 1.1 likelihood and marginalization tests covering NaN evidence, structural removal semantics, tensor output reduction, conditional probability, missing decision features, out-of-bound continuous values, unseen categories, invalid binary values, and a 30-second fixture-query budget in `tests/integration/tpm/test_spflow_v1_query.py`
- [X] T029 [P] [US2] Add current model sidecar save/load, manifest hash verification, corrupt payload, and pre-1.0 rejection tests in `tests/integration/tpm/test_spflow_v1_persistence.py`
- [X] T030 [P] [US2] Add mixed-feature mapping and pre-SPFlow validation tests for continuous bounds, binary domains, categorical membership, required decision features, supported mixed scopes, dtypes, and structured errors containing `feature_name`, `expected_domain`, `reason`, and an optional `supplied_value` in `tests/unit/tpm/test_spflow_v1_features.py`
- [X] T031 [P] [US2] Add tests proving production mode fails without a valid current payload while explicit fixture replay remains deterministic in `tests/integration/tpm/test_execution_modes.py`
- [X] T032 [P] [US2] Add current-SPFlow-to-piecewise-MIO compiler contract tests for sum/product graphs with one channel/repetition, Normal/Bernoulli/Categorical leaves, the canonical five-breakpoint configuration, invalid breakpoint rejection, and type-and-scope diagnostics for arbitrary modules, custom leaves, extra channels/repetitions, shared subgraphs, and legacy histograms in `tests/unit/tpm/test_spflow_v1_mio.py`
- [X] T033 [US2] Add native-likelihood versus current-SPFlow-to-piecewise-MIO probability parity tests using five breakpoints and enforcing `1e-6` maximum absolute error and `1e-9` repeatability in `tests/integration/tpm/test_spflow_v1_mio_parity.py`

### Corrective Implementation For User Story 2

- [X] T034 [US2] Implement SPFlow 1.1 capability/version diagnostics and lazy loading without legacy `spn.*` runtime imports in `src/open_energy_lab/tpm/optional_spflow.py`
- [X] T035 [US2] Implement typed feature-to-`Scope` mapping for Normal, Bernoulli, and Categorical leaves, treating mixed models as concrete leaves on separate scopes, and translate legacy fit configuration to `learn_spn` in `src/open_energy_lab/tpm/features.py` and `src/open_energy_lab/tpm/fit.py`
- [X] T036 [US2] Implement deterministic Torch-backed fitting for canonical seed 13 and robustness seeds 37/101, persist fit-relevant determinism configuration and stable structure/parameter/likelihood summaries for repeatability comparison without relying on serialized-byte equality, and persist schema-v2 model sidecars in `src/open_energy_lab/tpm/fit.py` and `src/open_energy_lab/tpm/artifact.py`
- [X] T037 [US2] Implement SPFlow 1.1 likelihood reduction, NaN-evidence marginalization, structural marginalization, conditional query semantics, and pre-backend structured feature errors with reasons `missing`, `out_of_bounds`, `unseen_category`, or `invalid_binary` and an optional supplied value in `src/open_energy_lab/tpm/query.py`
- [ ] T038 [US2] Gate empirical dataset evaluation behind explicit `fixture_replay` and remove automatic table/metadata fallback in `src/open_energy_lab/tpm/query.py` and `src/open_energy_lab/tpm/fit.py`
- [ ] T039 [US2] Implement the versioned current-SPFlow-to-piecewise-MIO compiler for sum/product, single-channel, single-repetition Normal/Bernoulli/Categorical graphs with five canonical breakpoints, recorded explicit overrides, invalid-configuration rejection, and module-type-and-scope errors in `src/open_energy_lab/tpm/mio.py`
- [ ] T040 [US2] Export execution modes, backend compatibility errors, artifact-version errors, and current-SPFlow capability metadata from `src/open_energy_lab/tpm/__init__.py` and extend `tests/unit/tpm/test_package_surface.py`
- [ ] T041 [US2] Replace fake-backend production fixtures/examples with reproducibly generated real current-SPFlow schema-v2 artifacts recording source dataset/configuration, seed, backend/compiler versions, five-breakpoint configuration, MIO epsilon, and sidecar SHA-256; provide a deterministic regeneration/verification command while retaining clearly labeled fixture replay evidence in `tests/fixtures/tpm/`, `examples/tpm_planning/run_generic_rows_pipeline.py`, and `examples/tpm_planning/README.md`

**Checkpoint**: US2 is complete only when real current-SPFlow fit/reload/query
and current-SPFlow-to-piecewise-MIO parity pass; fixture replay alone is insufficient.

---

## Phase 5: User Story 3 - Solve Chance-Constrained Planning Problems (Priority: P3)

**Goal**: Consume the supported current-SPFlow-to-piecewise-MIO compiler output
and solve the battery-and-solar planning problem through required Pyomo/HiGHS,
with Gurobi remaining supplemental.

**Independent Test**: Starting with a real current-SPFlow artifact, compile the
supported piecewise model, solve optimal and infeasible cases through
`SolverFactory("highs")`, and reproduce design, objective, risk, termination,
and solver metadata across repeated runs.

### Completed Baseline For User Story 3

- [X] T042 [US3] Consolidate completed planning problem validation and direct battery/solar decision scope in `src/open_energy_lab/planning/problem.py` and `tests/unit/planning/test_problem.py`
- [X] T043 [US3] Consolidate completed piecewise planning assembly baseline in `src/open_energy_lab/planning/piecewise.py` and `tests/unit/planning/test_piecewise.py`
- [X] T044 [US3] Consolidate completed Pyomo handoff and solve summary baseline in `src/open_energy_lab/planning/optional_solver.py` and `tests/unit/planning/test_optional_solver.py`
- [X] T045 [US3] Consolidate completed planning assembly and fixture-backed solve coverage in `tests/integration/planning/test_problem_assembly.py` and `tests/integration/planning/test_optional_solve.py`
- [X] T046 [US3] Consolidate completed planning public API and fixture metadata in `src/open_energy_lab/planning/__init__.py` and `tests/fixtures/planning/planning_problem_case.json`

### Corrective Tests For User Story 3

- [ ] T047 [P] [US3] Add tests that omission of solver configuration selects `highs` and missing/incompatible Pyomo or `highspy` is a required-install failure in `tests/unit/planning/test_highs_solver.py`
- [ ] T048 [P] [US3] Add real Pyomo/HiGHS optimal, infeasible, integrality, 30-second time limit, one-thread execution, solution-loading, and `1e-9` repeatability tests in `tests/integration/planning/test_highs_solver.py`
- [ ] T049 [P] [US3] Add environment-independent policy tests for explicit Gurobi selection, missing binary/license diagnostics, permitted optional skip behavior, and parsing fixture-defined comparison tolerances in `tests/unit/planning/test_gurobi_solver.py`
- [ ] T050 [US3] Add an end-to-end real current-SPFlow artifact to current-SPFlow-to-piecewise-MIO compiler output to Pyomo/HiGHS solve test in `tests/integration/planning/test_spflow_v1_highs_pipeline.py`

### Corrective Implementation For User Story 3

- [ ] T051 [US3] Make `highs` the default solver with seed 13, one thread, 30-second time limit, and `1e-9` tolerance, recording Pyomo, `highspy`, interface, options, termination, and versions in `src/open_energy_lab/planning/problem.py` and `src/open_energy_lab/planning/optional_solver.py`
- [ ] T052 [US3] Remove successful skip behavior for required Pyomo/HiGHS failures while retaining explicit supplemental-solver skip behavior in `src/open_energy_lab/planning/optional_solver.py`
- [ ] T053 [US3] Adapt planning piecewise assembly to consume versioned current-SPFlow-to-piecewise-MIO compiler output and reject incompatible compiler metadata in `src/open_energy_lab/planning/piecewise.py` and `src/open_energy_lab/planning/problem.py`
- [ ] T054 [US3] Update planning fixtures for required HiGHS optimal/infeasible outcomes, `1e-9` repeatability, and supplemental Gurobi comparison metadata defining `reference_solver`, `candidate_solver`, `objective_tolerance`, and `risk_tolerance` in `tests/fixtures/planning/planning_problem_case.json` and `tests/fixtures/planning/README.md`
- [ ] T055 [US3] Port the real backend pipeline to SPFlow 1.1 and default HiGHS in `examples/tpm_planning/run_real_backend_pipeline.py` and `examples/tpm_planning/README.md`
- [ ] T056 [US3] Update planning solve and reproducibility guidance for required HiGHS and optional Gurobi in `docs/migration/tpm-planning.md` and `specs/009-tpm-planning/quickstart.md`

**Checkpoint**: US3 requires a real, license-free current-SPFlow-to-HiGHS solve;
assembly-only and fake-backend results do not complete the story.

---

## Phase 6: Polish And Cross-Cutting Validation

**Purpose**: Reconcile repository-wide maturity claims and prove the corrected
009 feature integrates with merged 008 behavior.

- [X] T057 Consolidate completed TPM/planning migration, maturity, dependency, fixture provenance, and environment documentation in `docs/migration/`
- [X] T058 Consolidate completed repository guidance and relevant validation command documentation in `AGENTS.md` and `specs/009-tpm-planning/quickstart.md`
- [ ] T059 [P] Update current-SPFlow migration provenance, refit policy, compiler scope, and parity limitations in `docs/migration/tpm-planning.md`, `docs/migration/parity-validation.md`, and `docs/migration/fixture-provenance.md`
- [ ] T060 [P] Update API maturity and dependency classifications so required SPFlow/Pyomo/HiGHS and optional Gurobi are consistent in `docs/migration/api-maturity.md`, `docs/migration/dependency-policy.md`, and `docs/migration/README.md`
- [ ] T061 Run required US2/US3 focused validation and record exact outcomes plus separate fit, query, compile, and solve durations in `specs/009-tpm-planning/quickstart.md`
- [ ] T062 Run the complete demand, simulator, TPM, planning, lazy-import, import-contract, and no-legacy-import regression commands from `AGENTS.md` and record outcomes in `specs/009-tpm-planning/quickstart.md`
- [ ] T063 Add and run optional licensed Gurobi integration coverage that records HiGHS and Gurobi objective/risk values, measured absolute differences, fixture-defined tolerances, and pass/fail or availability-skip results, then run optional legacy parity checks without weakening required validation in `tests/integration/planning/test_gurobi_solver.py` and `specs/009-tpm-planning/quickstart.md`

---

## Dependencies And Execution Order

### Phase Dependencies

- T003 blocks T004, T005, and all required-backend corrective work. T004 and
  T005 do not block Phase 2 implementation after T003 completes, but both must
  finish before T061 and T062 final validation.
- Phase 2 artifact/mode contracts block US2 and US3 corrective implementation.
- US1 baseline is complete; T020 can run after Phase 2 and in parallel with
  early US2 tests.
- US2 current-SPFlow fit/query work precedes its
  current-SPFlow-to-piecewise-MIO compiler tasks.
- US2 compiler parity (T032, T033, T039) blocks US3 integration tasks T050 and
  T053.
- US3 HiGHS unit/integration work can begin after Phase 2, but end-to-end
  completion depends on US2 compiler output.
- Phase 6 final validation depends on all selected corrective tasks.

### Corrective Dependency Graph

```text
T003 required stack and supported-Python evidence
  |-> T004 matching required-backend CI matrix
  |-> T005 dependency-policy documentation
  `-> T009-T014 foundational contracts
        |-> T020 US1 regression
        |-> T027-T031 current-SPFlow fit/query
        |     `-> T032-T033, T039 compiler parity
        |           `-> T050, T053 current-SPFlow-to-HiGHS integration
        `-> T047-T049, T051-T052 solver policy
              `-> T050 end-to-end pipeline

T004 + T005 + T050 + remaining corrective work
  `-> T059-T060 documentation reconciliation
        `-> T061-T062 required final validation
              `-> T063 optional Gurobi/legacy follow-up
```

## Parallel Execution Examples

### Foundational

```text
T009 tests/unit/test_lazy_dependency_boundaries.py
T010 tests/unit/tpm/test_backend_compatibility.py
T011 tests/unit/tpm/test_artifact_schema.py
T012 tests/unit/tpm/test_query.py
```

### User Story 2

```text
T027 tests/integration/tpm/test_spflow_v1_fit.py
T028 tests/integration/tpm/test_spflow_v1_query.py
T029 tests/integration/tpm/test_spflow_v1_persistence.py
T030 tests/unit/tpm/test_spflow_v1_features.py
T031 tests/integration/tpm/test_execution_modes.py
T032 tests/unit/tpm/test_spflow_v1_mio.py
```

### User Story 3

```text
T047 tests/unit/planning/test_highs_solver.py
T048 tests/integration/planning/test_highs_solver.py
T049 tests/unit/planning/test_gurobi_solver.py
```

## Implementation Strategy

### Revised MVP

US1 is already delivered. The corrective MVP is:

1. Complete T003 and Phase 2.
2. Complete US2 real current-SPFlow fit/reload/query through T038.
3. Validate US2 independently before implementing the new
   current-SPFlow-to-piecewise-MIO compiler.

### Incremental Delivery

1. Deliver SPFlow 1.1 fit/query and explicit execution modes.
2. Deliver the current-SPFlow-to-piecewise-MIO compiler with native likelihood
   parity.
3. Deliver required Pyomo/HiGHS solving and end-to-end planning integration.
4. Reconcile documentation and run full 008+009 regression validation.

### Completion Rule

The corrected feature is not complete until T061 and T062 pass. Fake-backend,
fixture-only, assembly-only, or skipped required-backend results cannot satisfy
the revised specification.

## Notes

- Completed baseline tasks are intentionally consolidated rather than copied
  one-for-one from the obsolete granular checklist.
- New tasks use strict sequential IDs and exact file paths.
- Gurobi and legacy runtime checks are supplementary; current SPFlow,
  Pyomo, and HiGHS are required.
