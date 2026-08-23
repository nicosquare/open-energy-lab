---
description: "Dependency-ordered implementation tasks for French BESS aFRR and mFRR services"
---

# Tasks: BESS aFRR and mFRR Services

**Input**: Design documents from `/specs/011-afrr-mfrr-services/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Tests**: Required by the feature specification. Focused tests, synthetic
oracles, restricted real-data demonstrations, secret scans, offline notebook
execution, and the unchanged Feature 010 regression suite precede or accompany
their corresponding implementation.

**Organization**: Tasks are grouped by the six user stories. Shared immutable
artifact, activation, control, and replay primitives are foundational; aFRR and
mFRR then remain separate independently testable product increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to execute in parallel because it changes different files and
  has no dependency on an incomplete task in the same execution group
- **[Story]**: Maps a task to `US1` through `US6`; setup, foundational, and
  polish tasks have no story label
- Every task names the exact file or directory it changes

## Phase 1: Setup

**Purpose**: Establish Feature 011 test, fixture, example, and environment
surfaces without changing `legacy/*` or adding a core dependency.

- [X] T001 [P] Register the opt-in `live_rte` pytest marker, add optional `nbclient` automated execution and `jupyterlab` interactive notebook dependencies, and add explicit Feature 011 restricted-fixture wheel/sdist exclusion placeholders without changing routine test selection or core dependencies in `pyproject.toml`
- [X] T002 [P] Create the synthetic/private fixture layout and document authored-versus-restricted handling in `tests/fixtures/restoration/README.md` and `tests/fixtures/restoration/RESTRICTED_DATA.md`
- [X] T003 [P] Create the acquisition, staging, offline replay, expected-result, and notebook consumer map in `examples/restoration_services/README.md`
- [X] T004 Verify the placeholder-only RTE/ENTSO-E variable template and ignored local dotenv policy, preserving caller secrets outside version control, in `.env.example`, `.gitignore`, and `tests/unit/market/test_rte_environment.py`

---

## Phase 2: Foundational Restoration Boundaries

**Purpose**: Define product-neutral restoration artifacts, bundles, mapping,
commitment, and replay primitives required by every user story while preserving
all closed Feature 010 types.

**Critical**: Every user story is blocked until this phase passes offline.
Tests should fail before the corresponding implementation when practical.

- [X] T005 [P] Add failing tests for restoration schema/version gates, one-source series manifests, source-null/field-absent/numeric-zero distinctions, per-series provenance, UTC/local coverage, and deterministic content/artifact fingerprints in `tests/unit/market/test_restoration_artifact.py`
- [X] T006 [P] Add failing tests for canonical finite JSON, immutable fingerprint filenames, atomic publication, corrupt-file refusal, raw digest evidence, safe sidecars, and zero-network/zero-environment offline loading in `tests/unit/market/test_restoration_artifact_io.py`
- [X] T007 [P] Add failing tests for immutable study-bundle references, exact artifact/series fingerprint resolution, no copied observations, exposed source disagreement, and strictest redistribution-policy propagation in `tests/unit/market/test_restoration_study_bundle.py`
- [X] T008 [P] Add failing lazy-import and public-owner tests proving restoration offline types do not import RTE/ENTSO-E transports, credentials, notebooks, solvers, or `legacy/*` in `tests/unit/market/test_restoration_import_boundary.py` and `tests/unit/market/test_package_surface.py`
- [X] T009 Implement restoration enums, observations, independently provenanced series, one-source artifacts, series availability, sanitized diagnostics, canonical serialization, and dual SHA-256 fingerprints in `src/open_energy_lab/market/restoration_artifact.py`
- [X] T010 Implement deterministic manifest filenames, verified offline load, manifest-last atomic writes, raw digest/sidecar validation, and immutable predecessor lineage in `src/open_energy_lab/market/restoration_artifact.py`
- [X] T011 Implement study-bundle reference validation, heterogeneous RTE/existing-Feature-010-ENTSO-E artifact resolution, exact selected-series fingerprints, no-copy composition, conflict exposure, and bundle fingerprints in `src/open_energy_lab/market/restoration_artifact.py`
- [X] T012 Publish lazy source-independent restoration artifact and study-bundle exports without exporting live adapters in `src/open_energy_lab/market/__init__.py`
- [X] T013 [P] Add failing tests for exact product/direction identities, fixed allocation fractions, MW-to-kW conversion, source lineage, explicit mapping creation time, capacity rejection, derived-simulation labels, and no normalization/clipping in `tests/unit/market/test_restoration_activation.py`
- [X] T014 Implement shared activation product/direction/source-kind values and immutable fixed-fraction `DerivedSimulationMapping` creation-time validation/fingerprints in `src/open_energy_lab/market/restoration_activation.py`
- [X] T015 [P] Add failing tests for asymmetric directional commitments, complete temporal coverage, restoration capability values, baseline headroom bounds, usable SOC/efficiency checks, and activation-input-free no-lookahead configs in `tests/unit/control/test_restoration_service.py`
- [X] T016 Implement shared directional commitment schedules, restoration energy baselines, capability inputs, configuration fingerprints, and headroom validation in `src/open_energy_lab/control/restoration_service.py`
- [X] T017 [P] Add failing tests for exact aFRR/mFRR request discriminators, charge-positive shared samples, capability-versus-physical attribution, ordered causes, conserved energy, tolerance, and deterministic fingerprints in `tests/unit/simulator/test_restoration_service.py`
- [X] T018 Implement shared exact-product replay request/result primitives, integration-grid validation, capability enforcement helpers, battery-transition adapter, ordered diagnostics, and energy-conserving aggregation helpers in `src/open_energy_lab/simulator/restoration_service.py`

**Checkpoint**: Source-independent artifacts, bundles, mappings, commitments,
and replay primitives construct, serialize, and load offline without accepting
FCR or invoking a live source.

---

## Phase 3: User Story 1 - Acquire Trustworthy French Restoration Data (Priority: P1) 🎯 MVP

**Goal**: Explicitly fetch or refresh bounded French RTE aFRR/mFRR observations,
preserve exact source meanings and provenance, compose sources only by
fingerprint reference, and reload immutable artifacts offline without exposing
credentials.

**Independent Test**: Use injected transports to fetch the verified aFRR hour
and mFRR quarter, assert exact PT15M coverage/fields and zero secret sentinels,
exercise unchanged/changed refresh, then block credentials and sockets and load
the artifacts and an RTE/ENTSO-E study bundle offline.

### Tests and Fixtures for User Story 1

- [X] T019 [P] [US1] Create authored aFRR/mFRR success payloads plus malformed root, empty, missing/null/zero, gap, overlap, duplicate/conflict, wrong-resolution, wrong-direction, wrong-unit, oversized, authentication, rate-limit, and transient/permanent response fixtures in `tests/fixtures/restoration/synthetic_rte/`
- [X] T020 [P] [US1] Add failing tests for token-free closed RTE v5.2 profiles/requests, HTTPS endpoints, bounded UTC periods, keyword-only credentials, sanitized diagnostics, and request identities in `tests/unit/market/test_rte_request.py`
- [X] T021 [P] [US1] Add failing tests for injected OAuth/data transports, bounded bodies, Basic/bearer confinement, token renewal, allowed transient classes, valid `Retry-After`, exactly three total transient attempts, and one permanent/auth attempt in `tests/unit/market/test_rte_transport.py`
- [X] T022 [US1] Add failing aFRR parser tests using `tests/fixtures/restoration/synthetic_rte/` for the `picasso` root, exact ten fields, chronological four-row PT15M coverage, field meanings/units, transformations, duplicates, ambiguity, and source diagnostics in `tests/unit/market/test_rte_afrr_parser.py`
- [X] T023 [US1] Add failing mFRR parser tests using `tests/fixtures/restoration/synthetic_rte/` for the `mari` root, directional rows, SA/DA requested/satisfied/activated distinctions, nested price entries, null/absent/zero states, sparse DA, and source diagnostics in `tests/unit/market/test_rte_mfrr_parser.py`
- [X] T024 [P] [US1] Add failing fake-transport integration tests for atomic fetch, zero-network offline load, unchanged refresh, one linked changed successor, failed refresh preservation, response digests, and credential/token sentinel scans in `tests/integration/market/test_rte_restoration_workflow.py`
- [X] T025 [P] [US1] Add failing integration tests that bundle one RTE restoration artifact with a time-compatible existing Feature 010 `fr-day-ahead-symmetric-fcr-v1` artifact, selecting its A44 `day_ahead_price` series by fingerprint without copying/renaming observations or selecting a fallback in `tests/integration/market/test_restoration_study_bundle.py`
- [X] T026 [P] [US1] Add an explicitly selected credentialed production compatibility check for the pinned aFRR/mFRR periods that skips clearly without credentials/network and persists no token or raw response in `tests/integration/market/test_rte_live.py`

### Implementation for User Story 1

- [X] T027 [US1] Implement closed aFRR/mFRR RTE profiles, credential-free requests, source query windows, transport response values, sanitized diagnostics, and typed acquisition errors in `src/open_energy_lab/market/rte.py`
- [X] T028 [US1] Implement runtime OAuth Basic-to-bearer exchange, ephemeral tokens, injected bounded HTTPS data transport, media checks, transient-only three-attempt retry, and permanent/auth one-attempt failure in `src/open_energy_lab/market/rte.py`
- [X] T029 [US1] Implement exact `standard_afrr_data` JSON parsing and independent requested-need, activated-for-France, activated-in-France, and weighted-price series normalization in `src/open_energy_lab/market/rte.py`
- [X] T030 [US1] Implement exact `standard_mfrr_data` JSON parsing with directional SA/DA requested, satisfied, locally activated, clearing/settlement price, nested price-entry, and missingness preservation in `src/open_energy_lab/market/rte.py`
- [X] T031 [US1] Implement complete in-memory validation and atomic `fetch_rte_restoration_data` publication with market-response digests, per-series provenance, restricted-policy metadata, and no OAuth evidence in `src/open_energy_lab/market/rte.py`
- [X] T032 [US1] Implement request-compatible immutable `refresh_rte_restoration_data` with unchanged/no-write, changed/one-successor, and failure/preserve-current outcomes in `src/open_energy_lab/market/rte.py`
- [X] T033 [US1] Implement the strict allowlisted dotenv reader and explicit RTE fetch/refresh CLI, reading credentials only inside the selected operation, in `examples/restoration_services/fetch_rte_period.py`

**Checkpoint**: US1 passes entirely with authored fixtures and injected
transports; the optional live check confirms current production compatibility
without becoming a routine correctness dependency.

---

## Phase 4: User Story 2 - Replay Automatic Restoration Delivery (Priority: P1)

**Goal**: Build fixed directional aFRR commitments and replay a complete signed
automatic trajectory against one BESS with auditable tracking, limits,
headroom, energy, and deterministic non-performance.

**Independent Test**: Run a hand-calculable trajectory containing upward,
downward, zero, ramp-limited, power-limited, SOC-limited, and headroom-limited
segments and reproduce every request, delivery, state, cause, energy total, and
fingerprint within `1e-6`.

### Tests and Fixtures for User Story 2

- [X] T034 [P] [US2] Encode the hand-calculable two-direction aFRR inputs and published expected samples/aggregates in `tests/fixtures/restoration/manual_afrr_v1.json`
- [X] T035 [P] [US2] Add failing tests for signed interval-average aFRR trajectories, exact coverage, direct energy integration, explicit `created_or_retrieved_at_utc` provenance, no interpolation/upsampling, opposing RTE-need rejection, fixed-fraction mapping, capacity rejection, and fingerprints in `tests/unit/market/test_afrr_activation.py`
- [X] T036 [P] [US2] Add failing tests for aFRR directional commitments, zero/fixed/deterministic baselines, baseline bounds, temporal alignment, usable energy, capability checks, and activation lookahead prohibition in `tests/unit/control/test_afrr_restoration.py`
- [X] T037 [P] [US2] Add failing tests for aFRR request/delivery attribution, directional headroom, tracking error, response delay, ramp, power/SOC/energy saturation, zero activation, ordered causes, aggregation conservation, and determinism in `tests/unit/simulator/test_afrr_restoration.py`
- [X] T038 [US2] Add the failing end-to-end manual aFRR oracle and repeated-fingerprint assertions using `tests/fixtures/restoration/manual_afrr_v1.json` in `tests/integration/simulator/test_afrr_restoration_manual.py`

### Implementation for User Story 2

- [X] T039 [P] [US2] Implement immutable `AFRRActivationSample`/`AFRRActivationTrajectory`, explicit creation-or-retrieval provenance time included in identity, RTE-requested-need mapping, ambiguity rejection, exact integration, serialization, and fingerprints in `src/open_energy_lab/market/restoration_activation.py`
- [X] T040 [P] [US2] Implement aFRR fixed directional schedule validation and no-lookahead baseline builders that reserve asymmetric power/energy headroom in `src/open_energy_lab/control/restoration_service.py`
- [X] T041 [US2] Implement exact `AFRRReplayRequest` validation and charge-positive sample replay through the shared capability layer and unchanged `apply_power_request` in `src/open_energy_lab/simulator/restoration_service.py`
- [X] T042 [US2] Implement aFRR per-sample/directional tracking, response, headroom, saturation duration, delivered/undelivered energy, conserved aggregates, diagnostics, and result fingerprints in `src/open_energy_lab/simulator/restoration_service.py`
- [X] T043 [US2] Publish lazy source-independent aFRR activation, control, and replay exports and exact module-owner assertions in `src/open_energy_lab/market/__init__.py`, `src/open_energy_lab/control/__init__.py`, `src/open_energy_lab/simulator/__init__.py`, and `tests/unit/test_import_contract.py`

**Checkpoint**: US2 is independently usable with synthetic canonical inputs,
never accesses a source adapter, and reports complete physical performance.

---

## Phase 5: User Story 3 - Replay Manual Restoration Events (Priority: P1)

**Goal**: Build fixed directional mFRR commitments and replay distinct
scheduled/direct manual events with exact delay/ramp/hold/ramp timing, energy,
delivery, and non-performance.

**Independent Test**: Replay one upward scheduled event and one downward direct
event, verify the analytic energy and every requested/actual timing and physical
value within `1e-6`, and reject every overlapping or cross-product input before
replay.

### Tests and Fixtures for User Story 3

- [X] T044 [P] [US3] Encode hand-calculable upward-SA, downward-DA, delayed/ramped, zero-activation, and overlapping-invalid mFRR inputs with expected event/sample results in `tests/fixtures/restoration/manual_mfrr_v1.json`
- [X] T045 [P] [US3] Add failing tests for exact SA/DA identities, direction-plus-magnitude inputs, delay/ramp/hold/ramp shapes, analytic event energy, complete horizon coverage, deterministic order, every overlap, sparse DA, and fingerprints in `tests/unit/market/test_mfrr_activation.py`
- [X] T046 [P] [US3] Add failing tests for mFRR directional commitments, product-specific fixed/deterministic baselines, activation-time/duration capability, headroom, temporal alignment, and no-lookahead behavior in `tests/unit/control/test_mfrr_restoration.py`
- [X] T047 [P] [US3] Add failing tests for event expansion, requested/actual starts/completions, SA/DA separation, ramp/timing/duration/power/SOC shortfalls, zero activation, event/aggregate energy conservation, and determinism in `tests/unit/simulator/test_mfrr_restoration.py`
- [X] T048 [US3] Add the failing end-to-end manual mFRR oracle, overlap rejection, and FCR/aFRR/mFRR exact-type substitution assertions using `tests/fixtures/restoration/manual_mfrr_v1.json` in `tests/integration/simulator/test_mfrr_restoration_manual.py`

### Implementation for User Story 3

- [X] T049 [P] [US3] Implement immutable `MFRRActivationEvent`/`MFRRActivationSequence`, analytic piecewise energy, SA/DA identity, overlap validation, RTE-SA requested-volume mapping, serialization, and fingerprints in `src/open_energy_lab/market/restoration_activation.py`
- [X] T050 [P] [US3] Implement mFRR fixed directional schedule validation and product-specific no-lookahead baseline builders with activation-time/duration and asymmetric headroom checks in `src/open_energy_lab/control/restoration_service.py`
- [X] T051 [US3] Implement exact `MFRRReplayRequest` validation, boundary-conserving event expansion, capability enforcement, and unchanged battery-transition replay in `src/open_energy_lab/simulator/restoration_service.py`
- [X] T052 [US3] Implement per-event SA/DA performance, requested/actual timing, requested/delivered/undelivered energy, ramp/duration causes, aggregate conservation, diagnostics, and result fingerprints in `src/open_energy_lab/simulator/restoration_service.py`
- [X] T053 [US3] Publish lazy source-independent mFRR activation/control/replay exports and exact module-owner assertions in `src/open_energy_lab/market/__init__.py`, `src/open_energy_lab/control/__init__.py`, `src/open_energy_lab/simulator/__init__.py`, and `tests/unit/test_import_contract.py`

**Checkpoint**: US3 is independently usable with synthetic canonical events;
SA and DA remain distinct and no overlap or product substitution is accepted.

---

## Phase 6: User Story 4 - Audit Product-Specific Economics (Priority: P2)

**Goal**: Settle either aFRR or mFRR with separately inspectable day-ahead,
directional capacity, activated energy, penalty, degradation, gross, and net
components while keeping incomplete settlement atomically unavailable.

**Independent Test**: Supply fixed prices, commitments, delivered energy,
shortfall, and throughput costs for each product; reproduce every component and
the reconciliation identity within `1e-6`, then remove or mismatch each required
price and verify physical replay remains available with no partial total.

### Tests and Fixtures for User Story 4

- [X] T054 [P] [US4] Add failing tests for immutable directional capacity/activation prices, units, currency, period coverage, eligibility, penalty rules, degradation rules, unconfigured statuses, and fingerprints in `tests/unit/simulator/test_restoration_settlement_rules.py`
- [X] T055 [P] [US4] Add failing tests proving missing/null/ambiguous/wrong-product/wrong-direction/wrong-unit/uncovered required prices make the whole settlement and net result unavailable while retaining physical replay in `tests/unit/simulator/test_restoration_settlement_availability.py`
- [X] T056 [P] [US4] Add failing tests for source-fingerprinted RTE weighted-average/clearing/settlement area-price mappings, direction/interval compatibility, `scenario_proxy` labels, and rejection of asset-invoice claims in `tests/unit/simulator/test_restoration_price_proxy.py`
- [X] T057 [US4] Add hand-calculable aFRR and mFRR settlement integration cases covering both directions, SA/DA price identity, zero activation, penalties, throughput, degradation, unavailable totals, and exact reconciliation in `tests/integration/simulator/test_restoration_settlement_manual.py`

### Implementation for User Story 4

- [X] T058 [US4] Implement directional price, area-price proxy, penalty, degradation, component-status, and settlement result entities with validation/fingerprints in `src/open_energy_lab/simulator/restoration_settlement.py`
- [X] T059 [US4] Implement atomic settlement-availability validation and source/field/period diagnostics without substituting zero or emitting partial totals in `src/open_energy_lab/simulator/restoration_settlement.py`
- [X] T060 [US4] Implement baseline day-ahead, eligible directional capacity, delivered directional activation-energy, and SA/DA-compatible revenue calculations with exact kW/MW and kWh/MWh conversions in `src/open_energy_lab/simulator/restoration_settlement.py`
- [X] T061 [US4] Implement explicit non-performance penalty and battery-terminal throughput degradation-proxy calculations with zero/unconfigured behavior in `src/open_energy_lab/simulator/restoration_settlement.py`
- [X] T062 [US4] Implement product-specific gross/net reconciliation, omission of unselected product fields, zero-activation behavior, canonical serialization, and deterministic settlement fingerprints in `src/open_energy_lab/simulator/restoration_settlement.py`
- [X] T063 [US4] Publish lazy restoration settlement exports and import-boundary coverage without changing FCR settlement exports in `src/open_energy_lab/simulator/__init__.py` and `tests/unit/simulator/test_import_boundary.py`

**Checkpoint**: US4 settles either product from synthetic replay results and
never hides a missing price or collapses the economics into one opaque total.

---

## Phase 7: User Story 5 - Learn and Reproduce the Feature Offline (Priority: P2)

**Goal**: Publish restricted, bounded real-data demonstrations, an offline
runner, precise source/redistribution documentation, and a documented notebook
with complete plots plus a separately guarded live section.

**Independent Test**: With credentials unset and sockets blocked, execute the
offline runner and every notebook cell in order, reproduce byte-stable artifact
and result fingerprints, and verify all required variable groups, provenance,
derived-simulation labels, and settlement components are displayed while the
live section remains disabled.

### Tests and Fixture Production for User Story 5

- [X] T064 [P] [US5] Add failing staging tests for exact RTE profiles/periods/fields, four aFRR records, nonzero downward SA requested/satisfied mFRR values, freshly recorded valid SHA-256 raw digests, semantic comparison with planning evidence without failing solely on digest drift, secret sentinels, restricted metadata, fixed destinations, and no raw OAuth/market body persistence in `tests/integration/market/test_restoration_reference_staging.py`
- [X] T065 [US5] Implement the fixed-destination staging CLI that consumes explicitly acquired artifacts, performs exact profile/period/field validation, records fresh digest and transformation metadata, reports planning-evidence drift, scans for secrets, publishes normalized data only, reads no credentials itself, and refuses public/package/release/mirror/CI-artifact/external-store targets in `examples/restoration_services/stage_private_reference_data.py`
- [X] T066 [US5] Use the explicit credentialed acquisition/staging workflow to publish only normalized restricted artifacts for aFRR `[2026-08-20T00:00:00Z,2026-08-20T01:00:00Z)` and mFRR `[2026-08-15T10:15:00Z,2026-08-15T10:30:00Z)` in `tests/fixtures/restoration/france_2026-08-20_afrr_market_v1.json` and `tests/fixtures/restoration/france_2026-08-15_mfrr_market_v1.json`
- [X] T067 [US5] Generate fixed-fraction `0.001` derived-simulation artifacts with chronological aFRR requests and the explicit rectangular downward-SA event assumption in `tests/fixtures/restoration/france_2026-08-20_afrr_scenario_v1.json` and `tests/fixtures/restoration/france_2026-08-15_mfrr_scenario_v1.json`
- [X] T068 [US5] Implement deterministic fixture loading, replay, proxy settlement, and expected-result generation with full input/result fingerprints in `examples/restoration_services/generate_reference_results.py` and `tests/fixtures/restoration/france_restoration_expected_results_v1.json`
- [X] T069 [P] [US5] Add zero-network real-data integration tests for exact source fields, mappings, aFRR replay, mFRR SA replay, sparse DA reporting, proxy labels, physical bounds, settlement reconciliation, and two-run fingerprint stability in `tests/integration/simulator/test_restoration_real_replays.py`
- [X] T070 [P] [US5] Implement the default offline artifact/mapping/replay/settlement consumer with concise audit tables and zero live imports in `examples/restoration_services/run_offline_replays.py`

### Documentation and Notebook for User Story 5

- [X] T071 [P] [US5] Document RTE Balancing Energy 5.2 OAuth, v5 paths, sanitized requests, exact aFRR/mFRR fields, units, PT15M resolution, UTC/Europe-Paris handling, source date/window rules, errors, ownership, terms, and area-versus-asset meaning in `docs/architecture/rte-balancing-energy.md`, and document that first-release complementary ENTSO-E support is limited to selecting the time-compatible A44 `day_ahead_price` series by fingerprint from the existing Feature 010 `fr-day-ahead-symmetric-fcr-v1` artifact, with bundle-only composition, inherited fetch/refresh/offline behavior, and no fallback in `docs/architecture/entsoe-transparency-platform.md`
- [X] T072 [P] [US5] Document ownership boundaries, fixed-fraction derivation, simulator assumptions, synthetic-versus-real evidence, Feature 010 preservation, and explicit exclusions in `docs/migration/afrr-mfrr-services.md`
- [X] T073 [P] [US5] Update restricted-source attribution, generation commands, fingerprints, retention, redistribution, visibility-change, refresh, and expected-invariant records in `tests/fixtures/restoration/README.md`, `tests/fixtures/restoration/RESTRICTED_DATA.md`, and `docs/migration/restricted-reference-fixtures.md`
- [X] T074 [P] [US5] Add failing source-structure tests for stable cell IDs, empty saved outputs, `RUN_LIVE_QUERY = False`, credential/live imports inside the guard, export disabled by default, required explanations, and all required plot/table variables in `tests/unit/simulator/test_restoration_services_notebook.py`
- [X] T075 [P] [US5] Add an optional `nbclient` notebook-group execution test that blocks sockets and credential access, executes all offline cells in order, and validates produced tables/figures without making notebook tooling a core dependency in `tests/integration/simulator/test_restoration_notebook_execution.py`
- [X] T076 [US5] Implement the offline notebook narrative, non-technical aFRR/mFRR-SA/mFRR-DA explanations, artifact provenance, mapping, commitments, activation, BESS response, SOC/headroom, performance, throughput/degradation, and settlement plots in `examples/restoration_services/restoration_services_walkthrough.ipynb`
- [X] T077 [US5] Add the separately guarded caller-period RTE live-query section and an optional ENTSO-E branch limited to the existing Feature 010 `fr-day-ahead-symmetric-fcr-v1` lifecycle; select only a time-compatible A44 `day_ahead_price` series by fingerprint or report that no compatible profile was selected, with no raw persistence or saved secret/output state in `examples/restoration_services/restoration_services_walkthrough.ipynb`
- [X] T078 [P] [US5] Align exact offline, `nbclient` execution, JupyterLab interaction, live fetch/refresh, staging, existing-profile-only ENTSO-E composition, and expected-failure commands in `examples/restoration_services/README.md` and `specs/011-afrr-mfrr-services/quickstart.md`
- [X] T079 [P] [US5] Add every restricted Feature 011 fixture to build exclusions and prove zero occurrence in wheel, sdist, release/public-CI paths, mirrors, or external upload manifests in `pyproject.toml` and `tests/unit/test_migration_policy_docs.py`
- [X] T080 [P] [US5] Add documentation completeness tests mapping each demonstrated field to owner, source version, request meaning, unit, resolution, time convention, transformation, redistribution status, and observed/derived identity in `tests/unit/market/test_restoration_source_documentation.py`
- [X] T081 [US5] Execute the offline runner and notebook validation, clear notebook outputs/execution counts, and pin the resulting expected display/result fingerprints in `examples/restoration_services/restoration_services_walkthrough.ipynb` and `tests/fixtures/restoration/france_restoration_expected_results_v1.json`

**Checkpoint**: US5 is a complete offline working example. Live access is
optional, explicit, non-persisting, and irrelevant to routine reproducibility.

---

## Phase 8: User Story 6 - Preserve Validated FCR Behavior (Priority: P3)

**Goal**: Prove Feature 011 is additive: Feature 010 types, public symbols,
fixture bytes, physical results, settlement results, and import boundaries do
not change, and all reserve-product substitutions fail.

**Independent Test**: Run the complete existing Feature 010 offline suite and
reference comparisons unchanged, compare all three stored FCR fixtures
byte-for-byte, then pass each FCR/aFRR/mFRR activation input to the wrong replay
profile and verify rejection before dispatch.

- [X] T082 [P] [US6] Add public-symbol, exact-type, constructor, serialization, and module-owner snapshots for Feature 010 market/control/simulator contracts in `tests/integration/simulator/test_restoration_fcr_public_compatibility.py`
- [X] T083 [P] [US6] Add exhaustive FCR/aFRR/mFRR trajectory/event/commitment/result cross-substitution rejection cases in `tests/integration/simulator/test_restoration_product_separation.py`
- [X] T084 [P] [US6] Add byte-stability assertions for the Feature 010 market, activation, and expected-replay fixtures plus unchanged recorded fingerprints in `tests/integration/simulator/test_restoration_fcr_fixture_compatibility.py`
- [X] T085 [US6] Run the unchanged Feature 010 manual, compatibility, generation, real-replay, notebook, market, control, and settlement suites and fix only additive Feature 011 code when regressions are exposed in `src/open_energy_lab/market/`, `src/open_energy_lab/control/`, and `src/open_energy_lab/simulator/`
- [X] T086 [US6] Run the explicitly selected unchanged Feature 010 reference benchmark and record any environment-only limitation without weakening correctness in `specs/011-afrr-mfrr-services/quickstart.md`
- [X] T087 [US6] Verify package-root lazy imports and zero `legacy/*`, notebook, source-adapter, credential, solver, GPU/SLURM, or experiment-tracker leakage from offline surfaces in `tests/unit/test_lazy_dependency_boundaries.py`, `tests/unit/test_import_contract.py`, and `tests/unit/test_no_legacy_imports.py`

**Checkpoint**: All Feature 010 behavior remains byte/API compatible and every
reserve identity boundary is enforced before replay.

---

## Phase 9: Polish and Cross-Cutting Validation

**Purpose**: Close documentation, security, packaging, determinism, and full
offline validation across all stories.

- [ ] T088 [P] Add Feature 011 source/design/example links without implying production dispatch or optimization in `README.md`, `docs/architecture/README.md`, and `docs/migration/README.md`
- [ ] T089 [P] Run credential/token sentinel scans over source, tests, fixtures, docs, examples, notebook JSON, filenames, captured diagnostics, and generated artifacts and add any missing assertions in `tests/unit/market/test_rte_environment.py`
- [ ] T090 Run wheel and sdist builds, inspect their complete file lists for restricted fixtures, and record the reproducible commands and expected exclusions in `specs/011-afrr-mfrr-services/quickstart.md`
- [ ] T091 Run the full offline market, control, simulator, restoration integration, import-boundary, policy, and Feature 010 regression commands from `specs/011-afrr-mfrr-services/plan.md` and resolve all failures in the files named by those failures
- [ ] T092 Run the offline runner, synthetic oracle, real replay, and optional notebook-group commands from `specs/011-afrr-mfrr-services/quickstart.md` and align any stale command/path expectations in `examples/restoration_services/README.md`
- [ ] T093 Verify CPU-only package imports and scan for forbidden `from legacy`/`import legacy` references across `src/open_energy_lab/market/`, `src/open_energy_lab/control/`, `src/open_energy_lab/simulator/`, and their Feature 011 test directories
- [ ] T094 Document any optional live RTE/ENTSO-E, notebook runtime, or reference-benchmark check that could not run and why, without weakening offline acceptance, in `specs/011-afrr-mfrr-services/quickstart.md`
- [ ] T095 Add deterministic bounded-scaling tests using counted observations, samples, and event segments to verify validation, replay, event expansion, aggregation, and fingerprinting visit inputs only a bounded constant number of times and retain linear-size results without introducing a wall-clock acceptance threshold in `tests/unit/simulator/test_restoration_scaling.py`

---

## Dependencies and Execution Order

### Phase Dependencies

```text
Phase 1: Setup
  -> Phase 2: Foundational restoration boundaries
       ├── Phase 3: US1 trustworthy acquisition (MVP)
       ├── Phase 4: US2 aFRR replay
       ├── Phase 5: US3 mFRR replay
       │    (US2 and US3 share only completed Phase 2 primitives)
       ├── Phase 8: US6 compatibility tests may start
       └── US2 + US3 -> Phase 6: US4 economics

US1 + US2 + US3 + US4
  -> Phase 7: US5 real offline demonstration and notebook

US1 through US5
  -> finish Phase 8: US6 complete compatibility gate
  -> Phase 9: polish and full validation
```

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 and independently delivers immutable
  trustworthy acquisition/offline loading.
- **US2 (P1)**: Depends only on Phase 2 and independently delivers synthetic
  aFRR control and physical replay.
- **US3 (P1)**: Depends only on Phase 2 and independently delivers synthetic
  mFRR control and physical replay; it does not depend on US2 implementation.
- **US4 (P2)**: Depends on completed US2 and US3 replay result contracts.
- **US5 (P2)**: Depends on US1 acquisition, US2/US3 replay, and US4 settlement.
- **US6 (P3)**: Compatibility tests can begin after Phase 2; final completion
  follows all additive implementations.

### Within Each User Story

1. Authored fixtures and failing contract tests
2. Immutable models and validation
3. Source/control/replay/settlement services
4. Integration and deterministic expected results
5. Public exports, examples, and documentation

---

## Parallel Execution Examples

### User Story 1

After T019 supplies synthetic payloads, run T020, T021, T022, T023, T024,
T025, and T026 across their separate test files. After request/transport types
exist, parser implementation remains serialized within `rte.py` while bundle
validation and the example CLI can proceed in their own files.

### User Story 2

Run T034, T035, T036, and T037 in parallel, then add T038. After the failing
contracts exist, T039 and T040 can proceed in parallel before T041-T042 connect
them through replay.

### User Story 3

Run T044, T045, T046, and T047 in parallel, then add T048. T049 and T050 can
proceed in parallel before T051-T052 connect events and commitments to replay.

### User Story 4

Run T054, T055, and T056 in parallel, then add T057. Settlement implementation
T058-T062 is serialized in one module to avoid conflicting edits.

### User Story 5

After T066-T068 publish the governed reference inputs/results, run T069-T075,
T078-T080 across separate test, script, and documentation files. T076-T077 then
assemble the notebook against stable offline APIs.

### User Story 6

Run T082, T083, and T084 in parallel. T085-T087 then execute the compatibility,
benchmark, and import-boundary gates against the completed additive feature.

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete US1 only.
3. Demonstrate explicit RTE fetch/refresh, immutable artifacts, a multi-source
   reference bundle, credential-safe diagnostics, and zero-network offline load.
4. Validate before adding BESS activation or settlement behavior.

### Incremental Delivery

1. **US1**: trusted source data and offline artifacts
2. **US2**: independent aFRR automatic tracking slice
3. **US3**: independent mFRR scheduled/direct event slice
4. **US4**: product-specific economics and unavailable-settlement behavior
5. **US5**: governed real-data examples, documentation, and notebook
6. **US6**: complete additive compatibility proof
7. **Polish**: packaging, security, full offline suite, and optional-check notes

### Guardrails

- Do not modify `legacy/*`.
- Do not widen Feature 010 closed schemas or change its fixture bytes.
- Do not persist credentials, OAuth responses, tokens, or raw source bodies.
- Do not infer asset dispatch from area prices, satisfied need, or activated
  volume.
- Do not interpolate, upsample, net, normalize, or clip activation inputs.
- Do not make live retrieval or notebook execution part of core imports or
  routine correctness validation.
