# Tasks: External Controller Boundary MVP

**Input**: Design documents from `/specs/004-controller-boundary/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Migration and library behavior tasks include focused unit,
integration, import-boundary, and fixture-validation checks because the spec
requires deterministic validation and stable public API evidence.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Path Conventions

- **Spec Kit**: `.specify/`, `.agents/`
- **Legacy references**: `legacy/old_tpm/`, `legacy/fed_trpo/`
- **Target library**: `src/open_energy_lab/core`, `src/open_energy_lab/simulator`
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/parity/`, `tests/fixtures/`

## Phase 1: Setup

**Purpose**: Establish feature-specific files and deterministic validation inputs without expanding legacy code.

- [X] T001 Confirm target module, test, and documentation paths in `specs/004-controller-boundary/plan.md`
- [X] T002 [P] Create the controller-driven arbitrage fixture scaffold in `tests/fixtures/simulator/controller_arbitrage_case.json`
- [X] T003 [P] Create the controller-driven battery-load-PV fixture scaffold in `tests/fixtures/simulator/controller_battery_load_pv_case.json`
- [X] T004 [P] Create the core boundary test package notes in `tests/unit/core/README.md`
- [X] T005 [P] Add controller fixture provenance placeholders in `tests/fixtures/simulator/README.md`

---

## Phase 2: Foundational

**Purpose**: Add shared validation scaffolding and documentation contracts that block all story work.

- [X] T006 [P] Add shared controller fixture loading helpers in `tests/integration/simulator/controller_fixture_utils.py`
- [X] T007 [P] Add controller fixture schema validation tests in `tests/integration/simulator/test_controller_fixture_schema.py`
- [X] T008 [P] Add controller migration note contract tests in `tests/unit/core/test_controller_migration_note.py`
- [X] T009 Create the controller migration note scaffold in `docs/migration/controller-boundary-mvp.md`

**Checkpoint**: Shared fixtures, migration-note coverage, and controller test scaffolding are in place.

---

## Phase 3: User Story 1 - Define a Controller-Facing Boundary (Priority: P1)

**Goal**: Give library consumers a stable typed way to produce one-step dispatch proposals without depending on simulator internals.

**Independent Test**: A focused unit test proves that `open_energy_lab.core` accepts a current-step `ControllerContext`, produces a one-step `DispatchProposal`, and rejects invalid sign or shape semantics before simulator evaluation.

### Tests for User Story 1

- [X] T010 [P] [US1] Add controller contract validation tests in `tests/unit/core/test_controller_contract.py`
- [X] T011 [P] [US1] Add core import-boundary tests for controller exports in `tests/unit/core/test_import_boundary.py`

### Implementation for User Story 1

- [ ] T012 [US1] Implement typed controller contracts in `src/open_energy_lab/core/controller.py`
- [ ] T013 [US1] Export the stable controller API from `src/open_energy_lab/core/__init__.py`
- [ ] T014 [US1] Document preserved, improved, and rejected controller-boundary semantics in `docs/migration/controller-boundary-mvp.md`

**Checkpoint**: User Story 1 is functional and independently testable through `tests/unit/core/test_controller_contract.py`.

---

## Phase 4: User Story 2 - Evaluate Controller-Driven Simulation Deterministically (Priority: P2)

**Goal**: Let the simulator own a deterministic controller episode loop that works for both migrated scenario families while preserving existing physics and settlement semantics.

**Independent Test**: Integration coverage proves that the same controller and scenario inputs produce identical proposals, realized traces, and aggregate results across repeated runs for both `ArbitrageScenario` and `BatteryLoadPVScenario`, while dedicated regression cases prove the preserved explicit-dispatch path and built-in `price_threshold` path remain available and behaviorally unchanged.

### Tests for User Story 2

- [ ] T015 [US2] Add controller runner validation, clamping, and named incomplete-context rejection tests in `tests/unit/simulator/test_controller_runner.py`
- [ ] T016 [P] [US2] Extend preserved explicit-dispatch and `price_threshold` regression coverage for arbitrage in `tests/integration/simulator/test_battery_arbitrage_trace.py`
- [ ] T017 [P] [US2] Extend preserved explicit-dispatch and `price_threshold` regression coverage for battery-load-PV in `tests/integration/simulator/test_battery_load_pv_trace.py`
- [ ] T018 [P] [US2] Add controller evaluation integration coverage for both scenarios in `tests/integration/simulator/test_controller_evaluation.py`
- [ ] T019 [P] [US2] Add named incomplete-context validation coverage for controller evaluation in `tests/integration/simulator/test_controller_evaluation.py`

### Implementation for User Story 2

- [ ] T020 [US2] Implement the simulator-owned controller evaluation loop and named pre-evaluation rejection handling in `src/open_energy_lab/simulator/controller_runner.py`
- [ ] T021 [US2] Add current-step context extraction helpers for supported scenarios in `src/open_energy_lab/simulator/scenario.py`
- [ ] T022 [US2] Export `evaluate_with_controller` from `src/open_energy_lab/simulator/__init__.py`
- [ ] T023 [US2] Populate expected proposal and trace values in `tests/fixtures/simulator/controller_arbitrage_case.json`
- [ ] T024 [P] [US2] Populate expected proposal and trace values in `tests/fixtures/simulator/controller_battery_load_pv_case.json`
- [ ] T025 [US2] Update controller evaluation and preserved-path regression commands and fixture notes in `specs/004-controller-boundary/quickstart.md`

**Checkpoint**: User Story 2 is functional and independently testable through `tests/integration/simulator/test_controller_evaluation.py` plus the preserved-path trace regression suites.

---

## Phase 5: User Story 3 - Preserve a Lightweight Core While Enabling Future Adapters (Priority: P3)

**Goal**: Keep the new stable controller boundary import-light, free of runtime `legacy/*` dependencies, and documented as stable public API for future adapters.

**Independent Test**: Import-boundary and legacy-isolation tests prove that `open_energy_lab.core` and the controller-enabled simulator surface load without TorchRL, PyTorch, CityLearn, solver stacks, or runtime `legacy/*` imports.

### Tests for User Story 3

- [ ] T026 [P] [US3] Extend optional dependency boundary coverage for core and controller-runner imports in `tests/unit/test_optional_dependency_boundaries.py`
- [ ] T027 [P] [US3] Add core no-legacy-import checks in `tests/unit/core/test_no_legacy_imports.py`
- [ ] T028 [P] [US3] Extend simulator import-boundary assertions for controller runner exports in `tests/unit/simulator/test_import_boundary.py`
- [ ] T029 [P] [US3] Extend root package import-contract coverage for `open_energy_lab.core` in `tests/unit/test_import_contract.py`

### Implementation for User Story 3

- [ ] T030 [US3] Refine import-light controller type hints in `src/open_energy_lab/core/controller.py`
- [ ] T031 [US3] Update stable API maturity guidance for the controller boundary in `docs/migration/api-maturity.md`
- [ ] T032 [US3] Update migration governance guidance for controller-boundary validation in `docs/migration/parity-validation.md`

**Checkpoint**: User Story 3 is functional and independently testable through the import-boundary and no-legacy-import suites.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Finalize dependency classification, environment notes, and validation records that span multiple stories.

- [ ] T033 [P] Update controller-boundary dependency classification in `docs/migration/dependency-policy.md`
- [ ] T034 [P] Update controller-boundary environment assumptions in `docs/migration/environment-assumptions.md`
- [ ] T035 Run the planned validation commands documented in `specs/004-controller-boundary/quickstart.md`
- [ ] T036 Document final validation outcomes and any skipped checks in `specs/004-controller-boundary/quickstart.md`

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story implementation begins.
- US1 is the MVP and must complete before US2 because the simulator runner depends on the stable controller contract.
- US2 must complete before US3 because the import-boundary checks need the final controller-enabled simulator surface.
- Phase 6 depends on the completion of the selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 -> US2 -> US3 -> Polish
```

## Parallel Execution Examples

### Setup

```text
T002 tests/fixtures/simulator/controller_arbitrage_case.json
T003 tests/fixtures/simulator/controller_battery_load_pv_case.json
T004 tests/unit/core/README.md
T005 tests/fixtures/simulator/README.md
```

### Foundational

```text
T006 tests/integration/simulator/controller_fixture_utils.py
T007 tests/integration/simulator/test_controller_fixture_schema.py
T008 tests/unit/core/test_controller_migration_note.py
```

### User Story 1

```text
T010 tests/unit/core/test_controller_contract.py
T011 tests/unit/core/test_import_boundary.py
```

### User Story 2

```text
T016 tests/integration/simulator/test_battery_arbitrage_trace.py
T017 tests/integration/simulator/test_battery_load_pv_trace.py
T018 tests/integration/simulator/test_controller_evaluation.py
T019 tests/integration/simulator/test_controller_evaluation.py
T024 tests/fixtures/simulator/controller_battery_load_pv_case.json
```

### User Story 3

```text
T026 tests/unit/test_optional_dependency_boundaries.py
T027 tests/unit/core/test_no_legacy_imports.py
T028 tests/unit/simulator/test_import_boundary.py
T029 tests/unit/test_import_contract.py
```

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Deliver US1 to establish the stable controller contract in `open_energy_lab.core`.
3. Stop and validate `tests/unit/core/test_controller_contract.py` before moving on.

### Incremental Delivery

1. Add US2 to wire the stable contract into deterministic simulator execution for both supported scenarios.
2. Validate repeated-run behavior, named incomplete-context rejection, and preserved-path regression coverage with the new fixtures and existing trace suites.
3. Add US3 to harden import boundaries and public API maturity documentation.

### Final Verification

1. Run the validation commands listed in `specs/004-controller-boundary/quickstart.md`.
2. Update migration and dependency docs with final outcomes and any skipped checks.
3. Keep all new product code out of `legacy/*`.

## Notes

- [P] tasks are safe to run in parallel because they touch different files and do not depend on unfinished tasks.
- Every task names an exact file path so an implementation agent can execute it without more context.
- The generated fixtures remain synthetic, tiny, and deterministic; do not replace them with broad legacy runtime replay.
- The stable controller contract belongs in `src/open_energy_lab/core`, while the simulator retains ownership of physics and settlement enforcement.
