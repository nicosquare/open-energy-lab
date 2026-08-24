# RTE Balancing Energy 5.2 Integration

This document is the operational source contract for Feature 011's French
aFRR and mFRR market-data producer. It records the exact API version, OAuth
boundary, requests, fields, time rules, normalization, error behavior, and
distribution constraints used by Open Energy Lab.

RTE publishes control-area observations. These records are useful market and
system context, but they are not instructions sent to an individual battery.
Open Energy Lab can turn selected requested-volume observations into a
separately fingerprinted, explicitly labelled simulation scenario; it never
silently treats an RTE record as observed BESS dispatch.

## Version, Ownership, And Product Meaning

The source is the RTE Balancing Energy API, catalog version **5.2**, owned and
published by RTE Réseau de Transport d'Électricité. The stable production URL
uses the path segment `v5`; catalog version `5.2` and path version `v5` are
recorded independently rather than conflated.

In non-technical terms:

- **aFRR** is automatic restoration: the control area continuously corrects a
  remaining imbalance after the fastest frequency response. The public PT15M
  values summarize area needs and activations; they are not the faster control
  signal that an individual qualified asset would track.
- **mFRR SA** is manual restoration scheduled activation: RTE requests energy
  for a planned quarter-hour activation through the balancing process.
- **mFRR DA** is manual restoration direct activation: RTE can call energy
  directly when a scheduled platform result is not the appropriate path. DA
  can be sparse or source-null and is never fabricated by this integration.

The closed source profiles are:

| Profile | Resource | JSON root/list | Product | Resolution |
| --- | --- | --- | --- | --- |
| `fr-rte-balancing-energy-v5.2-afrr-v1` | `standard_afrr_data` | `picasso` / `picasso_mesures` | aFRR | PT15M |
| `fr-rte-balancing-energy-v5.2-mfrr-v1` | `standard_mfrr_data` | `mari` / `mari_mesures` | mFRR SA and DA context | PT15M |

## OAuth And Local Environment Boundary

Explicit acquisition uses OAuth client credentials:

```text
POST https://digital.iservices.rte-france.com/token/oauth/
Authorization: Basic <base64(RTE_CLIENT_ID:RTE_CLIENT_SECRET)>
Content-Type: application/x-www-form-urlencoded
Accept: application/json

grant_type=client_credentials
```

The returned short-lived access token exists only in memory. The active data
request carries `Authorization: Bearer <runtime-access-token>` in its transient
header. Authentication responses, Basic and Bearer values, token expiry, and
credentials are not request identities or market evidence and are never
persisted, logged, fingerprinted, or included in exceptions.

Package code accepts `client_id` and `client_secret` only as keyword-only
arguments to an explicit fetch or refresh operation. It never opens `.env`.
The example consumer may read only `RTE_CLIENT_ID` and `RTE_CLIENT_SECRET` from
the caller-selected environment file. Exported environment values take
precedence, interpolation is disabled, and the process environment is not
mutated. Copy `.env.example` to the ignored repository-root `.env` for local
use; never commit it. Offline artifact loading, control, replay, settlement,
tests, and notebook execution do not read credentials or initialize networking.

## Exact Data Requests

The data origin is `https://digital.iservices.rte-france.com`. The endpoint
stored in a token-free request is the pinned HTTPS origin and exact path only;
userinfo, query text, fragments, credentials, and tokens are rejected.

Sanitized aFRR example:

```text
GET /open_api/balancing_energy/v5/standard_afrr_data
    ?start_date=2026-08-20T00%3A00%3A00Z
    &end_date=2026-08-20T01%3A00%3A00Z
Host: digital.iservices.rte-france.com
Accept: application/json
Authorization: Bearer <runtime-access-token>
```

Sanitized mFRR example:

```text
GET /open_api/balancing_energy/v5/standard_mfrr_data
    ?start_date=2026-08-15T10%3A15%3A00Z
    &end_date=2026-08-15T10%3A30%3A00Z
Host: digital.iservices.rte-france.com
Accept: application/json
Authorization: Bearer <runtime-access-token>
```

`start_date` is inclusive and `end_date` is exclusive. Both must be aware UTC
instants aligned to a 15-minute boundary, with start before end. Open Energy Lab
accepts at most 31 days per caller request and splits it deterministically into
contiguous source calls of at most one day. Publication remains atomic for the
whole caller interval. The adapter does not guess whether an unpublished or
future period should exist: the caller selects a historical period and exact
root/row coverage is required. An empty, partial, gapped, overlapping, or
duplicate response fails rather than being filled.

## aFRR Field Contract

The root must declare `resolution=PT15M`, source volume unit `MW`, and source
price unit `EUR/MWh`. Every aFRR row must contain both bounds and every field
below as a finite number. Each source field becomes its own series; no netting,
substitution, interpolation, or price-to-command inference occurs.

| Canonical series ID | Exact RTE field | Direction | Meaning | Unit | Identity |
| --- | --- | --- | --- | --- | --- |
| `afrr_requested_need_upward` | `upward_afrr_requested_need` | Upward | French control-area upward aFRR need requested | MW | Observed area aggregate; reference scenario driver |
| `afrr_requested_need_downward` | `downward_afrr_requested_need` | Downward | French control-area downward aFRR need requested | MW | Observed area aggregate; opposing driver checked separately |
| `afrr_activated_for_fr_upward` | `upward_afrr_activated_volume_for_fr` | Upward | aFRR activated for France, irrespective of activation location | MW | Observed comparison only |
| `afrr_activated_for_fr_downward` | `downward_afrr_activated_volume_for_fr` | Downward | aFRR activated for France, irrespective of activation location | MW | Observed comparison only |
| `afrr_activated_in_fr_upward` | `upward_afrr_activated_volume_in_fr` | Upward | aFRR physically activated in France | MW | Observed comparison only |
| `afrr_activated_in_fr_downward` | `downward_afrr_activated_volume_in_fr` | Downward | aFRR physically activated in France | MW | Observed comparison only |
| `afrr_weighted_average_price_upward` | `upward_weighted_average_price_afrr_activated_for_fr` | Upward | Weighted-average price of upward aFRR activated for France | EUR/MWh | Observed area price; optional explicit scenario proxy |
| `afrr_weighted_average_price_downward` | `downward_weighted_average_price_afrr_activated_for_fr` | Downward | Weighted-average price of downward aFRR activated for France | EUR/MWh | Observed area price; optional explicit scenario proxy |

All rows are preserved as PT15M interval averages. The only source
normalization is parsing an explicit timestamp offset to the equivalent UTC
instant, chronological row ordering while retaining `source_row`, and
structural conversion into independently fingerprinted series. Values and
units are unchanged.

The fixed reference hour contains four chronological upward requested needs:
`425`, `315`, `290`, and `345 MW`; downward need is zero in all four intervals.
These numbers describe the French area. They become simulated BESS requests
only through the separate fixed-fraction mapping documented below.

## mFRR Field Contract

The root must declare `resolution=PT15M`, `MW`, and `EUR/MWh`. RTE emits one
row per direction and interval. `UPWARD` and `DOWNWARD` are normalized only for
case; the directions remain separate. The adapter preserves field absent,
source JSON null, and numeric zero as three different states.

| Canonical series IDs, each suffixed `_upward` or `_downward` | Exact RTE field | Process/meaning | Unit | Identity |
| --- | --- | --- | --- | --- |
| `mfrr_sa_requested_volume_*` | `total_requested_volume_SA` | SA volume requested by RTE | MW | Observed area aggregate; selected reference driver |
| `mfrr_sa_satisfied_need_*` | `total_satisfied_need_SA` | SA need satisfied, including applicable platform outcome | MW | Observed comparison only |
| `mfrr_sa_activated_volume_*` | `total_activated_volume_SA` | SA volume activated in France | MW | Observed comparison only |
| `mfrr_da_requested_volume_*` | `total_requested_volume_DA` | DA volume requested by RTE | MW | Observed area aggregate; never inferred from SA |
| `mfrr_da_satisfied_need_*` | `total_satisfied_need_DA` | DA need satisfied | MW | Observed comparison only |
| `mfrr_da_activated_volume_*` | `total_activated_volume_DA` | DA volume activated in France | MW | Observed comparison only |
| `mfrr_clearing_price_*` | `clearing_price` | Directional clearing-price context | EUR/MWh | Observed area price; optional explicit scenario proxy |
| `mfrr_settlement_price_current_*` | `settlement_price_current` | Current directional settlement-price context | EUR/MWh | Observed area price; optional explicit scenario proxy |
| `mfrr_settlement_price_previous_*` | `settlement_price_previous` | Previous directional settlement-price context | EUR/MWh | Observed comparison; not silently substituted |
| `mfrr_submitted_offer_volume_*` | `total_volume_submitted_offers` | Submitted-offer volume | MW | Observed market context only |
| `mfrr_filtered_offer_volume_*` | `total_volume_filtered_offers` | Filtered-offer volume | MW | Observed market context only |

`requested_activated_volumes_by_prices` remains nested evidence. Each entry
preserves `activation_type`, `requested_price`, `requested_volume`, and
`satisfied_need` independently. Activation type may be `SA`, `DA`, or source
null. Requested price may be finite numeric evidence, the exact RTE meaning
code `ATP`, or source null. Null activation type is not guessed from another
field, `ATP` is not converted to a numeric price, and nested values do not
silently replace the closed series above.

The reference quarter retains both directional rows. The downward row records
`357 MW` SA requested, `300 MW` SA satisfied, and `64.83 EUR/MWh` clearing
price; the upward volumes and DA fields are source-null. Source-null DA is
reported as sparse evidence and creates no direct-activation event.

## UTC And Europe/Paris Time

Canonical identity uses continuous, start-inclusive/end-exclusive UTC. RTE
timestamps may use `Z` or another explicit offset such as `+02:00`; each is
converted to the same UTC instant. Every canonical interval also records its
`Europe/Paris` local start and end labels, UTC offsets, and fold flags. This
preserves French-market interpretation through daylight-saving gaps and folds
without duplicating or omitting a UTC interval.

No local clock value is accepted without an explicit offset. No PT15M value is
upsampled to a faster automatic-control signal, and no mFRR event timing is
deduced from an area interval. The real-data demonstrations use interval
averages and a separately declared rectangular event assumption respectively.

## From Area Observation To Derived BESS Scenario

The explicit mapping is:

```text
requested_bess_kw = requested_area_mw * 1000 * asset_allocation_fraction
```

The reference allocation fraction is fixed at `0.001` for the whole scenario.
Therefore the four aFRR values become upward/discharge requests of `-425`,
`-315`, `-290`, and `-345 kW` under the simulator's charge-positive convention.
The mFRR value becomes one declared downward/charge **scheduled** event at
`357 kW`, with zero delay, zero ramp, a 900-second hold, and zero ramp-down.
Those event-shape parameters are modelling assumptions, not fields returned by
RTE.

The mapping fingerprints its source artifact, exact driver series, allocation,
unit scale, commitment, assumptions, and transformation. It rejects a request
above the direction-compatible commitment and an aFRR interval with simultaneous
nonzero upward and downward need. Activated volumes and prices remain comparison
or explicit price-proxy observations; they never become an activation command.
Every downstream result is labelled `derived_simulation`. Area prices may be
used only through an explicit direction/product/interval-compatible mapping
labelled `scenario_proxy`, never as an observed asset invoice.

## Fetch, Refresh, Offline Load, And Retention

The three modes are explicit:

- `FETCH` acquires and publishes a new immutable one-source artifact.
- `REFRESH` requires the same request identity. Unchanged normalized content
  writes nothing; changed content creates a predecessor-linked successor and
  never overwrites the current artifact.
- Offline load validates an existing artifact through
  `open_energy_lab.market.restoration_artifact`, without importing the RTE
  adapter, reading environment variables, or opening a socket.

All required windows and series are validated in memory before publication.
Files use deterministic finite JSON, distinct content and full-artifact
fingerprints, atomic replacement, and fail-closed collision checks. A market
artifact contains exactly one source acquisition. A multi-source study uses a
bundle of artifact/series fingerprints; it never copies or merges source rows.

Raw production bodies are digest-only by default. The committed reference
artifacts record response SHA-256, byte count, media type, request window, and
retrieval time but contain no raw body or OAuth response. A raw body could only
be a separately verified restricted sidecar if source rights and project policy
explicitly allowed it; the current references have no sidecars.

## Errors And Bounded Transport

OAuth bodies are capped at 64 KiB and market responses at 10 MiB. HTTPS status,
media type, finite JSON, exact root, units, resolution, row duration, direction,
coverage, and source semantics are validated. Failures identify the sanitized
source, resource or field, requested period, observed condition, expected
condition, category, and attempt count. Diagnostics never contain credentials,
headers, raw bodies, or credential-bearing URLs.

Timeouts, connection interruptions, HTTP 408/429, and 5xx responses receive at
most three total attempts per source window, including the first. A valid
non-negative `Retry-After` is honored up to 30 seconds; otherwise deterministic
backoff is used. One in-memory token renewal is permitted after the first 401.
Authentication/authorization rejection after that renewal and all other
permanent 4xx responses fail immediately. Any failed window or semantic check
prevents complete artifact publication.

## Attribution, Terms, And Redistribution

Every artifact attributes **RTE Balancing Energy API v5.2; normalized by Open
Energy Lab** and records RTE as source owner. The RTE Services Portal terms
require source attribution for reuse of public information and place the
responsibility for respecting third-party rights on the user. Source access or
a private repository does not, by itself, grant public redistribution rights.

The owner-confirmed project policy therefore treats every normalized real RTE
fixture and deterministic derivative as private restricted research data. It
is available only to authorized collaborators and is not offered under the
repository's Apache-2.0 license. It must not enter packages, releases, public
CI artifacts, public forks or mirrors, or external artifact stores, and must
be removed or reassessed before repository visibility changes. Code,
documentation, schemas, and project-authored synthetic fixtures remain
redistributable independently. The exact governed files and fingerprints are
listed in [Restricted French reference fixtures](../migration/restricted-reference-fixtures.md).

For completeness, the fail-closed evidence vocabulary is exact: field absent,
source JSON null, and numeric zero remain different; area observations are not
commands addressed to the reference battery; `repository_publication` is
prohibited; packages, releases, public CI artifacts, public forks or mirrors
are prohibited destinations; source bodies are digest-only; and transport uses
at most three total attempts for an eligible transient failure.

## Verified Reference Evidence

The explicit production acquisition on 2026-08-23 produced:

| Resource and UTC period | Records | Raw response SHA-256 | Normalized artifact fingerprint |
| --- | ---: | --- | --- |
| aFRR `[2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)` | 4 PT15M rows | `d2496d713c7f217ff76487db2aba0b7a49479861118bea61ca3c001fbbfe2eb3` | `83f0c88e5c8d9c0f781305a9552596c3a03956588a75871e9f78e97415811516` |
| mFRR `[2026-08-15T10:15:00Z, 2026-08-15T10:30:00Z)` | 2 directional PT15M rows | `ce9d3c3d694a78776e5bdb188239f9b2ed4b711e3c389d0e89c8a47e5391d1a1` | `d2d4007fafe5138f0bfdc8d91ba232c435f9b4f7097a0cc519064011c624ca10` |

These digests prove the exact acquired bytes without redistributing those
bytes. A later digest change is evidence for semantic review, not automatic
permission to overwrite the immutable references.

## Official References

- [RTE Balancing Energy API catalog 5.2](https://data.rte-france.com/catalog/-/api/market/Balancing-Energy/v5.2)
- [RTE Balancing Energy 5.2 user guide](https://data.rte-france.com/catalog/-/api/doc/user-guide/Balancing+Energy/5.2)
- [RTE OAuth 2 guide](https://data.rte-france.eu/documents/20182/22648/EN_GuideOauth2_v5.1.pdf/54d3d183-f20f-4290-9417-bcae122b9e46)
- [RTE balancing data and product definitions](https://www.services-rte.com/en/view-data-published-by-rte/balancing.html)
- [RTE manual-frequency services](https://www.services-rte.com/en/learn-more-about-our-services/respond-to-the-manual-frequency.html)
- [RTE Services Portal general terms](https://www.services-rte.com/en/general-terms-and-conditions-of-use.html)
