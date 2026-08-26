# Feature Specification: FCR Bid-Evaluation Parity

**Feature Branch**: `012-fcr-bid-evaluation-parity`
**Created**: 2026-08-26
**Status**: Draft
**Input**: User description: "Make the existing FCR simulator a deterministic, bidder-independent evaluator for fixed daily bid plans, with bounded aggregate parity against the pinned robust-storage-bidding reference implementation and no optimization in scope."

## Purpose *(mandatory)*

Provide one trustworthy evaluation boundary for fixed day-ahead energy and
Frequency Containment Reserve (FCR) bids. A researcher must be able to submit
the same complete daily schedules regardless of whether they came from a
manual case, a heuristic, a future robust optimizer, or a future tractable
probabilistic model (TPM), then receive physical replay, settlement, daily
metrics, and diagnostics from one common environment.

The feature also establishes bounded reference-result parity against the pinned
implementation under `baselines/robust_storage_bidding/`. The reference
implementation, rather than a general claim of being "paper-compatible", is
the coding and result reference. The associated publication remains
mathematical context. Parity is claimed only for the fixed decisions and
aggregate result fields supported by the generated 2023-06-18 reference
artifact.

Feature 012 evaluates and compares fixed bids. It does not choose, optimize, or
revise them. This separation lets later bidders compete through identical
schedule, replay, settlement, and reporting contracts.

## Clarifications

### Session 2026-08-26

- Q: When the battery cannot fully deliver requested FCR, which energy basis
  determines activation-energy revenue? → A: Delivered FCR energy; undelivered
  energy is unpaid and remains separately reportable for penalties.
- Q: How should the full reference `xi_EU` activation dataset be supplied? → A:
  Do not redistribute it; users download it directly from the documented
  upstream location and place it at the documented local location.
- Q: Which battery-state unit is canonical for reference parity? → A: Stored
  energy in kWh; normalized SOC is optional supplementary information.
- Q: What result should an invalid fixed bid plan produce? → A: A deterministic
  failed evaluation report with diagnostics and no valid settlement or profit;
  any diagnostic physical replay remains separate.
- Q: How should daily requested and delivered FCR activation energy be
  summarized? → A: Separate non-negative upward/discharge and
  downward/charge totals plus signed net energy.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability and validation
- **Target surface**: Public fixed-bid evaluation and reporting surface;
  versioned settlement profile; deterministic reference fixtures; migration
  and provenance documentation
- **Legacy reference paths**: None. `legacy/*` remains out of scope. The
  external reference implementation is pinned separately under
  `baselines/robust_storage_bidding/`.
- **New-code location**: Existing reusable extension points under
  `src/open_energy_lab`, with corresponding unit and integration validation
  under `tests`; exact module placement is deferred to planning. No new code
  belongs under `baselines/*` or `legacy/*`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evaluate Any Fixed FCR Bid Plan Consistently (Priority: P1)

As a storage researcher, I need to evaluate one complete daily energy-and-FCR
bid plan without the evaluator knowing how the plan was produced so that
manual, heuristic, robust, and TPM plans can be compared fairly.

**Why this priority**: A common bidder-independent boundary is the prerequisite
for every later bidding comparison. Without it, observed performance
differences could come from different physical or accounting implementations.

**Independent Test**: A reviewer can submit a hand-calculable fixed plan using
the existing energy and FCR schedules, replay it against a complete activation
trace, and independently reproduce every physical and economic result.

**Acceptance Scenarios**:

1. **Given** one valid hourly energy schedule, one valid four-hour FCR schedule,
   a compatible battery, prices, time contract, and activation trace, **When**
   the researcher evaluates the plan, **Then** one deterministic result reports
   its physical trace, settlement, daily metrics, diagnostics, and lineage.
2. **Given** otherwise identical plans labelled as manual, heuristic, robust,
   or TPM-produced, **When** they contain identical schedule values and
   metadata relevant to evaluation, **Then** they receive identical physical
   and economic results.
3. **Given** a manual or heuristic plan with no optimization objective or
   bound, **When** it is evaluated, **Then** evaluation succeeds and the
   unavailable optimization metadata is explained explicitly rather than
   fabricated.
4. **Given** zero FCR capacity, **When** evaluation runs, **Then** existing
   arbitrage behavior is preserved and no FCR activation payment or penalty is
   created.
5. **Given** a zero energy baseline and valid nonzero FCR capacity, **When**
   evaluation runs, **Then** day-ahead energy revenue is zero while FCR
   delivery, capacity revenue, activation-energy revenue, tracking, and
   throughput remain independently visible.

---

### User Story 2 - Translate And Compare A Pinned Reference Result (Priority: P1)

As a researcher reproducing the reference work, I need fixed reference
decisions to be translated without hidden sign, unit, time, or index choices so
that Open Energy Lab can be compared with a concrete result from the pinned
implementation.

**Why this priority**: This is the first evidence that the shared environment
has the semantics needed by the future reference optimizer and TPM bidder.

**Independent Test**: A reviewer can transform the generated Experiment 2
result for 2023-06-18, replay the same declared inputs, and match every
supported rounded aggregate within its declared parity domain.

**Acceptance Scenarios**:

1. **Given** the reference implementation's 24 hourly `x0` decisions, **When**
   they are transformed, **Then** positive-discharge reference power becomes
   equal-magnitude negative library power and negative-charge reference power
   becomes equal-magnitude positive library power.
2. **Given** the reference implementation's six non-negative four-hour `xr`
   decisions, **When** they are transformed, **Then** their magnitude and
   non-negative capacity meaning are preserved.
3. **Given** the reference prices, battery parameters, activation values, and
   fixed decisions, **When** the translated case is assembled, **Then** every
   unit, interval mapping, timezone assumption, and source fingerprint is
   declared and validated before replay.
4. **Given** the complete 2023-06-18 case, **When** Open Energy Lab evaluates
   it, **Then** the declared aggregate profit, energy-flow, stored-energy, and
   power fields agree with the generated reference artifact under the
   documented field-specific source-precision policy derived from its rounded
   decisions and outputs.
5. **Given** a result field or temporal detail not present in the generated
   reference artifact, **When** a parity comparison is requested for it,
   **Then** the comparison reports that the evidence is unavailable and does
   not extend the parity claim by inference.

---

### User Story 3 - Audit Settlement And Daily Performance (Priority: P1)

As a researcher comparing bidders, I need each revenue, battery-use, and
delivery component to remain inspectable so that I can explain why two bid
plans perform differently.

**Why this priority**: Total profit alone cannot reveal whether performance
came from day-ahead trading, FCR availability, activation energy, penalties,
or a physically infeasible request.

**Independent Test**: A reviewer can calculate a small case by hand and
reconcile day-ahead revenue, capacity revenue, activation-energy revenue,
penalties, energy flows, throughput, and total profit independently.

**Acceptance Scenarios**:

1. **Given** reference-result settlement with energy payment enabled, **When**
   replay finishes, **Then** accepted day-ahead revenue, FCR capacity revenue,
   activation-energy revenue based only on delivered FCR energy, penalties,
   and total profit are separately visible and reconcile within the internal
   numeric tolerance.
2. **Given** the reference artifact's combined `profit_fcr`, **When** it is
   compared with the library result, **Then** the library's capacity and
   activation-energy components sum to the combined reference value under the
   declared rounding policy.
3. **Given** a plan whose baseline and FCR capacity violate static
   charge/discharge reserve power headroom or use incompatible battery inputs,
   **When** accepted-commitment preflight runs without inspecting the realized
   activation trajectory, **Then** the evaluator returns a deterministic failed
   report with diagnostics and no valid settlement or profit. A separately
   selected diagnostic replay may expose requested and delivered power,
   tracking error, non-delivery, and saturation causes, but cannot enter normal
   bidder comparisons.
4. **Given** a plan that passes static accepted-commitment preflight but whose
   realized activation drives the battery to a stored-energy bound, **When**
   physical replay runs, **Then** the result remains a valid settled evaluation,
   activation-energy revenue uses only delivered energy, any configured
   non-delivery penalty is applied, and the saturated run remains outside the
   initial reference-parity domain.
5. **Given** unavailable imbalance, degradation, intraday, or terminal-value
   assumptions, **When** a daily report is produced, **Then** those components
   are marked unavailable rather than silently set to zero.
6. **Given** a day with both upward/discharge and downward/charge activation,
   **When** requested and delivered FCR energy are summarized, **Then** each
   direction is reported separately as a non-negative quantity, signed net
   energy follows the library's charge-positive convention, and throughput is
   not derived from the cancellation-prone net value.

---

### User Story 4 - Reproduce Results Offline With Complete Lineage (Priority: P2)

As a maintainer, I need committed, provenance-rich fixtures and deterministic
reports so that routine validation does not depend on the reference repository,
commercial tools, network services, or an earlier research session.

**Why this priority**: The parity evidence must remain reviewable and stable in
ordinary development and continuous integration environments.

**Independent Test**: From a checkout without an initialized reference
submodule, Julia, Gurobi, the external activation dataset, credentials, or
network access, a reviewer can run the hand oracle and public input-contract
tests twice and receive identical results and fingerprints. A separately
selected full-reference check succeeds after the user follows the documented
download and placement instructions.

**Acceptance Scenarios**:

1. **Given** the normalized Golden Reference Fixture, **When** its provenance
   is inspected, **Then** the reference commit, generation command, original
   digest, configuration, mapping rules, expected fields, and redistribution
   status are available.
2. **Given** identical validated inputs, **When** evaluation is repeated,
   **Then** ordered traces, daily reports, diagnostics, and fingerprints are
   identical.
3. **Given** an unavailable reference submodule, optional reference runtime,
   or external activation dataset, **When** routine validation runs, **Then**
   all routine validation completes offline from library-owned fixtures.
4. **Given** a researcher who wants to run the full 2023-06-18 parity case,
   **When** the upstream activation dataset is absent, **Then** documentation
   identifies its authoritative download location, required local placement,
   and integrity checks, and the library performs no implicit download.
5. **Given** a correctly placed and validated upstream activation dataset,
   **When** the researcher explicitly selects the full-reference check,
   **Then** the 2023-06-18 input slice is loaded and evaluated without requiring
   Julia, Gurobi, or network access during that check.

---

### User Story 5 - Preserve Validated Feature 010 Behavior (Priority: P2)

As a library maintainer, I need reference-result evaluation to extend rather
than reinterpret the existing FCR vertical slice so that prior studies and
fixtures remain reproducible.

**Why this priority**: The new parity profile cannot be trusted if enabling it
silently changes the already validated default simulator and settlement
semantics.

**Independent Test**: The unchanged Feature 010 oracle, zero-FCR,
regulation-only, real-replay, import-boundary, and fingerprint cases retain
their expected outputs when the new profile is not selected.

**Acceptance Scenarios**:

1. **Given** an existing Feature 010 request using the default settlement
   behavior, **When** it is replayed after Feature 012 is added, **Then** its
   public result, component values, ordering, and fingerprints remain
   unchanged.
2. **Given** a researcher who explicitly selects reference-result evaluation,
   **When** the same physical schedules are replayed, **Then** the selected
   profile and its additional accounting are explicit in the inputs, outputs,
   and fingerprints.
3. **Given** existing FCR, aFRR, and mFRR types, **When** the new evaluator
   validates its inputs, **Then** it accepts only the intended FCR contracts
   and cannot silently substitute restoration-product inputs.

### Edge Cases

- The daily horizon has missing, duplicate, overlapping, or partial hourly,
  quarter-hour, four-hour, or ten-second intervals.
- A requested period is a 23-hour or 25-hour daylight-saving transition day
  but is represented as an ordinary 24-hour parity case.
- Reference values contain non-finite numbers, negative FCR capacity, an
  undeclared unit, or an unknown sign convention.
- Reference price units or FCR block-price semantics are incompatible with the
  declared library units.
- The activation trace, prices, schedules, or battery configuration do not
  cover exactly the same absolute period.
- The supplied reference digest, source commit, schema version, or input
  fingerprint does not match the fixture provenance.
- The objective value or objective bound is confused with realized profit.
- Reference values are rounded to three decimals while library calculations
  use finer precision.
- The source reference artifact does not contain a requested comparison field,
  including the complete ten-second stored-energy trajectory.
- A plan passes shape validation but fails static accepted-commitment power
  headroom validation; diagnostic replay must remain distinguishable from valid
  replay.
- A plan passes static accepted-commitment validation but the realized
  activation produces stored-energy saturation and non-delivery; the run remains
  settleable but outside the initial reference-parity domain.
- Settlement components do not reconcile to the reported total.
- The reference submodule, Julia, Gurobi, network access, or restricted source
  data is unavailable during routine validation.
- The user-supplied activation dataset is missing, stored at the wrong
  location, truncated, structurally incompatible, or fails its documented
  integrity check.
- Invalid input must never be silently filled, interpolated, clipped,
  upsampled, or reinterpreted as valid reference evidence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST evaluate a fixed bid plan without depending on
  the method that produced it.
- **FR-002**: A fixed bid plan MUST reference exactly one existing complete
  hourly energy schedule and one existing complete four-hour FCR capacity
  schedule rather than duplicate their interval values.
- **FR-003**: A fixed bid plan MUST identify its producer, semantics version,
  information cutoff, schedule fingerprints, relevant input fingerprints,
  status, and ordered diagnostics.
- **FR-004**: Objective value and objective bound MUST be optional plan
  metadata, MUST remain distinct from realized settlement, and MUST have an
  explicit unavailability reason when absent.
- **FR-005**: The evaluator MUST reuse the existing FCR schedule, time,
  battery, replay, delivery-attribution, and saturation meanings rather than
  introduce a second physical model.
- **FR-006**: Reference hourly `x0` power MUST be transformed by sign inversion
  from positive-discharge reference semantics to positive-charge library
  semantics.
- **FR-007**: Reference non-negative `xr` values MUST preserve their magnitude
  and capacity meaning when transformed into FCR commitments.
- **FR-008**: The reference activation-response and combined-power mapping MUST
  be declared and independently validated against the existing library
  convention.
- **FR-009**: Every reference mapping MUST declare input and output units,
  price basis, currency, interval indexing, absolute period, timezone, and
  conversion rule; undeclared or incompatible mappings MUST fail.
- **FR-010**: The ordinary-day reference profile MUST require 24 complete
  hourly decisions, six complete four-hour FCR decisions, 96 complete
  quarter-hour checkpoints, and 8,640 complete ten-second activation intervals.
- **FR-011**: The evaluator MUST reject incomplete, duplicate, overlapping,
  ambiguous, non-finite, or temporally incompatible inputs before representing
  them as a valid evaluation.
- **FR-012**: Reference-result settlement MUST be an explicitly selected and
  versioned profile, while the existing Feature 010 default remains unchanged.
- **FR-013**: The reference-result settlement profile MUST separately report
  accepted day-ahead revenue, FCR capacity revenue, activation-energy revenue
  based only on delivered FCR energy, penalties, and total profit; requested
  but undelivered FCR energy MUST remain unpaid and separately reportable for
  penalty treatment.
- **FR-014**: Reference-result settlement MUST report charge energy, discharge
  energy, and throughput separately.
- **FR-015**: Every available settlement component MUST reconcile to total
  profit within the declared internal tolerance.
- **FR-016**: The sum of library FCR capacity and activation-energy revenue
  MUST reconcile with the reference artifact's combined `profit_fcr` after the
  reference comparison policy is applied.
- **FR-017**: Imbalance settlement, degradation cost, intraday settlement, and
  terminal value MUST remain explicitly unavailable unless a future versioned
  profile supplies them.
- **FR-018**: Every successful daily evaluation MUST report total and component
  profit, charge and discharge energy, throughput,
  initial/minimum/maximum/terminal stored energy in kWh, requested and
  delivered power extrema, requested and delivered FCR energy by direction and
  net, tracking, non-delivery, saturation or violation diagnostics, producer
  identity, information cutoff, and lineage fingerprints. For both requested
  and delivered FCR energy, upward/discharge and downward/charge totals MUST be
  separate non-negative quantities and signed net energy MUST use the library's
  charge-positive convention. Throughput MUST remain separate from net energy.
  Normalized SOC MAY be included as supplementary information but MUST NOT
  replace the stored-energy parity fields.
- **FR-019**: A comparison result MUST identify which fields were compared,
  which passed or failed, the applied mapping and precision policy, and which
  requested fields lacked reference evidence.
- **FR-020**: The initial Golden Reference Fixture containing aggregate parity
  evidence MUST be derived from the generated reference Experiment 2 result for
  2023-06-18 and MUST preserve the provenance stated under Reference
  Implementation Requirements.
- **FR-021**: The Golden Reference Fixture MUST contain the permitted reference
  result, mappings, expected aggregates, and provenance needed by routine
  validation, but MUST reference rather than embed the upstream full activation
  dataset.
- **FR-022**: Reference aggregate comparison MUST use the reference artifact's
  documented three-decimal precision separately from the library's internal
  equation tolerance. Because the initial artifact rounds both `x0`/`xr`
  decisions and aggregate outputs, the initial comparison MUST propagate the
  decision-rounding uncertainty into a documented field-specific acceptance
  interval and MUST record whether exact rounded equality also holds. A
  blanket tolerance or an exact-equality claim unsupported by unrounded
  decisions is forbidden.
- **FR-023**: The reference parity claim MUST be limited to the fixed decisions
  and aggregate fields actually supported by the generated artifact.
- **FR-024**: The feature MUST NOT claim complete ten-second parity with the
  reference implementation because the generated artifact does not contain a
  ten-second stored-energy trajectory.
- **FR-025**: A hand-calculable oracle MUST independently validate sign
  conversion, activation direction, efficiency-aware stored energy, settlement
  components, energy flow, tracking, non-delivery, saturation diagnostics, and
  total reconciliation.
- **FR-026**: The library's detailed trace MUST satisfy energy conservation,
  time aggregation, battery-bound, delivery-attribution, and deterministic
  ordering invariants even where no detailed reference trace exists.
- **FR-027**: Identical validated inputs MUST produce identical ordered traces,
  reports, diagnostics, and fingerprints without randomness or wall-clock
  state.
- **FR-028**: Routine validation MUST operate offline without Julia, JuMP,
  Gurobi, solver licenses, network access, notebooks, an initialized reference
  submodule, or the externally downloaded full activation dataset.
- **FR-029**: Running the reference implementation MUST remain an explicit
  fixture-generation or fixture-refresh workflow rather than a routine test or
  production dependency.
- **FR-030**: Open Energy Lab MUST NOT redistribute the full reference
  activation dataset. User documentation MUST identify the authoritative
  upstream download, the required local placement, the expected structure and
  integrity evidence, and the explicit full-reference operation that consumes
  it; library behavior MUST NOT download it implicitly.
- **FR-031**: Production library behavior MUST NOT import, execute, or mutate
  files under `baselines/*` or `legacy/*`.
- **FR-032**: Behavior migrated from the reference implementation MUST cite the
  exact reference source path and distinguish preserved behavior from
  intentionally rejected brittle assumptions.
- **FR-033**: Invalid reference evidence MUST NOT be silently filled,
  interpolated, upsampled, clipped, or relabelled as observed parity evidence.
- **FR-034**: Existing zero-FCR, regulation-only, default-settlement, replay,
  fixture, fingerprint, import, and lazy-dependency behavior from Feature 010
  MUST remain compatible.
- **FR-035**: The feature MUST NOT generate bids, formulate optimization
  problems, construct uncertainty sets, apply intraday recourse, orchestrate
  multiple days, carry SOC across days, fit TPMs, or alter aFRR/mFRR behavior.
- **FR-036**: A plan that fails accepted-commitment validation MUST produce a
  deterministic failed evaluation report with validation diagnostics and no
  valid settlement or profit. Any separately selected diagnostic physical
  replay MUST remain labelled invalid and MUST NOT enter normal bidder
  comparisons. Accepted-commitment validation MUST cover static schedule,
  battery compatibility, and charge/discharge reserve power headroom without
  using the realized activation trajectory; activation input validation remains
  a separate evaluation-time gate.
- **FR-037**: A plan that passes static accepted-commitment validation MAY
  experience dynamic stored-energy saturation or non-delivery under the
  realized activation trace. Such a run MUST remain a successful settled
  evaluation, MUST price only delivered activation energy, MUST apply only an
  explicitly configured non-delivery penalty, and MUST be reported as outside
  the initial reference-parity domain rather than as reference-compatible.

### Reference Implementation Requirements

- **Source paths**:
  - `baselines/robust_storage_bidding/code/01_datastruct.jl` for parameters,
    efficiencies, time resolutions, and sign conventions
  - `baselines/robust_storage_bidding/code/02_model.jl` for market-decision
    indexing and fixed-decision SOC helpers
  - `baselines/robust_storage_bidding/code/03_backtest_save.jl`, especially
    `bt_simulation`, for realized replay, activation-energy accounting, and
    daily output fields
  - `baselines/robust_storage_bidding/code/04_parse_results.jl` for reported
    field meanings and aggregate metrics
  - `baselines/robust_storage_bidding/results/result_overview.xlsx` for
    supporting published-result context only
- **Behavior to preserve**: Fixed `x0`/`xr` meanings and indexing; battery
  efficiency and SOC equations within the shared supported domain; realized
  activation-energy accounting; daily profit, energy, SOC, and power field
  meanings; explicit experiment configuration.
- **Behavior to improve or drop**: Implicit working-directory assumptions,
  mutable or machine-specific output paths, runtime solver coupling, rounded
  values without declared comparison policy, and missing fine-grained lineage
  are not library behavior to preserve. The reference tree remains read-only.
- **Parity evidence**:
  - pinned commit:
    `7e44738bb30e5c8204efe40103b9be4c2203685c`
  - generation command from the reference `code/` directory:
    `julia --project=. 12.jl 2023-06-18`
  - original generated result:
    `baselines/robust_storage_bidding/results/02/2023-06-18.json`
  - original result SHA-256:
    `8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`
  - configuration: restriction model, `xi_EU`, energy payment enabled,
    intraday trading disabled, charge/discharge efficiency `0.92`, 96
    quarter-hour planning intervals, `1/360` hour activation resolution, six
    four-hour FCR commitments, and three-decimal result rounding
  - expected values: objective value/bound EUR `11.028`; realized total profit
    EUR `10.749`; day-ahead profit EUR `0.168`; combined FCR profit EUR
    `10.581`; intraday profit EUR `0.000`; reference fields named `soc_*`
    represent stored energy, with initial/terminal values `53.328`/`55.482`
    kWh and realized minimum/maximum values `23.495`/`58.579` kWh;
    charge/discharge energy `46.122`/`37.056` kWh; realized minimum/maximum
    reference power `-14.385`/`31.826` kW; reported zero bilinear violations
  - solve time and the reported bilinear-violation count are provenance only,
    not parity assertions; the restriction run does not export an independent
    bilinear-slack evaluation

### Key Entities

- **Fixed Bid Plan**: Bidder-neutral envelope that identifies the schedule
  producer, information cutoff, status, optional optimization metadata,
  diagnostics, and references to exactly one hourly energy schedule and one
  four-hour FCR schedule.
- **Reference Mapping Declaration**: Versioned statement of source fields,
  signs, units, prices, time interpretation, index mapping, conversions, and
  source fingerprints used to translate a reference case.
- **Reference Settlement Profile**: Explicit accounting selection that adds
  realized activation-energy treatment and exposes component reconciliation
  without altering the default Feature 010 profile.
- **Daily Evaluation Report**: Immutable physical, economic, diagnostic, and
  lineage summary for one fixed plan and one daily activation scenario.
- **Golden Reference Fixture**: Normalized, immutable reference inputs,
  expected aggregate outputs, external activation-data reference, provenance,
  precision policy, and redistribution classification used by offline
  validation.
- **Parity Comparison**: Field-level outcome recording comparable fields,
  expected and actual values, mappings, tolerances, pass/fail status, and
  unavailable evidence.

### Dependency and Environment Requirements

- **Core dependencies**: Existing Open Energy Lab market, control, simulator,
  battery, schedule, replay, settlement, serialization, and fingerprint
  capabilities; no new unconditional heavyweight dependency.
- **Optional dependencies**: Julia, JuMP, and Gurobi are allowed only for an
  explicit reference-fixture generation or refresh workflow and are not
  required for feature use or routine validation.
- **External services**: None for routine validation. A researcher separately
  downloads the reference activation dataset from the documented upstream
  release before selecting the full-reference check; the library performs no
  acquisition.
- **Hardware assumptions**: CPU-only ordinary development and continuous
  integration environments for routine validation; no GPU, SLURM, or
  commercial solver is required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Researchers can evaluate manual, heuristic, future robust, and
  future TPM-produced plans through one fixed-plan boundary without changing
  the replay or settlement path.
- **SC-002**: The hand-calculable oracle starts from explicit reference-form
  `x0`/`xr` decisions, independently reproduces their mapped library schedules
  and every declared physical and economic component, and agrees within the
  library's `1e-6` internal absolute tolerance.
- **SC-003**: After the user installs the validated upstream activation
  dataset, the assembled 2023-06-18 case contains exactly 24 hourly energy
  decisions, six four-hour FCR decisions, 96 quarter-hour checkpoints, and
  8,640 ten-second activation intervals.
- **SC-004**: The explicitly selected full-reference evaluation is
  source-precision-compatible with every supported 2023-06-18 aggregate from
  the pinned reference result under field-specific bounds derived from the
  three-decimal `x0`/`xr` and output precision; the report separately records
  exact rounded matches, and objective metadata is not compared with realized
  profit.
- **SC-005**: Two evaluations of identical validated inputs produce identical
  ordered traces, reports, diagnostics, and fingerprints.
- **SC-006**: Day-ahead, FCR capacity, activation-energy, and penalty
  components reconcile to total profit within `1e-6`, and the applicable FCR
  subcomponents reconcile to the reference combined FCR profit under the
  reference precision policy.
- **SC-007**: All routine checks pass without Julia, Gurobi, a solver license,
  network access, notebooks, an initialized reference submodule, or the
  externally downloaded activation dataset.
- **SC-008**: Existing Feature 010 default cases retain their expected public
  results and fingerprints when the reference-result profile is not selected.
- **SC-009**: Every reference-derived fixture exposes its pinned commit,
  generation command, original digest, mapping version, comparison policy, and
  redistribution status to a reviewer.
- **SC-010**: Published parity reporting names every compared and unavailable
  field and makes no claim of complete ten-second reference parity without a
  separate detailed reference artifact.
- **SC-011**: A researcher can follow the documentation to download, validate,
  place, and use the upstream activation dataset without modifying library
  source code or exposing credentials.
- **SC-012**: Every statically invalid accepted commitment yields a reproducible
  failed report with no valid profit, no diagnostic replay can be mistaken for
  a successful bidder result, and dynamic stored-energy saturation after valid
  preflight remains distinguishable as a settled non-delivery outcome.
- **SC-013**: For every bid plan containing activation in both directions,
  requested and delivered upward/downward FCR energy remain independently
  reproducible, their signed net values reconcile with the directional totals,
  and throughput remains unaffected by directional cancellation.
- **SC-014**: For the required 8,640-interval ordinary-day evaluation, each
  instrumented validation, replay, aggregation, comparison, and fingerprinting
  stage performs at most two complete iterations over its primary interval
  collection and retains no superlinear collection. Validation MUST use
  operation counts rather than wall-clock thresholds.

## Assumptions

- The primary users are researchers comparing storage bidding methods and
  maintainers validating the shared evaluation environment.
- Feature 010's existing schedules, battery physics, replay, and settlement
  contracts remain the authoritative library foundation.
- The generated 2023-06-18 JSON and its recorded digest are available during
  planning so that a normalized library-owned fixture can be prepared.
- The full activation dataset used by the reference run is not redistributed
  by Open Energy Lab; users obtain it directly from the upstream location named
  by the pinned reference project and place it according to library
  documentation.
- Reference decisions and aggregate values rounded to three decimals are
  sufficient for an initial bounded, source-precision-compatible parity claim,
  not for unsupported exact rounded equality; detailed Julia step trajectories
  and unrounded decisions are not assumed to exist.
- The successful Julia/Gurobi execution is the initial fixture-generation
  event. Re-execution is required only for an intentional fixture refresh or
  optional parity-maintenance check.
- The exact placement of additive library types and functions will be decided
  during planning while keeping new reusable code under `src/open_energy_lab`.
- Feature 013 will own reference bid optimization; later features will own TPM
  dataset construction and bid selection.
