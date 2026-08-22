---
description: "Dependency-ordered implementation tasks for French BESS stacked services"
---

# Tasks: French BESS Stacked Services

**Input**: Design documents from `/specs/010-bess-stacked-services/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Tests**: This feature is validation-heavy. Focused unit and integration tests,
the manual oracle, compatibility gates, and deterministic offline replay are
required and are scheduled before their corresponding implementations.

**Organization**: Tasks are grouped by user story so the two P1 capabilities
can be developed and tested independently after the shared canonical
time/artifact foundation. The real demonstration then connects them without
moving source access into the simulator.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no
  dependency on an incomplete task in the same execution group
- **[Story]**: Maps the task to `US1`, `US2`, `US3`, or `US4`
- Every task names the exact file or directory it changes

## Phase 1: Setup

**Purpose**: Establish the import-light package, test, fixture, and example
surfaces without changing `legacy/*` or adding a core dependency.

- [X] T001 Create the import-light market and test-package scaffolds in `src/open_energy_lab/market/__init__.py`, `tests/unit/market/__init__.py`, and `tests/integration/market/__init__.py`
- [X] T002 [P] Register the explicitly selected `live_entsoe` and `reference_benchmark` pytest markers without adding either to routine test selection in `pyproject.toml`
- [X] T003 [P] Document the market-fixture layout, token prohibition, raw-sidecar rule, and gated real-fixture policy in `tests/fixtures/market/README.md`
- [X] T004 [P] Create the explicit-fetch and offline-replay consumer outline in `examples/bess_stacked_services/README.md`

---

## Phase 2: Foundational Canonical Boundaries

**Purpose**: Define the source-independent time and market-artifact contracts
used by both market-data production and simulation.

**Critical**: These tasks block every user story. Tests must fail before the
corresponding implementation when practical.

- [X] T005 [P] Add failing tests for aware half-open UTC intervals, Europe/Paris labels and folds, 23/25-hour delivery days, exact resolution divisibility, and multi-rate boundary maps in `tests/unit/market/test_time.py`
- [X] T006 [P] Add failing tests for the v1 market schema, required France series, units, coverage, deterministic JSON, content fingerprints, artifact fingerprints, and cross-series FCR alignment in `tests/unit/market/test_artifact.py`
- [X] T007 [P] Add failing tests for unknown schemas, malformed/non-finite data, immutable atomic writes, digest-only evidence, safe verified sidecars, traversal rejection, and offline loading in `tests/unit/market/test_artifact_io.py`
- [X] T008 [P] Add failing package-surface tests proving `open_energy_lab.market` is import-light and does not import networking, notebooks, solvers, credentials, or `legacy/*` in `tests/unit/market/test_import_boundary.py`
- [X] T009 Implement canonical intervals, UTC/local delivery metadata validation, resolution parsing, complete-block checks, and exact multi-rate index construction in `src/open_energy_lab/market/time.py`
- [X] T010 Implement immutable market-series/artifact entities, strict schema and France-profile validation, canonical serialization, and dual SHA-256 fingerprints in `src/open_energy_lab/market/artifact.py`
- [X] T011 Implement token-free immutable filenames, manifest-last atomic publication, load-time integrity checks, and optional raw-sidecar containment/digest validation in `src/open_energy_lab/market/artifact.py`
- [X] T012 Publish lazy canonical-artifact and time exports and verify the public surface in `src/open_energy_lab/market/__init__.py` and `tests/unit/market/test_package_surface.py`

**Checkpoint**: Canonical market artifacts can be constructed, written, and
loaded deterministically with no source adapter or network access.

---

## Phase 3: User Story 1 - Produce A Reusable French Market Artifact (Priority: P1)

**Goal**: Explicitly fetch or refresh French A44 day-ahead prices, A81
symmetric-FCR volume, and A89 compatible FCR capacity prices into one validated
immutable artifact, then reload it offline without exposing the token.

**Independent Test**: With a caller-supplied credential, fetch one bounded
period, inspect all series and provenance, scan files/output/errors for a
sentinel credential, and reload the artifact with transport access disabled.
The injected-transport workflow supplies the routine offline proof; the
credentialed source check is explicitly selected.

### Tests and fixtures for User Story 1

- [X] T013 [P] [US1] Create minimal redistributable A44, A81, and A89 success documents plus acknowledgement, empty, duplicate, gap, wrong-product, wrong-unit/resolution, unsafe XML, and DST variants in `tests/fixtures/market/synthetic_entsoe/`
- [X] T014 [P] [US1] Add failing tests for token-separated requests, HTTPS-only injected transport, response-size ceilings, sanitized diagnostics, transient retry classes/delays, three-attempt exhaustion, and one-attempt permanent failures in `tests/unit/market/test_entsoe_transport.py`
- [X] T015 [P] [US1] Add failing parser tests against the synthetic documents for namespace/root classification, required semantic fields, curve expansion, revision selection, exact/conflicting duplicates, coverage, negative prices, product identity, unit conversion, and DST handling; for each applicable failure assert the typed diagnostic contains source, required series, requested period, observed coverage/resolution when available, expected profile/contract, and no credential material in `tests/unit/market/test_entsoe_parser.py`
- [X] T016 [P] [US1] Add failing end-to-end fake-transport tests for fetch, offline load with zero transport calls, unchanged/changed/regressed refresh, raw sidecars, atomic failure, and sentinel-token scans; assert applicable failures expose source, series, requested period, observed coverage/resolution, expected contract, attempt/final status, and no credential material in `tests/integration/market/test_entsoe_fixture_workflow.py`
- [X] T017 [P] [US1] Add an opt-in credentialed France A44/A81/A89 compatibility test that skips clearly when no token/network is available and never records the token in `tests/integration/market/test_entsoe_live.py`

### Implementation for User Story 1

- [X] T018 [US1] Implement the token-free France request/profile types, typed sanitized failures, injected synchronous HTTPS transport, byte limit, and fixed three-attempt retry policy in `src/open_energy_lab/market/entsoe.py`
- [X] T019 [US1] Implement defensive A44/A81/A89 XML classification, parsing, revision selection, curve expansion, France/product validation, unit normalization, and complete requested-period validation in `src/open_energy_lab/market/entsoe.py`
- [X] T020 [US1] Implement explicit `fetch_entsoe_market_data` with enclosing local-day query windows, in-memory all-series validation, raw-response digests, retention metadata, and atomic artifact publication in `src/open_energy_lab/market/entsoe.py`
- [X] T021 [US1] Implement explicit `refresh_entsoe_market_data` outcomes for unchanged content, linked immutable publication, and comparable revision regression without mutating the current artifact in `src/open_energy_lab/market/entsoe.py`
- [X] T022 [US1] Implement the token-safe `fetch` and `refresh` example consumer, reading `ENTSOE_API_TOKEN` only at the explicit retrieval boundary, in `examples/bess_stacked_services/fetch_french_period.py`

**Checkpoint**: User Story 1 passes entirely with injected transports and can
optionally prove current ENTSO-E compatibility with a caller credential.

---

## Phase 4: User Story 2 - Replay Fixed Arbitrage And FCR Commitments (Priority: P1)

**Goal**: Consume canonical market and activation artifacts, align fixed
hourly energy and four-hour symmetric-FCR schedules, replay battery physics at
activation resolution, and report auditable delivery and settlement.

**Independent Test**: Run the four-hour manual fixture and independently assert
all eight requested/delivered powers, nine stored-energy states, 2 kWh
throughput, EUR 0.05 energy revenue, EUR 0.08 FCR revenue, zero tracking error,
zero penalty, and EUR 0.13 total profit within `1e-6`.

### Tests and fixtures for User Story 2

- [X] T023 [P] [US2] Add failing tests for interval-average and explicit left-hold activation imports, normalization/sign provenance, fingerprints, gaps, duplicates, ambiguous timezones, non-finite/range errors, unsupported semantics, and unproven A83/A84 rejection in `tests/unit/market/test_activation.py`
- [X] T024 [P] [US2] Add failing tests for one-BESS schedule validation, complete hourly/four-hour blocks, exact PT10S/PT15M/PT1H/PT4H maps, market-volume/headroom checks, partial/incompatible horizons, requested-versus-delivered attribution, power/SOC saturation causes, aggregation conservation, and deterministic events in `tests/unit/simulator/test_stacked_service.py`
- [X] T025 [P] [US2] Add failing tests for schedule-based energy revenue, aligned FCR capacity revenue, absent and explicit EUR/kWh penalties, throughput, not-modeled statuses, and exact profit reconciliation in `tests/unit/simulator/test_fcr_settlement.py`
- [X] T026 [P] [US2] Encode the published four-hour arithmetic oracle and add the failing end-to-end assertion table in `tests/fixtures/market/manual_stacked_service_v1.json` and `tests/integration/simulator/test_stacked_service_manual.py`

### Implementation for User Story 2

- [X] T027 [US2] Implement source-independent activation request/sample/trace entities, both declared import modes, strict validation, serialization, fingerprints, and offline load/write behavior in `src/open_energy_lab/market/activation.py`
- [X] T028 [US2] Implement fixed energy/FCR schedule entities, replay request/result entities, complete product-block validation, exact grid alignment, market-volume checks, and symmetric power-headroom validation in `src/open_energy_lab/simulator/stacked_service.py`
- [X] T029 [US2] Implement charge-positive substep replay via existing `apply_power_request`, preserving requested/delivered combined and FCR power, baseline diagnostics, SOC/efficiency effects, tracking, non-delivery, and ordered saturation causes/events in `src/open_energy_lab/simulator/stacked_service.py`
- [X] T030 [US2] Implement per-interval and aggregate day-ahead/FCR capacity settlement, optional explicit non-delivery penalty, battery-terminal throughput, not-modeled statuses, and exact total-profit reconciliation in `src/open_energy_lab/simulator/fcr_settlement.py`
- [X] T031 [US2] Complete 15-minute/hourly/FCR aggregation, energy-conservation checks, deterministic trace/result fingerprints, and report-only terminal-SOC compliance in `src/open_energy_lab/simulator/stacked_service.py`
- [X] T032 [US2] Publish import-light activation and replay/settlement exports and extend boundary coverage in `src/open_energy_lab/market/__init__.py`, `src/open_energy_lab/simulator/__init__.py`, and `tests/unit/simulator/test_import_boundary.py`

**Checkpoint**: User Story 2 passes the manual oracle using only synthetic
canonical inputs and makes no transport or optimization object available to
replay.

---

## Phase 5: User Story 3 - Reproduce A Real French Historical Demonstration (Priority: P2)

**Goal**: Preserve and replay the selected 2022-08-19 Europe/Paris delivery day
from a credential-validated ENTSO-E artifact and a separately provenanced RTE
10-second activation artifact, entirely offline after fixture production.

**Independent Test**: Block all network access, load the three committed
reference fixtures, perform one warm-up and five measured runs under the
Reference Benchmark Protocol in `plan.md`, and reproduce the exact input,
trace, result, SOC, delivery, throughput, terminal-report, and settlement
outputs with every measured run under ten seconds.

### Tests for User Story 3

- [X] T033 [P] [US3] Add a zero-network integration test that loads the committed normalized artifact, verifies exactly 8,640 gap-free PT10S samples, naive Europe/Paris timestamp provenance, explicit left-hold semantics, `clip((50-f)/0.2,-1,1)` provenance, source revision/digest, coverage, and exact trace fingerprint, and never opens the external raw RTE dataset in `tests/integration/market/test_reference_activation_import.py`
- [X] T034 [P] [US3] Add a failing zero-network real-replay test that always validates 24 energy intervals, 96 checkpoints, six FCR blocks, 8,640 samples, expected component totals, and byte-stable fingerprints; add a separately marked `reference_benchmark` case in the same file that implements the one-warm-up/five-run measurement boundaries and under-ten-second assertions from the Reference Benchmark Protocol in `tests/integration/simulator/test_stacked_service_real_replay.py`

### Implementation and fixture production for User Story 3

- [X] T035 [P] [US3] Implement an explicitly selected regeneration consumer that accepts a caller-supplied local copy of `lauinger/robust-storage-bidding@7e44738bb30e5c8204efe40103b9be4c2203685c:data_processing/freq_data/RTE_Frequence_2022_08.txt`, verifies and records its SHA-256 digest, imports the selected observations without notebook gap filling, and publishes the attributed normalized trace in `examples/bess_stacked_services/import_reference_activation.py` and `tests/fixtures/market/france_2022-08-19_activation_v1.json`
- [X] T036 [P] [US3] Run the explicit credentialed completeness and legal-reuse gate for UTC `[2022-08-18T22:00:00Z, 2022-08-19T22:00:00Z)` and publish `tests/fixtures/market/france_2022-08-19_market_v1.json` only if compatible A44/A81/A89 coverage and normalized-fixture reuse terms pass; otherwise record the blocker in `tests/fixtures/market/README.md` without fallback or patching
- [X] T037 [US3] Replay the fixed 100 kWh/10--90 kWh, 50 kW, 0.92-efficiency battery with six 5 kW FCR blocks, zero penalty, and report-only 50 kWh terminal target; record the 475/540 EUR/MWh thresholds, 5 kW controller request, every unmodified threshold request, every admissible FCR-headroom interval, the resulting fixed hourly baseline, independently checked traces/totals, and fingerprints in `tests/fixtures/market/france_2022-08-19_expected_replay_v1.json`
- [X] T038 [US3] Implement the zero-network demonstration loader, fingerprint verification, recorded fixed-schedule loading, expected-result comparison, and settlement output in `examples/bess_stacked_services/run_offline_replay.py`
- [X] T039 [US3] Record the exact external commit/path evidence, ENTSO-E and RTE attribution/reuse basis, normalization equations, no-runtime-dependency rule, and a single-owner matrix assigning retrieval/normalization to `market.entsoe`, market-artifact validity to `market.artifact`, activation-artifact validity to `market.activation`, fixed schedules to `control.stacked_service`, physical delivery to `simulator.stacked_service`, settlement to `simulator.fcr_settlement`, and robust bidding to a later feature in `docs/migration/bess-stacked-services.md` and `tests/fixtures/market/README.md`

**Checkpoint**: User Story 3 is reproducible without a credential or network.
If T036 fails its hard gate, this story remains explicitly blocked and no
synthetic, RTE-price, or partial-market replacement is accepted.

---

## Phase 6: User Story 4 - Validate Baseline Compatibility (Priority: P3)

**Goal**: Provide deterministic arbitrage-only, regulation-only, and
headroom-clipped stacked schedule builders and prove both limiting-case
identities against established battery/arbitrage semantics.

**Independent Test**: Repeatedly build and replay all three profiles from the
same battery/time inputs; verify zero FCR matches the existing arbitrage trace
and settlement, zero energy produces regulation-only behavior and zero energy
revenue, and future activation changes cannot alter schedule construction.

### Tests for User Story 4

- [X] T040 [P] [US4] Add failing unit tests for a zero energy schedule, efficiency-aware centered initial energy, no recovery dispatch, fixed FCR commitments, headroom-clipped price-threshold requests, empty admissible intervals, determinism, and no activation lookahead in `tests/unit/control/test_stacked_service.py`
- [X] T041 [P] [US4] Add failing integration tests for zero-FCR physical/SOC/throughput/settlement parity, zero-energy regulation-only revenue and delivery, deterministic stacked replay, exact reproduction of the fixed schedule recorded in `tests/fixtures/market/france_2022-08-19_expected_replay_v1.json`, and report-only terminal-target invariance in `tests/integration/simulator/test_stacked_service_compatibility.py`

### Implementation for User Story 4

- [X] T042 [US4] Implement deterministic arbitrage-only and regulation-only schedule configuration/builders, including the efficiency-aware centered initial energy and no recovery schedule, in `src/open_energy_lab/control/stacked_service.py`
- [X] T043 [US4] Implement the deterministic stacked builder that invokes current-step price-threshold behavior and clips every energy request to bidirectional power remaining after symmetric FCR reservation without reading activation in `src/open_energy_lab/control/stacked_service.py`
- [X] T044 [US4] Publish lazy baseline-builder exports and extend control package-boundary tests in `src/open_energy_lab/control/__init__.py` and `tests/unit/control/test_import_boundary.py`

**Checkpoint**: All three deterministic baselines are independently repeatable,
and neither schedule construction nor replay embeds robust optimization.

---

## Phase 7: Polish And Cross-Cutting Validation

**Purpose**: Finalize public maturity/provenance guidance and run the complete
offline evidence suite without widening feature scope.

- [X] T045 [P] Document experimental-v1 public maturity, stable module locations, offline defaults, and the single-owner market-data/control/simulator/later-optimization matrix, then add a documentation test that rejects missing or multiply assigned responsibilities in `docs/migration/api-maturity.md`, `docs/migration/fixture-provenance.md`, and `tests/unit/test_migration_policy_docs.py`
- [X] T046 [P] Reconcile all implemented API names, fixture paths, explicit fetch/refresh commands, failure behavior, compatibility checks, and optional-live-check guidance in `specs/010-bess-stacked-services/quickstart.md` and `examples/bess_stacked_services/README.md`
- [X] T047 Extend repository-wide lazy import, public import, and no-legacy coverage for the new market/control/simulator modules in `tests/unit/test_lazy_dependency_boundaries.py`, `tests/unit/test_import_contract.py`, and `tests/unit/test_no_legacy_imports.py`
- [X] T048 Run `uv run pytest tests/unit/market tests/integration/market -m "not live_entsoe"`, `uv run pytest tests/unit/control tests/unit/simulator`, and `uv run pytest tests/integration/control tests/integration/simulator -m "not reference_benchmark"`, resolving failures only in the Feature 010 paths under `src/open_energy_lab/`, `tests/unit/`, and `tests/integration/`
- [X] T049 Run the existing battery/arbitrage regression set `uv run pytest tests/unit/simulator/test_battery.py tests/unit/simulator/test_objective.py tests/integration/simulator/test_battery_arbitrage_trace.py tests/unit/control/test_price_threshold.py tests/integration/control/test_price_threshold_controller.py`; resolve failures in Feature 010 implementation without weakening existing expected behavior, and require an explicit specification change before altering any existing regression expectation
- [X] T050 Run `uv run pytest tests/integration/simulator/test_stacked_service_real_replay.py -m reference_benchmark -q` on the reference host with networking blocked, fail on any fingerprint/result mismatch or measured run at or above ten seconds, never modify `tests/fixtures/market/france_2022-08-19_expected_replay_v1.json` during validation, and record the CPU, allocation, memory, OS, Python, repository revision, and five timing samples required by the Reference Benchmark Protocol in `docs/migration/bess-stacked-services.md`
- [X] T051 Run `uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py`, the package import smoke command from `specs/010-bess-stacked-services/quickstart.md`, and the documented `rg "from legacy|import legacy"` scan over all Feature 010 source/test paths
- [X] T052 Run `uv run pytest tests/integration/market/test_entsoe_live.py -m live_entsoe -q` only when a caller token and network are deliberately supplied, recording unavailable credentials/network or a failed A44/A81/A89 compatibility gate in `specs/010-bess-stacked-services/quickstart.md` without weakening offline validation or publishing substitute data

---

## Phase 8: Corrective ENTSO-E R3 Alignment

**Purpose**: Supersede the obsolete pre-R3 A81/A89 acquisition assumptions
without changing the three source-independent canonical series or publishing
restricted A44 values.

- [X] T053 [P] [US1] Replace source-contract tests with exact A44 and combined A81 `B95/A52/A01` requests, R3 XML fields, dynamic ISP conversion, shared provenance, and legacy A89 rejection in `tests/unit/market/`
- [X] T054 [P] [US1] Replace reserve success fixtures with project-authored R3 combined A81 XML and exercise XML/ZIP, missing-measure, wrong-product/unit, archive-safety, and exact PT4H reconciliation cases in `tests/fixtures/market/synthetic_entsoe/` and `tests/integration/market/`
- [X] T055 [US1] Revise `oel.market-data.v1` in place so both FCR series carry exact source-value fields and reference the same selected A81 document, with optional archive-member provenance and explicit rejection of legacy A89 artifacts in `src/open_energy_lab/market/artifact.py`
- [X] T056 [US1] Implement bounded ZIP extraction, R3 `Balancing_MarketDocument` parsing, sparse combined quantity/price expansion, ISP-duration price conversion, and inference-free PT4H reconciliation in `src/open_energy_lab/market/entsoe.py`
- [X] T057 [US1] Update fake and opt-in live acquisition to publish three canonical series from two responses and scan all outputs for the token in `tests/integration/market/`
- [X] T058 [P] Reconcile `spec.md`, `plan.md`, `research.md`, `data-model.md`, contracts, quickstart, and this task history with the corrective R3 contract while retaining the original failed gate as a superseded diagnostic in `specs/010-bess-stacked-services/`
- [X] T059 [P] Document the R3 version, endpoint, exact requests, authentication/dotenv boundary, XML/ZIP handling, normalization, retries, official references, and redistribution policy in `docs/architecture/entsoe-transparency-platform.md`, and link it from architecture, migration, feature, and example guidance
- [X] T060 Run the focused offline market, control, simulator, import-boundary, and existing battery/arbitrage regression suites; keep routine validation token-free and offline
- [X] T061 Run the credentialed exact-period live gate from `.env`, record technical compatibility separately from A44 redistribution, scan outputs for the token, and leave real market/replay fixtures uncommitted pending an explicit repository-storage decision

---

## Phase 9: Restricted Private-Repository Fixture Boundary

**Purpose**: Apply the repository owner's confirmation that the repository is
private without claiming or enabling public redistribution of the real-data
fixtures.

- [X] T062 Reconcile the Feature 010 specification, plan, research, data model, contracts, quickstart, architecture, migration, example, and fixture guidance with restricted collaborator-only repository storage, prohibited public/package/release distribution, and removal before any public visibility change
- [X] T063 Replace the public-publication authorization workflow with an explicit token-free private staging consumer, fail-closed metadata validation, replay policy propagation, focused tests, and source/wheel distribution exclusions
- [X] T064 Stage the exact technically validated market fixture with unchanged content and a new restricted-policy artifact fingerprint, generate the independently checked expected replay, scan committed bytes for the token, and complete T037
- [X] T065 Run the committed-fixture reference-host benchmark with networking blocked, record the clean revision and five timings, and complete T050

---

## Phase 10: Interactive Offline Walkthrough

**Purpose**: Provide a documented notebook consumer that makes the complete
stacked-service market, control, physical, battery, quality, settlement, and
audit surfaces inspectable without weakening the private-fixture boundary.

- [X] T066 Add a source-only working notebook that reuses the validated offline replay, retains every canonical interval/sample in analysis tables, and plots the A44/A81 market series, deterministic decisions and FCR headroom, activation and requested/delivered power, battery energy/SOC/throughput, tracking/non-delivery/saturation, settlement, terminal target, and reproducibility fingerprints in `examples/bess_stacked_services/stacked_services_walkthrough.ipynb`
- [X] T067 Document optional notebook setup and restricted-output handling, add a structural regression for cleared execution state, complete variable/plot coverage, and zero network/secret imports on the default path, then execute every code cell headlessly against the committed fixtures without saving outputs in `examples/bess_stacked_services/README.md`, `specs/010-bess-stacked-services/quickstart.md`, and `tests/unit/simulator/test_stacked_services_notebook.py`
- [X] T068 Add a disabled-by-default live ENTSO-E notebook section with caller-editable UTC query parameters, guarded dotenv/token handling, A44 plus combined A81 `B95/A52/A01` acquisition, sanitized request/result summaries, direct plots of all three canonical market series, ignored digest-only output, and structural guard coverage in `examples/bess_stacked_services/stacked_services_walkthrough.ipynb`, `tests/unit/simulator/test_stacked_services_notebook.py`, and notebook guidance

---

## Dependencies And Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks every user story.
- **Phase 3 (US1)**: Depends on Phase 2. It does not depend on simulator work.
- **Phase 4 (US2)**: Depends on Phase 2. It consumes canonical in-memory or
  synthetic artifacts and can proceed in parallel with US1.
- **Phase 5 (US3)**: Depends on completed US1 and US2 contracts. T035 and T036
  can run in parallel, but T037--T039 require both artifacts and their storage
  gate.
- **Phase 6 (US4)**: Depends on US2 and the existing price-threshold controller;
  its unit work can proceed in parallel with US3, while T041's recorded-schedule
  assertion additionally depends on T037.
- **Phase 7 (Polish)**: Depends on all completed, unblocked user stories.
- **Phase 8 (Corrective R3 alignment)**: Supersedes the Phase 3 source adapter
  assumptions and the technical portion of T036/T052.
- **Phase 9 (Restricted private-repository boundary)**: Supersedes the earlier
  assumption that public redistribution permission was required for internal
  Git storage. Owner-confirmed private, collaborator-only storage unblocks
  T037/T050 while public/package/release distribution remains prohibited.
- **Phase 10 (Interactive offline walkthrough)**: Depends on the complete
  restricted fixture set and offline replay. Its default path remains offline;
  its source adapter and secret helper load only inside a disabled explicit-live
  guard, and notebook execution remains outside routine validation.

### User Story Dependency Graph

```text
Setup -> Canonical Foundation -> US1 Market Producer -----+
                              \                            +-> US3 Real Replay
                               -> US2 Physical Replay ----+
                                           \
                                            +-> US4 Baseline Compatibility

US1 + US2 constitute the P1 MVP; US3 is gated by real-source completeness and
reuse terms. US4 implementation is independent of the real fixture except for
T041's recorded-schedule compatibility assertion, which depends on T037.
```

### Within Each User Story

- Author the listed failing tests and deterministic fixtures first.
- Implement entities and validation before orchestration.
- Keep networking confined to explicit US1 fetch/refresh operations.
- Keep activation import source-independent and separate from A83/A84.
- Reuse existing battery physics before adding aggregation and settlement.
- Do not stage a real fixture until source completeness, integrity, and the
  restricted private-repository policy pass. Never package or publicly
  distribute the real fixtures.

### Parallel Opportunities

- T002, T003, and T004 can run in parallel after T001 establishes directories.
- T005--T008 can run in parallel; T009--T012 then complete the foundation in
  dependency order.
- After T013, T014--T017 can be authored in parallel; T018--T021 are sequential
  in the shared adapter file, while T022 follows their public API.
- T023--T026 can be authored in parallel; T027, T028/T030, and then T029/T031
  follow their respective contract dependencies.
- US1 and US2 can be implemented by separate contributors after Phase 2.
- T033 and T034 can be authored in parallel, and T035 and T036 are independent
  fixture-production gates.
- T040 and the non-fixture parts of T041 can be authored in parallel with US3;
  T041's recorded-schedule assertion completes after T037.
- T045 and T046 can run in parallel before the final validation commands.

---

## Parallel Execution Examples

### User Story 1

```text
After T013:
  T014 transport/retry/secret tests
  T015 XML/semantic normalization tests
  T016 artifact workflow/refresh tests
  T017 explicitly selected live-contract test
```

### User Story 2

```text
In parallel after the canonical foundation:
  T023 activation-artifact tests
  T024 replay/alignment/physics tests
  T025 settlement tests
  T026 manual end-to-end oracle
```

### User Stories 3 And 4

```text
Contributor A: T033-T039 real fixture and offline demonstration
Contributor B: T040 and T042-T044 baseline implementation; finish T041 after T037
```

---

## Implementation Strategy

### MVP First: Both P1 Boundaries

1. Complete Setup and the Canonical Foundation (T001--T012).
2. Complete US1 and US2 (T013--T032), which may proceed in parallel after the
   foundation.
3. Stop and validate the explicit fetch/offline-load workflow plus the manual
   four-hour replay oracle.
4. This MVP proves the architectural boundary and core stacked-service
   equations without depending on the real demonstration fixture.

### Incremental Delivery

1. Add the source-independent artifact boundary.
2. Add explicit France retrieval and offline reuse (US1).
3. Add fixed stacked replay and the manual oracle (US2).
4. Join them through the gated recorded French day (US3).
5. Add limiting-case deterministic baseline proofs (US4).
6. Run cross-cutting offline, import-boundary, and optional-live validation.
7. Add the source-only, optional-dependency notebook walkthrough after the
   restricted offline reference is complete.

### Scope Guardrails

- Do not add aFRR, mFRR, generic European profiles, streaming, implicit fetch,
  optimization, rolling/intraday control, RL, network constraints, activation
  energy/imbalance settlement, or electrochemical degradation.
- Do not edit or import `legacy/*`.
- Do not treat ENTSO-E A83/A84 as the PT10S FCR command without a separate
  resolution-and-semantics proof.
- Do not let market-source types enter replay, or physical/settlement behavior
  enter the market producer.
- Do not add a fallback source or synthetic patch if the real A44/combined-A81 gate
  fails.

---

## Notes

- `[P]` tasks are parallel only after their documented prerequisites pass.
- Default validation is offline and fixture-backed; the live check is opt-in.
- Every fingerprint and expected total must be derived from validated inputs,
  never copied from a lossy dataframe or notebook output.
- Raw ENTSO-E responses remain digest evidence or separately verified sidecars;
  they are never embedded in the canonical artifact.
- The API token is transient operation input and must never be persisted,
  printed, logged, fingerprinted, cached, or included in an exception.
