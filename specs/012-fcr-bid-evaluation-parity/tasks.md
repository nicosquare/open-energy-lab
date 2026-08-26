---
description: "Dependency-ordered implementation tasks for FCR bid-evaluation parity"
---

# Tasks: FCR Bid-Evaluation Parity

**Input**: Design documents from `/specs/012-fcr-bid-evaluation-parity/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Tests**: Required by the feature specification. Write the hand-calculable
oracle, contract tests, bounded reference comparisons, offline-data checks, and
Feature 010 regression assertions before or with the corresponding behavior.

**Organization**: Tasks are grouped by the five user stories. Shared plan,
evaluation-context, replay-kernel, serialization, and test-builder work is
foundational. The full external-reference run remains explicitly selected.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to execute in parallel because the task changes different files
  and has no dependency on unfinished work in the same execution group
- **[Story]**: Maps the task to `US1` through `US5`; setup, foundational, and
  polish tasks have no story label
- Every task names the exact file or directory it changes

## Phase 1: Setup

**Purpose**: Establish governed fixture, example, marker, CI, and documentation
surfaces without modifying `baselines/*`, `legacy/*`, or core dependencies.

- [X] T001 [P] Create the Feature 012 fixture policy and layout, including the authored-oracle versus external-only reference boundary and ignored local CSV location, in `tests/fixtures/fcr_bid_evaluation/README.md`
- [X] T002 [P] Create the fixed-plan, full-reference, fixture-refresh, and expected-failure consumer map without executable placeholder imports in `examples/fcr_bid_evaluation/README.md`
- [X] T003 [P] Register the `external_reference_data` pytest marker and exclude it explicitly from the broad routine offline CI job without changing core dependencies in `pyproject.toml` and `.github/workflows/ci.yml`
- [X] T004 [P] Create the Feature 012 ownership, preserve/improve/reject, reference-source, and out-of-scope documentation scaffold in `docs/migration/fcr-bid-evaluation-parity.md`

---

## Phase 2: Foundational Evaluation Boundaries

**Purpose**: Establish shared plan entities, evaluation inputs/results, one
physical replay kernel, canonical fingerprints, test builders, and import
boundaries required by every user story.

**Critical**: User-story implementation is blocked until the existing Feature
010 replay has characterization evidence and this phase passes offline.

- [X] T005 [P] Characterize unchanged Feature 010 request validation, sample ordering, settlement payloads, fixture byte digests, trace fingerprints, and result fingerprints before refactoring in `tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py`
- [X] T006 [P] Add failing tests for `BidPlanProducer`, available/unavailable optimization metrics, ordered plan diagnostics, exact schedule-object references, schedule-only serialization references, cutoff validation, activation look-ahead rejection, and deterministic plan fingerprints in `tests/unit/control/test_fcr_bid_plan.py`
- [X] T007 Implement frozen plan, producer, optimization-metric, diagnostic, serialized schedule-reference, builder, and canonical plan-fingerprint entities in `src/open_energy_lab/control/fcr_bid_plan.py`
- [X] T008 [P] Add failing tests for discriminated evaluation market contexts, plan-to-request schedule integrity, battery mutation detection, evaluation-only activation lineage, component availability, successful/failed report shapes, canonical serialization, and deterministic input/result fingerprints in `tests/unit/simulator/test_fcr_bid_evaluation.py`
- [X] T009 Implement source-independent evaluation market contexts, evaluation request validation, component-availability primitives, successful/failed report base entities, canonical serialization, and input/result fingerprint helpers in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T010 Refactor the existing private physical sample, checkpoint, summary, saturation, and terminal-report path into one source-independent kernel while keeping `StackedServiceReplayRequest`, `replay_stacked_services`, `replay_stacked_services_diagnostic`, default settlement calls, public outputs, and fingerprint payloads unchanged in `src/open_energy_lab/simulator/stacked_service.py`
- [X] T011 Run the characterization and unchanged Feature 010 stacked-service/settlement tests after the kernel refactor and correct only additive/internal behavior in `src/open_energy_lab/simulator/stacked_service.py` and `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T012 [P] Add failing lazy-import and exact-owner tests proving plan/evaluation offline types import no reference CSV, baseline, Julia, solver, notebook, network adapter, or `legacy/*` code in `tests/unit/control/test_import_boundary.py`, `tests/unit/market/test_import_boundary.py`, `tests/unit/simulator/test_import_boundary.py`, `tests/unit/test_import_contract.py`, and `tests/unit/test_lazy_dependency_boundaries.py`
- [X] T013 Publish only approved source-independent plan and evaluator symbols through the existing lazy package-root maps while keeping the external reference loader a focused import in `src/open_energy_lab/control/__init__.py` and `src/open_energy_lab/simulator/__init__.py`
- [X] T014 Create deterministic Feature 010 schedule, battery, activation, price-context, and request builders shared by Feature 012 integration tests in `tests/integration/simulator/fcr_bid_evaluation_fixture_utils.py`

**Checkpoint**: A fixed plan and evaluation request can be constructed and
fingerprinted, and the shared physical kernel preserves all characterized
Feature 010 outputs before story-specific behavior is added.

---

## Phase 3: User Story 1 - Evaluate Any Fixed FCR Bid Plan Consistently (Priority: P1) 🎯 MVP

**Goal**: Evaluate one complete fixed hourly energy plus four-hour FCR plan
through a bidder-independent physical and settlement path with deterministic
daily results.

**Independent Test**: Submit the authored hand-calculable plan through manual,
heuristic, robust, and TPM producer identities; reproduce every physical and
economic value, confirm producer labels do not affect dispatch/economics, and
exercise zero-FCR and zero-energy cases within `1e-6`.

### Tests And Fixture For User Story 1

- [X] T015 [P] [US1] Encode the authored fixed-plan oracle with explicit reference-form `x0`/`xr`, independently authored mapped library schedule values, intervals, battery, prices, activation in both directions, requested combined power, expected samples, stored-energy states, settlement components, directional energy, and fingerprints in `tests/fixtures/fcr_bid_evaluation/manual_fcr_bid_evaluation_v1.json`
- [X] T016 [P] [US1] Add failing unit tests for valid preflight, identical-value producer invariance, absent objective/bound reasons, no activation in producer lineage, zero FCR, zero energy baseline, exact schedule binding, and repeated fingerprints in `tests/unit/simulator/test_fcr_bid_evaluation.py`
- [X] T017 [P] [US1] Add failing tests for the explicit reference settlement profile ID, day-ahead/capacity/delivered-activation formulas, explicit no-rule zero penalty, unavailable intraday/imbalance/degradation/terminal-value components, and `1e-6` total reconciliation in `tests/unit/simulator/test_fcr_reference_settlement.py`
- [X] T018 [US1] Add the failing end-to-end hand oracle that independently asserts `library_baseline_kw = -reference_x0_kw`, unchanged `xr` capacity, `requested_power_kw = library_baseline_kw - activation * library_fcr_capacity_kw`, every sample, checkpoint, energy flow, basic daily metric, settlement component, ordered diagnostic, and repeated fingerprint from `tests/fixtures/fcr_bid_evaluation/manual_fcr_bid_evaluation_v1.json` in `tests/integration/simulator/test_fcr_bid_evaluation_manual.py`

### Implementation For User Story 1

- [X] T019 [US1] Implement deterministic evaluation preflight and the valid fixed-plan adapter into the shared physical kernel, including exact schedule/context/time/battery/activation alignment and accepted-bid evidence validation, in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T020 [US1] Implement the additive `robust-storage-bidding-reference-settlement-v1` price and delivered-activation accounting path without changing `SettlementBreakdown` or `settle_stacked_services()` in `src/open_energy_lab/simulator/fcr_settlement.py`
- [X] T021 [US1] Implement initial/min/max/terminal stored energy, requested/delivered power extrema, charge/discharge/throughput, tracking, non-delivery, saturation, interval-count, and deterministic daily aggregation in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T022 [US1] Implement producer-kind invariance, manual/heuristic unavailable optimization metadata, zero-FCR, and zero-energy semantics through the same evaluation path in `src/open_energy_lab/control/fcr_bid_plan.py`, `src/open_energy_lab/simulator/fcr_bid_evaluation.py`, and `src/open_energy_lab/simulator/fcr_settlement.py`
- [X] T023 [US1] Generate and pin the authored oracle's canonical plan/input/trace/settlement/result fingerprints only after all independent numeric assertions pass in `tests/fixtures/fcr_bid_evaluation/manual_fcr_bid_evaluation_v1.json` and `tests/integration/simulator/test_fcr_bid_evaluation_manual.py`
- [X] T024 [US1] Replace the generic fixed-plan example placeholders with runnable manual-plan construction, evaluation, failed-metadata explanation, and result inspection in `examples/fcr_bid_evaluation/README.md`
- [X] T025 [US1] Run the focused US1 unit and manual integration suite and align its exact commands and expected statuses in `specs/012-fcr-bid-evaluation-parity/quickstart.md`

**Checkpoint**: US1 is an independently usable bidder-neutral evaluator for
authored fixed plans and is the suggested MVP.

---

## Phase 4: User Story 2 - Translate And Compare A Pinned Reference Result (Priority: P1)

**Goal**: Import the pinned 2023-06-18 published decisions and explicit external
`xi_EU` data, assemble existing OEL schedules/activation, and compare only
supported aggregates under rigorous source-precision bounds.

**Independent Test**: Validate the Golden Reference Fixture without a submodule,
then explicitly supply the digest-matched CSV, construct exactly 24/6/96/8,640
intervals, verify every sign/unit/time/index mapping, and obtain only `exact` or
`source_precision_compatible` outcomes for supported fields while unsupported
fields remain `unavailable`.

### Tests And Fixture For User Story 2

- [X] T026 [P] [US2] Encode the immutable 2023-06-18 Golden Reference Fixture with pinned commit/command/result digest, exact source paths, configuration, 24 rounded `x0`, six rounded `xr`, prices, expected fields, unsupported fields, external descriptor, runtime provenance, redistribution states, and field-specific precision bounds in `tests/fixtures/fcr_bid_evaluation/robust_storage_bidding_2023-06-18_aggregate_v1.json`
- [X] T027 [P] [US2] Add failing schema, digest, count, finite-value, JSON-pointer, runtime-provenance, redistribution, unsupported-field, and byte-stable fingerprint tests for the Golden Reference Fixture in `tests/integration/simulator/test_fcr_reference_fixture.py`
- [X] T028 [P] [US2] Add failing tests for discharge-positive `x0` sign inversion, unchanged non-negative `xr`, deterministic rejection of any negative `xr` before schedule construction with a stable field/index diagnostic, deterministic accepted-bid/price references, activation-equation equivalence, power-extrema sign reversal, EUR/MWh and EUR/MW/4h conversions, one-based index conversion, Europe/Paris/UTC mapping, and DST-day rejection in `tests/unit/control/test_fcr_bid_plan.py`
- [X] T029 [P] [US2] Add failing external-loader tests using injected tiny descriptors for missing/wrong-size/wrong-digest/wrong-header/duplicate/gap/overlap/nonfinite/wrong-date/wrong-column cases, exact PT10S construction, no download, no environment lookup, and no `baselines/` fallback in `tests/unit/market/test_reference_fcr.py`
- [X] T030 [P] [US2] Add failing field-comparison tests for exact, analytic `source_precision_compatible`, mismatch, unavailable, exact-rounded-match recording, interval overlap, recomputed per-field bounds, objective-versus-profit separation, and rejection of a blanket tolerance in `tests/unit/simulator/test_fcr_bid_evaluation.py`

### Implementation For User Story 2

- [X] T031 [US2] Implement immutable Golden Reference Fixture, reference-price, mapping, external-descriptor, precision-policy, expected-field, and runtime/redistribution entities plus strict offline JSON loading and fixture fingerprint verification in `src/open_energy_lab/market/reference_fcr.py`
- [X] T032 [US2] Implement the pinned `x0`/`xr` to existing `EnergyBaselineSchedule`/`FCRCapacitySchedule` mapper with finite non-negative `xr` validation before schedule construction, exact accepted-bid/price references, units, interval counts, Europe/Paris delivery metadata, source citations, and mapping fingerprints in `src/open_energy_lab/control/fcr_bid_plan.py`
- [X] T033 [US2] Implement explicit-path regulation CSV byte-count/SHA-256/header/date/cadence/value validation and construction of the existing `RegulationActivationTrace` without download, interpolation, deduplication, fallback, or persistence in `src/open_energy_lab/market/reference_fcr.py`
- [X] T034 [US2] Implement the source-independent reference-result market context assembler for published `p0`/`pr` and accepted `xr` evidence without fabricating A44/A81 observations in `src/open_energy_lab/market/reference_fcr.py`
- [X] T035 [US2] Implement field-level parity results, analytic decision-rounding propagation, output-rounding intervals, exact-rounded flags, supported/unavailable evidence gates, overall status, and comparison fingerprints in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T036 [US2] Add the offline Golden Reference Fixture assembly integration case proving mapping declarations, 24/6 schedule counts, price conversions, objective metadata separation, and zero reads of baseline/external paths in `tests/integration/simulator/test_fcr_reference_fixture.py`
- [X] T037 [US2] Add the explicitly selected complete 2023-06-18 integration test with exact 24/6/96/8,640 counts, full physical replay, supported aggregate comparisons, deterministic fingerprints, and actionable absent-data skip in `tests/integration/simulator/test_fcr_reference_aggregate_parity.py`
- [X] T038 [US2] Implement the explicit `--activation-path` full-reference consumer with concise mapping, lineage, physical, settlement, exact/source-precision/unavailable comparison output and nonzero mismatch exit status in `examples/fcr_bid_evaluation/run_reference_parity.py`
- [X] T039 [US2] Perform the initial US2 external acceptance run of the complete reference consumer/test with the digest-validated user-supplied CSV when available and record the baseline comparison statuses, fingerprints, or precise external-data blocker for later regression comparison in `tests/fixtures/fcr_bid_evaluation/README.md` and `specs/012-fcr-bid-evaluation-parity/quickstart.md`

**Checkpoint**: US2 reproduces the maximum defensible aggregate evidence from
the pinned result without requiring Julia/Gurobi or overstating exact parity.

---

## Phase 5: User Story 3 - Audit Settlement And Daily Performance (Priority: P1)

**Goal**: Make every available revenue, energy, state, delivery, tracking,
saturation, diagnostic, and lineage component independently inspectable, while
invalid accepted commitments produce no settlement or profit.

**Independent Test**: Recalculate a bid containing both activation directions
and valid dynamic SOC-limited non-delivery, assert every component and
directional identity within `1e-6`, then submit a statically invalid
power-headroom commitment and receive a deterministic failed report plus a
separately labelled diagnostic replay.

### Tests And Fixture Extensions For User Story 3

- [X] T040 [P] [US3] Add failing tests for component availability, both activation directions, delivered-only energy payment, explicit penalty application, charge/discharge/throughput, signed-net reconciliation, combined-FCR reconciliation, and internal total failure in `tests/unit/simulator/test_fcr_reference_settlement.py`
- [X] T041 [P] [US3] Add failing tests distinguishing deterministic static schedule/battery/reserve-power-headroom preflight failures from valid dynamic SOC saturation, with ordered diagnostics, absent trace/settlement/profit fields only for failures, battery mutation, missing fingerprints, diagnostic replay labelling, and settlement/comparison rejection of diagnostic results in `tests/unit/simulator/test_fcr_bid_evaluation.py`
- [X] T042 [P] [US3] Extend the authored fixture with independently calculated upward/downward activation, valid dynamic SOC-limited delivery and non-delivery penalty, an invalid static power-headroom case, unavailable components, and failed-plan cases in `tests/fixtures/fcr_bid_evaluation/manual_fcr_bid_evaluation_v1.json`
- [X] T043 [US3] Extend the manual integration oracle to assert requested/delivered directional FCR energy, signed net, tracking, valid dynamic SOC saturation and non-delivery, saturation event ordering, delivered-energy revenue, penalties, statically invalid failed reports, diagnostic replay separation, and all reconciliation identities in `tests/integration/simulator/test_fcr_bid_evaluation_manual.py`

### Implementation For User Story 3

- [X] T044 [US3] Implement full reference component-availability states, delivered directional activation-energy payment, explicit non-delivery penalties, directional energy summaries, unavailable component reasons, and strict component reconciliation in `src/open_energy_lab/simulator/fcr_settlement.py`
- [X] T045 [US3] Implement deterministic `validation_failed` reports for static schedule/battery/reserve-power-headroom failures, preserve valid settled reports for dynamic SOC saturation, and implement the separate `invalid_commitment_diagnostic` replay operation with guards against normal settlement/comparison use in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T046 [US3] Complete daily report serialization with producer/cutoff identity, objective/bound availability, stored-energy/SOC metrics, requested/delivered power extrema, directional FCR energy, tracking, saturation diagnostics, settlement availability, and complete fingerprints in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T047 [US3] Implement combined reference `profit_fcr` reconciliation and explicit unavailable outcomes for detailed trace, directional FCR, tracking, saturation, separate reference-observed subrevenue, and throughput evidence in `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [X] T048 [US3] Add integration cases for zero FCR, zero energy, no penalty, configured penalty, both activation directions, valid settled dynamic SOC saturation with delivered-only revenue and optional penalty, static power-headroom validation failure with diagnostic-only replay, saturated-run reference-parity unavailability, and product-type rejection in `tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py`
- [X] T049 [US3] Pin deterministic ordered daily-report, failed-report, diagnostic, settlement, and comparison fingerprints only after all independent oracle assertions pass in `tests/fixtures/fcr_bid_evaluation/manual_fcr_bid_evaluation_v1.json` and `tests/integration/simulator/test_fcr_bid_evaluation_manual.py`
- [X] T050 [US3] Run the focused settlement, evaluator, manual-oracle, and compatibility suite and align exact audit/failure expectations in `specs/012-fcr-bid-evaluation-parity/quickstart.md`

**Checkpoint**: US3 exposes auditable economics and physical delivery without
allowing invalid or diagnostic runs to masquerade as bidder performance.

---

## Phase 6: User Story 4 - Reproduce Results Offline With Complete Lineage (Priority: P2)

**Goal**: Make routine validation fully fixture-backed and deterministic while
providing explicit user-managed data installation and reviewed fixture-refresh
workflows.

**Independent Test**: Remove the reference submodule and external CSV, block
sockets and environment lookup, run the routine suite twice with identical
bytes/fingerprints, then verify missing or corrupt external data fails with
actionable instructions rather than an implicit download or synthetic fallback.

### Tests For User Story 4

- [ ] T051 [P] [US4] Add zero-network/zero-environment tests proving routine Golden Reference Fixture load and validation never resolve reference source paths, initialize the submodule, inspect Julia/Gurobi, or open the external CSV in `tests/integration/simulator/test_fcr_reference_fixture.py`
- [ ] T052 [P] [US4] Add actionable public-loader error and optional-pytest-skip tests for absent, misplaced, truncated, digest-mismatched, or structurally invalid external data in `tests/unit/market/test_reference_fcr.py` and `tests/integration/simulator/test_fcr_reference_aggregate_parity.py`
- [ ] T053 [US4] Add two-run canonical byte and plan/input/trace/settlement/comparison/result fingerprint stability tests for manual and Golden Reference Fixture routine paths in `tests/integration/simulator/test_fcr_reference_fixture.py` and `tests/integration/simulator/test_fcr_bid_evaluation_manual.py`
- [ ] T054 [P] [US4] Add failing normalizer tests for explicit input/output paths, exact original digest/configuration, no Julia execution, no baseline mutation, byte-stable ignored output, semantic-diff reporting, and refusal to overwrite committed fixtures in `tests/integration/simulator/test_fcr_reference_normalization.py`

### Implementation And Documentation For User Story 4

- [ ] T055 [US4] Implement the explicit generated-JSON normalizer with strict provenance/configuration validation, canonical aggregate output below caller-selected ignored destinations, semantic diffing, and no Julia/Gurobi invocation in `examples/fcr_bid_evaluation/normalize_reference_result.py`
- [ ] T056 [US4] Complete fixture provenance, authoritative/superseded URLs, exact digest/size/header, external-only handling, source-precision bounds, supported/unavailable fields, generation/refresh commands, and latest validation record in `tests/fixtures/fcr_bid_evaluation/README.md`
- [ ] T057 [P] [US4] Complete the Feature 012 preserve/improve/reject decisions, exact baseline source citations, common-environment ownership, reference evidence limits, and no-optimizer boundary in `docs/migration/fcr-bid-evaluation-parity.md`
- [ ] T058 [P] [US4] Add Feature 012 Golden Reference Fixture containing aggregate evidence, external-data, bounded-parity, offline-environment, and review-path rules to `docs/migration/fixture-provenance.md`, `docs/migration/parity-validation.md`, `docs/migration/environment-assumptions.md`, and `docs/migration/README.md`
- [ ] T059 [P] [US4] Add policy tests proving the 529 MB CSV path is ignored and absent from Git/package/release/public-CI manifests while the small Golden Reference Fixture contains complete required provenance in `tests/unit/test_fixture_provenance_docs.py`, `tests/unit/test_migration_policy_docs.py`, and `tests/unit/test_ci_workflow.py`
- [ ] T060 [US4] Finalize runnable download/place/verify/full-run/refresh commands, explicit no-download behavior, absent-data outcomes, and generic bidder example in `examples/fcr_bid_evaluation/README.md` and `specs/012-fcr-bid-evaluation-parity/quickstart.md`
- [ ] T061 [US4] Execute the documented routine suite twice with sockets blocked and the external path absent, then correct only Feature 012 fixture, example, test, or library files exposed by failures in `tests/fixtures/fcr_bid_evaluation/`, `examples/fcr_bid_evaluation/`, and `src/open_energy_lab/`

**Checkpoint**: US4 routine validation is self-contained, while external data
and reference refresh remain explicit, integrity-checked researcher operations.

---

## Phase 7: User Story 5 - Preserve Validated Feature 010 Behavior (Priority: P2)

**Goal**: Prove the new evaluator is additive and cannot change or substitute
Feature 010 FCR contracts, fixtures, default settlement, physical results, public
symbols, or import boundaries.

**Independent Test**: Run the complete unchanged Feature 010 suite, compare all
three stored reference fixtures and recorded fingerprints byte-for-byte, and
verify FCR/aFRR/mFRR cross-substitution fails before physical replay.

### Compatibility Tests For User Story 5

- [ ] T062 [P] [US5] Add final public-symbol, constructor, exact-type, serialization, module-owner, and default-settlement snapshots for Feature 010 plus additive Feature 012 symbols in `tests/integration/simulator/test_fcr_bid_evaluation_public_compatibility.py`
- [ ] T063 [P] [US5] Add exhaustive rejection of Feature 011 aFRR/mFRR commitments, trajectories, events, replay results, and settlement inputs at every Feature 012 FCR boundary in `tests/integration/simulator/test_fcr_bid_evaluation_product_separation.py`
- [ ] T064 [P] [US5] Add byte-stability assertions for the three Feature 010 market fixtures and exact preservation of the recorded market/activation/schedule/trace/result fingerprints in `tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py`
- [ ] T065 [P] [US5] Extend import scans to reject production imports/execution from `baselines/*` and `legacy/*` plus Julia, Gurobi, network, notebook, and external-data leakage from ordinary package imports in `tests/unit/test_no_legacy_imports.py`, `tests/unit/test_lazy_dependency_boundaries.py`, and `tests/unit/test_import_contract.py`
- [ ] T066 [US5] Run the unchanged Feature 010 market, control, stacked replay, default settlement, manual oracle, compatibility, fixture-generation, and real-replay suites and fix only additive Feature 012 code in `src/open_energy_lab/control/fcr_bid_plan.py`, `src/open_energy_lab/market/reference_fcr.py`, `src/open_energy_lab/simulator/stacked_service.py`, `src/open_energy_lab/simulator/fcr_settlement.py`, and `src/open_energy_lab/simulator/fcr_bid_evaluation.py`
- [ ] T067 [US5] Run the explicitly selected unchanged Feature 010 `reference_benchmark` and document an environment-only limitation without weakening correctness in `specs/012-fcr-bid-evaluation-parity/quickstart.md`
- [ ] T068 [US5] Add final zero-FCR baseline-only and zero-energy regulation-only comparisons proving the Feature 010 default profile remains unchanged while the explicit reference profile remains separately fingerprinted in `tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py`
- [ ] T069 [US5] Verify final lazy export ordering and focused external-loader imports without adding package-root baseline/data/solver side effects in `src/open_energy_lab/control/__init__.py`, `src/open_energy_lab/market/__init__.py`, `src/open_energy_lab/simulator/__init__.py`, and `tests/unit/simulator/test_import_boundary.py`

**Checkpoint**: US5 proves exact Feature 010 compatibility and strict reserve-
product/import separation after every additive Feature 012 path is present.

---

## Phase 8: Polish And Cross-Cutting Validation

**Purpose**: Close documentation, scaling, packaging, complete test execution,
external-reference evidence, and source-boundary review across all stories.

- [ ] T070 [P] Add the Feature 012 common-evaluator, bounded-reference-parity, and example review links without implying bid optimization or complete Julia trace parity in `README.md` and `docs/architecture/README.md`
- [ ] T071 [P] Add SC-014 instrumented scaling tests for one valid 8,640-interval ordinary-day evaluation, proving each validation, replay, aggregation, comparison, and fingerprinting stage performs at most two complete iterations over its primary interval collection and retains no superlinear collection, without a wall-clock threshold, in `tests/unit/simulator/test_fcr_bid_evaluation_scaling.py`
- [ ] T072 [P] Add documentation consistency tests for exact reference terminology, baseline source paths, authoritative URL/digest, supported/unavailable fields, source-precision wording, and absence of “paper-compatible” acceptance claims in `tests/unit/test_fixture_provenance_docs.py` and `tests/unit/test_migration_policy_docs.py`
- [ ] T073 Build wheel and sdist, inspect complete file lists for the external CSV, baseline contents, ignored artifacts, and unintended reference data, and record reproducible commands/results in `specs/012-fcr-bid-evaluation-parity/quickstart.md`
- [ ] T074 Run the full routine Feature 012 suite with `uv run pytest tests/unit/control/test_fcr_bid_plan.py tests/unit/market/test_reference_fcr.py tests/unit/simulator/test_fcr_bid_evaluation.py tests/unit/simulator/test_fcr_reference_settlement.py tests/integration/simulator/ -m "not external_reference_data and not reference_benchmark"` and resolve every failure in the exact file named by that failure
- [ ] T075 Run the complete Feature 010 regression, fixture-generation, import-boundary, no-legacy/baseline-import, and lazy-dependency commands from `specs/012-fcr-bid-evaluation-parity/quickstart.md` and resolve every additive regression
- [ ] T076 After US3-US5 and all polish changes, rerun the explicit full 2023-06-18 consumer and `external_reference_data` integration test when the digest-matched CSV is installed, compare statuses and fingerprints with the T039 baseline, record the final regression outcome, or document the precise missing-data blocker without weakening routine checks in `tests/fixtures/fcr_bid_evaluation/README.md` and `specs/012-fcr-bid-evaluation-parity/quickstart.md`
- [ ] T077 Verify `git diff --check`, strict task/fixture/schema versions, no production `baselines/*` or `legacy/*` imports, no external CSV under tracked/package paths, and exact agreement between quickstart commands and implemented files in `specs/012-fcr-bid-evaluation-parity/quickstart.md`

---

## Dependencies And Execution Order

### Phase Dependencies

```text
Phase 1: Setup
  -> Phase 2: Foundational evaluation boundaries
       -> Phase 3: US1 bidder-neutral evaluator (MVP)
            ├── Phase 4: US2 pinned reference translation/parity
            └── Phase 5: US3 settlement/report audit

US2 + US3
  -> Phase 6: US4 offline reproducibility and refresh workflow

Phase 2 characterization may start US5 compatibility tests early;
US1 through US4 must finish before US5 final regression completion.

US1 through US5
  -> Phase 8: polish and cross-cutting validation
```

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 and independently delivers the common
  fixed-plan evaluator; this is the MVP.
- **US2 (P1)**: Depends on US1 evaluation/settlement/report contracts and adds
  the pinned reference fixture, mapping, external loader, and bounded comparison.
- **US3 (P1)**: Depends on US1 and can proceed in parallel with US2 after the
  common evaluator exists; it completes audit and invalid-plan behavior.
- **US4 (P2)**: Depends on US2 fixture/external workflows and US3 final report
  states so routine/refresh documentation covers the completed surface.
- **US5 (P2)**: Characterization tasks begin in Phase 2, but final completion
  follows all additive implementations so the full compatibility suite is final.

### Within Each User Story

1. Author or extend deterministic fixtures.
2. Add failing unit/contract/integration tests.
3. Implement frozen entities and validation.
4. Implement replay, settlement, comparison, or workflow behavior.
5. Pin fingerprints only after independent numeric assertions pass.
6. Run the focused story suite and align documentation.

---

## Parallel Execution Examples

### User Story 1

Run T015, T016, and T017 in parallel. After the fixture and contracts exist,
T018 can assemble the oracle. T019-T022 then proceed in module order before
T023 pins fingerprints; T024 can update the example in parallel with T023.

### User Story 2

Run T026-T030 across separate fixture/test files. After those contracts fail as
expected, T031 and T032 can proceed in parallel; T033-T034 remain serialized in
`reference_fcr.py`. T035 can proceed against the stable fixture entities before
T036-T039 assemble and execute the complete workflow.

### User Story 3

Run T040-T042 in parallel, then add T043. Settlement work T044 and evaluator
failure/report work T045-T047 touch separate modules initially; serialize edits
inside `fcr_bid_evaluation.py`. T048 can proceed before T049 pins fingerprints.

### User Story 4

Run T051, T052, and T054 in parallel. Add T053 after T051. After the normalizer
contract is fixed, T055 can proceed while T056-T059 update separate
fixture/document/test files. T060-T061 then validate the assembled offline
workflow.

### User Story 5

Run T062-T065 in parallel across separate compatibility files. T066-T069 then
execute the final regression, benchmark, zero-profile, and import gates against
the completed additive feature.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 only.
3. Demonstrate one fixed manual plan evaluated through the common physical and
   settlement environment with deterministic daily reporting.
4. Validate manual/heuristic/robust/TPM identity invariance, zero-FCR,
   zero-energy, and Feature 010 characterization before adding reference data.

### Incremental Delivery

1. **US1**: bidder-neutral fixed-plan evaluator and hand oracle
2. **US2**: pinned decision mapping, external activation loader, and bounded
   aggregate parity
3. **US3**: complete settlement/report audit and invalid-plan separation
4. **US4**: self-contained routine fixtures, docs, and reviewed refresh workflow
5. **US5**: final Feature 010 API/byte/fingerprint/import compatibility proof
6. **Polish**: packaging, scaling, full suites, and explicit external check

### Guardrails

- Do not modify, import, execute, or write production code in `baselines/*` or
  `legacy/*`.
- Do not introduce another energy/FCR schedule type or another battery simulator.
- Do not manufacture A44/A81 provenance for reference-result inputs.
- Do not expose realized activation to a bidder before its information cutoff.
- Do not pay requested but undelivered activation energy.
- Do not use a blanket parity tolerance or claim exact equality from rounded
  decisions.
- Do not embed, track, package, upload, or implicitly download the external CSV.
- Do not change Feature 010 default settlement, fixture bytes, public results,
  trace fingerprints, or result fingerprints.
