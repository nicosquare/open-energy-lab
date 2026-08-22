# ENTSO-E Market-Data Contract

## Ownership

`open_energy_lab.market.entsoe` owns authenticated source access, France query
construction, retries, XML/ZIP classification/parsing, normalization, source
diagnostics, and handoff to atomic artifact publication. ENTSO-E transport or
XML types never enter simulator or controller APIs.

## Public Operations

```python
fetch_entsoe_market_data(
    request: EntsoeMarketDataRequest,
    *,
    api_token: str,
    destination_dir: Path,
    transport: EntsoeTransport | None = None,
) -> MarketDataFetchResult

refresh_entsoe_market_data(
    request: EntsoeMarketDataRequest,
    *,
    current_artifact: MarketDataArtifact,
    api_token: str,
    destination_dir: Path,
    transport: EntsoeTransport | None = None,
) -> MarketDataRefreshResult
```

The names express the required behavior; implementation may use equivalent
typed names while preserving the contract.

There is no token-bearing client object and no implicit `fetch_on_missing`
option. Offline use calls `load_market_data_artifact` from the artifact
contract and never reaches this module's transport.

## France Profile

The v1 profile accepts only:

- Area EIC `10YFR-RTE------C`
- `A44` day-ahead price for the France bidding zone
- combined `A81` contracted reserve volume and price with process `A52`, market
  agreement `A01`, business type `B95`, symmetric direction `A03`, standard
  product `A01` when returned, and mixed PSR type `A03`
- Market timezone `Europe/Paris`
- Canonical units `EUR/MWh`, `MW`, and `EUR/MW/h`

A44 source documents may spell the exact hourly duration as either `PT1H` or
`PT60M`; source evidence preserves the returned spelling and canonical output
uses `PT1H`. This is duration equivalence, not resampling.

Every source parameter and every returned semantic field are validated and
preserved separately. Returned source semantics take precedence over an
assumption based only on the request.

The A44 query window records process `A01`, but Article 12.1(d) response
documents are permitted to omit `process.processType`, as specified by the
ENTSO-E extraction profile. That absence is preserved as null in source
document evidence. If an A44 process is returned it must be `A01`; combined
A81 response documents must return `A52`. The producer never issues A89.

## Period Contract

- Caller period is an aware UTC half-open interval.
- Start must precede end and both must be finite valid instants.
- The adapter queries enclosing Europe/Paris delivery days in deterministic
  chronological order and retains the exact caller request separately.
- Source documents may cover complete intervals outside the request; actual
  coverage records that fact.
- Fetch can preserve a partial boundary product period, but it cannot publish
  unless every instant in the requested period is covered by all three required
  series without gap or conflict.
- Replay completeness is a later simulator validation and does not cause the
  producer to trim or prorate the artifact.

## Secret Contract

- Empty or rejected tokens fail acquisition.
- The token is accepted only as the keyword-only operation argument.
- It must not participate in request equality, representations, cache keys,
  identifiers, filenames, logs, exceptions, metrics, response recordings,
  notebooks, source metadata, or artifact fingerprints.
- Wire request creation happens inside the transport and uses HTTPS only.
- Raw transport exceptions are caught and replaced with sanitized typed errors.
- A sentinel-token test scans produced files, paths, captured stdout/stderr,
  logs, exception text, and object representations and must find zero matches.

## Transport And Retry Contract

The transport is synchronous and injected for tests. For each source window:

- Total attempts are at most three, including the first.
- Retry only timeout, connection interruption, HTTP 408/429, and 5xx classes.
- Authentication rejection and other permanent 4xx classes receive one attempt.
- A valid `Retry-After` from 0 through 120 seconds is honored.
- An invalid or over-bound delay is diagnosed without an unbounded sleep.
- Otherwise waits are deterministically one second and then two seconds.
- No source windows execute concurrently in v1.
- Every response must remain below the configured byte ceiling before parse.

Attempt diagnostics contain source, document, window, attempt number, status or
acknowledgement class, delay decision, and final outcome. They contain no full
wire URL or header/body material.

## XML And ZIP Contract

- Reject DTD or entity declarations and over-bound input before parse.
- Accept XML or ZIP with bounded compressed/uncompressed sizes and member
  count; reject encrypted, duplicate, directory, traversal, nested-archive,
  non-XML, malformed, and over-bound members.
- Preserve a safe archive-member path in source-document provenance.
- Accept only validated ENTSO-E data root/namespace families for A44 and A81.
- Classify acknowledgement/problem/empty responses explicitly.
- Require document mRID, revision, created time, profile-applicable process, area, period,
  resolution, unit, series identity, and point values needed by the profile.
- Support fixed-position A44 and sparse A03 A81 curves only when their
  intervals expand unambiguously.
- Select the highest revision for repeated versions of one document mRID and
  retain evidence of superseded versions.
- Collapse exact duplicates only when source identity, interval, unit, and
  normalized value agree; record the collapse.
- Reject conflicting duplicates, gaps, overlaps, invalid positions, unknown
  curve types, unexpected resolutions, wrong areas/products/directions,
  incompatible units, and non-finite values.
- Preserve negative day-ahead prices.

## Unit And Product Conversion

Any source-to-canonical conversion records source unit/resolution, canonical
unit/resolution, factor/formula, constituent intervals, product evidence, and
exact source value field. A81 quantity and procurement price must occur at the
same change points. `EUR/MW/h = source_value / ISP_duration_hours`; finer ISPs
form a PT4H block only when complete and identical in product, volume, and
price semantics. Ambiguity fails instead of being averaged or inferred.

## Atomicity

The producer builds and validates the complete candidate in memory. Permitted
sidecars and the manifest are staged as temporary siblings. The manifest is
atomically published last. A failed window, parse, semantic check, fingerprint,
sidecar write, or revision check yields no complete artifact and no manifest
that references an incomplete sidecar set.

## Refresh Outcomes

- `unchanged`: normalized content and comparable revisions are unchanged; no
  artifact is written.
- `published`: validated content changed; a new immutable artifact links to the
  predecessor and the predecessor is not overwritten.
- `revision_regression`: at least one comparable returned revision is lower;
  the current artifact remains untouched and no candidate is published.

Different document mRIDs, series identities, or covered periods are not ordered
as one revision sequence.

## Required Failure Diagnostics

Every failure identifies source, sanitized query window, required series,
requested period, observed coverage/resolution/unit where available, expected
profile, and retry/final status. Distinct typed failures cover at least:

- missing/invalid authentication
- acknowledgement or empty response
- transient exhaustion and permanent HTTP failure
- malformed/unsafe/over-bound XML or ZIP
- missing series or field
- wrong area/product/process/direction
- gap, overlap, or conflicting duplicate
- unexpected resolution or incompatible unit
- invalid DST coverage
- raw sidecar or artifact publication failure
- refresh revision regression

No failure may include the token.
