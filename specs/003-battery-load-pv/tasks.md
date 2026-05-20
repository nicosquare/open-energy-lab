# Tasks: Deterministic Battery Load PV Scenario MVP

**Input**: Design documents from `/specs/003-battery-load-pv/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks are included because this feature explicitly requires deterministic validation, energy-balance and settlement invariants, weather-to-PV evidence, lightweight-import guarantees, and migration evidence tied to selected legacy behavior.

**Organization**: Tasks are grouped by user story so each story can be implemented and reviewed independently. No task adds planning, MPC, RL, CityLearn runtime, notebook, W&B, GPU/SLURM, solver, broad weather-subsystem migration, real weather ingestion, or Rust-bound behavior to the simulator core.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Establish feature-specific fixture, provenance, and migration-note scaffolding before simulator implementation starts.

- [X] T001 Create deterministic fixture shell in `tests/fixtures/simulator/battery_load_pv_case.json`
- [X] T002 [P] Create feature migration note in `docs/migration/battery-load-pv-mvp.md` naming the exact legacy reference files plus the intended preserved/improved/rejected scope
- [X] T003 [P] Update `tests/fixtures/simulator/README.md` with provenance requirements for `tests/fixtures/simulator/battery_load_pv_case.json`
- [X] T004 [P] Update `tests/fixtures/README.md` to register `tests/fixtures/simulator/battery_load_pv_case.json` and the human-readable weather-field plus TMY-label mapping expectation

---

## Phase 2: Foundational

**Purpose**: Add shared weather-schema guardrails, graph support, and migration-note checks before story-specific behavior lands.

**Critical**: These tasks must complete before user-story implementation because they define the shared weather-field vocabulary, component relationship support, import expectations, and migration-note checks used across the feature.

- [X] T005 Create shared weather field metadata and TMY-label mapping helpers in `src/open_energy_lab/simulator/_weather_schema.py`
- [X] T006 Extend internal component-graph relation coverage for load, weather, PV, net-grid, and settlement links in `src/open_energy_lab/simulator/_graph.py`
- [X] T007 [P] Add weather schema contract tests in `tests/unit/simulator/test_weather_schema.py` covering human-readable field names, canonical TMY source labels, and deferred standard weather fields
- [X] T008 [P] Add migration-note documentation test in `tests/unit/simulator/test_battery_load_pv_migration_notes.py` checking `docs/migration/battery-load-pv-mvp.md` contains exact legacy files plus preserved/improved/rejected behavior
- [X] T009 [P] Update `tests/unit/simulator/test_import_boundary.py` to reserve the import-light module boundary for `open_energy_lab.simulator.load`, `open_energy_lab.simulator.weather`, and `open_energy_lab.simulator.pv`

**Checkpoint**: Shared weather-schema conventions, graph support, and migration-note guardrails exist before scenario-specific work begins.

---

## Phase 3: User Story 1 - Assemble a Multi-Component Scenario (Priority: P1)

**Goal**: Provide a typed, component-graph simulator surface for battery, load, weather, PV, pricing, and grid accounting without broadening the simulator-core dependency boundary.

**Independent Test**: `uv run pytest tests/unit/simulator/test_weather_schema.py tests/unit/simulator/test_load.py tests/unit/simulator/test_weather.py tests/unit/simulator/test_pv.py tests/unit/simulator/test_multi_component_scenario.py`

### Tests for User Story 1

- [X] T010 [P] [US1] Add deterministic load component tests in `tests/unit/simulator/test_load.py`
- [X] T011 [P] [US1] Add weather component tests in `tests/unit/simulator/test_weather.py` covering human-readable field names, TMY label mappings, required weather subset handling, and deferred-field behavior
- [X] T012 [P] [US1] Add PV component tests in `tests/unit/simulator/test_pv.py` covering weather-driven generation inputs, irradiance selection, and deterministic PV derivation behavior
- [X] T013 [P] [US1] Add multi-component scenario assembly tests in `tests/unit/simulator/test_multi_component_scenario.py` covering aligned series validation, explicit graph shape, and mutually exclusive dispatch-versus-policy inputs

### Implementation for User Story 1

- [X] T014 [US1] Implement deterministic load profile types in `src/open_energy_lab/simulator/load.py`
- [X] T015 [US1] Implement weather component types with human-readable field names and TMY label-mapping behavior in `src/open_energy_lab/simulator/weather.py`
- [X] T016 [US1] Implement PV component types and deterministic weather-driven generation helpers in `src/open_energy_lab/simulator/pv.py`
- [X] T017 [US1] Extend `src/open_energy_lab/simulator/scenario.py` with battery + load + weather + PV assembly and explicit component-graph wiring
- [X] T018 [US1] Update `src/open_energy_lab/simulator/__init__.py` to export the new experimental multi-component surfaces from the stable `open_energy_lab.simulator` package boundary
- [X] T019 [US1] Update `docs/migration/battery-load-pv-mvp.md` and `specs/003-battery-load-pv/quickstart.md` with implemented assembly semantics, weather-field mappings, and explicit multi-component scope boundaries

**Checkpoint**: User Story 1 is complete when a reviewer can assemble a typed battery + load + PV scenario with explicit component links and inspect the intended boundary without broader simulator subsystems.

---

## Phase 4: User Story 2 - Validate Net-Grid Energy Balance and Settlement (Priority: P2)

**Goal**: Implement deterministic multi-component trace evaluation, weather-driven PV output, one-net grid accounting, and discounted settlement backed by small reproducible fixtures and invariant checks.

**Independent Test**: `uv run pytest tests/unit/simulator/test_grid_settlement.py tests/integration/simulator/test_battery_load_pv_trace.py`

### Tests for User Story 2

- [X] T020 [P] [US2] Add net-grid settlement tests in `tests/unit/simulator/test_grid_settlement.py` covering one-net import/export behavior, discounted export settlement, and per-step versus total settlement sums
- [X] T021 [P] [US2] Add deterministic integration trace tests in `tests/integration/simulator/test_battery_load_pv_trace.py` covering explicit-dispatch and `price_threshold` execution paths against the shared fixture

### Implementation for User Story 2

- [X] T022 [US2] Extend `src/open_energy_lab/simulator/objective.py` with net-grid settlement helpers for battery + load + PV traces
- [X] T023 [US2] Extend `src/open_energy_lab/simulator/scenario.py` with deterministic trace evaluation that derives PV generation, net-grid traces, and settlement from explicit dispatch or `price_threshold` requests
- [X] T024 [US2] Finalize deterministic fixture contents in `tests/fixtures/simulator/battery_load_pv_case.json`
- [X] T025 [US2] Update `tests/fixtures/simulator/README.md` and `docs/migration/battery-load-pv-mvp.md` with fixture provenance, exact legacy evidence, energy-balance invariants, and `1e-6` tolerance rationale

**Checkpoint**: User Story 2 is complete when the simulator produces deterministic battery + load + PV traces and one-net settlement outcomes that can be checked from a small committed fixture without solver or external-data dependencies.

---

## Phase 5: User Story 3 - Preserve a Lightweight Simulator Core (Priority: P3)

**Goal**: Ensure `open_energy_lab.simulator` and the new load/weather/PV modules remain importable without heavy research stacks or `legacy/*` imports while documenting the final core-versus-optional boundary.

**Independent Test**: `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/simulator/test_import_boundary.py tests/unit/simulator/test_no_legacy_imports.py && uv run python -c "import open_energy_lab.simulator"`

### Tests for User Story 3

- [X] T026 [P] [US3] Extend optional dependency boundary coverage in `tests/unit/test_optional_dependency_boundaries.py` to verify `import open_energy_lab.simulator`, `open_energy_lab.simulator.weather`, and `open_energy_lab.simulator.pv` do not load heavy optional stacks
- [X] T027 [P] [US3] Extend simulator legacy-isolation coverage in `tests/unit/simulator/test_no_legacy_imports.py` for `src/open_energy_lab/simulator/load.py`, `src/open_energy_lab/simulator/weather.py`, `src/open_energy_lab/simulator/pv.py`, and the extended `src/open_energy_lab/simulator/scenario.py`

### Implementation for User Story 3

- [ ] T028 [US3] Audit and tighten imports plus `TYPE_CHECKING` boundaries in `src/open_energy_lab/simulator/__init__.py`, `src/open_energy_lab/simulator/load.py`, `src/open_energy_lab/simulator/weather.py`, `src/open_energy_lab/simulator/pv.py`, `src/open_energy_lab/simulator/scenario.py`, and `src/open_energy_lab/simulator/objective.py`
- [ ] T029 [US3] Update `docs/migration/battery-load-pv-mvp.md` and `specs/003-battery-load-pv/quickstart.md` with the final dependency classification, experimental API boundary, and deferred weather-field scope

**Checkpoint**: User Story 3 is complete when the simulator package imports cleanly in the foundation environment and its boundary against heavy research stacks and `legacy/*` is test-backed and documented.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Run the feature-level validation commands and finalize parity and quickstart notes that cut across stories.

- [ ] T030 [P] Update `tests/parity/README.md` with the battery load PV MVP parity stance, the exact weather/PV evidence sources, and why targeted invariants replace a broad end-to-end parity suite
- [ ] T031 Run `uv run pytest tests/unit/simulator tests/integration/simulator tests/unit/test_optional_dependency_boundaries.py`
- [ ] T032 Run `uv run python -c "import open_energy_lab.simulator"` from the repository root
- [ ] T033 Run `rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit/simulator tests/integration/simulator`
- [ ] T034 Run `cd legacy/old_tpm && python scripts/test_battery_consistency.py` if local prerequisites allow it, otherwise document the skip in `specs/003-battery-load-pv/quickstart.md`
- [ ] T035 Update `specs/003-battery-load-pv/quickstart.md` with final validation commands, the legacy-check outcome or skip reason, and any intentionally omitted checks

---

## Dependencies

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story.
- User Story 1 is the MVP and should complete before User Stories 2 and 3 because it establishes the load, weather, PV, scenario, and package-export surfaces.
- User Story 2 depends on the shared helpers from Phase 2 and the multi-component scenario surface from User Story 1.
- User Story 3 depends on the implemented simulator modules from User Stories 1 and 2 because import-boundary and legacy-isolation checks must evaluate the final code paths.
- Phase 6 runs after all selected user stories are complete.

### User Story Dependencies

- **US1**: Depends on Phase 1 and Phase 2 only.
- **US2**: Depends on US1 scenario, weather, and PV surfaces plus Phase 2 shared helpers.
- **US3**: Depends on US1 and US2 implemented simulator modules.

---

## Parallel Execution Examples

### User Story 1

After Phase 2, these can run together:

```text
T010 tests in tests/unit/simulator/test_load.py
T011 tests in tests/unit/simulator/test_weather.py
T012 tests in tests/unit/simulator/test_pv.py
T013 tests in tests/unit/simulator/test_multi_component_scenario.py
```

### User Story 2

After US1 establishes the multi-component scenario surface, these can run together:

```text
T020 tests in tests/unit/simulator/test_grid_settlement.py
T021 tests in tests/integration/simulator/test_battery_load_pv_trace.py
```

### User Story 3

After US2 completes the simulator modules, these can run together:

```text
T026 extend tests/unit/test_optional_dependency_boundaries.py
T027 extend tests/unit/simulator/test_no_legacy_imports.py
```

---

## Implementation Strategy

### MVP First

Complete Phases 1 and 2, then deliver User Story 1. This yields the first
reviewable multi-component simulator surface: load, weather, PV, component
relationships, and the extended scenario assembly boundary.

### Incremental Delivery

1. Deliver US1 and verify assembly behavior with `uv run pytest tests/unit/simulator/test_weather_schema.py tests/unit/simulator/test_load.py tests/unit/simulator/test_weather.py tests/unit/simulator/test_pv.py tests/unit/simulator/test_multi_component_scenario.py`.
2. Deliver US2 and verify deterministic balance and settlement with `uv run pytest tests/unit/simulator/test_grid_settlement.py tests/integration/simulator/test_battery_load_pv_trace.py`.
3. Deliver US3 and verify lightweight imports with `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/simulator/test_import_boundary.py tests/unit/simulator/test_no_legacy_imports.py`.
4. Run Phase 6 commands for the full feature validation pass.

### Scope Guard

If any task appears to require CityLearn runtime integration, broad weather
subsystem migration, real weather ingestion, solver-backed optimization,
MPC/RL control, notebooks, W&B, GPU/SLURM tooling, Rust bindings, or broad
legacy simulator copying into `src/open_energy_lab`, stop and create a later
migration spec instead.
