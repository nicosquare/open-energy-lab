# ENTSO-E Transparency Platform R3 Integration

This document is the operational contract for Feature 010's explicit French
market-data producer. It records the API generation, exact requests, response
normalization, authentication boundary, and redistribution policy used by Open
Energy Lab.

## Version And Endpoint

Open Energy Lab targets the ENTSO-E Transparency Platform **R3** REST API at
`https://web-api.tp.entsoe.eu/api`. The endpoint path is unversioned; “R3” is
the platform/data-item generation, not a URL segment. The implementation was
checked on 2026-08-22 against the official Postman collection published on
2026-01-16 and the current 17.1.B&C data-item documentation.

The validated XML families are:

| Data | Root | Namespace baseline |
| --- | --- | --- |
| Day-ahead prices | `Publication_MarketDocument` | IEC 62325 `451-3:publicationdocument` family |
| Contracted reserve volume and price | `Balancing_MarketDocument` | `urn:iec62325.351:tc57wg16:451-6:balancingdocument:4:4` |

The parser validates the root and namespace family before reading values. An
acknowledgement, problem document, unrelated namespace, or legacy
`ReserveAllocationResult_MarketDocument` is not accepted as market data.

## Exact Requests

All intervals are start-inclusive/end-exclusive UTC intervals. `periodStart`
and `periodEnd` use `yyyyMMddHHmm` without punctuation. Parameter names are
case-sensitive.

### A44 day-ahead prices

| Parameter | Value |
| --- | --- |
| `documentType` | `A44` |
| `processType` | `A01` |
| `in_Domain` | `10YFR-RTE------C` |
| `out_Domain` | `10YFR-RTE------C` |
| `periodStart` | Requested/enclosing UTC start |
| `periodEnd` | Requested/enclosing UTC end |

The current response may omit `process.processType`; if present it must be
`A01`. Values come from `Point/price.amount`, with `EUR/MWh` preserved and
`PT1H` or the equivalent `PT60M` normalized to canonical `PT1H`.

### Combined A81 contracted reserves (17.1.B&C)

| Parameter | Value |
| --- | --- |
| `documentType` | `A81` |
| `businessType` | `B95` |
| `processType` | `A52` |
| `Type_MarketAgreement.Type` | `A01` |
| `controlArea_Domain` | `10YFR-RTE------C` |
| `periodStart` | Requested/enclosing UTC start |
| `periodEnd` | Requested/enclosing UTC end |

`psrType` is deliberately omitted from the request. The response itself must
prove business type `B95`, process `A52`, symmetric direction `A03`, market
agreement `A01`, mixed PSR type `A03`, and the France area. If a standard
market product is present it must be `A01`; its absence is preserved rather
than inferred. A separate A89 request is not made: R3 publishes contracted
reserve quantity and procurement price together in A81.

A sanitized example for the selected day is:

```text
GET https://web-api.tp.entsoe.eu/api
  ?documentType=A81
  &businessType=B95
  &processType=A52
  &Type_MarketAgreement.Type=A01
  &controlArea_Domain=10YFR-RTE------C
  &periodStart=202208182200
  &periodEnd=202208192200
  &securityToken=<ENTSOE_API_TOKEN>
```

The token is shown only as a placeholder. Code constructs the token-free
parameter mapping first and adds `securityToken` only inside the HTTPS
transport.

## Authentication And Dotenv

Acquisition requires `ENTSOE_API_TOKEN`. Copy `.env.example` to the ignored
repository-root `.env`, replace the placeholder, and pass `--env-file .env` to
the explicit example consumer, or export the variable in the calling shell.
The dotenv reader accepts only that key, performs no interpolation, and does
not mutate the process environment.

The token must never appear in a persistable request, artifact, raw-response
digest input, filename, cache identity, command argument, diagnostic, log,
test fixture, or documentation example. Artifact loading, schedule building,
and replay never read `.env` and have no transport-capable argument.

## XML, ZIP, And Normalization

The transport accepts XML or `application/zip` and caps the compressed response at 10 MiB.
ZIP extraction permits at most 16 XML files and 10 MiB total uncompressed
content. It rejects encrypted entries, duplicate names, directories, absolute
or traversing paths, nested archives, non-XML members, malformed archives, and
declared or observed size overflow. Each parsed document records its optional
archive member while raw evidence records the digest and media type of the
whole HTTP response.

The combined A81 sparse `A03` curve is expanded at its declared ISP
resolution. Every change point must contain both `quantity` and
`procurement_Price.amount`; neither value is inferred from another point or
document. Canonical PT4H blocks are formed only when a complete four-hour run
has identical product, quantity, and price semantics in every ISP.

The source price unit is `EUR/MW/ISP`. Conversion is duration-based:

```text
EUR/MW/h = source_value / ISP_duration_hours
```

For `PT30M`, `ISP_duration_hours = 0.5` and the factor is `2`. The artifact
records the formula, source resolution, duration, factor, and exact source
field. Both FCR canonical series reference the same selected A81 document.

Transient connection failures, HTTP 408/429, and 5xx responses receive at most
three deterministic attempts. Permanent 4xx responses fail after one attempt.
Any archive, XML, semantic, unit, curve, coverage, or PT4H reconciliation
failure aborts the whole acquisition before manifest publication.

## Retention, Attribution, And Redistribution

Real acquisition output is local research material under the Git-ignored
`artifacts/` directory. Routine tests use project-authored synthetic XML; live
tests are opt-in and do not snapshot production responses.

ENTSO-E's current free-reuse list, last modified 18 October 2023 and rechecked
through the legal page on 22 August 2026, places contracted reserve amount and
price under CC BY 4.0. Redistributed A81-derived values therefore require
ENTSO-E attribution and an indication of changes. Article 12.1(d) day-ahead
prices are absent from that list. ENTSO-E's current Energy Prices page names
power exchanges or TSOs as the Primary Owner; RTE's French market-data page
identifies the displayed French spot prices as EPEX SPOT data and states that
copying or distribution requires the power exchange's prior consent.

The repository owner confirmed on 2026-08-22 that this is a private repository
and limited to authorized collaborators. The exact Feature 010 normalized
market, activation, and derived replay fixtures may therefore be stored here
only as restricted private-repository data. That decision does not claim public
redistribution permission for A44 values. The fixtures are not offered under
the project license and must not enter a public repository, fork, mirror,
package, release, public CI artifact, or external artifact store. They must be
removed before repository visibility is changed to public.

The staging consumer performs no network access, requires explicit
acknowledgement of the private/restricted repository, preserves normalized
content, and emits a new artifact fingerprint carrying
`repository_storage=permitted_private_restricted` and
`repository_publication=prohibited`. Raw responses remain digest-only. The
complete storage and removal policy is recorded in
[Restricted French reference fixtures](../migration/restricted-reference-fixtures.md).

Researchers may run the documented producer privately with their own account
and token. Code, request documentation, provenance schemas, and synthetic
fixtures remain redistributable independently of the restricted real-data
fixtures.

## Feature 011 Complementary Composition

Feature 011 does not add an ENTSO-E aFRR or mFRR acquisition profile. RTE
Balancing Energy 5.2 remains the primary verified source for the restoration
observations. The only supported first-release ENTSO-E composition is an
already acquired Feature 010 artifact whose profile is exactly
`fr-day-ahead-symmetric-fcr-v1`.

A restoration study may select only that artifact's A44 `day_ahead_price`
series, and only when the series covers the study interval under the same UTC
half-open convention. The selection records the Feature 010 artifact identity,
artifact fingerprint, exact `day_ahead_price` series fingerprint, requested
coverage, and redistribution policy in a `RestorationStudyBundle`. The bundle
references observations; it does not copy, merge, rename, resample, or
reinterpret them. The RTE artifact remains an independent one-source artifact.

The A44 series continues to use Feature 010's unchanged fetch, immutable
refresh, and zero-network offline lifecycle documented above. Feature 011 does
not issue a substitute ENTSO-E request, widen the closed A44/A81 schema, or
create a new restoration fetch profile. If the caller has no existing
time-compatible Feature 010 artifact, the composition branch reports that no
compatible profile was selected and proceeds without ENTSO-E data. ENTSO-E is
never an automatic fallback for an absent, null, incompatible, or failed RTE
series, and matching timestamps alone never establish matching semantics.

The selected A44 price retains its original ownership and redistribution
status. In particular, composing it into a study does not convert restricted
EPEX SPOT-derived values into publicly redistributable data. The bundle adopts
the strictest policy of its referenced artifacts.

## Official References

- [Official ENTSO-E Postman collection](https://documenter.getpostman.com/view/7009892/2s93JtP3F6)
- [Amount and Prices Paid of Balancing Reserves Under Contract 17.1.B&C](https://transparencyplatform.zendesk.com/hc/en-us/articles/12826309684756-Amount-and-Prices-Paid-of-Balancing-Reserves-Under-Contract-17-1-B-C)
- [Request endpoint](https://transparencyplatform.zendesk.com/hc/en-us/articles/15696677194644-Request-Endpoint)
- [Request parameters and UTC guidance](https://transparencyplatform.zendesk.com/hc/en-us/articles/15696716612372-Request-Parameters)
- [Legacy-publication archive migration](https://transparencyplatform.zendesk.com/hc/en-us/articles/41986091964305-Archives-for-legacy-Transparency-Platform-publications)
- [ENTSO-E legal terms](https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions)
- [List of data available for free reuse](https://transparency.entsoe.eu/content/static_content/download?path=%2FStatic+content%2Fterms+and+conditions%2F231018_List_of_Data_available_for_reuse.pdf)
- [ENTSO-E Energy Prices 12.1(d) ownership profile](https://transparencyplatform.zendesk.com/hc/en-us/articles/16647234190100-Energy-Prices-12-1-D)
- [RTE French spot-price ownership and use terms](https://www.rte-france.com/en/data-publications/eco2mix/market-data)
