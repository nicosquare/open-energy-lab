# Feature Specification: FCR Rolling Backtest Parity

**Feature Branch**: `015-fcr-rolling-backtest-parity`
**Created**: 2026-08-28
**Status**: Draft
**Input**: User description: "Implement a deterministic, offline-by-default rolling backtest for the pinned robust-storage-bidding reference's non-intraday Experiments 1-5, reusing Feature 013 for bid optimization and Feature 012 for all physical replay and settlement, with bounded Julia/Gurobi evidence and explicit causal, carry-over, resume, and parity semantics."

## Purpose *(mandatory)*

Give storage-market researchers a reproducible way to determine whether Open
Energy Lab can match the pinned reference's multi-day, non-intraday behavior,
not merely one isolated daily schedule. The study must cover independent daily
solves, midnight stored-energy carry-over, and 08:00 overlapping-horizon bidding
without exposing future activation or evaluation results to bid selection.

The feature extends the existing single-day bidder and common evaluator into a
versioned study workflow. Feature 013 remains responsible for bid optimization,
and Feature 012 remains the sole authority for battery transitions, physical
tracking, settlement, and realized profit. This prevents rolling orchestration
from creating a second physical or accounting model whose behavior could drift
from the common evaluation environment.

The scientific outcome must distinguish what the evidence actually proves.
Agreement with a displayed, three-decimal source schedule is different from
compatibility with its rounding intervals; a feasible incumbent from a
time-limited solve is different from a proven optimum. The resulting records
must preserve these distinctions, retain incomplete and failed dates, and avoid
claiming paper-table parity when source labels cannot be reconciled.

## Clarifications

### Session 2026-08-28

- Q: Which battery stored-energy value initializes the next coupled optimization? → A: Feature 012's realized stored energy at the handoff; Feature 013's modeled terminal stored energy remains separate optimization evidence.
- Q: How is a delivery day represented as it changes from provisional to finalized? → A: One delivery-date record envelope contains immutable original, provisional, and finalized revisions.
- Q: May a coupled study continue after a failed predecessor by accepting a caller-supplied battery state? → A: Yes. A fingerprinted state with provenance starts a new continuity segment, and no continuity or parity claim crosses the failed gap.
- Q: How are execution purpose and parity-comparison eligibility represented for each requested date? → A: Each date has exactly one execution role (`included`, `warm-up`, `close-out`, or `excluded`) plus a separate comparison-eligibility flag; only included dates may be comparison-eligible.
- Q: Which coupled profiles support a native full-precision handoff instead of source-compatible three-decimal rounding? → A: Experiment 5 supports both policies; Experiment 4 always uses the source-compatible three-decimal 08:00 handoff.
- Q: How many experiment profiles may one rolling-study manifest execute? → A: Exactly one; cross-profile analysis combines separate study results.
- Q: What happens when a rolling-study manifest omits its bid-acceptance policy? → A: Validation fails; every manifest must explicitly declare assumed acceptance or fingerprinted evidence-backed individual acceptance.
- Q: What evidence remains when the manifest declares an activation artifact but its samples are unavailable at execution time? → A: Eligible independent optimization may produce an optimization-only result with replay unavailable; every handoff requiring activation-derived state is blocked.
- Q: How are study aggregates reported when some otherwise eligible dates lack the required evidence? → A: Publish coverage-labelled partial aggregates with exact contributing dates and omission reasons; complete-study parity requires complete coverage.
- Q: How is one overall source-comparison summary derived from field-level outcomes that are not naturally ordered? → A: Field outcomes remain authoritative; report compatibility as `compatible`, `incompatible`, or `incomplete` plus the canonically ordered evidence bases used.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability, reference-method migration, and validation
- **Target surface**: Public rolling-study inputs and immutable results; experiment profiles; bounded normalized reference fixture; offline research and resume workflow
- **Legacy reference paths**: None. `legacy/*` remains out of scope. The pinned implementation under `baselines/robust_storage_bidding/` is reference evidence only.
- **New-code location**: Reusable code under `src/open_energy_lab`, with validation under `tests`; exact package and module placement is deferred to planning. No reusable code belongs under `baselines/*` or `legacy/*`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproduce the Five Non-Intraday Profiles (Priority: P1)

As a storage-market researcher, I need one common study interface that can run
each of the five pinned non-intraday experiment profiles separately so that I can compare reset-day, FCR-disabled,
midnight carry-over, and 08:00 rolling behavior without manually joining daily
outputs.

**Why this priority**: The feature's central research question cannot be
answered unless every requested reference profile has an explicit and
reviewable native meaning.

**Independent Test**: A reviewer can construct and solve one bounded authored
problem for each executable profile and verify its formulation classification,
FCR policy, required coupling inputs, plan classification, date treatment, and
ordered delivery-date record-envelope structure without external reference
artifacts. Complete causal 08:00 chaining and realized midnight handoff are
validated independently by User Stories 2 and 3.

**Acceptance Scenarios**:

1. **Given** a valid ordered manifest of ordinary delivery days, **When** Experiment 1 is selected, **Then** every included day is solved independently with the relaxation profile, its plan is classified diagnostic and non-robust, and no previous-day state is reused.
2. **Given** the same manifest, **When** Experiment 2 is selected, **Then** every included day is solved independently with the restriction profile and only plans passing Feature 013's deployability policy may be classified deployable.
3. **Given** the same manifest, **When** Experiment 3 is selected, **Then** every FCR capacity decision is constrained to exactly zero and the resulting study reports day-ahead arbitrage only.
4. **Given** explicit valid predecessor fixings and a cutoff state, **When** an Experiment 4 problem is constructed, **Then** its profile declares the 08:00 cutoff, accepted-overlap fixing contract, source-compatible handoff requirement, and initialization/finalization semantics; User Story 2 validates the complete causal chain.
5. **Given** an explicit valid predecessor state, **When** an Experiment 5 problem is constructed, **Then** its restriction profile requires that state under the selected midnight carry-over policy; User Story 3 validates its derivation from realized predecessor replay.
6. **Given** a profile label from a paper or workbook, **When** its relationship to the executable scripts cannot be reconciled field by field, **Then** the study reports the discrepancy and makes no Table A1 parity claim.

---

### User Story 2 - Preserve Causal 08:00 Bidding (Priority: P1)

As a researcher evaluating rolling bids, I need the 08:00 bidder to see only
accepted prior decisions and activation observed by its information cutoff so
that apparent parity cannot be produced by future-data leakage.

**Why this priority**: Causal information boundaries are necessary for a valid
backtest; matching source numbers with future activation would not reproduce a
usable bidding process.

**Independent Test**: Two inputs that are identical through 08:00 but differ in
later activation produce exactly the same optimization problem, accepted fixed
decisions, bidding-time stored energy, and bid-selection fingerprints.

**Acceptance Scenarios**:

1. **Given** an accepted predecessor plan and activation samples ending at the declared 08:00 cutoff, **When** bidding-time stored energy is derived, **Then** the realized state comes from Feature 012's existing physical replay behavior, is retained as evidence, and its source-compatible three-decimal value initializes the next Experiment 4 optimization.
2. **Given** two activation traces that are identical through the cutoff and differ afterward, **When** the next rolling bid is selected, **Then** the bid-selection inputs, fixed prior decisions, cutoff state, problem fingerprint, and selected decisions are unchanged.
3. **Given** hourly energy and four-hour FCR decisions already accepted for overlapping delivery intervals, **When** the next problem is formed, **Then** those decisions retain their identities and values and cannot be re-optimized.
4. **Given** the first bounded source date, **When** no earlier 08:00 solve exists to finalize it, **Then** it is retained and labelled initialization-only rather than counted as complete comparison evidence.
5. **Given** the last bounded source date, **When** no following 08:00 solve has finalized its delivery record, **Then** it is retained as unfinalized and excluded explicitly from finalized parity aggregates.
6. **Given** a following 08:00 solve, **When** a provisional daily result is finalized, **Then** one delivery-date record envelope retains separately identifiable immutable original, provisional, and finalized revisions rather than replacing evidence or adding a second top-level entry for the date.

---

### User Story 3 - Carry Stored Energy Across Midnight (Priority: P1)

As a researcher reproducing the source trajectory, I need explicit rounded and
full-precision state carry-over policies so that source parity and native
numerical behavior are both available without conflating their fingerprints or
claims.

**Why this priority**: A small rounding difference in one terminal state can
change all later daily decisions, so the selected carry-over rule is part of the
experiment rather than a display detail.

**Independent Test**: A hand-calculable three-day case produces the declared
initial and terminal stored energy under each policy, with exact predecessor
links and distinct semantic fingerprints.

**Acceptance Scenarios**:

1. **Given** the source-compatible carry-over profile, **When** one day completes, **Then** its eligible realized Feature 012 terminal stored energy is rounded to three decimals by the declared source rule before becoming the next day's initial stored energy.
2. **Given** the native full-precision profile, **When** one day completes, **Then** its eligible full-precision realized Feature 012 terminal stored energy becomes the next day's initial stored energy without source rounding.
3. **Given** otherwise identical studies using the two carry-over profiles, **When** their identities are computed, **Then** their manifests, daily inputs, and study fingerprints are distinct and later schedule equality is not assumed.
4. **Given** a coupled day whose declared initial stored energy does not reconcile with its predecessor's carried state, **When** validation runs, **Then** the inconsistency is rejected before optimization.
5. **Given** a predecessor without a valid carry state, **When** the next coupled day is reached, **Then** the day remains in the study as blocked-by-predecessor unless a fingerprinted caller-supplied state with provenance starts a new continuity segment; the failed gap remains visible and no continuity or parity claim crosses it.

---

### User Story 4 - Inspect Complete and Resumable Study Evidence (Priority: P1)

As a researcher running multi-day studies, I need every requested date and its
lineage retained through failures, interruptions, and restarts so that aggregate
results are reproducible and cannot hide missing or incompatible work.

**Why this priority**: A backtest that silently drops failures or resumes under
changed assumptions can produce convincing but invalid aggregate results.

**Independent Test**: A bounded study containing a successful day, a failed
day, and dependent and independent successors yields the expected statuses,
aggregates, and resume decisions under fixed fingerprints.

**Acceptance Scenarios**:

1. **Given** a requested delivery date that fails before or during optimization or evaluation, **When** the study completes, **Then** that date appears in ordered results with its failure status and diagnostics and is not omitted from completeness accounting.
2. **Given** a failure in an independent reset-day profile, **When** later independent dates are processed, **Then** they may continue and remain independently attributable.
3. **Given** a failure in a coupled profile, **When** later dependent dates are processed without an explicit valid state, **Then** they are retained as blocked-by-predecessor and are not solved using an invented state; when a fingerprinted caller-supplied state with provenance is accepted, later work begins a separately identified continuity segment.
4. **Given** a prior partial result, **When** resume is requested with exact agreement on the manifest, semantic profile, completed-day fingerprints, and carry-over state, **Then** valid completed work may be reused without changing final semantic results.
5. **Given** a change in solver policy, source artifact, date ordering, rounding policy, activation input, or completed-day evidence, **When** reuse of an existing continuity segment is requested, **Then** incompatible reuse is rejected actionably; a caller-supplied state may only begin a new segment and cannot make the prior gap continuous.
6. **Given** a completed or partial study, **When** aggregates are formed, **Then** requested, included, compared, finalized, failed, blocked, excluded, warm-up, close-out, and unfinalized counts reconcile exactly with the retained delivery-date record envelopes and their applicable revisions; each metric identifies its exact contributing dates, omission reasons, and complete or partial coverage.
7. **Given** two runs with identical semantic inputs and decisions but different runtime durations, **When** study identity is computed, **Then** their semantic fingerprints are equal while runtime evidence remains reportable outside that identity.

---

### User Story 5 - Interpret Source Parity Without Overclaiming (Priority: P1)

As a reviewer, I need native results compared with the bounded Julia/Gurobi
oracle using evidence-aware statuses so that time-limited incumbents, source
rounding, multiple optima, and missing proof are not collapsed into a generic
"parity" claim.

**Why this priority**: The value of the migration is its defensible evidence.
Numerical resemblance alone is insufficient when the source outputs are rounded
or the source solver stopped at a time limit.

**Independent Test**: Without reading the baseline tree at runtime, a reviewer
can compare normalized evidence for 2023-06-17 through 2023-06-20 and inspect
field-level and study-level outcomes for objectives, bounds, decisions,
feasibility, finalization, and provenance.

**Acceptance Scenarios**:

1. **Given** native decisions exactly equal to all displayed source decisions and compatible objective and feasibility evidence, **When** comparison runs, **Then** exact displayed-decision parity is reported with the underlying field evidence.
2. **Given** native values that differ only within closed intervals implied by source rounding, **When** joint interval-aware feasibility and objective checks pass, **Then** source-precision compatibility is reported without claiming exact decision equality.
3. **Given** materially different native and source decision regions with sufficient optimality evidence and common-feasibility evidence, **When** objectives are equivalent under the declared policy, **Then** alternative-optimum compatibility may be reported and the differences remain visible.
4. **Given** a source solve that ended with a feasible incumbent and upper bound at its time limit, **When** native evidence is compared, **Then** the outcome distinguishes source-incumbent equivalence, an improved feasible incumbent compatible with the source bound, and bound incompatibility as applicable; it never calls two time-limited incumbents alternative optima solely because their objectives are close.
5. **Given** insufficient termination, feasibility, objective, or decision evidence, **When** comparison runs, **Then** the affected outcome is unavailable, incomplete, or unfinalized rather than inferred.
6. **Given** incompatible values outside both the source-precision and native tolerance policies, **When** comparison runs, **Then** it reports mismatch with ordered field-level reasons.
7. **Given** the rerun of Experiment 2 on 2023-06-18, **When** it is normalized, **Then** it remains distinct from Feature 013's governed original fixture, preserves that fixture unchanged, and compares semantic fields rather than raw-file identity.
8. **Given** source restriction output containing `bilinear_violations=0`, **When** feasibility is assessed, **Then** that field is not accepted as independent proof and Feature 013's formulation audit supplies the feasibility evidence.
9. **Given** the bounded 08:00 profile, **When** parity evidence is summarized, **Then** 2023-06-18 and 2023-06-19 are the primary paired comparison dates, 2023-06-17 is initialization evidence, and 2023-06-20 is close-out evidence rather than a finalized delivery result.
10. **Given** required comparison fields with different evidence outcomes, **When** an overall summary is formed, **Then** every field outcome remains authoritative, the summary reports `incompatible` when any required field proves mismatch or bound incompatibility, `incomplete` when no incompatibility is proven but required evidence is unavailable or unfinalized, and `compatible` only when every required field has compatible evidence; the canonically ordered evidence bases remain visible.

---

### User Story 6 - Replay and Settle Through One Common Environment (Priority: P2)

As a bidder-comparison researcher, I need every eligible daily plan evaluated by
the same physical and financial contracts so that optimization parity and
realized performance remain separate, comparable claims.

**Why this priority**: Reusing one environment protects the validity of later
comparisons among robust, heuristic, TPM, and manually authored plans.

**Independent Test**: An authored multi-day study can trace every cutoff-state
and full-day replay to Feature 012, reconcile each settlement with study totals,
and demonstrate that optimization objectives and best bounds are never used as
realized profit.

**Acceptance Scenarios**:

1. **Given** an eligible restriction plan and an accepted activation input, **When** full-day evaluation runs, **Then** Feature 012 alone produces the physical trace, tracking, settlement, realized profit, diagnostics, and their fingerprints.
2. **Given** relaxation decisions, **When** diagnostic replay is explicitly requested, **Then** they are labelled non-robust diagnostic plans and are never presented as robustly deployable even when the realized trace happens to be feasible.
3. **Given** a study result, **When** financial evidence is displayed, **Then** ex-ante objective, best bound, realized settlement components, and realized profit remain separately named, fingerprinted, and aggregated.
4. **Given** a declared external activation artifact whose samples are absent, **When** an independent optimization or optimization comparison runs, **Then** it may produce an optimization-only result, all replay and settlement fields are explicitly unavailable, any activation-dependent successor is blocked, and no replacement activation or state is searched for, downloaded, inferred, or silently substituted.
5. **Given** the external activation file is supplied explicitly for the bounded reference dates, **When** optional replay runs, **Then** its descriptor and fingerprint are recorded and its daily and aggregate outputs use the same Feature 012 contracts as authored cases.

---

### User Story 7 - Validate the Workflow Offline (Priority: P2)

As a maintainer, I need a bounded routine validation path and clearly separated
research-scale checks so that ordinary continuous integration remains
deterministic while the complete reference comparison is still reproducible on
demand.

**Why this priority**: Solver-heavy or licensed checks must not make the shared
library unreliable, but their absence must remain visible rather than weakening
the evidence claim.

**Independent Test**: A clean offline environment can run hand-calculable
oracles, bounded deterministic optimization cases, authored multi-day replay,
and normalized-fixture checks twice with identical semantic results and without
reference runtimes, licenses, credentials, or network access.

**Acceptance Scenarios**:

1. **Given** an ordinary offline CPU environment with required project dependencies, **When** routine validation runs, **Then** it uses bounded cases and committed normalized evidence without accessing the network, credentials, Julia, Gurobi, raw generated baseline outputs, or the complete activation file.
2. **Given** identical bounded inputs and deterministic solve policy, **When** the study is repeated in the same supported environment, **Then** every semantic fingerprint, ordered status, decision, and aggregate is identical.
3. **Given** an unavailable or incompatible required routine optimization backend, **When** a solve is requested, **Then** it fails actionably rather than silently selecting a different backend or weakening validation.
4. **Given** no licensed exact solver, **When** routine validation runs, **Then** all required evidence remains available and optional licensed evidence is reported as unavailable.
5. **Given** the complete four-day native reference solve, **When** it is requested, **Then** it runs only through the explicit reference-benchmark workflow and is not required for routine acceptance.
6. **Given** the full 2020-07-01 through 2024-06-30 date range, **When** a researcher elects to run it, **Then** it is treated as an optional resumable research study rather than a release or acceptance requirement.

### Edge Cases

- A requested date is not an ordinary 24-hour delivery day, falls on a daylight-saving transition, is duplicated, is out of order, has more than one execution role, or is marked comparison-eligible while its execution role is not included.
- A manifest selects zero or multiple experiment profiles; it is rejected rather than producing a study with mixed formulation, coupling, or aggregation semantics.
- A manifest omits a required descriptor, unit, sign, temporal mapping, provenance field, fingerprint, cutoff, solver policy, terminal rule, acceptance assumption, or normalized-fixture lineage.
- An acceptance policy is omitted, has an unknown value, labels an assumption as evidence, or selects evidence-backed acceptance without an individual acceptance descriptor and fingerprint; validation fails before study execution.
- Hourly energy prices, four-hour FCR prices, quarter-hour planning intervals, or ten-second activation samples are incomplete, duplicated, overlapping, misaligned, non-finite, or attributed to a different delivery day.
- A market-data descriptor attempts to infer individual bid acceptance from system-wide contracted reserve volume; the study rejects that claim and requires an explicit accepted-bid assumption or actual individual evidence.
- An independent-day profile accidentally receives a predecessor state, or a coupled profile lacks a required predecessor identity and carried state.
- Source-compatible rounding produces signed zero, a midpoint, or a state close to a stored-energy boundary; the declared rounding rule is applied deterministically before validation, and it does not widen physical tolerances. Experiment 4 always applies this rule at its 08:00 handoff, while Experiment 5 applies it only under its source-compatible policy.
- A full-precision trajectory diverges from source-rounded later decisions; this is expected evidence under a distinct profile and is not automatically a mismatch.
- The activation trace changes after the 08:00 cutoff; bid selection and cutoff-state identity remain unchanged while later replay and settlement may legitimately change.
- An activation sample at the exact cutoff boundary is included or excluded inconsistently; the manifest's interval-closure rule is authoritative and fingerprinted.
- Accepted predecessor energy or FCR decisions are missing, overlap incorrectly, or conflict with the rolling lower-index mapping; the next problem is rejected rather than repairing or re-optimizing them.
- A cutoff-state replay saturates, tracks imperfectly, or fails physical validation; the observed result is retained and dependent bidding cannot proceed from an invalid invented state.
- A restriction solve returns a feasible incumbent at a limit without proving optimality; deployability remains governed by Feature 013's explicit incumbent opt-in and independent audit policy.
- A relaxation decision replays successfully; it remains diagnostic and non-robust.
- Zero FCR prices are present in an arbitrage-only study; every FCR decision is still fixed exactly to zero, so zero prices alone are not treated as the disabling mechanism.
- A failed independent day is followed by valid independent dates; those dates may continue, but completeness metrics retain the failure.
- A coupled predecessor fails, is excluded, remains provisional, or lacks an eligible carried state; all dependent dates remain visible and blocked until a valid caller-supplied state starts a new continuity segment.
- A caller-supplied state follows a failed or missing predecessor; its value, unit, effective handoff, provenance, and fingerprint are required, it begins a new continuity segment, and aggregate or source-comparison evidence must not bridge the discontinuity.
- Resume input has matching dates but a different order, solver policy, semantic profile, rounding rule, activation fingerprint, fixture lineage, or prior result fingerprint; reuse is rejected.
- A runtime duration, host detail, or other volatile field changes while semantic inputs are unchanged; it remains reportable but does not alter the semantic fingerprint.
- One or more aggregation-eligible dates lack a metric because they failed, are blocked, remain unfinalized, or lack activation; the available values may form a partial aggregate only when its exact contributing dates, omitted dates and reasons, and partial status are retained, and missing values are never replaced with zero.
- A source JSON value lies exactly on a three-decimal rounding boundary; comparison uses a closed, explicitly defined precision interval and does not replace it with the native solver tolerance.
- A source log lacks enough information to establish termination or an upper bound; the corresponding evidence is unavailable rather than inferred from the JSON.
- A source solve reached its 900-second limit; its objective is interpreted as an incumbent and its best bound as a bound, not as proof of optimality.
- Script, workbook, and paper profile labels or aggregate fields disagree; the discrepancy is retained and unsupported Table A1 claims are prohibited.
- The external regulation CSV is absent, corrupt, has the wrong fingerprint, or covers the wrong dates; optional replay skips or fails actionably without affecting required offline optimization evidence.
- Declared activation samples are unavailable after an eligible optimization result is produced; the delivery-date record remains as optimization-only evidence, evaluation fields remain unavailable, and no continuity segment may cross an activation-dependent handoff until valid samples are supplied.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST provide an immutable, versioned rolling-study manifest that completely identifies one ordered multi-day research study and selects exactly one experiment profile.
- **FR-002**: The manifest MUST assign every requested ordinary delivery date exactly one execution role from `included`, `warm-up`, `close-out`, and `excluded`, plus a separate comparison-eligibility flag. Only an `included` date MAY be comparison-eligible; initialization, provisional, finalized, failed, blocked, and unfinalized are result lifecycle states rather than manifest execution roles.
- **FR-003**: The manifest MUST preserve the requested date order and MUST reject duplicates, implicit reordering, non-ordinary 24-hour delivery days, multiple execution roles, and comparison eligibility on a non-included date for the initial reference profiles.
- **FR-004**: The manifest MUST identify day-ahead prices, four-hour FCR capacity prices, and the expected ten-second activation artifact with units, signs, temporal mappings, provenance, and content fingerprints. The activation descriptor is mandatory even when its samples are not locally available at execution time, and sample availability MUST be recorded separately from artifact identity.
- **FR-005**: The manifest MUST identify battery parameters, both uncertainty sets and their derivation, terminal rule, solver policy, settlement profile, experiment profile, and numeric policy without weakening Feature 013's single-day definitions.
- **FR-006**: The manifest MUST identify decision cutoffs and information cutoffs separately and MUST define interval-boundary treatment at each cutoff.
- **FR-007**: The manifest MUST identify reset, midnight carry-over, and 08:00 bidding-state semantics, including predecessor eligibility and initial, cutoff, terminal, and carried stored-energy meanings.
- **FR-008**: The manifest MUST identify source-compatible three-decimal and native full-precision carry-over as distinct Experiment 5 policies with distinct semantic fingerprints. Experiment 4 MUST identify only its source-compatible three-decimal handoff policy and MUST reject a full-precision Experiment 4 variant.
- **FR-009**: The manifest MUST define resume, failure propagation, aggregation, accepted-bid, and normalized-reference-lineage policies. The accepted-bid policy MUST be explicit and MUST have exactly one value: `assumed_accepted` or `evidence_backed_accepted`; omission or an unknown value MUST fail validation before study execution.
- **FR-010**: An `assumed_accepted` policy MUST identify and fingerprint the assumption that optimizer-selected bids are accepted and MUST NOT present it as market evidence. An `evidence_backed_accepted` policy MUST identify and fingerprint individual bid-acceptance evidence. Neither policy may infer individual acceptance from system-wide contracted reserve volume, and no profile may supply a silent default.
- **FR-011**: The feature MUST preserve Feature 013's existing exact single-day 24-hour, 96-quarter-hour, 24-energy-block, and six-FCR-block public contract and fingerprints.
- **FR-012**: Rolling behavior MUST be represented through additive study contracts and MUST NOT broaden, reinterpret, or silently migrate existing Feature 013 inputs or results.
- **FR-013**: The feature MUST provide five explicit profiles whose authoritative executable meanings correspond to reference scripts `11.jl` through `15.jl`; cross-profile analysis MUST consume separate study results rather than mix profiles within one result.
- **FR-014**: Experiment 1 MUST use the relaxation with independently reset midnight days and MUST classify any replayable decisions as diagnostic and non-robust.
- **FR-015**: Experiment 2 MUST use the restriction with independently reset midnight days and MUST apply Feature 013's deployability and feasible-incumbent opt-in rules unchanged.
- **FR-016**: Experiment 3 MUST model day-ahead arbitrage with all six FCR capacity decisions constrained exactly to zero, independent of FCR price values.
- **FR-017**: Experiment 4 MUST reproduce the reference's 08:00 overlapping-horizon indexing, lower-index derivation, accepted-decision fixing, source-compatible three-decimal bidding-state handoff, and daily finalization semantics.
- **FR-018**: Experiment 5 MUST reproduce restriction bidding with midnight stored-energy carry-over between consecutive eligible delivery days.
- **FR-019**: Every coupled daily problem MUST derive its Feature 013 battery input from the valid realized Feature 012 stored energy at the declared handoff and MUST reconcile that initial state with its predecessor record; Feature 013's modeled terminal stored energy MUST remain separate optimization evidence and MUST NOT initialize the successor.
- **FR-020**: Source-compatible midnight carry-over MUST apply the declared three-decimal source rounding rule to the eligible realized Feature 012 terminal stored energy before constructing the successor's initial state.
- **FR-021**: Native full-precision carry-over MUST retain the eligible realized Feature 012 terminal stored energy without source rounding and MUST NOT claim that later decisions should match the source-rounded trajectory.
- **FR-022**: The 08:00 profile MUST represent previously accepted hourly energy and four-hour FCR decisions explicitly, preserve their interval identities, and prevent their re-optimization.
- **FR-023**: The 08:00 bidding-time stored energy MUST be derived only from the accepted plan and activation observed through the declared cutoff using Feature 012's physical replay behavior. The realized cutoff value MUST remain recorded as physical evidence, while its deterministic source-compatible three-decimal value MUST be the state supplied to the next Experiment 4 optimization. If the required samples are unavailable, no cutoff state may be inferred and every dependent successor MUST remain blocked.
- **FR-024**: Bid selection MUST NOT receive activation after the information cutoff, future physical replay results, future settlement, or future realized profit.
- **FR-025**: Changes confined to activation after the cutoff MUST NOT change the next bid-selection input, cutoff stored energy, optimization problem, fixed decisions, or their fingerprints.
- **FR-026**: The 08:00 profile MUST retain one delivery-date record envelope per requested date containing separately identifiable immutable original, provisional, and finalized revisions with predecessor and finalizer lineage.
- **FR-027**: The 08:00 profile MUST retain the applicable first day as initialization-only and the applicable last delivery record as unfinalized until a following 08:00 solve closes it.
- **FR-028**: Initialization-only and unfinalized edge records MUST be excluded explicitly from finalized parity aggregates while remaining present in requested-date counts and study results.
- **FR-029**: Relaxation decisions MUST remain upper-bound or diagnostic evidence and MUST never be labelled robustly deployable.
- **FR-030**: Restriction decisions MUST remain subject to Feature 013's modeled-slack, independent-residual, solve-status, and feasible-incumbent acceptance policies.
- **FR-031**: Ex-ante optimization objective, best bound, realized Feature 012 settlement, and realized profit MUST remain distinct named quantities with separate evidence and fingerprints.
- **FR-032**: The feature MUST use Feature 012 as the sole physical replay, tracking, settlement, and realized-profit authority for cutoff and full-day evaluation.
- **FR-033**: The feature MUST NOT introduce a second battery transition, tracking, settlement, or profit model.
- **FR-034**: Every requested date MUST produce or retain exactly one immutable delivery-date record envelope, including excluded, initialization-only, optimization-only, provisional, finalized, failed, blocked-by-predecessor, and unfinalized dates; lifecycle revisions MUST NOT create duplicate top-level date entries.
- **FR-035**: Each delivery-date record envelope MUST identify the study, profile, delivery date, decision and information cutoffs, predecessor, current status, and the identities and relationships of every retained revision.
- **FR-036**: Each applicable revision within a delivery-date record envelope MUST carry input, problem, plan, activation, replay, settlement, result, predecessor, and finalizer fingerprints and MUST mark unavailable fingerprints explicitly.
- **FR-037**: Each applicable revision MUST report initial, realized cutoff, handed-off cutoff, realized terminal, and carried stored energy with units and applicability so that any source-compatible rounding remains visible.
- **FR-038**: Each applicable solved revision MUST report solve status, termination status, incumbent objective, best bound, absolute and relative gap, and runtime metadata without treating volatile duration as semantic identity.
- **FR-039**: Each applicable solved revision MUST retain all 24 hourly energy decisions, all six four-hour FCR decisions, modeled feasibility slacks, independent residual-audit evidence, and ordered diagnostics.
- **FR-040**: Each applicable evaluated revision MUST retain Feature 012 replay and settlement fingerprints and the metrics required to reconcile daily and study-level results. When declared activation samples are unavailable, an otherwise eligible independent solve MAY retain an optimization-only revision, but every replay, settlement, activation-derived state, and realized-profit field MUST be explicitly unavailable.
- **FR-041**: A deterministic study result MUST contain exactly one delivery-date record envelope for every requested date in manifest order, coverage-labelled aggregate metrics, completeness status, ordered diagnostics, comparison outcomes, and one semantic fingerprint.
- **FR-042**: The study semantic fingerprint MUST include all semantically relevant manifest, profile, lineage, daily-result, carry-over, and aggregation evidence. It MUST exclude volatile solver runtime duration, execution-host identity, process-local metadata, and caller-local filesystem paths. Solver policy and version, content fingerprints, market-interval timestamps, decision and information cutoffs, and provenance MUST remain semantic.
- **FR-043**: No failed, blocked, excluded, provisional, initialization-only, close-out, or unfinalized date may disappear from the study result or completeness accounting.
- **FR-044**: Independent reset-day profiles MAY continue after a failed or optimization-only date; coupled profiles MUST mark each activation-dependent successor blocked when required samples or a valid handoff state are unavailable, unless a caller supplies a valid state with its unit, effective handoff, provenance, and fingerprint. An accepted caller-supplied state MUST begin a new identified continuity segment and MUST NOT erase or repair the missing physical evidence.
- **FR-045**: Every study aggregate metric MUST reconcile exactly with its declared eligible revisions and MUST retain the ordered contributing dates, every omitted otherwise-eligible date and reason, and a `complete` or `partial` coverage status. A partial aggregate MAY be reported, but missing values MUST NOT be replaced with zero and partial coverage MUST NOT support complete-study parity. Study-level counts MUST separately reconcile every requested-date status.
- **FR-046**: Resume MUST require exact agreement of the study manifest, semantic profile, date order, solver and numeric policies, source and activation artifacts, completed-day fingerprints, and carry-over state.
- **FR-047**: Resume MUST reject reused evidence from a different rounding policy, source lineage, accepted-bid assumption, settlement profile, or any other fingerprint-bearing semantic input.
- **FR-048**: Resuming a compatible partial continuity segment MUST produce the same final semantic result as uninterrupted execution of that segment with the same accepted solve outcomes. A segment begun from a caller-supplied state MUST remain distinct and MUST NOT support continuity, carry-over parity, or aggregate parity claims across the preceding gap.
- **FR-049**: The bounded source oracle MUST identify reference revision `7e44738bb30e5c8204efe40103b9be4c2203685c`, dates 2023-06-17 through 2023-06-20, scripts `11.jl` through `15.jl`, outputs under `results/01` through `results/05`, and their retained source logs.
- **FR-050**: The normalized source evidence MUST record Julia 1.10.1 and Gurobi 11.0.3 runtime evidence and MUST record committed manifest package versions separately from versions stated by the reference README.
- **FR-051**: The normalized fixture MUST be small, immutable, provenance-rich, and derived only through an explicit normalization workflow that pins the digest of every raw generated JSON and log used.
- **FR-052**: The normalized fixture MUST NOT include raw logs, the complete regulation CSV, the baseline workbook, or a wholesale copy of all generated source JSON files.
- **FR-053**: Production and routine validation MUST consume only normalized committed evidence and MUST NOT read raw generated source logs or JSON files directly.
- **FR-054**: Feature 013's governed 2023-06-18 Experiment 2 fixture MUST remain unchanged; the new rerun MUST be separate evidence and MUST be compared semantically rather than by raw digest.
- **FR-055**: Source values recorded to three decimals MUST be interpreted through closed source-precision intervals distinct from native feasibility, solver, and objective-comparison tolerances.
- **FR-056**: Source feasibility MUST be established through Feature 013's independent formulation audit; the restriction JSON's `bilinear_violations=0` field MUST NOT be treated as independent feasibility proof.
- **FR-057**: Termination and bound evidence MUST be normalized from retained source logs and MUST distinguish proven optimal results from feasible incumbents returned at the 900-second limit.
- **FR-058**: Field-level comparison MUST support the distinct outcomes exact displayed-decision parity, source-precision compatibility, alternative-optimum compatibility, source-incumbent equivalence, improved feasible incumbent compatible with the source bound, bound incompatibility, mismatch, unavailable, and incomplete or unfinalized evidence. These outcomes MUST NOT be treated as one total severity order.
- **FR-059**: Alternative-optimum compatibility MUST require sufficient optimality evidence for both sides, common-feasibility evidence, and objective equivalence under the declared policy; objective proximity between time-limited incumbents alone MUST NOT qualify.
- **FR-060**: A different native decision vector MAY be accepted only when it passes the same independent formulation audit and its objective relationship is justified by the source incumbent, source bound, source-precision envelope, and declared native tolerance.
- **FR-061**: Comparison MUST retain authoritative field-level evidence for incumbent objective, best bound, all 24 hourly energy decisions, all six four-hour FCR decisions, feasibility, termination, finalization, and schedule fingerprints where supported. An overall summary MUST report both a compatibility class and the canonically ordered distinct field-evidence bases: `incompatible` when any required field proves mismatch or bound incompatibility; otherwise `incomplete` when any required field is unavailable, incomplete, or unfinalized; otherwise `compatible`. The summary MUST NOT replace or hide any field outcome.
- **FR-062**: The bounded oracle MUST use 2023-06-18 and 2023-06-19 as primary paired comparison dates for the 08:00 profile, 2023-06-17 as initialization, and the 2023-06-20 solve as close-out without treating that date's unfinalized delivery record as complete parity evidence.
- **FR-063**: The feature MUST audit the executable scripts' relationship to `results/result_overview.xlsx` and the paper's labels and field meanings, report unresolved discrepancies, and prohibit Table A1 parity claims unless exact reconciliation is documented.
- **FR-064**: Routine validation MUST include hand-calculable orchestration cases for date ordering, ordinary-day filtering, 08:00 lower-index derivation, fixed decisions, cutoff-state derivation, both carry-over policies, finalization, failure propagation, and aggregate reconciliation.
- **FR-065**: Routine validation MUST include deterministic bounded required-backend cases for independent days, exact FCR disabling, midnight coupling, 08:00 overlap, infeasibility, feasible-incumbent handling, restart compatibility, and repeatability.
- **FR-066**: Routine validation MUST include authored multi-day physical replay and settlement solely through Feature 012, causal cutoff-state checks, and exact reconciliation of eligible daily metrics with study aggregates.
- **FR-067**: Validation MUST compare bounded native evidence directly with the normalized Julia/Gurobi fixture for the 2023-06-17 through 2023-06-20 source run.
- **FR-068**: Routine validation MUST remain deterministic and offline and MUST NOT require the complete four-day native reference solve.
- **FR-069**: The complete four-day native reference solve MUST be an explicit `reference_benchmark` workflow rather than a routine acceptance requirement.
- **FR-070**: Full 2020-07-01 through 2024-06-30 execution MUST remain an optional resumable research workflow and MUST NOT be an acceptance requirement.
- **FR-071**: An optional `external_reference_data` bounded replay MAY use only an explicitly supplied regulation CSV, MUST verify its descriptor and fingerprint, and MUST skip actionably when it is absent.
- **FR-072**: No production or routine-test path may import from `baselines` or `legacy`, invoke Julia, require Gurobi, access the network, inspect credentials, search for external data, use future activation in bid selection, or require full-history completion.
- **FR-073**: Pyomo, the required routine HiGHS backend, and optional Gurobi evidence MUST preserve the repository's existing lazy import boundaries; an unavailable required routine backend MUST fail actionably.
- **FR-074**: No additional RTE or ENTSO-E document type, intraday recourse, Experiment 6-9 behavior, scenario generation, TPM fitting or bid selection, aFRR/mFRR bidding, degradation cost, or live data acquisition may be introduced by this feature.

### Reference Requirements

- **Source paths**:
  - `baselines/robust_storage_bidding/code/01_datastruct.jl`
  - `baselines/robust_storage_bidding/code/02_model.jl`
  - `baselines/robust_storage_bidding/code/03_backtest_save.jl`
  - `baselines/robust_storage_bidding/code/04_parse_results.jl`
  - `baselines/robust_storage_bidding/code/05_dates.txt`
  - `baselines/robust_storage_bidding/code/11.jl`
  - `baselines/robust_storage_bidding/code/12.jl`
  - `baselines/robust_storage_bidding/code/13.jl`
  - `baselines/robust_storage_bidding/code/14.jl`
  - `baselines/robust_storage_bidding/code/15.jl`
  - Generated bounded-run JSON files under `baselines/robust_storage_bidding/results/01` through `results/05` for 2023-06-17 through 2023-06-20, each included only as digest-pinned normalization input
  - Generated bounded-run logs under `baselines/robust_storage_bidding/code/`, each included only as digest-pinned normalization input
  - `baselines/robust_storage_bidding/results/result_overview.xlsx`, only for claims with explicitly reconciled profile mapping and field meaning
- **Behavior to preserve**: The executable definitions of the five non-intraday profiles; source time and decision mappings; independent reset days; exact FCR disabling; rounded midnight carry-over; 08:00 overlapping fixed decisions and finalization; source termination, incumbent, bound, and runtime evidence; and displayed three-decimal results.
- **Behavior to improve or drop**: Replace implicit date roles, mutable aggregation, ambiguous profile labels, hidden rounding, silent failure omission, and overbroad optimal-parity language with versioned contracts and evidence-aware statuses. Do not preserve runtime access to source files, hardcoded `bilinear_violations=0` as proof, false individual-acceptance claims from system volume, or any future-information leakage.
- **Parity evidence**: Hand-calculable orchestration oracles; bounded deterministic native studies; independent Feature 013 residual audits; Feature 012 replay and settlement; a normalized fixture with every source digest and provenance field pinned; explicit source-precision intervals; and optional activation-backed replay when the caller supplies the governed external file.

### Key Entities

- **Rolling Study Manifest**: Immutable identity of exactly one experiment profile together with ordered dates, date roles, data descriptors, battery and uncertainty assumptions, terminal and solver policies, cutoffs, carry-over, acceptance, failure, resume, aggregation, and reference lineage. A cross-profile analysis references multiple separate manifests and study results.
- **Rolling Experiment Profile**: Versioned meaning of one of Experiments 1-5, including formulation classification, reset or coupling mode, bid time, fixed-decision rules, carry-over precision, finalization, and deployability classification. Experiment 4 permits only a source-compatible three-decimal handoff; Experiment 5 provides separate source-compatible and native full-precision variants.
- **Delivery-Date Classification**: Exactly one execution role (`included`, `warm-up`, `close-out`, or `excluded`) plus a separate comparison-eligibility flag. Only included dates may be comparison-eligible. Initialization-only, optimization-only, provisional, finalized, failed, blocked, and unfinalized describe record lifecycle rather than manifest classification.
- **Accepted Decision Set**: Hourly energy and four-hour FCR decisions already committed for overlapping intervals, with plan identity, interval mapping, acceptance assumption or evidence, and protection from re-optimization.
- **Rolling State Link**: Provenance-rich relationship among a predecessor's eligible stored-energy evidence and a successor's initial or cutoff state, including rounding policy, units, and reconciliation status.
- **Delivery-Date Record Envelope**: The single immutable top-level entry for one requested date. It carries current status and an ordered set of immutable original, optimization-only, provisional, and finalized revisions, each retaining applicable inputs, decisions, solve evidence, state values, audits, replay, settlement, diagnostics, and fingerprints. Failed, blocked, excluded, initialization-only, and unfinalized dates remain represented by their single envelope even when no solved revision exists.
- **Study Result**: Ordered collection containing exactly one delivery-date record envelope for every requested date plus identified continuity segments, reconciled coverage-labelled aggregates, completeness evidence, comparison outcomes, diagnostics, and a semantic fingerprint governed by FR-042: volatile runtime duration, execution-host/process metadata, and caller-local paths are excluded, while solver/version, content, cutoff, interval, and provenance evidence remains semantic.
- **Aggregate Metric Evidence**: One named ex-ante or ex-post aggregate with its value when available, eligible-date rule, ordered contributing dates, omitted dates and reasons, and `complete` or `partial` coverage. Partial evidence is useful diagnostically but cannot establish complete-study parity.
- **Resume Evidence**: Partial-study identity, completed-day fingerprints, carry state, and compatibility decision governing whether earlier work may be reused. A caller-supplied state additionally carries its unit, effective handoff, provenance, and fingerprint and starts a new continuity segment rather than repairing a failed one.
- **Normalized Source Fixture**: Small committed representation of digest-pinned Julia/Gurobi outputs and logs, including provenance, versions, displayed decisions, objectives, bounds, termination evidence, date roles, precision policy, and unavailable fields.
- **Source Comparison Result**: Authoritative field-level evidence assigning only the declared parity, incumbent, bound, mismatch, unavailable, or incomplete outcomes, plus a separate overall compatibility class and canonically ordered evidence bases. Compatibility is `incompatible` when any required field proves mismatch or bound incompatibility, otherwise `incomplete` when required evidence is unavailable or unfinalized, and otherwise `compatible`; no total ordering of the nine field outcomes is implied.
- **Activation Data Descriptor**: Mandatory expected identity of the separately sourced ten-second signal, including coverage, cadence, units, sign, provenance, content fingerprint, and information-availability boundary. Local sample availability is separate execution evidence; absence permits only eligible optimization-only results and never an inferred replay or coupled handoff.
- **Accepted-Bid Policy**: Mandatory fingerprinted statement selecting exactly one of `assumed_accepted` or `evidence_backed_accepted`. The former records a visible assumption; the latter requires a descriptor and fingerprint for individual acceptance evidence. There is no implicit default, and system-wide contracted reserve volume is insufficient evidence.

### Dependency and Environment Requirements

- **Core dependencies**: Existing Feature 012 evaluation and Feature 013 bidding contracts, including their existing lazy Pyomo integration and required deterministic HiGHS path. No second simulator or settlement dependency is permitted.
- **Optional dependencies**: Gurobi is optional research evidence only. The complete external activation CSV and full reference benchmark inputs are caller-supplied research artifacts, not core dependencies.
- **External services**: None. Routine operation and validation are offline; no credentials or network service may be inspected.
- **Hardware assumptions**: Ordinary CPU environment for routine bounded validation. No GPU, SLURM environment, Julia runtime, or commercial solver license is required for routine acceptance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The manifest contract can select each of the five requested non-intraday experiment profiles but exactly one per study, and five bounded authored studies demonstrate the correct formulation, FCR, reset/coupling, cutoff, and finalization semantics for 5 of 5 profiles without mixed-profile results.
- **SC-002**: For every study, 100% of requested dates have exactly one valid execution role and appear exactly once in manifest order in completeness accounting; comparison eligibility is recorded separately, and all successful, failed, blocked, excluded, initialization-only, close-out, provisional, finalized, and unfinalized evidence remains attributable to its date.
- **SC-003**: In causal 08:00 tests, changing any activation value strictly after the declared cutoff changes 0 bid-selection inputs, fixed decisions, cutoff-state values, optimization problem fingerprints, or selected-plan fingerprints.
- **SC-004**: In hand-calculable midnight studies, 100% of successor initial states reconcile with their eligible predecessor carry state under the selected three-decimal or full-precision policy, and the two policies have distinct fingerprints.
- **SC-005**: Every eligible cutoff-state and full-day physical result in validation is traceable to Feature 012, with 0 duplicate battery-transition, tracking, settlement, or realized-profit calculations in the rolling feature.
- **SC-006**: For every evaluated study, 100% of reported optimization-objective, best-bound, settlement, and realized-profit aggregates reconcile exactly with their declared contributing dates under the numeric policy, retain all omission reasons and coverage status, and never substitute zero for unavailable evidence; the four quantity families remain separate.
- **SC-007**: The normalized bounded oracle covers all 5 profiles and all 4 dates from 2023-06-17 through 2023-06-20, pins 100% of raw JSON and log inputs by digest, and preserves Feature 013's governed fixture byte-for-byte.
- **SC-008**: Every native-to-source field comparison assigns one of the nine declared evidence outcomes and includes the objective, bound, 24 hourly energy decisions, six FCR decisions, feasibility, termination, and finalization evidence wherever the source supports them; 100% of overall summaries preserve those field outcomes and deterministically report the separate compatibility class and canonical evidence bases.
- **SC-009**: All time-limited source cases are reported as incumbent-and-bound evidence with 0 unsupported claims of proven optimality or alternative optima.
- **SC-010**: Compatible partial continuity segments resume to the same semantic fingerprint as uninterrupted execution of those segments, while each tested change to date order, solver policy, source lineage, rounding policy, activation identity, or carry state is rejected; every caller-supplied restart state creates a distinct segment with 0 cross-gap continuity or parity claims.
- **SC-011**: Routine validation completes twice offline with identical semantic fingerprints and requires 0 network calls, credential reads, Julia invocations, Gurobi licenses, raw baseline-runtime reads, or external activation files.
- **SC-012**: Missing optional activation data and optional licensed evidence produce actionable unavailable or skipped outcomes while 100% of required routine validation remains runnable; eligible independent solves retain optimization-only evidence, 100% of activation-dependent fields are unavailable, and 100% of dependent handoffs are blocked rather than inferred.
- **SC-013**: Any unresolved mismatch among executable scripts, workbook fields, and paper labels is documented, and the feature makes 0 Table A1 parity claims until exact reconciliation exists.
- **SC-014**: Reviewers can identify from one study result whether the study is complete, which dates are comparable, why any date failed or was blocked, which carry-over policy was used, and whether each source claim concerns exact decisions, precision compatibility, an incumbent, a bound, or proven optimal evidence.

## Assumptions

- Researchers use the unified Open Energy Lab contracts from Python, while the pinned Julia project remains reference-only evidence and is never a production runtime dependency.
- Feature 013 remains the authority for single-day restriction and relaxation formulation, solver evidence, deployability, decision canonicalization, and independent residual audits.
- Feature 012 remains the authority for activation binding, battery transitions, tracking, settlement, realized profit, and physical-result fingerprints.
- The initial rolling profiles cover ordinary 24-hour Europe/Paris delivery days with the existing 24/96/6 planning grids and 8,640 ten-second activation samples when full replay is requested; daylight-saving transition days are excluded rather than resampled.
- The study uses the existing hourly French day-ahead price evidence, four-hour FCR capacity prices, and separately sourced ten-second activation trace. No new RTE or ENTSO-E document type is needed.
- Optimizer-selected FCR commitments are treated as accepted only when every manifest explicitly selects and fingerprints either the visible `assumed_accepted` policy or an `evidence_backed_accepted` policy with individual evidence; no profile supplies that policy implicitly.
- The source's three-decimal serialization describes closed precision intervals and is not exact full-precision evidence. Native feasibility and objective tolerances remain separate.
- Generated bounded-run JSON and logs are available only to the fixture-normalization workflow; their normalized fixture is the sole routine comparison input.
- The complete four-day native solve can be substantially slower than bounded routine cases, so it remains an explicit reference benchmark. The full historical period remains optional research work.
- Intraday recourse, Experiments 6-9, scenario generation, TPM fitting or bid selection, aFRR/mFRR bidding, degradation costs, live acquisition, required full-history execution, and new market-data document types remain out of scope.
