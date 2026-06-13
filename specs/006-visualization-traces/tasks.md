# Tasks: Visualization And Trace Inspection MVP

**Input**: Design documents from `/specs/006-visualization-traces/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The feature requires focused unit, integration, fixture-validation,
import-boundary, and deterministic regression checks because the spec calls
for stable inspection/reporting behavior, experimental plotting isolation,
same-family comparison guarantees, and persisted-output reuse without
re-simulation.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Path Conventions

- **Spec Kit**: `.specify/`, `.agents/`
- **Legacy references**: `legacy/old_tpm/`, `legacy/fed_trpo/`
- **Target library**: `src/open_energy_lab/visualization`, `src/open_energy_lab/simulator`, `src/open_energy_lab/core`
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/parity/`, `tests/fixtures/`

## Phase 1: Setup

**Purpose**: Establish feature-specific visualization scaffolding, fixtures,
and migration-note placeholders without expanding legacy code.

- [X] T001 Create visualization test package scaffolds in `tests/unit/visualization/__init__.py` and `tests/integration/visualization/__init__.py`
- [X] T002 [P] Create visualization fixture scaffolds in `tests/fixtures/visualization/inspection_arbitrage_case.json`, `tests/fixtures/visualization/inspection_battery_load_pv_case.json`, `tests/fixtures/visualization/comparison_arbitrage_case.json`, and `tests/fixtures/visualization/persisted_arbitrage_case.json`
- [X] T003 [P] Add visualization fixture provenance placeholders in `tests/fixtures/visualization/README.md`
- [X] T004 [P] Create the visualization migration note scaffold in `docs/migration/visualization-traces.md`

---

## Phase 2: Foundational

**Purpose**: Add shared package scaffolding and validation infrastructure that
blocks all user story work.

- [X] T005 [P] Add visualization package import-boundary coverage in `tests/unit/visualization/test_import_boundary.py`
- [X] T006 [P] Add visualization runtime no-legacy-import coverage in `tests/unit/visualization/test_no_legacy_imports.py`
- [X] T007 [P] Add visualization fixture loading helpers in `tests/integration/visualization/fixture_utils.py`
- [X] T008 [P] Add fixture-schema and provenance validation for visualization fixtures in `tests/integration/visualization/test_fixture_schema.py`
- [X] T009 [P] Add package-surface maturity coverage for stable inspection exports and experimental plotting exports in `tests/unit/visualization/test_package_surface.py`
- [X] T010 Create visualization package scaffolding and export placeholders in `src/open_energy_lab/visualization/__init__.py`, `src/open_energy_lab/visualization/inspection.py`, `src/open_energy_lab/visualization/comparison.py`, `src/open_energy_lab/visualization/plotting.py`, and `src/open_energy_lab/visualization/_persistence.py`
- [X] T011 [P] Add visualization API-maturity and dependency-boundary placeholders in `docs/migration/api-maturity.md`, `docs/migration/dependency-policy.md`, and `docs/migration/visualization-traces.md`
- [X] T012 [P] Add persisted-output schema validation coverage for supported visualization inputs in `tests/unit/visualization/test_persistence_schema.py`
- [X] T013 Define the supported persisted-output normalization and validation rules in `src/open_energy_lab/visualization/_persistence.py`

**Checkpoint**: Shared visualization scaffolding, fixture utilities, and
boundary validation are in place.

---

## Phase 3: User Story 1 - Inspect A Single Deterministic Run (Priority: P1)

**Goal**: Let a library consumer inspect supported deterministic runs through
one stable surface and generate basic static single-run plots from existing
in-memory or persisted outputs without rerunning simulation.

**Independent Test**: A deterministic arbitrage run and a controller-driven
arbitrage result can be transformed into the same stable inspection surface,
loaded again from a supported persisted output, and rendered through the
optional plotting layer without direct simulator traversal or re-simulation.

### Tests for User Story 1

- [X] T014 [P] [US1] Add stable inspection-view unit coverage for series ordering, summary extraction, and explicit availability markers in `tests/unit/visualization/test_inspection.py`
- [X] T015 [P] [US1] Add arbitrage inspection integration coverage for simulator and controller-driven outputs in `tests/integration/visualization/test_inspection_arbitrage.py`
- [X] T016 [P] [US1] Add persisted-output loading coverage for stable inspection reuse in `tests/integration/visualization/test_persisted_outputs.py`
- [X] T017 [P] [US1] Add experimental static-plot integration coverage proving no-resimulation behavior in `tests/integration/visualization/test_plotting.py`

### Implementation for User Story 1

- [X] T018 [US1] Implement stable inspection-view builders and summary extraction in `src/open_energy_lab/visualization/inspection.py`
- [X] T019 [US1] Implement persisted-output loading helpers for supported arbitrage results in `src/open_energy_lab/visualization/_persistence.py`
- [X] T020 [US1] Implement experimental static single-run plotting helpers over inspection views in `src/open_energy_lab/visualization/plotting.py`
- [X] T021 [US1] Export stable inspection/reporting helpers and keep plotting behind experimental imports in `src/open_energy_lab/visualization/__init__.py`
- [X] T022 [US1] Populate arbitrage and persisted-output fixtures, including provenance notes, in `tests/fixtures/visualization/inspection_arbitrage_case.json`, `tests/fixtures/visualization/persisted_arbitrage_case.json`, and `tests/fixtures/visualization/README.md`
- [X] T023 [US1] Document stable inspection usage, persisted-output reuse, and experimental plotting behavior in `docs/migration/visualization-traces.md`

**Checkpoint**: User Story 1 is functional and independently testable through
`tests/integration/visualization/test_inspection_arbitrage.py`,
`tests/integration/visualization/test_persisted_outputs.py`, and
`tests/integration/visualization/test_plotting.py`.

---

## Phase 4: User Story 2 - Inspect Weather-Aware PV Runs (Priority: P2)

**Goal**: Extend the stable inspection surface so battery + load + PV runs
show load, PV, net-grid, and simulator-exposed weather context in one
deterministic review flow.

**Independent Test**: A deterministic `BatteryLoadPVScenario` result can be
inspected through the stable visualization surface and exposes load, PV,
net-grid, settlement, and only the weather fields already exposed by the
simulator for that scenario family.

### Tests for User Story 2

- [X] T024 [P] [US2] Add weather-aware inspection unit coverage for present-versus-absent optional sections in `tests/unit/visualization/test_weather_reporting.py`
- [X] T025 [P] [US2] Add battery-load-PV inspection integration coverage in `tests/integration/visualization/test_inspection_battery_load_pv.py`
- [X] T026 [P] [US2] Add regression coverage proving unsupported runs do not invent weather sections in `tests/integration/visualization/test_inspection_availability.py`
- [X] T027 [P] [US2] Add persisted-output inspection coverage for supported battery-load-PV results in `tests/integration/visualization/test_persisted_outputs.py`
- [X] T028 [P] [US2] Add static-plot integration coverage for battery-load-PV and simulator-exposed weather traces in `tests/integration/visualization/test_plotting_battery_load_pv.py`

### Implementation for User Story 2

- [X] T029 [US2] Extend inspection-view builders for load, PV, net-grid, and simulator-exposed weather series in `src/open_energy_lab/visualization/inspection.py`
- [X] T030 [US2] Populate battery-load-PV visualization fixture coverage in `tests/fixtures/visualization/inspection_battery_load_pv_case.json` and `tests/fixtures/visualization/persisted_battery_load_pv_case.json`
- [ ] T031 [US2] Extend experimental plotting helpers for supported battery-load-PV and weather-backed single-run traces in `src/open_energy_lab/visualization/plotting.py`
- [ ] T032 [US2] Document weather-aware inspection scope, persisted-output support, and no-weather fallback behavior in `docs/migration/visualization-traces.md`

**Checkpoint**: User Story 2 is functional and independently testable through
`tests/integration/visualization/test_inspection_battery_load_pv.py`.

---

## Phase 5: User Story 3 - Compare Deterministic Runs Side By Side (Priority: P2)

**Goal**: Add deterministic same-scenario-family comparison so maintainers can
review trace-level and summary-level differences without hand-built scripts.

**Independent Test**: Two arbitrage runs from the same scenario family can be
compared through one canonical comparison surface, while a cross-family
comparison request is rejected deterministically.

### Tests for User Story 3

- [ ] T033 [P] [US3] Add same-family comparison unit coverage for aligned series and summary deltas in `tests/unit/visualization/test_comparison.py`
- [ ] T034 [P] [US3] Add integration coverage for supported same-family comparison and unsupported cross-family requests in `tests/integration/visualization/test_comparison.py`
- [ ] T035 [P] [US3] Add regression coverage for missing-series and incompatible-length comparison failures in `tests/integration/visualization/test_comparison_failures.py`

### Implementation for User Story 3

- [ ] T036 [US3] Implement same-family comparison views and deterministic unsupported-case handling in `src/open_energy_lab/visualization/comparison.py`
- [ ] T037 [US3] Populate same-family comparison fixture coverage in `tests/fixtures/visualization/comparison_arbitrage_case.json`
- [ ] T038 [US3] Document comparison scope, unsupported cross-family behavior, and deferred comparison plots in `docs/migration/visualization-traces.md`

**Checkpoint**: User Story 3 is functional and independently testable through
`tests/integration/visualization/test_comparison.py`.

---

## Phase 6: User Story 4 - Preserve A Lightweight Inspection Boundary (Priority: P3)

**Goal**: Keep the stable visualization package import-light, free of runtime
`legacy/*` imports, and explicit about the stable-versus-experimental maturity
split.

**Independent Test**: Base `open_energy_lab.visualization` imports succeed in
the minimal local environment without optional plotting dependencies, runtime
legacy imports, notebooks, or external services, while experimental plotting
remains isolated.

### Tests for User Story 4

- [ ] T039 [P] [US4] Extend root optional dependency boundary coverage for visualization imports in `tests/unit/test_optional_dependency_boundaries.py`
- [ ] T040 [P] [US4] Add root import-contract coverage for stable visualization exports in `tests/unit/test_import_contract.py`
- [ ] T041 [P] [US4] Add direct import smoke coverage separating base visualization imports from experimental plotting imports in `tests/unit/visualization/test_optional_plotting_imports.py`

### Implementation for User Story 4

- [ ] T042 [US4] Refine package-root visualization imports and experimental plotting gating in `src/open_energy_lab/visualization/__init__.py`
- [ ] T043 [US4] Update migration documentation for stable inspection/reporting and experimental plotting maturity in `docs/migration/api-maturity.md` and `docs/migration/visualization-traces.md`
- [ ] T044 [US4] Update dependency-boundary guidance for optional plotting support in `docs/migration/dependency-policy.md` and `docs/migration/README.md`

**Checkpoint**: User Story 4 is functional and independently testable through
the import-boundary and import-smoke suites.

---

## Phase 7: Polish and Cross-Cutting Concerns

**Purpose**: Finalize quickstart validation guidance, fixture provenance, and
cross-story documentation.

- [ ] T045 [P] Update visualization fixture provenance details and refresh guidance in `tests/fixtures/visualization/README.md`
- [ ] T046 [P] Update review and validation commands in `specs/006-visualization-traces/quickstart.md`
- [ ] T047 [P] Update migration overview references for the visualization feature in `docs/migration/README.md`
- [ ] T048 Run the validation commands documented in `specs/006-visualization-traces/quickstart.md`: `uv run pytest tests/unit/visualization tests/integration/visualization`, `uv run pytest tests/unit/simulator tests/integration/simulator`, `uv run python -c "import open_energy_lab.visualization; import open_energy_lab.simulator; import open_energy_lab.core"`, and `rg "from legacy|import legacy" src/open_energy_lab/visualization tests/unit/visualization tests/integration/visualization docs/migration`
- [ ] T049 Document final validation outcomes and any skipped optional-backend checks in `specs/006-visualization-traces/quickstart.md`

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story implementation begins.
- US1 is the MVP and must complete before US2 and US3 because it establishes
  the stable inspection surface and persisted-output handling that both later
  stories consume.
- US2 and US3 can proceed in parallel after US1 if they do not overwrite the
  same in-progress inspection APIs.
- US4 depends on the completion of US1 and should land after US2 and US3 so
  the final import and maturity boundary reflects the full feature surface.
- Phase 7 depends on the completion of the selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 -> {US2, US3} -> US4 -> Polish
```

## Parallel Execution Examples

### Setup

```text
T002 tests/fixtures/visualization/inspection_arbitrage_case.json
T003 tests/fixtures/visualization/README.md
T004 docs/migration/visualization-traces.md
```

### Foundational

```text
T005 tests/unit/visualization/test_import_boundary.py
T006 tests/unit/visualization/test_no_legacy_imports.py
T007 tests/integration/visualization/fixture_utils.py
T008 tests/integration/visualization/test_fixture_schema.py
T009 tests/unit/visualization/test_package_surface.py
T011 docs/migration/api-maturity.md
```

### User Story 1

```text
T012 tests/unit/visualization/test_inspection.py
T013 tests/integration/visualization/test_inspection_arbitrage.py
T014 tests/integration/visualization/test_persisted_outputs.py
T015 tests/integration/visualization/test_plotting.py
```

### User Story 2

```text
T022 tests/unit/visualization/test_weather_reporting.py
T023 tests/integration/visualization/test_inspection_battery_load_pv.py
T024 tests/integration/visualization/test_inspection_availability.py
```

### User Story 3

```text
T028 tests/unit/visualization/test_comparison.py
T029 tests/integration/visualization/test_comparison.py
T030 tests/integration/visualization/test_comparison_failures.py
```

### User Story 4

```text
T034 tests/unit/test_optional_dependency_boundaries.py
T035 tests/unit/test_import_contract.py
T036 tests/unit/visualization/test_optional_plotting_imports.py
```

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Deliver US1 to establish the stable inspection/reporting surface plus the
   experimental no-resimulation plotting path.
3. Validate `tests/integration/visualization/test_inspection_arbitrage.py`,
   `tests/integration/visualization/test_persisted_outputs.py`, and
   `tests/integration/visualization/test_plotting.py` before expanding scope.

### Incremental Delivery

1. Add US2 to cover weather-aware battery + load + PV inspection.
2. Add US3 to introduce same-family comparison and explicit unsupported
   cross-family behavior.
3. Add US4 to harden the final import boundary and public maturity split.

### Final Verification

1. Run the validation commands listed in
   `specs/006-visualization-traces/quickstart.md`.
2. Update migration and dependency documentation with final outcomes and any
   skipped optional-backend checks.
3. Keep all new product code out of `legacy/*`.

## Notes

- [P] tasks are safe to run in parallel because they touch different files and
  do not depend on unfinished tasks.
- Every task names an exact file path so an implementation agent can execute
  it without more context.
- The visualization package consumes supported current-library outputs rather
  than widening simulator or controller execution ownership.
- Optional plotting remains experimental and must never become a hidden
  re-simulation path.
