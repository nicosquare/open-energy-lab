# Tasks: Stochastic Weather Generation And Simulator Integration

**Input**: Design documents from `/specs/007-stochastic-weather/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The feature requires focused unit, integration, fixture-validation,
import-boundary, no-legacy-import, and stochastic acceptance checks because
the spec promotes a stable weather package, persisted artifacts, offline
sampling, and simulator family evaluation with preserved deterministic paths.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another task
- **[Story]**: Which user story this task belongs to, such as US1, US2, US3
- Include exact file paths in descriptions

## Path Conventions

- **Spec Kit**: `.specify/`, `.agents/`
- **Legacy references**: `legacy/old_tpm/`, `legacy/fed_trpo/`
- **Target library**: `src/open_energy_lab/weather`, `src/open_energy_lab/simulator`
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/parity/`, `tests/fixtures/`

## Phase 1: Setup

**Purpose**: Establish the weather package, deterministic fixtures, and
migration-note scaffolding without expanding legacy runtime code.

- [X] T001 Create weather test package scaffolds in `tests/unit/weather/__init__.py` and `tests/integration/weather/__init__.py`
- [X] T002 [P] Create deterministic weather and simulator fixture scaffolds in `tests/fixtures/weather/recorded_pvgis_tmy_response.json`, `tests/fixtures/weather/location_unavailable_response.json`, `tests/fixtures/weather/fitted_weather_artifact_v1.json`, `tests/fixtures/simulator/stochastic_weather_family_case.json`, and `tests/fixtures/simulator/blackout_weather_family_case.json`
- [X] T003 [P] Add weather fixture provenance placeholders in `tests/fixtures/weather/README.md` and `tests/fixtures/simulator/README.md`
- [X] T004 [P] Create the stochastic-weather migration note file in `docs/migration/stochastic-weather.md`

---

## Phase 2: Foundational

**Purpose**: Add shared validation infrastructure and package scaffolding that
blocks all user story work.

- [X] T005 [P] Add weather package import-boundary coverage in `tests/unit/weather/test_import_boundary.py`
- [X] T006 [P] Add weather package no-legacy-import coverage in `tests/unit/weather/test_no_legacy_imports.py`
- [X] T007 [P] Extend root optional dependency boundary coverage for `open_energy_lab.weather` and `open_energy_lab.simulator.stochastic_weather` in `tests/unit/test_optional_dependency_boundaries.py`
- [X] T008 [P] Add weather fixture loading helpers in `tests/integration/weather/fixture_utils.py` and `tests/integration/simulator/weather_family_fixture_utils.py`
- [X] T009 [P] Add fixture-schema and provenance validation for weather artifacts and simulator family fixtures in `tests/integration/weather/test_fixture_schema.py` and `tests/integration/simulator/test_weather_family_fixture_schema.py`
- [X] T010 [P] Add stable weather package-surface and import-contract coverage in `tests/unit/weather/test_package_surface.py` and `tests/unit/test_import_contract.py`
- [X] T011 Create shared weather package module scaffolding and stable export placeholders in `src/open_energy_lab/weather/__init__.py`, `src/open_energy_lab/weather/_canonical.py`, `src/open_energy_lab/weather/tmy.py`, `src/open_energy_lab/weather/fit.py`, `src/open_energy_lab/weather/artifact.py`, `src/open_energy_lab/weather/sampling.py`, `src/open_energy_lab/weather/events.py`, and `src/open_energy_lab/simulator/stochastic_weather.py`
- [X] T012 [P] Populate stochastic-weather API-maturity and dependency-boundary placeholder content in `docs/migration/stochastic-weather.md`, `docs/migration/api-maturity.md`, and `docs/migration/dependency-policy.md`

**Checkpoint**: Shared package scaffolding, fixture utilities, and boundary
validation are in place.

---

## Phase 3: User Story 1 - Fit And Persist A Location-Specific Weather Model (Priority: P1)

**Goal**: Let a library user provide geolocation input, fetch and normalize
TMY weather data, fit a stochastic weather artifact, and reload that artifact
offline later.

**Independent Test**: A reviewer can run the fit workflow against a recorded
PVGIS TMY fixture, inspect the persisted artifact, and reload it offline to
confirm it remains sampleable without refetching source data.

### Tests for User Story 1

- [X] T013 [P] [US1] Add canonical schema and local-civil-time normalization unit coverage in `tests/unit/weather/test_canonical_schema.py`
- [X] T014 [P] [US1] Add artifact schema, provenance, timestep lock, and unsupported-version unit coverage in `tests/unit/weather/test_artifact_schema.py`
- [X] T015 [P] [US1] Add recorded fetch-to-artifact integration coverage for offline reload, missing-field failures, and syntactically valid but source-unavailable locations in `tests/integration/weather/test_fit_workflow.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement the PVGIS-backed TMY fetch adapter in `src/open_energy_lab/weather/tmy.py` using `legacy/old_tpm/src_py/weather/fetch.py` as reference-only evidence
- [X] T017 [US1] Implement canonical field ordering, full ten-field normalization, source-label mapping, and local-civil-time normalization in `src/open_energy_lab/weather/_canonical.py` and `src/open_energy_lab/simulator/_weather_schema.py` using `legacy/old_tpm/src_py/weather/pipeline.py` as reference-only evidence
- [X] T018 [US1] Implement artifact fitting, JSON persistence, and supported-version loading in `src/open_energy_lab/weather/fit.py` and `src/open_energy_lab/weather/artifact.py` using `legacy/old_tpm/src_py/weather/models/gaussian.py` and `legacy/old_tpm/src_py/weather/models/enhanced.py` as reference-only evidence
- [X] T019 [US1] Export `fit_weather_model` and `load_weather_artifact` from `src/open_energy_lab/weather/__init__.py`
- [X] T020 [US1] Populate recorded fetch and artifact fixtures with provenance in `tests/fixtures/weather/recorded_pvgis_tmy_response.json`, `tests/fixtures/weather/missing_required_field_response.json`, `tests/fixtures/weather/location_unavailable_response.json`, `tests/fixtures/weather/fitted_weather_artifact_v1.json`, `tests/fixtures/weather/fitted_weather_artifact_unsupported_version.json`, and `tests/fixtures/weather/README.md`
- [X] T021 [US1] Document geolocation-to-artifact preserve/improve/reject decisions and fit workflow usage in `docs/migration/stochastic-weather.md` and `specs/007-stochastic-weather/quickstart.md`

**Checkpoint**: User Story 1 is functional and independently testable through
`tests/integration/weather/test_fit_workflow.py`.

---

## Phase 4: User Story 2 - Sample Many Arbitrary-Horizon Weather Instances (Priority: P2)

**Goal**: Let a researcher load a fitted artifact and generate many seeded
weather traces for any positive horizon length while preserving the full
canonical weather field set and explicit cloud-event metadata.

**Independent Test**: A reviewer can load a persisted artifact, request
multiple seeded samples for several positive `num_steps` values, and verify
that each scenario contains the complete canonical field set, exact horizon
length, deterministic seed behavior, and physical-bounds enforcement.

### Tests for User Story 2

- [X] T022 [P] [US2] Add seeded family-sampling unit coverage for arbitrary horizons and timestep mismatch failures in `tests/unit/weather/test_sampling.py`
- [X] T023 [P] [US2] Add cloud-event overlay and physical-bounds unit coverage in `tests/unit/weather/test_events.py`
- [X] T024 [P] [US2] Add offline family sampling integration coverage for reproducibility and exact `num_steps` outputs in `tests/integration/weather/test_offline_sampling.py`
- [X] T025 [P] [US2] Add stochastic acceptance coverage for `100` sampled scenarios at `num_steps=168` across family seeds `0..9`, including explicit physical-bounds, lag-1 autocorrelation (`<= 0.15` mean absolute error), pairwise-correlation (`<= 0.20` mean absolute error), and cloud-event contiguity thresholds in `tests/integration/weather/test_sampling_statistics.py`

### Implementation for User Story 2

- [ ] T026 [US2] Implement contiguous irradiance-event calibration and overlay logic in `src/open_energy_lab/weather/events.py` using `legacy/old_tpm/src_py/weather/analysis/drops.py` and `legacy/old_tpm/src_py/weather/models/enhanced.py` as reference-only evidence
- [ ] T027 [US2] Implement seeded arbitrary-horizon family sampling and request validation in `src/open_energy_lab/weather/sampling.py` using `legacy/old_tpm/src_py/weather/models/gaussian.py` as reference-only evidence
- [ ] T028 [US2] Extend artifact loading and stable sampler exports for offline family sampling in `src/open_energy_lab/weather/artifact.py` and `src/open_energy_lab/weather/__init__.py`
- [ ] T029 [US2] Populate sampling request and sampled-family fixtures with provenance in `tests/fixtures/weather/sampling_request_case.json`, `tests/fixtures/weather/sampled_weather_family_case.json`, and `tests/fixtures/weather/README.md`
- [ ] T030 [US2] Document stable versus experimental sampling controls and stochastic validation expectations in `docs/migration/stochastic-weather.md` and `specs/007-stochastic-weather/quickstart.md`

**Checkpoint**: User Story 2 is functional and independently testable through
`tests/integration/weather/test_offline_sampling.py` and
`tests/integration/weather/test_sampling_statistics.py`.

---

## Phase 5: User Story 3 - Evaluate Stochastic Weather In The Simulator While Preserving Deterministic Debugging (Priority: P3)

**Goal**: Let simulator maintainers evaluate scenario families against sampled
weather and caller-configured blackouts without breaking the deterministic
`BatteryLoadPVScenario` path.

**Independent Test**: A reviewer can run one deterministic
`BatteryLoadPVScenario` through the existing fixed-weather path and also run a
family evaluation from a loaded artifact, verifying scenario-indexed results,
fixed percentile summaries, explicit blackout semantics, and preserved
deterministic debugging behavior.

### Tests for User Story 3

- [ ] T031 [P] [US3] Add simulator unit coverage for family summaries, blackout traces, and unmet-load fields in `tests/unit/simulator/test_stochastic_weather.py`
- [ ] T032 [P] [US3] Add stochastic family integration coverage for scenario-indexed results and fixed percentile summaries in `tests/integration/simulator/test_stochastic_weather_family.py`
- [ ] T033 [P] [US3] Add blackout grid-outage integration coverage for disabled grid exchange and explicit unmet load in `tests/integration/simulator/test_blackout_semantics.py`
- [ ] T034 [P] [US3] Extend deterministic fixed-weather regression coverage to preserve `BatteryLoadPVScenario` debugging behavior in `tests/integration/simulator/test_battery_load_pv_trace.py`

### Implementation for User Story 3

- [ ] T035 [US3] Implement simulator-side weather-family request, result, and summary types in `src/open_energy_lab/simulator/stochastic_weather.py`
- [ ] T036 [US3] Extend simulator scenario and trace entities for blackout-aware family evaluation in `src/open_energy_lab/simulator/scenario.py`
- [ ] T037 [US3] Preserve deterministic weather inputs while adapting sampled canonical weather traces for PV evaluation and enforcing the artifact-versus-simulator-consumed field boundary in `src/open_energy_lab/simulator/weather.py` and `src/open_energy_lab/simulator/pv.py` using `legacy/old_tpm/src_py/simulator/common/weather.py` and `legacy/old_tpm/src_py/simulator/common/pv.py` as reference-only evidence
- [ ] T038 [US3] Export the stochastic family evaluation surface from `src/open_energy_lab/simulator/__init__.py`
- [ ] T039 [US3] Populate stochastic family and blackout fixtures with provenance in `tests/fixtures/simulator/stochastic_weather_family_case.json`, `tests/fixtures/simulator/blackout_weather_family_case.json`, and `tests/fixtures/simulator/README.md`
- [ ] T040 [US3] Document simulator family semantics, preserved deterministic debugging, blackout behavior, and the artifact-versus-simulator-consumed field boundary in `docs/migration/stochastic-weather.md` and `specs/007-stochastic-weather/quickstart.md`

**Checkpoint**: User Story 3 is functional and independently testable through
`tests/integration/simulator/test_stochastic_weather_family.py` and
`tests/integration/simulator/test_blackout_semantics.py`.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Finalize migration guidance, validation commands, and repository
working notes that apply across all stories.

- [ ] T041 [P] Update public API maturity and dependency classification for `open_energy_lab.weather` and simulator stochastic evaluation in `docs/migration/api-maturity.md` and `docs/migration/dependency-policy.md`
- [ ] T042 [P] Update fixture, environment, and parity guidance for weather validation in `docs/migration/fixture-provenance.md`, `docs/migration/environment-assumptions.md`, and `docs/migration/parity-validation.md`
- [ ] T043 [P] Update migration index and repository working guidance for the weather feature in `docs/migration/README.md`, `AGENTS.md`, and `specs/007-stochastic-weather/quickstart.md`
- [ ] T044 Run the validation commands documented in `specs/007-stochastic-weather/quickstart.md`: `uv run pytest tests/unit/weather tests/integration/weather tests/integration/simulator`, `uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py`, `uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.simulator"`, and `rg "from legacy|import legacy" src/open_energy_lab/weather src/open_energy_lab/simulator tests/unit/weather tests/integration/weather tests/integration/simulator docs/migration`
- [ ] T045 Document final validation outcomes and any skipped live-fetch or optional-dependency checks in `specs/007-stochastic-weather/quickstart.md`

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 must complete before any user story implementation begins.
- US1 is the MVP and must complete before US2 because offline sampling depends
  on persisted fitted artifacts and canonical normalization.
- US2 must complete before US3 because simulator family evaluation consumes the
  loaded artifact, sampled weather traces, and family-seed semantics.
- Phase 6 depends on the completion of the selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 -> US2 -> US3 -> Polish
```

## Parallel Execution Examples

### Setup

```text
T002 tests/fixtures/weather/recorded_pvgis_tmy_response.json
T003 tests/fixtures/weather/README.md
T004 docs/migration/stochastic-weather.md
```

### Foundational

```text
T005 tests/unit/weather/test_import_boundary.py
T006 tests/unit/weather/test_no_legacy_imports.py
T008 tests/integration/weather/fixture_utils.py
T009 tests/integration/weather/test_fixture_schema.py
T010 tests/unit/weather/test_package_surface.py
T012 docs/migration/api-maturity.md
```

### User Story 1

```text
T013 tests/unit/weather/test_canonical_schema.py
T014 tests/unit/weather/test_artifact_schema.py
T015 tests/integration/weather/test_fit_workflow.py
```

### User Story 2

```text
T022 tests/unit/weather/test_sampling.py
T023 tests/unit/weather/test_events.py
T024 tests/integration/weather/test_offline_sampling.py
T025 tests/integration/weather/test_sampling_statistics.py
```

### User Story 3

```text
T031 tests/unit/simulator/test_stochastic_weather.py
T032 tests/integration/simulator/test_stochastic_weather_family.py
T033 tests/integration/simulator/test_blackout_semantics.py
T034 tests/integration/simulator/test_battery_load_pv_trace.py
```

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Deliver US1 to establish the stable geolocation-to-artifact workflow.
3. Validate `tests/integration/weather/test_fit_workflow.py` before expanding
   scope.

### Incremental Delivery

1. Add US2 to deliver offline seeded family sampling with cloud-event behavior
   and stochastic acceptance evidence.
2. Add US3 to integrate sampled weather into simulator family evaluation while
   preserving deterministic debugging and adding blackout semantics.
3. Finish Phase 6 to align migration docs, repository guidance, and validation
   commands with the shipped surface.

### Final Verification

1. Run the validation commands listed in
   `specs/007-stochastic-weather/quickstart.md`.
2. Update migration, fixture, and repository guidance with final outcomes and
   any skipped live-fetch checks.
3. Keep all new product code out of `legacy/*`.

## Notes

- [P] tasks are safe to run in parallel because they touch different files and
  do not depend on unfinished work.
- Every task names an exact file path so an implementation agent can execute
  it without more context.
- The stable weather package owns fetch, normalization, fitting, artifact
  persistence, and offline sampling; the simulator remains the consumer and
  owner of execution semantics.
- Live weather fetches remain isolated validation targets; default review
  should rely on recorded fixtures and persisted artifacts.
