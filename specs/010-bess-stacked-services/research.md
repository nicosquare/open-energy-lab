# Research: French BESS Stacked Services

**Feature**: `010-bess-stacked-services`  
**Date**: 2026-08-21  
**Status**: Complete for Phase 1 design

## Decision 1: Use a strict France ENTSO-E profile

**Decision**: Implement one profile for area `10YFR-RTE------C` and require all
three market series in the same completed artifact:

| Canonical series | Source document | Required semantics |
| --- | --- | --- |
| Day-ahead energy price | `A44` | France in/out bidding-zone domain, day-ahead process, `EUR/MWh` |
| Symmetric FCR contracted volume | `A81` | France control area, contracted process `A34`, daily market agreement `A01`, FCR business type `A95`, symmetric direction `A03`, `MW` |
| Symmetric FCR capacity price | `A89` | Same contracted FCR product identity and delivery interval as A81, source price in currency/MW/ISP converted explicitly to `EUR/MW/h` |

The query builder sends only the parameters supported for the applicable data
item. The parser then validates the returned document, process, business,
direction, area, market-agreement/product, currency, unit, interval, and
revision fields. A query parameter is not treated as proof that the response
has the requested meaning.

ENTSO-E's current material identifies `A81` and `A89` as contracted reserve
volume and price documents, `A95` as FCR, `A34` as contracted, `A01` as the
daily market-agreement type required by this query, and `A03` as a symmetric
direction. It also defines reserve volume per ISP and price as
currency/MW/ISP. The FCR Cooperation describes the relevant product as a
usually four-hour symmetric product, subject to daylight-saving shifts.

**Rationale**: This is the narrowest profile that satisfies the feature without
creating a generic European market framework. Strict returned-semantics checks
prevent a directional reserve, aFRR/mFRR, activated-balancing series, or a
differently settled price from being accepted merely because a query returned
data.

**Rejected alternatives**:

- `entsoe-py`: useful for generic analysis, but its dataframe boundary hides
  source-document revisions and raw-response evidence needed by this feature.
- RTE or regelleistung.net price fallback: useful future adapters, but not a
  substitute for the required ENTSO-E demonstration. Missing A81/A89 fails.
- A83/A84 as the FCR command: these represent activated quantities/prices and
  do not prove a 10-second normalized FCR request.

**Primary references**:

- [ENTSO-E REST API endpoint and HTTPS requirement](https://transparencyplatform.zendesk.com/hc/en-us/articles/15696677194644-Request-Endpoint)
- [ENTSO-E request parameters and UTC/DST guidance](https://transparencyplatform.zendesk.com/hc/en-us/articles/15696716612372-Request-Parameters)
- [ENTSO-E contracted reserve volume and price semantics](https://transparencyplatform.zendesk.com/hc/en-us/articles/12826309684756-Amount-and-Prices-Paid-of-Balancing-Reserves-Under-Contract-17-1-B-C)
- [ENTSO-E flow-direction codes](https://transparencyplatform.zendesk.com/hc/en-us/articles/15857071081620-flowDirection-direction)
- [ENTSO-E legal terms and open-data list](https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions)
- [ENTSO-E legacy-publication archive notice](https://transparencyplatform.zendesk.com/hc/en-us/articles/41986091964305-Archives-for-legacy-Transparency-Platform-publications)
- [ENTSO-E FCR product information](https://www.entsoe.eu/network_codes/eb/fcr/)

## Decision 2: Keep the token outside every persistable request object

**Decision**: Public acquisition calls accept a token as a keyword-only secret
separate from `EntsoeMarketDataRequest`. The request contains the endpoint
identity without a query string, area, period, profile, and source-window
policy. Only the private transport combines the token with an HTTPS request.
Raw transport exceptions never cross the boundary; they are converted to
typed diagnostics containing document type, sanitized window, attempt, HTTP or
acknowledgement classification, and retry outcome.

The default implementation uses Python's standard-library HTTPS client behind
an injected transport protocol. It does not log requests. Error formatting
never renders the full request URL, form body, headers, or raw exception. Test
transports accept the secret separately and use a sentinel scan over captured
output, exceptions, filenames, manifests, and sidecars.

**Rationale**: ENTSO-E requires a security token, and the documented GET form
places it in a query parameter. Separating request identity from transport
authentication makes accidental persistence and exception leakage testable.
It also allows deterministic failure and retry tests without network access.

**Rejected alternatives**:

- Token on a request dataclass or client instance: its `repr`, cache key, or
  exception context could leak the secret.
- Token-derived cache keys: credentials are not part of market-data identity.
- A mandatory third-party HTTP client: unnecessary for bounded synchronous
  acquisition and would widen the dependency surface.

**Primary references**:

- [ENTSO-E security-token process](https://transparencyplatform.zendesk.com/hc/en-us/articles/12845911031188-How-to-get-security-token)
- [ENTSO-E GET and POST request methods](https://transparencyplatform.zendesk.com/hc/en-us/articles/15696643163924-Request-Methods)

## Decision 3: Query enclosing local delivery days with bounded retries

**Decision**: A caller supplies a bounded UTC half-open period. The France
profile maps it to enclosing `Europe/Paris` delivery days and queries each
required series in deterministic one-delivery-day windows. Returned full
intervals are preserved; `requested_period` and `actual_covered_period` remain
distinct. This deliberately conservative windowing stays below documented
response limits and makes a failed source day easy to identify.

Each window has at most three total attempts. Retry only connection
interruptions, timeouts, HTTP 408/429, and 5xx responses. Authentication and
other permanent 4xx failures receive one attempt. A syntactically valid
`Retry-After` delay from zero through the fixed 120-second acquisition bound is
honored; malformed, negative, or over-bound values produce a sanitized
diagnostic and use no unbounded wait. Otherwise deterministic waits are one
second before attempt two and two seconds before attempt three. Clock and
sleeper are injected in tests.

All windows and all required series must fetch and validate before publication.
Optional raw sidecars are written to temporary sibling paths first, and the
canonical manifest is atomically replaced last. A failed operation publishes
neither a complete manifest nor a sidecar referenced by one.

**Rationale**: The API can return complete delivery days even for partial
queries, and its own guidance requires timezone awareness. Daily windows
provide simple all-or-nothing diagnostics while remaining practical for the
one-day demonstration and month-scale research periods.

**Rejected alternatives**:

- One request for an arbitrarily long period: harder to diagnose and more
  likely to hit changing API response limits.
- Concurrent source requests: not needed for the first release and complicates
  the shared token's rate-limit behavior.
- Jittered retries: this is a research acquisition boundary, so deterministic
  injected waits are easier to validate.

**Primary references**:

- [ENTSO-E query-size limits](https://transparencyplatform.zendesk.com/hc/en-us/articles/15854536354964-API-Query-Size-Limit)
- [ENTSO-E token rate limits](https://transparencyplatform.zendesk.com/hc/en-us/articles/12783148966036-API-Rate-Limit-Part-1)
- [ENTSO-E response period behavior](https://transparencyplatform.zendesk.com/hc/en-us/articles/15230327975828-Subscription-Service-Introduction-Guide-for-Data-Consumers)

## Decision 4: Parse XML defensively without adding a dependency

**Decision**: Parse bounded byte responses with the standard library after
rejecting DTD/entity declarations and enforcing a fixed response-size ceiling.
Validate the root local name and namespace family before reading content. Keep
namespace URI, document mRID, revision number, created timestamp, process,
area, and time-series identity in source evidence.

Support the fixed-position curve form and the variable-sized-block form only
when positions are monotone, resolution is explicit, and the next point or
period end determines every interval unambiguously. Select the highest revision
for repeated versions of the same document mRID; record superseded evidence.
Exact duplicate observations are reported and may collapse only when semantic
identity and normalized values match. Conflicting duplicates fail.

**Rationale**: ENTSO-E uses versioned IEC 62325 XML namespaces, so hard-coding
one namespace string would be brittle. Namespace-aware local-name parsing plus
a root/schema allowlist preserves validation without tying the artifact to the
source XML version. Bounded input and disabled DTD/entity processing avoid an
unnecessary XML-security dependency.

**Rejected alternatives**:

- Namespace-blind descendant searches with no root validation: they can accept
  acknowledgement or unrelated market documents as data.
- Silent last-write-wins duplicates: this hides source conflicts.
- General-purpose XML object binding: unnecessary for three document profiles.

## Decision 5: Use immutable JSON artifacts with two fingerprints

**Decision**: `MarketDataArtifact` schema v1 is human-inspectable JSON. It
contains normalized values and metadata but never a raw response. Every source
response has a SHA-256 digest, sanitized request identity, document evidence,
and retention/license record. A permitted raw response is an optional sidecar
with a relative locator and a digest verified during load.

Two hashes serve different purposes:

- `content_fingerprint`: canonical normalized series, temporal semantics,
  units, profile, source document identities, and revisions. It excludes
  retrieval time, lineage, artifact identity, and sidecar locator. Refresh uses
  it to detect no-change.
- `artifact_fingerprint`: the entire canonical serialized manifest except its
  own field. It covers retrieval time, content fingerprint, lineage, retention
  metadata, and sidecar references and is verified on every load.

A changed refresh creates a new artifact linked by the predecessor artifact
fingerprint. A no-change refresh writes nothing. Revisions are compared only
for matching source, endpoint, document mRID/type, semantic series, and covered
period; a lower matching revision rejects the whole refresh.

**Rationale**: One hash cannot both ignore volatile retrieval provenance for
change detection and protect the complete stored manifest. Separate hashes
make those meanings explicit and preserve immutable lineage.

**Rejected alternatives**:

- Parquet as the only artifact: efficient but less inspectable for a one-day
  fixture and awkward for nested document provenance.
- Retrieval timestamp in the content comparison: every refresh would appear
  changed even when source data did not change.
- Raw XML embedded as base64: violates the canonical boundary and bloats every
  offline consumer.

## Decision 6: Preserve UTC computation and local delivery identity together

**Decision**: Every interval has aware `start_utc` and `end_utc` values plus
`Europe/Paris` local start/end labels, offsets, and fold markers. UTC intervals
are authoritative for ordering and energy integration. Local fields are
authoritative for product labels and DST auditability. Intervals are always
start-inclusive/end-exclusive.

The reference profile accepts hourly A44 values and constructs four-hour FCR
blocks only from source intervals that exactly cover one declared product
block and have compatible product identity and units. Finer A81/A89 source
intervals may collapse only through an explicit recorded conversion when all
constituent intervals cover the block with no gap/overlap and their conversion
reconciles exactly. No averaging or forward fill is inferred.

Market artifacts may represent 23- or 25-hour local days if source intervals
are unambiguous. The 24-hour reference replay rejects a DST day whose hourly,
15-minute, four-hour, and 10-second grids do not map as exact integers. The
selected demonstration day is a non-transition summer day.

**Rationale**: UTC alone loses market-delivery labels; naive local time loses
the repeated-hour distinction. Both are required to audit source data and
align settlement.

## Decision 7: Keep activation as a separate artifact and normalize frequency explicitly

**Decision**: `RegulationActivationTrace` schema v1 is independent of the
market artifact. It accepts either already interval-average normalized values
or point/setpoint observations with an explicit conversion mode. The real
fixture uses RTE's 10-second France grid-frequency observations and the cited
reference normalization:

```text
xi = clip((50.0 Hz - frequency_hz) / 0.2 Hz, -1, 1)
```

Each timestamped observation is declared a left-held setpoint for the following
half-open 10-second interval. The normalized left-held value is therefore the
canonical interval-average activation for that interval. Positive `xi`
corresponds to low frequency and requests upward/discharge FCR.

For the selected local day 2022-08-19, the inspected raw reference file has
8,640 observations from `00:00:00` through `23:59:50`, no duplicate timestamp,
no non-10-second step, and frequency range 49.9234--50.0547 Hz. The importer
still validates these invariants; the counts are evidence, not a bypass.

The reference notebook's behavior of keeping one duplicate and filling gaps
with nominal 50 Hz is intentionally **not** migrated. Gaps, duplicates, an
ambiguous source timezone, or a missing conversion mode fail.

**Rationale**: This follows the robust-storage-bidding baseline without
mislabeling ENTSO-E A83/A84 as a physical FCR command. It also turns the point
versus interval-average issue into explicit, reviewable provenance.

**Reference evidence**:

- `lauinger/robust-storage-bidding` commit
  `7e44738bb30e5c8204efe40103b9be4c2203685c`
- `data_processing/RTE_frequencies.ipynb` for source and droop normalization
- `data_processing/freq_data/RTE_Frequence_2022_08.txt` for the selected raw
  observations
- [RTE public-data reuse terms](https://www.services-rte.com/en/general-terms-and-conditions-of-use.html)

## Decision 8: Reuse the existing battery physics and convert signs once

**Decision**: Schedules and battery replay use kW/kWh because the current
`BatteryComponent` and `apply_power_request` contracts use those units. Market
volume remains MW, energy price remains EUR/MWh, and FCR price remains
EUR/MW/h; volume and settlement convert by exactly 1,000 at their boundary.

Open Energy Lab positive battery power means charge. With charge-positive
baseline `p_base`, non-negative reserve `r`, and canonical activation `xi`, the
requested combined power is:

```text
p_requested = p_base - xi * r
```

Each 10-second request passes through the existing battery transition. The
stacked replay derives deterministic saturation causes by comparing the
request, power-clamped request, available SOC energy, and delivered power. It
may report both a power and SOC cause when both constrain a sample. It does not
change the existing transition equation or global sign convention.

Commitment validation checks:

```text
p_base - r >= -P_discharge
p_base + r <=  P_charge
r / 1000 <= contracted_fcr_volume_mw
```

It also requires one compatible A89 price and A81 volume for every commitment
block. These are immediate power/market checks, not a claim of robust SOC
feasibility for all possible signals.

**Rationale**: Reusing `src/open_energy_lab/simulator/battery.py` is the most
direct path to zero-FCR physical parity and avoids a second battery model.

**Reference evidence**:

- `src/open_energy_lab/simulator/battery.py`
- external `code/01_datastruct.jl` for the reference positive-discharge sign,
  10-second step, and battery defaults
- external `code/02_model.jl` for symmetric reserve power envelopes and
  reference price loading

## Decision 9: Attribute FCR delivery relative to the accepted baseline

**Decision**: During nonzero FCR commitment:

```text
requested_fcr_kw = -xi * r
delivered_fcr_kw = delivered_combined_kw - p_base
tracking_error_kw = requested_fcr_kw - delivered_fcr_kw
non_delivery_kwh = abs(tracking_error_kw) * duration_h
```

Signed and absolute tracking error, undelivered energy, causes, and contiguous
events are retained. With `r == 0`, requested/delivered FCR response,
non-delivery, and FCR penalty are exactly zero; a physically clamped energy
baseline is a separate baseline-delivery diagnostic.

**Rationale**: The accepted day-ahead baseline is the service performance
reference. Reallocating a combined shortfall after the fact would make
settlement dependent on an undocumented attribution heuristic and could break
zero-FCR compatibility.

## Decision 10: Keep first-release settlement schedule-based and explicit

**Decision**: For interval duration `h`:

```text
energy_revenue_eur = -p_base_kw / 1000 * h * price_eur_per_mwh
fcr_revenue_eur = r_kw / 1000 * h * price_eur_per_mw_h
throughput_kwh = sum(abs(delivered_combined_kw) * activation_duration_h)
total_profit_eur = energy_revenue_eur + fcr_revenue_eur - penalty_eur
```

The only built-in nonzero research penalty profile in v1 is a declared
`EUR/kWh` rate applied to absolute FCR non-delivery energy and summed per
activation interval. Omitting the rule means exactly zero penalty. Capacity
revenue is not silently reduced by delivery. Activation energy, imbalance,
degradation cost, and terminal-SOC value are reported as not modeled.

The optional terminal SOC target reports signed/absolute deviation and
tolerance compliance only. It does not alter replay or settlement.

**Rationale**: These equations are auditable, reproduce the manual fixture,
and avoid inventing a French non-performance or activation-energy settlement
profile that is outside the feature.

## Decision 11: Keep deterministic baselines outside optimization

**Decision**:

- Arbitrage-only uses the existing current-price threshold controller output.
- Regulation-only uses a zero energy schedule, caller-fixed FCR capacity, and
  initial stored energy
  `(y_max + eta_charge * eta_discharge * y_min) /
  (1 + eta_charge * eta_discharge)`, with no recovery dispatch.
- Stacked mode first obtains the existing deterministic arbitrage request and
  clips it to `[-P_discharge + r, P_charge - r]`. It does not inspect future
  activation and does not claim robust SOC feasibility.

**Rationale**: These are comparison schedules, not bidding policies. They keep
the boundary ready for the following robust-bidding feature without embedding
optimization in market ingestion or simulation.

## Decision 12: Select the 2022-08-19 France delivery day

**Decision**: The selected delivery period is:

```text
local:  [2022-08-19T00:00:00+02:00, 2022-08-20T00:00:00+02:00)
UTC:    [2022-08-18T22:00:00Z,      2022-08-19T22:00:00Z)
```

Pre-screening against the cited external reference found 24 hourly French
day-ahead values, six four-hour French FCR price blocks, and a complete raw
10-second RTE frequency day. The feature must still acquire and validate A44,
A81, and A89 through its own ENTSO-E producer before the market fixture is
accepted. The committed fixture records the ENTSO-E document revisions,
response digests, retrieval time, legal-reuse basis, normalization version,
and activation source/commit.

The fixed demonstration configuration is:

- 100 kWh battery, 10--90 kWh operating range, 50 kWh initial energy
- 50 kW charge and discharge limits; 0.92 charge/discharge efficiency
- 5 kW deterministic threshold-controller requests below 475 EUR/MWh or above
  540 EUR/MWh, then headroom clipping
- fixed 5 kW symmetric FCR commitment in all six eligible blocks
- zero penalty and optional 50 kWh report-only terminal target

Expected trace fingerprint and totals are recorded only after fixture
generation; they are never inferred in this plan.

**Rationale**: The day is within the robust-storage-bidding backtest, is not a
DST transition, exercises large French price variation, and has complete
source-explicit high-resolution frequency observations.

**Blocking gate**: If credentialed ENTSO-E acquisition does not prove complete
compatible A44/A81/A89 source data and reusable normalized-fixture terms for
this exact day, no real fixture may be published under Feature 010 until the
selected period is amended through the specification workflow.

## Decision 13: Make routine validation completely offline

**Decision**: Unit tests use synthetic XML and injected transports. Integration
tests use committed canonical artifacts. The live ENTSO-E check is explicitly
selected, requires a caller-provided token, and may verify source compatibility
without becoming a routine test dependency. Tests patch the transport boundary
to assert zero network calls during artifact load, schedule generation,
simulation, settlement, and offline examples.

The full RTE activation regeneration is also explicitly selected: it accepts a
caller-supplied local raw file, verifies and records its digest, and never
downloads source data implicitly. Routine integration tests validate the
committed normalized activation artifact without reopening the external raw
file. The hardware-specific reference benchmark is selected separately from
routine correctness checks and follows the protocol in `plan.md`.

The required matrix includes manual arithmetic, real replay twice, zero FCR,
zero energy, token sentinel, retry classes, acknowledgement/empty responses,
gaps, exact/conflicting duplicates, revision regression, wrong area/product,
unit/resolution mismatch, 23/25-hour delivery days, activation range and
alignment, sidecar digest mismatch, incomplete product blocks, power/SOC
saturation, aggregation conservation, terminal-target report-only behavior,
and import/no-legacy boundaries.

**Rationale**: Network availability and a private token are acquisition
concerns, not prerequisites for reproducible simulation review.

## Source And License Notes

- ENTSO-E publishes a list of data available for free reuse under CC BY 4.0;
  the exact current list and attribution requirement must be captured when the
  real fixture is generated. See [ENTSO-E legal terms](https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions).
- RTE's terms permit reuse of public data with source attribution. The selected
  activation fixture must identify RTE and the reference repository's exact
  transformation provenance. See [RTE terms](https://www.services-rte.com/en/general-terms-and-conditions-of-use.html).
- The external baseline is reference evidence, not a dependency. See
  [lauinger/robust-storage-bidding](https://github.com/lauinger/robust-storage-bidding)
  and [Lauinger, Cote, and Sun, arXiv:2510.10856v2](https://arxiv.org/abs/2510.10856).
