# Data Model: FCR Rolling Backtest Parity

All public entities are frozen dataclasses with tuple or read-only mapping
fields. Builders validate before construction. `to_dict()` returns detached,
JSON-compatible values with explicit units, ISO-8601 UTC timestamps ending in
`Z`, declared semantic versions, and fingerprints. Floats must be finite;
fingerprint-bearing decimals use the existing canonical numeric policy rather
than platform `repr` as an unstated format.

## 1. Data and policy descriptors

### `RollingFCRDataDescriptor`

Identifies one price or activation data family without loading it.

- `descriptor_id`, `kind`, `schema_version`
- `unit`, `sign_convention`, `timezone`, `temporal_resolution`
- interval-bound and hourly/four-hour/ten-second mapping rule IDs
- source organization/document identifiers and acquisition cutoff
- content SHA-256, normalized-data fingerprint, provenance
- `descriptor_fingerprint`

`kind` is one of `day_ahead_price`, `fcr_capacity_price`, or
`regulation_activation`. Paths, credentials, network locators, and activation
sample values are excluded from semantic identity. A descriptor with the wrong
unit or mapping is rejected before orchestration.

### `AcceptedBidPolicy`

- `policy_id`
- `kind`: `assumed_accepted` or `evidence_backed_accepted`
- explicit assumption statement and fingerprint for `assumed_accepted`
- individual acceptance `evidence_descriptor` for `evidence_backed_accepted`
- `reject_system_volume_as_individual_evidence=True`
- `policy_fingerprint`

Every manifest has exactly one policy. The reference profile uses the explicit
assumption kind. A system-wide contracted-volume descriptor can never satisfy
the individual-evidence kind.

### `DeliveryDateClassification`

- `delivery_date`
- `execution_role`: `included`, `warm-up`, `close-out`, or `excluded`
- `comparison_eligible`
- ordered reason codes
- `classification_fingerprint`

Dates are strictly ordered and unique. Only `included` may be comparison
eligible. Excluded dates still receive envelopes; warm-up and close-out dates
are not silently included in comparison aggregates.

### `RollingFCRNumericPolicy`

- solver and objective-comparison tolerances inherited from the named Feature
  013 `RobustFCRSolvePolicy`
- `state_carry_policy`: `source_three_decimal` or `native_full_precision`
- decimal places, rounding mode, signed-zero rule, closed-interval rule
- state-link and aggregate reconciliation tolerances
- source decision/objective/bound precision policies
- `numeric_policy_fingerprint`

The 08:00 source executable accepts only `source_three_decimal`. Midnight
carry-over supports either value, and the choice changes semantic identity.

### `RollingFCRExperimentProfile`

- stable executable `profile_id`
- source script/result-directory identities and digests
- formulation kind: `relaxation`, `restriction`, or `arbitrage_only`
- bidding time and horizon/indexing rule
- state mode: `reset`, `midnight_carry`, or `rolling_0800`
- predecessor decision-fixing and finalization rules
- allowed state-carry policies
- feasible-incumbent continuation policy
- plan classification: `robust_candidate`, `diagnostic_non_robust`, or
  `arbitrage_only`
- paper experiment and workbook column crosswalk with reconciliation status
- `profile_fingerprint`

Exactly the five versioned profiles in `research.md` are supported in v1.

## 2. Study definition

### `RollingFCRBatteryBinding`

Bridges Feature 013 battery optimization inputs and Feature 012 replay inputs.

- Feature 013 `RobustFCRBatteryParameters`
- nominal `capacity_kwh` required by Feature 012
- component identity and replay fingerprint
- explicit charge-positive mapping and efficiency lineage
- `binding_fingerprint`

The stored-energy limits and efficiencies must match across both contracts.
A fresh simulator battery component is created per replay segment; the mutable
component is never stored as semantic evidence.

### `RollingFCRStudyManifest`

The complete immutable study identity:

- `schema_version`, `study_id`, one `RollingFCRExperimentProfile`
- ordered `DeliveryDateClassification` tuple
- day-ahead, FCR-price, and activation descriptors
- battery binding, Feature 013 uncertainty and terminal-rule contracts
- Feature 013 solver policy, settlement profile, accepted-bid policy, numeric
  policy
- decision and information cutoff rules
- reset/carry/08:00 semantics, predecessor-date rule, failure and aggregation
  policies
- resume policy and caller-state declarations
- reference revision and normalized-fixture lineage
- `manifest_fingerprint`

One manifest contains exactly one executable profile. All ordinary delivery
dates must have valid 24/96/6 time contracts. Every descriptor range covers its
declared executed dates. Activation is described here but never embedded.

### `RollingFCRDayInput`

Bidder-visible input for one date:

- manifest and profile fingerprints, date classification
- one ordinary Feature 013 bidding problem or the inputs needed to derive it
- full-precision 24 hourly and six four-hour prices with fingerprints
- reset or carried initial stored energy and state-link identity
- decision cutoff and information cutoff
- predecessor identities/fixings where required
- `day_input_fingerprint`

This entity cannot contain activation samples, replay reports, settlement,
future states, source comparisons, or credentials. The 08:00 solve request is
derived only after the predecessor's causal cutoff state exists.

## 3. Rolling optimization

### `RobustFCRAcceptedDecisionFixings`

- predecessor plan/problem/result fingerprints
- signed source and public frame identities
- 16 fixed hourly energy decisions with indices/timestamps
- four fixed FCR decisions with block indices/timestamps
- mapping rule and full-precision values
- `fixings_fingerprint`

Values must be exactly the accepted predecessor decisions; displayed
source-rounded fixture values are never silently promoted to exact native
fixings.

### `RobustFCRRollingBiddingProblem`

- base daily problem identity and current 24/96/6 market inputs
- extended time contract and `K_lower`
- predecessor price tail and accepted decision fixings for `rolling_0800`
- initial state at previous-day 08:00 and derived current-midnight robust bounds
- formulation/terminal/solver/numeric profiles
- source-positive-discharge to public-charge-positive mapping
- `rolling_problem_fingerprint`

For `rolling_0800`, validation requires 40 hourly, 160 quarter-hour, ten FCR
blocks, `K_lower=-63`, and exact 16/4 fixings. For `arbitrage_only`, it requires
a 24-hour frame and model-level zero FCR decisions. These contracts are
additive and cannot construct a non-24/96/6 `RobustFCRBiddingProblem`.

### `RobustFCRRollingSolveResult`

- problem/profile/formulation identity
- solve/termination/incumbent status, objective, upper bound, gap
- objective components including separately reported fixed-tail constant
- runtime/backend metadata outside semantic identity
- complete current-day decisions and extended-frame audit evidence
- feasibility slacks and independent family residuals
- plan classification and optional current-day `FixedFCRBidPlan`
- diagnostics and `semantic_fingerprint`

Restriction plan emission follows Feature 013's deployability policy. A
relaxation may expose only an explicitly diagnostic non-robust plan. The
arbitrage-only plan has six exact zero FCR blocks. All public energy decisions
are charge-positive.

## 4. Physical replay and state links

### `FCRAcceptedPlanSegment`

- unchanged parent `FixedFCRBidPlan` fingerprint
- half-open `[start_utc, end_utc)` segment
- sliced energy/FCR schedule fingerprints
- accepted-bid and market-context fingerprints
- `segment_fingerprint`

Segments partition the original plan without gaps or overlaps. They do not
claim that the accepted plan changed.

### `FCRSegmentedEvaluationReport`

- manifest/date/plan/activation identities
- ordered Feature 012 daily/partial report fingerprints
- initial, cutoff, terminal stored energy
- reconciled requested/delivered energy, directional FCR energy, throughput,
  saturation, settlement components, and realized profit
- contributor segment identities and reconciliation residuals
- diagnostics and `semantic_fingerprint`

Every segment is evaluated through Feature 012. Aggregation sums only additive
metrics, derives extrema from segment extrema, and verifies the prior terminal
equals the next initial within policy tolerance. It contains no new battery or
settlement equation.

### `RollingFCRStateLink`

- predecessor/successor date, plan, replay, and segment fingerprints
- handoff kind: `midnight`, `cutoff_0800`, or `caller_supplied`
- observation cutoff and activation fingerprint through that cutoff
- full-precision replay checkpoint kWh
- carried kWh, rounding policy/evidence, and closed source interval
- modeled terminal reconciliation and tolerance result
- continuity-segment identity
- `state_link_fingerprint`

A caller-supplied link begins a new continuity segment. A coupled successor
cannot start without a valid link. Future activation identities or settlements
are forbidden.

## 5. Immutable date lifecycle

### `RollingFCRDayRevision`

- monotonically increasing `revision_number`
- `revision_kind`: `original`, `optimization_only`, `provisional`, or
  `finalized`
- creation cause and predecessor/successor identities
- input/problem/solve/plan/activation/replay/settlement/state fingerprints, or
  explicit unavailable evidence with ordered reason codes
- initial, realized cutoff, handed-off cutoff, modeled terminal, realized
  terminal, and carried energy, each with applicability
- complete 24 hourly and six FCR decisions when an incumbent exists
- solver evidence including absolute/relative gap and runtime metadata,
  residual audit, feasibility slacks, diagnostics
- realized metrics when available
- source-comparison outcomes when requested
- `revision_fingerprint`

Revisions never overwrite prior evidence. A finalized revision references the
unchanged original plan plus the successor-triggered tail replay.

### `DeliveryDateRecordEnvelope`

- manifest/profile/date/predecessor identities
- date classification and continuity segment
- ordered immutable revisions
- terminal lifecycle status:
  `excluded`, `initialization_only`, `optimization_only`, `provisional`,
  `finalized`, `failed`, `blocked_by_predecessor`, or `unfinalized`
- ordered diagnostics and comparison summary
- `envelope_fingerprint`

Exactly one envelope exists per requested date, in manifest order. Status and
revision invariants:

- `excluded`: no solve/replay revision.
- `initialization_only`: bootstrap evidence exists but is ineligible for paired
  comparison.
- `optimization_only`: a solve exists and activation-dependent evidence is
  unavailable.
- `provisional`: cutoff replay exists but successor finalization does not.
- `finalized`: all profile-required revisions and reconciliations pass.
- `failed`: the date's own required solve/evaluation failed.
- `blocked_by_predecessor`: execution did not occur because a coupled link is
  absent/invalid.
- `unfinalized`: a valid original/provisional edge awaits a successor.

State transition overview:

```text
excluded ----------------------------------------------------> excluded

requested -> original solve -> optimization_only
                         |             |
                         | activation  | independent profile complete
                         v             v
                    provisional ----> finalized
                         |
                         | no close-out successor
                         v
                    unfinalized

requested -> own error -------------------------------------> failed
requested -> invalid/missing coupled predecessor -----------> blocked_by_predecessor
```

`initialization_only` is a role/status overlay for the first 08:00 bootstrap;
its successor may still consume its accepted decisions and cutoff state.

## 6. Continuity, resume, and aggregation

### `ContinuitySegment`

- segment ID and ordered member dates
- origin: `manifest_initial`, `valid_predecessor`, or `caller_supplied`
- first state-link fingerprint and predecessor relation
- terminal state-link fingerprint when complete
- completeness and diagnostics
- `segment_fingerprint`

Parity assertions never cross a caller-supplied or otherwise uncertified gap.

### `RollingFCRResumeEvidence`

- prior result semantic fingerprint
- manifest/profile fingerprints
- ordered reused envelope/revision fingerprints
- last continuity/state-link identity
- exact compatibility checks and ordered diagnostics
- status: `compatible` or `incompatible`
- `resume_fingerprint`

Resume is all-or-nothing for reused evidence. Volatile runtime does not affect
semantic compatibility, but changed policies, inputs, date ordering, source
artifacts, activation descriptors, or state links do.

### `AggregateMetricEvidence`

- metric name, unit, aggregation rule
- eligible, contributing, and omitted dates with reasons
- source revision/report fingerprints
- value and reconciliation residual
- status: `complete`, `partial`, or `unavailable`
- `aggregate_fingerprint`

Optimization objective, best bound, realized settlement, realized profit,
directional FCR energy, and throughput are distinct metric records. No missing
date receives a zero value.

### `RollingFCRStudyResult`

- schema/manifest/profile identity
- every requested date envelope in order
- continuity segments and state links
- exact lifecycle/status counts reconciled to the envelopes
- aggregate metric evidence
- study completeness: `complete`, `partial`, `failed`, or `incomplete`
- resume lineage, ordered diagnostics, and optional comparisons
- runtime metadata outside semantic identity
- `semantic_fingerprint`

Loading validates the schema, recomputes every nested semantic fingerprint,
and recomputes the top-level identity before the result can be resumed.

## 7. Reference evidence and comparison

### `RollingFCRReferenceFixture`

- fixture/schema identity and fingerprint
- pinned revision and source/runtime/toolchain provenance
- explicit raw input manifest with digest/status/redistribution entries
- profile crosswalk and known discrepancies
- four-date study window and roles
- normalized inputs, solve records, delivery evidence, and lifecycle evidence
- source numeric/rounding policies and unavailable fields
- Feature 013 original-versus-rerun semantic cross-check
- `fixture_fingerprint`

No raw log, complete activation samples, path, credential, or machine identity
is retained.

### `RollingFCRReferenceFieldResult`

- field path and compared units
- native and source values/intervals/evidence fingerprints
- delta and allowed numerical/source-precision envelope
- one required detailed outcome
- reason codes and `field_result_fingerprint`

### `RollingFCRReferenceComparison`

- fixture/manifest/result identities
- ordered field results by profile/date/category
- joint latent certificate identities where applicable
- per-date and per-profile summaries
- canonically ordered distinct field-evidence bases used for the summary
- overall compatibility: `compatible`, `incompatible`, or `incomplete`
- diagnostics and `comparison_fingerprint`

Field results are authoritative. Overall `compatible` requires all mandatory
fields to have a compatible outcome and complete required lifecycle evidence;
`incompatible` requires at least one proven incompatible field; otherwise the
result is `incomplete`.

## 8. Fingerprint boundaries

Included in semantic identity:

- schema and equation versions, ordered dates, roles, profile and mappings;
- all normalized input values and descriptors;
- battery, uncertainty, terminal, solver, numeric, acceptance, settlement,
  failure, resume, and aggregation policies;
- decisions, states, residual/slack evidence, replay/settlement metrics;
- predecessor, activation-through-cutoff, segment, revision, and continuity
  identities; and
- comparison policy/outcomes and source artifact digests.

Excluded from semantic identity but reportable:

- wall-clock duration, CPU time, host, process ID, memory, solver log text;
- local filesystem paths, environment variables, credentials, and licenses;
- serialization timestamp and output filename.

Any included change produces a new fingerprint. Runtime-only changes may alter
the persisted byte digest but not the semantic fingerprint.
