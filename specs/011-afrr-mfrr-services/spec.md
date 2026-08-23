# Feature Specification: BESS aFRR and mFRR Services

**Feature Branch**: `011-afrr-mfrr-services`  
**Created**: 2026-08-22  
**Status**: Draft  
**Input**: User description: "Extend the validated BESS arbitrage-and-FCR vertical slice with distinct French aFRR and mFRR market profiles, historical-data acquisition, deterministic physical replay, product-specific settlement, offline demonstrations, and documented source and redistribution boundaries."

## Purpose *(mandatory)*

Extend Open Energy Lab's validated battery energy storage system (BESS)
service model from day-ahead arbitrage and Frequency Containment Reserve (FCR)
to two distinct restoration-reserve products: automatic Frequency Restoration
Reserve (aFRR) and manual Frequency Restoration Reserve (mFRR). Researchers
must be able to acquire bounded historical French market records, preserve
their meaning and provenance, supply explicit asset-level activation inputs,
replay one battery's physical response, and audit delivery, revenue,
non-performance, throughput, and a simple degradation-cost proxy.

The feature must preserve the boundary established by Feature 010. Market-data
production owns source access, normalization, provenance, and artifact
validity. The simulator owns battery physics, requested versus delivered
service, and realized accounting. Public market-area records provide context
for a study; they are not operational commands sent to the simulated battery.
Where a researcher creates an asset-level scenario from area-level records,
the mapping must be explicit, reproducible, and unmistakably labelled as a
derived simulation scenario rather than observed dispatch.

## Clarifications

### Session 2026-08-22

- Q: What should each canonical aFRR trajectory sample represent? → A: Signed
  requested BESS balancing power in kW; negative is upward/discharge and
  positive is downward/charge.
- Q: What happens when physical inputs are valid but a required settlement
  price is missing? → A: Complete physical replay, but mark settlement and
  the total net result unavailable.
- Q: What asset-level activation input should the real-data aFRR demonstration
  use? → A: A transparent derived scenario mapped from the recorded RTE
  aggregates and prominently labelled as simulated.
- Q: How should the real scheduled-activation mFRR record be used for BESS
  replay? → A: Map it explicitly into a simulated BESS event and label the
  event as derived.
- Q: How should the first release handle overlapping mFRR delivery intervals?
  → A: Reject every overlap before replay.
- Q: Which reserve products may one Feature 011 replay include? → A:
  Day-ahead plus either aFRR or mFRR; exactly one restoration product per
  replay.

### Session 2026-08-23

- Q: How should RTE and ENTSO-E series be composed for a study? → A: Keep one
  immutable artifact per source acquisition and reference them from an explicit
  study bundle.
- Q: Which RTE quantities should drive the reference BESS activation requests?
  → A: aFRR requested need and mFRR scheduled-activation requested volume.
- Q: How should area-level requested volume be converted to BESS requested
  power? → A: Apply a fixed documented asset-allocation fraction; reject the
  scenario if it exceeds committed capacity.
- Q: How should an mFRR event express its requested amount? → A: Non-negative
  requested power in kW plus an explicit upward/downward direction.
- Q: What temporal meaning should each canonical aFRR power sample have? → A:
  Interval-average power over its half-open interval; no interpolation or
  upsampling.
- Q: How should a derived aFRR scenario handle one interval with both upward
  and downward requested need? → A: Reject that interval as ambiguous for
  asset-level derivation.
- Q: What requested power shape should each canonical mFRR event define? → A:
  Request time, optional delay, linear ramp-up, full-power hold, and linear
  ramp-down as separate durations.
- Q: How should derived real-data demonstrations price simulated BESS activated
  energy? → A: Use the matching RTE weighted-average or settlement price as a
  labelled area-price proxy.
- Q: Which acquisition lifecycle should the RTE and ENTSO-E profiles expose?
  → A: Explicit fetch, immutable refresh, and offline load; retry transient
  failures up to three total attempts.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability
- **Target surface**: Public market-data, control, and simulator library
  surfaces; canonical data artifacts; deterministic fixtures; documentation;
  and an offline-first research notebook
- **Legacy reference paths**: None. Existing `legacy/*` projects are neither
  runtime dependencies nor migration targets for this feature.
- **New-code location**:
  - `src/open_energy_lab/market` for source-specific acquisition and
    source-independent restoration-market artifacts
  - `src/open_energy_lab/control` for fixed commitments and deterministic
    product-specific baseline heuristics
  - `src/open_energy_lab/simulator` for aFRR and mFRR physical replay,
    performance reporting, and settlement
  - corresponding validation under `tests/unit`, `tests/integration`, and
    restricted, versioned fixtures under `tests/fixtures`
  - explanatory material under `docs/` and `examples/`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Acquire Trustworthy French Restoration Data (Priority: P1)

As a researcher, I need to retrieve a bounded historical period of French aFRR
or mFRR market records and preserve each returned series with its exact source
meaning so that I can repeat a study without depending on a live service or
confusing area-level data with battery instructions.

**Why this priority**: Source meaning, temporal coverage, secret handling, and
reproducible artifacts are prerequisites for every physical or financial
result in the feature.

**Independent Test**: A reviewer can explicitly acquire one verified aFRR hour
and one verified mFRR period, inspect the normalized records and provenance,
verify that credential sentinels are absent, then reload the artifacts with all
network access disabled.

**Acceptance Scenarios**:

1. **Given** valid caller-owned RTE credentials and the verified one-hour aFRR
   period, **When** the researcher explicitly requests the period, **Then** four
   consecutive 15-minute records are preserved with separate upward and
   downward need, activation-volume, and activation-price meanings.
2. **Given** valid caller-owned RTE credentials and a verified mFRR historical
   period, **When** the researcher explicitly requests the period, **Then**
   scheduled-activation and direct-activation fields remain distinct by
   direction, and at least one known scheduled-activation record preserves its
   requested and satisfied volumes.
3. **Given** a request for a complementary ENTSO-E series whose French product,
   document, units, and resolution have been validated, **When** acquisition
   succeeds, **Then** that series retains ENTSO-E-specific provenance and is
   not merged with, substituted for, or represented as an RTE series.
4. **Given** an existing valid artifact and no credentials or network access,
   **When** the researcher loads it for an offline study, **Then** validation
   succeeds without initiating authentication or retrieval.
5. **Given** missing coverage, an incompatible unit or resolution, an
   ambiguous field, conflicting duplicates, or a source failure, **When**
   acquisition validates the requested series, **Then** it reports the source,
   field, requested period, observed condition, and expected contract and does
   not publish a complete artifact.
6. **Given** a study that needs RTE and ENTSO-E observations, **When** its
   inputs are assembled, **Then** an explicit study bundle references the
   immutable source-artifact fingerprints and selected series without copying
   or merging their observations.
7. **Given** an existing source-acquisition artifact, **When** explicit refresh
   returns unchanged normalized content, **Then** it reports no change and
   publishes no new artifact; changed content creates a linked immutable
   successor without overwriting the prior version.
8. **Given** a transient live-source failure, **When** the operation cannot
   succeed within three total attempts, **Then** it fails atomically with the
   attempt count and sanitized final cause; permanent client and authentication
   failures stop immediately.

---

### User Story 2 - Replay Automatic Restoration Delivery (Priority: P1)

As a storage researcher, I need to replay directional aFRR commitments against
an explicit automatic activation trajectory so that I can measure whether the
battery tracks upward and downward requests while respecting its physical
limits.

**Why this priority**: Automatic trajectory tracking is the defining aFRR
behavior and cannot be represented faithfully by the existing FCR signal or by
15-minute area totals alone.

**Independent Test**: A reviewer can run a small hand-calculable trajectory
with upward, downward, zero, ramp-limited, power-limited, and SOC-limited
segments and reproduce every request, delivery, tracking, energy,
non-performance value, and physical-result fingerprint within the declared
numeric tolerance. Product economics are tested independently under User Story
4 after the physical replay contracts exist.

**Acceptance Scenarios**:

1. **Given** a fixed energy baseline, separate upward and downward aFRR
   commitments, and a complete asset-level activation trajectory, **When** the
   replay runs, **Then** the requested and delivered automatic response,
   battery power, SOC, headroom, ramp, tracking error, and non-performance are
   separately visible at every simulation interval.
2. **Given** an activation request that exceeds power, SOC, reserved-capacity,
   headroom, ramp, or activation-time capability, **When** the battery responds,
   **Then** physical limits remain satisfied and the amount, direction, cause,
   and duration of non-delivery are reported.
3. **Given** zero aFRR activation throughout the replay, **When** replay runs,
   **Then** the committed baseline is unchanged, delivered balancing energy is
   zero, and physical non-performance is zero.
4. **Given** an area-level market series plus a researcher-declared mapping,
   **When** an aFRR trajectory is derived for simulation, **Then** the mapping,
   inputs, assumptions, and fingerprint are recorded and every output identifies
   the trajectory as derived rather than observed asset dispatch.

---

### User Story 3 - Replay Manual Restoration Events (Priority: P1)

As a storage researcher, I need to replay scheduled and direct mFRR activation
events as distinct event types so that I can evaluate start time, ramp,
duration, energy delivery, and non-performance without treating manual reserve
as an automatic trajectory.

**Why this priority**: mFRR is event-driven and its scheduled and direct modes
have different evidence and timing; merging them would invalidate delivery and
settlement conclusions.

**Independent Test**: A reviewer can replay one upward scheduled event, one
downward direct event, and overlapping invalid events against a small battery,
then reproduce event timing, delivered energy, constraint outcomes,
non-performance, and physical-result fingerprints from a published calculation
table. Product economics are tested independently under User Story 4.

**Acceptance Scenarios**:

1. **Given** a fixed mFRR capacity commitment and a valid scheduled-activation
   event with requested start, duration, ramp, direction, and requested power,
   **When** replay runs, **Then** the event's requested and delivered power and
   energy remain auditable from start through completion.
2. **Given** an otherwise equivalent direct-activation event, **When** replay
   runs, **Then** it remains typed and reported as direct activation and cannot
   be silently processed as scheduled activation.
3. **Given** public data in which direct activation is absent, **When** the
   historical demonstration is prepared, **Then** absence is reported as
   source coverage and no direct event or value is fabricated.
4. **Given** any events whose delivery intervals overlap, **When** validation
   is attempted, **Then** the sequence is rejected before replay regardless of
   event direction or scheduled/direct identity.
5. **Given** an event that starts outside the replay period, violates an
   activation delay, cannot meet its ramp or duration, or exceeds directional
   capacity and battery limits, **When** validation or replay is attempted,
   **Then** the offending event and deterministic failure or non-performance
   outcome are identified.

---

### User Story 4 - Audit Product-Specific Economics (Priority: P2)

As a researcher comparing reserve strategies, I need aFRR and mFRR accounting
to expose each economic component independently so that I can understand how
capacity, activated energy, non-performance, and battery use contribute to the
result.

**Why this priority**: A single net value would hide material differences
between the products and make studies difficult to reproduce or challenge.

**Independent Test**: Using fixed prices, commitments, delivered energy,
penalty rules, and a throughput cost, a reviewer can calculate all component
totals by hand and reconcile the reported net result exactly.

**Acceptance Scenarios**:

1. **Given** explicit directional capacity prices and eligible commitments,
   **When** settlement runs, **Then** upward and downward capacity revenue are
   reported separately for each product.
2. **Given** explicit activation-energy prices and delivered eligible energy,
   **When** settlement runs, **Then** upward and downward activated-energy
   revenue are reported separately, scheduled and direct mFRR identities remain
   distinct, and values are not inferred from aggregate price or volume fields
   with incompatible meaning.
3. **Given** a derived real-data scenario and a direction-, product-, and
   interval-compatible RTE activation price, **When** the researcher explicitly
   selects that price mapping, **Then** activated energy is settled with the
   observed area price and every result labels it as a scenario proxy rather
   than an asset invoice.
4. **Given** a declared non-performance rule and a declared throughput-cost
   rule, **When** replay completes, **Then** penalties, degradation proxy,
   throughput, gross revenue, and net result are each inspectable and reconcile
   to the documented identity.
5. **Given** a required settlement price that is absent or ambiguous, **When**
   settlement is requested, **Then** physical replay remains available but the
   settlement and total net result are marked unavailable; no component is
   silently assumed to be zero and no partial total is reported.
6. **Given** a valid aFRR or mFRR replay containing zero activation, **When** it
   is settled with complete compatible rules, **Then** balancing-energy revenue
   is zero while independently eligible capacity and baseline components retain
   their declared values.

---

### User Story 5 - Learn and Reproduce the Feature Offline (Priority: P2)

As a researcher new to French balancing markets, I need a documented working
example with clear plots and an optional guarded live section so that I can
understand both the feature's capabilities and the limits of the public data.

**Why this priority**: The distinction between market-area observations and
asset-level simulation inputs is subtle and must be visible in the primary
example, not left implicit in source code.

**Independent Test**: From a clean environment with no credentials or network,
a reviewer can execute the offline notebook in order, reproduce all recorded
tables and plots, and confirm that the live section is skipped by default.

**Acceptance Scenarios**:

1. **Given** the versioned offline examples, **When** the notebook is executed
   from start to finish, **Then** it explains aFRR, mFRR scheduled activation,
   and mFRR direct activation in non-technical language and plots market
   inputs, commitments, activation, requested and delivered battery power,
   SOC, headroom, tracking, non-performance, throughput, degradation proxy,
   and settlement components.
2. **Given** the notebook's default settings, **When** all offline sections
   execute, **Then** no credential is loaded, no network request is attempted,
   and no raw response is persisted.
3. **Given** an informed researcher who explicitly enables live acquisition
   and supplies a bounded period, **When** the guarded section runs, **Then** it
   demonstrates current retrieval while keeping credentials and short-lived
   tokens out of outputs and saved notebook state.
4. **Given** the source documentation, **When** a reviewer inspects any
   displayed public record, **Then** they can identify its owner, source
   version, request meaning, units, temporal resolution, transformations,
   redistribution status, and whether it is observed market data or a derived
   simulation input.

---

### User Story 6 - Preserve Validated FCR Behavior (Priority: P3)

As a library maintainer, I need the new restoration products to extend rather
than reinterpret existing FCR contracts so that current Feature 010 studies
remain reproducible.

**Why this priority**: aFRR and mFRR add new capabilities, but a regression in
the validated FCR reference profile would undermine the shared foundation.

**Independent Test**: A reviewer can run the complete existing Feature 010
offline validation and reference replay before and after the extension and
obtain the same public behavior and stored results.

**Acceptance Scenarios**:

1. **Given** an existing valid Feature 010 FCR request and fixtures, **When**
   the established replay and settlement paths run, **Then** their inputs,
   results, and reference values are unchanged.
2. **Given** an aFRR trajectory, an mFRR event sequence, or an FCR activation
   trace, **When** it is passed to a different product profile, **Then** the
   mismatch is rejected before replay rather than converted implicitly.
3. **Given** identical fixed inputs and artifacts for aFRR or mFRR, **When**
   acquisition-free schedule construction and replay are repeated, **Then**
   event ordering, traces, diagnostics, and totals are identical.

### Edge Cases

- A requested period is empty, reversed, open-ended, outside source coverage,
  only partially covered, or expressed in an ambiguous local time.
- A French delivery day contains a daylight-saving gap or fold; UTC intervals
  remain continuous and local labels remain unambiguous.
- RTE authentication is missing, rejected, expired, or interrupted; token
  renewal also fails, or a source request fails after authentication.
- A live source times out, interrupts a connection, rate-limits a request, or
  returns a transient server error across three total attempts; no partial
  acquisition is published.
- A credential or bearer token sentinel appears in a request description,
  artifact, filename, cache key, log, exception, fixture, document, plot, or
  saved notebook output.
- A source returns an empty or error response, malformed content, unexpected
  direction, non-finite value, unknown unit, unsupported resolution, duplicate
  interval, conflicting revision, price without matching quantity, or quantity
  without its declared market meaning.
- RTE and ENTSO-E observations overlap in time but disagree, use different
  aggregation boundaries, or describe different market concepts; both remain
  separate and the conflict is exposed.
- An RTE 15-minute requested need, activated volume, or price is supplied as an
  asset command without an explicit derived-scenario mapping.
- One RTE interval contains both nonzero upward and nonzero downward requested
  aFRR need; the derived scenario rejects the interval because the aggregate
  does not reveal the order of opposing requests.
- A derived mapping omits its inputs, fixed asset-allocation fraction,
  MW-to-kW scaling, no-clipping rule, assumptions, transformation history, or
  fingerprint.
- An asset-level aFRR trajectory has gaps, overlaps, ambiguous sample meaning,
  an incompatible interval grid, a direction outside its commitment, or a
  requested ramp that cannot be met.
- An mFRR event has an unknown activation type, missing requested start,
  negative delay or segment duration, zero total event duration, unsupported
  direction, a non-finite requested power, or a complete event interval
  extending beyond the study horizon.
- Two mFRR event delivery intervals overlap; the first release rejects the
  sequence before replay without adding, netting, or prioritizing requests.
- Scheduled and direct mFRR fields are both missing, only requested volume is
  available, or satisfied and locally activated volumes differ; no field is
  silently substituted for another.
- Direct mFRR activation is absent throughout the selected real period; the
  demonstration remains valid for scheduled activation and declares the gap.
- Fixed upward and downward commitments are negative, overlap incompatibly,
  exceed source eligibility, or leave insufficient charge/discharge headroom
  around the accepted energy baseline.
- A request is power-feasible initially but sustained activation reaches a
  minimum or maximum SOC boundary, or efficiency losses exhaust energy
  headroom before the activation ends.
- Battery energy or power bounds are invalid; initial SOC is outside its
  bounds; efficiencies, prices, costs, or tolerances are non-finite or outside
  their allowed ranges.
- Zero activation occurs under a nonzero capacity commitment; capacity revenue
  remains eligible under the declared rule while balancing-energy settlement
  remains zero.
- A capacity, activation-energy, penalty, or degradation component is requested
  without an explicit price or rule, unit, direction, and application period.
- A raw or normalized real-data fixture is selected for a package, release,
  public artifact, public mirror, or external store despite its restricted
  redistribution metadata.
- Offline loading encounters a missing artifact, invalid schema, digest
  mismatch, unsupported semantics version, or any attempt to initialize a live
  client implicitly.

## Requirements *(mandatory)*

### Functional Requirements

#### Compatibility and Ownership Boundaries

- **FR-001**: The feature MUST add aFRR and mFRR without changing Feature 010's
  FCR activation, scheduling, physical replay, settlement, artifact, or public
  result contracts.
- **FR-002**: Market-data production MUST own authentication, retrieval,
  normalization, validation, provenance, and artifact publication; control
  components MUST own fixed commitment and deterministic baseline construction;
  and the simulator MUST own physical delivery, performance, degradation proxy,
  and realized settlement.
- **FR-003**: aFRR, mFRR scheduled activation, mFRR direct activation, and FCR
  MUST have distinct product identities and validated inputs. No trajectory,
  event, price, quantity, commitment, or result MAY be silently converted or
  reused across those identities. Each Feature 011 replay MUST select exactly
  one restoration profile: day-ahead plus aFRR, or day-ahead plus mFRR.
  Simultaneous aFRR/mFRR or FCR/restoration replay is not supported.

#### Historical Data Acquisition and Artifacts

- **FR-004**: The primary French activation-data profile MUST use RTE
  Balancing Energy version 5.2 and MUST preserve the catalog version, requested
  resource, production endpoint identity, requested and covered periods,
  retrieval time, source resolution, field meanings, and source ownership.
- **FR-005**: The RTE aFRR profile MUST retrieve `standard_afrr_data` and
  preserve separate interval values for upward and downward requested need,
  volume activated for France, volume activated in France, and the associated
  weighted-average activation prices without reinterpreting one field as
  another. A successful request for the verified one-hour demonstration period
  MUST contain four complete consecutive 15-minute market-area records.
- **FR-006**: The RTE mFRR profile MUST retrieve `standard_mfrr_data` and
  preserve separate scheduled-activation (SA) and direct-activation (DA)
  requested, satisfied, locally activated, and clearing or settlement-price
  fields by direction when supplied by the source. Null, absent, and zero
  values MUST remain distinguishable.
- **FR-007**: The ENTSO-E Transparency Platform MUST remain a complementary
  source for French capacity, procurement, bid, activation, exchange, and price
  series only when the selected document, process, product, direction, unit,
  resolution, and coverage have been explicitly validated. ENTSO-E records
  MUST retain independent provenance and MUST NOT be used as an undocumented
  fallback for RTE records. The first Feature 011 release MUST NOT introduce an
  unvalidated restoration profile: its only supported complementary composition
  is the existing validated Feature 010 `fr-day-ahead-symmetric-fcr-v1`
  artifact, selecting its time-compatible A44 `day_ahead_price` series by
  fingerprint without changing or reinterpreting the closed Feature 010
  profile.
- **FR-008**: Acquisition MUST accept a caller-selected bounded
  start-inclusive/end-exclusive historical period. Canonical instants MUST use
  UTC while retaining the Europe/Paris local labels, offsets, and fold or gap
  information required to interpret French delivery intervals.
- **FR-009**: Every canonical series MUST independently record source, source
  version, resource or document identity, market/product/process identity,
  direction, area, requested and actual coverage, source and canonical
  resolution, source and canonical units, currency where applicable,
  retrieval time, transformation history, and content fingerprint.
- **FR-010**: Normalization MUST preserve source observations exactly except
  for declared, reproducible unit, sign, time, and structural transformations.
  Sources and fields MUST NOT be silently combined, substituted, interpolated,
  filled, scaled, or semantically reinterpreted.
- **FR-011**: Missing, incompatible, insufficiently resolved, ambiguous,
  overlapping, or conflicting source data MUST fail the requested acquisition
  or declared study contract with a diagnostic naming the source, resource or
  field, requested period, observed condition, and expected condition. A
  partially successful retrieval MUST NOT be published as complete.
- **FR-012**: Canonical restoration-market artifacts MUST be source-independent,
  immutable, versioned, integrity-checked, limited to one source acquisition,
  and usable without source-networking objects. Each artifact MUST declare
  which series are present, absent, requested, and required for its intended
  study. RTE and ENTSO-E observations MUST NOT be published together in one
  acquisition artifact.
- **FR-012a**: A study requiring multiple source acquisitions MUST compose them
  through an explicit immutable study bundle. The bundle MUST reference each
  artifact by identity and fingerprint, select the required series, record its
  own fingerprint, and preserve each source's provenance and redistribution
  policy without copying, merging, or renaming observations.
- **FR-013**: RTE and ENTSO-E area or platform aggregates MUST remain market
  observations and MUST NOT be represented as commands delivered to an
  individual BESS. Price and activated-energy observations MUST NOT be used to
  infer an asset-level activation command implicitly.
- **FR-014**: A researcher MAY create an asset-level activation scenario from
  area-level data only through an explicit mapping that records source inputs,
  a fixed finite asset-allocation fraction in `[0, 1]`, unit scaling,
  assumptions, transformation history, creation time, and fingerprint. For
  requested area volume in `MW`, the directional BESS request magnitude in
  `kW` MUST equal `area_requested_MW * 1000 * asset_allocation_fraction`. The
  same fraction MUST apply throughout one derived scenario. Period-relative
  normalization, hidden clipping, and time-varying allocation are prohibited;
  if any mapped request exceeds its direction-compatible committed capacity,
  scenario construction MUST fail. The resulting artifact and every downstream
  demonstration MUST identify it as a derived simulation scenario, not
  observed asset dispatch. For an aFRR mapping, an interval with both upward
  and downward requested need greater than zero MUST be rejected as ambiguous;
  neither netting, direction selection, nor invented subintervals are allowed.
- **FR-015**: Canonical artifacts MUST record raw-response content digests and
  retention and redistribution status without embedding credentials. A raw
  response MAY be retained as a separately verified restricted sidecar only
  when source terms and project policy permit it.

#### Acquisition Security and Offline Operation

- **FR-016**: Live RTE and ENTSO-E retrieval MUST be explicit and opt-in.
  Artifact loading, validation, control construction, replay, settlement,
  documentation examples, and routine tests MUST default to offline operation
  and MUST NOT initialize authentication or networking implicitly.
- **FR-016a**: Each RTE and ENTSO-E profile MUST expose three explicit
  acquisition modes. `fetch` creates a new immutable source-acquisition
  artifact, `refresh` compares new normalized source content with one existing
  artifact of the same request identity, and `offline` loads and validates an
  artifact without source access. An unchanged refresh MUST report no change
  and publish nothing; changed content MUST create an immutable successor linked
  to its predecessor and MUST NOT overwrite any version. In the first release,
  the ENTSO-E portion of this requirement is satisfied only by reusing the
  existing Feature 010 fetch/refresh/offline lifecycle for
  `fr-day-ahead-symmetric-fcr-v1`; Feature 011 defines no new ENTSO-E
  restoration acquisition profile.
- **FR-017**: `RTE_CLIENT_ID`, `RTE_CLIENT_SECRET`, and `ENTSOE_API_TOKEN` MUST
  be read only within an explicit acquisition operation. RTE short-lived access
  tokens MUST be obtained at runtime and MUST NOT be accepted as persisted
  request or artifact fields.
- **FR-018**: Credentials and access tokens MUST NOT appear in persisted
  requests, artifacts, raw-response digests, filenames, cache identities, logs,
  exceptions, fixtures, documentation, plots, or notebook inputs and outputs.
  Produced files and captured diagnostics MUST be verifiable with sentinel
  secret scans.
- **FR-019**: The repository MUST provide a safe local-environment template
  containing variable names and instructions but no values, and MUST continue
  to ignore local `.env` files. Loading a local environment file MUST not occur
  during package import or any offline workflow.
- **FR-020**: Authentication, transport, timeout, rate-limit, and server
  failures MUST be sanitized and atomic: no credential may be disclosed and no
  artifact may be marked complete unless all declared required requests and
  validations succeed. Fetch and refresh MUST retry only timeouts, connection
  interruptions, rate-limit responses, and transient server failures for no
  more than three total attempts per failed request window, including the
  initial attempt. They MUST honor a valid source retry delay, report the final
  sanitized cause and attempt count, and fail immediately for authentication
  and other permanent client errors.

#### Product Commitments and Activation Inputs

- **FR-021**: The simulator MUST accept fixed non-negative upward and downward
  capacity commitments separately for aFRR and mFRR, aligned to their declared
  delivery periods. Commitments are study inputs, not optimized bids.
- **FR-022**: An aFRR activation trajectory MUST declare product identity,
  source or derivation, direction/sign convention, period, sample boundaries,
  sample interpretation, resolution, creation or retrieval time, and
  fingerprint. Each sample MUST be signed requested BESS balancing power in
  `kW` under the library's charge-positive convention: negative is
  upward/discharge response, positive is downward/charge response, and zero is
  no aFRR activation. Each value MUST be the interval-average requested power
  over its start-inclusive/end-exclusive sample interval and MUST be integrated
  directly for energy. It MUST cover the replay horizon without gaps or
  conflicts; interpolation and upsampling are prohibited. A source expressed
  as points or setpoints requires a separately provenanced conversion before it
  satisfies this contract.
- **FR-023**: An mFRR activation sequence MUST contain typed scheduled or
  direct events. Every event MUST declare identity, direction, requested start,
  optional activation-delay duration, linear ramp-up duration, full-power hold
  duration, linear ramp-down duration, a finite non-negative requested power
  magnitude in `kW`, source or derivation, and fingerprint. Requested start
  begins the event: power remains zero during the declared delay, rises linearly
  from zero to the requested magnitude during ramp-up, remains at the requested
  magnitude during the hold, and falls linearly to zero during ramp-down. Each
  duration MUST be finite and non-negative, the total event duration MUST be
  positive, and the full event interval MUST be start-inclusive/end-exclusive.
  Direction MUST be a separate upward/downward identity: upward maps to negative
  charge-positive balancing power and downward maps to positive charge-positive
  balancing power. Requested event energy MUST be the exact integral of this
  piecewise profile and MUST NOT be accepted as an alternative request input.
  SA and DA fields MUST remain distinct even when their event shapes happen to
  match. The complete event intervals, including delay and both ramps, of any
  two events MUST NOT overlap; every overlap MUST be rejected before replay
  regardless of direction or SA/DA identity, with no addition, netting, or
  precedence rule.
- **FR-024**: Public 15-minute area-level records MAY provide market context or
  inputs to a declared derived scenario, but they MUST NOT by themselves
  satisfy the asset-level aFRR trajectory or mFRR event contract.
- **FR-025**: Deterministic product-specific baselines MAY construct fixed valid
  commitments and energy baselines from declared inputs. They MUST reserve
  directional capacity and charge/discharge headroom before assigning energy
  power, MUST NOT inspect future activation values, and MUST NOT claim optimal
  bidding or feasibility against unobserved activation.
- **FR-026**: Commitment validation MUST deterministically check product
  identity, temporal alignment, directional capacity, accepted energy baseline,
  charge and discharge power, usable SOC energy, efficiency, reserved capacity,
  headroom, activation time, ramp, and duration before a schedule is described
  as valid.

#### Physical Replay and Performance

- **FR-027**: The simulator MUST preserve the Feature 010 convention that
  positive battery power means charging. Every result MUST separately expose
  the accepted energy baseline, requested balancing response, requested
  combined power, delivered combined power, and delivered balancing response.
- **FR-028**: Every physical step MUST respect configured charge/discharge
  power, minimum/maximum SOC, charge/discharge efficiency, ramp, and applicable
  activation-time and duration limits even when the requested response is
  infeasible.
- **FR-029**: aFRR replay MUST report directional requested and delivered
  response, signed and absolute tracking error, delivered and undelivered
  energy, response delay, achieved ramp, saturation cause, saturation duration,
  SOC, and remaining upward and downward headroom at every relevant interval
  and in aggregate.
- **FR-030**: mFRR replay MUST report the same physical quantities by event and
  in aggregate, including requested and actual start, requested and actual
  completion, scheduled/direct identity, requested and delivered event energy,
  and any activation-time, ramp, duration, power, or SOC non-performance.
- **FR-031**: Zero activation under either product MUST preserve the accepted
  energy baseline, produce zero requested and delivered balancing energy, and
  produce zero balancing-energy revenue and non-performance. Capacity
  eligibility remains governed only by the declared capacity rule.
- **FR-032**: Multi-rate aggregation MUST conserve delivered charge,
  discharge, net, activated, and undelivered energy. No activation sample or
  event portion MAY be dropped, duplicated, or prorated without an explicit
  supported boundary rule.
- **FR-033**: Repeated replay with identical artifacts, battery configuration,
  commitments, baseline, activation inputs, settlement rules, degradation rule,
  and tolerance MUST produce identical samples, events, diagnostics,
  fingerprints, and totals without network access or randomness.

#### Settlement and Degradation

- **FR-034**: Settlement MUST keep day-ahead energy revenue, aFRR upward and
  downward capacity and activated-energy revenue when the selected profile is
  aFRR, or mFRR upward and downward capacity and activated-energy revenue when
  the selected profile is mFRR. The selected profile's non-performance
  penalties, degradation proxy, and total net result MUST also remain
  separately inspectable; components for the unselected restoration product
  MUST NOT appear as zero-valued settlement entries.
- **FR-035**: Capacity revenue MUST use only eligible fixed commitments,
  explicit direction-compatible prices, and covered duration. Activated-energy
  revenue MUST use only eligible delivered activation energy and explicit
  direction-compatible prices. Aggregate market volumes or prices MUST NOT be
  treated as asset settlement values without a declared study mapping. For a
  derived RTE scenario, the matching direction-, product-, and
  interval-compatible RTE weighted-average, clearing, or settlement activation
  price MAY be mapped explicitly as an area-price proxy for the simulated
  asset. The mapping and every financial output MUST identify it as a scenario
  proxy rather than an observed asset invoice; a missing or incompatible price
  remains subject to FR-038.
- **FR-036**: A non-performance penalty MUST use an explicit deterministic rule
  declaring product, event or period basis, direction, measured shortfall,
  price or rate, unit, and application period. With no penalty rule, penalty
  MUST be zero and identified as unconfigured rather than inferred.
- **FR-037**: Delivered battery-terminal throughput MUST equal total absolute
  delivered charge and discharge energy. The first-release degradation proxy
  MUST be an optional explicit non-negative cost per unit of throughput; when
  omitted, degradation cost MUST be zero and identified as unconfigured. No
  electrochemical-aging claim may be made from this proxy.
- **FR-038**: The total net result MUST reconcile exactly as declared
  day-ahead energy revenue plus all capacity revenue plus all activated-energy
  revenue minus explicit non-performance penalties minus the explicit
  degradation proxy. If any price required by the declared settlement is
  missing, incompatible, or ambiguous, physical replay MUST remain available
  but the settlement and total net result MUST be marked unavailable. No
  missing component may be silently replaced with zero, and no partial total
  may be reported.

#### Demonstrations, Documentation, and Distribution

- **FR-039**: The feature MUST include hand-calculable synthetic aFRR and mFRR
  cases that exercise both directions, zero activation, delivery, physical
  limits, ramp and timing behavior, settlement, and non-performance with
  published expected results and a default absolute numeric tolerance of
  `1e-6`.
- **FR-040**: The feature MUST include a bounded offline aFRR demonstration
  backed by four recorded 15-minute RTE observations from one verified hour and
  a reproducible signed-power scenario explicitly mapped from those
  observations. The mapping MUST use the separate upward and downward requested
  need as the source quantities that drive the simulated request; volumes
  activated for France and in France MUST remain observed comparison data and
  MUST NOT drive the command. The four derived samples MUST remain 15-minute
  interval averages and MUST NOT be interpolated or upsampled. The mapping MUST
  reject any interval containing nonzero requested need in both directions,
  satisfy FR-014, and ensure the scenario, replay, plots, and narrative
  prominently identify the activation as simulated rather than observed
  battery dispatch. Separately sourced or synthetic trajectories with shorter
  intervals MUST provide the ramp and high-resolution validation cases.
  Direction-compatible RTE weighted-average activation prices MAY be used only
  through the labelled area-price proxy defined by FR-035.
- **FR-041**: The feature MUST include a bounded offline mFRR demonstration
  containing at least one real scheduled-activation period with requested and
  satisfied volumes. That area-level observation MUST be mapped under FR-014
  into an explicit simulated BESS scheduled-activation event using the
  scheduled-activation requested volume as the source quantity that drives the
  simulated request. Satisfied need and locally activated volume MUST remain
  observed comparison data and MUST NOT drive the command. The event, replay,
  plots, and narrative MUST prominently identify it as derived rather than
  observed asset dispatch. Direct activation MAY be demonstrated only when
  observed or supplied through a separately valid explicit event artifact;
  sparse or absent DA source data MUST NOT be fabricated. A compatible RTE
  clearing or settlement activation price MAY be used only through the labelled
  area-price proxy defined by FR-035.
- **FR-042**: Raw and normalized real-data fixtures MUST be restricted to
  authorized collaborators in the owner-confirmed private repository. Their
  metadata and build rules MUST prohibit inclusion in packages, releases,
  public CI artifacts, public forks or mirrors, and external artifact stores,
  and MUST require reassessment before any repository visibility change.
- **FR-043**: A document under `docs/` MUST explain RTE Balancing Energy 5.2
  and the applicable ENTSO-E profile, authentication and local-environment
  handling, sanitized request examples, exact requested resources and fields,
  units, resolutions, UTC and Europe/Paris handling, query limits, errors,
  source ownership, redistribution restrictions, transformations, and the
  distinction between area aggregates and asset-level activation commands.
- **FR-044**: The feature MUST provide a documented notebook that executes
  offline by default, explains aFRR, mFRR SA, and mFRR DA in non-technical
  language, and displays all market, commitment, activation, physical,
  performance, throughput, degradation, provenance, and settlement variables
  needed to audit the demonstrations.
- **FR-045**: The notebook MUST contain a separately guarded live-acquisition
  section with caller-selected bounded query parameters for RTE and, where
  applicable, ENTSO-E. For the first release, ENTSO-E is applicable only when
  the selected period can use the existing Feature 010
  `fr-day-ahead-symmetric-fcr-v1` lifecycle and its A44 `day_ahead_price`
  series; otherwise the branch MUST report that no compatible profile was
  selected and perform no substitute query. The section MUST be disabled by
  default, require explicit opt-in, avoid persistence of raw responses and
  secrets, and explain that live source availability is not required for the
  offline results.
- **FR-046**: Public restoration-market, control, and simulator surfaces MUST
  be stable and source-independent for offline consumers. Live retrieval and
  notebook capabilities MUST remain isolated so default imports and routine
  validation need no credentials, network, notebook runtime, commercial
  solver, GPU/SLURM resource, experiment tracker, or legacy runtime.
- **FR-047**: Reproducibility inputs MUST include every market and activation
  artifact fingerprint, any study-bundle fingerprint, product and semantics
  version, temporal grid, battery configuration, fixed schedules or heuristic
  parameters, derived-scenario mapping, settlement and degradation rules,
  numeric tolerance, and expected result fingerprint.

### Out of Scope

- Joint bidding or optimization across FCR, aFRR, and mFRR
- Simultaneous physical replay or settlement of more than one reserve product;
  each first-release replay selects either aFRR or mFRR alongside day-ahead
- Forecast-aware model-predictive control, stochastic bidding, reinforcement
  learning, or any claim of optimal profitability
- Continuous ingestion, streaming, production operations, or mandatory live
  data access
- Cross-border balancing-platform, network, congestion, or portfolio modeling
- Detailed national prequalification, certification, imbalance, tax, or
  contractual penalty rules not explicitly represented by a study input
- Detailed electrochemical aging or lifetime prediction beyond the declared
  first-order throughput-cost proxy
- Treating public control-area or platform aggregates as observed operational
  dispatch instructions for an individual asset
- Fabricating unavailable direct mFRR activation or any other missing source
  observation

### Key Entities *(include if feature involves data or API design)*

- **Restoration Market Data Request**: Persistable, credential-free
  description of one explicit bounded source operation, including source,
  version, resource or document identity, market area, product, direction,
  requested fields, half-open period, and fetch or refresh mode. Offline load
  consumes an artifact identity rather than a source request.
- **Restoration Market Artifact**: Immutable, versioned, source-independent
  collection of market series from exactly one source acquisition, with a
  manifest of present, absent, requested, and study-required series; temporal
  contract; provenance; integrity; predecessor lineage where applicable; and
  retention and redistribution metadata.
- **Restoration Study Bundle**: Immutable composition manifest that references
  one or more source-acquisition artifacts and selected series by identity and
  fingerprint. It has its own fingerprint and study purpose but copies or
  merges no source observations and weakens no source redistribution rule.
- **Restoration Market Series**: One interval-indexed observed price, volume,
  need, procurement, bid, activation, or exchange series with its own source,
  semantic identity, direction, units, resolution, coverage, transformations,
  and fingerprint.
- **Derived Simulation Mapping**: Explicit reproducible rule that converts
  identified area-level observations into a simulated asset-level input,
  including one fixed asset-allocation fraction, MW-to-kW scaling, capacity
  rejection, assumptions, lineage, and a label that prevents the output from
  being mistaken for observed dispatch. It performs no period-relative
  normalization or hidden clipping.
- **Directional Capacity Commitment**: Fixed non-negative upward or downward
  capacity for one product and delivery period, associated with eligibility,
  price, baseline, and headroom checks.
- **aFRR Activation Trajectory**: Source-independent automatic asset-level
  request over declared intervals, expressed as signed requested BESS balancing
  power in `kW`, where negative is upward/discharge and positive is
  downward/charge. Each value is interval-average power over a half-open sample
  interval and is never interpolated or upsampled, with product identity,
  provenance or derivation, coverage, and fingerprint.
- **mFRR Activation Event**: Source-independent scheduled or direct manual
  request with direction, requested start, optional activation delay, separate
  linear ramp-up, full-power hold, and linear ramp-down durations, finite
  non-negative requested power in `kW`, provenance or derivation, and identity.
  Upward and downward are explicit identities mapped respectively to negative
  and positive charge-positive balancing power. The complete half-open event
  interval includes every segment, and requested energy is the exact integral
  of the piecewise profile.
- **Restoration Replay Result**: Auditable requested and delivered baseline and
  balancing traces, physical states, headroom, tracking or event performance,
  non-delivery causes, energy totals, provenance, and fingerprints.
- **Restoration Settlement Rule**: Explicit capacity, activated-energy,
  non-performance, and total-reconciliation contract with product, direction,
  price, unit, eligibility, and period meaning. If any required price is
  unavailable, the physical replay remains valid but this settlement and its
  total net result are unavailable as a whole. A matching RTE area activation
  price may be used only as an explicitly mapped and labelled scenario proxy,
  never as an observed asset invoice.
- **Throughput Degradation Rule**: Optional first-order cost per unit of
  battery-terminal throughput, reported independently and explicitly excluded
  from electrochemical aging claims.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Existing unified-library runtime only; the feature
  must not add an unconditional heavyweight dependency to default imports or
  offline replay.
- **Optional dependencies**: Explicit live acquisition and notebook plotting
  dependencies may remain isolated from the core library and routine tests.
- **External services**: RTE Balancing Energy version 5.2 and the ENTSO-E
  Transparency Platform R3 service, contacted only by explicit live
  acquisition operations.
- **Credentials**: Caller-owned `RTE_CLIENT_ID`, `RTE_CLIENT_SECRET`, and
  `ENTSOE_API_TOKEN`, available only at explicit acquisition boundaries and
  absent from all persistable entities.
- **Hardware assumptions**: CPU-only operation; no GPU, SLURM, commercial
  solver, or external experiment tracker is required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One explicit acquisition of the verified one-hour French aFRR
  period produces exactly four consecutive 15-minute records containing every
  requested upward and downward need, activation-volume, and price field, with
  zero credential or token sentinel occurrences in produced files and captured
  output.
- **SC-002**: One explicit acquisition of the verified French mFRR reference
  period preserves at least one real scheduled-activation record containing
  requested and satisfied volume, while the presence or absence of direct
  activation is reported exactly as observed.
- **SC-003**: One hundred percent of retained market series expose source,
  version, semantic identity, direction, requested and covered periods,
  resolution, units, transformation history, retrieval time, and a verifiable
  content fingerprint.
- **SC-004**: Synthetic aFRR validation reproduces all published upward,
  downward, zero-activation, ramp-limited, power-limited, and SOC-limited
  requested and delivered values, energy totals, performance metrics, and
  settlement components within `1e-6` absolute tolerance.
- **SC-005**: Synthetic mFRR validation reproduces all published scheduled and
  direct event start, ramp, duration, requested and delivered energy,
  non-performance, and settlement values within `1e-6` absolute tolerance and
  rejects 100% of cross-product input substitutions.
- **SC-006**: Across every validated replay, delivered battery power and SOC
  exceed their configured bounds in zero intervals, and all applicable power,
  SOC, headroom, ramp, activation-time, and duration shortfalls are attributed
  to a deterministic cause.
- **SC-007**: For both aFRR and mFRR, zero-activation cases reproduce the
  accepted baseline exactly within `1e-6`, deliver exactly zero balancing
  energy, and report exactly zero balancing-energy revenue.
- **SC-008**: For every settled demonstration, the sum of independently
  displayed day-ahead, directional capacity, directional activated-energy,
  penalty, and degradation components equals the displayed total net result
  within `1e-6`.
- **SC-009**: Two offline executions of every recorded demonstration produce
  identical artifact and result fingerprints, event ordering, diagnostics,
  traces, and settlement totals with zero attempted network calls.
- **SC-010**: Validation covers at least one failure for each of these classes:
  authentication redaction, missing field, incomplete coverage, incompatible
  resolution, incompatible product type, power, SOC, headroom, ramp,
  activation time, duration, event overlap, source disagreement, artifact
  integrity, and restricted redistribution.
- **SC-011**: All offline notebook cells execute in order without credentials
  or network access and produce labelled plots or tables for 100% of the market,
  commitment, activation, requested/delivered power, SOC/headroom,
  performance, throughput/degradation, provenance, and settlement variable
  groups required by this specification; the live section remains disabled.
- **SC-012**: A reviewer can use the source document to identify, for every
  demonstrated field, its owner, source version, request meaning, units,
  resolution, time convention, transformation, redistribution status, and
  whether it is observed or derived, with no undocumented field remaining.
- **SC-013**: The complete pre-existing Feature 010 validation suite passes
  unchanged, and its recorded FCR reference outputs remain byte-for-byte
  stable.
- **SC-014**: Restricted real-data artifacts occur in zero built packages,
  releases, public CI artifacts, configured public mirrors, or external
  artifact uploads.
- **SC-015**: An unchanged refresh publishes zero new artifacts, a changed
  refresh preserves the prior artifact and creates exactly one linked immutable
  successor, each deterministic transient-failure case makes exactly three
  attempts, and each permanent client-failure case makes exactly one attempt.

## Assumptions

- Target users are researchers running one-BESS historical simulations through
  the public Python library and optional notebook, not market operators issuing
  real-time dispatch.
- RTE Balancing Energy 5.2 is the primary French source for area-level aFRR and
  mFRR activation information. Its `standard_afrr_data` and
  `standard_mfrr_data` resources provide 15-minute market-area records, not
  asset-level control signals.
- The verified aFRR acquisition sample is the UTC hour
  `[2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)`. The verified mFRR sample is a
  bounded period on 2026-08-15 containing a downward scheduled activation with
  requested and satisfied volume; planning will pin its exact enclosing UTC
  interval and source fingerprint.
- Direct mFRR activation is sparse and may be absent from the selected
  historical period. Synthetic DA validation is required, but a real DA fixture
  is not a completion condition unless genuine source coverage is found.
- RTE price, requested-need, satisfied-need, and activated-volume fields describe
  different concepts. A value being present does not authorize substitution
  for another field or direct use as an individual battery command.
- ENTSO-E remains complementary and may have product- and period-dependent
  coverage. Only series whose meaning and resolution are proven during planning
  may become required by a reference profile.
- Asset-level aFRR trajectories and mFRR events are explicit source-independent
  inputs. When no suitable observed asset signal is available, deterministic
  synthetic cases and transparently derived scenarios establish simulator
  behavior without claiming observed dispatch.
- The real-data aFRR demonstration uses a transparent derived scenario mapped
  from its recorded RTE upward and downward requested-need aggregates and labels
  the resulting signed-power trajectory and replay as simulated, not observed
  asset dispatch. Its four samples remain 15-minute interval averages without
  interpolation or upsampling; activated-volume fields remain comparison
  observations.
- The real-data mFRR demonstration maps its verified RTE scheduled-activation
  requested volume into a simulated BESS event through an explicit
  derived-scenario mapping and never presents that event as an observed battery
  instruction. Satisfied and locally activated volumes remain comparison
  observations.
- Each real-data derived scenario pins one fixed asset-allocation fraction,
  applies `area_requested_MW * 1000 * fraction` without normalization or
  clipping, and is invalid if the mapped request exceeds committed capacity.
- Each settled real-data derived scenario may map its matching RTE activation
  price as a labelled area-price proxy; this is a simulation assumption and not
  evidence of the BESS's actual settlement invoice.
- The first release reuses Feature 010's one-BESS physical transition, accepted
  energy-baseline concept, charge-positive sign convention, offline artifact
  boundary, default `1e-6` numeric tolerance, and restricted-fixture policy.
- The throughput degradation rule is a transparent first-order cost proxy for
  comparative studies, not an electrochemical health or lifetime model.
- Fixed schedules and deterministic heuristics are research baselines. Bid
  selection and joint multi-product optimization belong to later features.
- Each Feature 011 replay combines the accepted day-ahead baseline with exactly
  one restoration product. Cross-product service stacking and settlement are
  deferred until the independent profiles are validated.
- RTE and ENTSO-E acquisition reuse Feature 010's explicit fetch, immutable
  refresh, and offline-load lifecycle plus its maximum of three total attempts
  for transient failures.
- The private repository is accessible only to authorized collaborators;
  private status does not grant permission to redistribute restricted source
  data through packages, releases, public CI artifacts, mirrors, or external
  stores.
