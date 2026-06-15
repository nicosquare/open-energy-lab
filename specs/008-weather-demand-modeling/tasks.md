# Tasks: Weather-Conditioned Demand Modeling And Simulator Integration

**Input**: Design documents from `/specs/008-weather-demand-modeling/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The feature requires focused unit, integration, fixture-validation,
import-boundary, no-legacy-import, and deterministic accounting checks because
the spec promotes a stable `open_energy_lab.demand` package, persisted JSON
artifacts, offline paired-family sampling, and cooling-aware simulator
evaluation with preserved deterministic paths.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Path Conventions

- **Spec Kit**: `.specify/`, `.agents/`
- **Legacy references**: `legacy/old_tpm/`, `legacy/fed_trpo/`
- **Target library**: `src/open_energy_lab/demand`, `src/open_energy_lab/simulator`
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/parity/`, `tests/fixtures/`

## Phase 1: Setup

**Purpose**: Establish demand-package, fixture, and migration-note scaffolding
without expanding legacy runtime code.

- [X] T001 Create demand package and test package scaffolds in `src/open_energy_lab/demand/__init__.py`, `tests/unit/demand/__init__.py`, and `tests/integration/demand/__init__.py`
- [X] T002 [P] Create deterministic demand and paired-simulator fixture scaffolds in `tests/fixtures/demand/aligned_training_case.json`, `tests/fixtures/demand/aligned_training_case_missing_cooling.json`, `tests/fixtures/demand/aligned_training_case_missing_non_thermal.json`, `tests/fixtures/demand/fitted_demand_artifact_v1.json`, `tests/fixtures/demand/fitted_demand_artifact_unsupported_version.json`, `tests/fixtures/demand/sampling_request_case.json`, `tests/fixtures/demand/sampled_demand_family_case.json`, `tests/fixtures/simulator/demand_local_electric_family_case.json`, `tests/fixtures/simulator/demand_district_cooling_family_case.json`, and `tests/fixtures/simulator/demand_invalid_mixed_cooling_case.json`
- [X] T003 [P] Add demand fixture provenance placeholders in `tests/fixtures/demand/README.md` and `tests/fixtures/simulator/README.md`
- [X] T004 [P] Create the weather-conditioned-demand migration note file in `docs/migration/weather-demand-modeling.md`

---

## Phase 2: Foundational

**Purpose**: Add shared validation infrastructure and package scaffolding that
blocks all user story work.

- [X] T005 [P] Add demand package import-boundary coverage in `tests/unit/demand/test_import_boundary.py`
- [X] T006 [P] Add demand package no-legacy-import coverage in `tests/unit/demand/test_no_legacy_imports.py`
- [X] T007 [P] Extend root optional dependency boundary coverage for `open_energy_lab.demand` and `open_energy_lab.simulator.stochastic_demand` in `tests/unit/test_optional_dependency_boundaries.py`
- [X] T008 [P] Extend stable package-surface and import-contract coverage for demand exports in `tests/unit/demand/test_package_surface.py` and `tests/unit/test_import_contract.py`
- [X] T009 [P] Add fixture loading helpers for demand and paired simulator cases in `tests/integration/demand/fixture_utils.py` and `tests/integration/simulator/demand_family_fixture_utils.py`
- [X] T010 [P] Add fixture-schema and provenance validation for demand artifacts, sampled demand family fixtures, and paired simulator cases in `tests/integration/demand/test_fixture_schema.py`, `tests/integration/demand/test_sampling_fixture_schema.py`, and `tests/integration/simulator/test_demand_family_fixture_schema.py`
- [X] T011 Create demand package module scaffolding and stable export placeholders in `src/open_energy_lab/demand/__init__.py`, `src/open_energy_lab/demand/_aligned_history.py`, `src/open_energy_lab/demand/_weather_response.py`, `src/open_energy_lab/demand/fit.py`, `src/open_energy_lab/demand/artifact.py`, and `src/open_energy_lab/demand/sampling.py`
- [X] T012 [P] Populate demand-feature API-maturity and dependency-boundary placeholders in `docs/migration/weather-demand-modeling.md`, `docs/migration/api-maturity.md`, and `docs/migration/dependency-policy.md`

**Checkpoint**: Shared package scaffolding, fixture helpers, and boundary
validation are in place.

---

## Phase 3: User Story 1 - Fit And Reload Weather-Conditioned Demand Artifacts (Priority: P1)

**Goal**: Let a library user fit, persist, and later reload an offline demand
artifact from aligned canonical weather, non-thermal electric demand, and
explicit cooling-demand history.

**Independent Test**: A reviewer can run the fit workflow against committed
aligned-history fixtures, write a JSON artifact, reload it offline, and
verify explicit non-thermal-electric and cooling-demand outputs plus fail-fast
validation for missing aligned inputs.

### Tests for User Story 1

- [ ] T013 [P] [US1] Add aligned-history validation unit coverage for timestep alignment, missing cooling history, missing non-thermal history, and ambiguous double-counting inputs in `tests/unit/demand/test_aligned_history.py`
- [ ] T014 [P] [US1] Add artifact schema, provenance, timestep lock, and unsupported-version unit coverage in `tests/unit/demand/test_artifact_schema.py`
- [ ] T015 [P] [US1] Add fit-to-artifact integration coverage for offline reload and fail-fast aligned-input errors in `tests/integration/demand/test_fit_workflow.py`

### Implementation for User Story 1

- [ ] T016 [US1] Implement aligned-history normalization and validation helpers in `src/open_energy_lab/demand/_aligned_history.py`
- [ ] T017 [US1] Implement dual-output weather-response feature extraction and baseline fitting in `src/open_energy_lab/demand/_weather_response.py` using `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`, `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`, and `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb` as conceptual-only reference evidence
- [ ] T018 [US1] Implement demand artifact fitting, JSON persistence, supported-version loading, and explicit double-counting metadata in `src/open_energy_lab/demand/fit.py` and `src/open_energy_lab/demand/artifact.py`
- [ ] T019 [US1] Export `fit_demand_model` and `load_demand_artifact` from `src/open_energy_lab/demand/__init__.py`
- [ ] T020 [US1] Populate aligned-training and fitted-artifact fixtures with provenance in `tests/fixtures/demand/aligned_training_case.json`, `tests/fixtures/demand/aligned_training_case_missing_cooling.json`, `tests/fixtures/demand/aligned_training_case_missing_non_thermal.json`, `tests/fixtures/demand/fitted_demand_artifact_v1.json`, `tests/fixtures/demand/fitted_demand_artifact_unsupported_version.json`, and `tests/fixtures/demand/README.md`
- [ ] T021 [US1] Document fit-workflow preserve/improve/reject decisions and offline artifact usage in `docs/migration/weather-demand-modeling.md` and `specs/008-weather-demand-modeling/quickstart.md`

**Checkpoint**: User Story 1 is functional and independently testable through
`tests/integration/demand/test_fit_workflow.py`.

---

## Phase 4: User Story 2 - Sample Paired Weather-Conditioned Demand Families (Priority: P2)

**Goal**: Let a researcher load a persisted demand artifact and sample
reproducible non-thermal electric and cooling-demand traces for arbitrary
positive horizons against an aligned sampled weather family.

**Independent Test**: A reviewer can load committed weather and demand
artifacts, request at least 10 paired scenarios for a positive horizon, and
verify exact horizon length, scenario ordering, required weather-field
validation, and deterministic replay of per-step weather and demand outputs
from one shared paired-family seed.

### Tests for User Story 2

- [ ] T022 [P] [US2] Add sampling-request fail-fast coverage for non-positive horizons, scenario counts, and timestep mismatches in `tests/unit/demand/test_sampling_request.py`
- [ ] T023 [P] [US2] Add paired-seed replay and required-weather-field unit coverage in `tests/unit/demand/test_sampling_family.py`
- [ ] T024 [P] [US2] Add offline artifact-to-family integration coverage for exact horizon outputs, scenario ordering, and successful sampling of at least 10 paired demand scenarios in `tests/integration/demand/test_offline_sampling.py`
- [ ] T025 [P] [US2] Add paired weather-and-demand replay integration coverage that reruns the same request and compares per-step weather and demand outputs for exact reproducibility in `tests/integration/demand/test_paired_replay.py`

### Implementation for User Story 2

- [ ] T026 [US2] Implement sampling request models, paired-seed derivation, and demand-family generation in `src/open_energy_lab/demand/sampling.py`
- [ ] T027 [US2] Extend artifact loading to validate required weather drivers and fixed timestep compatibility in `src/open_energy_lab/demand/artifact.py`
- [ ] T028 [US2] Export `DemandSamplingRequest` and `sample_demand_family` from `src/open_energy_lab/demand/__init__.py`
- [ ] T029 [US2] Populate paired sampling fixtures and provenance notes in `tests/fixtures/demand/sampling_request_case.json`, `tests/fixtures/demand/sampled_demand_family_case.json`, and `tests/fixtures/demand/README.md`
- [ ] T030 [US2] Document shared paired-family seed semantics and offline sampling workflow in `docs/migration/weather-demand-modeling.md` and `specs/008-weather-demand-modeling/quickstart.md`

**Checkpoint**: User Story 2 is functional and independently testable through
`tests/integration/demand/test_offline_sampling.py` and
`tests/integration/demand/test_paired_replay.py`.

---

## Phase 5: User Story 3 - Evaluate Cooling Service Paths While Preserving Deterministic Simulator Boundaries (Priority: P3)

**Goal**: Let simulator maintainers evaluate aligned weather-and-demand
scenario families with local-electric or district-cooling service while
preserving the existing deterministic `BatteryLoadPVScenario` path and
import-light package boundaries.

**Independent Test**: A reviewer can run one cooling-aware paired family for
both local-electric and district-cooling service, verify explicit cooling
service balance and settlement outputs, reject invalid district-cooling
configuration, confirm blackout intervals remain simulator-side only, and
confirm the deterministic simulator path still works without any demand
artifact.

### Tests for User Story 3

- [ ] T031 [P] [US3] Add cooling-service configuration and electric-conversion unit coverage in `tests/unit/simulator/test_demand.py`
- [ ] T032 [P] [US3] Add paired weather-and-demand family summary and alignment unit coverage in `tests/unit/simulator/test_stochastic_demand.py`
- [ ] T033 [P] [US3] Add local-electric versus district-cooling integration coverage, including blackout-aware family evaluation that keeps blackout semantics simulator-side, in `tests/integration/simulator/test_stochastic_demand_family.py`
- [ ] T034 [P] [US3] Add mixed cooling-path rejection, missing district-tariff rejection, district over-service rejection, and unserved-cooling integration coverage in `tests/integration/simulator/test_cooling_service_validation.py`
- [ ] T035 [P] [US3] Extend deterministic `BatteryLoadPVScenario` regression coverage for preserved direct-load debugging in `tests/integration/simulator/test_battery_load_pv_trace.py`

### Implementation for User Story 3

- [ ] T036 [US3] Implement cooling service configuration types and local-electric conversion helpers in `src/open_energy_lab/simulator/demand.py`
- [ ] T037 [US3] Implement paired weather-and-demand family request, evaluation, and summary types while preserving blackout-semantics separation in `src/open_energy_lab/simulator/stochastic_demand.py`
- [ ] T038 [US3] Extend deterministic load composition and scenario trace models for explicit cooling service balance outputs in `src/open_energy_lab/simulator/load.py` and `src/open_energy_lab/simulator/scenario.py`
- [ ] T039 [US3] Implement deterministic district-cooling settlement and served-`RT-hour` accounting in `src/open_energy_lab/simulator/pricing.py` and `src/open_energy_lab/simulator/objective.py` using `legacy/old_tpm/src_py/simulator/common/pricing.py` as migration evidence
- [ ] T040 [US3] Export the cooling-aware family evaluation surface from `src/open_energy_lab/simulator/__init__.py`
- [ ] T041 [US3] Populate paired simulator demand fixtures and document exact legacy evidence in `tests/fixtures/simulator/demand_local_electric_family_case.json`, `tests/fixtures/simulator/demand_district_cooling_family_case.json`, `tests/fixtures/simulator/demand_invalid_mixed_cooling_case.json`, `tests/fixtures/simulator/README.md`, `docs/migration/weather-demand-modeling.md`, and `specs/008-weather-demand-modeling/quickstart.md`

**Checkpoint**: User Story 3 is functional and independently testable through
`tests/integration/simulator/test_stochastic_demand_family.py`,
`tests/integration/simulator/test_cooling_service_validation.py`, and the
preserved deterministic regression path in
`tests/integration/simulator/test_battery_load_pv_trace.py`.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Finalize migration guidance, validation commands, and repository
working notes that apply across all stories.

- [ ] T042 [P] Update public API maturity and dependency classification for `open_energy_lab.demand` and cooling-aware simulator evaluation in `docs/migration/api-maturity.md` and `docs/migration/dependency-policy.md`
- [ ] T043 [P] Update fixture provenance, environment, and parity guidance for demand validation in `docs/migration/fixture-provenance.md`, `docs/migration/environment-assumptions.md`, and `docs/migration/parity-validation.md`
- [ ] T044 [P] Update migration index and repository working guidance for the demand feature in `docs/migration/README.md` and `AGENTS.md`
- [ ] T045 Run the validation commands documented in `specs/008-weather-demand-modeling/quickstart.md`: `uv run pytest tests/unit/demand tests/integration/demand tests/integration/simulator`, `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py`, `uv run python -c "import open_energy_lab; import open_energy_lab.demand; import open_energy_lab.simulator"`, and `rg "from legacy|import legacy" src/open_energy_lab/demand src/open_energy_lab/simulator tests/unit/demand tests/integration/demand tests/integration/simulator docs/migration`
- [ ] T046 Document final validation outcomes and any skipped optional checks in `specs/008-weather-demand-modeling/quickstart.md`

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story implementation begins.
- US1 is the MVP and must complete before US2 because demand-family sampling
  depends on persisted fitted artifacts and aligned-history validation.
- US3 depends on US1 and US2 because simulator family evaluation consumes the
  demand artifact, sampled demand traces, and paired-family seed semantics.
- Phase 6 depends on the completion of the selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 -> US2 -> US3 -> Polish
```

## Parallel Execution Examples

### Setup

```text
T002 tests/fixtures/demand/aligned_training_case.json
T003 tests/fixtures/demand/README.md
T004 docs/migration/weather-demand-modeling.md
```

### Foundational

```text
T005 tests/unit/demand/test_import_boundary.py
T006 tests/unit/demand/test_no_legacy_imports.py
T009 tests/integration/demand/fixture_utils.py
T010 tests/integration/demand/test_fixture_schema.py
T012 docs/migration/weather-demand-modeling.md
```

### User Story 1

```text
T013 tests/unit/demand/test_aligned_history.py
T014 tests/unit/demand/test_artifact_schema.py
T015 tests/integration/demand/test_fit_workflow.py
```

### User Story 2

```text
T022 tests/unit/demand/test_sampling_request.py
T023 tests/unit/demand/test_sampling_family.py
T024 tests/integration/demand/test_offline_sampling.py
T025 tests/integration/demand/test_paired_replay.py
```

### User Story 3

```text
T031 tests/unit/simulator/test_demand.py
T032 tests/unit/simulator/test_stochastic_demand.py
T033 tests/integration/simulator/test_stochastic_demand_family.py
T034 tests/integration/simulator/test_cooling_service_validation.py
T035 tests/integration/simulator/test_battery_load_pv_trace.py
```

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Deliver US1 to establish the stable aligned-history-to-artifact workflow.
3. Validate `tests/integration/demand/test_fit_workflow.py` before expanding
   scope.

### Incremental Delivery

1. Add US2 to deliver offline paired-family sampling from persisted artifacts.
2. Add US3 to integrate sampled demand into cooling-aware simulator family
   evaluation while preserving deterministic debugging and import-light
   boundaries.
3. Finish Phase 6 to align migration docs, repository guidance, and
   validation commands with the shipped surface.

### Final Verification

1. Run the validation commands listed in
   `specs/008-weather-demand-modeling/quickstart.md`.
2. Update migration, fixture, and repository guidance with final outcomes and
   any skipped optional checks.
3. Keep all new product code out of `legacy/*`.

## Notes

- [P] tasks are safe to run in parallel because they touch different files and
  have no dependency on unfinished work.
- Every task names exact files or directories to keep execution unambiguous.
- All checklist entries follow the required `- [ ] T### [P?] [Story?] ...`
  format.
