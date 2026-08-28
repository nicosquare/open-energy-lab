# Tasks: FCR Rolling Backtest Parity

**Input**: Design documents from `/specs/015-fcr-rolling-backtest-parity/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Tests**: The specification requires test-first validation at equation,
bounded-solver, common-replay, normalized-source, benchmark, and optional
external-data levels. Test tasks precede implementation in each story whenever
practical.

**Organization**: Tasks are grouped by user story. The shared Feature 012
segmentation boundary and Feature 013 private refactor are foundational because
causal bidding, midnight carry-over, source comparison, and common replay all
depend on them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to execute in parallel because it changes different files and
  has no dependency on another incomplete task in the same phase
- **[Story]**: User story from `spec.md`
- Every checklist item names the exact file or directory it changes or verifies

---

## Phase 1: Setup

**Purpose**: Establish Feature 015's source, example, fixture, and documentation
surfaces without changing dependencies or writing into the reference baseline.

- [X] T001 Create the Feature 015 example package and document its offline, no-baseline-runtime scope in `examples/fcr_rolling_backtest/README.md`
- [X] T002 [P] Create the normalized-fixture governance scaffold and redistribution limits in `tests/fixtures/fcr_rolling_backtest/README.md`
- [X] T003 [P] Add deterministic raw authored battery, price, date, activation, and solver-policy builders using only existing public contracts in `tests/fcr_rolling_case_utils.py`
- [X] T004 [P] Create the migration evidence ledger with the exact source citation map and initial no-Table-A1/no-optimality claims in `docs/migration/fcr-rolling-backtest-parity.md`

---

## Phase 2: Foundational Boundaries and Regression Protection

**Purpose**: Protect Feature 013 compatibility and add the reusable Feature 012
segmentation primitives required by multiple user stories.

**Critical**: Do not implement rolling orchestration until these regression and
ownership boundaries are in place.

### Tests first

- [x] T005 [P] Add regression assertions for Feature 013's existing 24/96/6 validation, public decisions, schedule fingerprints, result fingerprints, and deployability behavior in `tests/unit/control/test_robust_fcr_problem.py`, `tests/unit/control/test_robust_fcr_solver.py`, and `tests/integration/control/test_robust_fcr_highs.py`
- [x] T006 [P] Add half-open activation slicing tests for exact coverage, cutoff-boundary ownership, provenance, fingerprints, and invalid gaps in `tests/unit/market/test_activation.py`
- [x] T007 [P] Add failing accepted-plan market-context and segmented-evaluation tests covering assumed/evidence-backed acceptance, EUR/kWh-to-EUR/MWh conversion, exact segment partitions, state reconciliation, and delegation to Feature 012 in `tests/unit/simulator/test_fcr_rolling_evaluation.py`
- [x] T008 [P] Add failing lazy-import and forbidden-boundary tests for the planned rolling control, market, and simulator modules in `tests/unit/control/test_fcr_rolling_import_boundary.py`

### Shared implementation

- [x] T009 Refactor reusable normalized index, variable, objective, constraint-family, and witness-audit helpers without changing ordinary-day equations in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [x] T010 Refactor reusable backend loading, status normalization, incumbent extraction, decision canonicalization, and plan-mapping helpers without changing Feature 013 results in `src/open_energy_lab/control/_robust_fcr_solver.py` and `src/open_energy_lab/control/robust_fcr_bidding.py`
- [x] T011 [P] Implement exact half-open `slice_regulation_activation_trace` with detached samples and retained source lineage in `src/open_energy_lab/market/activation.py`
- [x] T012 [P] Add the explicit accepted-plan market context, reject system-volume-as-individual-acceptance evidence, and preserve existing context kinds in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [x] T013 Implement `FCRAcceptedPlanSegment`, `FCRSegmentedEvaluationReport`, plan/schedule slicing, fresh-battery segment construction, Feature 012 delegation, and deterministic reconciliation in `src/open_energy_lab/simulator/fcr_rolling_evaluation.py`
- [x] T014 Add lazy public exports for activation slicing and segmented evaluation without eager solver or pandas imports in `src/open_energy_lab/market/__init__.py` and `src/open_energy_lab/simulator/__init__.py`
- [x] T015 Run the protected Feature 012/013 unit and integration selections and record the unchanged golden fingerprints in `docs/migration/fcr-rolling-backtest-parity.md`

**Checkpoint**: Existing Feature 013 evidence is unchanged, and partial/full
accepted-plan replay is available solely by composing Feature 012.

---

## Phase 3: User Story 1 - Reproduce the Five Non-Intraday Profiles (Priority: P1)

**Goal**: Provide one immutable study interface that selects exactly one of the
five executable profiles and produces ordered date envelopes with the correct
formulation, FCR, reset/coupling, cutoff, and classification semantics.

**Independent Test**: Construct and solve one bounded authored problem per
profile without baseline files and verify 5/5 profile identities, formulation
classifications, FCR behavior, required coupling inputs, plan classifications,
date roles, and ordered envelope structure. T041 and T050 independently complete
the causal 08:00 and realized midnight chains.

### Tests first

- [x] T016 [P] [US1] Add failing manifest tests for immutable descriptors, exactly one profile, ordered ordinary dates, roles versus lifecycle, separate decision/information cutoffs, battery binding, uncertainty/terminal/solver policies, failure-propagation policy, aggregation policy, resume policy, accepted-bid policy, normalized-reference-lineage policy, provenance, fingerprints, and rejection of new RTE/ENTSO-E document kinds in `tests/unit/control/test_fcr_rolling_manifest.py`
- [x] T017 [P] [US1] Add failing executable-profile crosswalk tests for scripts/results 11/01 through 15/05, paper mapping 1/2/4/5/3, workbook columns 11/12/14/15/13, and the no-Table-A1 rule in `tests/unit/control/test_fcr_rolling_source_documentation.py`
- [x] T018 [P] [US1] Add hand-calculable rolling optimization tests for no-FCR assembly, `K_lower=-63`, 40/160/10 dimensions, 16/4 predecessor fixings, fixed-tail objective separation, terminal mapping, and charge-positive extraction in `tests/unit/control/test_fcr_rolling_orchestration.py`
- [x] T019 [P] [US1] Add deterministic bounded Pyomo/HiGHS tests for relaxation, restriction, exact-zero-FCR, midnight-coupled restriction, 08:00 fixed overlap, infeasibility, fingerprinted feasible-incumbent continuation, and repeatability in `tests/integration/control/test_fcr_rolling_highs.py`

### Implementation

- [x] T020 [US1] Implement frozen data descriptors, date classification, numeric policy, battery binding, failure-propagation policy, aggregation policy, resume policy, accepted-bid policy, normalized-reference-lineage policy, and the five versioned executable profiles in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T021 [US1] Implement `RollingFCRStudyManifest` and `RollingFCRDayInput` builders with strict 24/96/6 ordinary-day, unit/sign, separate decision/information cutoff, one-profile, all five required manifest policies, provenance, fingerprint, and bidder-visible-field validation in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T022 [US1] Implement core immutable day revision, date envelope, state-link, continuity-segment, aggregate-evidence, and study-result value objects with canonical serialization in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T023 [US1] Implement `RobustFCRAcceptedDecisionFixings`, `RobustFCRRollingBiddingProblem`, `RobustFCRRollingSolveResult`, and the rolling problem builder in `src/open_energy_lab/control/robust_fcr_rolling.py`
- [x] T024 [US1] Add the source-compatible 24-hour arbitrage-only assembly that constrains all six output FCR decisions exactly to zero regardless of prices in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [x] T025 [US1] Add the 40-hour `-63..96` robust assembly, signed hourly/FCR mappings, predecessor price tail, exact accepted-decision fixings, propagated robust state bounds, and fixed-tail objective component in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [x] T026 [US1] Implement lazy `solve_robust_fcr_rolling_bid` status handling, complete witness extraction, independent audit, objective/bound/gap evidence, and deterministic semantics in `src/open_energy_lab/control/robust_fcr_rolling.py` and `src/open_energy_lab/control/_robust_fcr_solver.py`
- [x] T027 [US1] Implement current-day 24/6 extraction with robust-candidate, feasible-incumbent, diagnostic-non-robust, and arbitrage-only plan classifications in `src/open_energy_lab/control/robust_fcr_rolling.py`
- [x] T028 [US1] Implement ordinary reset-day restriction/relaxation dispatch through `solve_robust_fcr_bid` and preserve failed dates in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T029 [US1] Implement initial profile dispatch for exact-zero-FCR, midnight-coupled, and 08:00 rolling requests without importing activation into bid construction in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T030 [US1] Implement initial `run_rolling_fcr_study` assembly for bounded profile problems supplied with valid coupling inputs, retaining one ordered envelope per requested date plus explicit role/lifecycle applicability while deferring causal 08:00 transitions to T039–T040 and realized midnight links to T045–T049 in `src/open_energy_lab/control/fcr_rolling_backtest.py` and `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T031 [US1] Add all Feature 015 control symbols through the existing lazy export map without expanding the root package API in `src/open_energy_lab/control/__init__.py`
- [x] T032 [US1] Complete five bounded profile-level assertions for formulation construction, required coupling inputs, plan classification, and ordered envelope structure, record the exact 5/5 evidence, and defer complete causal 08:00 and realized midnight chains to T041 and T050 in `tests/integration/control/test_fcr_rolling_highs.py` and `docs/migration/fcr-rolling-backtest-parity.md`

**Checkpoint**: Five separate manifests construct and solve the five bounded
profile/formulation families and return correctly classified, ordered evidence
without source runtime access; complete rolling chains remain gated by US2 and
US3.

---

## Phase 4: User Story 2 - Preserve Causal 08:00 Bidding (Priority: P1)

**Goal**: Reproduce source 08:00 overlap and immutable finalization while making
future activation structurally unavailable to bid selection.

**Independent Test**: Two traces equal through 08:00 and different afterward
produce identical cutoff state, fixings, rolling problem, and selected-plan
fingerprints; initialization and unfinalized edges remain explicit.

### Tests first

- [x] T033 [P] [US2] Add failing oracle tests for source bootstrap, listed-date predecessor semantics, exact 09–24 hourly and block 3–6 fixings, predecessor price-tail mapping, and fixed-tail objective accounting in `tests/unit/control/test_fcr_rolling_orchestration.py`
- [x] T034 [P] [US2] Add a causal twin-trace integration test proving post-08:00 activation changes zero cutoff, problem, fixing, decision, or plan fingerprints in `tests/integration/simulator/test_fcr_rolling_feature_012_replay.py`
- [x] T035 [P] [US2] Add guarded post-cutoff access, exact-boundary sample ownership, missing-prefix, saturation, and invalid-checkpoint tests in `tests/integration/simulator/test_fcr_rolling_feature_012_replay.py`

### Implementation

- [x] T036 [US2] Implement extraction and validation of unchanged full-precision accepted predecessor decisions with signed interval identities and plan/problem/result lineage in `src/open_energy_lab/control/robust_fcr_rolling.py`
- [x] T037 [US2] Implement causal 00:00–08:00 Feature 012 prefix replay, full-precision checkpoint evidence, and required three-decimal handed-off state in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T038 [US2] Implement successor 40-hour construction using only pre-cutoff state, accepted fixings, declared prices, and bidder-visible provenance in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T039 [US2] Implement immutable original, provisional, and successor-finalized evaluation revisions while retaining the unchanged original full-day plan in `src/open_energy_lab/control/fcr_rolling_backtest.py` and `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T040 [US2] Implement initialization-only first-date and unfinalized last-date handling plus explicit exclusion from finalized parity aggregates in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T041 [US2] Complete the bounded four-date authored 08:00 chain, causal sentinels, edge statuses, and revision lineage assertions in `tests/integration/simulator/test_fcr_rolling_feature_012_replay.py`

**Checkpoint**: The 08:00 chain is causal, fixes accepted overlap exactly, and
never mutates or silently finalizes source evidence.

---

## Phase 5: User Story 3 - Carry Stored Energy Across Midnight (Priority: P1)

**Goal**: Support source-compatible three-decimal and native full-precision
midnight carry-over as different semantic profiles with auditable state links.

**Independent Test**: A hand-calculable three-day chain reconciles every
realized Feature 012 terminal state to the next initial state under both
policies, produces distinct fingerprints, and blocks invalid predecessors.

### Tests first

- [x] T042 [P] [US3] Add rounding oracles for Decimal-from-string half-even three-place values, midpoint endpoints, signed zero, boundary states, closed source intervals, and full-precision identity in `tests/unit/control/test_fcr_rolling_orchestration.py`
- [x] T043 [P] [US3] Add a three-day midnight replay test for source-rounded and native-full-precision state trajectories, distinct problem/plan/study fingerprints, and modeled-versus-realized terminal separation in `tests/integration/simulator/test_fcr_rolling_feature_012_replay.py`
- [x] T044 [P] [US3] Add coupled-predecessor failure, state mismatch, caller-supplied restart provenance, and no-cross-gap parity tests in `tests/unit/control/test_fcr_rolling_orchestration.py`

### Implementation

- [x] T045 [US3] Implement source-three-decimal and native-full-precision state-carry helpers, rounding evidence, source intervals, and `RollingFCRStateLink` validation in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T046 [US3] Implement midnight replay-terminal handoff and next-day Feature 013 battery construction from realized—not modeled—stored energy in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T047 [US3] Enforce predecessor identity, state applicability, unit, tolerance, and initial-state reconciliation before every coupled solve in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T048 [US3] Implement fingerprinted caller-supplied state validation and new continuity-segment creation without repairing the preceding gap in `src/open_energy_lab/control/fcr_rolling_backtest.py` and `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T049 [US3] Reject full-precision script-14 manifests and give script-15 rounded/full-precision policies distinct manifest, day-input, state-link, and study identities in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T050 [US3] Complete repeatable bounded HiGHS three-day cases for both midnight policies and their blocked/restarted variants in `tests/integration/control/test_fcr_rolling_highs.py`

**Checkpoint**: Every coupled initial state has one valid realized predecessor
or begins an explicitly separate caller-supplied continuity segment.

---

## Phase 6: User Story 4 - Inspect Complete and Resumable Study Evidence (Priority: P1)

**Goal**: Retain every requested date, failure, revision, omission, aggregate,
and resume decision under deterministic semantic identity.

**Independent Test**: A mixed success/failure study produces exact ordered
statuses and partial aggregates; compatible resume matches uninterrupted
execution while every fingerprint-bearing change is rejected.

### Tests first

- [x] T051 [P] [US4] Add failing result-contract tests for deep immutability, revision ordering, explicit unavailable fingerprints, absolute/relative gaps, runtime separation, lifecycle invariants, and exact status counts in `tests/unit/control/test_fcr_rolling_results.py`
- [x] T052 [P] [US4] Add independent-continuation, coupled-blocking, caller-restart, and no-disappearing-date failure tests in `tests/unit/control/test_fcr_rolling_results.py`
- [x] T053 [P] [US4] Add aggregate tests for eligible/contributing/omitted dates, reasons, complete/partial/unavailable coverage, no zero fill, and separate objective/bound/settlement/profit/throughput metrics in `tests/unit/control/test_fcr_rolling_results.py`
- [x] T054 [P] [US4] Add resume tests for exact reuse and mismatches in profile, ordering, solver, numeric, rounding, source, activation, acceptance, settlement, revision, continuity, and carried-state evidence in `tests/integration/control/test_fcr_rolling_resume.py`
- [x] T055 [P] [US4] Add serialization/load tests proving changes to retained volatile start, finish, and duration evidence do not alter semantic identity; execution-host, process-local, and caller-path data cannot enter semantic payloads; and solver version, artifact digest, cutoff, malformed schema, and nested fingerprint changes are detected in `tests/integration/control/test_fcr_rolling_resume.py`

### Implementation

- [x] T056 [US4] Complete strict `to_dict`/`from_dict` validation and nested fingerprint recomputation for revisions, envelopes, state links, continuity segments, aggregates, and study results in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T057 [US4] Implement deterministic per-date exception normalization, independent continuation, coupled blocking, and ordered diagnostics without swallowing process-integrity errors in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T058 [US4] Implement `aggregate_rolling_fcr_records` with status-count reconciliation, exact contributor/omission lineage, coverage labels, and distinct ex-ante/ex-post quantities in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T059 [US4] Implement `assess_rolling_fcr_resume` with fail-closed semantic checks and continuity-state validation in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T060 [US4] Implement strict offline `load_rolling_fcr_study_result` for the v1 result schema without loading paths, environments, solvers, or source artifacts in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T061 [US4] Integrate compatible resume reuse, new-segment caller states, lifecycle finalization, aggregate recomputation, and stable runtime-independent study identity in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T062 [US4] Complete uninterrupted-versus-resumed, tamper, failure propagation, coverage, and status-count integration assertions in `tests/integration/control/test_fcr_rolling_resume.py`

**Checkpoint**: A result is self-auditing for dates, lifecycle, continuity,
coverage, and resume compatibility; no missing work can masquerade as zero.

---

## Phase 7: User Story 5 - Interpret Source Parity Without Overclaiming (Priority: P1)

**Goal**: Normalize and compare the bounded Julia/Gurobi rerun through
field-level precision, feasibility, incumbent, bound, finalization, and
availability evidence without reading baseline artifacts at runtime.

**Independent Test**: Load the committed five-profile/four-date fixture in an
offline process and obtain deterministic field outcomes and overall
compatibility while preserving Feature 013's governed fixture byte-for-byte.

### Tests first

- [x] T063 [P] [US5] Add failing strict fixture-loader tests for schema version, provenance, revision, 5x4 coverage, raw digest manifest, toolchain versions, precision policy, redistribution limits, unknown keys, tampering, and unavailable fields in `tests/unit/control/test_fcr_rolling_reference.py`
- [x] T064 [P] [US5] Add table-driven comparison tests for all nine field outcomes, objective/bound ordering, optimal versus time-limit evidence, alternative-optimum prerequisites, finalization, and compatible/incompatible/incomplete summaries in `tests/unit/control/test_fcr_rolling_reference.py`
- [x] T065 [P] [US5] Add normalizer tests for explicit inputs only, pre-parse digest verification, exact log-run segmentation, JSON/log reconciliation, redaction, deterministic ordering, atomic artifact-only output, and no solver/network/subprocess use in `tests/integration/control/test_fcr_rolling_reference_normalization.py`
- [x] T066 [P] [US5] Add source-documentation tests for all cited Julia line ranges, the script/paper/workbook crosswalk, script-13 time-limit discrepancy, workbook energy-metric mismatch, and prohibited Table A1 claims in `tests/unit/control/test_fcr_rolling_source_documentation.py`
- [x] T067 [P] [US5] Add a guard that records and verifies the existing Feature 013 fixture bytes/fingerprint before and after Feature 015 normalization in `tests/integration/control/test_fcr_rolling_reference_normalization.py`

### Implementation and fixture governance

- [x] T068 [US5] Implement frozen normalized fixture, field-result, comparison, provenance, discrepancy, unavailable-field, and compatibility-summary contracts plus strict offline loading in `src/open_energy_lab/control/fcr_rolling_reference.py`
- [x] T069 [US5] Implement exact-displayed, source-precision, mismatch, unavailable, and incomplete/unfinalized field comparisons with ordered evidence in `src/open_energy_lab/control/fcr_rolling_reference.py`
- [x] T070 [US5] Implement source-incumbent equivalence, improved feasible incumbent within source bound, bound incompatibility, and alternative-optimum eligibility using separate native/source tolerances in `src/open_energy_lab/control/fcr_rolling_reference.py`
- [x] T071 [US5] Implement deterministic overall compatible/incompatible/incomplete derivation while retaining canonically ordered distinct field-evidence bases in `src/open_energy_lab/control/fcr_rolling_reference.py`
- [x] T072 [US5] Implement closed three-decimal interval construction and joint latent formulation/objective/state certification through shared Feature 013 audit helpers in `src/open_energy_lab/control/fcr_rolling_reference.py` and `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [x] T073 [US5] Implement cross-day 08:00 latent-overlap certification, fixed-tail objective comparison, and explicit exact-restart unavailability when hidden full-precision fixings cannot be proved in `src/open_energy_lab/control/fcr_rolling_reference.py`
- [x] T074 [P] [US5] Create the explicit normalization input manifest pinning all 20 generated JSON files, 11 retained logs, cited sources, price/activation descriptors, committed Project/Manifest, workbook, and Feature 013 rerun/original identities in `examples/fcr_rolling_backtest/reference_inputs_v1.json`
- [x] T075 [US5] Implement the no-glob, digest-first, redacting, schema-validating, atomic artifact writer and ordered semantic diff command in `examples/fcr_rolling_backtest/normalize_reference_fixture.py`
- [x] T076 [US5] Run the explicit normalizer against the selected local rerun, review the semantic diff, and deliberately promote only normalized evidence to `tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json`
- [x] T077 [US5] Complete fixture provenance, raw-artifact non-redistribution, source-status, edge-date, precision, Feature 013 cross-check, and refresh instructions in `tests/fixtures/fcr_rolling_backtest/README.md`
- [x] T078 [US5] Assert exact five-profile/four-date normalized coverage, primary 08:00 comparison dates, runtime status evidence, fixture fingerprint, and no raw/external payload leakage in `tests/unit/control/test_fcr_rolling_reference.py`
- [x] T079 [US5] Document the bounded comparison result vocabulary, source-incumbent limits, hidden-fixing limitation, workbook discrepancy, and no-Table-A1 boundary in `docs/migration/fcr-rolling-backtest-parity.md`

**Checkpoint**: Routine source comparison is small, immutable, offline, and
evidence-aware; it never upgrades rounded time-limited output to proven parity.

---

## Phase 8: User Story 6 - Replay and Settle Through One Common Environment (Priority: P2)

**Goal**: Evaluate every eligible robust, diagnostic, and arbitrage-only plan
through Feature 012 while keeping optimization and realized economics separate.

**Independent Test**: An authored multi-day study traces every physical and
financial field to Feature 012, reconciles daily and study totals, and handles
missing or explicitly supplied external activation without hidden lookup.

### Tests first

- [x] T080 [P] [US6] Add full multi-day restriction and arbitrage-only replay tests for physical/report/settlement fingerprints, state reconciliation, daily totals, and aggregate totals in `tests/integration/simulator/test_fcr_rolling_feature_012_replay.py`
- [x] T081 [P] [US6] Add diagnostic relaxation replay tests proving successful realized tracking never changes the non-robust classification in `tests/integration/simulator/test_fcr_rolling_feature_012_replay.py`
- [x] T082 [P] [US6] Add missing-activation tests for independent optimization-only evidence, explicit unavailable replay/settlement/profit fields, and blocked activation-derived successors in `tests/integration/simulator/test_fcr_rolling_feature_012_replay.py`
- [x] T083 [P] [US6] Add the explicitly selected `external_reference_data` test with exact path/digest/coverage validation, actionable absence skip, bounded date slicing with exactly 8,640 ten-second samples per ordinary day, and Feature 012-only source/native replay in `tests/integration/simulator/test_fcr_rolling_external_reference_replay.py`

### Implementation

- [x] T084 [US6] Integrate accepted-plan market contexts and full-day/segmented Feature 012 evaluation into date revisions without importing simulator equations into control in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T085 [US6] Implement distinct optimization-objective, best-bound, settlement-component, realized-profit, directional-FCR-energy, and throughput evidence/aggregates in `src/open_energy_lab/control/fcr_rolling_backtest.py`
- [x] T086 [US6] Enforce diagnostic-non-robust and arbitrage-only evaluation eligibility without relabelling either result as a robust deployable plan in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T087 [US6] Implement explicit unavailable activation/replay/settlement evidence and activation-dependent blocking without filesystem search or substitution in `src/open_energy_lab/control/_fcr_rolling_orchestrator.py`
- [x] T088 [US6] Reuse the existing Feature 012 external activation importer/request builders from the optional test path and keep all CSV location handling out of production code in `tests/integration/simulator/test_fcr_rolling_external_reference_replay.py`
- [x] T089 [US6] Run Feature 012 public compatibility, product separation, settlement, and Feature 015 replay suites and record reconciliation evidence in `docs/migration/fcr-rolling-backtest-parity.md`

**Checkpoint**: Every realized field has Feature 012 lineage, and absent
activation cannot affect ex-ante evidence or be silently replaced.

---

## Phase 9: User Story 7 - Validate the Workflow Offline (Priority: P2)

**Goal**: Provide deterministic routine CI, an explicit full four-date
reference benchmark, optional licensed/external checks, and a resumable
full-history research command.

**Independent Test**: Run the routine gate twice offline with identical
semantic results and zero baseline, Julia, Gurobi, network, credential, or
external-CSV access; collect heavy checks only through their explicit markers.

### Tests first

- [x] T090 [P] [US7] Add network, credential, subprocess/Julia, baseline/raw-artifact, external-path, eager-Pyomo/HiGHS/Gurobi, and future-activation sentinel tests in `tests/unit/control/test_fcr_rolling_import_boundary.py`
- [x] T091 [P] [US7] Add required-backend unavailable/incompatible failures, no solver fallback, deterministic two-run equality, operation counts, and model-cardinality growth tests in `tests/integration/control/test_fcr_rolling_highs.py`
- [x] T092 [P] [US7] Add CI contract tests ensuring bounded rolling tests run in required-backend/offline jobs while `reference_benchmark`, `external_reference_data`, and optional Gurobi remain excluded in `tests/unit/test_ci_workflow.py`
- [x] T093 [P] [US7] Add the complete five-profile/four-date native comparison test under the explicit `reference_benchmark` marker with partial/time-limit evidence retention in `tests/parity/test_fcr_rolling_reference_benchmark.py`

### Workflows and CI

- [x] T094 [P] [US7] Implement the authored five-profile, carry-policy, stop/resume, and deterministic JSON reporting command in `examples/fcr_rolling_backtest/run_authored_study.py`
- [x] T095 [P] [US7] Implement the explicit fixture/date/profile/solver/time-limit/output reference benchmark command with no raw-source discovery in `examples/fcr_rolling_backtest/run_reference_benchmark.py`
- [x] T096 [US7] Add explicit optional Gurobi selection, license/version unavailability reporting, and no fallback to the benchmark command in `examples/fcr_rolling_backtest/run_reference_benchmark.py`
- [x] T097 [US7] Add an explicit full-history manifest, immutable date ordering, resumable output, partial failure retention, and research-only non-release-gating execution while retaining the mandatory accepted-bid policy in `examples/fcr_rolling_backtest/run_reference_benchmark.py`
- [x] T098 [P] [US7] Complete authored, normalization, benchmark, Gurobi, external activation, resume, and full-history usage/evidence limits in `examples/fcr_rolling_backtest/README.md`
- [x] T099 [US7] Add bounded Feature 015 selections to required-backend and offline CI jobs while preserving the existing 120-second focused-test command limits and 15-minute job limits and excluding heavy/optional markers in `.github/workflows/ci.yml`
- [x] T100 [US7] Run the exact routine Feature 015 quickstart gate twice offline and record pass counts plus stable semantic fingerprints in `docs/migration/fcr-rolling-backtest-parity.md`
- [x] T101 [US7] Verify marker collection for the full reference benchmark, external replay, and optional Gurobi paths and document unavailable evidence without executing it as routine acceptance in `docs/migration/fcr-rolling-backtest-parity.md`

**Checkpoint**: Routine validation is deterministic and offline; research-scale
evidence remains explicit, resumable, and visibly optional.

---

## Phase 10: Polish and Cross-Cutting Concerns

**Purpose**: Finish public documentation, fixture indexes, compatibility
guards, and exact validation evidence across all stories.

- [x] T102 [P] Update the root feature index and architecture navigation for the rolling backtest API and ownership boundaries in `README.md` and `docs/architecture/README.md`
- [x] T103 [P] Update migration navigation and maturity classification for Feature 015 in `docs/migration/README.md` and `docs/migration/api-maturity.md`
- [x] T104 [P] Document unchanged required Pyomo/HiGHS pins, optional Gurobi, zero new core dependencies, lazy import boundaries, and research-only artifacts in `docs/migration/dependency-policy.md` and `docs/migration/environment-assumptions.md`
- [x] T105 [P] Add the Feature 015 normalized fixture and source-precision/incumbent evidence rules to `tests/fixtures/README.md`, `docs/migration/fixture-provenance.md`, and `docs/migration/parity-validation.md`
- [ ] T106 Synchronize the implemented public surface and commands with `specs/015-fcr-rolling-backtest-parity/contracts/python-api.md`, both JSON schemas under `specs/015-fcr-rolling-backtest-parity/contracts/`, and `specs/015-fcr-rolling-backtest-parity/quickstart.md`
- [ ] T107 Update lazy export snapshots and package import contracts for all new control, market, and simulator symbols in `tests/unit/control/test_fcr_rolling_import_boundary.py`, `tests/unit/test_lazy_dependency_boundaries.py`, and `tests/unit/test_import_contract.py`
- [ ] T108 Run the exact routine Feature 015 unit/integration command from `specs/015-fcr-rolling-backtest-parity/quickstart.md` and record final results in `docs/migration/fcr-rolling-backtest-parity.md`
- [ ] T109 Run existing Feature 012 and Feature 013 unit/integration suites to confirm evaluator, settlement, 24/96/6, fingerprints, and lazy backend behavior remain unchanged, recording results in `docs/migration/fcr-rolling-backtest-parity.md`
- [ ] T110 Run repository CI, fixture-provenance, migration-policy, import-boundary, and no-legacy/no-baseline contract tests listed in `specs/015-fcr-rolling-backtest-parity/quickstart.md`
- [ ] T111 Run `compileall` and the forbidden-import, activation-leakage, raw-path, network/credential, and external-data static scans from `specs/015-fcr-rolling-backtest-parity/quickstart.md`
- [ ] T112 Exercise explicitly selected optional external/Gurobi checks when locally available, otherwise record actionable skips without weakening routine evidence in `docs/migration/fcr-rolling-backtest-parity.md`
- [ ] T113 Run syntax validation for `specs/015-fcr-rolling-backtest-parity/contracts/fcr-rolling-reference-fixture-v1.schema.json` and `specs/015-fcr-rolling-backtest-parity/contracts/fcr-rolling-study-result-v1.schema.json`, local documentation-link checks for `specs/015-fcr-rolling-backtest-parity/quickstart.md`, `git diff --check`, and final scope/diff review without modifying `baselines/robust_storage_bidding` or `legacy/*`

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: Starts immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks all user stories.
- **User Story 1**: Depends on Phase 2; establishes public rolling profiles,
  solve contracts, and the initial study state machine.
- **User Story 2**: Depends on User Story 1 and completes causal 08:00 behavior.
- **User Story 3**: Depends on User Story 1 and may proceed alongside User Story
  2 after coordinating changes to `_fcr_rolling_orchestrator.py`.
- **User Story 4**: Depends on User Stories 2 and 3 for complete lifecycle and
  state-link semantics.
- **User Story 5**: Depends on User Stories 1 and 4; it may proceed in parallel
  with User Story 6 once normalized result contracts are stable.
- **User Story 6**: Depends on the foundational Feature 012 boundary and User
  Stories 1–4; it may proceed in parallel with User Story 5.
- **User Story 7**: Depends on all functional stories so CI and research
  workflows exercise the final public behavior.
- **Polish**: Depends on all user stories.

### User story dependency graph

```text
Setup -> Foundational -> US1
                           |-> US2 -|
                           |-> US3 -|-> US4 -> US5 -|
                                            -> US6 -|-> US7 -> Polish
```

### Within each user story

1. Write focused failing contract/oracle/integration tests.
2. Implement immutable models and pure validation.
3. Implement solver, replay, orchestration, or comparison behavior.
4. Complete story-level integration evidence.
5. Run the independent test before starting a dependent story.

---

## Parallel Execution Examples

### User Story 1

After Phase 2, one contributor can write manifest/profile tests in
`test_fcr_rolling_manifest.py` while another writes bounded formulation/HiGHS
tests in `test_fcr_rolling_orchestration.py` and `test_fcr_rolling_highs.py`.

### User Story 2

The source-index/fixing oracles in `test_fcr_rolling_orchestration.py` can be
written alongside causal twin-trace and cutoff-guard tests in
`test_fcr_rolling_feature_012_replay.py`.

### User Story 3

Pure Decimal rounding/state-link oracles can be written in parallel with the
Feature 012 three-day replay integration case; implementation changes to the
shared orchestrator remain serialized.

### User Story 4

Result/lifecycle/aggregation unit tests can proceed in parallel with resume and
serialization integration tests before the shared result implementation begins.

### User Story 5

Fixture-loader/comparator unit tests, normalizer isolation tests, source
documentation tests, and the explicit raw input manifest touch different files
and can proceed concurrently.

### User Story 6

Full-day/segmented replay, diagnostic relaxation, missing activation, and
external-data tests can be authored in parallel before orchestration wiring.

### User Story 7

Offline/import sentinels, backend repeatability, CI contracts, benchmark tests,
and the two example commands can be developed concurrently after APIs stabilize.

---

## Implementation Strategy

### MVP first

Complete Phases 1–3. This yields the smallest useful increment: five explicit
executable profile/formulation families, immutable manifests, bounded
profile-level native solver coverage, and ordered study-envelope structure
without runtime baseline access. It does not yet provide complete rolling
studies; do not claim full rolling parity until causal state, carry-over,
lifecycle, and comparison phases are complete.

### Incremental delivery

1. **Profile MVP**: Setup, protect Feature 012/013, and run all five bounded
   native profile families.
2. **Causal rolling core**: Add 08:00 cutoff/fixing/finalization and both
   midnight carry policies.
3. **Research-grade study evidence**: Add failure retention, resume,
   continuity, coverage-labelled aggregates, and deterministic persistence.
4. **Bounded source evidence**: Normalize the 5x4 Julia/Gurobi rerun and add
   precision/incumbent/bound-aware comparison.
5. **Common realized evaluation**: Complete multi-day Feature 012 settlement
   and optional external activation replay.
6. **Operational validation**: Add CI, reference benchmark, optional Gurobi,
   full-history resume workflow, and final documentation.

### Evidence gates

- No production implementation proceeds without its focused failing test or
  explicit existing regression guard.
- Feature 013 fingerprints must remain unchanged after private refactors.
- No routine test reads `baselines/*`, invokes Julia, uses Gurobi, accesses the
  network/credentials, or locates the external activation CSV.
- Only the maintainer normalizer may read digest-pinned generated source files,
  and it writes only beneath ignored `artifacts/` before deliberate promotion.
- The complete four-date native solve stays behind `reference_benchmark`; the
  external activation replay stays behind `external_reference_data`.
- Every story checkpoint must pass independently before dependent work begins.

---

## Notes

- `[P]` tasks are safe only under the file/dependency boundaries stated above.
- No task authorizes edits inside `baselines/robust_storage_bidding` or
  `legacy/*`.
- Raw logs, raw generated JSON, the workbook, and the complete activation CSV
  are never committed into the Open Energy Lab fixture tree.
- A relaxation replay is diagnostic; a source time-limit result is an
  incumbent plus bound; neither is proven robust optimality.
- The 2023-06-20 08:00 delivery record remains unfinalized without a successor
  even though its solve may serve as close-out evidence for 2023-06-19.
