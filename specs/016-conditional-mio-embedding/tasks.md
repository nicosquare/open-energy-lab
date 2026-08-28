# Tasks: Composable Conditional MIO Embedding

**Input**: Design documents from `specs/016-conditional-mio-embedding/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: The specification requires focused unit tests, real current-SPFlow integration,
Pyomo/HiGHS parity, immutable evidence, compatibility regressions, and headless notebook execution.
Each user-story phase therefore starts with tests that should fail until that story is implemented.

**Organization**: Tasks are grouped by user story so pair compilation, continuous attachment,
discrete composition, parity/fidelity, safe reuse, and offline explanation remain independently
reviewable increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another
  unfinished task in the same group.
- **[Story]**: Maps the task to a user story in `spec.md`.
- Every task names the exact source, test, fixture, workflow, or documentation path it changes.

## Phase 1: Setup and Reproducible Inputs

**Purpose**: Establish the reviewed nonuniform mixed input and fixture helpers without generating
derived SPFlow or compiler evidence prematurely.

- [X] T001 Add the human-reviewable nonuniform continuous, binary, ordered categorical, marginalized uncertainty, and binary event rows plus declared domains, fixed fit seed/options, max/PWL policies, representative assignments, and purpose-labelled tolerances to `tests/fixtures/tpm/conditional_mio_embedding_v1.json`
- [X] T002 Document the source-row provenance, deliberate nonuniformity, no-retry refresh policy, expected current-SPFlow Sum-node invariant, representative non-Cartesian cases, and future derived fixture paths in `tests/fixtures/tpm/README.md`
- [X] T003 Add source/config loading, deterministic semantic comparison, artifact/pair/evidence byte snapshots, and temporary-output helpers in `tests/integration/tpm/conditional_mio_test_support.py`

---

## Phase 2: Foundational Conditional Records and Graph Semantics

**Purpose**: Create the import-light immutable pair vocabulary and one shared, mathematically correct
conditioner before any public compilation or attachment workflow is built.

**Critical**: Complete this phase first so later stories cannot create competing pair schemas,
identity rules, marginalization behavior, or planning-only compiler transformations.

- [X] T004 Add failing unit contracts for compilation requests, source references, feature/event meaning, circuit nodes and roots, recursive immutability, finite canonical JSON, pair identity, schema rejection, and round trips in `tests/unit/tpm/test_conditional_pair.py`
- [X] T005 [P] Add failing unit contracts for arbitrary binary event-value indexing, numerator event fixing, denominator event marginalization, common nonevent marginalization, exact log-one constants, Product simplification, fully marginalized Sum simplification, and acyclic circuit validation in `tests/unit/tpm/test_conditional_mio.py`
- [X] T006 Implement immutable conditional compilation requests, source/event/validity/encoding records, circuit node/graph records, conditional-pair validation, detached serialization, and canonical SHA-256 identity without backend imports in `src/open_energy_lab/tpm/conditional.py`
- [X] T007 Implement finite canonical JSON loading plus the nominal flushed/fsynced atomic no-replace create-or-verify path, including identical reuse, ordinary conflicting-target rejection, temporary-file cleanup, and no final overwrite operation, in `src/open_energy_lab/tpm/conditional.py`
- [X] T008 Extract a TPM-owned serialized-graph conditioning primitive with explicit event index, exact log-one nodes, Product/Sum simplification, common-origin metadata, and invariant checks in `src/open_energy_lab/tpm/mio.py`
- [X] T009 Complete the conditioner extraction by making the existing planning conditioner delegate directly to the shared TPM primitive while preserving its public payload and hard-coded legacy event behavior, and add focused delegation regressions in `src/open_energy_lab/planning/piecewise.py` and `tests/unit/planning/test_piecewise.py`

**Checkpoint**: Conditional meaning, pair identity, immutable persistence, and exact marginalization
have one tested import-light representation, while existing planning behavior remains unchanged.

---

## Phase 3: User Story 1 — Compile a Reusable Conditional Pair (Priority: P1)

**Goal**: Compile one explicit event numerator and learned denominator from one eligible persisted
current-SPFlow artifact, persist/reload the pair, and directly execute its selected max or PWL
semantics without refitting or assuming a uniform denominator.

**Independent Test**: Fit and persist the reviewed real artifact, compile max and PWL pairs for one
event value with retained decisions, reload them, and directly evaluate finite numerator,
denominator, raw log-risk, and unclamped probability at declared-domain and model-coordinate
assignments while proving changed semantic inputs receive different identities.

### Tests for User Story 1

- [X] T010 [P] [US1] Add compiler tests for current schema-v3/sidecar eligibility, rejection of omitted or legacy-inferred semantics, explicit event/value and retained-feature validation, extra fixed-context rejection, approximation domains, shared source/model digest, common marginalization, explicit learned denominator, max/PWL resolution, max approximate-and-uncertified labelling, PWL weighted-log-sum-exp-approximation labelling, contradictory or missing label rejection, no fallback, and changed-input identities in `tests/unit/tpm/test_conditional_mio.py`
- [X] T011 [P] [US1] Extend pair tests with create/verify/reload behavior, complete semantic round trips including max/PWL approximation and certification labels, corruption and mismatch rejection, unchanged source bytes, and identity changes for event, decision order, validity, encoding, compiler version, and tolerance inputs in `tests/unit/tpm/test_conditional_pair.py`
- [X] T012 [US1] After T010, add direct-evaluator tests for complete declared-domain versus model-coordinate modes, exact max and persisted PWL operation order, closed boundaries, missing/extra/mixed assignments, no interpolation clipping, nonfinite failure, preserved probability underflow, positive numerical-noise classification, materially positive log-risk rejection, and no clamping in `tests/unit/tpm/test_conditional_mio.py`
- [X] T013 [P] [US1] Add one real current-SPFlow fit, schema-v3 persist/reload, raw native numerator/denominator query, max/PWL compile, pair persist/reload, and direct-evaluation path with genuine learned Sum nodes and deliberately nonuniform decision evidence in `tests/integration/tpm/test_conditional_mio_current_spflow.py`

### Implementation for User Story 1

- [X] T014 [US1] Implement lazy eligible-artifact verification, current-SPFlow sidecar loading, retain/marginalize-once graph preparation, single base compilation, numerator/denominator derivation, shared provenance, resolved max/PWL policy, persisted max approximate-and-uncertified and PWL weighted-log-sum-exp-approximation labels, contradictory/missing label rejection, and pair construction in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T015 [US1] Implement selected-semantics conditioned-circuit evaluation for constants, leaves, Products, max Sums, and persisted shift/exp/total/log PWL Sums with strict assignment/domain and raw numerical policies in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T016 [US1] Add an explicit-event current-SPFlow evaluator that verifies pair/source provenance and returns raw numerator log, denominator log, difference, and unclamped probability without compiled or empirical fallback in `src/open_energy_lab/tpm/query.py`
- [X] T017 [US1] Expose the request, pair, persistence, compilation, direct-evaluation, and explicit native-evaluation public surface through lazy TPM exports; prove core imports remain usable without SPFlow and compilation/native calls fail with clear dependency diagnostics when SPFlow is absent in `src/open_energy_lab/tpm/__init__.py`, `tests/unit/tpm/test_package_surface.py`, and `tests/unit/tpm/test_import_boundary.py`
- [X] T018 [US1] Add deterministic maintainer staging and verify-only modes for the reviewed source artifact and current-SPFlow sidecar only, without publishing the final mixed conditional pairs before discrete support exists, in `examples/tpm_planning/run_conditional_mio_embedding.py`, `tests/fixtures/tpm/tpm_artifact_conditional_mio_v3.json`, and `tests/fixtures/tpm/sidecars/tpm_artifact_conditional_mio_v3.spn_payload.pkl`
- [X] T019 [US1] Run the US1 slice from `specs/016-conditional-mio-embedding/quickstart.md` covering temporary max/PWL pair persist-reload in `test_conditional_pair.py`, `test_conditional_mio.py`, and `test_conditional_mio_current_spflow.py`, then update the source artifact/sidecar digests, backend/compiler versions, and verified commands in `tests/fixtures/tpm/README.md`

**Checkpoint**: User Story 1 independently supplies an immutable, explicit-denominator conditional
pair and exact selected-semantics direct/native evidence without Pyomo composition.

---

## Phase 4: User Story 2 — Attach Continuous Risk to a Caller Model (Priority: P1)

**Goal**: Attach an unchanged pair to a caller-owned continuous variable or structurally affine
expression in physical units, returning composable roots and log-risk while leaving caller policy
outside OEL.

**Independent Test**: Build a caller Pyomo model with a continuous affine expression, attach a pair
under one namespace, verify physical/model-coordinate links and inclusive validity constraints, and
add a caller objective, unrelated deterministic constraint, alpha, and log-risk constraint without
OEL creating any of them.

### Tests for User Story 2

- [X] T020 [P] [US2] Add continuous mapping and attachment contracts for scalar variables, multivariable affine expressions, fixed continuous variables, fixed parameters, constant-only rejection, exact mapping coverage, U-Bounds normalization, inclusive approximation boundaries, returned roots/links/log-risk, and absence of OEL policy components in `tests/unit/tpm/test_conditional_attachment.py`
- [X] T021 [P] [US2] Add structural preflight tests that reject fixed-variable nonlinear products, general integer or binary variables hidden in affine-looking expressions, unfixed parameters, nonfinite coefficients, foreign-model variables, non-scalar mappings, and invalid namespaces before model mutation in `tests/unit/tpm/test_conditional_attachment.py`
- [X] T022 [P] [US2] Add a small consumer-owned Pyomo composition check that constructs an unrelated objective, deterministic constraint, alpha, and conditional log-risk constraint while decisions remain unfixed, assigns finite diagnostic values without fixing or changing their domains, numerically evaluates the caller-owned expressions, and proves OEL did not create those policy components in `tests/integration/tpm/test_conditional_mio_highs.py`

### Implementation for User Story 2

- [X] T023 [US2] Add import-light typed continuous mapping and frozen attachment-result metadata records with strict complete-coverage validation in `src/open_energy_lab/tpm/conditional.py`
- [X] T024 [US2] Implement lazy structural affine-expression inspection that includes fixed variables, checks target-model ownership and continuous domains without mutating caller state, and rejects constant-only/nonlinear/integer/binary forms in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T025 [US2] Factor reusable conditioned-circuit Pyomo encoding for shared caller-supplied model coordinates, selected max/PWL semantics, roots, auxiliaries, and residual metadata without adding decisions or policy in `src/open_energy_lab/tpm/mio.py`
- [X] T026 [US2] Implement full continuous attachment preflight and one detached namespaced Pyomo Block with physical/model links, closed validity constraints, numerator/denominator subblocks, and conditional-log-risk Expression in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T027 [US2] Expose continuous mapping and attachment behavior lazily, prove core imports remain usable without Pyomo and attachment calls fail with a clear dependency diagnostic when Pyomo is absent, run the US2 unit and consumer-composition slices, and resolve package-surface regressions in `src/open_energy_lab/tpm/__init__.py`, `tests/unit/tpm/test_package_surface.py`, `tests/unit/tpm/test_import_boundary.py`, and `tests/integration/tpm/test_conditional_mio_highs.py`

**Checkpoint**: User Stories 1 and 2 allow a caller to compose continuous symbolic risk with its own
model policy; no fixed-assignment solver-parity claim is made yet.

---

## Phase 5: User Story 3 — Compose Binary and Categorical Decisions (Priority: P1)

**Goal**: Add caller-owned binary and ordered categorical one-hot decisions to the same symbolic
conditional pair without recreating decisions or enumerating a Cartesian risk table.

**Independent Test**: Attach the reviewed mixed pair to one caller binary variable and a complete
ordered categorical indicator vector, exercise both binary states and representative categories,
and verify ordering, exactly-one enforcement, joint mixed-type roots, and absence of lookup-table
enumeration.

### Tests for User Story 3

- [X] T028 [P] [US3] Add binary and categorical mapping contracts for declared binary-value ordering, labelled persisted category ordering, distinct binary indicators, exactly-one ownership, complete mixed-type coverage, positive reuse of valid indicators that already participate in caller-owned constraints, and rejection of missing, duplicate, reordered, extra, nonbinary, or foreign-model indicators in `tests/unit/tpm/test_conditional_attachment.py`
- [X] T029 [P] [US3] Add direct-evaluation contracts for declared binary/category values, model-coordinate indices, invalid indices/labels, mixed supported feature types, and symbolic graphs with no Cartesian lookup payload in `tests/unit/tpm/test_conditional_mio.py`
- [X] T030 [P] [US3] Extend the real mixed current-SPFlow path to attach both binary states and representative categorical values in one conditional pair without evaluating the full Cartesian product in `tests/integration/tpm/test_conditional_mio_current_spflow.py`

### Implementation for User Story 3

- [X] T031 [US3] Add import-light typed binary and ordered labelled categorical one-hot mapping records with exact declared-order and distinct-indicator invariants in `src/open_energy_lab/tpm/conditional.py`
- [X] T032 [US3] Implement binary/categorical model-ownership and domain preflight, declared-value/index translation, complete mixed-type mapping validation, and categorical exactly-one construction in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T033 [US3] Extend conditioned-circuit direct and Pyomo encoding to reference caller-owned binary/one-hot inputs symbolically, preserve one joint numerator/denominator pair, and bypass the existing categorical Cartesian lookup shortcut in `src/open_energy_lab/tpm/mio.py` and `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T034 [US3] After T033, extend `examples/tpm_planning/run_conditional_mio_embedding.py` deterministic staging/verification to compile and publish the final mixed max/PWL pairs at `tests/fixtures/tpm/conditional_pair_max_v1.json` and `tests/fixtures/tpm/conditional_pair_pwl_v1.json`, then run the US3 slices from `specs/016-conditional-mio-embedding/quickstart.md` and verify both immutable pairs retain joint continuous/binary/categorical semantics with no enumerated decision table

**Checkpoint**: One conditional pair can jointly retain all three supported decision forms and
attach them symbolically to caller-owned variables.

---

## Phase 6: User Story 4 — Distinguish Solver Parity from Compiler Fidelity (Priority: P1)

**Goal**: Evaluate fixed caller assignments through Pyomo/HiGHS, gate only direct-versus-attached
embedding parity, and retain current-SPFlow compiler-fidelity discrepancies separately without an
adequacy threshold.

**Independent Test**: For both max and PWL at the predeclared lower, interior, and upper mixed
assignments, solve objective-free attached models with HiGHS, match both roots, log-risk, and local
residuals to direct selected-semantics evaluation within $10^{-6}$, and separately retain all four
native/compiler discrepancies.

### Tests for User Story 4

- [X] T035 [P] [US4] Add post-solve inspector and evidence-metric tests for attachment-local equality/inequality violation magnitudes, roots, raw log-risk/probability, solver status, finite checks, $10^{-6}$ parity gates, positive-noise classification, and separate parity/fidelity schemas in `tests/unit/tpm/test_conditional_evidence.py`
- [X] T036 [P] [US4] Add max and PWL objective-free Pyomo/HiGHS parity tests at the predeclared lower/interior/upper mixed assignments and one required uninterrupted real-backend case that fits, persists, reloads, natively queries, compiles, persists/reloads the same pair, directly evaluates, attaches, fixes caller decisions, and solves with HiGHS; retain solver termination, roots, risk, and attachment-local residuals in `tests/integration/tpm/test_conditional_mio_highs.py`
- [X] T037 [P] [US4] Add native-current-SPFlow fidelity tests retaining numerator-log, denominator-log, conditional-log-risk, and probability differences without an adequacy gate or clamping in `tests/integration/tpm/test_conditional_mio_current_spflow.py`

### Implementation for User Story 4

- [X] T038 [US4] Implement read-only post-solve attachment inspection with caller-supplied solver metadata, raw roots/risk/probability, active attachment-only constraint violations, and numerical classifications in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T039 [US4] Add immutable embedding-parity and compiler-fidelity record types, canonical identities, strict validation, and create-or-verify persistence separate from conditional-pair bytes in `src/open_energy_lab/tpm/conditional.py`
- [X] T040 [US4] Implement parity and fidelity evidence builders that compare identical compiled semantics for solver parity, compare the exact source artifact for native fidelity, retain signed/raw values, and never invoke a solver or impose a native adequacy threshold in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T041 [US4] Extend the fixture command to run the representative direct/native/HiGHS cases, prove pair bytes and IDs are unchanged, and publish separate reviewed evidence in `examples/tpm_planning/run_conditional_mio_embedding.py` and `tests/fixtures/tpm/conditional_mio_evidence_v1.json`
- [X] T042 [US4] Expose inspector and evidence behavior lazily with public-surface tests in `src/open_energy_lab/tpm/__init__.py`, `tests/unit/tpm/test_package_surface.py`, and `tests/unit/tpm/test_import_boundary.py`
- [X] T043 [US4] Run the US4 unit, current-SPFlow, HiGHS, and fixture-verification commands from `specs/016-conditional-mio-embedding/quickstart.md`, treating embedding disagreement as failure while retaining unfavorable native/compiler values as evidence

**Checkpoint**: The feature can now locate an error in the embedding/solver layer separately from
the compiler-approximation layer, with both pair and evidence identities auditable.

---

## Phase 7: User Story 5 — Attach Safely and Reuse Auditable Evidence (Priority: P2)

**Goal**: Harden create-only reuse, namespace isolation, atomic attachment, immutable evidence, and
existing whole-model compatibility so failures cannot corrupt caller models or prior records.

**Independent Test**: Reload and verify a pair, attach it under two distinct namespaces, reject
concurrent publication conflicts, duplicate namespaces, invalid mappings, and injected component
construction failures, and prove pair bytes, evidence files, caller components, and established
whole-model behavior remain unchanged.

### Tests for User Story 5

- [X] T044 [P] [US5] Extend pair/evidence tests with recursive mutation attempts, concurrent identical/conflicting publication, incomplete targets, unwritable destinations, changed-input non-overwrite behavior, and byte-stable evaluation reuse in `tests/unit/tpm/test_conditional_pair.py`
- [X] T045 [P] [US5] Extend attachment tests with two isolated namespaces, duplicate/unrelated component collisions, missing/duplicate/extra mappings, invalid pair/domain inputs, injected detached-build/final-add failures, exact rollback, and caller component snapshots in `tests/unit/tpm/test_conditional_attachment.py`
- [X] T046 [P] [US5] Add compatibility regressions proving existing whole-model compilation, categorical lookup compatibility, planning payloads, and public entry points retain their established behavior in `tests/unit/tpm/test_mio.py`, `tests/unit/planning/test_piecewise.py`, and `tests/integration/planning/test_problem_assembly.py`

### Implementation for User Story 5

- [X] T047 [US5] Add adversarial hardening beyond T007 for concurrent final-name appearance after preflight, simultaneous identical/conflicting publishers, injected write/link/fsync failures, directory durability, abandoned temporary files, and nested mutation attempts while preserving verified identical reuse in `src/open_energy_lab/tpm/conditional.py`
- [X] T048 [US5] Harden complete preflight, detached-block construction, one final component add, exact rollback, repeated distinct attachment, and collision diagnostics without deleting caller-owned components in `src/open_energy_lab/tpm/conditional_mio.py`
- [X] T049 [US5] Resolve only compatibility regressions exposed by T046 in existing whole-model and planning adapters, without adding a second conditioner or routing established public entry points through the new composable contract, in `src/open_energy_lab/tpm/mio.py`, `src/open_energy_lab/planning/piecewise.py`, and `src/open_energy_lab/planning/problem.py`
- [X] T050 [US5] Extend fixture verification with corruption/mismatch cases, immutable source/pair/evidence snapshots, repeated verified reuse, and failure-without-repair behavior in `examples/tpm_planning/run_conditional_mio_embedding.py`
- [X] T051 [US5] Run the US5 persistence, atomicity, existing TPM/planning compatibility, and verify-only fixture slices from `specs/016-conditional-mio-embedding/quickstart.md` and confirm no compatibility fixture was rewritten

**Checkpoint**: Conditional pairs and evidence are safely reusable, multiple attachments coexist,
and rejected operations leave caller models and prior evidence intact.

---

## Phase 8: User Story 6 — Review the Composition Boundary Offline (Priority: P3)

**Goal**: Provide a thin, self-contained, public-API notebook that explains and demonstrates the
composition boundary offline without implementing compiler behavior or regenerating evidence.

**Independent Test**: Execute the output-free notebook headlessly with network access blocked in the
locked CPU environment and verify it loads reviewed fixtures, demonstrates max/PWL plus all mapping
forms, distinguishes parity from fidelity, and leaves notebook and evidence bytes unchanged.

### Tests for User Story 6

- [X] T052 [P] [US6] Add notebook source contracts for output-free cells, required mathematical/ownership explanations, public OEL imports, fixture-only usage, all three mapping forms, max/PWL, parity-versus-fidelity labels, and prohibited fitting/regeneration/compiler/grid/benchmark code in `tests/unit/tpm/test_conditional_mio_notebook.py`
- [X] T053 [P] [US6] Add blocked-network headless execution through a copied local kernel, semantic result markers, source-byte preservation, and fixture-byte preservation in `tests/integration/tpm/test_conditional_mio_notebook_execution.py`
- [X] T054 [P] [US6] Add CI contract tests requiring a Python 3.11 notebook job with locked `dev` and `notebook` groups while keeping notebook execution out of the Python 3.11-3.14 backend matrix in `tests/unit/test_ci_workflow.py`

### Implementation for User Story 6

- [X] T055 [US6] Create the thin output-free walkthrough with numerator/denominator density meaning, explicit learned denominator, caller/OEL ownership, continuous affine, binary, and ordered categorical mappings, representative max/PWL fixed solves, separate parity/fidelity presentation, and an unsolved caller-policy composition in `examples/tpm_planning/conditional_mio_embedding_walkthrough.ipynb`
- [X] T056 [US6] Document notebook kernel setup, offline execution, reviewed fixture provenance, expected sections, and the no-regeneration/no-benchmark boundary in `examples/tpm_planning/README.md`
- [X] T057 [US6] Add the required locked Python 3.11 headless notebook job to `.github/workflows/ci.yml`, explicitly verify installed SPFlow, Pyomo, HiGHS availability, and notebook dependencies before testing, run both notebook test files through the `notebook` group, and resolve the fail-closed CI assertions in `tests/unit/test_ci_workflow.py`

**Checkpoint**: A reviewer can understand and execute the complete composition example without
reading compiler internals, while tests and persisted evidence remain authoritative.

---

## Phase 9: Polish and Cross-Cutting Validation

**Purpose**: Document the public capability, validate lazy boundaries, and execute the complete
offline acceptance surface without changing dependencies or the parent repository.

- [X] T058 [P] Document conditional meaning, pair lifecycle, public compilation/evaluation/attachment flow, mapping forms, caller ownership, numerical policy, parity/fidelity separation, compatibility, and migration limitations in `docs/migration/conditional-mio-embedding.md`
- [X] T059 [P] Extend package-wide isolated-process checks proving core imports succeed without SPFlow, Pyomo, HiGHS, or notebook packages while the corresponding compilation/native-query, attachment, required-solver validation, and notebook execution paths fail clearly without fallback; retain public-contract and no-legacy checks in `tests/unit/test_lazy_dependency_boundaries.py`, `tests/unit/test_import_contract.py`, and `tests/unit/test_no_legacy_imports.py`
- [X] T060 Run the fixture verification, focused unit, real current-SPFlow, Pyomo/HiGHS, notebook, and full TPM/planning regression commands from `specs/016-conditional-mio-embedding/quickstart.md`, resolving all failures in the files named by the failing checks
- [X] T061 Run `uv lock --check`, the offline import smoke, no-legacy `rg`, `git diff --check`, and `git status --short`; record the executed commands and any genuine environmental limitation without weakening acceptance in `specs/016-conditional-mio-embedding/quickstart.md`
- [X] T062 Audit `tests/fixtures/tpm/README.md`, every conditional source/artifact/pair/evidence fixture under `tests/fixtures/tpm/`, OEL `git status`, and the parent repository status to confirm complete provenance, no unexpected lock/dependency change, no generalized artifact framework, and no parent file or gitlink commit in this feature

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: Starts immediately.
- **Phase 2 (Foundational)**: Depends on the fixture vocabulary from Phase 1.
- **US1 (Phase 3)**: Depends on Phase 2 and establishes the pair, compiler, direct evaluator, and
  real source artifact required by every later story.
- **US2 (Phase 4)**: Depends on US1 and establishes continuous caller-owned attachment.
- **US3 (Phase 5)**: Depends on US1 and US2 because it extends the same mapping, encoder, and
  attachment block to discrete decisions.
- **US4 (Phase 6)**: Depends on US1-US3 so parity exercises one mixed pair and all supported mapping
  forms. Its evidence records do not alter those stories' pair contract.
- **US5 (Phase 7)**: Depends on US1-US4 and hardens reuse, rollback, and compatibility around the
  complete capability.
- **US6 (Phase 8)**: Depends on US1-US5 and their reviewed fixtures/evidence.
- **Polish (Phase 9)**: Depends on all user stories.

### User-story dependency graph

```text
Setup → Foundational → US1 → US2 → US3 → US4 → US5 → US6 → Polish
```

The delivery sequence is intentionally linear at the story boundary because later stories reuse
the exact pair, mapping, attachment, and evidence surfaces established earlier. Parallel work is
available inside each phase as described below.

### Within each user story

1. Add the listed unit/integration contracts before implementation where practical.
2. Implement import-light records before lazy backend adapters.
3. Keep compiler/evaluator behavior stable before publishing derived fixtures.
4. Generate or verify evidence only after the story's semantics pass in temporary outputs.
5. Run the story's focused command and resolve failures before its checkpoint.

---

## Parallel Execution Examples

### Setup and Foundational

After T001 fixes the source vocabulary, T002 and T003 may proceed on documentation and test support.
In Phase 2, T004 and T005 can establish record and circuit contracts in parallel; implementation is
sequential through T006-T009 because identity, persistence, conditioning, and planning delegation
build on one another.

### User Story 1

T010, T011, and T013 can proceed in parallel across compiler, pair, and real-backend test files;
T012 follows T010 in `test_conditional_mio.py`. T014-T016 are sequential semantic implementation in
shared TPM modules; T017 can update lazy exports after those names stabilize, and T018 waits for the
complete compile/evaluate path.

### User Story 2

T020 and T021 share `test_conditional_attachment.py` and should be written sequentially; T022 may be
prepared in parallel in the integration file. T023-T026 then proceed in dependency order from
records through validation, encoding, and final attachment.

### User Story 3

T028-T030 can proceed in parallel across attachment, evaluator, and real-backend tests. T031 defines
mapping records before T032 validates them, and T033 then connects them to shared direct/Pyomo
encoding.

### User Story 4

T035-T037 can proceed in parallel across unit, HiGHS, and current-SPFlow evidence tests. T038-T040
then implement inspection, records, and evidence builders in order; T041 publishes evidence only
after all three are stable.

### User Story 5

T044-T046 can proceed in parallel across pair, attachment, and compatibility tests. T047-T049 touch
overlapping source responsibilities and should remain sequential; T050 then validates immutable
reuse against the finished behavior.

### User Story 6

T052-T054 can proceed in parallel across notebook source, execution, and CI contract tests. T055 and
T056 may then proceed in parallel on the notebook and README; T057 updates CI after test names and
dependency requirements are final.

### Polish

T058 and T059 can proceed in parallel on migration documentation and package-wide boundary tests.
T060-T062 are sequential final validation and audit tasks.

---

## Implementation Strategy

### MVP first

1. Complete Setup and Foundational phases.
2. Complete User Story 1.
3. Stop and review the explicit learned denominator, pair identity, max/PWL selected-semantics
   evaluator, and real current-SPFlow source before adding Pyomo attachment.

This is the smallest independently useful MVP: researchers can compile, audit, persist, reload, and
directly evaluate a reusable conditional numerator/denominator pair without uniform-denominator
assumptions or enumeration.

### Incremental delivery

1. **US1**: Immutable solver-neutral pair plus direct/native evaluation.
2. **US2**: Continuous caller-owned Pyomo composition and policy ownership.
3. **US3**: Joint binary and ordered categorical symbolic composition.
4. **US4**: Objective-free HiGHS parity separated from native compiler fidelity.
5. **US5**: Race-safe persistence, atomic attachment, namespace isolation, and compatibility.
6. **US6**: Offline public-API notebook and required headless CI.
7. **Polish**: Migration guidance and complete locked validation.

### Scope controls

- Do not add benchmark objectives, operational thresholds, decision optimization, Figure 1
  qualification, risk tables, fixed context, multiple events, general integers, or new fitting
  experiments.
- Do not add new max/PWL mathematics, breakpoint search, scientific tuning, selectivity
  certification, large parity grids, solver-option bundles, retry machinery, or a generalized
  artifact framework.
- Do not add a commercial solver, GPU/device work, network dependency, unconditional heavy import,
  new project dependency, or lockfile update unless a separately reviewed scope change requires it.
- Do not modify `legacy/*`, the parent paper repository, or the parent OEL gitlink in this feature.

## Notes

- Tasks marked `[P]` touch distinct files, or are independent test preparations in distinct test
  files, after their phase prerequisites are complete.
- When two tasks name the same file, execute them sequentially even if their surrounding phase has
  other parallel work.
- Required current-SPFlow, Pyomo, HiGHS, and notebook checks fail when their locked environment is
  incomplete; they do not silently skip or fall back.
- Every generated artifact retains source rows/configuration, fit seed/options, backend/compiler
  versions, pair/evidence identity, encoding, domains, assignments, and purpose-labelled tolerances.
