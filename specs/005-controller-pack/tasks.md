# Tasks: Native Controller Pack

**Input**: Design documents from `/specs/005-controller-pack/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The feature requires focused unit, integration, fixture-validation,
import-boundary, and preserved-path regression checks because the spec calls
for deterministic validation, stable public API evidence, and explicit
lightweight dependency boundaries.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Path Conventions

- **Spec Kit**: `.specify/`, `.agents/`
- **Legacy references**: `legacy/old_tpm/`, `legacy/fed_trpo/`
- **Target library**: `src/open_energy_lab/control`, `src/open_energy_lab/core`, `src/open_energy_lab/simulator`
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/parity/`, `tests/fixtures/`

## Phase 1: Setup

**Purpose**: Establish feature-specific test, fixture, and migration-note
scaffolding without expanding legacy code.

- [X] T001 Create control test package scaffolds in `tests/unit/control/__init__.py` and `tests/integration/control/__init__.py`
- [X] T002 [P] Create deterministic controller fixture scaffolds in `tests/fixtures/simulator/price_threshold_controller_case.json`, `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json`, and `tests/fixtures/simulator/pv_self_consumption_case.json`
- [X] T003 [P] Add controller-pack fixture provenance placeholders in `tests/fixtures/simulator/README.md`
- [X] T004 [P] Create the controller-pack migration note scaffold in `docs/migration/controller-pack.md`

---

## Phase 2: Foundational

**Purpose**: Add shared package scaffolding and validation infrastructure that
blocks all user story work.

- [X] T005 [P] Add control package import-boundary coverage in `tests/unit/control/test_import_boundary.py`
- [X] T006 [P] Add typed controller configuration validation coverage in `tests/unit/control/test_configs.py`
- [X] T007 [P] Add controller support-matrix and unsupported-scenario coverage in `tests/unit/control/test_support_matrix.py`
- [X] T008 [P] Add controller-pack fixture loading helpers in `tests/integration/control/controller_fixture_utils.py`
- [X] T009 [P] Extend controller fixture schema validation for controller-pack artifacts, provenance fields, and legacy-reference fields in `tests/integration/simulator/test_controller_fixture_schema.py`
- [X] T010 Create shared control configuration helpers, shipped-controller support declarations, and package scaffolding in `src/open_energy_lab/control/_config.py` and `src/open_energy_lab/control/__init__.py`
- [X] T011 Create the initial preserve/improve/reject migration note content in `docs/migration/controller-pack.md`
- [X] T012 [P] Add shipped controller `ControllerInterface` conformance coverage in `tests/unit/control/test_controller_interface.py`

**Checkpoint**: Shared control package scaffolding, configuration validation,
support declarations, and fixture helpers are in place.

---

## Phase 3: User Story 1 - Run a Shipped Arbitrage Controller (Priority: P1)

**Goal**: Let a library consumer import, configure, and run a native
price-threshold controller for arbitrage through the public control package.

**Independent Test**: A deterministic arbitrage scenario evaluated twice with
the same `PriceThresholdController` configuration produces identical requested
dispatch, realized dispatch, and settlement totals through the package-root
control surface.

### Tests for User Story 1

- [X] T013 [P] [US1] Add price-threshold controller behavior tests in `tests/unit/control/test_price_threshold.py`
- [X] T014 [P] [US1] Add arbitrage integration coverage for the package-root price-threshold controller in `tests/integration/control/test_price_threshold_controller.py`
- [X] T015 [P] [US1] Extend deterministic arbitrage controller evaluation coverage for shipped controller fixtures in `tests/integration/simulator/test_controller_evaluation.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement `PriceThresholdConfig` in `src/open_energy_lab/control/_config.py`
- [X] T017 [US1] Implement `PriceThresholdController` in `src/open_energy_lab/control/price_threshold.py`
- [X] T018 [US1] Export `PriceThresholdConfig` and `PriceThresholdController` from `src/open_energy_lab/control/__init__.py`
- [ ] T019 [US1] Populate the deterministic arbitrage controller fixture, including provenance and legacy-reference fields, in `tests/fixtures/simulator/price_threshold_controller_case.json`
- [ ] T020 [US1] Document arbitrage controller behavior and usage in `docs/migration/controller-pack.md`

**Checkpoint**: User Story 1 is functional and independently testable through
`tests/integration/control/test_price_threshold_controller.py`.

---

## Phase 4: User Story 2 - Reuse Guardrail Logic Across Supported Scenarios (Priority: P2)

**Goal**: Ship native SOC guardrail and PV self-consumption controllers that
work through the stable controller contract on their supported scenario
families.

**Independent Test**: Scenario-level validation proves that the SOC guardrail
controller behaves deterministically on supported scenarios and the PV
self-consumption controller behaves deterministically on
`BatteryLoadPVScenario`, with unsupported-scenario use failing explicitly.

### Tests for User Story 2

- [ ] T021 [P] [US2] Add SOC guardrail controller unit behavior tests in `tests/unit/control/test_soc_guardrail.py`
- [ ] T022 [P] [US2] Add PV self-consumption controller unit behavior tests in `tests/unit/control/test_pv_self_consumption.py`
- [ ] T023 [P] [US2] Add scenario-support integration coverage for native controllers in `tests/integration/control/test_scenario_support.py`
- [ ] T024 [P] [US2] Extend simulator controller evaluation coverage for SOC guardrail and PV self-consumption controllers in `tests/integration/simulator/test_controller_evaluation.py`

### Implementation for User Story 2

- [ ] T025 [US2] Implement `SocGuardrailConfig` in `src/open_energy_lab/control/_config.py`
- [ ] T026 [US2] Implement `SocGuardrailController` in `src/open_energy_lab/control/soc_guardrail.py`
- [ ] T027 [US2] Implement `PVSelfConsumptionConfig` in `src/open_energy_lab/control/_config.py`
- [ ] T028 [US2] Implement `PVSelfConsumptionController` in `src/open_energy_lab/control/pv_self_consumption.py`
- [ ] T029 [US2] Export the guardrail and PV controller public surface from `src/open_energy_lab/control/__init__.py`
- [ ] T030 [US2] Populate guardrail and PV deterministic fixtures, including provenance and legacy-reference fields, in `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json` and `tests/fixtures/simulator/pv_self_consumption_case.json`
- [ ] T031 [US2] Update controller-pack support notes and fixture provenance in `tests/fixtures/simulator/README.md` and `docs/migration/controller-pack.md`

**Checkpoint**: User Story 2 is functional and independently testable through
`tests/integration/control/test_scenario_support.py`.

---

## Phase 5: User Story 3 - Keep the Control Package Lightweight and Bounded (Priority: P3)

**Goal**: Keep `open_energy_lab.control` import-light, free of runtime
`legacy/*` imports, and documented as stable public API without breaking
preserved simulator baselines.

**Independent Test**: Import-boundary, no-legacy-import, and preserved-path
regression suites prove that the control package stays lightweight and that
existing explicit-dispatch and built-in simulator rule paths remain available.

### Tests for User Story 3

- [ ] T032 [P] [US3] Extend optional dependency boundary coverage for `open_energy_lab.control` in `tests/unit/test_optional_dependency_boundaries.py`
- [ ] T033 [P] [US3] Add control package no-legacy-import checks in `tests/unit/test_no_legacy_imports.py`
- [ ] T034 [P] [US3] Extend root import-contract coverage for `open_energy_lab.control` in `tests/unit/test_import_contract.py`
- [ ] T035 [P] [US3] Extend preserved explicit-dispatch and built-in rule regression coverage in `tests/integration/simulator/test_battery_arbitrage_trace.py` and `tests/integration/simulator/test_battery_load_pv_trace.py`

### Implementation for User Story 3

- [ ] T036 [US3] Refine package-root control imports and metadata for import-light behavior in `src/open_energy_lab/control/__init__.py`
- [ ] T037 [US3] Update control package API maturity guidance in `docs/migration/api-maturity.md`
- [ ] T038 [US3] Update control package dependency and parity guidance in `docs/migration/dependency-policy.md` and `docs/migration/parity-validation.md`

**Checkpoint**: User Story 3 is functional and independently testable through
the import-boundary and preserved-path regression suites.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Finalize quickstart validation guidance and cross-story
documentation.

- [ ] T039 [P] Update controller-pack review and validation commands in `specs/005-controller-pack/quickstart.md`
- [ ] T040 [P] Update migration overview references for the native control package in `docs/migration/README.md`
- [ ] T041 Run the validation commands documented in `specs/005-controller-pack/quickstart.md`: `uv run pytest tests/unit/control tests/integration/control tests/integration/simulator`, `uv run pytest tests/unit/core tests/unit/simulator`, `uv run python -c "import open_energy_lab.control; import open_energy_lab.core; import open_energy_lab.simulator"`, and `rg "from legacy|import legacy" src/open_energy_lab/control tests/unit/control tests/integration/control tests/integration/simulator docs/migration`
- [ ] T042 Document final validation outcomes and any skipped checks in `specs/005-controller-pack/quickstart.md`

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story implementation begins.
- US1 is the MVP and must complete before US2 because the first shipped
  arbitrage controller establishes the reusable public control surface.
- US2 must complete before US3 because the final import-boundary and preserved
  regression work depends on the full shipped controller set.
- Phase 6 depends on the completion of the selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 -> US2 -> US3 -> Polish
```

## Parallel Execution Examples

### Setup

```text
T002 tests/fixtures/simulator/price_threshold_controller_case.json
T003 tests/fixtures/simulator/README.md
T004 docs/migration/controller-pack.md
```

### Foundational

```text
T005 tests/unit/control/test_import_boundary.py
T006 tests/unit/control/test_configs.py
T007 tests/unit/control/test_support_matrix.py
T008 tests/integration/control/controller_fixture_utils.py
T009 tests/integration/simulator/test_controller_fixture_schema.py
T012 tests/unit/control/test_controller_interface.py
```

### User Story 1

```text
T013 tests/unit/control/test_price_threshold.py
T014 tests/integration/control/test_price_threshold_controller.py
T015 tests/integration/simulator/test_controller_evaluation.py
```

### User Story 2

```text
T021 tests/unit/control/test_soc_guardrail.py
T022 tests/unit/control/test_pv_self_consumption.py
T023 tests/integration/control/test_scenario_support.py
T024 tests/integration/simulator/test_controller_evaluation.py
```

### User Story 3

```text
T032 tests/unit/test_optional_dependency_boundaries.py
T033 tests/unit/test_no_legacy_imports.py
T034 tests/unit/test_import_contract.py
T035 tests/integration/simulator/test_battery_arbitrage_trace.py
```

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Deliver US1 to establish the first shipped native controller and the public
   package-root control surface.
3. Validate `tests/integration/control/test_price_threshold_controller.py`
   before moving to broader controller support.

### Incremental Delivery

1. Add US2 to expand the controller pack across the supported scenario
   families with explicit support declarations.
2. Validate shipped controller behavior with controller-specific fixtures and
   repeated-run checks through `evaluate_with_controller`.
3. Add US3 to harden import boundaries, API maturity docs, and preserved-path
   regressions.

### Final Verification

1. Run the validation commands listed in `specs/005-controller-pack/quickstart.md`.
2. Update migration and dependency docs with final outcomes and any skipped
   checks.
3. Keep all new product code out of `legacy/*`.

## Notes

- [P] tasks are safe to run in parallel because they touch different files and
  do not depend on unfinished tasks.
- Every task names an exact file path so an implementation agent can execute
  it without more context.
- The controller-pack fixtures remain synthetic, reviewable, and deterministic;
  do not replace them with broad legacy runtime parity artifacts.
- `open_energy_lab.control` layers on top of the stable `open_energy_lab.core`
  contract and `open_energy_lab.simulator` runner rather than replacing
  either boundary.
