# Tasks: Declared TPM Feature Domains

**Input**: Design documents from `specs/014-declared-feature-domains/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: The specification requires focused unit, integration, real-SPFlow, persistence, and
Pyomo/HiGHS evidence. Each user-story phase therefore begins with tests that should fail before its
implementation is complete.

**Organization**: Tasks are grouped by user story so declaration-aware fitting, native querying,
compiler validity, and compatibility can be reviewed as separate increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another
  task in the same group.
- **[Story]**: Maps the task to a user story in `spec.md`.
- Every task names the exact source, test, fixture, or documentation path it changes.

## Phase 1: Setup and Reproducible Inputs

**Purpose**: Establish reviewable U-Bounds inputs and protect existing artifact evidence before
changing the TPM representation.

- [X] T001 Add the scalar decision, unbounded demand, declared discrete domains, physical training rows, exact endpoint/adjacent-outside query probes, and compiler probes to `tests/fixtures/tpm/declared_feature_domains_v1.json` without embedding generated model output or treating existing tolerances as domain tolerances
- [X] T002 Document the new fixture's provenance and refresh policy, and identify the existing v1/v2 manifests and sidecars as immutable compatibility anchors, in `tests/fixtures/tpm/README.md`
- [X] T003 Add fixture-loading, semantic-comparison, and source-byte snapshot helpers for later real-backend tests in `tests/integration/tpm/declared_domains_test_support.py`

---

## Phase 2: Foundational Semantic Records

**Purpose**: Create the import-light semantic vocabulary shared by all four user stories.

**Critical**: Complete this phase before story implementation so later code cannot introduce a
second representation of domains, support, or normalization.

- [X] T004 Add failing unit contracts for continuous finite/fixed/lower/upper/unbounded/unknown states, purpose and origin, exact finite endpoint validation, single-feature declaration structure, rejection of coupled constraint payloads, declared binary ordering, categorical completeness, training support, normalization metadata, and JSON round trips in `tests/unit/tpm/test_domains.py`
- [X] T005 Implement immutable, JSON-compatible `TPMFeatureDomain`, `TPMTrainingSupport`, and `TPMNormalizationSpec` records with strict invariants and no SPFlow/Pyomo imports in `src/open_energy_lab/tpm/domains.py`
- [X] T006 Expose only the intended declaration types through the lazy TPM package surface and prove imports remain lazy in `src/open_energy_lab/tpm/__init__.py`, `tests/unit/tpm/test_package_surface.py`, and `tests/unit/tpm/test_import_boundary.py`

**Checkpoint**: Domain meaning, observation evidence, and normalization provenance have one tested,
import-light representation.

---

## Phase 3: User Story 1 — Declare and Audit Mathematical Domains (Priority: P1)

**Goal**: Let callers declare role-appropriate mathematical domains, make those declarations govern
pre-backend validation and normalization, and reload complete v3 feature metadata without confusing
declarations with observed support.

**Independent Test**: Fit and reload feature descriptions for all continuous shapes, a finite scalar
decision, explicitly unbounded demand, an incomplete observed binary pair, and an incomplete
observed categorical set; verify declared/identity/legacy transformations, pre-backend rejection,
purpose, origin, observed subset, and ordering remain distinct.

### Tests for User Story 1

- [X] T007 [P] [US1] Add resolved-feature tests for semantic records, role compatibility, single-feature ownership, coupled/multi-feature declaration rejection, derived legacy convenience fields, declared binary label order, and contradictory-state rejection in `tests/unit/tpm/test_features.py`
- [X] T008 [P] [US1] Add declaration-first type-resolution and physical training-support tests, including one-observed-value binary and incomplete categorical data, in `tests/unit/tpm/test_data_handler.py`
- [X] T009 [P] [US1] Add v3 manifest and sidecar-schema round-trip tests plus foundational v2 adapter tests for unknown mathematical meaning, legacy-inferred ranges, v2-only reserialization, every domain shape, provenance retention, non-finite rejection, and manifest/sidecar disagreement in `tests/unit/tpm/test_artifact_schema.py`
- [X] T010 [P] [US1] Add fit API tests for `TPMArtifactBuildRequest.feature_domains`, the optional planning-dataset/study-manifest `feature_domains` keyword, shared resolution, omitted keys, unknown or unselected keys, and role-ambiguous declarations before backend use in `tests/unit/tpm/test_fit.py`
- [X] T017 [US1] After T007, add forward/inverse normalization and exact assignment-validation tests for finite, fixed, one-sided, unbounded, unknown, declared binary, and declared categorical domains, including endpoint and adjacent-outside values without tolerance reuse, in `tests/unit/tpm/test_features.py`
- [X] T018 [US1] After T008, add tests for different training extrema with identical declared coordinates, exact endpoint membership, explicit unknown versus omission, adjacent/out-of-domain observations, non-finite values, and unchanged physical training support in `tests/unit/tpm/test_data_handler.py`
- [X] T019 [US1] After T010, add backend-spy and output-path tests proving invalid physical rows fail before SPFlow and publish no complete artifact in `tests/unit/tpm/test_fit.py`

### Implementation for User Story 1

- [X] T011 [US1] Extend `TPMFeatureSpec` with resolved domain, training-support, and normalization records while retaining old bounds/value/order fields only as derived compatibility projections in `src/open_energy_lab/tpm/features.py`
- [X] T012 [US1] Separate physical row canonicalization and training-support derivation from declaration resolution, use declarations as authoritative feature typing, classify omitted declarations immediately as unknown mathematical meaning plus legacy-inferred training/normalization behavior, keep explicit unknown on identity normalization, and do not consult compiler metadata, in `src/open_energy_lab/tpm/data.py`
- [X] T022 [US1] Implement exact closed-domain validation plus forward and inverse declared/identity/legacy transforms, including fixed-to-zero behavior, finite-only numeric input, and no reuse of fit/query/compiler tolerances for domain membership, in `src/open_energy_lab/tpm/domains.py` and `src/open_energy_lab/tpm/features.py`
- [X] T023 [US1] Refactor training preparation into physical support derivation, declaration-or-omission resolution, pre-backend validation, normalization, and tensor construction while ignoring compiler approximation intervals in `src/open_energy_lab/tpm/data.py`
- [X] T013 [US1] Add `TPMArtifactBuildRequest.feature_domains`, add the optional keyword-only `feature_domains` mapping to planning-dataset and study-manifest fit entry points, and route all three through one resolver that rejects unknown/unselected keys without inferring declarations from planning metadata in `src/open_energy_lab/tpm/fit.py`
- [X] T014 [US1] Introduce TPM artifact schema v3 for new fits and the explicit foundational v2 adapter that classifies old bounds/values as legacy-inferred, preserves v2-only reserialization, requires refitting for v3 semantics, and retains v1/future-version rejection in `src/open_energy_lab/tpm/artifact.py`
- [X] T015 [US1] Serialize and verify v3 feature semantics inside the current-SPFlow sidecar without eager backend imports or manifest/sidecar drift in `src/open_energy_lab/tpm/optional_spflow.py`
- [X] T024 [US1] Make all public fit paths consume the declaration-aware pipeline before writing v3, persist exact physical support and transform provenance, and publish artifacts transactionally only after validation succeeds in `src/open_energy_lab/tpm/fit.py`
- [X] T016 [US1] Run the US1 unit slice `uv run --locked --no-sync pytest tests/unit/tpm/test_domains.py tests/unit/tpm/test_features.py tests/unit/tpm/test_data_handler.py tests/unit/tpm/test_fit.py tests/unit/tpm/test_artifact_schema.py tests/unit/tpm/test_package_surface.py tests/unit/tpm/test_import_boundary.py` and resolve failures in the named files

**Checkpoint**: User Story 1 independently provides declaration-aware production fitting,
pre-backend validation, declared/identity/legacy transformations, v3 semantic round trips, and the
foundational v2 semantic adapter; it does not yet claim native-query or compiler behavior.

---

## Phase 4: User Story 2 — Query and Validate Declared Meaning (Priority: P1)

**Goal**: Make native queries consume the declared meaning already used by fitting, preserve
physical units for one-sided, unbounded, and explicitly unknown continuous features, and produce
real-backend fixture evidence for the complete fit/query path.

**Independent Test**: Fit two datasets with different observed extrema and the same declared
$[40,160]$ decision domain, confirm a shared probe maps identically, confirm unbounded normal demand
uses identity coordinates, and query valid values outside training support through real SPFlow.

### Tests for User Story 2

- [X] T020 [P] [US2] Add native-query tests for inside-domain/outside-training assignments, one-sided endpoints, fixed values, unobserved declared discrete values, and source-specific validation diagnostics in `tests/unit/tpm/test_query.py`
- [X] T021 [P] [US2] Add a real current-SPFlow fit/query/reload check for finite scalar decision bounds, identity-normalized unbounded demand, stable probes across two training supports, and backend-owned unobserved-category probability in `tests/integration/tpm/test_declared_domains_fit_query.py`

### Implementation for User Story 2

- [X] T025 [US2] Remove semantic reliance on synthetic alternate observations or perturbed values, confine any necessary backend stabilization to backend-only state, and add regression coverage in `src/open_energy_lab/tpm/features.py`, `src/open_energy_lab/tpm/optional_spflow.py`, `tests/unit/tpm/test_spflow_v1_features.py`, and `tests/unit/tpm/test_optional_spflow.py`
- [X] T026 [US2] Route native assignment validation and normalization through resolved semantic records with distinct non-finite, decision-domain, distribution-support, discrete-membership, unknown-domain, and legacy-limit diagnostics in `src/open_energy_lab/tpm/query.py`
- [X] T027 [US2] Add an offline regenerate/verify mode for declared-domain v3 evidence in `examples/tpm_planning/run_declared_domains_pipeline.py`, generate `tests/fixtures/tpm/tpm_artifact_domains_v3.json` and `tests/fixtures/tpm/sidecars/tpm_artifact_domains_v3.spn_payload.pkl`, and record the command, seed, versions, digest, probes, and tolerances in `tests/fixtures/tpm/README.md`
- [X] T028 [US2] Run `uv run --locked --no-sync pytest tests/unit/tpm/test_domains.py tests/unit/tpm/test_features.py tests/unit/tpm/test_data_handler.py tests/unit/tpm/test_fit.py tests/unit/tpm/test_query.py tests/unit/tpm/test_spflow_v1_features.py tests/unit/tpm/test_optional_spflow.py tests/integration/tpm/test_declared_domains_fit_query.py` and verify the fixture with `uv run --locked --no-sync python examples/tpm_planning/run_declared_domains_pipeline.py --verify-fixture`

**Checkpoint**: User Stories 1 and 2 form the practical declared-domain fitting, persistence, and
native-query capability on CPU with real SPFlow evidence.

---

## Phase 5: User Story 3 — Qualify Compiler Approximation Regions (Priority: P2)

**Goal**: Require explicit physical validity intervals only for retained continuous approximations,
persist derived coordinates, reject extrapolation, and expose auditable physical/model decision
linking.

**Independent Test**: Compile a retained scalar decision on explicit physical interval $[60,140]$
under mathematical domain $[40,160]$, verify derived interval $[1/6,5/6]$, evaluate endpoints and an
interior point, reject outside evidence, and solve the physical/model-coordinate link with HiGHS.

### Tests for User Story 3

- [X] T029 [P] [US3] Add approximation-domain and compiled-validity record tests for finite positive-width intervals, physical/model coordinate derivation, round trips, encoding identity, and invalid non-finite/reversed/zero-width requests in `tests/unit/tpm/test_domains.py`
- [X] T030 [P] [US3] Add compiler contract tests for missing, out-of-decision-domain, unknown-feature, discrete-feature, unused, no-fallback, and loaded-v2 fitted-artifact rejection cases plus persisted physical/model breakpoints in `tests/unit/tpm/test_spflow_v1_mio.py`
- [X] T031 [P] [US3] Add real-SPFlow compiled evaluation tests for physical evidence, model-coordinate internal evidence, endpoint acceptance, outside-region rejection, marginalized continuous features, and discrete-only graphs in `tests/integration/tpm/test_declared_domains_mio.py`
- [X] T032 [P] [US3] Add planning integration tests proving marginalization precedes compilation and only retained approximate continuous features require intervals in `tests/integration/planning/test_spflow_v1_highs_pipeline.py` and `tests/integration/planning/test_problem_assembly.py`
- [X] T033 [P] [US3] Add a constant-objective Pyomo/HiGHS feasibility smoke test that fixes lower/interior/upper physical decisions, verifies model coordinates, and rejects an outside value in `tests/integration/tpm/test_declared_domains_highs_link.py`

### Implementation for User Story 3

- [X] T034 [US3] Implement import-light `TPMApproximationDomain` and `TPMCompiledValidityRecord` semantics with physical authority and derived model-coordinate serialization, and expose the intended compiler request type lazily, in `src/open_energy_lab/tpm/domains.py`, `src/open_energy_lab/tpm/__init__.py`, and `tests/unit/tpm/test_package_surface.py`
- [X] T035 [US3] Version new compiler output as compiled payload v2, require a v3 fitted artifact with a finite declared domain for every retained continuous decision approximation, reject loaded v2 artifacts and unknown/legacy-only semantics, validate one explicit physical interval per retained approximation, derive relative breakpoints through persisted normalization, and record all required validity provenance in `src/open_energy_lab/tpm/mio.py`
- [X] T036 [US3] Add checked physical-evidence evaluation and checked model-coordinate evaluation for compiled v2 without clipping or extrapolation, while keeping normalized-only compiled v1 evaluation separate in `src/open_energy_lab/tpm/mio.py`
- [X] T037 [US3] Replace implicit `[0,1]` continuous decisions with physical and model-coordinate Pyomo variables plus affine/identity links, and decode arbitrary declared binary labels by caller order, in `src/open_energy_lab/tpm/mio.py`
- [X] T038 [US3] Make planning workflows structurally marginalize with the existing TPM primitive before compilation and forward explicit approximation requests without adding conditional numerator/denominator blocks in `src/open_energy_lab/planning/workflow.py` and `src/open_energy_lab/planning/problem.py`
- [X] T039 [US3] Teach planning piecewise consumers to validate compiled v2 validity records while retaining explicit compiled v1 compatibility, changing shared piecewise metadata only where required, in `src/open_energy_lab/planning/piecewise.py` and `src/open_energy_lab/tpm/piecewise.py`
- [X] T040 [US3] Update existing compiler call sites to refit source rows as declared-domain v3 artifacts before requesting compiled v2, use exact/marginalized treatments, or assert the expected loaded-v2 rejection; never attach a physical interval to a v2 fitted artifact as if it supplied a mathematical domain, and preserve focused native-versus-compiled checks, in `tests/unit/tpm/test_mio.py`, `tests/unit/tpm/test_spflow_v1_mio.py`, `tests/integration/tpm/test_spflow_v1_mio_parity.py`, `tests/integration/planning/test_tpm_fixture_schema.py`, and `tests/integration/planning/test_spflow_v1_highs_pipeline.py`
- [X] T041 [US3] Run `uv run --locked --no-sync pytest tests/unit/tpm/test_domains.py tests/unit/tpm/test_mio.py tests/unit/tpm/test_spflow_v1_mio.py tests/integration/tpm/test_declared_domains_mio.py tests/integration/tpm/test_declared_domains_highs_link.py tests/integration/tpm/test_spflow_v1_mio_parity.py tests/integration/planning/test_spflow_v1_highs_pipeline.py tests/integration/planning/test_problem_assembly.py`

**Checkpoint**: User Story 3 compiles only explicitly qualified continuous regions and proves the
physical/model link through open CPU tooling without adding conditional risk or benchmark models.

---

## Phase 6: User Story 4 — Preserve Existing Artifacts Without Strengthening Their Claims (Priority: P2)

**Goal**: Keep v2 artifacts and declaration-free callers operational while classifying observed
ranges and values as legacy-inferred and preserving their old restrictions without theoretical
claims.

**Independent Test**: Snapshot a representative v2 manifest and sidecar, load/query and reserialize
them, verify source bytes and numeric behavior are preserved, and audit that mathematical domains
remain unknown and legacy operational limits remain visibly classified. Separately, evaluate an
already-persisted compiled-v1 payload through its normalized-only path without inferring physical
validity.

### Tests for User Story 4

- [X] T042 [P] [US4] Extend the foundational v2 adapter tests with unchanged mixed-feature loading, safe sidecar/integrity behavior, byte-stable source loading, and repeated schema-aware v2 reserialization in `tests/unit/tpm/test_artifact_schema.py`
- [X] T043 [P] [US4] Add declaration-free fit tests for observed-extrema min-max, fixed legacy ranges, existing discrete inference/order/encoding, explicit-unknown separation, and no fabricated unobserved value in `tests/unit/tpm/test_data_handler.py` and `tests/unit/tpm/test_fit.py`
- [X] T044 [P] [US4] Add native-query tests proving legacy out-of-observed-range rejection is labelled operational compatibility behavior and cannot be reported as a mathematical-domain violation in `tests/unit/tpm/test_query.py`
- [X] T045 [P] [US4] Add production-v2 manifest/sidecar load and query checks that snapshot bytes and preserve current normalization results in `tests/integration/tpm/test_spflow_v1_persistence.py` and `tests/integration/tpm/test_spflow_v1_query.py`
- [X] T046 [P] [US4] Add compiled-v1 tests proving normalized-only payloads remain evaluable but never acquire inferred physical validity in `tests/unit/tpm/test_mio.py`

### Implementation for User Story 4

- [X] T047 [US4] Harden the foundational v2 adapter for mixed-feature fixtures, integrity-checked sidecars, byte-stable loading, and repeatable v2-only reserialization without adding v3 semantics in `src/open_energy_lab/tpm/artifact.py`
- [X] T048 [US4] Harden and regression-test the foundational omission classification for continuous and discrete features, preserving unknown mathematical meaning plus legacy-inferred training/normalization behavior while keeping explicit unknown on identity normalization, in `src/open_energy_lab/tpm/data.py`, `src/open_energy_lab/tpm/features.py`, and `src/open_energy_lab/tpm/fit.py`
- [X] T049 [US4] Preserve legacy assignment limits with source-aware diagnostics that distinguish operational compatibility restrictions from mathematical-domain failures in `src/open_energy_lab/tpm/query.py`
- [X] T050 [US4] Preserve compiled v1 normalized evaluation and planning consumption without deriving physical intervals or routing it through compiled-v2 validity rules, and regression-test that compatibility never promotes compiled-v1 payloads to physical validity, in `src/open_energy_lab/tpm/mio.py` and `src/open_energy_lab/planning/piecewise.py`
- [X] T051 [US4] Run `uv run --locked --no-sync pytest tests/unit/tpm/test_artifact_schema.py tests/unit/tpm/test_data_handler.py tests/unit/tpm/test_fit.py tests/unit/tpm/test_query.py tests/unit/tpm/test_mio.py tests/integration/tpm/test_spflow_v1_persistence.py tests/integration/tpm/test_spflow_v1_query.py` and confirm `tests/fixtures/tpm/tpm_artifact_v2.json` plus its sidecars are byte-unchanged

**Checkpoint**: All representative pre-feature fitted-artifact behavior remains usable and visibly
legacy-inferred, v2-only reserialization remains intact, and already-persisted compiled-v1 payloads
remain evaluable without acquiring physical validity.

---

## Phase 7: Polish and Cross-Cutting Validation

**Purpose**: Document the public migration, validate dependency boundaries, and run the complete
offline acceptance surface.

- [X] T052 [P] Document declaration shapes and carriers, exact boundary comparisons, single-feature ownership and coupled-constraint rejection, omission versus explicit unknown, v3/v2 compatibility, native-query behavior, and physical/model-coordinate compiler intervals in `docs/migration/declared-feature-domains.md`
- [X] T053 [P] Extend package-wide lazy-import and no-legacy checks for the new domain module and changed planning adapters in `tests/unit/test_lazy_dependency_boundaries.py`, `tests/unit/test_import_contract.py`, and `tests/unit/test_no_legacy_imports.py`
- [X] T054 Run the full TPM/planning regression command from `specs/014-declared-feature-domains/quickstart.md`, excluding only the already documented optional Gurobi/legacy-backend files and treating the new SPFlow/HiGHS tests as required
- [X] T055 Run `uv lock --check`, the import smoke command, the no-legacy `rg` check, and `git diff --check`; then update actual commands or explicitly documented environmental limitations in `specs/014-declared-feature-domains/quickstart.md`
- [X] T056 Audit `tests/fixtures/tpm/README.md`, all manifests under `tests/fixtures/tpm/`, OEL `git status`, and the parent repository gitlink to confirm provenance is complete, old fixture bytes are preserved, no dependency change was introduced, and no parent-repository file or gitlink was modified

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: Starts immediately.
- **Phase 2 (Foundational records)**: Depends on Phase 1's fixture vocabulary.
- **User Story 1 (Phase 3)**: Depends on Phase 2; establishes resolved metadata, artifact v3, and
  the semantic v2 adapter required by every later consumer.
- **User Story 2 (Phase 4)**: Depends on User Story 1; routes native queries through the established
  semantics and adds real-SPFlow fit/query evidence. Declaration-aware fitting is already
  operational after User Story 1.
- **User Story 3 (Phase 5)**: Depends on User Stories 1 and 2 for persisted transforms and physical
  query behavior.
- **User Story 4 (Phase 6)**: Depends on User Stories 1 and 2 for the resolved v3/v2 semantic model
  and normalization behavior, but its compatibility hardening is independent of User Story 3 and
  may run in parallel with it.
- **Polish (Phase 7)**: Depends on User Stories 3 and 4.

### User-story dependency graph

```text
Setup → Foundational → US1 → US2 ─┬→ US3 ─┐
                                  └→ US4 ─┴→ Polish
```

### Within each user story

1. Write the listed unit and integration contracts first.
2. Implement semantic/model changes before workflow adapters.
3. Generate persisted production evidence only after fit/query behavior is stable.
4. Run the story's focused command and resolve failures before its checkpoint.

---

## Parallel Execution Examples

### User Story 1

After T004–T006 establish the semantic vocabulary, T007–T010 can proceed in parallel across their
separate test files. T017 follows T007, T018 follows T008, and T019 follows T010; after those direct
prerequisites, the three second-wave tasks touch distinct files and may proceed concurrently.
Implement T011, T012, T022, T023, T013–T015, and T024 in dependency order so complete validation and
transformation semantics exist before public fit paths emit v3.

### User Story 2

T020 and T021 establish native-query and real-backend contracts against declaration-aware US1
fitting. T025 and T026 then complete backend isolation and querying; T027 waits until the real
fit/query implementation is stable.

### User Story 3

T029–T033 can run in parallel as domain, compiler, planning, and solver contract tests. T034 must
land before the compiler work; T035–T037 share `tpm/mio.py` and remain sequential; T038 and T039 may
then proceed in parallel on distinct planning files before T040 updates all callers.

### User Story 4

T042–T046 can run in parallel across artifact, fit/data, query, integration, and compiler
compatibility tests. T047–T050 follow the corresponding source boundaries and do not depend on US3.

---

## Implementation Strategy

### MVP first

1. Complete Setup and Foundational records.
2. Complete User Story 1.
3. Stop and review declaration-aware fitting and the v3 round trip before adding native querying.

This is the smallest independently reviewable MVP: it proves that mathematical domains, observed
support, and normalization provenance govern real fitting and can be audited without semantic loss.
User Story 2 completes the practical library release by routing native queries through the same
meaning and adding real-SPFlow evidence.

### Incremental delivery

1. **US1**: Semantic declaration, auditable v3 persistence, and foundational v2 adaptation.
2. **US2**: Native-query behavior and real SPFlow evidence for the stable fit-time normalization.
3. **US3**: Explicit compiler validity and HiGHS decision linking.
4. **US4**: Fully labelled compatibility for artifacts and omission-based callers.
5. **Polish**: Public migration guidance and complete offline regression evidence.

### Scope controls

- Do not add conditional numerator/denominator MIO blocks, objective-free risk parity, benchmark
  objectives, integer linking, device selection, notebook work, or generalized transforms.
- Do not select benchmark bounds, sample counts, parity-grid sizes, or a domain-boundary tolerance;
  existing fit/query/compiler tolerances retain their current purposes.
- Do not regenerate v1/v2 compatibility fixtures into v3 or reinterpret compiled v1 coordinates as
  physical validity.
- Do not modify `pyproject.toml`, `uv.lock`, `legacy/*`, or the parent repository unless a separate
  reviewed scope change explicitly authorizes it.

## Notes

- Tasks marked `[P]` touch different files and can be executed concurrently after their phase
  prerequisites complete.
- Existing Gurobi and legacy-backend checks remain optional; current SPFlow and HiGHS evidence added
  by this feature is required.
- Every generated result must retain its declared inputs, seed/configuration, backend/compiler
  versions, digest, transforms, validity intervals, and assertion tolerance.
