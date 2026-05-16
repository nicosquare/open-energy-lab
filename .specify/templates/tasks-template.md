---
description: "Task list template for Open Energy Lab feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Migration and library behavior tasks should include tests or
reproducible validation cases. Long-running training jobs are not a substitute
for focused checks.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Path Conventions

- **Spec Kit**: `.specify/`, `.agents/`
- **Legacy references**: `legacy/old_tpm/`, `legacy/fed_trpo/`
- **Target library**: Use the package/test paths chosen by the foundation spec
- **Tests**: Prefer `tests/unit/`, `tests/integration/`, `tests/parity/`, and `tests/fixtures/` once the target test layout exists

<!--
  The /speckit-tasks command MUST replace the examples below with actual tasks
  based on spec.md, plan.md, research.md, data-model.md, and contracts/.
-->

## Phase 1: Setup

**Purpose**: Establish feature-specific structure without expanding legacy code by default.

- [ ] T001 Confirm target package and test paths from plan.md
- [ ] T002 Identify legacy reference files and configs in `legacy/*` used by this feature
- [ ] T003 [P] Create or update fixtures needed for deterministic validation
- [ ] T004 [P] Document environment assumptions for optional dependencies, solvers, GPU, W&B, or SLURM

---

## Phase 2: Tests and Validation First

**Purpose**: Define the evidence that migrated or new behavior is correct.

**Critical**: Migration tasks must not proceed without a focused test, parity
fixture, or reproducible validation command unless the plan explicitly justifies
the gap.

- [ ] T005 [P] Add unit test for [library behavior] in [target test path]
- [ ] T006 [P] Add parity test comparing against [legacy source/config] in [target parity test path]
- [ ] T007 [P] Add fixture/config provenance notes in [fixture README or quickstart]
- [ ] T008 Define acceptable tolerance for [numeric/stochastic behavior] in [test or documentation path]

**Checkpoint**: Validation exists and should fail before implementation when practical.

---

## Phase 3: User Story 1 - [Title] (Priority: P1)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 1

- [ ] T009 [US1] Implement [public API/internal module] in [target package path]
- [ ] T010 [US1] Isolate optional dependency [dependency] behind [adapter/extra/module path]
- [ ] T011 [US1] Port only the selected behavior from [legacy source path], avoiding wholesale file copying
- [ ] T012 [US1] Add validation/error handling for [inputs, units, configs, solver availability]
- [ ] T013 [US1] Update quickstart usage for this story in `specs/[###-feature]/quickstart.md`

**Checkpoint**: User Story 1 is functional and testable independently.

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 2

- [ ] T014 [US2] Implement [public API/internal module] in [target package path]
- [ ] T015 [US2] Add or update fixtures/configs in [target fixture path]
- [ ] T016 [US2] Integrate with User Story 1 APIs without importing from `legacy/*`
- [ ] T017 [US2] Update documentation and validation commands

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 3

- [ ] T018 [US3] Implement [public API/internal module] in [target package path]
- [ ] T019 [US3] Add tests or reproducible validation for [behavior]
- [ ] T020 [US3] Update docs or examples for [workflow/API]

**Checkpoint**: All selected user stories are independently functional.

---

## Phase N: Polish and Cross-Cutting Concerns

**Purpose**: Final checks that affect multiple stories.

- [ ] TXXX [P] Update README or library documentation if public behavior changed
- [ ] TXXX [P] Remove accidental imports from `legacy/*` in target library code
- [ ] TXXX Review dependency boundaries and optional imports
- [ ] TXXX Run applicable quickstart commands
- [ ] TXXX Run applicable tests: [exact commands from plan.md]
- [ ] TXXX Document any checks not run and why

---

## Dependency Rules

- Setup tasks precede tests and implementation.
- Tests/parity fixtures precede migration implementation when practical.
- User stories can proceed in priority order or in parallel only if they touch
  different files and do not depend on unfinished APIs.
- Legacy edits require an explicit task and justification from plan.md.

## Validation Command Examples

Use only commands that apply to the feature:

```bash
cd legacy/old_tpm && cargo test
cd legacy/old_tpm && python scripts/test_battery_consistency.py
cd legacy/old_tpm && pytest src_py/tpm/spn/test_tangent_lower_bound.py
cd legacy/old_tpm && ./scripts/test_data_validation.sh --test-type automatic
```

## Notes

- [P] tasks must be safe to run in parallel.
- Every task should name exact files or directories.
- Avoid vague migration tasks such as "port simulator"; specify the exact
  behavior, source path, target path, and validation evidence.
- Do not add new product code to `legacy/*` unless the feature explicitly
  authorizes a legacy maintenance change.
