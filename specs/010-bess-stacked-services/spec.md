# Feature Specification: BESS Stacked Services

**Feature Branch**: `010-bess-stacked-services`  
**Created**: 2026-08-21  
**Status**: Draft  
**Input**: User description: "Provide the first end-to-end French BESS simulation for day-ahead energy arbitrage stacked with symmetric Frequency Containment Reserve, backed by explicit ENTSO-E historical-data workflows and deterministic offline replay."

## Purpose *(mandatory)*

Add the first trustworthy end-to-end battery energy storage system (BESS)
service-stacking capability to the unified Open Energy Lab library. A
researcher will be able to acquire a bounded historical French market period,
preserve it as a reusable source-independent artifact, combine a fixed
day-ahead energy schedule with a symmetric FCR commitment and an explicit
high-resolution activation trace, and inspect both physical delivery and
settlement outcomes without relying on notebooks or hidden network access.

The feature establishes three deliberately separate responsibilities:
market-data production owns retrieval, normalization, validation, and
provenance; the simulator owns battery physics, delivery limitations, and
realized accounting; later optimization features may choose bids but do not
belong here. This boundary creates validated behavior that the following
robust-bidding feature can consume without embedding source-specific data
handling or redefining battery semantics.

## Clarifications

### Session 2026-08-21

- Q: How should terminal SOC be handled in the first release? → A: Use an
  optional terminal target; report deviation and compliance, but do not alter
  dispatch or profit.
- Q: What does each canonical FCR activation value represent? → A: The
  interval-average activation over its half-open `[start, end)` sample interval.
- Q: How should periods containing partial energy or FCR product blocks be
  handled? → A: Fetch may preserve any bounded period, but replay requires
  complete product blocks.
- Q: What raw-source evidence should the canonical market artifact retain? →
  A: Always retain a digest and source metadata; keep a raw response only as an
  optional separate sidecar when its terms permit retention.
- Q: How should delivery shortfall be allocated between the energy baseline and
  FCR? → A: Treat the accepted day-ahead baseline as the performance reference;
  deviation during a nonzero FCR commitment counts as FCR non-delivery.
- Q: How should the regulation-only deterministic baseline maintain SOC
  headroom? → A: Use a zero energy baseline, the efficiency-aware centered
  initial SOC, and a fixed FCR commitment, with no recovery schedule.
- Q: How should the deterministic stacked heuristic preserve FCR headroom? →
  A: Reserve symmetric FCR power first and cap the existing deterministic
  arbitrage request to the remaining charge/discharge power.
- Q: How should explicit fetch or refresh handle transient ENTSO-E failures? →
  A: Retry transient failures for up to three total attempts, then fail
  atomically; permanent client errors fail immediately.
- Q: How should refresh handle an older revision for the same source data? →
  A: Reject the revision regression, preserve the current artifact, and report
  the stale source response.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability
- **Target surface**: Public market-data and simulator library surfaces,
  versioned data artifacts, deterministic fixtures, and an offline end-to-end
  demonstration
- **Legacy reference paths**: None. Existing `legacy/*` projects are not
  runtime dependencies or migration targets for this feature.
- **New-code location**:
  - `src/open_energy_lab/market` for source adapters and the source-independent
    market-data artifact boundary
  - `src/open_energy_lab/simulator` for stacked-service physical replay and
    settlement behavior
  - matching validation under `tests/unit`, `tests/integration`, and
    `tests/fixtures`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Produce A Reusable French Market Artifact (Priority: P1)

As a researcher, I need to retrieve a caller-selected historical French
market period using my own ENTSO-E credential and preserve the required series
in a validated artifact so that I can reuse the same market inputs without
coupling studies to a live service.

**Why this priority**: Trustworthy market inputs, temporal alignment, and
secret handling are prerequisites for any real-data stacked-service result.

**Independent Test**: Using a credentialed test period, a reviewer can perform
one explicit fetch, inspect the artifact and captured diagnostics for required
series and provenance, verify that a sentinel credential is absent, and load
the artifact again with network access disabled.

**Acceptance Scenarios**:

1. **Given** a valid caller-provided credential, the France area, and a valid
   start-inclusive/end-exclusive historical period, **When** the caller
   explicitly fetches the period, **Then** the producer retrieves day-ahead
   prices plus applicable symmetric-FCR capacity volumes and prices and writes
   one validated versioned artifact with complete provenance.
2. **Given** an existing artifact and the same requested period, **When** the
   caller explicitly refreshes it, **Then** the producer reports whether the
   source content changed and creates a linked new immutable version only when
   the normalized source content or source revision changed.
3. **Given** an existing valid artifact and no credential or network access,
   **When** the caller selects offline replay, **Then** the artifact loads and
   validates without initiating any network operation.
4. **Given** an empty response, missing required series, incompatible FCR
   product, gap, conflicting duplicate, or unsupported resolution, **When**
   fetch or refresh validates the response, **Then** it fails with the source,
   series, period, and incompatibility identified and does not publish a
   complete artifact.
5. **Given** a timeout, rate limit, connection interruption, or transient
   server error, **When** fetch or refresh cannot complete within three total
   attempts, **Then** it reports the attempts and final failure without
   publishing any partial artifact.
6. **Given** an existing artifact and a refresh response with a lower revision
   for the same source, document, series, and covered period, **When** refresh
   validates lineage, **Then** it reports a revision regression, preserves the
   current artifact, and publishes no replacement.

---

### User Story 2 - Replay Fixed Arbitrage And FCR Commitments (Priority: P1)

As a storage researcher, I need to replay a fixed day-ahead schedule and
symmetric FCR commitments against a normalized activation trace so that I can
measure whether one battery can deliver both services and understand the
resulting profit.

**Why this priority**: The physical and settlement semantics of the combined
service are the central capability on which all later bidding methods depend.

**Independent Test**: A reviewer can run a four-hour hand-calculable fixture
containing nonzero energy and FCR schedules, compare every requested and
delivered transition with the published calculation table, and reproduce its
SOC, throughput, revenue, penalty, and profit totals within the documented
tolerance.

**Acceptance Scenarios**:

1. **Given** a valid market artifact, one BESS, a fixed energy-baseline
   schedule, a non-negative symmetric FCR schedule, and a complete normalized
   activation trace, **When** the simulation runs, **Then** each high-resolution
   request combines the aligned energy baseline and FCR response using the
   documented sign convention.
2. **Given** a combined request that reaches a battery power or SOC limit,
   **When** the physical step is evaluated, **Then** delivered power remains
   within all limits while requested power, delivered power, saturation cause,
   delivered FCR response, tracking error, and non-delivery remain separately
   visible relative to the accepted energy baseline.
3. **Given** the reference timing profile, **When** a full French delivery day
   is replayed, **Then** hourly energy schedules, 15-minute state checkpoints,
   four-hour FCR commitments, and 10-second activation samples align without
   losing or double-counting energy.
4. **Given** a completed replay, **When** settlement is evaluated, **Then**
   day-ahead energy revenue, FCR capacity revenue, non-delivery penalties,
   delivered throughput, and total profit are separately reported and reconcile
   to the documented total.
5. **Given** an optional terminal SOC target, **When** replay completes,
   **Then** the result reports the target, realized terminal SOC, deviation,
   and tolerance-based compliance without modifying dispatch or profit.

---

### User Story 3 - Reproduce A Real French Historical Demonstration (Priority: P2)

As a reviewer, I need a recorded real French market period and activation
trace to replay end to end so that I can validate realistic timing and
settlement without possessing an ENTSO-E credential or depending on current
network availability.

**Why this priority**: A synthetic fixture proves equations, while a
provenanced historical fixture proves the market-data and multi-rate boundaries
work together on real inputs.

**Independent Test**: With all network access blocked, a reviewer can load the
committed historical artifacts, run the documented fixed stacked schedule, and
reproduce the stored trace fingerprint and all aggregate results exactly.

**Acceptance Scenarios**:

1. **Given** the selected bounded historical French period, **When** an
   authorized maintainer explicitly acquires and normalizes it, **Then** the
   resulting fixture records its real source, requested and delivered periods,
   revision, retrieval time, integrity information, and redistribution status.
2. **Given** that fixture and the separately provenanced 10-second FCR
   activation trace, **When** the demonstration runs offline twice, **Then**
   both runs produce identical requested/delivered traces, SOC trajectory,
   delivery metrics, settlement components, and total profit.
3. **Given** an ENTSO-E activated-balancing series for the same period, **When**
   its semantics or resolution has not been shown to match normalized
   10-second FCR activation, **Then** it is rejected as the activation trace
   rather than silently substituted.

---

### User Story 4 - Validate Baseline Compatibility (Priority: P3)

As a simulator maintainer, I need deterministic arbitrage-only,
regulation-only, and stacked baselines so that the new behavior can be compared
with established simulator semantics and later optimization methods.

**Why this priority**: Limiting cases reveal sign, timing, and settlement
errors before more sophisticated schedules depend on them.

**Independent Test**: A reviewer can run three fixed profiles from the same
battery and timing inputs and verify the zero-FCR and zero-energy identities,
plus the deterministic output of the stacked heuristic.

**Acceptance Scenarios**:

1. **Given** identical arbitrage inputs and the existing arbitrage settlement
   configuration, **When** every FCR commitment and activation response is
   zero, **Then** the new replay reproduces the existing arbitrage requested
   power, delivered power, SOC, throughput, and settlement results within the
   shared numeric tolerance.
2. **Given** a zero energy baseline, a nonzero valid FCR commitment, and a
   balanced activation trace from the efficiency-aware centered initial SOC,
   **When** the regulation-only profile runs, **Then** it reports zero
   day-ahead energy revenue while preserving FCR capacity revenue, physical
   delivery, tracking, SOC, throughput, penalties, and total profit without
   adding a recovery energy schedule.
3. **Given** the same artifact, battery, and deterministic heuristic
   configuration, **When** arbitrage-only, regulation-only, or stacked schedule
   generation is repeated, **Then** it produces the same fixed schedule and
   replay result without randomness or network access.
4. **Given** an existing deterministic arbitrage request and a valid symmetric
   FCR commitment, **When** the stacked heuristic constructs the fixed energy
   baseline, **Then** it clips that request to the charge/discharge power left
   after reserving FCR in both directions without consulting future activation.

### Edge Cases

- The requested market period is empty, reversed, open-ended, outside the
  historical service window, or expressed with an ambiguous timezone.
- The caller omits the token for fetch/refresh, supplies an invalid token, or
  includes a token value that could accidentally appear in diagnostics,
  artifact metadata, cache identities, notebooks, or test recordings.
- The source returns an acknowledgement, error document, empty document,
  partially covered interval, overlapping request-window boundary, duplicate
  interval, conflicting revision, unexpected unit, or unexpected resolution.
- The source times out, interrupts a connection, rate-limits a request, returns
  a transient server error across three attempts, or provides an invalid retry
  delay; no successfully retrieved subset may be published as a complete
  artifact.
- A French local delivery day contains 23 or 25 hours at a daylight-saving
  transition; UTC coverage remains continuous while local labels and offsets
  remain unambiguous.
- Negative day-ahead prices are valid market observations and are preserved;
  missing prices, non-finite values, or undocumented unit conversions are not.
- Reserve data is absent, directional rather than symmetric, assigned to a
  different area or product, inconsistent between volume and price, or unable
  to cover the requested period and commitment blocks.
- Refresh returns unchanged content, revised content for only one series, or a
  source revision older than the currently preserved revision for the same
  source, document, series, and covered period. The older response is rejected
  without changing the current lineage.
- An artifact has an unknown schema version, mismatched integrity digest,
  inconsistent source metadata, or series coverage that no longer satisfies
  its own manifest.
- A raw response cannot legally be retained or redistributed, a configured raw
  sidecar is missing or has the wrong digest, or raw source content is embedded
  in the canonical artifact instead of being managed separately.
- The activation trace contains values outside `[-1, 1]`, non-finite values,
  gaps, duplicates, a partial final sample, undocumented sign semantics, or a
  resolution or sample interpretation that cannot align exactly with the
  simulation grids.
- ENTSO-E activated-balancing quantities are offered as a 10-second normalized
  FCR command despite having incompatible aggregation or market semantics.
- Energy or FCR schedules contain gaps, overlaps, non-finite values, negative
  reserve capacity, or boundaries that do not align with the artifact and
  activation periods. A fetched artifact may preserve a partial boundary
  period, but replay rejects any horizon containing an incomplete energy or FCR
  product block.
- The energy, state-checkpoint, FCR, and activation resolutions are not exact
  integer relationships, including across a local daylight-saving transition.
- The baseline plus full positive or negative reserve request exceeds charge
  or discharge power headroom before replay begins.
- A request is power-feasible but sustained activation exhausts charge or
  discharge SOC headroom during replay.
- Charge or discharge efficiency is zero or outside its valid range, initial
  SOC is outside its bounds, or the battery has invalid energy or power limits.
- A penalty is requested without a declared non-delivery measure, rate, unit,
  and application rule; no hidden market penalty may be inferred.
- An offline simulation is attempted with a missing required artifact or tries
  to activate a network client implicitly.

## Requirements *(mandatory)*

### Functional Requirements

#### Market-Data Production And Artifacts

- **FR-001**: The feature MUST provide a library-owned market-data producer
  whose source-specific retrieval and response formats do not cross into the
  simulator.
- **FR-002**: Fetch and refresh MUST accept a caller-provided valid ENTSO-E API
  token only at the retrieval boundary and MUST fail explicitly on missing or
  rejected authentication without publishing a complete artifact.
- **FR-003**: The first ENTSO-E profile MUST target France using area identifier
  `10YFR-RTE------C` and MUST reject data whose declared market area is
  incompatible with that profile.
- **FR-004**: Retrieval MUST accept a caller-selected bounded historical start
  and end instant, use a start-inclusive/end-exclusive interval convention,
  and preserve the exact requested period even when the source must be queried
  in smaller windows. The retrieval period need not align with complete energy
  or FCR product blocks.
- **FR-005**: A complete first-release market artifact MUST contain French
  day-ahead energy prices from the applicable price document (`A44`),
  applicable symmetric-FCR contracted capacity volumes, and applicable FCR
  capacity prices from the same combined R3 contracted-reserve document
  (`A81`) covering the requested period, with the exact source fields, product,
  and process filters preserved in provenance. A separate `A89` request MUST
  NOT be issued by this profile.
- **FR-006**: The library-owned market-data boundary MUST expose three explicit
  workflows. The ENTSO-E adapter MUST own `fetch` to create an artifact from a
  source request and `refresh` to compare a new source response with an existing
  artifact. The source-independent artifact module MUST own `offline` loading
  and validation without importing or invoking the ENTSO-E transport.
- **FR-006a**: Fetch and refresh MUST retry only transient timeouts, connection
  interruptions, rate-limit responses, and server errors for no more than
  three total attempts per failed request window, including the initial
  attempt. They MUST honor a valid source-provided retry delay, fail immediately
  on authentication and other permanent client errors, report attempt count
  and final failure without exposing the token, and publish no artifact unless
  every required window and series succeeds and validates.
- **FR-007**: Simulation, artifact loading, schedule generation, and offline
  demonstration MUST NOT initiate implicit network requests; only an explicit
  fetch or refresh operation may contact the external service.
- **FR-008**: The resulting market-data artifact MUST be immutable, versioned,
  validated, and source-independent so that simulator and future optimization
  consumers require no ENTSO-E request or response concepts.
- **FR-009**: The artifact MUST record, for itself and each series as
  applicable, artifact/schema version, source name and endpoint identity,
  source revision, document and business/process identity, area, requested
  period, actual covered period, interval boundaries, source resolution,
  canonical resolution, source units, canonical units, currency, market
  timezone, retrieval time, normalization version, and integrity information.
- **FR-010**: The canonical artifact MUST always record an integrity digest of
  every raw source response plus its source metadata and MUST record the
  retention and redistribution status governing the normalized fixture. It
  MUST NOT embed raw responses. When source terms explicitly permit retention,
  a raw response MAY be preserved as a separately managed sidecar referenced
  by locator and verified against the recorded digest; otherwise no raw
  sidecar is retained.
- **FR-010a**: XML and ZIP responses MUST be accepted only within explicit
  compressed and uncompressed byte/member limits. ZIP processing MUST reject
  encryption, traversal, absolute paths, directories, duplicate names, nested
  archives, non-XML members, malformed archives, and size overflow, and MUST
  preserve the selected archive-member name in document provenance.
- **FR-011**: Canonical instants MUST be represented in UTC while preserving
  Europe/Paris local delivery labels, UTC offsets, and daylight-saving fold or
  gap meaning needed to reconstruct market delivery periods unambiguously.
- **FR-012**: Validation MUST explicitly detect acknowledgements and error
  documents, empty responses, missing intervals, conflicting duplicates,
  unexpected resolutions, incompatible units, misaligned series, and invalid
  daylight-saving coverage; it MUST NOT silently fill, interpolate, or replace
  required market observations.
- **FR-013**: Missing or incompatible required day-ahead, FCR-volume, or
  FCR-price series MUST fail completion with source, series, requested period,
  observed coverage/resolution, and expected contract in the diagnostic.
- **FR-014**: A source other than ENTSO-E MUST NOT be substituted silently.
  Any future or caller-provided alternative must enter through the same
  canonical artifact contract and retain its own explicit series-level
  provenance; it does not satisfy the required ENTSO-E demonstration by
  implication.
- **FR-015**: Refresh MUST compare normalized content and source revisions. An
  unchanged response MUST produce an explicit no-change outcome; changed
  content MUST create a new immutable version linked to its predecessor rather
  than overwriting it.
- **FR-015a**: When source, document identity, series, and covered period match
  an existing artifact lineage, refresh MUST reject a lower source revision as
  a regression, preserve the current artifact unchanged, publish no new
  version, and identify the current and returned revisions in the diagnostic.
  Revisions from different documents, series, or covered periods MUST NOT be
  compared as one revision sequence.
- **FR-016**: The API token MUST NOT appear in artifacts, filenames, cache
  identities, logs, exception text, notebooks, fixture recordings, or
  provenance. Validation MUST scan produced files and captured output using a
  sentinel token value.
- **FR-017**: Negative market prices MUST remain valid values. All values MUST
  be finite, and every unit or resolution conversion MUST be declared and
  reproducible rather than inferred silently.
- **FR-018**: The canonical first-release units MUST be explicit and internally
  consistent: energy prices in `EUR/MWh`, reserve volume in `MW`, and FCR
  capacity remuneration in `EUR/MW/h`, with source conversions preserved in
  provenance.
- **FR-018a**: Combined A81 `quantity` and `procurement_Price.amount` points
  MUST be expanded from their declared sparse `A03` ISP curve. The capacity
  price conversion MUST use `source_value / ISP_duration_hours`; canonical
  PT4H blocks may be formed only from complete consecutive ISPs with identical
  product, volume, and price semantics.
- **FR-018b**: `docs/architecture/entsoe-transparency-platform.md` MUST record
  the ENTSO-E API generation and endpoint, exact case-sensitive A44/A81
  requests, authentication/dotenv boundary, XML/ZIP handling, normalization
  formula, retry/failure behavior, official references, and the distinction
  between restricted private-repository storage and public redistribution.

#### Activation-Trace Ingestion

- **FR-019**: The feature MUST accept a high-resolution FCR activation trace
  as a separate source-independent input artifact with its own schema version,
  source and revision, period, interval convention, resolution, units,
  normalization rule, sign meaning, retrieval or creation time, and integrity
  information.
- **FR-020**: The canonical activation value MUST be finite and lie in
  `[-1, 1]`, where `+1` means a request for full upward/discharge response and
  `-1` means a request for full downward/charge response. Any source with a
  different convention MUST document and apply an explicit normalization.
- **FR-020a**: Each canonical activation value MUST represent the average
  normalized activation over its start-inclusive/end-exclusive sample
  interval. Replay MUST use that interval average directly for power and
  energy integration and MUST NOT infer interpolation between samples. A
  source expressed as instantaneous points or setpoints MUST undergo an
  explicit, provenanced conversion before it satisfies this contract.
- **FR-021**: The reference historical demonstration MUST use a complete
  10-second activation trace. Other configured high-resolution traces MAY be
  accepted only when their resolution and boundaries align exactly with all
  coarser grids and their product meaning satisfies the same normalized FCR
  contract.
- **FR-022**: Activated-balancing quantities (`A83`) or prices (`A84`) MUST NOT
  be treated as the required activation trace unless both their temporal
  resolution and semantic equivalence to the normalized FCR command have been
  validated and recorded. Otherwise they remain supporting market data only.
- **FR-023**: Activation gaps, duplicates, out-of-range values, ambiguous sign
  meaning, incomplete period coverage, or incompatible resolution MUST fail
  before physical replay and identify the offending interval and contract.

#### Stacked-Service Simulation And Settlement

- **FR-024**: The first release MUST simulate exactly one BESS and consume a
  valid canonical market-data artifact plus a separately validated activation
  trace; source-networking objects MUST NOT be simulator inputs.
- **FR-025**: The simulator MUST accept fixed day-ahead energy baseline
  schedules and fixed non-negative symmetric FCR capacity commitments. It MUST
  NOT choose optimal bids.
- **FR-026**: The reference profile MUST align hourly energy schedules,
  15-minute state checkpoints, four-hour FCR blocks, and 10-second activation
  samples. Resolutions MAY be configurable only when every boundary maps
  exactly and no sample is dropped, duplicated, or proportionally guessed.
- **FR-026a**: A replay horizon MUST start and end on boundaries that contain
  complete energy and FCR product blocks. Replay MUST reject an incomplete
  leading or trailing product block with the offending boundary identified and
  MUST NOT automatically trim the horizon or prorate settlement. The enclosing
  market artifact MAY cover a broader or partially bounded retrieval period.
- **FR-027**: The simulator MUST preserve the library convention that positive
  battery power means charging. For canonical activation `xi`, charge-positive
  baseline `p_base`, and non-negative FCR capacity `r`, the charge-positive
  combined request MUST be `p_requested = p_base - xi * r`.
- **FR-028**: Before replay, schedule validation MUST verify that every FCR
  commitment aligns with a compatible price and contracted-volume interval,
  does not exceed that interval's applicable market volume, and leaves charge
  and discharge power headroom at both reserve extremes. Any violation MUST
  mark the schedule non-deliverable and prevent it from passing commitment
  validation, even if an explicitly requested diagnostic replay later exposes
  its physical non-delivery.
- **FR-029**: At every activation substep, delivered power and SOC MUST respect
  configured charge power, discharge power, minimum SOC, maximum SOC, charge
  efficiency, and discharge efficiency constraints, even when the requested
  schedule is infeasible.
- **FR-030**: Every substep MUST preserve requested combined power separately
  from physically delivered power and MUST identify whether any difference was
  caused by charge-power, discharge-power, minimum-SOC, or maximum-SOC
  saturation.
- **FR-030a**: During a nonzero FCR commitment, the accepted day-ahead energy
  baseline MUST remain the regulation-performance reference. Charge-positive
  requested FCR response MUST equal `-xi * r`; delivered FCR response MUST
  equal delivered combined power minus the accepted baseline; and FCR tracking
  error MUST equal requested FCR response minus delivered FCR response. The
  resulting deviation MUST be attributed to FCR non-delivery without changing
  physical replay or schedule-based day-ahead settlement.
- **FR-030b**: When FCR commitment is zero, delivered FCR response and FCR
  non-delivery MUST both be zero. Any difference between requested baseline and
  delivered combined power MUST instead be reported as a baseline-delivery
  diagnostic and MUST NOT create an FCR penalty.
- **FR-031**: Replay results MUST include per-substep and aggregate absolute
  and signed tracking error, undelivered energy, saturation count, saturation
  duration, and non-delivery events with cause and interval.
- **FR-032**: SOC MUST be advanced from delivered charge and discharge energy
  at the activation resolution using the configured direction-specific
  efficiencies. Aggregation to 15-minute, hourly, and FCR-block summaries MUST
  conserve the same delivered energy within the numeric tolerance.
- **FR-033**: Replay output MUST include aligned energy baseline, FCR
  commitment, activation, requested and delivered FCR response, requested
  combined power, delivered combined power, baseline-delivery diagnostics,
  SOC, charge energy, discharge energy, tracking, saturation, and settlement
  traces sufficient to audit every aggregate.
- **FR-034**: Day-ahead energy revenue for the French reference profile MUST be
  calculated from the accepted fixed day-ahead baseline, its delivery duration,
  and the aligned day-ahead price, with charging represented as a cost and
  discharging as revenue.
- **FR-035**: FCR capacity revenue MUST be calculated from committed eligible
  capacity, aligned capacity remuneration, and covered commitment duration
  after documented unit conversion. Physical non-delivery MUST NOT silently
  reduce capacity revenue except through an explicit penalty rule.
- **FR-036**: Penalties MUST use an explicit deterministic rule declaring the
  rate, unit, and application period and MUST apply to the canonical FCR
  non-delivery derived relative to the accepted baseline. When no penalty rule
  is configured, the reported penalty MUST be zero rather than an inferred
  market value.
- **FR-037**: Delivered throughput MUST equal total absolute delivered charge
  and discharge energy at the battery terminal, and MUST remain separate from
  revenue and penalties.
- **FR-038**: Total first-release profit MUST reconcile exactly as day-ahead
  energy revenue plus FCR capacity revenue minus penalties. Activation-energy
  payment, imbalance settlement, and degradation cost MUST be reported as not
  modeled rather than hidden in another component.
- **FR-039**: Repeated replay from identical artifacts, schedules, battery
  configuration, penalty rule, and tolerance MUST reproduce identical traces,
  event ordering, component totals, and total profit without a random seed or
  network access.
- **FR-039a**: A replay MAY accept an optional terminal SOC target. When
  supplied, the result MUST report the target, realized terminal SOC, signed
  and absolute deviation, and compliance using the configured numeric
  tolerance. The target MUST NOT clamp or otherwise alter requested power,
  delivered power, settlement components, or total profit.

#### Baselines, Demonstrations, And Boundaries

- **FR-040**: The feature MUST provide deterministic fixed-schedule baselines
  for arbitrage-only, regulation-only with SOC headroom, and stacked operation
  that permits arbitrage only while declared FCR power headroom remains
  available.
- **FR-040a**: The regulation-only baseline MUST use a zero day-ahead energy
  schedule, a caller-selected fixed FCR commitment, and the efficiency-aware
  centered initial stored energy
  `y_center = (y_max + eta_charge * eta_discharge * y_min) /
  (1 + eta_charge * eta_discharge)`. It MUST NOT add recovery or recentering
  dispatch and MUST NOT use future activation values to construct its schedule.
- **FR-040b**: The stacked deterministic heuristic MUST begin with the existing
  deterministic arbitrage request and reserve symmetric FCR power before
  assigning the energy baseline. For charge-positive power bounds
  `[-P_discharge, P_charge]` and commitment `r`, it MUST clip the arbitrage
  request to `[-P_discharge + r, P_charge - r]`. It MUST reject an empty
  admissible interval, MUST NOT use future activation values, and MUST NOT claim
  robust SOC feasibility beyond physical replay of the supplied trace.
- **FR-041**: With zero FCR commitment, the stacked replay MUST reproduce the
  existing arbitrage physical and settlement behavior when given identical
  battery, schedule, timing, price, and existing settlement configuration. With
  a zero energy baseline, it MUST support nonzero FCR replay and report zero
  day-ahead energy revenue.
- **FR-042**: The hand-calculable stacked fixture MUST use one 4 kWh battery
  with 0--4 kWh bounds, 2 kWh initial energy, `+/-2 kW` power limits, and unit
  efficiencies over four hours. It MUST use charge-positive hourly baselines
  `[+1, 0, 0, -1] kW`, one `1 kW` FCR commitment, half-hour activation values
  `[+1, -1, 0, 0, 0, 0, +1, -1]`, day-ahead prices
  `[50, 60, 70, 100] EUR/MWh`, an FCR capacity price of `20 EUR/MW/h`, and no
  penalty. The published expected results MUST be requested/delivered power
  `[0, +2, 0, 0, 0, 0, -2, 0] kW`, stored energy
  `[2, 2, 3, 3, 3, 3, 3, 2, 2] kWh` including initial state, `2 kWh`
  throughput, `EUR 0.05` energy revenue, `EUR 0.08` FCR capacity revenue, zero
  tracking error, and `EUR 0.13` total profit.
- **FR-043**: The feature MUST include an end-to-end demonstration over one
  selected bounded historical French period containing required market series
  obtained through the ENTSO-E producer, a separately provenanced compatible
  10-second FCR activation trace, one fixed deterministic stacked schedule,
  and recorded expected outputs.
- **FR-044**: The real-data demonstration artifacts MUST be preserved for
  reproducible offline replay and routine validation only in the owner-
  confirmed private repository for authorized collaborators. Their metadata
  MUST prohibit public publication, packages, releases, public forks/mirrors,
  and external artifact upload; the build MUST exclude them, and they MUST be
  removed before repository visibility becomes public. Routine tests MUST NOT
  require a live credential, network access, notebook execution, or fixture
  regeneration.
- **FR-045**: A credentialed fetch/refresh check MAY be run explicitly to
  validate current source compatibility, but its absence or network
  unavailability MUST be documented separately and MUST NOT weaken offline
  artifact and simulation validation.
- **FR-046**: Public module locations for market-data and simulator consumers
  MUST be stable, while first-release ENTSO-E, FCR-profile, and stacked-service
  concrete types MAY remain experimental with that maturity stated clearly.
- **FR-047**: Market-data production MUST own retrieval and artifact validity;
  the simulator MUST own physical delivery and realized settlement; schedule
  inputs MUST remain fixed or deterministic; later optimization MUST consume
  these contracts without being embedded into either producer or simulator.
- **FR-048**: Default imports and offline replay MUST remain usable without
  service credentials, notebooks, commercial solver licenses, GPU/SLURM
  resources, experiment trackers, or legacy runtimes. Any retrieval-only
  dependency MUST remain isolated from simulator imports and offline use.
- **FR-049**: Reproducibility inputs MUST include artifact and activation
  fingerprints, all grid definitions, battery configuration, fixed schedules
  or heuristic parameters, settlement and penalty rules, numeric tolerance,
  and simulation-semantics version. The default absolute numeric tolerance
  MUST be `1e-6` unless a validation case documents a stricter value.
- **FR-050**: The first release MUST be limited to France, one BESS, day-ahead
  energy arbitrage, symmetric FCR capacity, fixed schedules, deterministic
  heuristic baselines, historical-period fetch, optional refresh, and
  deterministic replay.
- **FR-051**: The first release MUST explicitly exclude aFRR, mFRR, generic
  pan-European profiles, continuous streaming, mandatory real-time retrieval,
  implicit downloading, robust bid optimization, rolling or intraday
  optimization, learned or reinforcement-learning controllers, network
  constraints, activation-energy and imbalance settlement, and detailed
  electrochemical degradation.

### Key Entities *(include if feature involves data or API design)*

- **Market Data Request**: Token-free, persistable description of one explicit
  source operation for France, with fetch/refresh mode, caller-selected
  half-open historical period, requested document/product identities, area,
  and the fixed bounded retry policy for source request windows. The caller
  credential is a separate keyword-only argument to fetch or refresh and is
  never part of this entity.
- **Market Data Artifact**: Immutable source-independent collection of aligned
  day-ahead and FCR market series plus schema version, temporal contract,
  canonical units, provenance, revision, integrity, and redistribution
  metadata. It never contains a credential or embedded raw response, and may
  reference a permitted separately managed raw sidecar by locator and digest.
  Its lineage is scoped by source, document identity, series, and covered
  period so refresh cannot silently roll back a comparable source revision.
- **Market Series**: One interval-indexed price or volume series with source and
  canonical resolution, unit, currency, coverage, area, product meaning, and
  series-level provenance.
- **Regulation Activation Trace**: Separately provenanced dimensionless FCR
  command in `[-1, 1]`, including explicit positive direction, interval
  boundaries, interval-average high-resolution samples, normalization,
  revision, and integrity.
- **Energy Baseline Schedule**: Fixed charge-positive BESS power assigned to
  every day-ahead delivery interval; it is an input, not an optimized decision.
- **FCR Capacity Schedule**: Fixed non-negative symmetric reserve capacity
  assigned to every eligible FCR block, coupled to the baseline by charge and
  discharge headroom.
- **Multi-Rate Time Contract**: Exact mapping between UTC activation samples,
  local delivery periods, 15-minute state checkpoints, hourly energy periods,
  and complete four-hour reserve blocks, including daylight-saving meaning and
  replay-boundary eligibility.
- **BESS Configuration And State**: One battery's energy and power bounds,
  initial stored energy, charge/discharge efficiencies, sign convention, and
  high-resolution SOC trajectory, plus an optional report-only terminal SOC
  target.
- **Stacked-Service Replay Result**: Auditable requested and delivered traces,
  requested and delivered FCR response relative to the accepted baseline,
  baseline-delivery diagnostics, SOC, energy movement, saturation and
  non-delivery events, tracking metrics, throughput, optional terminal-target
  compliance, settlement components, fingerprints, and total profit.
- **Settlement Rule**: Explicit day-ahead, FCR-capacity, and penalty accounting
  contract with units, period application, and reconciliation identity.
- **Deterministic Baseline**: Fixed rule and parameters producing an
  arbitrage-only, regulation-only, or headroom-aware stacked schedule without
  optimization or randomness. The regulation-only baseline uses zero energy
  schedule, efficiency-aware centered initial SOC, and fixed FCR commitment
  without recovery dispatch. The stacked baseline caps the existing
  deterministic arbitrage request to the bidirectional power remaining after
  reserving symmetric FCR.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Only lightweight artifact validation, temporal
  alignment, unit handling, battery replay, and settlement capabilities needed
  for ordinary offline library use.
- **Optional dependencies**: Retrieval/response parsing support may be isolated
  to explicit fetch and refresh workflows; notebooks, solvers, learning stacks,
  experiment tracking, and legacy runtimes are not required.
- **External services**: ENTSO-E Transparency Platform access and a valid
  caller-provided token are required only for explicit fetch or refresh.
- **Hardware assumptions**: CPU-only local execution is sufficient; no GPU,
  SLURM cluster, or commercial solver license is required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For one explicit credentialed French period, fetch produces an
  artifact containing 100% coverage for all required day-ahead price,
  symmetric-FCR volume, and FCR-price intervals, while a scan of the artifact,
  filenames, and captured output finds zero occurrences of a sentinel token.
- **SC-002**: The hand-calculable four-hour fixture reproduces all nine stored
  energy states, eight requested and delivered power values, `2 kWh`
  throughput, `EUR 0.05` energy revenue, `EUR 0.08` FCR revenue, zero tracking
  error, and `EUR 0.13` total profit within `1e-6` absolute tolerance.
- **SC-003**: A 24-hour reference replay aligns 24 hourly energy periods, 96
  state-checkpoint periods, 6 four-hour FCR blocks, and 8,640 10-second
  activation samples with zero missing or multiply assigned samples.
- **SC-004**: For every validated replay, delivered power and SOC violate their
  configured lower or upper bounds by no more than `1e-6`, including fixtures
  deliberately requesting infeasible power or sustained activation.
- **SC-005**: Energy calculated directly from every delivered 10-second sample
  and energy calculated from each supported coarser aggregation differ by no
  more than `1e-6 kWh` per aggregation period and over the full horizon, using
  each activation value as the interval average without interpolation.
- **SC-006**: Two offline executions of the recorded real-data demonstration
  produce identical trace fingerprints, event ordering, revenue components,
  penalties, throughput, and total profit, with zero attempted network calls.
- **SC-007**: With zero FCR, requested power, delivered power, SOC, throughput,
  and settlement match the existing arbitrage path within `1e-6`; with a zero
  energy baseline, day-ahead energy revenue is exactly zero while nonzero FCR
  delivery and capacity settlement remain observable.
- **SC-008**: Validation fixtures cover at least one case each for invalid
  authentication, empty response, missing required series, gap, conflicting
  duplicate, unexpected resolution, daylight-saving transition, incompatible
  FCR semantics, invalid activation range, activation misalignment, artifact
  integrity failure, partial replay product block, power saturation, and SOC
  saturation, and every case returns a specific diagnostic rather than an
  imputed result.
- **SC-009**: Under the Reference Benchmark Protocol defined in `plan.md`, every
  one of five measured executions of the complete recorded 24-hour,
  8,640-substep offline demonstration MUST complete in under 10 seconds and
  expose every settlement component independently. The recorded acceptance
  result MUST include the benchmark environment and all timing measurements.
- **SC-010**: Routine validation completes with no credential, network,
  notebook, solver license, GPU/SLURM resource, experiment-tracking account, or
  legacy runtime, while an explicitly invoked credentialed check remains
  available for source compatibility.
- **SC-011**: Feature documentation MUST contain one ownership matrix assigning
  ENTSO-E source retrieval and normalization to `market.entsoe`, canonical
  market-artifact validity to `market.artifact`, activation-artifact validity to
  `market.activation`, deterministic fixed-schedule construction to
  `control.stacked_service`, physical delivery to `simulator.stacked_service`,
  realized settlement to `simulator.fcr_settlement`, and robust bid selection
  to a later feature. Every responsibility MUST have exactly one owner, and no
  source-networking type may appear in simulator inputs.
- **SC-012**: Two otherwise identical replays with and without a terminal SOC
  target produce identical requested and delivered traces and identical profit;
  the targeted replay additionally reports terminal deviation and compliance
  within the configured `1e-6` tolerance.
- **SC-013**: Every fetched artifact records a verifiable digest for every raw
  response and embeds zero raw response payloads. A raw sidecar is created only
  in a fixture whose recorded terms permit retention, and its digest matches
  the artifact exactly.
- **SC-014**: In every replay with nonzero FCR, requested FCR response equals
  requested combined power minus the accepted baseline and delivered FCR
  response equals delivered combined power minus that baseline within `1e-6`;
  their difference reconciles exactly to reported FCR tracking error and
  non-delivery. With zero FCR, reported FCR response, non-delivery, and penalty
  are all zero.
- **SC-015**: The regulation-only baseline begins at the efficiency-aware
  centered SOC within `1e-6`, contains zero energy-schedule power in every
  interval, produces exactly zero day-ahead energy revenue, and reproduces the
  same fixed FCR schedule and replay result on repeated execution without
  activation lookahead or recovery dispatch.
- **SC-016**: For every stacked-heuristic interval, the fixed energy baseline
  lies within `[-P_discharge + r, P_charge - r]` to within `1e-6`; repeated
  generation is identical, and changing future activation samples without
  changing market inputs or commitments does not change the generated
  schedule.
- **SC-017**: In deterministic source-failure tests, transient failures produce
  no more than three total attempts and publish zero partial artifacts;
  authentication or other permanent client failures produce exactly one
  attempt. A valid retry delay is honored, and all diagnostics contain zero
  occurrences of a sentinel token.
- **SC-018**: Refreshing an artifact lineage at source revision `N` with a
  response at revision `N-1` publishes zero new artifacts, leaves the current
  artifact fingerprint unchanged, and reports both revision values; a revision
  from a different document or covered period is not rejected by that
  comparison alone.

## Assumptions

- Researchers use the library from deterministic scripts, tests, or notebooks,
  but notebooks are consumers and are not required execution environments.
- The first real-data demonstration will select during planning a bounded
  historical French period for which the required ENTSO-E series are complete,
  compatible, and legally preservable as a normalized offline fixture. A
  period that does not satisfy those conditions is rejected rather than
  patched with synthetic values.
- Real A44 responses remain digest-only. Normalized values and reconstructable
  derived outputs may be committed only to the owner-confirmed private
  repository for authorized collaborators, with public redistribution and
  package/release distribution explicitly prohibited. This restricted storage
  decision is not a public-data license; remove the fixtures before making the
  repository or its relevant history public.
- The French reference market timezone is `Europe/Paris`; UTC is the canonical
  computation timeline, and local delivery meaning remains metadata.
- The reference day-ahead schedule uses hourly blocks, the state-checkpoint
  view uses 15-minute blocks, symmetric FCR uses four-hour blocks, and physical
  replay uses 10-second activation. Historical periods with incompatible
  market resolution require a documented, validated conversion or are not
  eligible for the reference fixture.
- ENTSO-E is the required market-data source for the demonstration. The
  source-independent artifact permits later declared adapters but does not
  authorize silent RTE or other fallback data when ENTSO-E coverage is absent.
- The separately sourced high-resolution FCR trace has redistribution terms
  compatible with routine offline validation and carries enough provenance to
  reproduce or audit its normalization.
- Positive battery power means charging throughout Open Energy Lab. The
  canonical activation trace uses positive values for upward/discharge
  response, so its contribution is subtracted from the charge-positive energy
  baseline.
- Day-ahead energy revenue is settled from the accepted fixed baseline rather
  than realized activation power. Symmetric FCR is capacity-only in this first
  release; activation-energy payments, imbalance settlement, and detailed
  market-specific penalty formulas require later explicit profiles.
- A caller may configure a deterministic non-delivery penalty for research
  comparisons. The default penalty is zero because the feature does not infer
  an undocumented French market rule.
- Existing arbitrage compatibility uses the existing settlement configuration;
  the French wholesale profile's schedule settlement does not silently change
  older discounted-export fixtures.
- Fixed schedules and deterministic heuristics are inputs and validation
  baselines. Feasibility under every possible activation signal and selection
  of optimal bids belong to the following robust-bidding feature.
- Delivered throughput is reported for later degradation studies, but no
  degradation cost or electrochemical aging model is included in total profit.
- Existing library behavior, the roadmap equations, and the cited
  robust-storage-bidding work are behavioral references only; external code is
  not a runtime dependency and no new code is added under `legacy/*`.
