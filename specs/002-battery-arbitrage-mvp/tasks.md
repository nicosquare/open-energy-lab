# Tasks: Battery Arbitrage Simulator MVP

**Input**: Design documents from `/specs/002-battery-arbitrage-mvp/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks are included because this feature explicitly requires deterministic validation, tolerance-backed evidence, lightweight-import guarantees, and migration evidence tied to selected legacy behavior.

**Organization**: Tasks are grouped by user story so each story can be implemented and reviewed independently. No task adds planning, control, RL, notebooks, W&B, GPU/SLURM, solver, CityLearn-runtime, weather migration, Rust bindings, or broad legacy simulator behavior to the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Establish feature-specific directories, fixture locations, and migration notes before simulator implementation starts.

- [X] T001 Create simulator marker READMEs in `tests/unit/simulator/README.md`, `tests/integration/simulator/README.md`, and `tests/fixtures/simulator/README.md`
- [X] T002 [P] Create deterministic fixture shell in `tests/fixtures/simulator/battery_arbitrage_case.json`
- [X] T003 [P] Create feature migration note in `docs/migration/battery-arbitrage-mvp.md` naming the exact legacy reference files and the intended preserved/improved/rejected scope
- [X] T004 [P] Update `tests/fixtures/README.md` to register `tests/fixtures/simulator/` and the provenance requirements for `tests/fixtures/simulator/battery_arbitrage_case.json`

---

## Phase 2: Foundational

**Purpose**: Add shared simulator internals and cross-story guardrails before story-specific behavior lands.

**Critical**: These tasks must complete before user-story implementation because they define common units, graph structure, import expectations, and migration-note checks used by the whole MVP.

- [X] T005 Create shared unit, sign-convention, and default-tolerance helpers in `src/open_energy_lab/simulator/_units.py`
- [X] T006 Create internal component-graph primitives in `src/open_energy_lab/simulator/_graph.py`
- [X] T007 Update `src/open_energy_lab/simulator/__init__.py` to keep the package import-light and mark concrete arbitrage surfaces as experimental under the stable `open_energy_lab.simulator` location
- [X] T008 [P] Add simulator import-boundary smoke test in `tests/unit/simulator/test_import_boundary.py`
- [X] T009 [P] Add migration-note documentation test in `tests/unit/simulator/test_migration_notes.py` checking `docs/migration/battery-arbitrage-mvp.md` contains exact legacy files plus preserved/improved/rejected behavior

**Checkpoint**: Shared simulator conventions and migration-note guardrails exist before scenario-specific work begins.

---

## Phase 3: User Story 1 - Assemble a Minimal Arbitrage Scenario (Priority: P1)

**Goal**: Provide a typed, component-graph battery arbitrage scenario surface with explicit time-grid, price-signal, dispatch/policy, and assembly validation behavior.

**Independent Test**: `uv run pytest tests/unit/simulator/test_scenario.py tests/unit/simulator/test_pricing.py` verifies scenario assembly, time-grid validation, discounted export price semantics, and the built-in `price_threshold` policy without needing battery trace execution.

### Tests for User Story 1

- [X] T010 [P] [US1] Add scenario assembly tests in `tests/unit/simulator/test_scenario.py` covering time-grid validation, required components, and mutually exclusive dispatch-versus-policy inputs
- [X] T011 [P] [US1] Add pricing and deterministic policy tests in `tests/unit/simulator/test_pricing.py` covering step-start import prices, discounted export ratio, and `price_threshold` charge/hold/discharge behavior

### Implementation for User Story 1

- [X] T012 [US1] Implement import/export price signal and `price_threshold` policy types in `src/open_energy_lab/simulator/pricing.py`
- [X] T013 [US1] Implement scenario entities, assembly validation, and component-graph composition in `src/open_energy_lab/simulator/scenario.py`
- [X] T014 [US1] Update `src/open_energy_lab/simulator/__init__.py` to export scenario and pricing surfaces at the stable package location while keeping concrete arbitrage types experimental
- [X] T015 [US1] Update `docs/migration/battery-arbitrage-mvp.md` with implemented scenario-assembly semantics, exact legacy references, and explicit planning/control non-goals
- [X] T016 [US1] Update `specs/002-battery-arbitrage-mvp/quickstart.md` with scenario-assembly usage and the `uv run pytest tests/unit/simulator/test_scenario.py tests/unit/simulator/test_pricing.py` command

**Checkpoint**: User Story 1 is complete when a reviewer can assemble a typed arbitrage scenario with either explicit dispatch requests or the built-in deterministic policy and inspect the intended boundary without broader simulator subsystems.

---

## Phase 4: User Story 2 - Validate Deterministic Battery Arbitrage Behavior (Priority: P2)

**Goal**: Implement battery physics, discounted-export settlement, and deterministic trace evaluation backed by a small reproducible fixture and tolerance-aware tests.

**Independent Test**: `uv run pytest tests/unit/simulator/test_battery.py tests/unit/simulator/test_objective.py tests/integration/simulator/test_battery_arbitrage_trace.py` verifies battery constraints, discounted-export settlement, explicit-dispatch traces, and `price_threshold` traces against deterministic expectations.

### Tests for User Story 2

- [X] T017 [P] [US2] Add battery state-transition tests in `tests/unit/simulator/test_battery.py` covering power limits, capacity limits, efficiencies, and `1e-6` tolerance behavior
- [X] T018 [P] [US2] Add settlement tests in `tests/unit/simulator/test_objective.py` covering discounted export accounting and per-step versus total settlement sums
- [X] T019 [P] [US2] Add deterministic integration trace tests in `tests/integration/simulator/test_battery_arbitrage_trace.py` covering explicit-dispatch and `price_threshold` evaluation paths against the shared fixture

### Implementation for User Story 2

- [X] T020 [P] [US2] Implement battery component and state-transition logic in `src/open_energy_lab/simulator/battery.py`
- [X] T021 [P] [US2] Implement discounted-export settlement logic in `src/open_energy_lab/simulator/objective.py`
- [X] T022 [US2] Extend `src/open_energy_lab/simulator/scenario.py` with feasible trace evaluation for explicit dispatch requests and the built-in `price_threshold` policy
- [X] T023 [US2] Finalize deterministic fixture contents in `tests/fixtures/simulator/battery_arbitrage_case.json`
- [X] T024 [US2] Update `tests/fixtures/simulator/README.md` and `docs/migration/battery-arbitrage-mvp.md` with fixture provenance, exact legacy evidence, deterministic invariants, and `1e-6` tolerance rationale

**Checkpoint**: User Story 2 is complete when the simulator produces deterministic battery traces and discounted-export settlement outcomes that can be checked from a small committed fixture without solver or external-data dependencies.

---

## Phase 5: User Story 3 - Preserve a Lightweight Simulator Core (Priority: P3)

**Goal**: Ensure `open_energy_lab.simulator` remains importable without heavy research stacks or `legacy/*` imports while documenting the final core-versus-optional boundary.

**Independent Test**: `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/simulator/test_import_boundary.py tests/unit/simulator/test_no_legacy_imports.py && uv run python -c "import open_energy_lab.simulator"` verifies that simulator-core imports stay lightweight and isolated from `legacy/*`.

### Tests for User Story 3

- [X] T025 [P] [US3] Extend optional dependency boundary coverage in `tests/unit/test_optional_dependency_boundaries.py` to verify `import open_energy_lab.simulator` does not load heavy optional stacks such as `torch`, `torchrl`, `citylearn`, `pyomo`, `gurobipy`, `docplex`, or `wandb`
- [X] T026 [P] [US3] Add simulator legacy-isolation test in `tests/unit/simulator/test_no_legacy_imports.py` scanning `src/open_energy_lab/simulator` for imports from `legacy/*`

### Implementation for User Story 3

- [X] T027 [US3] Audit and tighten simulator imports and `__all__` definitions in `src/open_energy_lab/simulator/__init__.py`, `src/open_energy_lab/simulator/pricing.py`, `src/open_energy_lab/simulator/scenario.py`, `src/open_energy_lab/simulator/battery.py`, and `src/open_energy_lab/simulator/objective.py`
- [X] T028 [US3] Update `docs/migration/battery-arbitrage-mvp.md` and `specs/002-battery-arbitrage-mvp/quickstart.md` with the final dependency classification, stable-versus-experimental API boundary, and adapter non-goals

**Checkpoint**: User Story 3 is complete when the simulator package imports cleanly in the foundation environment and its boundary against heavy research stacks and `legacy/*` is test-backed and documented.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Run the feature-level validation commands and finalize parity/quickstart notes that cut across stories.

- [X] T029 [P] Update `tests/parity/README.md` with the battery arbitrage MVP parity stance, the exact legacy evidence files, and why targeted invariants replace a broad end-to-end parity suite
- [X] T030 Run `uv run pytest tests/unit/simulator tests/integration/simulator tests/unit/test_optional_dependency_boundaries.py`
- [X] T031 Run `uv run python -c "import open_energy_lab.simulator"` from the repository root
- [X] T032 Run `rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit/simulator tests/integration/simulator`
- [X] T033 Run `cd legacy/old_tpm && python scripts/test_battery_consistency.py` if local prerequisites allow it, otherwise document the skip in `specs/002-battery-arbitrage-mvp/quickstart.md`
- [X] T034 Update `specs/002-battery-arbitrage-mvp/quickstart.md` with final validation commands, the parity-check outcome or skip reason, and any intentionally omitted checks

---

## Dependencies

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story.
- User Story 1 is the MVP and should complete before User Stories 2 and 3 because it establishes the scenario, pricing, and package-export surfaces.
- User Story 2 depends on the shared helpers from Phase 2 and the scenario/pricing API from User Story 1.
- User Story 3 depends on the implemented simulator modules from User Stories 1 and 2 because import-boundary and legacy-isolation checks must evaluate the final code paths.
- Phase 6 runs after all selected user stories are complete.

### User Story Dependencies

- **US1**: Depends on Phase 1 and Phase 2 only.
- **US2**: Depends on US1 scenario/pricing surfaces plus Phase 2 shared helpers.
- **US3**: Depends on US1 and US2 implemented simulator modules.

---

## Parallel Execution Examples

### User Story 1

After Phase 2, these can run together:

```text
T010 tests in tests/unit/simulator/test_scenario.py
T011 tests in tests/unit/simulator/test_pricing.py
```

### User Story 2

After US1 establishes the scenario and pricing surfaces, these can run together:

```text
T017 tests in tests/unit/simulator/test_battery.py
T018 tests in tests/unit/simulator/test_objective.py
T019 tests in tests/integration/simulator/test_battery_arbitrage_trace.py
T020 battery implementation in src/open_energy_lab/simulator/battery.py
T021 settlement implementation in src/open_energy_lab/simulator/objective.py
```

### User Story 3

After US2 completes the simulator modules, these can run together:

```text
T025 extend tests/unit/test_optional_dependency_boundaries.py
T026 add tests/unit/simulator/test_no_legacy_imports.py
```

---

## Implementation Strategy

### MVP First

Complete Phases 1 and 2, then deliver User Story 1. This yields the first
reviewable simulator surface: time grid, price signal, discounted export
semantics, scenario assembly, and the optional built-in deterministic
`price_threshold` policy.

### Incremental Delivery

1. Deliver US1 and verify assembly behavior with `uv run pytest tests/unit/simulator/test_scenario.py tests/unit/simulator/test_pricing.py`.
2. Deliver US2 and verify deterministic battery traces with `uv run pytest tests/unit/simulator/test_battery.py tests/unit/simulator/test_objective.py tests/integration/simulator/test_battery_arbitrage_trace.py`.
3. Deliver US3 and verify lightweight imports with `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/simulator/test_import_boundary.py tests/unit/simulator/test_no_legacy_imports.py`.
4. Run Phase 6 commands for the full feature validation pass.

### Scope Guard

If any task appears to require solver-backed optimization, TorchRL, CityLearn,
weather migration, notebooks, W&B, GPU/SLURM tooling, Rust bindings, or broad
legacy simulator copying into `src/open_energy_lab`, stop and create a later
migration spec instead.
