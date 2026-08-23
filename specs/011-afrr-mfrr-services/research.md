# Phase 0 Research: BESS aFRR and mFRR Services

**Feature**: `011-afrr-mfrr-services`  
**Date**: 2026-08-23  
**Status**: Complete; no unresolved clarifications

## Decision 1: Add restoration modules; do not generalize FCR contracts in place

**Decision**: Implement new restoration-specific artifact, activation, control,
replay, and settlement modules. Reuse general primitives and implementation
patterns, but leave Feature 010's `MarketDataArtifact`,
`RegulationActivationTrace`, `FCRCapacitySchedule`, `MultiRateTimeContract`,
`StackedServiceReplayRequest`, and `SettlementBreakdown` unchanged.

**Rationale**: Those existing types are deliberately closed around A44/A81,
dimensionless FCR activation, symmetric PT4H commitments, and FCR-named result
fields. Widening them would change accepted inputs, fingerprints, serialization,
or byte-stable fixtures and would violate FR-001. `CanonicalInterval` and
`apply_power_request` are product-neutral and safe to reuse.

**Alternatives considered**:

- Add optional aFRR/mFRR fields to Feature 010 classes: rejected because absent
  versus zero fields and fingerprints would change.
- Create one generic reserve type immediately: rejected because it would make
  FCR, aFRR, mFRR SA, and mFRR DA easier to substitute accidentally.
- Fork battery physics: rejected because the current transition already owns
  power, SOC, and efficiency enforcement correctly.

## Decision 2: Use the official RTE v5.2 production profile with a v5 path

**Decision**: The RTE adapter uses catalog version `5.2` and these explicit
production interfaces:

- OAuth token: `POST https://digital.iservices.rte-france.com/token/oauth/`
  with HTTP Basic client credentials supplied only at runtime
- aFRR: `GET /open_api/balancing_energy/v5/standard_afrr_data`
- mFRR: `GET /open_api/balancing_energy/v5/standard_mfrr_data`
- bounded `start_date` and `end_date` query parameters in ISO 8601
- bearer access token only in the transient Authorization header

The catalog version and URL path version are recorded independently because the
catalog is 5.2 while the stable path segment is `v5`.

**Rationale**: Production access was verified with caller-owned credentials.
RTE's [Balancing Energy catalog](https://data.rte-france.com/catalog/-/api/market/Balancing-Energy/v5.2)
identifies version 5.2, and its [v5.2 user guide](https://data.rte-france.com/catalog/-/api/doc/user-guide/Balancing+Energy/5.2)
defines the resource paths, date parameters, media types, roots, fields, and
PT15M output. RTE's [OAuth guide](https://data.rte-france.eu/documents/20182/22648/EN_GuideOauth2_v5.1.pdf/54d3d183-f20f-4290-9417-bcae122b9e46)
documents the token endpoint and Basic-to-bearer exchange. Tokens are short
lived and never satisfy a persistable request contract.

**Alternatives considered**:

- Accept an already-created bearer token as a request field: rejected because
  it is secret, short lived, and would contaminate identities and logs.
- Use a third-party RTE client: rejected because standard-library HTTP plus an
  injected transport meets the bounded requirements without a core dependency.
- Treat catalog 5.2 as path `/v5.2/`: rejected because the verified production
  resources use `/v5/`.

## Decision 3: Pin the real RTE demonstrations to verified UTC periods

**Decision**: Use these source periods as implementation staging gates:

| Profile | Requested UTC period | Returned local period | Resolution | Records |
|---|---|---|---|---:|
| aFRR | `[2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)` | `[02:00,03:00)` Europe/Paris (+02:00) | PT15M | 4 |
| mFRR | `[2026-08-15T10:15:00Z, 2026-08-15T10:30:00Z)` | `[12:15,12:30)` Europe/Paris (+02:00) | PT15M | 2 directional rows |

The 2026-08-23 feasibility response-byte SHA-256 values were
`d2496d713c7f217ff76487db2aba0b7a49479861118bea61ca3c001fbbfe2eb3`
for the aFRR hour and
`ce9d3c3d694a78776e5bdb188239f9b2ed4b711e3c389d0e89c8a47e5391d1a1`
for the mFRR quarter. These are planning evidence, not canonical artifact
fingerprints. Staging must reacquire, record retrieval time, normalize, and
publish through the final contract.

The selected mFRR downward row contains `total_requested_volume_SA=357`,
`total_satisfied_need_SA=300`, and `clearing_price=64.83`. Its upward row is
retained separately and contains null volume fields. DA is absent and remains
absent.

**Rationale**: The periods directly satisfy SC-001 and SC-002 and avoid
inventing sparse direct activation. UTC request identity and local source labels
are both auditable.

**Alternatives considered**:

- Stage the whole mFRR day: rejected for the minimal reference fixture because
  a bounded quarter proves the required SA semantics with less restricted data.
- Search until a DA record appears: rejected because DA is optional and sparse.
- Persist feasibility response bodies: rejected; planning needed only sanitized
  field, count, and digest evidence.

## Decision 4: Parse source fields exactly and preserve their distinct meanings

**Decision**: The aFRR parser accepts root `picasso`, root resolution `PT15M`,
and list `picasso_mesures`. Each row preserves:

- `upward_afrr_requested_need` / `downward_afrr_requested_need`
- `upward_afrr_activated_volume_for_fr` /
  `downward_afrr_activated_volume_for_fr`
- `upward_afrr_activated_volume_in_fr` /
  `downward_afrr_activated_volume_in_fr`
- direction-compatible weighted-average activated-for-France prices
- row start and end

The mFRR parser accepts root `mari`, root resolution `PT15M`, and list
`mari_mesures`. It preserves `direction`, total SA/DA requested and satisfied
need, SA/DA locally activated volume, clearing and current/previous settlement
prices, the nested requested-volume-by-price entries, submitted/filtered offer
volumes, and row bounds. Unknown fields may be retained as source extensions but
never satisfy a known canonical field silently.

**Rationale**: RTE's [balancing definitions](https://www.services-rte.com/en/view-data-published-by-rte/balancing.html)
distinguish area need, activated for France, activated in France, SA clearing
price, DA settlement prices, and submitted/activated bids. They are not
interchangeable quantities.

**Alternatives considered**:

- Flatten aFRR fields to one volume and one price: rejected as semantic loss.
- Net upward and downward records: rejected because direction and opposing
  activity are meaningful and can be temporally ambiguous.
- Treat mFRR requested, satisfied, and locally activated volumes as aliases:
  rejected because each answers a different question.

## Decision 5: Model source absence, source null, and numeric zero separately

**Decision**: Each requested canonical series has an availability state
(`present`, `present_with_nulls`, `source_absent`, or `not_requested`). Each
observation has a value state (`value`, `source_null`, or `field_absent`) and a
numeric value only for `value`. A numeric zero is stored as value `0.0`, never
as null or absence.

**Rationale**: The verified mFRR response contains real nulls alongside numeric
values and emits both directions separately. Financial and scenario decisions
depend on knowing whether zero was observed or data was unavailable.

**Alternatives considered**:

- Omit null observations: rejected because coverage would appear complete.
- Convert null to zero: rejected because it fabricates source meaning.
- Use NaN: rejected because canonical JSON forbids non-finite numbers and NaN
  does not distinguish the reasons for missingness.

## Decision 6: Use one immutable artifact per source acquisition and a reference-only bundle

**Decision**: A `RestorationMarketArtifact` contains normalized series from
exactly one source operation. It has distinct normalized-content and full
artifact fingerprints, source evidence, request identity, series manifest,
lineage, and redistribution policy. A `RestorationStudyBundle` references
artifact identity/fingerprint plus selected series IDs; it copies no
observations and adopts the strictest referenced policy.

**Rationale**: This preserves independent ownership, version, temporal,
transformation, and distribution meaning. It also lets a study combine RTE
activation context with a separately acquired ENTSO-E series without creating a
false merged source.

**Alternatives considered**:

- One artifact containing RTE and ENTSO-E rows: rejected by FR-012.
- Join observations by timestamp in the bundle: rejected because the bundle is
  provenance composition, not a semantic data transformation.
- Reuse Feature 010's `MarketDataArtifact`: rejected because its exact profile
  and evidence are closed to A44/A81.

## Decision 7: Keep ENTSO-E complementary and evidence-gated

**Decision**: Feature 011 introduces no new ENTSO-E restoration acquisition
profile in its first release. Its only supported complementary composition is
an existing, time-compatible Feature 010
`fr-day-ahead-symmetric-fcr-v1` artifact, with the A44 `day_ahead_price` series
selected by fingerprint through the study bundle. The closed A44/A81 profile,
including its existing fetch/refresh/offline lifecycle, remains unchanged. A
future ENTSO-E restoration profile may be added only after its document,
process, product, direction, unit, resolution, and coverage pass the same
semantic gate.

**Rationale**: The [ENTSO-E Transparency Platform REST documentation](https://documenter.getpostman.com/view/7009892/2s93JtP3F6)
offers multiple capacity, bid, activation, exchange, and price query shapes,
but matching timestamps do not establish matching semantics. RTE is the
verified primary source, and the reference restoration behavior does not need
an ENTSO-E fallback.

**Alternatives considered**:

- Require an ENTSO-E restoration fixture for completion: rejected because no
  exact compatible profile has been proven for the selected periods.
- Use A83/A84 or another activation document as an asset command: rejected
  without an exact resolution and semantic proof.
- Make ENTSO-E an automatic fallback: rejected because source substitution
  would be invisible and irreproducible.

## Decision 8: Derive BESS requests only through a fixed allocation mapping

**Decision**: A `DerivedSimulationMapping` references exact source artifact and
series fingerprints and applies:

`requested_bess_kw = requested_area_mw * 1000 * asset_allocation_fraction`

The fraction is finite, fixed for the whole scenario, and in `[0,1]`. It may
not normalize against the period maximum, vary by interval, or clip. The
builder rejects any request exceeding its direction-compatible commitment and
labels all outputs `derived_simulation`.

For the recorded demonstrations, use fraction `0.001`. This maps the verified
aFRR upward needs to 425, 315, 290, and 345 kW in chronological order, and the
selected downward mFRR SA request to 357 kW. The activated/satisfied quantities
remain comparison observations.

**Rationale**: A fixed fraction is transparent and hand-verifiable while
preserving the crucial statement that area aggregates are not BESS commands.

**Alternatives considered**:

- Normalize to battery nameplate: rejected because it erases the source's
  absolute scale and changes with the requested period.
- Clip to commitment: rejected because it hides an invalid scenario.
- Derive from activated volume or price: rejected because the specification
  explicitly selects requested need/volume as the driver.

## Decision 9: Represent aFRR as signed interval-average requested power

**Decision**: `AFRRActivationTrajectory` contains complete non-overlapping
half-open samples with signed charge-positive `requested_balancing_power_kw`:
negative for upward/discharge, positive for downward/charge. Values are
interval averages integrated directly. No interpolation or upsampling occurs.
Any mapped RTE interval with simultaneous nonzero upward and downward need is
rejected as ambiguous.

**Rationale**: PT15M area aggregates cannot reveal within-quarter automatic
control. Treating them as interval averages supports a reproducible derived
energy scenario without pretending to reproduce a high-frequency AGC signal.
Synthetic or separately sourced traces provide ramp and tracking resolution.

**Alternatives considered**:

- Interpret values as end-of-interval setpoints: rejected because energy and
  ramp meaning would depend on an unstated hold rule.
- Net simultaneous directions: rejected because ordering is unknowable.
- Upsample PT15M values: rejected because it fabricates operational detail.

## Decision 10: Represent mFRR as typed piecewise scheduled/direct events

**Decision**: Each `MFRRActivationEvent` contains a separate SA/DA identity,
direction, requested start, delay, linear ramp-up, full-power hold, linear
ramp-down, and non-negative requested magnitude. Requested energy is the exact
integral of the trapezoidal profile. Complete event intervals may not overlap.

The recorded SA scenario maps the selected downward RTE quarter to a simulated
event starting at `2026-08-15T10:15:00Z` with zero delay, zero ramp-up, 15-minute
hold, zero ramp-down, and 357 kW requested power. This is a declared modelling
assumption, not an observed activation order. Synthetic cases exercise
non-zero delay and ramps in both directions and DA identity.

**Rationale**: mFRR is event-oriented, and SA/DA settlement fields differ.
Explicit segments make start, duration, ramp, energy, and overlap validation
deterministic.

**Alternatives considered**:

- Convert events to the aFRR trajectory type at the public boundary: rejected
  because it would erase event and SA/DA identity.
- Accept requested energy as an input: rejected because power shape and energy
  could conflict.
- Sum or prioritize overlapping events: rejected for the first release.

## Decision 11: Keep commitments and no-lookahead baselines in control

**Decision**: Restoration control owns immutable directional commitment
schedules and deterministic baseline builders. For maximum discharge
`D`, maximum charge `C`, upward commitment `U`, and downward commitment `L`,
accepted baseline power must satisfy:

`-D + U <= baseline_kw <= C - L`

Builders validate temporal alignment, usable SOC energy, efficiency, capability
ramp/activation-time/duration, and commitment eligibility. They do not receive
the activation trajectory/event sequence and cannot claim future feasibility or
optimal bidding.

**Rationale**: This extends Feature 010's headroom pattern while supporting
asymmetric directional capacity. It preserves the boundary between study
commitments and realized simulator performance.

**Alternatives considered**:

- Let replay silently reduce commitments: rejected because committed capacity
  and non-performance would become unauditable.
- Let the baseline builder inspect activations: rejected as lookahead.
- Add bidding optimization: rejected as explicitly out of scope.

## Decision 12: Reuse battery physics and add restoration capability in replay

**Decision**: A new immutable `RestorationCapability` supplies ramp,
activation-time, and supported-duration limits without altering
`BatteryComponent`. Restoration replay first determines the capability- and
commitment-constrained request for each integration interval, then calls
`apply_power_request` for power/SOC/efficiency enforcement. It attributes
delivery relative to the accepted baseline and records one deterministic
ordered cause set for every shortfall.

**Rationale**: Battery power, SOC, and efficiency are already well-tested.
Ramp, delay, duration, and product commitments belong to the service layer and
must not change Feature 010 battery serialization.

**Alternatives considered**:

- Add ramp fields to `BatteryComponent`: rejected because it changes a stable
  cross-feature contract.
- Clamp only after battery transition: rejected because requested versus
  capability-accepted versus physically delivered values would be conflated.
- Raise on every infeasible activation: rejected because valid replay must
  report realized non-performance while preserving physical bounds.

## Decision 13: Use separate aFRR and mFRR replay request/result types

**Decision**: Provide exact `AFRRReplayRequest` and `MFRRReplayRequest` types
with shared internal helpers only. A replay carries one energy baseline, one
product commitment, one matching activation input, battery/capability, and
tolerance. It cannot contain FCR or both restoration products. aFRR results are
sample/tracking oriented; mFRR results are event/timing oriented.

**Rationale**: Exact types provide the strongest cross-product substitution
gate and keep irrelevant result fields absent instead of zero or null.

**Alternatives considered**:

- One request with three optional activation fields: rejected because invalid
  combinations multiply and product-specific meaning becomes implicit.
- Reuse `StackedServiceReplayRequest`: rejected because it requires an FCR
  trace and FCR-specific multi-rate grid.

## Decision 14: Make settlement availability atomic and economics explicit

**Decision**: Physical replay always has its own validity. Settlement has
status `available` or `unavailable`. If any declared required price is missing,
ambiguous, direction-incompatible, product-incompatible, or uncovered, the
whole settlement and total are unavailable. Otherwise report day-ahead energy,
upward/downward capacity, upward/downward activated energy, penalty,
degradation proxy, gross, and net separately. Components for the unselected
product are absent.

Area weighted-average/clearing/settlement prices are allowed only through an
explicit `AreaPriceProxyMapping` referencing compatible source observations and
must label every financial result `scenario_proxy`, never `asset_invoice`.

**Rationale**: Partial totals and implicit zeros invite incorrect comparisons.
Capacity, delivered energy, non-performance, and throughput answer independent
questions and must reconcile exactly when settlement is available.

**Alternatives considered**:

- Set missing prices to zero: rejected because zero is a real price/value.
- Report a partial net total: rejected because it appears comparable to a full
  settlement.
- Settle requested rather than delivered activation: rejected because this
  simulator reports realized delivery and non-performance separately.

## Decision 15: Mirror Feature 010 acquisition security and immutable refresh

**Decision**: Use token-free frozen requests, injected synchronous transports,
bounded HTTPS bodies, exact media/schema checks, sanitized typed diagnostics,
and atomic publication. Retry only timeouts, connection interruptions, HTTP
408/429, and transient 5xx responses, for three total attempts including the
first. Honor a valid bounded `Retry-After`; fail authentication and permanent
client errors after one attempt. OAuth responses are never evidence or digests.

`fetch` creates one immutable artifact. `refresh` requires matching request
identity, compares normalized content, publishes nothing when unchanged, and
creates one predecessor-linked successor when changed. `offline` validates a
path without reading environment variables or importing networking adapters.

**Rationale**: The existing ENTSO-E adapter and artifact IO have tested patterns
for redaction, bounded retry, fsync, atomic replace, and immutable identity.
Reusing those patterns reduces security and determinism risk.

**Alternatives considered**:

- Automatic refresh on artifact load: rejected because offline behavior would
  depend on credentials/network/current source state.
- Cache OAuth tokens on disk: rejected as a credential leak.
- Retry all 4xx responses: rejected because permanent client failures should be
  diagnosed immediately.

## Decision 16: Keep dotenv handling in explicit example consumers

**Decision**: Package code accepts credentials as keyword-only values and never
loads `.env`. Example acquisition scripts may use a small strict loader that
allowlists `RTE_CLIENT_ID`, `RTE_CLIENT_SECRET`, and `ENTSOE_API_TOKEN`, prefers
already-exported environment values, performs no interpolation or environment
mutation, and never includes values in diagnostics. `.env.example` remains
safe and `.env` remains ignored.

**Rationale**: This supports convenient local acquisition without adding
`python-dotenv` or letting imports trigger secret access.

**Alternatives considered**:

- Add `python-dotenv` as a core dependency: rejected as unnecessary.
- Load `.env` during package import: rejected because offline workflows must not
  touch credentials.
- Persist a bearer token for repeatability: rejected; artifacts, not sessions,
  are the reproducibility boundary.

## Decision 17: Keep real fixtures restricted and distribution-excluded

**Decision**: Author-written synthetic JSON fixtures are redistributable and
routine. Normalized real RTE/ENTSO-E fixtures and any permitted raw sidecars are
marked `permitted_private_restricted`, excluded explicitly from wheel/sdist,
releases, public CI artifacts, mirrors, and external stores, and covered by a
visibility-change removal/reassessment gate. Digest-only raw evidence is the
default. Build-policy tests enumerate every restricted path.

**Rationale**: A private repository permits collaborator use but does not grant
redistribution rights. This preserves the Feature 010 policy and the source's
ownership.

**Alternatives considered**:

- Treat private Git storage as redistribution permission: rejected.
- Download fixtures on cache miss: rejected because routine validation would
  become credentialed, mutable, and network-dependent.
- Exclude only raw responses: rejected because normalized real observations may
  also carry redistribution restrictions.

## Decision 18: Validate synthetic behavior independently from real context

**Decision**: Use small equation-level synthetic cases for both directions,
zero activation, ramp, delay, duration, power, SOC, headroom, overlap,
settlement, unavailable settlement, penalty, and degradation. Use the verified
RTE fixtures only for parser/provenance/derived-scenario demonstrations. Run all
routine tests offline and preserve the complete Feature 010 suite and bytes.

**Rationale**: PT15M public aggregates cannot prove high-resolution automatic
tracking or an operational mFRR dispatch shape. Synthetic oracles can prove the
library equations without overstating the evidence in area-level data.

**Alternatives considered**:

- Validate physical behavior only against real RTE records: rejected because
  the records are aggregates, not asset commands.
- Execute the live API in routine CI: rejected because credentials, availability,
  revisions, and rate limits are external and mutable.
- Rely only on end totals: rejected because intermediate delivery, cause, SOC,
  headroom, timing, and energy conservation must be auditable.

## Resolved Technical Context

All source, dependency, storage, interface, numeric, security, fixture, and
validation choices required for Phase 1 are resolved. No implementation item
is marked `NEEDS CLARIFICATION`.
